# -*- coding: utf-8 -*-
"""Extract front / left / back cutouts from lmy414/ai-chan-sheets 三视图 slices.

The slices are horizontal setting-board partitions: three cards side by side,
each with a title (正面 / 左侧 / 背面) and a footer note on a white inner
background, framed by light-grey rounded borders on a light page background.

Pipeline:
  1. detect the three card rectangles from the light-grey border lines,
  2. crop just inside each card, flood-fill the white background,
  3. drop title / footer text components, keep the figure (largest component)
     plus small accessories that sit close to it,
  4. normalise every view to the common canvas (height 1000, feet 1060,
     pivot centred on the bottom 12%), like tools/threeview.py,
  5. write build/sheets/<char>-{front,side,back}.png + <char>-review.png.

Usage:
  python tools/sheets.py                 # all 8 characters
  python tools/sheets.py deepseek gpt    # subset
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cutout import flood_background, checker_preview  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, 'reference', 'sheets')
OUT_DIR = os.path.join(ROOT, 'build', 'sheets')

CHARS = ['deepseek', 'gpt', 'claude', 'grok', 'gemini', 'kimi', 'glm', 'qwen']

CHAR_H = 1000
CANVAS_W = 720
CANVAS_H = 1120
FEET_Y = 1060

MAX_W = 2200   # downscale target for speed; still ~1100px tall figures


def _clusters(flags):
    """Return list of (start, end) index ranges for True runs, merging 1px gaps."""
    runs = []
    start = None
    for i, v in enumerate(flags):
        if v and start is None:
            start = i
        elif not v and start is not None:
            runs.append([start, i - 1])
            start = None
    if start is not None:
        runs.append([start, len(flags) - 1])
    merged = []
    for r in runs:
        if merged and r[0] - merged[-1][1] <= 2:
            merged[-1][1] = r[1]
        else:
            merged.append(r)
    return merged


def detect_cards(im):
    """Find the three card rectangles as (left, top, right, bottom) tuples."""
    rgb = np.asarray(im.convert('RGB')).astype(np.int16)
    h, w, _ = rgb.shape
    mx = rgb.max(axis=2)
    mn = rgb.min(axis=2)
    # light grey border lines: low saturation, mid-high brightness
    grey = ((mx - mn) <= 28) & (mn >= 150) & (mn <= 238)
    col_score = grey.sum(axis=0) / float(h)
    row_score = grey.sum(axis=1) / float(w)
    vlines = _clusters(col_score > 0.55)
    hlines = _clusters(row_score > 0.45)
    if len(vlines) < 4 or not hlines:
        return None
    # merge line clusters to their centres
    vx = [int((a + b) / 2) for a, b in vlines]
    hy = [int((a + b) / 2) for a, b in hlines]
    top, bottom = min(hy), max(hy)
    # group vertical lines into pairs that bound 3 cards; if there are 6 lines
    # use consecutive pairs, otherwise fall back to thirds.
    if len(vx) >= 6:
        vx = vx[:6]
        cards = [(vx[i], top, vx[i + 1], bottom) for i in (0, 2, 4)]
    elif len(vx) == 4:
        cards = [(vx[0], top, vx[1], bottom), (vx[1], top, vx[2], bottom),
                 (vx[2], top, vx[3], bottom)]
    else:
        return None
    cards = [c for c in cards if c[2] - c[0] > w * 0.1]
    if len(cards) != 3:
        return None
    return cards


def _keep_components(fg, crop_h):
    """Figure mask: largest component + close accessories, minus text rows."""
    lbl, n = ndimage.label(fg, structure=np.ones((3, 3), dtype=np.uint8))
    if n == 0:
        return fg
    sizes = ndimage.sum(fg, lbl, range(1, n + 1))
    order = np.argsort(sizes)[::-1]
    body = int(order[0] + 1)
    ys, xs = np.nonzero(lbl == body)
    bx0, bx1, by0, by1 = xs.min(), xs.max(), ys.min(), ys.max()
    keep = np.zeros_like(fg)
    keep[lbl == body] = True
    # text rows: title in the top 5%, footer in the bottom 5%
    text_cut_top = crop_h * 0.05
    text_cut_bottom = crop_h * 0.95
    for rank in order[1:]:
        cand = int(rank + 1)
        area = sizes[rank]
        if area < max(20, sizes[order[0]] * 0.0004):
            continue
        cys, cxs = np.nonzero(lbl == cand)
        cy = cys.mean()
        if cy < text_cut_top or cy > text_cut_bottom:
            continue
        cx = cxs.mean()
        # only accessories close to the body bbox
        if (bx0 - crop_h * 0.04 <= cx <= bx1 + crop_h * 0.04 and
                by0 - crop_h * 0.03 <= cy <= by1 + crop_h * 0.03):
            keep[lbl == cand] = True
    return keep


def crop_figure(card):
    """card = (rgb array, x0, y0, x1, y1) -> RGBA crop of the figure."""
    rgb, x0, y0, x1, y1 = card
    pad = 4
    x0, y0 = max(0, x0 + pad), max(0, y0 + pad)
    x1, y1 = min(rgb.shape[1], x1 - pad), min(rgb.shape[0], y1 - pad)
    sub = rgb[y0:y1, x0:x1]
    bg = flood_background(sub)
    fg = ~bg
    fg = _keep_components(fg, sub.shape[0])
    ys, xs = np.nonzero(fg)
    if len(ys) == 0:
        return None
    p = 6
    bx0, bx1 = max(0, xs.min() - p), min(sub.shape[1], xs.max() + p + 1)
    by0, by1 = max(0, ys.min() - p), min(sub.shape[0], ys.max() + p + 1)
    alpha = (fg[by0:by1, bx0:bx1].astype(np.uint8)) * 255
    out = Image.fromarray(sub[by0:by1, bx0:bx1].copy(), 'RGB').convert('RGBA')
    out.putalpha(Image.fromarray(alpha, 'L'))
    return out


def _bottom_pivot(img):
    a = np.asarray(img)[:, :, 3]
    ys, xs = np.nonzero(a > 32)
    if len(ys) == 0:
        return img.width / 2.0, float(img.height)
    bottom = ys.max()
    band = max(3, int(img.height * 0.12))
    sel = ys >= bottom - band
    return (xs[sel].min() + xs[sel].max()) / 2.0, float(bottom)


def normalise(img):
    bbox = img.getbbox()
    if not bbox:
        return Image.new('RGBA', (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    img = img.crop(bbox)
    px, feet_y = _bottom_pivot(img)
    scale = CHAR_H / max(1.0, img.height)
    nw = max(1, int(round(img.width * scale)))
    nh = max(1, int(round(img.height * scale)))
    scaled = img.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new('RGBA', (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    if nw > CANVAS_W:
        left = int(round(px * scale - CANVAS_W / 2.0))
        left = max(0, min(left, nw - CANVAS_W))
        scaled = scaled.crop((left, 0, left + CANVAS_W, nh))
        paste_x = 0
    else:
        paste_x = int(round(CANVAS_W / 2.0 - px * scale))
    paste_y = int(round(FEET_Y - feet_y * scale))
    canvas.alpha_composite(scaled, (paste_x, paste_y))
    return canvas


def font(size):
    for p in [r'C:\Windows\Fonts\msyh.ttc', r'C:\Windows\Fonts\simhei.ttf']:
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


def process(name):
    src = os.path.join(SRC_DIR, '%s-threeview.webp' % name)
    if not os.path.exists(src):
        src = os.path.join(SRC_DIR, '%s-threeview.png' % name)
    if not os.path.exists(src):
        print('MISS', src)
        return False
    im = Image.open(src).convert('RGB')
    if im.width > MAX_W:
        scale = MAX_W / float(im.width)
        im = im.resize((MAX_W, int(round(im.height * scale))), Image.LANCZOS)
    rgb = np.asarray(im)
    cards = detect_cards(im)
    if cards is None:
        # fallback: equal thirds, top/bottom inset
        w, h = im.size
        cards = [(w // 3 * i + 6, int(h * 0.06), w // 3 * (i + 1) - 6, int(h * 0.94))
                 for i in range(3)]
        print('  WARN card detection fallback for', name)
    views = []
    for (x0, y0, x1, y1) in cards:
        v = crop_figure((rgb, x0, y0, x1, y1))
        if v is None:
            print('  ERR empty view for', name)
            return False
        views.append(normalise(v))
    os.makedirs(OUT_DIR, exist_ok=True)
    for label, img in zip(['front', 'side', 'back'], views):
        img.save(os.path.join(OUT_DIR, '%s-%s.png' % (name, label)))
    review_montage(views, os.path.join(OUT_DIR, '%s-review.png' % name), name)
    print('%-10s cards=%s -> %s' % (name, cards, OUT_DIR))
    return True


def main():
    names = sys.argv[1:] or CHARS
    ok = 0
    for n in names:
        if process(n):
            ok += 1
    print('done %d/%d' % (ok, len(names)))


if __name__ == '__main__':
    main()
