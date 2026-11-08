"""Prepare transparent chibi portraits, views and the exact S/H video references.
The generated turnaround PNGs are the source assets; this script only splits,
scales and lays them out, without changing the drawn design.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage
import spec

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "reference" / "chibi"
SOURCE_SIZE = (1280, 720)
SOURCE_HEIGHT = 468
SOURCE_FEET = 612
SOURCE_DRAG_OFFSET = 22
VIEW_SIZE = (1200, 1200)
VIEW_HEIGHT = 1000
VIEW_FEET = 1100

def bbox(image, threshold=16):
    alpha = np.asarray(image.convert("RGBA"))[:, :, 3]
    yy, xx = np.nonzero(alpha > threshold)
    if not len(xx):
        raise ValueError("Empty transparent image")
    return (int(xx.min()), int(yy.min()), int(xx.max()) + 1, int(yy.max()) + 1)

def split_sheet(path):
    image = Image.open(path).convert("RGBA")
    alpha = np.asarray(image)[:, :, 3]
    if np.mean(alpha < 8) < 0.05:
        raise ValueError(str(path) + ": expected real transparent background, not a painted checkerboard")
    mask = alpha > 16
    labels, count = ndimage.label(mask)
    sizes = np.bincount(labels.ravel())
    if count < 3:
        raise ValueError(str(path) + ": fewer than three separate views")
    bodies = np.argsort(sizes[1:])[-3:] + 1
    centres = ndimage.center_of_mass(mask, labels, bodies)
    bodies = [int(label) for _, label in sorted(zip([p[1] for p in centres], bodies))]
    centres = [ndimage.center_of_mass(mask, labels, [body])[0] for body in bodies]
    if not all(sizes[body] > mask.size * 0.015 for body in bodies):
        raise ValueError("Expected three full figures, not a figure plus detached ornaments")
    groups = {body: i for i, body in enumerate(bodies)}
    for label in range(1, count + 1):
        if label in groups or sizes[label] < 4:
            continue
        cy, cx = ndimage.center_of_mass(mask, labels, [label])[0]
        groups[label] = min(range(3), key=lambda i: (cx - centres[i][1]) ** 2 + 0.1 * (cy - centres[i][0]) ** 2)
    crops = []
    for index in range(3):
        chosen = np.zeros(mask.shape, dtype=bool)
        for label, group in groups.items():
            if group == index:
                chosen |= labels == label
        # Include anti-aliased pixels immediately next to the selected shape.
        allowed = ndimage.binary_dilation(chosen, iterations=2)
        raw = np.array(image)
        raw[:, :, 3] = np.where(allowed, raw[:, :, 3], 0)
        raw[:, :, 3][raw[:, :, 3] < 4] = 0
        raw[:, :, 3][raw[:, :, 3] >= 250] = 255
        isolated = Image.fromarray(raw, "RGBA")
        box = bbox(isolated, 1)
        crops.append(isolated.crop(box))
    return crops

def place(image, size, height, feet, background=(0, 0, 0, 0)):
    box = bbox(image)
    cropped = image.crop(box)
    scale = height / float(cropped.height)
    scaled = cropped.resize((max(1, round(cropped.width * scale)), height), Image.LANCZOS)
    # Use the bottom shoe band as the body pivot, rather than a wide tail.
    alpha = np.asarray(cropped)[:, :, 3]
    yy, xx = np.nonzero(alpha > 32)
    bottom = yy.max()
    selected = yy >= bottom - max(3, round(cropped.height * 0.045))
    pivot = (xx[selected].min() + xx[selected].max()) / 2.0
    x = round(size[0] / 2 - pivot * scale)
    y = feet - height
    if x < 8 or x + scaled.width > size[0] - 8 or y < 8 or feet > size[1] - 8:
        raise ValueError("Normalisation would crop the character")
    canvas = Image.new("RGBA", size, background)
    canvas.alpha_composite(scaled, (x, y))
    return canvas

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chars", nargs="+", choices=[c["id"] for c in spec.CHARACTERS])
    args = parser.parse_args(argv)
    chars = [c for c in spec.CHARACTERS if not args.chars or c["id"] in args.chars]
    for directory in ("portraits", "views", "firstframes"):
        (ART / directory).mkdir(parents=True, exist_ok=True)
    manifest_path = ART / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"characters": {}}
    for char in chars:
        cid = char["id"]
        sheet = ART / "turnarounds" / (cid + ".png")
        crops = split_sheet(sheet)
        entries = {}
        for label, crop in zip(("front", "side", "back"), crops):
            view = place(crop, VIEW_SIZE, VIEW_HEIGHT, VIEW_FEET)
            target = ART / "views" / (cid + "-" + label + ".png")
            view.save(target)
            entries[label] = target.relative_to(ROOT).as_posix()
        portrait = place(crops[0], VIEW_SIZE, VIEW_HEIGHT, VIEW_FEET)
        portrait.save(ART / "portraits" / (cid + ".png"))
        for suffix, offset in (("", 0), ("-drag", SOURCE_DRAG_OFFSET)):
            frame = place(crops[0], SOURCE_SIZE, SOURCE_HEIGHT, SOURCE_FEET - offset, (0, 255, 0, 255))
            frame.convert("RGB").save(ART / "firstframes" / (cid + suffix + ".png"))
        manifest["characters"][cid] = {
            "name": char["name"], "source": sheet.relative_to(ROOT).as_posix(),
            "source_sha256": hashlib.sha256(sheet.read_bytes()).hexdigest(),
            "portrait": "reference/chibi/portraits/" + cid + ".png", "views": entries,
            "standing_reference": "reference/chibi/firstframes/" + cid + ".png",
            "drag_reference": "reference/chibi/firstframes/" + cid + "-drag.png"
        }
        print("prepared " + cid)
    manifest["geometry"] = {
        "source_size": list(SOURCE_SIZE), "standing_height": SOURCE_HEIGHT,
        "standing_feet_y": SOURCE_FEET, "drag_offset_y": SOURCE_DRAG_OFFSET,
        "output_size": [640, 360], "fps": 24, "normalised_master": [2160, 1215],
        "normalised_character_height": 900, "normalised_feet_y": 1115
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if len(manifest["characters"]) == len(spec.CHARACTERS):
        make_overview()
    return manifest

def make_overview():
    sheet = Image.new("RGB", (2000, 1160), (245, 247, 252))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 27)
    except OSError:
        font = ImageFont.load_default()
    for index, char in enumerate(spec.CHARACTERS):
        portrait = Image.open(ART / "portraits" / (char["id"] + ".png")).convert("RGBA")
        portrait.thumbnail((470, 510), Image.LANCZOS)
        x = (index % 4) * 500 + (500 - portrait.width) // 2
        y = (index // 4) * 580
        sheet.paste(portrait, (x, y), portrait)
        draw.text(((index % 4) * 500 + 180, y + 535), char["id"], fill=(35, 38, 55), font=font)
    target = ROOT / "docs" / "screenshots" / "chibi-all8.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(target)

if __name__ == "__main__":
    main()
