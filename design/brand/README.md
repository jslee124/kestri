# Kestri visual identity

[简体中文](README.zh-CN.md)

The primary color logo and avatar use the user's selected portrait **without redrawing,
cropping, simplifying gradients, or adding margin**. The original is preserved as
[kestri-portrait-source.png](kestri-portrait-source.png). The avatar and color-mark PNGs
are byte-for-byte copies of that image. The horizontal logo combines the original
square portrait with the existing vector wordmark.

The full-body mascot remains a separate vector illustration. Secondary monochrome
marks are simplified vector interpretations, not exact replicas of the color portrait.

## Deliverables

| Asset | Vector master | PNG export | Use |
| --- | --- | --- | --- |
| Primary logo | [SVG](assets/kestri-logo.svg) | [1920 × 640](assets/kestri-logo.png) | Project headers and websites |
| Color logo for dark backgrounds | [SVG](assets/kestri-logo-dark.svg) | [1920 × 640](assets/kestri-logo-dark.png) | Color kestrel with warm-white lettering |
| Ink logo | [SVG](assets/kestri-logo-ink.svg) | [1920 × 640](assets/kestri-logo-ink.png) | Single-color use on light backgrounds |
| Reverse logo | [SVG](assets/kestri-logo-reverse.svg) | [1920 × 640](assets/kestri-logo-reverse.png) | Single-color use on dark backgrounds |
| Mascot | [SVG](assets/kestri-mascot.svg) | [1440 × 1920](assets/kestri-mascot.png) | README, documentation and illustrations |
| Color mark | [SVG](assets/kestri-mark.svg) | [1254 × 1254](assets/kestri-mark.png) | Standalone product identification |
| Ink mark | [SVG](assets/kestri-mark-ink.svg) | [1024 × 1024](assets/kestri-mark-ink.png) | Single-color identification |
| Reverse mark | [SVG](assets/kestri-mark-reverse.svg) | [1024 × 1024](assets/kestri-mark-reverse.png) | Identification on dark backgrounds |
| Wordmark | [SVG](assets/kestri-wordmark.svg) | [1024 × 366](assets/kestri-wordmark.png) | Text-only branding |
| Avatar | [SVG](assets/kestri-avatar.svg) | [1254 × 1254](assets/kestri-avatar.png) | Telegram profile upload |
| Brand sheet | [SVG](assets/kestri-brand-sheet.svg) | [2400 × 1650](assets/kestri-brand-sheet.png) | Review and sharing |

Additional avatar exports: [512](assets/kestri-avatar-512.png),
[128](assets/kestri-avatar-128.png), [64](assets/kestri-avatar-64.png),
and [32 pixels](assets/kestri-avatar-32.png).
The portrait, color mark and avatar have the original opaque warm-white background.
Logo lettering sits on transparent space around that original square image. The mascot,
wordmark and monochrome assets have transparent backgrounds. Monochrome face areas
are genuine transparent cutouts. Color logo, mark, avatar and brand-sheet SVGs embed
the original PNG; these are hybrid files, not fully vector artwork. The mascot,
wordmark and monochrome variants use editable vector paths with no external fonts.

## Colors

These fixed colors describe the vector mascot and lettering. The portrait retains
its original gradients and colors, which are not reduced to these swatches.

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
mascot must not be stretched, recolored or rotated. Preserve the portrait's existing
gradients and edge-to-edge crop; do not add a surrounding margin or rounded bust cutout.
Leave external clear space equal to one lowercase letter's height around the logo,
and at least 10% of the mascot's displayed height around the mascot.

The recommended minimum displayed logo width is 180 CSS pixels; below that width,
use the standalone mark or avatar. Use the avatar at 32 pixels or larger and the
full mascot at 160 pixels or larger. These are design recommendations, not platform
requirements. Upload the square avatar PNG; the face and crown remain inside its
circular crop. Avoid using the full mascot as a tiny avatar.

The asset files are ready for project use. The configured Telegram bot uses the color
avatar; Telegram confirmed the update and a subsequent profile-photo lookup returned
the new square image. The root README centers the logo and uses the color kestrel in
both themes, with warm-white lettering on dark backgrounds.
The earlier generated PNGs remain historical concept references, not official masters.

## Editing and export

Edit the named paths and shared colors in [build_assets.py](build_assets.py), then run:

```sh
python3 design/brand/build_assets.py
node design/brand/render_assets.cjs
node design/brand/check_assets.cjs
python3 scripts/check_docs.py
```

The Python builder uses only the standard library and reads the original portrait
from `kestri-portrait-source.png`; include that file when sharing the builder. The PNG renderer requires the
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
parseable SVGs, unique IDs, internal references, exact embedded portrait bytes,
absence of external resources/fonts, output dimensions, transparency where intended,
and monochrome cutouts. The avatar and color-mark PNGs are verified against the
original file byte for byte.
The local documentation checker includes the `design` directory and verifies
translation pairs and links. Local crop previews do not establish acceptance inside
a live Telegram client's rendering or print production; the API update and photo
readback establish that the configured bot's profile photo has changed.
