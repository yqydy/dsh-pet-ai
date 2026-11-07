# -*- coding: utf-8 -*-
"""Review montages for 2.5D (yaw) animations: decode webm frames -> grid contact sheet."""
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FFMPEG = r'C:\Users\20862\AppData\Roaming\Python\Python38\site-packages\imageio_ffmpeg\binaries\ffmpeg-win64-v4.2.2.exe'
TEST_DIR = os.path.join(ROOT, 'build', 'webm')
OUT_DIR = os.path.join(ROOT, 'build', 'spin-review')


def font(size):
    for p in [r'C:\Windows\Fonts\msyh.ttc', r'C:\Windows\Fonts\simhei.ttf']:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def decode_frames(path, count=10):
    tmp = tempfile.mkdtemp(prefix='rev_')
    # probe duration
    probe = subprocess.run([FFMPEG, '-hide_banner', '-i', path], capture_output=True)
    text = (probe.stderr or b'').decode('utf-8', errors='replace')
    dur = 2.0
    for line in text.splitlines():
        if 'Duration:' in line:
            try:
                h, m, s = line.split('Duration:')[1].split(',')[0].strip().split(':')
                dur = int(h) * 3600 + int(m) * 60 + float(s)
            except Exception:
                pass
    frames = []
    for i in range(count):
        t = dur * i / max(1, count - 1)
        t = min(t, max(0.0, dur - 0.05))
        out = os.path.join(tmp, 'f%02d.png' % i)
        subprocess.run([FFMPEG, '-y', '-hide_banner', '-loglevel', 'error',
                        '-c:v', 'libvpx-vp9', '-i', path,
                        '-ss', '%.3f' % t, '-frames:v', '1', '-pix_fmt', 'rgba', out], check=True)
        frames.append((t, Image.open(out).convert('RGBA')))
    return frames


def sheet(path, label, count=10):
    frames = decode_frames(path, count)
    cw, ch = 320, 210
    cols = 5
    rows = (count + cols - 1) // cols
    img = Image.new('RGB', (cols * cw, rows * ch + 40), (22, 22, 32))
    d = ImageDraw.Draw(img)
    d.text((8, 8), label, fill=(240, 240, 255), font=font(18))
    for i, (t, fr) in enumerate(frames):
        bg = Image.new('RGB', (640, 360), (44, 47, 62))
        bg.paste(fr, (0, 0), fr)
        bg.thumbnail((cw - 8, ch - 30))
        x = (i % cols) * cw + (cw - bg.width) // 2
        y = 36 + (i // cols) * ch + (ch - 30 - bg.height) // 2
        img.paste(bg, (x, y))
        d.text((i % cols * cw + 6, 36 + (i // cols) * ch + 2),
               't=%.2fs' % t, fill=(220, 220, 235), font=font(13))
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, label + '.png')
    img.save(out)
    print('saved', out)


if __name__ == '__main__':
    char = sys.argv[1] if len(sys.argv) > 1 else 'gpt'
    names = ['东张西望', '转圈展示', '点击回应-开心跃动', '点击回应-害羞惊讶',
             '被鼠标拖拽悬空反馈', '工作状态-雀跃庆祝']
    for n in names:
        p = os.path.join(TEST_DIR, char, '%s.webm' % n)
        if not os.path.exists(p):
            p = os.path.join(ROOT, 'build', 'anim_test', '%s-%s.webm' % (char, n))
        if os.path.exists(p):
            sheet(p, '%s-%s' % (char, n), 10)
