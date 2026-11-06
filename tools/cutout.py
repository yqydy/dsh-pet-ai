# -*- coding: utf-8 -*-
"""Background removal for AI-girl portrait / turnaround art.

White-background illustration -> RGBA cutout with soft edges.
Pure numpy + PIL, no scipy needed (vectorized flood fill from borders).
"""
import os
import sys
import numpy as np
from PIL import Image, ImageFilter

WHITE = 235  # channel threshold for "background white"
TOL = 18    # max per-channel deviation allowed for a pixel to be considered joinable


def flood_background(rgb):
    """Return boolean mask of background connected to the image border.

    Background = near-white pixels connected (8-neighbour) to the border
    through near-white pixels.  Vectorised iterative dilation keeps it fast.
    """
    h, w, _ = rgb.shape
    near_white = np.min(rgb, axis=2) >= WHITE
    # Allow slight grey/off-white: low saturation and bright
    mx = rgb.max(axis=2).astype(np.int16)
    mn = np.min(rgb, axis=2).astype(np.int16)
    near_white |= (mn >= 225) & ((mx - mn) <= TOL)

    # seed: border pixels that are near white
    seed = np.zeros((h, w), dtype=bool)
    seed[0, :] = near_white[0, :]
    seed[-1, :] = near_white[-1, :]
    seed[:, 0] = near_white[:, 0]
    seed[:, -1] = near_white[:, -1]

    mask = seed.copy()
    # grow through near-white pixels only
    allowed = near_white
    for _ in range(max(h, w) + 2):
        grown = mask.copy()
        grown[1:, :] |= mask[:-1, :]
        grown[:-1, :] |= mask[1:, :]
        grown[:, 1:] |= mask[:, :-1]
        grown[:, :-1] |= mask[:, 1:]
        # diagonals
        grown[1:, 1:] |= mask[:-1, :-1]
        grown[:-1, :-1] |= mask[1:, 1:]
        grown[1:, :-1] |= mask[:-1, 1:]
        grown[:-1, 1:] |= mask[1:, :-1]
        new = grown & allowed
        if np.array_equal(new, mask):
            break
        mask = new
    return mask


def cutout(src_path, dst_path, erode=1, blur=0.9, pad=6):
    im = Image.open(src_path).convert('RGB')
    rgb = np.asarray(im).astype(np.uint8)
    h, w, _ = rgb.shape
    bg = flood_background(rgb)

    fg = ~bg
    # if empty guard
    if not fg.any():
        raise RuntimeError('no foreground found: ' + src_path)

    alpha = fg.astype(np.uint8) * 255
    a = Image.fromarray(alpha, 'L')

    # shrink 1px to eat the white fringe, then soften
    if erode > 0:
        a = a.filter(ImageFilter.MinFilter(2 * erode + 1))
    if blur > 0:
        a = a.filter(ImageFilter.GaussianBlur(blur))

    rgba = im.convert('RGBA')
    rgba.putalpha(a)
    # trim to content bbox
    bbox = a.getbbox()
    if bbox:
        x0, y0, x1, y1 = bbox
        x0 = max(0, x0 - pad); y0 = max(0, y0 - pad)
        x1 = min(w, x1 + pad); y1 = min(h, y1 + pad)
        rgba = rgba.crop((x0, y0, x1, y1))
    rgba.save(dst_path)
    return rgba


def checker_preview(rgba, bg1=200, bg2=120, tile=24):
    """Composite on a checkerboard so transparency is visible in previews."""
    w, h = rgba.size
    yy, xx = np.mgrid[0:h, 0:w]
    checker = (((xx // tile) + (yy // tile)) % 2).astype(np.uint8)
    bg = np.where(checker == 0, bg1, bg2).astype(np.uint8)
    bg_rgb = np.stack([bg, bg, bg], axis=2)
    arr = np.asarray(rgba).astype(np.float32)
    a = arr[:, :, 3:4] / 255.0
    out = arr[:, :, :3] * a + bg_rgb * (1 - a)
    return Image.fromarray(out.astype(np.uint8), 'RGB')


if __name__ == '__main__':
    ref = r'F:\ceshi\dsh-pet-ai-girls\reference'
    out = r'F:\ceshi\dsh-pet-ai-girls\build\cutouts'
    os.makedirs(out, exist_ok=True)
    names = sys.argv[1:] or ['deepseek', 'gpt', 'claude', 'grok', 'gemini', 'kimi', 'glm', 'qwen']
    for n in names:
        src = os.path.join(ref, 'portrait-%s.webp' % n)
        dst = os.path.join(out, 'portrait-%s.png' % n)
        rgba = cutout(src, dst)
        prev = checker_preview(rgba)
        prev.save(os.path.join(out, 'preview-%s.png' % n))
        print('%-10s %s -> rgba %s preview saved' % (n, Image.open(src).size, rgba.size))
