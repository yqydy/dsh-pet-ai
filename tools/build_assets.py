# -*- coding: utf-8 -*-
"""Full asset build for the dsh-pet AI-girl pack.

Renders all 17 animations for all 8 characters (640x360 / 24fps / VP9-alpha),
then verifies every file, writes ``build/webm/manifest.json`` and one review
montage per character (3 frames per animation) under ``build/previews/``.

Usage
-----
    python tools/build_assets.py                     # full build (crf=36)
    python tools/build_assets.py --crf 30            # high-quality pass
    python tools/build_assets.py --chars gpt kimi    # subset (debug)
    python tools/build_assets.py --workers 8
    python tools/build_assets.py --build-only        # skip verify/manifest
    python tools/build_assets.py --finalize-only     # verify+manifest+previews

Pipeline
--------
1. multiprocessing pool (one worker per character) renders every animation.
2. If the total output size exceeds ``--size-limit-mb``, all footage is
   transcoded once at ``--fallback-crf`` (VP9-alpha -> VP9-alpha, lossless
   timestamps) so the shipped pack stays small.
3. Every webm is probed (640x360, 24fps, vp9, alpha_mode=1, duration) and its
   first frame is decoded through the libvpx-vp9 decoder to prove the alpha
   plane survived encoding.
4. manifest.json + per-character montages are written.
"""
import argparse
import concurrent.futures as cf
import glob
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, 'tools')
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import animlib  # noqa: E402

CHARS = ['deepseek', 'gpt', 'claude', 'grok', 'gemini', 'kimi', 'glm', 'qwen']

ANIM_CLASSES = [
    animlib.RestIdle,        # 待机呼吸 4.0 loop
    animlib.FloatIdle,       # 原地漂浮 4.6 loop
    animlib.NapIdle,         # 原地小憩 6.0 loop
    animlib.LookAround,      # 东张西望 3.0 once
    animlib.DragFlail,       # 被鼠标拖拽悬空反馈 1.6 loop
    animlib.ClickJoy,        # 点击回应-开心跃动 1.35 once
    animlib.ClickShy,        # 点击回应-害羞惊讶 1.4 once
    animlib.ClickWave,       # 点击回应-元气挥手 1.3 once
    animlib.ThinkBubble,     # 工作状态-思考冒泡 3.2 loop
    animlib.BusyBounce,      # 工作状态-忙碌点按 1.6 loop
    animlib.TidyNod,         # 工作状态-清点归档 2.6 loop
    animlib.StepPace,        # 工作状态-原地踱步张望 2.8 loop
    animlib.Celebrate,       # 工作状态-雀跃庆祝 2.2 once
    animlib.DroopSweat,      # 工作状态-垂头叹气冒汗 2.8 loop
    animlib.WhisperDaze,     # 碎碎念-发呆碎碎念 3.6 loop
    animlib.SpinShow,        # 转圈展示 2.4 once
    animlib.Stretch,         # 伸懒腰 2.6 once
]

WEBM_DIR = os.path.join(ROOT, 'build', 'webm')
PREVIEW_DIR = os.path.join(ROOT, 'build', 'previews')
CUTOUT_DIR = os.path.join(ROOT, 'build', 'cutouts')

MAX_DURATION_ERR = 0.15       # seconds, acceptance tolerance
MIN_TRANSPARENT = 0.02        # first frame must have >=2% fully transparent px


def setup_console():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass


def human(nbytes):
    return '%.2f MB' % (nbytes / 1048576.0)


# ---------------------------------------------------------------------------
# phase 1: parallel render (one process per character)
# ---------------------------------------------------------------------------
def build_char(task):
    """Render all animations of one character.  Runs inside a worker process."""
    cid, crf = task
    t0 = time.time()
    char = animlib.Character(os.path.join(CUTOUT_DIR, 'portrait-%s.png' % cid))
    out_dir = os.path.join(WEBM_DIR, cid)
    os.makedirs(out_dir, exist_ok=True)
    entries = {}
    for cls in ANIM_CLASSES:
        anim = cls()
        out_path = os.path.join(out_dir, anim.name + '.webm')
        t_anim = time.time()
        animlib.render_anim(char, anim, out_path, crf=crf)
        size = os.path.getsize(out_path)
        entries[anim.name] = {
            'file': 'webm/%s/%s.webm' % (cid, anim.name),
            'duration': round(anim.frames / float(animlib.FPS), 3),
            'loop': bool(anim.loop),
            'bytes': int(size),
            'frames': int(anim.frames),
        }
        print('[%s] %-14s %5.2fs  %6.2f MB  (%d frames)' % (
            cid, anim.name, time.time() - t_anim, size / 1048576.0, anim.frames), flush=True)
    elapsed = time.time() - t0
    total = sum(e['bytes'] for e in entries.values())
    print('[%s] DONE %d/%d files, %s, %.1fs' % (
        cid, len(entries), len(ANIM_CLASSES), human(total), elapsed), flush=True)
    return cid, entries, elapsed


# ---------------------------------------------------------------------------
# phase 2: optional size reduction via one VP9-alpha -> VP9-alpha transcode
# ---------------------------------------------------------------------------
def reencode_char(task):
    cid, crf = task
    files = sorted(glob.glob(os.path.join(WEBM_DIR, cid, '*.webm')))
    total = 0
    for path in files:
        tmp = path + '.reenc.webm'
        cmd = [
            animlib.FFMPEG, '-y', '-hide_banner', '-loglevel', 'error',
            '-c:v', 'libvpx-vp9', '-i', path,          # force alpha-capable decoder
            '-c:v', 'libvpx-vp9',
            '-pix_fmt', 'yuva420p',
            '-b:v', '0', '-crf', str(crf),
            '-auto-alt-ref', '0',
            '-row-mt', '1',
            '-metadata:s:v:0', 'alpha_mode=1',
            tmp,
        ]
        subprocess.run(cmd, check=True)
        os.replace(tmp, path)
        total += os.path.getsize(path)
    print('[%s] re-encoded %d files at crf=%s -> %s' % (
        cid, len(files), crf, human(total)), flush=True)
    return cid, total


# ---------------------------------------------------------------------------
# phase 3: verification
# ---------------------------------------------------------------------------
_DUR_RE = re.compile(r'Duration:\s*(\d+):(\d+):(\d+\.\d+)')
_SIZE_RE = re.compile(r'Video:\s*vp9[^\n]*?(\d{2,5})x(\d{2,5})')
_FPS_RE = re.compile(r'(\d+(?:\.\d+)?)\s*fps')
_ALPHA_RE = re.compile(r'ALPHA_MODE\s*:\s*1', re.I)


def probe_webm(path):
    """Parse container/stream info with ffmpeg -i (no decoding of the video)."""
    res = subprocess.run([animlib.FFMPEG, '-hide_banner', '-i', path],
                         capture_output=True, text=True,
                         encoding='utf-8', errors='replace')
    txt = res.stderr
    info = {'decoder_ok': False, 'width': None, 'height': None, 'fps': None,
            'duration': None, 'alpha_mode': False}
    m = _DUR_RE.search(txt)
    if m:
        info['duration'] = (int(m.group(1)) * 3600 + int(m.group(2)) * 60
                            + float(m.group(3)))
    m = _SIZE_RE.search(txt)
    if m:
        info['width'], info['height'] = int(m.group(1)), int(m.group(2))
    m = _FPS_RE.search(txt)
    if m:
        info['fps'] = float(m.group(1))
    info['alpha_mode'] = bool(_ALPHA_RE.search(txt))
    info['decoder_ok'] = 'Video: vp9' in txt or 'Video: vp9 ' in txt
    return info


def first_frame_alpha(path):
    """Decode frame 0 through libvpx-vp9 and report alpha statistics."""
    import tempfile
    import numpy as np
    from PIL import Image
    tmp = tempfile.mkdtemp(prefix='petverify_')
    try:
        out = os.path.join(tmp, 'f.png')
        subprocess.run([
            animlib.FFMPEG, '-y', '-hide_banner', '-loglevel', 'error',
            '-c:v', 'libvpx-vp9', '-i', path, '-frames:v', '1',
            '-pix_fmt', 'rgba', out,
        ], check=True)
        im = Image.open(out).convert('RGBA')
        alpha = np.asarray(im)[:, :, 3]
        return {
            'size': list(im.size),
            'alpha_max': int(alpha.max()),
            'transparent_ratio': float((alpha < 16).mean()),
        }
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def verify_file(task):
    cid, name, entry = task
    path = os.path.join(WEBM_DIR, cid, name + '.webm')
    result = {'char': cid, 'anim': name, 'file': path, 'ok': False, 'errors': []}
    try:
        nbytes = os.path.getsize(path)
    except OSError:
        result['errors'].append('missing file')
        return result
    result['bytes'] = nbytes
    if nbytes <= 0:
        result['errors'].append('zero bytes')
        return result
    info = probe_webm(path)
    result.update(info)
    if not info['decoder_ok']:
        result['errors'].append('not decodable as vp9')
    if (info['width'], info['height']) != (animlib.CANVAS_W, animlib.CANVAS_H):
        result['errors'].append('size %sx%s != 640x360' % (info['width'], info['height']))
    if info['fps'] is None or abs(info['fps'] - animlib.FPS) > 0.01:
        result['errors'].append('fps %s != 24' % info['fps'])
    if not info['alpha_mode']:
        result['errors'].append('missing ALPHA_MODE metadata')
    if info['duration'] is None or abs(info['duration'] - entry['duration']) > MAX_DURATION_ERR:
        result['errors'].append('duration %s vs expected %.3f' % (
            info['duration'], entry['duration']))
    try:
        alpha = first_frame_alpha(path)
        result['alpha'] = alpha
        if alpha['size'] != [animlib.CANVAS_W, animlib.CANVAS_H]:
            result['errors'].append('decoded frame size %s' % (alpha['size'],))
        if alpha['alpha_max'] > 254 and alpha['transparent_ratio'] < MIN_TRANSPARENT:
            result['errors'].append('alpha plane looks lost (transparent_ratio=%.3f)' %
                                    alpha['transparent_ratio'])
    except Exception as exc:  # pragma: no cover - defensive
        result['errors'].append('alpha decode failed: %s' % exc)
    result['ok'] = not result['errors']
    return result


# ---------------------------------------------------------------------------
# phase 4: preview montages (3 frames per animation, one row per animation)
# ---------------------------------------------------------------------------
CELL_W, CELL_H = 384, 216
LABEL_W, MARGIN, GAP, HEADER = 180, 14, 8, 52
MONTAGE_W = MARGIN + LABEL_W + GAP + 3 * (CELL_W + GAP) + MARGIN
MONTAGE_H = HEADER + len(ANIM_CLASSES) * (CELL_H + 10) + MARGIN
GROUND_LINE_Y = int(round(animlib.GROUND_Y / float(animlib.CANVAS_H) * CELL_H))


def _load_font(size, bold=False):
    from PIL import ImageFont
    candidates = [
        r'C:\Windows\Fonts\msyhbd.ttc' if bold else r'C:\Windows\Fonts\msyh.ttc',
        r'C:\Windows\Fonts\msyh.ttc',
        r'C:\Windows\Fonts\simhei.ttf',
        r'C:\Windows\Fonts\arial.ttf',
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def extract_preview_frames(webm_path, nframes, out_dir, tag, count=3):
    """Decode `count` evenly spaced frames (RGBA) from a webm.  Returns paths."""
    import tempfile
    idxs = sorted(set([0, nframes // 2, max(0, nframes - 2)]))[:count]
    os.makedirs(out_dir, exist_ok=True)
    tmpdir = tempfile.mkdtemp(prefix='petprev_', dir=out_dir)
    sel = '+'.join('eq(n\\,%d)' % i for i in idxs)
    vf = "select='%s'" % sel
    pattern = os.path.join(tmpdir, 'f%02d.png')
    base = [animlib.FFMPEG, '-y', '-hide_banner', '-loglevel', 'error',
            '-c:v', 'libvpx-vp9', '-i', webm_path, '-vf', vf, '-vsync', '0',
            '-pix_fmt', 'rgba', pattern]
    try:
        subprocess.run(base, check=True)
    except subprocess.CalledProcessError:
        # fallback: seek per frame (input seeking with the libvpx decoder)
        paths = []
        for i, idx in enumerate(idxs):
            dst = os.path.join(tmpdir, 's%02d.png' % i)
            subprocess.run([animlib.FFMPEG, '-y', '-hide_banner', '-loglevel', 'error',
                            '-ss', '%.4f' % (idx / float(animlib.FPS)),
                            '-c:v', 'libvpx-vp9', '-i', webm_path,
                            '-frames:v', '1', '-pix_fmt', 'rgba', dst], check=True)
            paths.append(dst)
        return tmpdir, paths
    paths = sorted(glob.glob(os.path.join(tmpdir, 'f*.png')))
    return tmpdir, paths[:count]


def _checker_background(w, h, tile=16, c1=(104, 110, 124), c2=(126, 132, 146)):
    from PIL import Image, ImageDraw
    im = Image.new('RGB', (w, h), c1)
    d = ImageDraw.Draw(im)
    for y in range(0, h, tile):
        for x in range(0, w, tile):
            if ((x // tile) + (y // tile)) % 2 == 0:
                d.rectangle((x, y, x + tile - 1, y + tile - 1), fill=c2)
    return im


def montage_char(task):
    """Build one character review sheet: 17 rows x 3 sampled frames."""
    from PIL import Image, ImageDraw
    cid, entries = task
    rows = [(cls().name, cls()) for cls in ANIM_CLASSES]
    sheet = Image.new('RGB', (MONTAGE_W, MONTAGE_H), (30, 34, 46))
    draw = ImageDraw.Draw(sheet)
    f_title = _load_font(26, bold=True)
    f_name = _load_font(17, bold=True)
    f_meta = _load_font(13)
    f_cap = _load_font(12)
    total_bytes = sum(entries[name]['bytes'] for name, _ in rows)
    draw.text((MARGIN, 12), '%s   ·   17 animations   ·   %s' % (cid, human(total_bytes)),
              font=f_title, fill=(235, 238, 250))
    y = HEADER
    tmpdirs = []
    try:
        for name, anim in rows:
            entry = entries[name]
            webm = os.path.join(WEBM_DIR, cid, name + '.webm')
            tmpdir, frames = extract_preview_frames(webm, anim.frames, PREVIEW_DIR, name)
            tmpdirs.append(tmpdir)
            # label column
            if f_name.getsize(name)[0] > LABEL_W - 10 and '-' in name:
                a, b = name.split('-', 1)
                draw.text((MARGIN, y + CELL_H // 2 - 34), a, font=f_name, fill=(230, 233, 245))
                draw.text((MARGIN, y + CELL_H // 2 - 10), b, font=f_name, fill=(230, 233, 245))
            else:
                draw.text((MARGIN, y + CELL_H // 2 - 24), name, font=f_name, fill=(230, 233, 245))
            meta = '%ss  %s  %s' % ('%g' % anim.duration,
                                    'loop' if anim.loop else 'once',
                                    '%.2fMB' % (entry['bytes'] / 1048576.0))
            draw.text((MARGIN, y + CELL_H // 2 + 8), meta, font=f_meta, fill=(150, 158, 178))
            # 3 frame cells
            captions = ['0%', '50%', '92%']
            for ci, fp in enumerate(frames):
                x = MARGIN + LABEL_W + GAP + ci * (CELL_W + GAP)
                bg = _checker_background(CELL_W, CELL_H)
                frame = Image.open(fp).convert('RGBA').resize((CELL_W, CELL_H), Image.LANCZOS)
                bg = bg.convert('RGBA')
                bg.alpha_composite(frame)
                bd = ImageDraw.Draw(bg)
                bd.line([(0, GROUND_LINE_Y), (CELL_W, GROUND_LINE_Y)],
                        fill=(110, 200, 140), width=1)
                bd.text((6, 4), captions[ci] if ci < len(captions) else '', font=f_cap,
                        fill=(255, 230, 150))
                sheet.paste(bg.convert('RGB'), (x, y))
            y += CELL_H + 10
    finally:
        import shutil
        for d in tmpdirs:
            shutil.rmtree(d, ignore_errors=True)
    out = os.path.join(PREVIEW_DIR, '%s-montage.png' % cid)
    sheet.save(out, compress_level=6)
    print('[%s] preview -> %s (%dx%d, %s)' % (
        cid, out, sheet.width, sheet.height, human(os.path.getsize(out))), flush=True)
    return cid, out, os.path.getsize(out)


# ---------------------------------------------------------------------------
# optional: headless-Chrome alpha spot check (real browser playback evidence)
# ---------------------------------------------------------------------------
CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'

_ALPHA_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body { margin: 0; background: #1b1e28; font: 13px "Microsoft YaHei", sans-serif; color: #eee; }
  .wrap { display: flex; gap: 20px; padding: 24px; }
  .cell { width: 320px; }
  .cell h3 { margin: 6px 0; font-size: 13px; font-weight: normal; }
  .checker { width: 320px; height: 180px; position: relative; overflow: hidden;
    background-color: #5f6675;
    background-image:
      linear-gradient(45deg, #8d94a3 25%, transparent 25%),
      linear-gradient(-45deg, #8d94a3 25%, transparent 25%),
      linear-gradient(45deg, transparent 75%, #8d94a3 75%),
      linear-gradient(-45deg, transparent 75%, #8d94a3 75%);
    background-size: 24px 24px;
    background-position: 0 0, 0 12px, 12px -12px, -12px 0px; }
  video { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: contain; }
</style>
</head>
<body>
<div class="wrap" id="wrap"></div>
<script>
const files = __FILES__;
const wrap = document.getElementById('wrap');
for (const f of files) {
  const cell = document.createElement('div');
  cell.className = 'cell';
  const h = document.createElement('h3');
  h.textContent = f.name;
  const box = document.createElement('div');
  box.className = 'checker';
  const v = document.createElement('video');
  v.src = f.src;
  v.autoplay = true; v.muted = true; v.loop = true; v.playsInline = true;
  box.appendChild(v);
  cell.appendChild(h); cell.appendChild(box);
  wrap.appendChild(cell);
}
</script>
</body>
</html>
"""


def run_chrome_alpha_check(count=2, seed=20241106):
    """Play N random clips on a checkerboard in real Chrome and screenshot it."""
    import random
    import json as _json
    files = sorted(glob.glob(os.path.join(WEBM_DIR, '*', '*.webm')))
    if not files:
        print('alpha-check: no webm files found')
        return None
    rng = random.Random(seed)
    picks = rng.sample(files, min(count, len(files)))
    rows = []
    for path in picks:
        rows.append({
            'name': os.path.relpath(path, WEBM_DIR).replace('\\', '/'),
            'src': os.path.relpath(path, PREVIEW_DIR).replace('\\', '/'),
        })
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    html_path = os.path.join(PREVIEW_DIR, 'alpha-check.html')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(_ALPHA_HTML.replace('__FILES__', _json.dumps(rows, ensure_ascii=False)))
    png_path = os.path.join(PREVIEW_DIR, 'alpha-check.png')
    print('\nalpha spot check: %s' % ', '.join(os.path.basename(p) for p in picks))
    print('  html: %s' % html_path)
    if not os.path.exists(CHROME):
        print('  WARNING: Chrome not found at %s (screenshot skipped)' % CHROME)
        return None
    url = 'file:///' + html_path.replace('\\', '/')
    cmd = [CHROME, '--headless=new', '--disable-gpu', '--no-sandbox',
           '--autoplay-policy=no-user-gesture-required',
           '--screenshot=' + png_path, '--window-size=720,300',
           '--virtual-time-budget=4000', url]
    try:
        subprocess.run(cmd, check=False, timeout=90)
    except Exception as exc:
        print('  WARNING: chrome screenshot failed: %s' % exc)
        return None
    if os.path.exists(png_path):
        print('  screenshot: %s (%d bytes)' % (png_path, os.path.getsize(png_path)))
        return png_path
    print('  WARNING: Chrome produced no screenshot')
    return None


# ---------------------------------------------------------------------------
# manifest
# ---------------------------------------------------------------------------
def write_manifest(entries_by_char):
    manifest = {}
    for cid in CHARS:
        if cid not in entries_by_char:
            continue
        manifest[cid] = {}
        for cls in ANIM_CLASSES:
            name = cls().name
            e = entries_by_char[cid].get(name)
            if not e:
                continue
            entry = dict(e)
            entry['file'] = 'webm/%s/%s.webm' % (cid, name)
            if not os.path.exists(os.path.join(ROOT, 'build', entry['file'])):
                continue
            entry['bytes'] = os.path.getsize(os.path.join(ROOT, 'build', entry['file']))
            manifest[cid][name] = entry
    path = os.path.join(WEBM_DIR, 'manifest.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write('\n')
    total = sum(e['bytes'] for c in manifest.values() for e in c.values())
    count = sum(len(c) for c in manifest.values())
    print('manifest -> %s  (%d characters, %d animations, %s)' % (
        path, len(manifest), count, human(total)))
    return manifest, path


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description='Build dsh-pet AI-girl webm assets.')
    ap.add_argument('--chars', nargs='*', default=None,
                    help='character ids to build (default: all 8)')
    ap.add_argument('--worker', '--workers', dest='workers', type=int, default=0,
                    help='parallel workers (default: min(8, cpu_count))')
    ap.add_argument('--crf', type=float, default=36,
                    help='initial VP9 crf (default 36: smoke measurement was '
                         '~13.8MB/char at crf=30, so 8 chars would break the '
                         '80MB budget; 34-36 is the Lead-approved band)')
    ap.add_argument('--size-limit-mb', type=float, default=80.0,
                    help='re-encode at --fallback-crf above this total size')
    ap.add_argument('--fallback-crf', type=float, default=38.0)
    ap.add_argument('--no-auto-reencode', action='store_true')
    ap.add_argument('--build-only', action='store_true',
                    help='stop after rendering')
    ap.add_argument('--finalize-only', action='store_true',
                    help='skip rendering, only verify + manifest + previews')
    ap.add_argument('--alpha-check', action='store_true',
                    help='after the build, play 2 random clips in headless Chrome '
                         'on a checkerboard and save a screenshot')
    ap.add_argument('--alpha-check-only', action='store_true',
                    help='only run the headless-Chrome alpha spot check')
    args = ap.parse_args(argv)
    setup_console()
    if args.alpha_check_only:
        return 0 if run_chrome_alpha_check(count=2) else 1

    chars = [c for c in (args.chars or CHARS)]
    bad = [c for c in chars if c not in CHARS]
    if bad:
        sys.exit('unknown character(s): %s (valid: %s)' % (', '.join(bad), ', '.join(CHARS)))
    workers = args.workers or min(8, os.cpu_count() or 4)
    workers = max(1, min(workers, len(chars)))
    cpu = os.cpu_count() or 4
    started = time.time()
    print('=' * 78)
    print('dsh-pet AI-girl asset build')
    print('  characters : %s' % ', '.join(chars))
    print('  animations : %d per character (%d files total)'
          % (len(ANIM_CLASSES), len(chars) * len(ANIM_CLASSES)))
    print('  workers    : %d (cpu=%d)   crf: %g   size limit: %g MB'
          % (workers, cpu, args.crf, args.size_limit_mb))
    print('  output     : %s' % WEBM_DIR)
    print('=' * 78, flush=True)

    os.makedirs(WEBM_DIR, exist_ok=True)
    os.makedirs(PREVIEW_DIR, exist_ok=True)

    entries_by_char = {}
    build_times = {}
    if not args.finalize_only:
        # clean stale files of the characters being rebuilt
        for cid in chars:
            out_dir = os.path.join(WEBM_DIR, cid)
            os.makedirs(out_dir, exist_ok=True)
            for stale in glob.glob(os.path.join(out_dir, '*.webm')):
                os.remove(stale)
        tasks = [(cid, args.crf) for cid in chars]
        with cf.ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(build_char, t): t[0] for t in tasks}
            for fut in cf.as_completed(futures):
                cid, entries, elapsed = fut.result()
                entries_by_char[cid] = entries
                build_times[cid] = elapsed
        total = sum(e['bytes'] for c in entries_by_char.values() for e in c.values())
        print('-' * 78)
        print('build finished in %.1fs, %d files, %s' % (
            time.time() - started, len(chars) * len(ANIM_CLASSES), human(total)))

        # optional size reduction pass
        if total > args.size_limit_mb * 1048576 and not args.no_auto_reencode:
            print('total size %.1f MB > limit %.1f MB -> transcoding at crf=%g'
                  % (total / 1048576.0, args.size_limit_mb, args.fallback_crf), flush=True)
            t_re = time.time()
            with cf.ProcessPoolExecutor(max_workers=workers) as pool:
                list(pool.map(reencode_char, [(cid, args.fallback_crf) for cid in chars]))
            total = sum(os.path.getsize(p) for p in glob.glob(
                os.path.join(WEBM_DIR, '*', '*.webm')))
            print('re-encode finished in %.1fs, now %s' % (time.time() - t_re, human(total)))

        if args.build_only:
            print('build-only requested; skipping verification/manifest/previews')
            return 0

    # finalize requires entries metadata; rebuild it from the spec when needed
    if args.finalize_only:
        for cid in chars:
            entries = {}
            for cls in ANIM_CLASSES:
                anim = cls()
                path = os.path.join(WEBM_DIR, cid, anim.name + '.webm')
                if not os.path.exists(path):
                    sys.exit('missing output for finalize: %s' % path)
                entries[anim.name] = {
                    'file': 'webm/%s/%s.webm' % (cid, anim.name),
                    'duration': round(anim.frames / float(animlib.FPS), 3),
                    'loop': bool(anim.loop),
                    'bytes': os.path.getsize(path),
                    'frames': anim.frames,
                }
            entries_by_char[cid] = entries

    # ---- verification -----------------------------------------------------
    print('\nverifying %d files ...' % (len(chars) * len(ANIM_CLASSES)), flush=True)
    t_ver = time.time()
    tasks = [(cid, cls().name, entries_by_char[cid][cls().name])
             for cid in chars for cls in ANIM_CLASSES]
    results = []
    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        for res in pool.map(verify_file, tasks):
            results.append(res)
    failures = [r for r in results if not r['ok']]
    total_bytes = sum(r.get('bytes', 0) for r in results)
    print('verification: %d/%d PASS (%.1fs)' % (
        len(results) - len(failures), len(results), time.time() - t_ver))
    for r in failures:
        print('  FAIL %s/%s: %s' % (r['char'], r['anim'], '; '.join(r['errors'])))
    if failures:
        print('!! %d file(s) failed verification -> see errors above' % len(failures))

    # ---- manifest ---------------------------------------------------------
    manifest, manifest_path = write_manifest(entries_by_char)

    # ---- previews ---------------------------------------------------------
    print('\nbuilding preview montages ...', flush=True)
    t_prev = time.time()
    for stale_dir in glob.glob(os.path.join(PREVIEW_DIR, 'petprev_*')):
        import shutil
        shutil.rmtree(stale_dir, ignore_errors=True)
    with cf.ProcessPoolExecutor(max_workers=workers) as pool:
        list(pool.map(montage_char, [(cid, entries_by_char[cid]) for cid in chars]))
    print('previews done in %.1fs' % (time.time() - t_prev))

    # ---- optional Chrome alpha spot check --------------------------------
    if args.alpha_check:
        run_chrome_alpha_check(count=2)

    # ---- summary ----------------------------------------------------------
    print('\n' + '=' * 78)
    print('%-10s %6s %10s %8s' % ('char', 'files', 'size', 'build'))
    print('-' * 78)
    for cid in chars:
        n = len(entries_by_char[cid])
        size = sum(e['bytes'] for e in entries_by_char[cid].values())
        print('%-10s %6d %9s %7.1fs' % (cid, n, human(size), build_times.get(cid, 0.0)))
    print('-' * 78)
    print('%-10s %6d %9s %7.1fs' % ('TOTAL', len(results), human(total_bytes),
                                    time.time() - started))
    print('manifest   : %s' % manifest_path)
    print('previews   : %s' % PREVIEW_DIR)
    print('verification: %s' % ('ALL PASS' if not failures else '%d FAILURES' % len(failures)))
    print('crf        : %g%s' % (args.crf,
                                 '' if args.no_auto_reencode else
                                 ' (fallback %g if > %g MB)' % (args.fallback_crf,
                                                                 args.size_limit_mb)))
    print('=' * 78)
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
