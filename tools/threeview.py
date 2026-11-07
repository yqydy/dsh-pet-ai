# -*- coding: utf-8 -*-
"""Extract front / side / back cutouts from a three-view turnaround sheet.

The GenderSwapAI turnaround sheets are 1536x1024: three full-body figures
(front, left-facing side, back) drawn on a white background, feet roughly on
the same baseline.  This script:

  1. removes the white background (reusing cutout.flood_background),
  2. splits the sheet into the three figures by finding vertical gaps of
     foreground (merging small gaps so floating accessories stay attached),
  3. normalises every view to a common canvas: identical character height,
     feet baseline and a common horizontal pivot (centre of the bottom rows),
  4. writes `build/threeview/<char>-{front,side,back}.png` plus a review
     montage `build/threeview/<char>-review.png`.

Usage:
  python tools/threeview.py                 # all 8 characters
  python tools/threeview.py gpt kimi        # subset
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cutout import flood_background, checker_preview  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF_DIR = os.path.join(ROOT, 'reference')
OUT_DIR = os.path.join(ROOT, 'build', 'threeview')

CHARS = ['deepseek', 'gpt', 'claude', 'grok', 'gemini', 'kimi', 'glm', 'qwen']

# normalised canvas: character height and feet baseline (both in px)
CHAR_H = 1000
CANVAS_W = 720
CANVAS_H = 1120
FEET_Y = 1060          # feet baseline inside the normalised canvas


def extract_views(sheet_path):
    """Split the sheet into the three figures and return RGBA crops.

    Figures are the 3 largest connected components of the foreground; small
    detached parts (sparkles, ribbons) are assigned to the nearest figure so
    they travel with it.
    """
    im = Image.open(sheet_path).convert('RGB')
    rgb = np.asarray(im).astype(np.uint8)
    h, w, _ = rgb.shape
    bg = flood_background(rgb)
    fg = ~bg
    lbl, n = ndimage.label(fg, structure=np.ones((3, 3), dtype=np.uint8))
    if n < 3:
        raise RuntimeError('%s: only %d foreground components' % (sheet_path, n))
    sizes = ndimage.sum(fg, lbl, range(1, n + 1))
    big = list(np.argsort(sizes)[::-1][:3] + 1)
    # centroids of the three bodies (x order = front / side / back)
    coms = ndimage.center_of_mass(fg, lbl, big)
    bodies = [int(label) for _, label in sorted(zip([c[1] for c in coms], big))]
    body_coms = {}
    for label, (cy, cx) in zip(big, coms):
        body_coms[int(label)] = (cx, cy)
    # assign every other component to the nearest body centroid
    group_of = {int(label): i for i, label in enumerate(bodies)}
    for label in range(1, n + 1):
        if label in group_of:
            continue
        if sizes[label - 1] < 3:
            continue
        cy, cx = ndimage.center_of_mass(fg, lbl, [label])[0]
        best, best_d = None, 1e18
        for i, b in enumerate(bodies):
            bx, by = body_coms[b]
            # weight vertical distance less: accessories stay near their figure
            d = (cx - bx) ** 2 + 0.15 * (cy - by) ** 2
            if d < best_d:
                best, best_d = i, d
        group_of[int(label)] = best
    rgba = im.convert('RGBA')
    alpha = fg.astype(np.uint8) * 255
    views = []
    for i in range(3):
        mask = np.zeros_like(fg)
        for label, g in group_of.items():
            if g == i:
                mask |= (lbl == label)
        ys, xs = np.nonzero(mask)
        if len(ys) == 0:
            raise RuntimeError('%s: empty view %d' % (sheet_path, i))
        pad = 6
        x0, x1 = max(0, xs.min() - pad), min(w, xs.max() + pad + 1)
        y0, y1 = max(0, ys.min() - pad), min(h, ys.max() + pad + 1)
        a = np.zeros((y1 - y0, x1 - x0), dtype=np.uint8)
        a[mask[y0:y1, x0:x1]] = 255
        view = rgba.crop((x0, y0, x1, y1))
        view.putalpha(Image.fromarray(a, 'L'))
        views.append(view)
    return views


def _bottom_pivot(img):
    """(pivot_x, feet_y): horizontal centre of the low 12% body rows."""
    a = np.asarray(img)[:, :, 3]
    ys, xs = np.nonzero(a > 32)
    if len(ys) == 0:
        return img.width / 2.0, float(img.height)
    bottom = ys.max()
    band = max(3, int(img.height * 0.12))
    sel = ys >= bottom - band
    px = (xs[sel].min() + xs[sel].max()) / 2.0
    return px, float(bottom)


def normalise(img):
    """Scale so character height = CHAR_H, align feet + pivot, paste on canvas."""
    px, feet_y = _bottom_pivot(img)
    top_y = 0.0  # bbox crop: top of the figure is 0
    char_h = feet_y - top_y
    scale = CHAR_H / char_h
    nw = max(1, int(round(img.width * scale)))
    nh = max(1, int(round(img.height * scale)))
    scaled = img.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new('RGBA', (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    paste_x = int(round(CANVAS_W / 2.0 - px * scale))
    paste_y = int(round(FEET_Y - feet_y * scale))
    canvas.alpha_composite(scaled, (paste_x, paste_y))
    return canvas


def font(size):
    for p in [r'C:\Windows\Fonts\msyh.ttc', r'C:\Windows\Fonts\simhei.ttf', r'C:\Windows\Fonts\arial.ttf']:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def review_montage(views, out_path, title):
    labels = ['front', 'side', 'back']
    cell_w, cell_h = 360, 560
    img = Image.new('RGB', (cell_w * 3, cell_h + 42), (18, 20, 34))
    d = ImageDraw.Draw(img)
    for i, v in enumerate(views):
        prev = checker_preview(v, tile=18)
        prev.thumbnail((cell_w - 20, cell_h - 30))
        x = i * cell_w + (cell_w - prev.width) // 2
        y = 36 + (cell_h - 30 - prev.height) // 2
        img.paste(prev, (x, y))
        d.text((i * cell_w + 10, 8), labels[i], fill=(240, 240, 255), font=font(20))
    img.save(out_path)


def main():
    names = sys.argv[1:] or CHARS
    os.makedirs(OUT_DIR, exist_ok=True)
    for name in names:
        sheet = os.path.join(REF_DIR, 'turnaround-%s.png' % name)
        views = extract_views(sheet)
        if len(views) != 3:
            raise RuntimeError('expected 3 views for ' + name)
        norm = [normalise(v) for v in views]
        for label, img in zip(['front', 'side', 'back'], norm):
            out = os.path.join(OUT_DIR, '%s-%s.png' % (name, label))
            img.save(out)
        review_montage(norm, os.path.join(OUT_DIR, '%s-review.png' % name), name)
        print('%-10s front %s side %s back %s -> %s'
              % (name, views[0].size, views[1].size, views[2].size, OUT_DIR))


if __name__ == '__main__':
    main()
