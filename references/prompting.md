# Prompting recipes

Load this when a first attempt missed, or when generating a coordinated set of
assets. Output quality is dominated by the spec, not by flags.

## The three rules that matter most

1. **Say where the negative space goes.** Any image that will sit behind or
   beside copy needs an explicit instruction like *"leave the left third empty
   and low-contrast for headline text"*. Without it you get a centered subject
   that fights every layout.
2. **Ban text by default.** `Constraints: no text, no logos, no watermark`.
   Generated lettering is frequently malformed. Overlay real text in HTML/CSS —
   it's sharper, translatable, selectable, and themeable.
3. **Name the project's real colors.** `deep indigo #1E1B4B background, cyan
   #22D3EE accents` makes the asset drop into the existing design instead of
   clashing with it.
4. **State the destination background.** The single most common miss: an
   illustration generated with a default cream/white backdrop dropped into a
   dark card, where it reads as a glowing rectangle. Say
   `the illustration background must be solid #0F0C1D so it blends into the
   dark card — do NOT use a light or cream background`, or use `--transparent`
   and let the page background show through.

## Copy-paste recipes

### Landing page hero background (copy overlays it)
```
Use case: ads-marketing
Asset type: landing page hero background, headline overlays the left side
Primary request: <abstract subject — flowing glass ribbons / layered mesh terrain / light refraction>
Style/medium: premium 3D render, soft depth of field
Composition/framing: subject occupies the right two thirds; left third stays
  dark, empty and low-contrast for headline copy
Lighting/mood: dark studio backdrop, cool rim lighting, modern and confident
Color palette: <site background color> base with <accent 1> and <accent 2> highlights
Constraints: no text, no logos, no watermark, no people
Avoid: busy patterns, stock-photo look, high-contrast detail on the left third
```

### Device / product mockup
```
Use case: ui-mockup
Asset type: marketing "product shot"
Primary request: a <MacBook Pro / iPhone 15> on a <clean desk / plain surface>,
  screen showing <describe the UI: dark dashboard, line chart, three KPI cards>
Style/medium: photorealistic product photography, 50mm, shallow depth of field
Composition/framing: three-quarter angle, device on the right, negative space left
Lighting/mood: bright airy daylight, soft shadows, premium
Constraints: screen content must read as a real interface; no readable brand
  names; no watermark
Avoid: gibberish text, warped screen edges, cluttered props
```
Describe screen UI as **shapes and blocks** ("blurred label bars", "three KPI
cards"), never as specific words — that's what keeps text from garbling.

### Flat vector spot illustration / empty state
```
Use case: illustration-story
Asset type: empty-state illustration for "<state>"
Primary request: <simple scene, one clear subject>
Style/medium: flat vector illustration, thick rounded shapes, subtle grain, no outlines
Composition/framing: centered subject, airy margins
Lighting/mood: light, optimistic
Color palette: <brand accent>, warm cream background, <secondary> accents
Constraints: no text, no logos, no watermark
Avoid: photorealism, drop shadows, clutter
```

### Transparent cutout (mascot, product, badge)
Add `--transparent`. Keep the subject solid and opaque; state
`full body centered, generous padding on all sides`. Use `--key-color '#ff00ff'`
whenever the subject is green.

### og:image / social card
Use `--aspect wide` (2048×1152 ≈ 1.91:1). Generate the *artwork only* with
`no text`, then composite the title in HTML/CSS or with a satori/canvas step.

## Consistent asset sets

To make N assets look like one family, hold a **style block** constant and vary
only `Primary request`:

```
Style/medium: flat vector illustration, thick rounded shapes, subtle grain, no outlines
Lighting/mood: light, optimistic
Color palette: indigo #4F46E5, cream #FDF6EC, sage #86A789
Constraints: no text, no logos, no watermark
```

Generate them in parallel background calls — each run is isolated by thread ID.

## Editing: repeat the invariants every time

Drift is the main failure mode. On every iteration restate what must not
change:

```
Constraints: change ONLY <the one thing>; keep composition, subject placement,
  framing, palette and lighting otherwise identical; no text; no watermark
```

Iterate with **one** change per round. Changing three things at once makes it
impossible to tell which instruction worked.

## Failure modes → fixes

| Symptom | Fix |
|---|---|
| Garbled text in the image | Add `no text` and overlay real text in CSS |
| Subject dead-center, no room for copy | Explicitly state which region stays empty |
| Too "stock photo" | Add a specific medium + camera/lens, and an `Avoid: stock-photo look` line |
| Clashes with the site design | Name literal hex colors from the palette |
| Art sits in a bright box inside a dark card | State the destination background hex, or use `--transparent` |
| Wrong aspect | Set `--aspect`, add `--exact-size` to force pixels |
| Edit changed too much | Restate invariants; change one thing per round |
| Green fringe on a cutout | Subject contained green — regenerate with `--key-color '#ff00ff'` |
| Cutout ate part of the subject | Subject too translucent for chroma key — generate on a solid backdrop instead |

## Aspect cheat sheet

| `--aspect` | Pixels | Use for |
|---|---|---|
| `landscape` | 1536×1024 | hero, blog header, section art (default) |
| `square` | 1024×1024 | avatars, mascots, spot illustrations, cutouts |
| `portrait` | 1024×1536 | mobile hero, poster, story card |
| `wide` | 2048×1152 | og:image, social card, wide banner |
| `square2k` | 2048×2048 | high-DPI square art |
| `4k` / `4k-portrait` | 3840×2160 / 2160×3840 | full-bleed backgrounds, print |
