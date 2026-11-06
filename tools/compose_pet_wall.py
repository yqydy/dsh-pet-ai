# -*- coding: utf-8 -*-
"""Compose captured dsh-pet desktop windows into one labeled pet-wall image.

Input : build/shots/pets/pet-*.png (PrintWindow captures, black background)
        build/shots/pets/windows.json
Output: build/shots/pets-wall.png

The captured windows show one pet each on a transparent (=> black) background.
We key out near-black pixels, trim, scale and lay them out on a soft gradient
background, then label with the character name.
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOT_DIR = os.path.join(ROOT, 'build', 'shots', 'pets')
OUT = os.path.join(ROOT, 'build', 'shots', 'pets-wall.png')

NAMES = ['DeepSeek 娘', 'GPT 娘', 'Claude 娘', 'Grok 娘',
         'Gemini 娘', 'Kimi 娘', 'GLM 娘', 'Qwen 娘']

CELL_W, CELL_H = 380, 420
COLS = 4
PAD = 18
TITLE_H = 92


def load_font(size):
    for p in [r'C:\Windows\Fonts\msyh.ttc', r'C:\Windows\Fonts\msyhbd.ttc',
              r'C:\Windows\Fonts\simhei.ttf', r'C:\Windows\Fonts\arial.ttf']:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def key_black(im, threshold=26):
    """Make near-black background transparent, keep pet pixels."""
    im = im.convert('RGBA')
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if r < threshold and g < threshold and b < threshold:
                px[x, y] = (r, g, b, 0)
    return im


def trim(im):
    bbox = im.getbbox()
    return im.crop(bbox) if bbox else im


def fit(im, max_w, max_h):
    w, h = im.size
    s = min(max_w / float(w), max_h / float(h))
    return im.resize((max(1, int(w * s)), max(1, int(h * s))), Image.LANCZOS)


def main():
    mapping = {}
    mapping_path = os.path.join(SHOT_DIR, 'mapping.json')
    if os.path.exists(mapping_path):
        with open(mapping_path, encoding='utf-8') as f:
            mapping = json.load(f)
    files = [f for f in mapping if os.path.exists(os.path.join(SHOT_DIR, f))]
    if not files:
        files = sorted(f for f in os.listdir(SHOT_DIR) if f.startswith('pet-') and f.endswith('.png'))
    files = [f for f in files if Image.open(os.path.join(SHOT_DIR, f)).width < 1000]
    if not files:
        print('no pet captures in', SHOT_DIR)
        sys.exit(1)
    rows = (len(files) + COLS - 1) // COLS
    W = PAD + COLS * (CELL_W + PAD)
    H = TITLE_H + PAD + rows * (CELL_H + PAD)
    canvas = Image.new('RGB', (W, H), (18, 20, 34))
    # soft gradient background
    grad = Image.new('RGB', (W, H))
    gd = grad.load()
    for y in range(H):
        t = y / float(H - 1)
        r = int(18 + 26 * t)
        g = int(20 + 24 * t)
        b = int(34 + 44 * t)
        for x in range(W):
            gd[x, y] = (r, g, b)
    canvas = grad
    d = ImageDraw.Draw(canvas)
    title_font = load_font(34)
    sub_font = load_font(16)
    name_font = load_font(22)
    d.text((PAD + 4, 20), 'AI 娘桌宠 · dsh-pet 实际渲染截图', font=title_font, fill=(240, 242, 255))
    d.text((PAD + 6, 62), '8 位角色 · 640×360 透明动画 · 由 dsh-pet 桌面模式窗口抓取',
           font=sub_font, fill=(150, 160, 200))

    for i, fn in enumerate(files):
        row, col = divmod(i, COLS)
        x0 = PAD + col * (CELL_W + PAD)
        y0 = TITLE_H + PAD + row * (CELL_H + PAD)
        # cell background
        cell = Image.new('RGB', (CELL_W, CELL_H), (28, 31, 48))
        cd = ImageDraw.Draw(cell)
        for yy in range(CELL_H):
            t = yy / float(CELL_H)
            cd.line([(0, yy), (CELL_W, yy)],
                    fill=(int(28 + 16 * t), int(31 + 16 * t), int(48 + 30 * t)))
        im = Image.open(os.path.join(SHOT_DIR, fn))
        im = key_black(im)
        im = trim(im)
        im = fit(im, CELL_W - 46, CELL_H - 70)
        canvas.paste(cell, (x0, y0))
        px = x0 + (CELL_W - im.width) // 2
        py = y0 + 18 + (CELL_H - 70 - im.height) // 2
        canvas.paste(im, (px, py), im)
        label = mapping.get(fn, '')
        if not label:
            idx = int(fn.replace('pet-', '').replace('.png', '')) - 1
            label = NAMES[idx] if idx < len(NAMES) else os.path.splitext(fn)[0]
        try:
            tw = d.textlength(label, font=name_font)
        except AttributeError:
            tw = name_font.getsize(label)[0]
        d.text((x0 + (CELL_W - tw) / 2, y0 + CELL_H - 46), label, font=name_font,
               fill=(225, 232, 255))
    canvas.save(OUT)
    print('saved', OUT, canvas.size)


if __name__ == '__main__':
    main()
