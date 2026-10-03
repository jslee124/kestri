// Verify vector portability and raster exports without calling an external service.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const sharp = require('sharp');

async function main() {
  const directory = path.join(__dirname, 'assets');
  const files = await fs.readdir(directory);
  const vectors = files.filter(name => name.endsWith('.svg'));
  assert.equal(vectors.length, 11);
  const portrait = await fs.readFile(path.join(__dirname, 'kestri-portrait-source.png'));
  const hybridAssets = new Set(['kestri-mark.svg', 'kestri-avatar.svg',
    'kestri-logo.svg', 'kestri-logo-dark.svg', 'kestri-brand-sheet.svg']);
  for (const name of vectors) {
    const source = await fs.readFile(path.join(directory, name), 'utf8');
    assert(!/<(?:text|script|foreignObject)\b/.test(source), `${name}: nonportable element`);
    assert(!/\bfont-family=/.test(source), `${name}: external font`);
    const images = [...source.matchAll(/\bhref="([^"]+)"/g)];
    assert.equal(images.length > 0, hybridAssets.has(name), `${name}: unexpected raster content`);
    for (const image of images) {
      assert(image[1].startsWith('data:image/png;base64,'), `${name}: external resource`);
      assert(Buffer.from(image[1].split(',')[1], 'base64').equals(portrait),
        `${name}: embedded portrait differs from approved image`);
    }
    const ids = [...source.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]);
    assert.equal(new Set(ids).size, ids.length, `${name}: duplicate IDs`);
    for (const reference of source.matchAll(/url\(#([^)]*)\)/g)) {
      assert(ids.includes(reference[1]), `${name}: unresolved reference`);
    }
    if (name === 'kestri-avatar.svg' || name === 'kestri-mark.svg') {
      const exported = await fs.readFile(path.join(directory, name.replace(/\.svg$/, '.png')));
      assert(exported.equals(portrait), `${name}: PNG is not an exact source copy`);
      continue;
    }
    const width = name.includes('brand-sheet') ? 2400
      : name.includes('mascot') ? 1440
      : name.includes('logo') ? 1920 : 1024;
    const expected = await sharp(Buffer.from(source)).resize({ width }).ensureAlpha()
      .raw().toBuffer({ resolveWithObject: true });
    const exported = await sharp(path.join(directory, name.replace(/\.svg$/, '.png')))
      .ensureAlpha().raw().toBuffer({ resolveWithObject: true });
    assert.deepEqual(exported.info, expected.info, `${name}: export dimensions differ`);
    assert(exported.data.equals(expected.data), `${name}: export is stale`);
    const { data, info } = exported;
    let transparent = 0;
    let opaque = 0;
    for (let pixel = 0; pixel < info.width * info.height; pixel++) {
      const alpha = data[pixel * 4 + 3];
      if (alpha === 0) transparent++;
      if (alpha === 255) opaque++;
    }
    assert(opaque > 0, `${name}: empty asset`);
    if (name.includes('avatar') || name.includes('brand-sheet')) {
      assert.equal(opaque, info.width * info.height, `${name}: background not opaque`);
    } else {
      assert(transparent > info.width * info.height / 10, `${name}: missing transparency`);
      for (let x = 0; x < info.width; x++) {
        assert.equal(data[x * 4 + 3], 0, `${name}: top edge clipped`);
        assert.equal(data[((info.height - 1) * info.width + x) * 4 + 3], 0,
          `${name}: bottom edge clipped`);
      }
      for (let y = 0; y < info.height; y++) {
        assert.equal(data[(y * info.width) * 4 + 3], 0, `${name}: left edge clipped`);
        assert.equal(data[(y * info.width + info.width - 1) * 4 + 3], 0,
          `${name}: right edge clipped`);
      }
    }
    if (name === 'kestri-mark-ink.svg' || name === 'kestri-mark-reverse.svg') {
      // A point in the lower cream cheek must be genuinely transparent in single-color marks.
      const pixel = (Math.round(433 * info.height / 512) * info.width
        + Math.round(359 * info.width / 512)) * 4;
      assert.equal(data[pixel + 3], 0, `${name}: face is not a cutout`);
    }
  }
  for (const size of [512, 128, 64, 32]) {
    const metadata = await sharp(path.join(directory, `kestri-avatar-${size}.png`)).metadata();
    assert.equal(metadata.width, size);
    assert.equal(metadata.height, size);
  }
  console.log('PASS: exact portrait copies, embedded source fidelity, matching exports, transparency and avatar sizes.');
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
