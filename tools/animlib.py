# -*- coding: utf-8 -*-
"""Paper-doll animation engine for AI-girl desktop pets.

Takes a transparent PNG cutout and bakes 640x360 / 24fps VP9-alpha webm clips
that the installed dsh-pet plugin can play as pet animations.

No external deps beyond numpy/PIL + an ffmpeg binary with libvpx-vp9.
"""
import math
import os
import shutil
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

CANVAS_W, CANVAS_H = 640, 360
FPS = 24
GROUND_Y = 356          # feet line on canvas
MAX_H = 322             # character height on canvas (leaves room for jumps/effects)
MAX_W = 600
FEET_PAD = 6            # cutout.py pads 6px below the feet

# ---------------------------------------------------------------------------
# Q版 (chibi) 2.5D turntable assets
# ---------------------------------------------------------------------------
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHIBI_DIR = os.path.join(ROOT_DIR, 'build', 'chibi')
THREEVIEW_DIR = os.path.join(ROOT_DIR, 'build', 'threeview')
TV_CHAR_H = 1000.0      # character height inside the normalised three-view canvas
TV_FEET_Y = 1060.0      # feet baseline inside the normalised three-view canvas
TV_SCALE = MAX_H / TV_CHAR_H

FFMPEG = os.environ.get(
    'PET_FFMPEG',
    r'C:\Users\20862\AppData\Roaming\Python\Python38\site-packages\imageio_ffmpeg\binaries\ffmpeg-win64-v4.2.2.exe',
)


# ----------------------------------------------------------------------------
# tiny 2D affine helpers (2x3 matrices)
# ----------------------------------------------------------------------------
def mat_mul(A, B):
    a, b, c = A
    d, e, f = B
    return (a * d + b * e, a * e + b * f, a * c + b * d + b * e * 0 + c,
            d * b + e * e * 0, 0, 0)  # placeholder, unused


def compose_affine(scale_x, scale_y, deg, tx, ty):
    """Return 2x3 forward matrix for: translate(tx,ty) * rotate(deg) * scale."""
    r = math.radians(deg)
    cos_r, sin_r = math.cos(r), math.sin(r)
    a = cos_r * scale_x
    b = -sin_r * scale_y
    c = tx
    d = sin_r * scale_x
    e = cos_r * scale_y
    f = ty
    return (a, b, c, d, e, f)


def affine_forward_point(M, x, y):
    a, b, c, d, e, f = M
    return a * x + b * y + c, d * x + e * y + f


def affine_inverse_data(M):
    """PIL Image.transform(AFFINE, data) maps output->input.

    For forward matrix M (input->output) return data for output->input.
    """
    a, b, c, d, e, f = M
    det = a * e - b * d
    ia = e / det
    ib = -b / det
    ic = (b * f - e * c) / det
    id_ = -d / det
    ie = a / det
    if_ = (d * c - a * f) / det
    return (ia, ib, ic, id_, ie, if_)


# ----------------------------------------------------------------------------
# character
# ----------------------------------------------------------------------------
class Character:
    def __init__(self, png_path):
        self.img = Image.open(png_path).convert('RGBA')
        self.cw, self.ch = self.img.size
        # target base scale: fit within MAX_H / MAX_W
        self.s0 = min(MAX_H / float(self.ch), MAX_W / float(self.cw))
        self.anchor = (self.cw / 2.0, self.ch - FEET_PAD)

    @property
    def draw_w(self):
        return self.cw * self.s0

    @property
    def draw_h(self):
        return self.ch * self.s0

    def render(self, pose, ground=GROUND_Y, canvas_w=CANVAS_W, canvas_h=CANVAS_H,
               pivot=None):
        """pose: (scale_x, scale_y, deg, tx, ty). pivot None = feet anchor."""
        sx, sy, deg, tx, ty = pose
        ax, ay = pivot if pivot else self.anchor
        scale_x = sx * self.s0
        scale_y = sy * self.s0
        # forward: p -> scale about anchor_src -> rotate -> place anchor at (cx+tx, ground+ty)
        acx = canvas_w / 2.0 + tx
        acy = ground + ty
        r = math.radians(deg)
        cos_r, sin_r = math.cos(r), math.sin(r)
        # p_dest = R*S*(p - anchor) + anchor_dest
        a = cos_r * scale_x
        b = -sin_r * scale_y
        d = sin_r * scale_x
        e = cos_r * scale_y
        c = acx - (a * ax + b * ay)
        f = acy - (d * ax + e * ay)
        forward = (a, b, c, d, e, f)
        data = affine_inverse_data(forward)
        return self.img.transform((canvas_w, canvas_h), Image.AFFINE, data,
                                  resample=Image.BICUBIC)


# ----------------------------------------------------------------------------
# 2.5D turntable character (front / side / back three-view art)
# ----------------------------------------------------------------------------
class TurnCharacter:
    """Pseudo-3D paper doll built from front / side / back turnaround art.

    Yaw rendering:
      * four view segments: front (0°), left profile (90°), back (180°),
        right profile (270°);
      * horizontal squash near the segment edges = perspective foreshortening;
      * short crossfade at the four view boundaries; when ``blur_deg`` > 0 the
        frame is a temporal average of neighbouring yaw angles, which reads as
        rotation motion blur and hides the crossfade;
      * the ground shadow width follows the visible silhouette (front/back
        dress wide, profile narrow).
    """

    def __init__(self, name):
        # Q版 chibi three-views are the default; fall back to the old set.
        base = CHIBI_DIR if os.path.exists(os.path.join(CHIBI_DIR, '%s-front.png' % name)) else THREEVIEW_DIR
        if not os.path.isdir(base):
            raise RuntimeError('Q版 three-view assets missing: ' + base +
                               '  (run: python tools/sheets.py && python tools/chibi.py)')
        def load(label):
            return Image.open(os.path.join(base, '%s-%s.png' % (name, label))).convert('RGBA')
        self.name = name
        self.views = {
            'front': load('front'),
            'side': load('side'),                       # drawn facing left
            'back': load('back'),
        }
        self.views['side_m'] = self.views['side'].transpose(Image.FLIP_LEFT_RIGHT)
        s = TV_SCALE
        self.sw = int(round(self.views['front'].width * s))
        self.sh = int(round(self.views['front'].height * s))
        for k in list(self.views):
            self.views[k] = self.views[k].resize((self.sw, self.sh), Image.LANCZOS)
        # pivot (feet) position inside the scaled view: x = centre, y = feet line
        self.pivot_x = self.sw / 2.0
        self.pivot_y = TV_FEET_Y * s
        self.top_y = GROUND_Y - self.pivot_y

    # -- view selection -----------------------------------------------------
    @staticmethod
    def _segment(angle):
        """(view_label, scale_x) for an absolute yaw angle in [0, 360)."""
        a = angle % 360.0
        r = math.radians(a)
        if a <= 45.0:
            return 'front', math.cos(r)
        if a <= 135.0:
            return 'side', math.sin(r)
        if a <= 225.0:
            return 'back', -math.cos(r)
        if a <= 315.0:
            return 'side_m', -math.sin(r)
        return 'front', math.cos(r)

    _BOUNDARIES = (45.0, 135.0, 225.0, 315.0)
    _FADE = 6.0

    def _base_frame(self, angle):
        """Character-only RGBA frame (640x360) at one exact yaw angle."""
        a = angle % 360.0
        # near a view boundary? crossfade the two neighbouring segments
        for b in self._BOUNDARIES:
            d = (a - b + 540.0) % 360.0 - 180.0       # signed distance in (-180,180]
            if abs(d) < self._FADE:
                t = (d + self._FADE) / (2.0 * self._FADE)
                t = t * t * (3 - 2 * t)
                v1, sx1 = self._segment(b - 0.01)
                v2, sx2 = self._segment(b + 0.01)
                return Image.blend(self._render_view(v1, sx1), self._render_view(v2, sx2), t)
        v, sx = self._segment(a)
        return self._render_view(v, sx)

    def _render_view(self, label, scale_x):
        canvas = Image.new('RGBA', (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
        img = self.views[label]
        w = max(1, int(round(self.sw * scale_x)))
        if w != self.sw:
            img = img.resize((w, self.sh), Image.LANCZOS)
        x = int(round(CANVAS_W / 2.0 - self.pivot_x * scale_x))
        y = int(round(self.top_y))
        canvas.alpha_composite(img, (x, y))
        return canvas

    def _yaw_frame(self, yaw, blur_deg):
        if blur_deg <= 0.2:
            return self._base_frame(yaw)
        # temporal supersampling: centre weighted more than the two side samples
        centre = self._base_frame(yaw).convert('RGBA')
        prev = self._base_frame(yaw - blur_deg).convert('RGBA')
        nxt = self._base_frame(yaw + blur_deg).convert('RGBA')
        side = Image.blend(prev, nxt, 0.5)
        return Image.blend(side, centre, 0.55)

    # -- compositing --------------------------------------------------------
    def _shadow(self, frame, pose):
        """Ground shadow ellipse; width follows the frame's lower silhouette."""
        sx, sy, deg, tx, ty = pose
        a = np.asarray(frame)[:, :, 3]
        ys, xs = np.nonzero(a > 24)
        if len(ys) == 0:
            return None
        bottom = int(ys.max())
        band = max(2, int(0.18 * MAX_H))
        sel = ys >= bottom - band
        foot_w = float(xs[sel].max() - xs[sel].min()) if sel.any() else 90.0
        shadow = Image.new('RGBA', (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
        draw_shadow(shadow, _ShadowProxy(foot_w), pose, alpha=58)
        return shadow

    def render(self, pose, yaw=0.0, blur_deg=0.0):
        """Render one 640x360 RGBA frame (character + ground shadow)."""
        frame = self._yaw_frame(yaw, blur_deg)
        shadow = self._shadow(frame, pose)
        layer = new_layer()
        if shadow is not None:
            layer.alpha_composite(shadow)
        # pose transform around the feet anchor (same math as Character.render)
        sx, sy, deg, tx, ty = pose
        ax, ay = CANVAS_W / 2.0, float(GROUND_Y)
        acx = CANVAS_W / 2.0 + tx
        acy = GROUND_Y + ty
        r = math.radians(deg)
        cos_r, sin_r = math.cos(r), math.sin(r)
        a = cos_r * sx
        b = -sin_r * sy
        d = sin_r * sx
        e = cos_r * sy
        c = acx - (a * ax + b * ay)
        f = acy - (d * ax + e * ay)
        transformed = frame.transform((CANVAS_W, CANVAS_H), Image.AFFINE,
                                      affine_inverse_data((a, b, c, d, e, f)),
                                      resample=Image.BICUBIC)
        layer.alpha_composite(transformed)
        return layer


class _ShadowProxy:
    """Minimal character stand-in for draw_shadow(): width of the ground footprint."""
    def __init__(self, footprint_w):
        self.draw_w = max(60.0, footprint_w * 2.0)


# ----------------------------------------------------------------------------
# drawing helpers (particles / props)
# ----------------------------------------------------------------------------
def new_layer():
    return Image.new('RGBA', (CANVAS_W, CANVAS_H), (0, 0, 0, 0))


def draw_shadow(layer, char, pose, alpha=42):
    sx, sy, deg, tx, ty = pose
    # shadow stays on the ground plane; shrinks/fades while jumping
    jump = max(0.0, -ty)
    w = max(30, min(240, char.draw_w * 0.5))
    w *= max(0.45, 1.0 - jump / 400.0)
    alpha = int(alpha * max(0.3, 1.0 - jump / 300.0))
    hh = max(4.0, w * 0.08)
    cx = CANVAS_W / 2.0 + tx * 0.5
    # keep the whole ellipse inside the canvas (no flat cut at y=360)
    cy = min(GROUND_Y + 1.5, CANVAS_H - 2.0 - hh / 2.0)
    ellipse = Image.new('RGBA', (int(w) + 4, int(hh * 2) + 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(ellipse)
    d.ellipse((2, 2, int(w) + 2, int(hh * 2) + 2), fill=(20, 20, 35, alpha))
    layer.alpha_composite(ellipse, (int(cx - w / 2 - 2), int(cy - hh - 2)))


def draw_heart(d, x, y, size, color, outline=(255, 255, 255, 235), width=2):
    """Draw a heart centred at (x,y)."""
    s = size
    d.ellipse((x - s, y - s * 0.9, x, y + s * 0.1), fill=color, outline=outline, width=width)
    d.ellipse((x, y - s * 0.9, x + s, y + s * 0.1), fill=color, outline=outline, width=width)
    d.polygon([(x - s * 0.95, y - s * 0.12), (x + s * 0.95, y - s * 0.12),
               (x, y + s * 1.05)], fill=color, outline=outline)


def draw_star(d, x, y, size, color=(255, 202, 60, 245), width=3):
    for ang in (0, 45, 90, 135):
        a = math.radians(ang)
        d.line([(x - math.cos(a) * size, y - math.sin(a) * size),
                (x + math.cos(a) * size, y + math.sin(a) * size)],
               fill=color, width=width)


def draw_sweat(d, x, y, size, color=(120, 195, 245, 245)):
    outline = (55, 100, 150, min(255, int(color[3])) if len(color) > 3 else 245)
    d.ellipse((x - size * 0.55 - 1, y - size * 0.55 - 1,
               x + size * 0.55 + 1, y + size * 0.55 + 1), fill=outline)
    d.polygon([(x - size * 0.5 - 1, y - size * 0.35), (x + size * 0.5 + 1, y - size * 0.35),
               (x, y - size * 1.35 - 1)], fill=outline)
    d.ellipse((x - size * 0.55, y - size * 0.55, x + size * 0.55, y + size * 0.55), fill=color)
    d.polygon([(x - size * 0.5, y - size * 0.35), (x + size * 0.5, y - size * 0.35),
               (x, y - size * 1.35)], fill=color)


def draw_check(d, x, y, size, color=(70, 190, 130, 235), width=4):
    """A little tick mark used by the 'tidy / counting' animation."""
    d.line([(x - size, y), (x - size * 0.25, y + size * 0.7)],
           fill=color, width=width, joint='curve')
    d.line([(x - size * 0.25, y + size * 0.7), (x + size, y - size * 0.8)],
           fill=color, width=width, joint='curve')


def draw_zzz(d, x, y, size, color=(225, 230, 255, 235)):
    """Stylised 'Z' made of thick polylines, with a dark rim so it reads on
    both light and dark wallpapers."""
    w = max(2, int(size * 0.22))
    segs = []
    for i in range(3):
        ox = x + i * size * 0.75
        oy = y - i * size * 0.8
        s = size * (0.55 + 0.12 * i)
        segs.append([(ox, oy), (ox + s, oy)])
        segs.append([(ox + s, oy), (ox, oy + s)])
        segs.append([(ox, oy + s), (ox + s, oy + s)])
    if len(color) == 4 and color[3] > 8:
        rim = (70, 82, 115, min(255, int(color[3] * 0.85)))
        for seg in segs:
            d.line(seg, fill=rim, width=w + 2, joint='curve')
    for seg in segs:
        d.line(seg, fill=color, width=w, joint='curve')


def draw_sparkle_burst(layer, cx, cy, t, n=5, spread=70, color=(255, 235, 140, 240)):
    if t <= 0:
        return
    d = ImageDraw.Draw(layer)
    for i in range(n):
        ang = -math.pi / 2 + (i - (n - 1) / 2.0) * 0.55
        dist = spread * (1 - math.exp(-t * 3.0))
        x = cx + math.cos(ang) * dist * 1.6
        y = cy + math.sin(ang) * dist
        alpha = int(255 * max(0.0, 1 - t * 1.4))
        draw_star(d, x, y, 7 + 3 * math.sin(i + t * 6), (color[0], color[1], color[2], alpha), width=3)


# ----------------------------------------------------------------------------
# keyframe helpers
# ----------------------------------------------------------------------------
def smooth(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def ease_out(t):
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    t = min(max(t, 0.0), 1.0)
    return 0.5 - 0.5 * math.cos(math.pi * t)


def key_interp(keys, u):
    """Piecewise smooth interpolation of [(u0, v0), (u1, v1), ...]."""
    if u <= keys[0][0]:
        return keys[0][1]
    for i in range(len(keys) - 1):
        a, va = keys[i]
        b, vb = keys[i + 1]
        if a <= u <= b:
            if b - a <= 1e-9:
                return vb
            return va + (vb - va) * ease_in_out((u - a) / (b - a))
    return keys[-1][1]


# ----------------------------------------------------------------------------
# animation specs
# ----------------------------------------------------------------------------
class Anim:
    def __init__(self, name, duration, loop=True, once_fade_out=0.0):
        self.name = name
        self.duration = duration
        self.loop = loop
        self.once_fade_out = once_fade_out
        self.frames = int(round(duration * FPS))

    def pose(self, u, t):
        """u = normalized time 0..1, t = seconds. Return pose + particle callback."""
        raise NotImplementedError

    def yaw_frame(self, u, t):
        """2.5D animations override: return (yaw_degrees, blur_degrees) or None."""
        return None


class RestIdle(Anim):
    """待机呼吸: subtle breathing + bob + tiny sway, seamless loop."""

    def __init__(self, duration=4.0, amp_breath=0.012, amp_bob=2.2, amp_sway=0.55, phase=0.0):
        super().__init__('待机呼吸', duration, loop=True)
        self.ab, self.abob, self.asw, self.phase = amp_breath, amp_bob, amp_sway, phase

    def pose(self, u, t):
        w = 2 * math.pi * u
        breathe = math.sin(w * 2 + self.phase)
        sway = math.sin(w + self.phase)
        sx = 1.0 - self.ab * breathe * 0.55
        sy = 1.0 + self.ab * breathe
        bob = -abs(self.abob * math.sin(w)) if self.abob else 0
        deg = self.asw * sway
        return (sx, sy, deg, 0.0, bob), None


class FloatIdle(Anim):
    """原地漂浮: gentle float + sway."""

    def __init__(self, duration=4.6, height=9.0, sway=10.0, amp_rot=1.1):
        super().__init__('原地漂浮', duration, loop=True)
        self.height, self.sway, self.amp_rot = height, sway, amp_rot

    def pose(self, u, t):
        w = 2 * math.pi * u
        bob = -self.height * (0.5 - 0.5 * math.cos(w))
        tx = self.sway * math.sin(w * 2 + 0.4)
        deg = self.amp_rot * math.sin(w + 0.8)
        return (1.0, 1.0, deg, tx, bob), None


class NapIdle(Anim):
    """原地小憩: slow breathing + sleepy tilt + Zzz."""

    def __init__(self, duration=6.0):
        super().__init__('原地小憩', duration, loop=True)

    def pose(self, u, t):
        w = 2 * math.pi * u
        sy = 1.0 + 0.014 * math.sin(w * 2)
        deg = 2.2 + 0.7 * math.sin(w)
        tx = -7.0
        bob = -4.0 + 1.5 * math.sin(w * 2 + 1.0)

        def fx(layer):
            d = ImageDraw.Draw(layer)
            phase = (t / self.duration) % 1.0
            # three drifting Z's floating up-right of the head (stay in canvas)
            hx = CANVAS_W / 2 + 50
            hy = GROUND_Y - 240
            for i in range(3):
                p = (phase + i / 3.0) % 1.0
                x = hx + 16 * math.sin(p * math.pi * 1.1) + p * 12
                y = hy - p * 55
                a = int(235 * math.sin(p * math.pi))
                if a > 8:
                    draw_zzz(d, x, y, 12 + 6 * p, (228, 233, 255, a))
        return (1.0, sy, deg, tx, bob), fx


class LookAround(Anim):
    """东张西望: 2.5D look-around — turn to both profiles, then back to front.

    Uses the front / right-profile / left-profile three-view art so the pet
    visibly turns around in 3D instead of sliding its flat image.
    """

    def __init__(self, duration=3.2):
        super().__init__('东张西望', duration, loop=False)
        self.keys = [(0.00, 0.0), (0.08, 0.0), (0.22, -74.0), (0.40, -74.0),
                     (0.52, 0.0), (0.60, 0.0), (0.74, 74.0), (0.92, 74.0),
                     (1.00, 0.0)]

    def pose(self, u, t):
        # gentle bob; end at neutral so the engine can crossfade back to idle
        bob = -2.5 * math.sin(min(1.0, u / 0.22) * math.pi) if u < 0.22 else 0.0
        bob += -2.0 * math.sin(min(1.0, (u - 0.52) / 0.14) * math.pi) if 0.52 <= u < 0.66 else 0.0
        deg = 1.2 * math.sin(2 * math.pi * u) * (1.0 - smooth(u))
        tx = 3.0 * math.sin(2 * math.pi * u)
        return (1.0, 1.0, deg, tx, bob), None

    def yaw_frame(self, u, t):
        yaw = key_interp(self.keys, u)
        # tiny idle sway while holding a profile (makes it feel alive)
        hold = 4.0 if 0.22 <= u <= 0.40 or 0.74 <= u <= 0.92 else 0.0
        if hold:
            yaw += hold * math.sin((u % 0.18) / 0.18 * 2 * math.pi) * 0.5
        d = abs(key_interp(self.keys, min(1.0, u + 0.015)) -
                key_interp(self.keys, max(0.0, u - 0.015)))
        return (yaw, min(13.0, d * 0.9 + 1.0))


class DragFlail(Anim):
    """被鼠标拖拽悬空反馈: dangling sway loop (feet lifted off the ground).

    Adds a ±40° yaw sway through the front/side views so the dangling pet
    shows its profile while being carried.
    """

    def __init__(self, duration=1.6):
        super().__init__('被鼠标拖拽悬空反馈', duration, loop=True)

    def pose(self, u, t):
        w = 2 * math.pi * u
        return (1.0, 1.012, 6.0 * math.sin(w), 6.5 * math.sin(w + 0.9),
                -19 + 3.0 * math.sin(w * 2)), None

    def yaw_frame(self, u, t):
        w = 2 * math.pi * u
        # hangs sideways and slowly swings through the profile views
        return (15.0 + 60.0 * math.sin(w + 0.35), 4.0)


class ClickJoy(Anim):
    """点击回应-开心跃动: quick squash -> small hop -> land -> settle.

    The hop amplitude is capped so the head never leaves the 640x360 canvas
    (the base character is 322px tall standing on GROUND_Y=356).
    """

    def __init__(self, duration=1.35):
        super().__init__('点击回应-开心跃动', duration, loop=False)

    def pose(self, u, t):
        if u < 0.14:  # anticipation squash
            k = ease_out(u / 0.14)
            sx, sy, ty, deg = 1.0 + 0.055 * k, 1.0 - 0.055 * k, 0.0, 0.0
        elif u < 0.44:  # hop
            k = ease_in_out((u - 0.14) / 0.30)
            jump = math.sin(k * math.pi)
            sx = 1.0 - 0.015 * jump
            sy = 1.0 - 0.01 * jump
            ty = -30.0 * jump
            deg = 1.6 * math.sin(k * math.pi)
        elif u < 0.60:  # landing squash (starts and ends neutral)
            k = math.sin(math.pi * (u - 0.44) / 0.16)
            sx, sy, ty, deg = 1.0 + 0.07 * k, 1.0 - 0.07 * k, 0.0, 0.0
        else:  # settle back to the neutral idle pose (clean hand-off)
            k = ease_in_out((u - 0.60) / 0.40)
            sx = 1.0 + 0.012 * math.sin(k * math.pi * 2) * (1 - k)
            sy = 1.0 - 0.012 * math.sin(k * math.pi * 2) * (1 - k)
            ty = 0.0
            deg = 0.9 * math.sin(k * math.pi * 3) * (1 - k) ** 2

        def fx(layer):
            d = ImageDraw.Draw(layer)
            # heart burst from the chest during the hop
            if 0.16 <= u <= 0.92:
                k = (u - 0.16) / 0.76
                for i, ang in enumerate([-2.6, -2.1, -1.55, -1.0, -0.45]):
                    dist = 16 + 92 * ease_out(k) * (0.7 + 0.3 * math.sin(i * 2.3))
                    x = CANVAS_W / 2 + math.cos(ang) * dist * 1.45 + 34
                    y = GROUND_Y - 195 + math.sin(ang) * dist * 0.75 - 30 * ease_out(k)
                    a = int(245 * max(0.0, 1 - k * 1.15))
                    size = 7 + 4 * math.sin(i * 1.7 + k * 5)
                    if a > 10:
                        draw_heart(d, x, y, size, (255, 120, 160, a))
        return (sx, sy, deg, 0.0, ty), fx

    def yaw_frame(self, u, t):
        # happy jump + 360° spin, ends facing front
        keys = [(0.00, 0.0), (0.18, 0.0), (0.52, 220.0), (0.72, 360.0),
                (1.00, 360.0)]
        yaw = key_interp(keys, u)
        d = abs(key_interp(keys, min(1.0, u + 0.012)) -
                key_interp(keys, max(0.0, u - 0.012)))
        return (yaw % 360.0, min(14.0, d * 0.9 + (2.0 if d > 1.0 else 0.0)))


class ClickShy(Anim):
    """点击回应-害羞惊讶."""

    def __init__(self, duration=1.4):
        super().__init__('点击回应-害羞惊讶', duration, loop=False)

    def pose(self, u, t):
        if u < 0.15:
            k = ease_out(u / 0.15)
            tx, ty, deg, sx = -20 * k, -6 * k, -3.5 * k, 1.0
        elif u < 0.42:
            k = ease_in_out((u - 0.15) / 0.27)
            tx = -20 + 38 * k
            ty = -6 + 6 * k
            deg = -3.5 + 7.0 * k
            sx = 1.0
        elif u < 0.7:
            k = ease_in_out((u - 0.42) / 0.28)
            tx = 18 - 12 * k
            deg = 3.5 - 2.0 * k
            ty = 0.0
            sx = 1.0
        else:
            k = ease_in_out((u - 0.7) / 0.3)
            tx = 6 * (1 - k)
            deg = 1.5 * (1 - k)
            ty = 0.0
            sx = 1.0
        sy = 1.0 - 0.02 * math.sin(min(u / 0.15, 1.0) * math.pi)

        def fx(layer):
            d = ImageDraw.Draw(layer)
            if u > 0.1:
                k = min(1.0, (u - 0.1) / 0.45)
                a = int(235 * max(0.0, 1 - max(0.0, u - 0.55) / 0.45))
                # sparkles beside the head (face stays clear)
                for i, (dx, dy) in enumerate([(-98, -270), (82, -276), (-118, -226), (104, -232)]):
                    if a > 8:
                        draw_star(d, CANVAS_W / 2 + dx, GROUND_Y + dy, 7 + 4 * math.sin(k * 6 + i),
                                  (255, 202, 60, a), width=3)
                # sweat drop
                if 0.15 < u < 0.75:
                    drop_k = min(1.0, (u - 0.15) / 0.6)
                    draw_sweat(d, CANVAS_W / 2 + 56, GROUND_Y - 262 + drop_k * 18, 7,
                               (140, 205, 250, int(240 * (1 - drop_k * 0.7))))
        return (sx, 1.0, deg, tx, ty), fx

    def yaw_frame(self, u, t):
        keys = [(0.00, 0.0), (0.10, 0.0), (0.28, -98.0), (0.50, -98.0),
                (0.74, 0.0), (1.00, 0.0)]
        yaw = key_interp(keys, u)
        d = abs(key_interp(keys, min(1.0, u + 0.015)) -
                key_interp(keys, max(0.0, u - 0.015)))
        return (yaw, min(12.0, d * 0.85 + 2.0))


class ClickWave(Anim):
    """点击回应-元气挥手: bouncy rocking + hand-wave motion arcs, ends neutral."""

    def __init__(self, duration=1.3):
        super().__init__('点击回应-元气挥手', duration, loop=False)

    def pose(self, u, t):
        w = 2 * math.pi * u * 2.4
        env = 1.0 if u < 0.68 else max(0.0, 1.0 - ease_in_out((u - 0.68) / 0.32))
        bounce = abs(math.sin(w)) * env
        ty = -10 * bounce
        deg = 4.5 * math.sin(w) * env
        tx = 5.5 * math.sin(w * 0.5) * env
        sy = 1.0 + 0.02 * math.sin(w * 2) * env

        def fx(layer):
            d = ImageDraw.Draw(layer)
            # cheerful stars drifting up beside the character
            for i in range(4):
                p = (u * 1.3 + i * 0.27) % 1.0
                x = CANVAS_W / 2 + math.sin((i * 2.1 + p * 4)) * 72
                y = GROUND_Y - 120 - p * 160
                a = int(230 * math.sin(p * math.pi) * env)
                if a > 8:
                    draw_star(d, x, y, 5 + 3 * math.sin(p * 9 + i), (255, 202, 60, a), width=2)
            # hand-wave motion arcs on the character's right side
            if env > 0.05:
                k = 0.5 + 0.5 * math.sin(w)
                for j in range(2):
                    r = 24 + j * 14
                    cx_ = CANVAS_W / 2 + 92 + 8 * k
                    cy_ = GROUND_Y - 180
                    a = int(150 * env * (1.0 - 0.25 * j))
                    d.arc((cx_ - r, cy_ - r, cx_ + r, cy_ + r),
                          start=-58 + 12 * k, end=34 + 12 * k,
                          fill=(255, 176, 80, a), width=4)
        return (1.0, sy, deg, tx, ty), fx


class ThinkBubble(Anim):
    """工作状态-思考冒泡."""

    def __init__(self, duration=3.2):
        super().__init__('工作状态-思考冒泡', duration, loop=True)

    def pose(self, u, t):
        w = 2 * math.pi * u
        deg = -2.0 + 1.0 * math.sin(w)
        tx = -6.0
        bob = -2.0 + 1.0 * math.sin(w * 2)

        def fx(layer):
            d = ImageDraw.Draw(layer)
            # three thought-bubble dots rising beside the head (dark rim for contrast)
            for i in range(3):
                p = (u + i / 3.0) % 1.0
                x = CANVAS_W / 2 + 68 + 8 * math.sin(p * math.pi * 2 + i)
                y = GROUND_Y - 256 - p * 44
                a = int(230 * math.sin(p * math.pi))
                r = 4.5 + 2 * i
                if a > 8:
                    d.ellipse((x - r - 2, y - r - 2, x + r + 2, y + r + 2),
                              fill=(88, 102, 142, int(a * 0.85)))
                    d.ellipse((x - r, y - r, x + r, y + r), fill=(245, 248, 255, a))
        return (1.0, 1.0, deg, tx, bob), fx


class BusyBounce(Anim):
    """工作状态-忙碌点按."""

    def __init__(self, duration=1.6):
        super().__init__('工作状态-忙碌点按', duration, loop=True)

    def pose(self, u, t):
        w = 2 * math.pi * u * 3
        bounce = abs(math.sin(w))
        sy = 1.0 - 0.02 + 0.035 * bounce
        sx = 1.0 + 0.02 - 0.03 * bounce
        ty = -5 * bounce
        deg = 0.8 * math.sin(w * 0.5)
        return (sx, sy, deg, 0.0, ty), None


class TidyNod(Anim):
    """工作状态-清点归档: gentle nod + floating tick marks beside the body."""

    def __init__(self, duration=2.6):
        super().__init__('工作状态-清点归档', duration, loop=True)

    def pose(self, u, t):
        w = 2 * math.pi * u * 2
        nod = 0.5 - 0.5 * math.cos(w)
        sy = 1.0 - 0.018 * nod
        ty = 1.5 * nod
        deg = 1.0 * math.sin(w * 0.5)

        def fx(layer):
            d = ImageDraw.Draw(layer)
            p = u % 1.0
            spots = ((-64, 0.0), (68, 0.34), (-36, 0.67))
            for dx, ph in spots:
                pp = (p + ph) % 1.0
                a = int(225 * math.sin(pp * math.pi))
                x = CANVAS_W / 2 + dx + 9 * math.sin(pp * 2 * math.pi)
                y = GROUND_Y - 176 - pp * 30
                if a > 8:
                    draw_check(d, x, y, 7.5, (60, 185, 125, a), width=4)
        return (1.0, sy, deg, 0.0, ty), fx


class StepPace(Anim):
    """工作状态-原地踱步张望."""

    def __init__(self, duration=2.8):
        super().__init__('工作状态-原地踱步张望', duration, loop=True)

    def pose(self, u, t):
        w = 2 * math.pi * u
        tx = 18 * math.sin(w)
        deg = 2.5 * math.sin(w + 0.4)
        bob = -2.0 * abs(math.sin(w * 2))
        sy = 1.0 + 0.006 * math.sin(w * 4)
        return (1.0, sy, deg, tx, bob), None


class Celebrate(Anim):
    """工作状态-雀跃庆祝: two capped hops + confetti, ends in the neutral pose."""

    def __init__(self, duration=2.2):
        super().__init__('工作状态-雀跃庆祝', duration, loop=False)

    def pose(self, u, t):
        if u < 0.12:  # anticipation squash
            k = ease_out(u / 0.12)
            sx, sy, ty, deg = 1.0 + 0.05 * k, 1.0 - 0.05 * k, 0.0, 0.0
        elif u < 0.46:  # hop 1 (big)
            k = ease_in_out((u - 0.12) / 0.34)
            jump = math.sin(k * math.pi)
            sx = 1.0 - 0.02 * jump
            sy = 1.0 - 0.012 * jump
            ty = -34 * jump
            deg = 2.2 * math.sin(k * math.pi * 2)
        elif u < 0.58:  # landing squash
            k = math.sin(math.pi * (u - 0.46) / 0.12)
            sx, sy, ty, deg = 1.0 + 0.06 * k, 1.0 - 0.06 * k, 0.0, 0.0
        elif u < 0.82:  # hop 2 (smaller)
            k = ease_in_out((u - 0.58) / 0.24)
            jump = math.sin(k * math.pi)
            sx = 1.0 - 0.012 * jump
            sy = 1.0
            ty = -20 * jump
            deg = 1.6 * math.sin(k * math.pi * 2)
        else:  # settle back to neutral idle
            k = ease_in_out((u - 0.82) / 0.18)
            sx = 1.0 + 0.01 * math.sin(k * math.pi * 2) * (1 - k)
            sy = 1.0 - 0.01 * math.sin(k * math.pi * 2) * (1 - k)
            ty = 0.0
            deg = 0.8 * math.sin(k * math.pi * 2) * (1 - k)

        def fx(layer):
            d = ImageDraw.Draw(layer)
            env = 1.0 if u < 0.80 else max(0.0, 1.0 - (u - 0.80) / 0.20)
            cols = [(255, 110, 130, 235), (255, 210, 70, 235), (110, 195, 255, 235),
                    (150, 240, 140, 235), (225, 145, 255, 235)]
            for i in range(16):
                p = (u * 1.35 + i * 0.139) % 1.0
                ang = i * 2.399
                x = CANVAS_W / 2 + math.cos(ang) * 34 + math.sin(p * 5 + i) * 74 * p
                y = GROUND_Y - 150 - 705 * p + 799 * p * p
                a = int(235 * max(0.0, 1.0 - p * 0.9) * env)
                if a > 8:
                    c = cols[i % len(cols)]
                    s = 3 + 2 * math.sin(i + p * 7)
                    d.rectangle((x - s, y - s * 0.6, x + s, y + s * 0.6),
                                fill=(c[0], c[1], c[2], a))
        return (sx, sy, deg, 0.0, ty), fx

    def yaw_frame(self, u, t):
        # celebratory 360° hop-spin, ends facing front again
        keys = [(0.00, 0.0), (0.12, 0.0), (0.46, 200.0), (0.58, 245.0),
                (0.82, 360.0), (1.00, 360.0)]
        yaw = key_interp(keys, u)
        d = abs(key_interp(keys, min(1.0, u + 0.012)) -
                key_interp(keys, max(0.0, u - 0.012)))
        return (yaw % 360.0, min(14.0, d * 0.9 + (2.0 if d > 1.0 else 0.0)))


class DroopSweat(Anim):
    """工作状态-垂头叹气冒汗."""

    def __init__(self, duration=2.8):
        super().__init__('工作状态-垂头叹气冒汗', duration, loop=True)

    def pose(self, u, t):
        w = 2 * math.pi * u
        # droop = lean + vertical squash; feet stay on the ground line
        # (a positive ty would push the skirt below the 360px canvas)
        deg = 2.2 + 0.4 * math.sin(w)
        ty = -0.6 + 0.3 * math.sin(w)
        sy = 1.0 - 0.022 * (0.5 + 0.5 * math.sin(w))
        sx = 1.0 + 0.006 * math.sin(w + 1.2)

        def fx(layer):
            d = ImageDraw.Draw(layer)
            p = u % 1.0
            # a sweat drop sliding down beside the head
            drop_y = GROUND_Y - 258 + 50 * p
            a = int(235 * math.sin(p * math.pi))
            if a > 8:
                draw_sweat(d, CANVAS_W / 2 + 58, drop_y, 7, (140, 205, 250, a))
            # sigh puff drifting down from the mouth area
            ca = int(120 * math.sin(p * math.pi))
            if ca > 8:
                cx = CANVAS_W / 2 - 46
                cy = GROUND_Y - 238 + p * 36
                d.ellipse((cx - 16, cy - 6, cx + 16, cy + 6),
                          fill=(225, 230, 242, ca))
                d.ellipse((cx - 10, cy - 10, cx + 22, cy + 10),
                          fill=(210, 218, 235, int(ca * 0.55)))
        return (sx, sy, deg, 0.0, ty), fx


class WhisperDaze(Anim):
    """碎碎念-发呆碎碎念."""

    def __init__(self, duration=3.6):
        super().__init__('碎碎念-发呆碎碎念', duration, loop=True)

    def pose(self, u, t):
        w = 2 * math.pi * u
        deg = 1.6 * math.sin(w)
        tx = 4.0 * math.sin(w + 1.0)
        bob = -1.5 + 1.5 * math.sin(w * 2)

        def fx(layer):
            d = ImageDraw.Draw(layer)
            # a small speech bubble with ellipsis, beside the head
            p = u
            bx = CANVAS_W / 2 + 88
            by = GROUND_Y - 262 + 3 * math.sin(p * 2 * math.pi)
            a = int(235 * min(1.0, math.sin(p * math.pi) * 1.6))
            if a > 8:
                box = (bx - 26, by - 16, bx + 26, by + 12)
                # Pillow 7.2 has no rounded_rectangle: draw rect + corner dots
                d.rectangle(box, fill=(255, 255, 255, a),
                            outline=(120, 130, 160, min(255, a)), width=2)
                for cx_, cy_ in ((box[0] + 2, box[1] + 2), (box[2] - 2, box[1] + 2),
                                 (box[0] + 2, box[3] - 2), (box[2] - 2, box[3] - 2)):
                    d.ellipse((cx_ - 2, cy_ - 2, cx_ + 2, cy_ + 2), fill=(255, 255, 255, a))
                d.polygon([(bx - 10, by + 10), (bx - 20, by + 24), (bx + 2, by + 10)],
                          fill=(255, 255, 255, a), outline=(120, 130, 160, min(255, a)))
                for i in range(3):
                    d.ellipse((bx - 15 + i * 11, by - 4, bx - 9 + i * 11, by + 2),
                              fill=(110, 120, 150, min(255, a)))
        return (1.0, 1.0, deg, tx, bob), fx


class SpinShow(Anim):
    """转圈展示: real 2.5D 360° turntable built from the three-view art."""

    def __init__(self, duration=2.8):
        super().__init__('转圈展示', duration, loop=False)

    def pose(self, u, t):
        if u < 0.08:
            k = ease_out(u / 0.08)
            sy = 1.0 - 0.03 * k
            sx = 1.0 + 0.02 * k
            bob = -2.0 * k
        elif u > 0.92:
            k = ease_out((u - 0.92) / 0.08)
            sy = 1.0 - 0.02 * (1 - k)
            sx = 1.0
            bob = 1.0 * (1 - k)
        else:
            sy = 1.0
            sx = 1.0
            bob = -3.0 * math.sin((u - 0.08) / 0.84 * math.pi)
        return (sx, sy, 0.0, 0.0, bob), None

    def yaw_frame(self, u, t):
        if u <= 0.08 or u >= 0.92:
            return (0.0, 0.0)          # holds the front view before/after
        k = (u - 0.08) / 0.84
        yaw = 360.0 * ease_in_out(k)
        d = abs(ease_in_out(min(1.0, k + 0.012)) - ease_in_out(max(0.0, k - 0.012)))
        blur = min(18.0, 360.0 * d * 0.9)
        return (yaw % 360.0, blur)


class Stretch(Anim):
    """伸懒腰（随机小动作）."""

    def __init__(self, duration=2.6):
        super().__init__('伸懒腰', duration, loop=False)

    def pose(self, u, t):
        if u < 0.3:
            k = ease_in_out(u / 0.3)
            sy = 1.0 + 0.055 * k
            sx = 1.0 - 0.045 * k
            deg = -1.5 * k
            ty = -4 * k
        elif u < 0.6:
            k = ease_in_out((u - 0.3) / 0.3)
            sy = 1.055 - 0.055 * k
            sx = 0.955 + 0.045 * k
            deg = -1.5 + 3.0 * k
            ty = -4 + 4 * k
        else:
            k = ease_in_out((u - 0.6) / 0.4)
            sy = 1.0 + 0.012 * math.sin(k * math.pi * 2)
            sx = 1.0
            deg = 1.5 * (1 - k)
            ty = 0.0
        return (sx, sy, deg, 0.0, ty), None


# ----------------------------------------------------------------------------
# encoder
# ----------------------------------------------------------------------------
def encode_frames(frames_dir, out_path, crf=30):
    cmd = [
        FFMPEG, '-y', '-hide_banner', '-loglevel', 'error',
        '-framerate', str(FPS),
        '-i', os.path.join(frames_dir, 'f%04d.png'),
        '-c:v', 'libvpx-vp9',
        '-pix_fmt', 'yuva420p',
        '-b:v', '0', '-crf', str(crf),
        '-auto-alt-ref', '0',
        '-row-mt', '1',
        '-metadata:s:v:0', 'alpha_mode=1',
        out_path,
    ]
    subprocess.run(cmd, check=True)


def render_anim(char, anim, out_path, keep_frames=False, crf=30, turn=None):
    """Render one animation to webm.

    ``turn`` is an optional TurnCharacter: animations that return a yaw via
    ``Anim.yaw_frame`` are rendered with the 2.5D three-view turntable.
    """
    tmp = tempfile.mkdtemp(prefix='petanim_')
    try:
        for i in range(anim.frames):
            u = i / float(anim.frames)
            t = i / float(FPS)
            pose, fx = anim.pose(u, t)
            yaw_spec = anim.yaw_frame(u, t)
            if yaw_spec is not None and turn is not None:
                yaw, blur = yaw_spec
                layer = turn.render(pose, yaw, blur)
            else:
                layer = new_layer()
                draw_shadow(layer, char, pose)
                layer.alpha_composite(char.render(pose))
            if fx:
                fx(layer)
            layer.save(os.path.join(tmp, 'f%04d.png' % i), optimize=False)
        encode_frames(tmp, out_path, crf=crf)
    finally:
        if not keep_frames:
            shutil.rmtree(tmp, ignore_errors=True)


def verify_alpha(webm_path):
    """Decode first frame back and report alpha stats.

    The default ffmpeg vp9 decoder drops the alpha plane; force the
    libvpx-vp9 decoder (before -i) so the alpha channel is decoded.
    """
    tmp = tempfile.mkdtemp(prefix='petcheck_')
    try:
        subprocess.run([FFMPEG, '-y', '-hide_banner', '-loglevel', 'error',
                        '-c:v', 'libvpx-vp9', '-i', webm_path,
                        '-frames:v', '1', '-pix_fmt', 'rgba',
                        os.path.join(tmp, 'f.png')], check=True)
        im = Image.open(os.path.join(tmp, 'f.png')).convert('RGBA')
        a = np.asarray(im)[:, :, 3]
        return {'size': im.size, 'alpha_min': int(a.min()), 'alpha_max': int(a.max()),
                'transparent_ratio': float((a < 16).mean())}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    import sys
    char_name = sys.argv[1] if len(sys.argv) > 1 else 'gpt'
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           'build', 'anim_test')
    os.makedirs(out_dir, exist_ok=True)
    portrait = os.path.join(CHIBI_DIR, '%s-portrait.png' % char_name)
    if not os.path.exists(portrait):
        portrait = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                'build', 'cutouts', 'portrait-%s.png' % char_name)
    char = Character(portrait)
    turn = None
    try:
        turn = TurnCharacter(char_name)
    except Exception as e:  # noqa: BLE001 - three-view assets are optional for 2D clips
        print('WARN 2.5D turntable disabled (%s); run tools/threeview.py first' % e)
    print('character base:', char.img.size, 'scale', round(char.s0, 3),
          'draw', round(char.draw_w), 'x', round(char.draw_h))
    anims = [RestIdle(), FloatIdle(), NapIdle(), LookAround(), DragFlail(),
             ClickJoy(), ClickShy(), ClickWave(), ThinkBubble(), BusyBounce(),
             TidyNod(), StepPace(), Celebrate(), DroopSweat(), WhisperDaze(),
             SpinShow(), Stretch()]
    selected = sys.argv[2:] or ['RestIdle']
    mapping = {a.__class__.__name__: a for a in anims}
    for key in selected:
        anim = mapping[key]
        out = os.path.join(out_dir, char_name + '-' + anim.name + '.webm')
        render_anim(char, anim, out, turn=turn)
        print('OK', anim.name, '->', os.path.basename(out),
              os.path.getsize(out), 'bytes', verify_alpha(out))
