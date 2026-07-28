# codex-image

A Claude Code skill that generates **real raster images** by driving the Codex
CLI's built-in `image_gen` tool.

Claude cannot draw. Hand-written SVG "illustrations", CSS-art hero graphics and
HTML mockups look amateurish. Codex can generate genuine art. This skill lets
Claude hand the art job to Codex, get a PNG back, and carry on building.

**Auth:** uses the existing ChatGPT OAuth login in `codex`. No
`OPENAI_API_KEY`, no per-image billing.

## Install

Clone anywhere, then symlink it into your Claude Code skills directory:

```bash
git clone https://github.com/<you>/codex-image-skill.git
ln -sfn "$(pwd)/codex-image-skill" ~/.claude/skills/codex-image
```

Requires `codex` on `PATH` and logged in (`codex login`). Verify with
`codex features list | grep image_generation` → should read `stable  true`.

## Use

Claude loads the skill automatically when a task needs artwork. Manually:

```bash
python3 ~/.claude/skills/codex-image/scripts/codex_image.py \
  --prompt "Use case: ads-marketing
Primary request: abstract 3D glass ribbons sweeping across a dark field
Style/medium: premium 3D render, soft depth of field
Composition/framing: subject on the right; left third empty for headline copy
Color palette: deep indigo base, violet and cyan refractions
Constraints: no text, no logos, no watermark" \
  --aspect landscape --out public/images/hero.png
```

| Flag | Purpose |
|---|---|
| `--out PATH` | Destination PNG (**required**) |
| `--aspect` | `landscape` (default), `square`, `portrait`, `wide`, `square2k`, `4k`, `4k-portrait` |
| `--variants N` | N distinct takes → `name-1.png`, `name-2.png`, … |
| `--input FILE` | Attach a reference / edit-target image (repeatable) |
| `--transparent` | Chroma-key generate, then cut out to alpha PNG |
| `--exact-size` | Force exact pixel dimensions |
| `--json` | Machine-readable result |

## What it does and does not do

**Does:** hero art, marketing visuals, illustrations, mascots, textures,
backgrounds, device/product mockups, og:images, empty-state art, cutouts.

**Does not:** UI code, layout/CSS, components, data charts (real data needs a
real chart library), existing SVG icon systems, or screenshots of a running app
(use the browser). The skill description encodes this boundary; it was validated
at 32/32 on a blind classification set spanning both sides of the line.

## How it works

1. Builds a structured spec and pipes it to `codex exec --json` over **stdin**
   (`-i/--image` is variadic and would otherwise swallow a positional prompt).
2. Runs Codex with `-s read-only` — Codex never writes to your repo; this script
   does all file placement.
3. Captures `thread_id` from the `thread.started` event and harvests only
   `$CODEX_HOME/generated_images/<thread_id>/`, so **concurrent runs never steal
   each other's images**.
4. Optionally chroma-keys to alpha via Codex's bundled `remove_chroma_key.py`,
   auto-provisioning Pillow into `.venv/` on first use.

~40–70s per image. Different assets can be generated in parallel.

## Layout

```
SKILL.md                  what Claude reads (triggering + workflow)
references/prompting.md   recipes, consistent asset sets, failure fixes
scripts/codex_image.py    the wrapper
examples/                 verified sample outputs
examples/demo/            end-to-end landing page built from generated assets
```

Open `examples/demo/index.html` to see the payoff: generated art carrying a
page, with all copy as real HTML text on top.
