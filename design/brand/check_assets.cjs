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
  for (const name of vectors) {
    const source = await fs.readFile(path.join(directory, name), 'utf8');
    assert(!/<(?:image|text|script|foreignObject)\b/.test(source), `${name}: nonportable element`);
    assert(!/\b(?:href|font-family)=/.test(source), `${name}: external resource or font`);
    const ids = [...source.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]);
    assert.equal(new Set(ids).size, ids.length, `${name}: duplicate IDs`);
    for (const reference of source.matchAll(/url\(#([^)]*)\)/g)) {
      assert(ids.includes(reference[1]), `${name}: unresolved reference`);
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
      const pixel = (Math.round(384 * info.height / 512) * info.width
        + Math.round(303 * info.width / 512)) * 4;
      assert.equal(data[pixel + 3], 0, `${name}: face is not a cutout`);
    }
  }
  for (const size of [512, 128, 64, 32]) {
    const metadata = await sharp(path.join(directory, `kestri-avatar-${size}.png`)).metadata();
    assert.equal(metadata.width, size);
    assert.equal(metadata.height, size);
  }
  console.log('PASS: 11 portable SVGs, matching PNG exports, transparent bounds, cutouts and 4 avatar sizes.');
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
