// Rasterize the official vector masters. Requires the public npm package sharp.
// Run `node design/brand/render_assets.cjs`; NODE_PATH may point to a bundled runtime.
const fs = require('node:fs/promises');
const path = require('node:path');
const sharp = require('sharp');

async function main() {
  const directory = path.join(__dirname, 'assets');
  for (const name of (await fs.readdir(directory)).filter(name => name.endsWith('.svg'))) {
    const input = path.join(directory, name);
    const width = name.includes('brand-sheet') ? 2400
      : name.includes('mascot') ? 1440
      : name.includes('logo') ? 1920 : 1024;
    await sharp(input).resize({ width }).png().toFile(input.replace(/\.svg$/, '.png'));
  }
  for (const size of [512, 128, 64, 32]) {
    await sharp(path.join(directory, 'kestri-avatar.svg'))
      .resize(size, size)
      .png()
      .toFile(path.join(directory, `kestri-avatar-${size}.png`));
  }
  console.log('Exported 11 PNG masters and 4 avatar sizes from the SVG sources.');
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
