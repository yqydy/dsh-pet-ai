# -*- coding: utf-8 -*-
"""Validate every pet webm in a real browser: true alpha + no frame clipping.

Chrome cannot decode VP9-alpha through ffmpeg here (ffmpeg build drops alpha),
so we seek every clip in headless Chrome, draw it on a canvas, read the alpha
channel from getImageData and report the content bounding box over sampled
frames.  Clipping = the character touches the canvas border in any sampled
frame (would mean head/feet/weapon cut off when shown as a desktop pet).

Usage:
  python tools/framecheck.py [--dir build/webm] [--out build/verify/framecheck.json]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'

HTML = r'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>body{margin:0;background:#000;color:#0f0;font:12px monospace}canvas{display:none}</style></head>
<body><pre id="out">RUNNING</pre>
<script>
const FILES = %FILES%;
const TIMES = [0.12, 0.35, 0.6, 0.88];
const cv = document.createElement('canvas'); cv.width = 640; cv.height = 360;
const ctx = cv.getContext('2d', { willReadFrequently: true });
function aabb(data) {
  let minX = 999, minY = 999, maxX = -1, maxY = -1, count = 0;
  for (let y = 0; y < 360; y++) {
    for (let x = 0; x < 640; x++) {
      const a = data[(y * 640 + x) * 4 + 3];
      if (a > 8) { count++; if (x < minX) minX = x; if (x > maxX) maxX = x; if (y < minY) minY = y; if (y > maxY) maxY = y; }
    }
  }
  return { minX, minY, maxX, maxY, count };
}
function loadVideo(src) {
  return new Promise((resolve, reject) => {
    const v = document.createElement('video');
    v.muted = true; v.playsInline = true; v.preload = 'auto';
    v.onloadeddata = () => resolve(v);
    v.onerror = () => reject(new Error('video error'));
    v.src = src; v.load();
  });
}
function seek(v, t) {
  return new Promise((resolve) => {
    const done = () => { v.removeEventListener('seeked', done); resolve(); };
    v.addEventListener('seeked', done);
    v.currentTime = Math.max(0.01, Math.min(t, Math.max(0.02, (v.duration || 1) - 0.05)));
  });
}
(async () => {
  const out = [];
  for (let i = 0; i < FILES.length; i++) {
    const rel = FILES[i];
    const item = { file: rel, frames: [], error: null };
    try {
      const v = await loadVideo('../webm/' + rel);
      item.duration = v.duration;
      for (const t of TIMES) {
        if (t > (v.duration || 0)) continue;
        await seek(v, t);
        ctx.clearRect(0, 0, 640, 360);
        ctx.drawImage(v, 0, 0, 640, 360);
        const d = ctx.getImageData(0, 0, 640, 360).data;
        const b = aabb(d);
        item.frames.push({ t: Math.round(t * 100) / 100, minX: b.minX, minY: b.minY, maxX: b.maxX, maxY: b.maxY, alphaPixels: b.count });
      }
      v.src = ''; v.load();
    } catch (e) { item.error = String(e && e.message || e); }
    out.push(item);
    document.getElementById('out').textContent = 'PROGRESS ' + (i + 1) + '/' + FILES.length;
  }
  document.getElementById('out').textContent = 'RESULT:' + JSON.stringify(out);
})();
</script></body></html>'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default=os.path.join(ROOT, 'build', 'webm'))
    ap.add_argument('--out', default=os.path.join(ROOT, 'build', 'verify', 'framecheck.json'))
    args = ap.parse_args()
    files = []
    for root, dirs, names in os.walk(args.dir):
        for n in sorted(names):
            if n.endswith('.webm'):
                files.append(os.path.relpath(os.path.join(root, n), args.dir).replace('\\', '/'))
    if not files:
        print('no webm found under', args.dir)
        sys.exit(1)
    files.sort()
    tmpdir = os.path.join(ROOT, 'build', 'framecheck')
    os.makedirs(tmpdir, exist_ok=True)
    html = HTML.replace('%FILES%', json.dumps(files, ensure_ascii=False))
    page = os.path.join(tmpdir, 'index.html')
    with open(page, 'w', encoding='utf-8') as f:
        f.write(html)
    user_data = os.path.join(tmpdir, 'chrome-profile')
    cmd = [CHROME, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
           '--autoplay-policy=no-user-gesture-required',
           '--user-data-dir=' + user_data,
           '--virtual-time-budget=180000', '--dump-dom',
           'file:///' + page.replace('\\', '/')]
    print('running headless Chrome on %d clips ...' % len(files))
    r = subprocess.run(cmd, capture_output=True, timeout=600)
    dom = (r.stdout or b'').decode('utf-8', errors='replace')
    m = re.search(r'RESULT:(\[.*?\])</pre>', dom, re.S)
    if not m:
        print('no RESULT in DOM; tail:', dom[-800:])
        sys.exit(2)
    data = json.loads(m.group(1))
    results = []
    clip_fail = []
    media_fail = []
    for item in data:
        if item.get('error'):
            media_fail.append(item['file'] + ': ' + item['error'])
            continue
        fr = item.get('frames') or []
        if not fr:
            media_fail.append(item['file'] + ': no frames')
            continue
        min_x = min(f['minX'] for f in fr)
        min_y = min(f['minY'] for f in fr)
        max_x = max(f['maxX'] for f in fr)
        max_y = max(f['maxY'] for f in fr)
        clip = {
            'top': min_y <= 1,
            'bottom': max_y >= 358,
            'left': min_x <= 1,
            'right': max_x >= 638,
        }
        rec = {
            'file': item['file'], 'duration': item.get('duration'),
            'bbox': {'minX': min_x, 'minY': min_y, 'maxX': max_x, 'maxY': max_y},
            'clip': clip, 'ok': not any(clip.values()),
        }
        results.append(rec)
        if not rec['ok']:
            clip_fail.append(rec)
    summary = {
        'total': len(files),
        'checked': len(results),
        'media_fail': media_fail,
        'clip_fail': [r['file'] for r in clip_fail],
        'pass': len(results) - len(clip_fail),
        'results': results,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print('checked %d clips: pass=%d clip_fail=%d media_fail=%d' % (
        summary['checked'], summary['pass'], len(clip_fail), len(media_fail)))
    for r in clip_fail[:15]:
        print('  CLIP', r['file'], r['bbox'], r['clip'])
    for m_ in media_fail[:10]:
        print('  MEDIA', m_)
    print('report:', args.out)
    sys.exit(0 if (not clip_fail and not media_fail) else 3)


if __name__ == '__main__':
    main()
