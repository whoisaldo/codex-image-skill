---
name: codex-image
description: Generate real raster images (PNG) via the Codex CLI's built-in image_gen tool — hero images, marketing visuals, illustrations, mascots, textures, backgrounds, product/device mockups, concept art, og:image cards, empty-state art, transparent cutouts. Use when a task needs an actual picture that would otherwise be faked with hand-written SVG, CSS gradients, emoji, or a placeholder box. Do NOT use for building or changing UI code, layout, CSS, components, data charts, existing SVG icon systems, or screenshots of a real running app.
---

# Codex Image Generation

Claude cannot draw. Hand-rolled SVG illustrations, CSS-art "hero graphics", and
ASCII/HTML mockups look amateurish and undermine otherwise good work. The Codex
CLI has a built-in `image_gen` tool that produces genuine, production-quality
raster art. This skill drives it, harvests the PNG, and hands the file back so
you can wire it into the project.

Auth is the user's existing ChatGPT OAuth login in `codex` — **no
`OPENAI_API_KEY` is needed, and image generation is effectively unmetered on
their plan.** Prefer generating a real asset over faking one.

## When to use this skill

Use it when **the deliverable is a picture**:

| Need | Example |
|---|---|
| Marketing / landing page art | hero background, section illustration, feature spot art |
| Product & device mockups | app on a laptop/phone, packaging, merch, billboard |
| Brand & character art | mascot, avatar, illustrative badge, sticker |
| Textures & backgrounds | noise, gradient mesh render, paper, fabric, abstract 3D |
| Content imagery | blog header, og:image / social card, docs explainer art |
| Empty & error states | "no results yet" illustration, 404 art |
| Concept & moodboards | style exploration before committing to a design |
| Cutouts | any of the above needing a transparent background |

## When NOT to use this skill

Do **not** reach for image generation when the deliverable is **code or a real
capture**:

- **Building or changing UI.** Components, layout, spacing, responsive fixes,
  Tailwind/CSS work, dark mode. Write code.
- **Screenshots of the real app.** Use the browser/`claude-in-chrome` tools.
  A generated "screenshot" is a lie — it shows a UI that does not exist.
- **Charts and data visualization.** Real numbers require a real chart library.
  Use the `dataviz` skill. A generated chart has invented data.
- **Extending an existing SVG icon set or logo system.** Match the vectors
  already in the repo.
- **Simple geometric shapes, arrows, dividers, spinners.** Inline SVG/CSS is
  smaller, sharper, themeable, and correct here.
- **Anything needing crisp small text, exact brand color values, or pixel-exact
  alignment.** Generated text is unreliable at small sizes.

> Rule of thumb: if the result should scale infinitely, be themeable, or reflect
> real data → write code. If it should look *photographed, rendered or painted*
> → use this skill.

**Never** silently generate an image in place of a UI change the user asked
for. If a request is ambiguous ("make the landing page look better"), do the
code work, and *offer* generated art for the decorative slots.

## Usage

```bash
python3 ~/.claude/skills/codex-image/scripts/codex_image.py \
  --prompt "<spec>" --out path/to/asset.png
```

Run it from the project root so relative `--out` paths land in the project.

Key flags:

| Flag | Purpose |
|---|---|
| `--out PATH` | Destination PNG (parent dirs created). **Required.** |
| `--aspect` | `landscape` (1536×1024, default), `square`, `portrait`, `wide` (2048×1152), `square2k`, `4k`, `4k-portrait` |
| `--variants N` | N distinct takes → `name-1.png`, `name-2.png`, … Use when the user should pick. |
| `--input FILE` | Attach a reference or edit-target image. Repeatable. |
| `--transparent` | Chroma-key generate, then cut out to alpha PNG. *(macOS)* |
| `--key-color` | Chroma color, default `#00ff00`; use `#ff00ff` for green subjects. |
| `--exact-size` | Force exact `--aspect` pixels: scale-to-cover then centre-crop, never stretch. *(macOS, needs `sips`)* |
| `--effort` | Reasoning effort, default `low`. Raise to `medium` for long or compositing-heavy specs where instruction adherence matters more than speed. |
| `--json` | Machine-readable result. |
| `--timeout` | Seconds, default 900. |

Budget ~40–70s per image (compositing an attached screenshot runs longer,
~120–140s). The script prints a heartbeat every 15s, so silence for more than
that means something is genuinely wrong, not slow. Run generations for
**different** assets in parallel (separate background Bash calls) — runs are
isolated by Codex thread ID.

## Mockups from a real screenshot

The highest-value use of `--input`: pass an actual screenshot of the running
product and have the model composite **that real UI** onto a device, instead of
inventing an interface. This is how you get a portfolio/marketing shot that
shows the thing you actually built.

```bash
python3 ~/.claude/skills/codex-image/scripts/codex_image.py \
  --input screenshots/dashboard.png --aspect landscape \
  --out public/images/card.png \
  --prompt "Use case: product-mockup
Primary request: The attached website screenshot shown running on a modern
  thin-bezel laptop, angled three-quarter view, on a dark matte surface
Style/medium: photorealistic studio product photography, 85mm, shallow depth of
  field, screen perfectly crisp and readable
Composition/framing: device left-of-centre; keep the right third empty and dark
Lighting/mood: soft key from upper left, gentle rim light, faint surface reflection
Color palette: near-black #08070d ground; the screen keeps its own colors exactly
Constraints: reproduce the attached screenshot on the screen EXACTLY as provided -
  do not redesign, redraw, restyle, re-lay-out, invent or alter any UI element,
  heading, body text, button or color within it; no added text; no watermark
Avoid: invented interface elements, garbled lettering, distorted screen content"
```

> ⚠️ **Always diff the result against the source screenshot before shipping.**
> If the model redrew the UI rather than reproducing it, the output is a
> fabricated screenshot of a product that does not exist — the worst failure
> this tool can produce, and easy to miss because it looks plausible. Check the
> headline wording, nav items, button labels and any numbers.

Note this inverts the advice in the *invented* device-mockup recipe
(`references/prompting.md`), which says to describe screen content as abstract
shapes to stop text garbling. That applies only when there is no real UI to
show. With `--input`, you want the real words, so demand fidelity instead.

## Writing the spec

Quality tracks almost entirely with prompt quality. Use this labeled schema —
include only the lines that matter, and always end with constraints:

```
Use case: <ads-marketing | product-mockup | ui-mockup | illustration-story |
           stylized-concept | logo-brand | infographic-diagram | photorealistic-natural>
Asset type: <where it will actually be used>
Primary request: <the subject, one sentence>
Style/medium: <photo | 3D render | flat vector illustration | watercolor | isometric>
Composition/framing: <angle, crop, and where to leave negative space>
Lighting/mood: <light direction/quality + emotional register>
Color palette: <concrete colors — match the site's real palette>
Constraints: no text, no logos, no watermark
Avoid: <failure modes to suppress>
```

Rules that materially change output quality:

- **Always** state where negative space goes if copy will overlay the image.
- **Always** add `no text, no logos, no watermark` unless you genuinely want
  text — generated lettering is usually malformed.
- Name real colors that match the project's palette, so the asset drops in.
- Use camera language (`85mm`, `shallow depth of field`, `three-quarter view`)
  for photoreal; use medium language (`flat vector`, `grainy risograph`) for
  illustration.
- For a set of assets that must look related, reuse one style/palette block
  verbatim across every prompt, changing only the subject.

See `references/prompting.md` for recipes and failure-mode fixes.

## Workflow

1. **Confirm it's an art task**, not a code task (see the table above).
2. Decide asset list, aspect, and destination inside the project
   (e.g. `public/images/hero.png`).
3. Write the spec; generate. Use `--variants 2` when the direction is unsettled.
4. **Look at the result with the Read tool.** Never ship an asset you have not
   viewed — check subject, framing, negative space, and that no garbled text
   crept in.
5. If it misses, change **one** thing in the spec and regenerate; don't rewrite
   the whole prompt.
6. Wire it into the project (`<img>`, `next/image`, CSS `background-image`) and
   tell the user the path, plus suggested `alt` text.

## Refining an existing image

Attach it and describe the change, repeating what must not change:

```bash
python3 ~/.claude/skills/codex-image/scripts/codex_image.py \
  --input public/images/hero.png \
  --prompt "Use case: lighting-weather
Primary request: shift this scene to golden-hour sunset lighting
Constraints: change only the lighting and sky; keep composition, subject
placement and framing identical; no text; no watermark" \
  --out public/images/hero-sunset.png
```

## Transparent cutouts

`--transparent` renders on a flat chroma-key background and removes it locally
(auto-provisions Pillow into `<skill_dir>/.venv` on first use).

Works well for solid subjects: mascots, products, icons, badges. Works poorly
for hair, fur, smoke, glass, or translucency — for those, generate on a solid
background that matches the destination instead, or keep the backdrop.

After cutting out, **view the PNG** to confirm clean edges and no green fringe.

## Failure handling

- **"codex produced no images"** — usually a spec the model read as a question.
  Make `Primary request:` declarative and retry.
- **Auth errors** — tell the user to run `codex login`. Never ask for an API key.
- **Wrong dimensions** — the built-in tool infers size from the prompt; add
  `--exact-size` to force it.
- **Garbled text in the image** — regenerate with `no text` in Constraints and
  overlay real text in HTML/CSS instead. That is always the better result.
