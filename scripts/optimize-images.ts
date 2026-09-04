// Compress card images so the repo (and Discord) stays light.
//
//   bun run scripts/optimize-images.ts              # every image in images/
//   bun run scripts/optimize-images.ts a.jpg b.png  # only these files
//
// Resizes to at most MAX_SIDE px on the longest side, re-encodes as progressive JPEG, strips
// metadata. A file is only rewritten when the result is at least 5% smaller, so already
// optimized files are never re-encoded. The pre-commit hook in hooks/ runs this on staged images.
import { readdirSync, statSync, writeFileSync } from "node:fs";
import { extname, join, basename } from "node:path";
import sharp from "sharp";

const MAX_SIDE = 1280; // Discord shows embed images at ~1280px at most
const QUALITY = 82;
const IMAGES_DIR = join(import.meta.dir, "..", "images");
const EXTS = new Set([".jpg", ".jpeg", ".png", ".webp"]);

async function optimize(path: string): Promise<[number, number]> {
  const before = statSync(path).size;
  const data = await sharp(path)
    .rotate() // apply EXIF orientation, then drop the metadata
    .resize({ width: MAX_SIDE, height: MAX_SIDE, fit: "inside", withoutEnlargement: true })
    .jpeg({ quality: QUALITY, progressive: true, mozjpeg: true })
    .toBuffer();
  if (data.length < before * 0.95) writeFileSync(path, data);
  return [before, statSync(path).size];
}

let files = process.argv.slice(2);
if (!files.length) files = readdirSync(IMAGES_DIR).sort().map((f) => join(IMAGES_DIR, f));
files = files.filter((f) => EXTS.has(extname(f).toLowerCase()) && statSync(f).isFile());

let totalBefore = 0, totalAfter = 0;
for (const f of files) {
  const [b, a] = await optimize(f);
  totalBefore += b;
  totalAfter += a;
  if (a < b) console.log(`${basename(f)}: ${b >> 10} KB -> ${a >> 10} KB`);
}
if (files.length) {
  const saved = 100 - Math.floor((totalAfter * 100) / Math.max(totalBefore, 1));
  console.log(`${files.length} files: ${totalBefore >> 10} KB -> ${totalAfter >> 10} KB (${saved}% smaller)`);
}
