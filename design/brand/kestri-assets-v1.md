# Kestri raster assets v1

[简体中文](kestri-assets-v1.zh-CN.md)

Historical raster exports. Use the [official identity](README.md) for production assets.

## Files

- `kestri-mascot-v1.png`: 1225 × 1284 RGBA PNG, transparent full-body mascot.
- `kestri-telegram-avatar-v1.png`: 1254 × 1254 RGB PNG, square avatar on warm ivory. Upload this square image; this file predates the official vector avatar.
- `preview.html`: now previews the official vector assets on light/dark backgrounds and at circular avatar sizes.

Derived from the approved `kestri-concept-v1.png` with the built-in image_gen tool. These are raster assets, not SVG masters. No Telegram profile update is performed.

## Mascot prompt

Use case: background-extraction. Input image: approved Kestri brand board, edit target. Extract ONLY the large full-body kestrel mascot on the LEFT of this board into a standalone transparent PNG illustration. Preserve its exact design faithfully: head tilt, three-quarter pose facing right, orange head and folded wings, creamy breast, charcoal oval eyes with small white highlights, dark vertical cheek marks, hooked blue-gray beak, layered blue-gray wing shapes, long dark-tipped tail and small golden feet. Keep all body proportions, expression, soft clean flat shapes and colors from the left large mascot. Do not invent a new bird or use the smaller pose samples. Entire bird including feet and tail visible, centered with comfortable transparent margin of about 8 percent on all sides. Actual alpha transparency everywhere outside the bird, NO background, no checkerboard painted into pixels, no ground shadow, no tile, no wordmark, no swatches, no text, no additional objects. Crisp clean edges suitable for project README and website placement.

## Avatar prompt

Use case: precise-object-edit. Input: approved Kestri brand board as identity reference and edit target. Produce ONLY a standalone square Telegram avatar based faithfully on the small colored bird head icon in the UPPER RIGHT of the reference board. Preserve exactly this kestrel character's terracotta orange head, creamy face and chest, charcoal oval eyes with tiny white highlights, deep charcoal vertical cheek marks, hooked blue-gray and golden beak, subtle head tilt and three-quarter view facing right. Clean simplified shape illustration, same graphic style as reference, no feather texture or added details. Composition: square 1:1 canvas with a FULL BLEED solid warm ivory background, no rounded square tile inside it, no border, no text. Center the head and upper chest as a friendly bust portrait. The entire top of the head must fit with generous margin. Keep all eyes, beak and dark cheek marks comfortably inside a central circular safe area: inset the head about 18 percent from top, left and right edges. The lower chest may meet the bottom edge but a circular crop must preserve head, cheeks and beak completely. Face large enough to recognize at 32 pixels. No logo wordmark, no mascot full body, no feet, no swatches, no shadows, no mockup. Output is ready-to-upload square avatar with opaque background.

