# -*- coding: utf-8 -*-
"""Prototype: pseudo-3D turntable from front/side/back three-view cutouts.

Renders yaw frames by blending adjacent views (crossfade) and/or nearest-view
discrete sprites, then writes montages for visual review.

Usage: python tools/spin_test.py [char ...]
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TV_DIR = os.path.join(ROOT, 'build', 'threeview')
OUT_DIR = os.path.join(ROOT, 'build', 'spin-test')

CANVAS_W, CANVAS_H = 640, 360
CHAR_H = 322
GROUND_Y = 356
FEET_Y = 1060          # in the normalised 720x1120 threeview canvas


def font(size):
    for p in [r'C:\Windows\Fonts\msyh.ttc', r'C:\Windows\Fonts\simhei.ttf']:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


class TurnViews:
    def __init__(self, char):
        def load(label):
            im = Image.open(os.path.join(TV_DIR, '%s-%s.png' % (char, label))).convert('RGBA')
            return im
        self.front = load('front')
        self.side = load('side')          # facing left
        self.back = load('back')
        self.side_m = self.side.transpose(Image.FLIP_LEFT_RIGHT)   # facing right
        s = CHAR_H / 1000.0
        self.scale = s
        sw = max(1, int(round(self.front.width * s)))
        sh = max(1, int(round(self.front.height * s)))
        self.front = self.front.resize((sw, sh), Image.LANCZOS)
        self.side = self.side.resize((sw, sh), Image.LANCZOS)
        self.back = self.back.resize((sw, sh), Image.LANCZOS)
        self.side_m = self.side_m.resize((sw, sh), Image.LANCZOS)
        self.sw, self.sh = sw, sh
        self.pivot_y = int(round(FEET_Y * s))
        self.pivot_x = sw // 2

    def base(self, view, scale_x=1.0):
        """Place one view on the canvas (feet on GROUND_Y, pivot centred)."""
        canvas = Image.new('RGBA', (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
        img = view
        if abs(scale_x - 1.0) > 0.01:
            w = max(1, int(img.width * scale_x))
            img = img.resize((w, img.height), Image.LANCZOS)
        x = int(round(CANVAS_W / 2 - self.pivot_x * scale_x))
        y = int(round(GROUND_Y - self.pivot_y))
        canvas.alpha_composite(img, (x, y))
        return canvas

    def yaw_blend(self, yaw):
        """Crossfade between adjacent views at the given yaw (0..360)."""
        yaw = yaw % 360.0
        keys = [(0.0, self.front, self.base(self.front)),
                (90.0, self.side, self.base(self.side)),
                (180.0, self.back, self.base(self.back)),
                (270.0, self.side_m, self.base(self.side_m)),
                (360.0, self.front, self.base(self.front))]
        for i in range(len(keys) - 1):
            a, va, ca = keys[i]
            b, vb, cb = keys[i + 1]
            if a <= yaw <= b:
                t = (yaw - a) / (b - a)
                t = t * t * (3 - 2 * t)      # smoothstep
                return Image.blend(ca, cb, t)
        return keys[0][2]

    def yaw_nearest(self, yaw):
        """Discrete nearest view (with mirroring for the right half)."""
        yaw = yaw % 360.0
        if yaw < 45 or yaw >= 315:
            return self.base(self.front)
        if yaw < 135:
            return self.base(self.side if yaw < 90 else self.side)
        if yaw < 225:
            return self.base(self.back)
        return self.base(self.side_m)


def montage(views, char, mode):
    cols, rows = 6, 2
    cw, ch = 320, 220
    img = Image.new('RGB', (cols * cw, rows * ch + 40), (20, 20, 30))
    d = ImageDraw.Draw(img)
    d.text((8, 8), '%s · %s' % (char, mode), fill=(240, 240, 255), font=font(18))
    for i in range(12):
        yaw = i * 30
        frame = views.yaw_blend(yaw) if mode == 'blend' else views.yaw_nearest(yaw)
        bg = Image.new('RGB', (CANVAS_W, CANVAS_H), (45, 48, 64))
        bg.paste(frame, (0, 0), frame)
        bg.thumbnail((cw - 8, ch - 26))
        x = (i % cols) * cw + (cw - bg.width) // 2
        y = 36 + (i // cols) * ch + (ch - 26 - bg.height) // 2
        img.paste(bg, (x, y))
        d.text((i % cols * cw + 6, 36 + (i // cols) * ch + 2),
               '%d°' % yaw, fill=(230, 230, 240), font=font(14))
    img.save(os.path.join(OUT_DIR, '%s-%s.png' % (char, mode)))


def main():
    chars = sys.argv[1:] or ['gpt', 'deepseek', 'gemini']
    os.makedirs(OUT_DIR, exist_ok=True)
    for c in chars:
        views = TurnViews(c)
        montage(views, c, 'blend')
        montage(views, c, 'nearest')
        print('done', c)


if __name__ == '__main__':
    main()
