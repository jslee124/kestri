// Export the exact approved portrait and render vector/hybrid logos with sharp.
// Run `node design/brand/render_assets.cjs`; NODE_PATH may point to a bundled runtime.
const fs = require('node:fs/promises');
const path = require('node:path');
const sharp = require('sharp');

async function main() {
  const directory = path.join(__dirname, 'assets');
  for (const name of (await fs.readdir(directory)).filter(name => name.endsWith('.svg'))) {
    const input = path.join(directory, name);
    if (name === 'kestri-avatar.svg' || name === 'kestri-mark.svg') {
      await fs.copyFile(path.join(__dirname, 'kestri-portrait-source.png'),
        input.replace(/\.svg$/, '.png'));
      continue;
    }
    const width = name.includes('brand-sheet') ? 2400
      : name.includes('mascot') ? 1440
      : name.includes('logo') ? 1920 : 1024;
    await sharp(input).resize({ width }).png().toFile(input.replace(/\.svg$/, '.png'));
  }
  for (const size of [512, 128, 64, 32]) {
    await sharp(path.join(__dirname, 'kestri-portrait-source.png'))
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
