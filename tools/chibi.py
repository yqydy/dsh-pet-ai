# -*- coding: utf-8 -*-
"""Chibi (Q版) conversion: smooth big-head / short-body warp for full-body art.

Prototype: takes a normalised three-view image (720x1120 canvas, character
height 1000px, feet at y=1060) and produces a chibi-proportioned version:

  * vertical magnification decays smoothly from k_top at the head to
    k_bottom at the feet (head becomes much taller relative to the body),
  * horizontal magnification decays from k_top_x to k_bottom_x (head /
    shoulders wider, legs / skirt narrower),
  * because both mappings are smooth there are no seams; long hair, tails and
    props stretch continuously,
  * the result is re-normalised to the same canvas (height 1000, feet 1060,
    pivot centred on the bottom 12% rows).

Usage:
  python tools/chibi.py                       # all chars from build/threeview
  python tools/chibi.py deepseek gpt          # subset
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# canonical three-view cutouts extracted from lmy414/ai-chan-sheets (tools/sheets.py)
TV_DIR = os.path.join(ROOT, 'build', 'sheets')
OUT_DIR = os.path.join(ROOT, 'build', 'chibi')
CHARS = ['deepseek', 'gpt', 'claude', 'grok', 'gemini', 'kimi', 'glm', 'qwen']

CANVAS_W, CANVAS_H = 720, 1120
CHAR_H = 1000.0
FEET_Y = 1060.0
TOP_Y = FEET_Y - CHAR_H

# tunables (chibi flavour)
K_TOP_Y = 1.78     # vertical magnification at the very top (head)
K_BOT_Y = 0.46     # vertical magnification at the feet (legs shrunk)
K_TOP_X = 1.72     # horizontal magnification at the head
K_BOT_X = 0.55     # horizontal magnification at the feet
FALLOFF = 0.72     # 0..1: how far down the head magnification reaches


def _smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _scale_y(t):
    """dy_out/dy_in at normalised height t (0 top, 1 feet)."""
    return K_BOT_Y + (K_TOP_Y - K_BOT_Y) * (1.0 - _smoothstep(t / FALLOFF))


def _scale_x(t):
    """dx_out/dx_in at normalised height t."""
    return K_BOT_X + (K_TOP_X - K_BOT_X) * (1.0 - _smoothstep(t / FALLOFF))


def chibi_warp(img, samples=4):
    """Continuous cartoon warp; returns RGBA image (same canvas convention)."""
    src = np.asarray(img.convert('RGBA')).astype(np.float32)
    h, w = src.shape[:2]
    # precompute vertical mapping: for each source row its [y0, y1) output span
    ys = np.arange(h, dtype=np.float32)
    t = np.clip((ys - TOP_Y) / CHAR_H, 0.0, 1.0)
    sy = np.where(ys < TOP_Y, 1.0, _scale_y(t))
    sy = np.where(ys > FEET_Y, 1.0, sy)
    spans = sy
    cum = np.concatenate([[0.0], np.cumsum(spans)])
    total = cum[-1]
    out_w = int(round(w * K_TOP_X)) + 4
    out = np.zeros((int(np.ceil(total)), out_w, 4), dtype=np.float32)
    # build output rows by resampling source rows (nearest with 4x supersample)
    oy = np.arange(out.shape[0], dtype=np.float32) + 0.5
    # inverse cumulative: find source y for output y
    src_y = np.interp(oy, cum[:-1], ys + 0.0)
    for i, y in enumerate(src_y):
        y0 = int(np.clip(np.floor(y), 0, h - 1))
        y1 = min(h - 1, y0 + 1)
        # vertical average for compression zones (smoother)
        frac = y - y0
        row = src[y0] * (1 - frac) + src[y1] * frac
        th = np.clip((y - TOP_Y) / CHAR_H, 0.0, 1.0)
        sx = _scale_x(th)
        ow = max(1, int(round(w * sx)))
        # horizontal resample around the pivot x (canvas centre)
        xs = (np.arange(ow) + 0.5) / sx - 0.5
        xs = np.clip(xs, 0, w - 1)
        x0 = np.floor(xs).astype(np.int32)
        x1 = np.clip(x0 + 1, 0, w - 1)
        fx = (xs - x0)[:, None]
        res = row[x0] * (1 - fx) + row[x1] * fx
        left = (out.shape[1] - ow) // 2
        out[i, left:left + ow] = res
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), 'RGBA')


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
    """Re-scale / re-centre to the standard three-view canvas."""
    bbox = img.getbbox()
    if not bbox:
        return Image.new('RGBA', (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    im = img.crop(bbox)
    px, _feet = _bottom_pivot(im)
    scale = CHAR_H / im.height
    nw = max(1, int(round(im.width * scale)))
    nh = int(round(CHAR_H))
    scaled = im.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new('RGBA', (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    if nw > CANVAS_W:
        left = int(round(px * scale - CANVAS_W / 2.0))
        left = max(0, min(left, nw - CANVAS_W))
        scaled = scaled.crop((left, 0, left + CANVAS_W, nh))
        paste_x = 0
    else:
        paste_x = int(round(CANVAS_W / 2.0 - px * scale))
        if paste_x < 0:
            scaled = scaled.crop((-paste_x, 0, scaled.width, nh))
            paste_x = 0
        elif paste_x + scaled.width > CANVAS_W:
            scaled = scaled.crop((0, 0, CANVAS_W - paste_x, nh))
    paste_y = int(round(FEET_Y - CHAR_H))
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


def review(orig, chibi, out_path, title):
    """Before/after contact sheet on checkerboard."""
    from cutout import checker_preview  # local import to avoid hard dep at module load

    def prep(im):
        bg = checker_preview(im, tile=18)
        bg.thumbnail((330, 520))
        return bg

    a, b = prep(orig), prep(chibi)
    W = a.width + b.width + 30
    H = max(a.height, b.height) + 40
    sheet = Image.new('RGB', (W, H), (20, 20, 30))
    d = ImageDraw.Draw(sheet)
    d.text((8, 8), title + '  (left: original / right: chibi)', fill=(240, 240, 255), font=font(18))
    sheet.paste(a, (10, 36))
    sheet.paste(b, (a.width + 20, 36))
    sheet.save(out_path)


def lineup(names):
    """All chibi fronts on a checkerboard, for quick visual review."""
    from cutout import checker_preview
    cell_w, cell_h = 200, 330
    img = Image.new('RGB', (cell_w * len(names), cell_h + 34), (18, 20, 34))
    d = ImageDraw.Draw(img)
    for i, c in enumerate(names):
        p = os.path.join(OUT_DIR, '%s-front.png' % c)
        if not os.path.exists(p):
            continue
        prev = checker_preview(Image.open(p).convert('RGBA'), tile=12)
        prev.thumbnail((cell_w - 8, cell_h - 26))
        img.paste(prev, (i * cell_w + (cell_w - prev.width) // 2, 30))
        d.text((i * cell_w + 8, 6), c, fill=(240, 240, 255), font=font(16))
    img.save(os.path.join(OUT_DIR, 'lineup.png'))


def main():
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    names = sys.argv[1:] or CHARS
    os.makedirs(OUT_DIR, exist_ok=True)
    for c in names:
        for label in ['front', 'side', 'back']:
            src_p = os.path.join(TV_DIR, '%s-%s.png' % (c, label))
            if not os.path.exists(src_p):
                print('MISS', src_p)
                continue
            orig = Image.open(src_p).convert('RGBA')
            warped = normalise(chibi_warp(orig))
            warped.save(os.path.join(OUT_DIR, '%s-%s.png' % (c, label)))
        # review sheet from the front view
        orig = Image.open(os.path.join(TV_DIR, '%s-front.png' % c)).convert('RGBA')
        chibi = Image.open(os.path.join(OUT_DIR, '%s-front.png' % c)).convert('RGBA')
        review(orig, chibi, os.path.join(OUT_DIR, '%s-review.png' % c), c)
        portrait = chibi.crop(chibi.getbbox())
        canvas = Image.new('RGBA', (portrait.width, portrait.height + 6), (0, 0, 0, 0))
        canvas.alpha_composite(portrait, (0, 0))
        canvas.save(os.path.join(OUT_DIR, '%s-portrait.png' % c))
        print('OK', c)

    # always build the full 8-character lineup, even for subset runs
    lineup(CHARS)


if __name__ == '__main__':
    main()
