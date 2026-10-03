# Kestri visual identity

[简体中文](README.zh-CN.md)

The official identity uses the selected second concept: a quiet, curious kestrel with a
terracotta crown, cream breast, dark cheek markings and a long tail. The vector masters
regularize the concept's contours and replace generated gradients with solid colors.
The mascot and logo symbol share exactly the same head geometry.

## Deliverables

| Asset | Vector master | PNG export | Use |
| --- | --- | --- | --- |
| Primary logo | [SVG](assets/kestri-logo.svg) | [1920 × 640](assets/kestri-logo.png) | Project headers and websites |
| Color logo for dark backgrounds | [SVG](assets/kestri-logo-dark.svg) | [1920 × 640](assets/kestri-logo-dark.png) | Color kestrel with warm-white lettering |
| Ink logo | [SVG](assets/kestri-logo-ink.svg) | [1920 × 640](assets/kestri-logo-ink.png) | Single-color use on light backgrounds |
| Reverse logo | [SVG](assets/kestri-logo-reverse.svg) | [1920 × 640](assets/kestri-logo-reverse.png) | Single-color use on dark backgrounds |
| Mascot | [SVG](assets/kestri-mascot.svg) | [1440 × 1920](assets/kestri-mascot.png) | README, documentation and illustrations |
| Color mark | [SVG](assets/kestri-mark.svg) | [1024 × 1024](assets/kestri-mark.png) | Standalone product identification |
| Ink mark | [SVG](assets/kestri-mark-ink.svg) | [1024 × 1024](assets/kestri-mark-ink.png) | Single-color identification |
| Reverse mark | [SVG](assets/kestri-mark-reverse.svg) | [1024 × 1024](assets/kestri-mark-reverse.png) | Identification on dark backgrounds |
| Wordmark | [SVG](assets/kestri-wordmark.svg) | [1024 × 366](assets/kestri-wordmark.png) | Text-only branding |
| Avatar | [SVG](assets/kestri-avatar.svg) | [1024 × 1024](assets/kestri-avatar.png) | Telegram profile upload |
| Brand sheet | [SVG](assets/kestri-brand-sheet.svg) | [2400 × 1650](assets/kestri-brand-sheet.png) | Review and sharing |

Additional avatar exports: [512](assets/kestri-avatar-512.png),
[128](assets/kestri-avatar-128.png), [64](assets/kestri-avatar-64.png),
and [32 pixels](assets/kestri-avatar-32.png).
The avatar and brand sheet have opaque backgrounds; all other masters and exports
have transparent backgrounds. Monochrome face areas are genuine transparent cutouts.
SVG files contain editable paths and shapes, with no embedded bitmap or external font.
The custom lowercase wordmark uses rounded vector strokes.

## Colors

| Role | Hex |
| --- | --- |
| Terracotta crown and wing | `#CA7448` |
| Cream face and breast | `#F6E5CC` |
| Ink eyes, cheek markings and lettering | `#30343B` |
| Blue-gray wing and beak | `#63758C` |
| Golden beak and feet | `#EAAF56` |
| Warm white background and highlights | `#FFFCF6` |

## Usage

Use the primary logo on white or warm-white backgrounds. Use the dark-background
color logo on ink-colored backgrounds, or the reverse logo for single-color use.
Keep the provided proportions and spacing; the logo and
mascot must not be stretched, recolored, rotated or given gradients and shadows.
Leave external clear space equal to one lowercase letter's height around the logo,
and at least 10% of the mascot's displayed height around the mascot.

The recommended minimum displayed logo width is 180 CSS pixels; below that width,
use the standalone mark or avatar. Use the avatar at 32 pixels or larger and the
full mascot at 160 pixels or larger. These are design recommendations, not platform
requirements. Upload the square avatar PNG; the face and crown remain inside its
circular crop. Avoid using the full mascot as a tiny avatar.

The asset files are ready for project use. They have not been uploaded to Telegram,
and the root README uses the color kestrel in both themes, with warm-white lettering on dark backgrounds.
The identity has not been published externally.
The earlier generated PNGs remain historical concept references, not official masters.

## Editing and export

Edit the named paths and shared colors in [build_assets.py](build_assets.py), then run:

```sh
python3 design/brand/build_assets.py
node design/brand/render_assets.cjs
node design/brand/check_assets.cjs
python3 scripts/check_docs.py
```

The Python builder uses only the standard library. The PNG renderer requires the
public npm package `sharp`; use an existing installation or set `NODE_PATH` to a
runtime that supplies it. [render_assets.cjs](render_assets.cjs) exports PNGs directly
from the vector masters. Editing a generated SVG directly is possible, but rebuilding
will overwrite that edit: update the builder for changes that must persist.

Open [the preview](preview.en.html) in a browser to compare light and dark backgrounds,
square and circular avatar crops, and small sizes. The static brand sheet provides
the same main visual identity without running a server.

## Validation

Run [check_assets.cjs](check_assets.cjs) with the same `sharp` runtime as the renderer.

The SVG masters and raster exports have been inspected locally. Validation checks
parseable SVGs, unique IDs, internal reference targets, absence of bitmap/font
dependencies, output dimensions, transparent backgrounds and monochrome cutouts.
The local documentation checker includes the `design` directory and verifies
translation pairs and links. Local crop previews do not establish acceptance inside
a live Telegram client or print production.
