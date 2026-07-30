#!/usr/bin/env python3
"""
codex_image.py - generate raster images through the Codex CLI's built-in
`image_gen` tool.

Auth: uses whatever `codex` is already logged in with (ChatGPT OAuth).
No OPENAI_API_KEY is required or used.

Images produced by the built-in tool land in
`$CODEX_HOME/generated_images/<thread_id>/`. We capture <thread_id> from the
`thread.started` event of `codex exec --json`, so harvesting is scoped to our
own run and never races with a concurrent Codex session.
"""

import argparse
import json
import os
import re
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import threading
import time
from math import gcd
from pathlib import Path

CODEX_HOME = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
GEN_ROOT = CODEX_HOME / "generated_images"
CHROMA_SCRIPT = CODEX_HOME / "skills/.system/imagegen/scripts/remove_chroma_key.py"
VENV_DIR = Path(__file__).resolve().parent.parent / ".venv"

# Friendly aspect names -> (width, height). These are gpt-image-2 legal sizes.
ASPECTS = {
    "landscape": (1536, 1024),
    "square": (1024, 1024),
    "portrait": (1024, 1536),
    "wide": (2048, 1152),
    "square2k": (2048, 2048),
    "4k": (3840, 2160),
    "4k-portrait": (2160, 3840),
}

CHROMA_BLOCK = """
BACKGROUND (mandatory, this asset will be cut out):
Render the subject on a perfectly flat solid {key} chroma-key background.
The background must be one uniform color: no shadows, no gradients, no texture,
no reflections, no floor plane, no lighting falloff. Keep the subject fully
separated from the background with crisp edges and generous padding.
Do not use {key} anywhere in the subject itself.
No cast shadow, no contact shadow, no reflection, no watermark.
"""


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def png_size(path):
    """Read (width, height) from a PNG header without any dependencies."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(26)
        if head[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        return struct.unpack(">II", head[16:24])
    except Exception:
        return None


def build_prompt(spec, count, aspect, transparent, key_color, has_inputs):
    w, h = ASPECTS[aspect]
    lines = [
        "You are acting as a headless image asset generator.",
        "",
        "Do exactly this and nothing else:",
        f"1. Call your built-in `image_gen` tool exactly {count} time(s) using the "
        "specification below.",
        "2. Do NOT create, edit, move, copy or delete any file.",
        "3. Do NOT run git, package managers, build tools, or any project command.",
        "4. Do NOT ask follow-up questions. If a detail is unspecified, choose a "
        "tasteful default and proceed.",
        "5. After the image(s) exist, reply with the single word: GENERATED",
        "",
    ]
    if has_inputs:
        lines += [
            "Attached image(s) are provided as input. Their role is described in the "
            "specification below. Use `view_image` if you need to inspect them.",
            "",
        ]
    if count > 1:
        lines += [
            f"Produce {count} DISTINCT variants of the same brief - vary composition, "
            "lighting and palette between them. Issue one separate `image_gen` call "
            "per variant.",
            "",
        ]
    lines += [
        "=== SPECIFICATION ===",
        spec.strip(),
        "",
        # Whole-number ratio, not w/h: portrait would otherwise render as
        # "0.667:1", which is a confusing way to say 2:3.
        f"Output framing: {aspect} orientation, target {w}x{h} pixels "
        f"({w // gcd(w, h)}:{h // gcd(w, h)} aspect ratio). "
        "Compose for this exact frame.",
    ]
    if transparent:
        lines.append(CHROMA_BLOCK.format(key=key_color))
    lines += ["=== END SPECIFICATION ===", ""]
    return "\n".join(lines)


def run_codex(prompt, inputs, timeout, effort, workdir):
    """Run codex exec --json. Returns (thread_id, last_message, returncode)."""
    cmd = [
        "codex", "exec", "--json",
        "--skip-git-repo-check",
        "-s", "read-only",           # we do all file writes ourselves
        "-C", str(workdir),
        "-c", f'model_reasoning_effort="{effort}"',
    ]
    for f in inputs:
        cmd += ["-i", str(f)]
    # The prompt goes over stdin, never as a positional arg: `-i/--image` is
    # variadic (`<FILE>...`) and would otherwise swallow the prompt as a
    # filename. stdin also sidesteps argv length limits on long specs.

    thread_id, last_msg, err_lines = None, None, []
    # stderr goes to a file, not a pipe: we drain stdout first, and an
    # unread stderr pipe would deadlock codex once its 64KB buffer filled.
    err_file = tempfile.TemporaryFile(mode="w+")
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=err_file,
            stdin=subprocess.PIPE, text=True, bufsize=1,
            # Own process group: `codex` is a Node wrapper that spawns the real
            # binary as a child. Killing only the wrapper orphans that child,
            # which keeps the inherited stdout pipe open and leaks a process.
            start_new_session=True,
        )
    except FileNotFoundError:
        err_file.close()
        return None, "codex CLI not found on PATH", 127

    # Hard watchdog. The stdout read loop below blocks indefinitely if codex
    # hangs without emitting a line, so the deadline cannot be enforced inline.
    timed_out = threading.Event()

    def _kill():
        timed_out.set()
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    watchdog = threading.Timer(timeout, _kill)
    watchdog.daemon = True
    watchdog.start()

    # Codex emits no events between thread start and completion, so a 60-140s
    # generation looks identical to a hang — especially from a backgrounded
    # caller that can only see the log afterwards. Tick so it's obviously alive.
    finished = threading.Event()

    def _heartbeat():
        waited = 0
        while not finished.wait(15):
            waited += 15
            log(f"  ... still generating ({waited}s elapsed)")

    hb = threading.Thread(target=_heartbeat, daemon=True)
    hb.start()

    try:
        try:
            proc.stdin.write(prompt)
            proc.stdin.close()
        except (BrokenPipeError, ValueError):
            pass

        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue
            etype = evt.get("type")
            if etype == "thread.started":
                thread_id = evt.get("thread_id")
                log(f"  codex thread {thread_id}")
            elif etype == "item.completed":
                item = evt.get("item", {})
                if item.get("type") == "agent_message":
                    last_msg = item.get("text")
            elif etype == "error":
                err_lines.append(json.dumps(evt)[:500])
        proc.wait()
    finally:
        finished.set()
        watchdog.cancel()

    if timed_out.is_set():
        err_file.close()
        return thread_id, f"timed out after {timeout}s", 124

    try:
        err_file.seek(0)
        stderr = err_file.read()
    except Exception:
        stderr = ""
    finally:
        err_file.close()

    if proc.returncode != 0 and stderr.strip():
        err_lines.append(stderr.strip()[-800:])
    return thread_id, (last_msg or "; ".join(err_lines) or None), proc.returncode


def harvest(thread_id):
    """Collect PNGs produced by this thread, oldest first."""
    d = GEN_ROOT / thread_id
    if not d.is_dir():
        return []
    files = [p for p in d.rglob("*.png") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime)
    return files


def ensure_pillow():
    """Return a python executable that has Pillow, provisioning a venv if needed."""
    for cand in (sys.executable, "python3.11", "python3"):
        exe = shutil.which(cand) if not os.path.isabs(cand) else cand
        if not exe:
            continue
        r = subprocess.run([exe, "-c", "import PIL"], capture_output=True)
        if r.returncode == 0:
            return exe

    venv_py = VENV_DIR / "bin" / "python"
    if venv_py.exists():
        r = subprocess.run([str(venv_py), "-c", "import PIL"], capture_output=True)
        if r.returncode == 0:
            return str(venv_py)

    log("  provisioning Pillow (one-time, for transparency support)...")
    base = shutil.which("python3.11") or shutil.which("python3") or sys.executable
    subprocess.run([base, "-m", "venv", str(VENV_DIR)], check=True,
                   capture_output=True)
    subprocess.run([str(venv_py), "-m", "pip", "install", "-q", "--disable-pip-version-check",
                    "pillow"], check=True, capture_output=True)
    return str(venv_py)


def make_transparent(src, dst, key_color):
    if not CHROMA_SCRIPT.exists():
        raise RuntimeError(f"chroma-key helper not found at {CHROMA_SCRIPT}")
    py = ensure_pillow()
    cmd = [
        py, str(CHROMA_SCRIPT),
        "--input", str(src), "--out", str(dst),
        "--key-color", key_color,
        "--auto-key", "border",
        "--soft-matte",
        "--transparent-threshold", "12",
        "--opaque-threshold", "220",
        "--despill",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"chroma-key removal failed: {r.stderr.strip()[:400]}")


def resize_exact(path, w, h):
    """Force exact pixel dimensions without distorting the subject. macOS only.

    Scale-to-cover, then centre-crop. `sips -z` on its own resamples to the
    target dimensions *ignoring aspect ratio*, so a square generation forced to
    `landscape` comes out horizontally stretched. On a device mockup that reads
    as a subtly warped laptop — invisible unless you go looking for it.
    Best-effort: returns False if sips is unavailable or either step fails.
    """
    if not shutil.which("sips"):
        return False
    got = png_size(path)
    if not got:
        return False
    cw, ch = got
    if (cw, ch) == (w, h):
        return True

    # Same factor on both axes preserves aspect; round up so the crop never
    # has to pad an edge.
    scale = max(w / cw, h / ch)
    sw, sh = max(w, round(cw * scale)), max(h, round(ch * scale))
    r = subprocess.run(["sips", "-z", str(sh), str(sw), str(path)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return False
    r = subprocess.run(["sips", "-c", str(h), str(w), str(path)],
                       capture_output=True, text=True)
    return r.returncode == 0


def resolve_outputs(out, count):
    out = Path(out).expanduser()
    if count == 1:
        return [out]
    stem, suffix = out.stem, out.suffix or ".png"
    return [out.with_name(f"{stem}-{i + 1}{suffix}") for i in range(count)]


def main():
    ap = argparse.ArgumentParser(
        description="Generate raster images via Codex CLI's built-in image_gen tool."
    )
    ap.add_argument("--prompt", help="Image specification text.")
    ap.add_argument("--prompt-file", help="File containing the image specification.")
    ap.add_argument("--out", required=True,
                    help="Output PNG path. With --variants N, becomes name-1.png ...")
    ap.add_argument("--aspect", default="landscape", choices=sorted(ASPECTS),
                    help="Target framing (default: landscape 1536x1024).")
    ap.add_argument("--variants", type=int, default=1,
                    help="Number of distinct variants to generate (default 1).")
    ap.add_argument("--input", action="append", default=[],
                    help="Reference/edit-target image to attach. Repeatable.")
    ap.add_argument("--transparent", action="store_true",
                    help="Chroma-key generate then cut out to alpha PNG.")
    ap.add_argument("--key-color", default="#00ff00",
                    help="Chroma key color (use #ff00ff for green subjects).")
    ap.add_argument("--exact-size", action="store_true",
                    help="Force exact --aspect pixels: scale-to-cover then "
                         "centre-crop, never stretch. Requires macOS sips.")
    ap.add_argument("--timeout", type=int, default=900, help="Seconds (default 900).")
    ap.add_argument("--effort", default="low",
                    choices=["minimal", "low", "medium", "high", "xhigh"],
                    help="Codex reasoning effort for prompt shaping (default low). "
                         "Raise to medium for long or compositing-heavy specs, "
                         "where instruction adherence matters more than speed.")
    ap.add_argument("--workdir", default=None,
                    help="Directory codex runs in (read-only). Default: cwd.")
    ap.add_argument("--json", action="store_true", help="Emit JSON result on stdout.")
    args = ap.parse_args()

    if not args.prompt and not args.prompt_file:
        ap.error("one of --prompt or --prompt-file is required")
    spec = args.prompt or Path(args.prompt_file).expanduser().read_text()

    for f in args.input:
        if not Path(f).expanduser().exists():
            ap.error(f"--input file not found: {f}")

    count = max(1, args.variants)
    workdir = Path(args.workdir).expanduser() if args.workdir else Path.cwd()
    inputs = [Path(f).expanduser().resolve() for f in args.input]

    prompt = build_prompt(spec, count, args.aspect, args.transparent,
                          args.key_color, bool(inputs))

    log(f"[codex-image] generating {count} image(s), aspect={args.aspect}"
        f"{', transparent' if args.transparent else ''}")
    t0 = time.time()
    thread_id, last_msg, rc = run_codex(prompt, inputs, args.timeout,
                                        args.effort, workdir)

    if rc == 124:
        fail(args, f"timed out after {args.timeout}s — raise --timeout "
                   f"(budget ~60s per image) and retry.")
    if thread_id is None:
        fail(args, f"codex did not start a thread (rc={rc}): {last_msg}")

    produced = harvest(thread_id)
    if not produced:
        hint = ""
        if last_msg and re.search(r"log ?in|auth|credential|401|unauthor",
                                  last_msg, re.I):
            hint = " -- run `codex login` and retry."
        fail(args,
             f"codex produced no images (rc={rc}). Last message: "
             f"{(last_msg or 'none')[:400]}{hint}")

    outs = resolve_outputs(args.out, count)
    results = []
    for i, out_path in enumerate(outs):
        if i >= len(produced):
            break
        src = produced[i]
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if args.transparent:
            make_transparent(src, out_path, args.key_color)
        else:
            shutil.copy2(src, out_path)
        if args.exact_size:
            w, h = ASPECTS[args.aspect]
            got = png_size(out_path)
            if got and got != (w, h):
                resize_exact(out_path, w, h)
        dims = png_size(out_path)
        results.append({
            "path": str(out_path.resolve()),
            "width": dims[0] if dims else None,
            "height": dims[1] if dims else None,
            "bytes": out_path.stat().st_size,
        })

    elapsed = round(time.time() - t0, 1)
    log(f"[codex-image] done in {elapsed}s -> {len(results)} file(s)")
    for r in results:
        log(f"  {r['path']}  {r['width']}x{r['height']}  "
            f"{round(r['bytes'] / 1024)}KB")

    if len(results) < count:
        log(f"[codex-image] WARNING: asked for {count}, got {len(results)}")

    payload = {"ok": True, "thread_id": thread_id, "elapsed_s": elapsed,
               "images": results}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for r in results:
            print(r["path"])
    return 0


def fail(args, msg):
    log(f"[codex-image] ERROR: {msg}")
    if args.json:
        print(json.dumps({"ok": False, "error": msg}, indent=2))
    sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
