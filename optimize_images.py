"""Compress card images so the repo (and Discord) stays light.

    python3 optimize_images.py              # every image in images/
    python3 optimize_images.py a.jpg b.png  # only these files

Resizes to at most MAX_SIDE px on the longest side, re-encodes as progressive JPEG,
strips metadata. A file is only rewritten when the result is smaller.
The pre-commit hook in hooks/ runs this on staged images automatically.
"""
import io
import os
import sys

from PIL import Image, ImageOps

MAX_SIDE = 1280   # Discord shows embed images at ~1280px at most
QUALITY = 82
IMAGES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")
EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def optimize(path):
    before = os.path.getsize(path)
    img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=QUALITY, optimize=True, progressive=True)
    data = buf.getvalue()
    if len(data) < before:
        with open(path, "wb") as f:
            f.write(data)
    return before, os.path.getsize(path)


def main(files):
    if not files:
        files = [os.path.join(IMAGES_DIR, f) for f in sorted(os.listdir(IMAGES_DIR))]
    files = [f for f in files if os.path.splitext(f)[1].lower() in EXTS and os.path.isfile(f)]
    total_before = total_after = 0
    for f in files:
        b, a = optimize(f)
        total_before += b
        total_after += a
        if a < b:
            print(f"{os.path.basename(f)}: {b // 1024} KB -> {a // 1024} KB")
    if files:
        saved = 100 - total_after * 100 // max(total_before, 1)
        print(f"{len(files)} files: {total_before // 1024} KB -> {total_after // 1024} KB ({saved}% smaller)")


if __name__ == "__main__":
    main(sys.argv[1:])
