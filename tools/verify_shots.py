#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
verify_shots.py —— 截图证据采集 + 像素级分析（headless Chrome + Win32 PrintWindow）。

为什么 GUI 截图不用 headless Chrome 打开 http://127.0.0.1:57076/：
  该 URL 对未携带 token 的请求返回 401 "dsh web authentication required; reopen the URL
  printed by dsh web."（已实测），headless Chrome 只能截到 401 页面。按 Lead 指定方案改为：
  - 真实桌宠窗口：Win32 PrintWindow 抓 "dsh-pet 桌宠（桌面模式）" 透明窗口（每只宠物一个窗口）；
  - DSH 主窗口：PrintWindow 抓标题含 "DeepSeek Harness" 的窗口（真实 GUI 内容）。

证据块：
  (a) alpha 测试：pack webm 放棋盘格上截图 + 同布局无视频背景图，像素对比判断透明；
      产出 build/shots/alpha-test.png / alpha-bg.png / alpha-crop-*.png
  (b) 图鉴页：file:// 截 plugin/visual/index.html -> build/shots/gallery.png
  (c) 真实窗口：调用 tools/verify_shots.ps1 枚举窗口，抓所有标题匹配的窗口 ->
      build/shots/pet-windows/、build/shots/dsh-gui-windows/
  (d) pet pack 预览页：从活的 /dsh-pet-7340/thumb/<prefix>/<待机动画>.webm 下载 8 个待机动画
      到 build/verify/assets/，生成 build/verify/preview.html（1600x900、按各 pack 的 size
      并排展示 8 只宠物），Chrome headless 截图 -> build/shots/petpack-preview.png

用法：
  python tools/verify_shots.py                     # 全量（阶段二）
  python tools/verify_shots.py --skip-gui --skip-preview   # 只跑 alpha + 图鉴
  python tools/verify_shots.py --skip-alpha --skip-gallery # 只跑窗口 + 预览
  python tools/verify_shots.py --strict            # 缺失 packs/图鉴 -> FAIL（默认 SKIP）
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:  # noqa: BLE001
    pass

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME_DEFAULT = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
SHOTS_DEFAULT = os.path.join(PROJECT, 'build', 'shots')
GUI_DEFAULT = 'http://127.0.0.1:57076'
THUMB_ROUTE = '/dsh-pet-7340/thumb/'
EXPECTED_IDS = ['deepseek', 'gpt', 'claude', 'grok', 'gemini', 'kimi', 'glm', 'qwen']
EXPECTED_PREFIXES = ['girl-' + i for i in EXPECTED_IDS]
CAPTURE_PS1 = os.path.join(PROJECT, 'tools', 'verify_shots.ps1')
POWERSHELL = r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'

checks = []
artifacts = {}
SHOTS = SHOTS_DEFAULT


def add(check_id, name, status, detail='', evidence=None):
    checks.append({'id': check_id, 'name': name, 'status': status,
                   'detail': detail, 'evidence': evidence})


def chrome_path(p):
    if p and os.path.isfile(p):
        return p
    for cand in (CHROME_DEFAULT,
                 r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
                 shutil.which('chrome') or '', shutil.which('chrome.exe') or ''):
        if cand and os.path.isfile(cand):
            return cand
    return None


def chrome_shot(chrome, url, out_png, window, budget, extra=None, timeout=150):
    rec = {'url': url, 'out': out_png, 'ok': False, 'ms': 0, 'returncode': None,
           'stderr_tail': '', 'size': None, 'error': ''}
    if not chrome:
        rec['error'] = 'chrome not found'
        return rec
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    if os.path.exists(out_png):
        try:
            os.remove(out_png)
        except OSError:
            pass
    args = [
        chrome, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
        '--no-first-run', '--no-default-browser-check', '--disable-extensions',
        '--disable-background-networking', '--mute-audio', '--force-device-scale-factor=1',
        '--user-data-dir=' + os.path.join(SHOTS, 'chrome-profile'),
        '--window-size=%d,%d' % window,
        '--virtual-time-budget=%d' % budget,
        '--run-all-compositor-stages-before-draw',
        '--autoplay-policy=no-user-gesture-required',
        '--allow-file-access-from-files',
        '--screenshot=' + os.path.abspath(out_png),
    ]
    if extra:
        args.extend(extra)
    args.append(url)
    t0 = time.time()
    try:
        p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        rec['returncode'] = p.returncode
        err = (p.stderr or b'').decode('utf-8', errors='replace')
        rec['stderr_tail'] = '\n'.join(err.strip().splitlines()[-3:])
    except Exception as e:  # noqa: BLE001
        rec['error'] = '%s: %s' % (type(e).__name__, e)
    rec['ms'] = int((time.time() - t0) * 1000)
    if os.path.isfile(out_png):
        rec['size'] = os.path.getsize(out_png)
        rec['ok'] = rec['size'] > 1000
    if not rec['ok'] and not rec['error']:
        rec['error'] = '截图文件缺失或过小'
    return rec


def img_stats(path):
    try:
        from PIL import Image
        import numpy as np
    except Exception:  # noqa: BLE001
        return None
    try:
        im = Image.open(path).convert('RGB')
        a = np.asarray(im).astype(np.int32)
        return {
            'width': im.width, 'height': im.height,
            'mean': round(float(a.mean()), 2), 'std': round(float(a.std()), 2),
            'nonwhite_ratio': round(float((np.abs(a - 255).max(axis=2) > 12).mean()), 4),
            'black_ratio': round(float((a.max(axis=2) < 24).mean()), 4),
        }
    except Exception:  # noqa: BLE001
        return None


def http_get(url, timeout=20, max_bytes=None):
    rec = {'url': url, 'status': None, 'error': '', 'content_type': '', 'content_length': None}
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'dsh-verifier/1.0'})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            rec['status'] = resp.status
            rec['content_type'] = resp.headers.get('content-type', '')
            cl = resp.headers.get('content-length')
            rec['content_length'] = int(cl) if cl is not None and str(cl).isdigit() else None
            rec['body'] = resp.read() if max_bytes is None else resp.read(max_bytes)
    except urllib.error.HTTPError as e:  # noqa: F821
        rec['status'] = e.code
        rec['error'] = 'HTTPError %s' % e.code
        try:
            rec['body'] = e.read(2048)
        except Exception:  # noqa: BLE001
            rec['body'] = b''
    except Exception as e:  # noqa: BLE001
        rec['error'] = '%s: %s' % (type(e).__name__, e)
    return rec


# ---------------- alpha 测试 ----------------
ALPHA_CSS = """
* { box-sizing: border-box; }
body { margin: 0; background: #222; font-family: sans-serif; }
.wrap { display: flex; gap: 12px; padding: 12px; }
.cell { width: 320px; }
.cell h3 { height: 22px; margin: 0; padding: 0; font: 14px/22px sans-serif; color: #fff;
           white-space: nowrap; overflow: hidden; }
.checker { width: 320px; height: 180px; position: relative; overflow: hidden;
  background-image:
    linear-gradient(45deg, #999 25%, transparent 25%),
    linear-gradient(-45deg, #999 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, #999 75%),
    linear-gradient(-45deg, transparent 75%, #999 75%);
  background-size: 24px 24px;
  background-position: 0 0, 0 12px, 12px -12px, -12px 0px;
  background-color: #666; }
video { position: absolute; left: 0; top: 0; width: 100%; height: 100%; object-fit: contain; }
"""


def pack_configs(packs_dir):
    """读 plugin/packs 下 config，返回 [{id,prefix,name,size,corner,idle,click}]。"""
    out = []
    if not os.path.isdir(packs_dir):
        return out
    for fn in sorted(os.listdir(packs_dir)):
        m = re.match(r'^(.+?)-config\.(json|jsonc)$', fn)
        if not m:
            continue
        prefix = m.group(1)
        try:
            with open(os.path.join(packs_dir, fn), 'r', encoding='utf-8-sig') as f:
                raw = f.read()
            try:
                cfg = json.loads(raw)
            except Exception:  # noqa: BLE001
                stripped = re.sub(r'/\*[\s\S]*?\*/', '', raw)
                stripped = re.sub(r'(^|[^\\:])//.*$', r'\1', stripped, flags=re.M)
                cfg = json.loads(stripped)
        except Exception:  # noqa: BLE001
            continue
        pets = cfg.get('pets') if isinstance(cfg.get('pets'), list) else []
        pet = pets[0] if pets and isinstance(pets[0], dict) else {}
        anims = cfg.get('animations') if isinstance(cfg.get('animations'), dict) else {}
        idle = [n for n in (anims.get('idle') or []) if isinstance(n, str)]
        clicks = [n for n in (anims.get('clicks') or []) if isinstance(n, str)]
        out.append({
            'prefix': prefix,
            'id': str(pet.get('id') or prefix),
            'name': str(pet.get('name') or prefix),
            'size': pet.get('size') if isinstance(pet.get('size'), (int, float)) else 320,
            'corner': str((pet.get('position') or {}).get('corner') or ''),
            'display': str(pet.get('display') or ''),
            'idle': idle,
            'click': clicks,
        })
    return out


def anim_dir_for(packs_dir, prefix):
    d = os.path.join(packs_dir, '%s-animation' % prefix)
    if os.path.isdir(os.path.join(d, 'webm')):
        return os.path.join(d, 'webm')
    return d


def gather_alpha_samples(packs_dir, fallback_dir):
    samples = []
    for p in pack_configs(packs_dir)[:1]:
        d = anim_dir_for(packs_dir, p['prefix'])
        names = p['idle'][:1] + p['click'][:1]
        for n in names:
            fp = os.path.join(d, n + '.webm')
            if os.path.isfile(fp):
                samples.append({'prefix': p['prefix'], 'name': n, 'path': fp})
    if not samples and fallback_dir and os.path.isdir(fallback_dir):
        files = sorted(f for f in os.listdir(fallback_dir) if f.lower().endswith('.webm'))[:2]
        for fn in files:
            samples.append({'prefix': 'fallback', 'name': os.path.splitext(fn)[0],
                            'path': os.path.join(fallback_dir, fn)})
    return samples


def build_alpha_pages(samples, out_dir):
    def html(with_video):
        cells = []
        for s in samples:
            rel = os.path.relpath(s['path'], out_dir).replace('\\', '/')
            rel = '/'.join(urllib.parse.quote(seg) for seg in rel.split('/'))
            vid = '<video src="%s" autoplay muted loop playsinline></video>' % rel if with_video else ''
            cells.append('<div class="cell"><h3>%s - %s</h3><div class="checker">%s</div></div>'
                         % (s['prefix'], s['name'], vid))
        return ('<!DOCTYPE html><html><head><meta charset="utf-8"><style>%s</style></head>'
                '<body><div class="wrap">%s</div></body></html>' % (ALPHA_CSS, '\n'.join(cells)))
    p1 = os.path.join(out_dir, 'alpha-test.html')
    p2 = os.path.join(out_dir, 'alpha-bg.html')
    with open(p1, 'w', encoding='utf-8') as f:
        f.write(html(True))
    with open(p2, 'w', encoding='utf-8') as f:
        f.write(html(False))
    return p1, p2


def analyze_alpha(img_with, img_bg, n_cells):
    try:
        from PIL import Image
        import numpy as np
    except Exception as e:  # noqa: BLE001
        return {'error': 'PIL/numpy 不可用: %s' % e}
    a = np.asarray(Image.open(img_with).convert('RGB')).astype(np.int32)
    b = np.asarray(Image.open(img_bg).convert('RGB')).astype(np.int32)
    h, w = min(a.shape[0], b.shape[0]), min(a.shape[1], b.shape[1])
    a, b = a[:h, :w], b[:h, :w]
    pad, h3h, cw, ch, gap = 12, 22, 320, 180, 12
    sx = w / max(1.0, pad * 2 + cw * n_cells + gap * (n_cells - 1))
    sy = h / max(1.0, pad * 2 + h3h + ch)
    cells = []
    for i in range(n_cells):
        x0 = int((pad + i * (cw + gap)) * sx)
        y0 = int((pad + h3h) * sy)
        x1 = min(int((pad + i * (cw + gap) + cw) * sx), w)
        y1 = min(int((pad + h3h + ch) * sy), h)
        if x1 <= x0 or y1 <= y0:
            continue
        ra, rb = a[y0:y1, x0:x1], b[y0:y1, x0:x1]
        diff = np.abs(ra - rb).max(axis=2)
        cells.append({
            'index': i, 'rect': [x0, y0, x1, y1],
            'identical_ratio': round(float((diff <= 8).mean()), 4),
            'diff_ratio': round(1.0 - float((diff <= 8).mean()), 4),
            'black_ratio': round(float((ra.max(axis=2) < 24).mean()), 4),
            'checker_gray_ratio': round(float(((np.abs(ra[:, :, 0] - ra[:, :, 1]) < 10) &
                                               (np.abs(ra[:, :, 1] - ra[:, :, 2]) < 10) &
                                               (ra.max(axis=2) >= 70) & (ra.max(axis=2) <= 190)).mean()), 4),
        })
    return {'cells': cells, 'size': [w, h]}


# ---------------- 真实窗口捕获 ----------------
def run_capture_ps1(title_match, out_dir, json_out, timeout=180):
    rec = {'title_match': title_match, 'out_dir': out_dir, 'json': json_out,
           'ok': False, 'error': '', 'data': None, 'ms': 0}
    if not os.path.isfile(CAPTURE_PS1):
        rec['error'] = 'tools/verify_shots.ps1 不存在'
        return rec
    ps = POWERSHELL if os.path.isfile(POWERSHELL) else 'powershell.exe'
    args = [ps, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', CAPTURE_PS1,
            '-TitleMatch', title_match, '-OutDir', out_dir, '-JsonOut', json_out]
    os.makedirs(os.path.dirname(json_out), exist_ok=True)
    t0 = time.time()
    try:
        p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        rec['returncode'] = p.returncode
        rec['stderr_tail'] = '\n'.join((p.stderr or b'').decode('utf-8', errors='replace')
                                       .strip().splitlines()[-3:])
    except Exception as e:  # noqa: BLE001
        rec['error'] = '%s: %s' % (type(e).__name__, e)
        return rec
    rec['ms'] = int((time.time() - t0) * 1000)
    if os.path.isfile(json_out):
        try:
            with open(json_out, 'r', encoding='utf-8-sig') as f:
                rec['data'] = json.load(f)
            rec['ok'] = True
        except Exception as e:  # noqa: BLE001
            rec['error'] = 'JSON 解析失败: %s' % e
    else:
        rec['error'] = rec.get('stderr_tail') or '未生成 JSON（窗口枚举失败）'
    return rec


def summarize_capture(rec):
    d = rec.get('data') or {}
    caps = d.get('captured') or []
    return {
        'matched': d.get('matched'),
        'windows_total': len(d.get('windows') or []),
        'captured': [{'title': c.get('title'), 'width': c.get('width'), 'height': c.get('height'),
                      'bytes': c.get('bytes'), 'path': os.path.relpath(c.get('path'), PROJECT)
                      if c.get('path') else None, 'result': c.get('result')} for c in caps],
    }


def run_gui_evidence(chrome, base):
    """真实窗口证据（PrintWindow）：DSH GUI 根路径 401 是已知鉴权限制，改抓窗口。"""
    gateway = base.rstrip('/')
    r = http_get(gateway + '/', timeout=10, max_bytes=2048)
    body = (r.get('body') or b'').decode('utf-8', errors='replace')[:200]
    if r['status'] == 401 and 'authentication' in body:
        add('dsh.http', 'DSH GUI 根路径鉴权探测', 'PASS',
            'GET %s/ -> 401（已知限制：需要 dsh web 打印的 token，headless 无法自动获得；'
            '改用 Win32 PrintWindow 抓真实窗口）body=%r' % (gateway, body[:120]))
        artifacts['dsh_http_401'] = {'status': 401, 'body': body}
    elif r['status'] == 200:
        add('dsh.http', 'DSH GUI 根路径鉴权探测', 'PASS', 'GET / -> 200')
    else:
        add('dsh.http', 'DSH GUI 根路径鉴权探测', 'WARN',
            'status=%r error=%s body=%r' % (r['status'], r.get('error'), body[:120]))

    # 1) dsh-pet 桌面宠物窗口（每只宠物一个窗口，标题相同）
    pet_dir = os.path.join(SHOTS, 'pet-windows')
    rec = run_capture_ps1('dsh-pet', pet_dir, os.path.join(PROJECT, 'build', 'verify', 'windows_pet.json'))
    sm = summarize_capture(rec)
    artifacts['windows_pet'] = {'rec_ok': rec['ok'], 'ms': rec['ms'], **sm}
    pets = [c for c in sm['captured'] if c.get('path') and c.get('bytes', 0) > 5000
            and ('桌宠' in (c.get('title') or '') or (c.get('width') or 0) < 1200)]
    gui_wins = [c for c in sm['captured'] if c.get('path') and (c.get('width') or 0) >= 1200]
    if not rec['ok']:
        add('dsh.window.capture', 'Win32 窗口枚举/抓图', 'FAIL', rec.get('error', ''))
    else:
        add('dsh.window.capture', 'Win32 窗口枚举/抓图', 'PASS',
            '可见窗口 %s 个，标题匹配 dsh-pet %s 个，抓图 %d 个（%.1fs）' % (
                sm['windows_total'], sm['matched'], len(sm['captured']), rec['ms'] / 1000.0))
        if pets:
            add('dsh.pet_windows', '抓到 dsh-pet 桌面宠物窗口', 'PASS',
                '; '.join('[%dx%d %dB] %s' % (c['width'], c['height'], c['bytes'],
                                              os.path.basename(c['path'])) for c in pets[:8]))
        else:
            add('dsh.pet_windows', '抓到 dsh-pet 桌面宠物窗口', 'FAIL',
                '未抓到带"桌宠"标题的窗口；captured=%s' % json.dumps(sm['captured'], ensure_ascii=False)[:400])
        if gui_wins:
            add('dsh.gui_window', '抓到 DSH GUI 主窗口（PrintWindow）', 'PASS',
                '; '.join('[%dx%d %dB] %s' % (c['width'], c['height'], c['bytes'],
                                              os.path.basename(c['path'])) for c in gui_wins[:4]))
    # 2) DSH 主窗口单独再按 "DeepSeek Harness" 抓一次（标题可能不含 dsh-pet）
    gui_dir = os.path.join(SHOTS, 'dsh-gui-windows')
    rec2 = run_capture_ps1('DeepSeek Harness', gui_dir,
                           os.path.join(PROJECT, 'build', 'verify', 'windows_gui.json'))
    sm2 = summarize_capture(rec2)
    artifacts['windows_gui'] = {'rec_ok': rec2['ok'], 'ms': rec2['ms'], **sm2}
    good = [c for c in sm2['captured'] if c.get('path') and c.get('bytes', 0) > 5000]
    if good:
        stats = img_stats(os.path.join(PROJECT, good[0]['path']))
        artifacts['gui_window_stats'] = stats
        add('dsh.gui_window2', 'DSH 主窗口截图（按标题 DeepSeek Harness）', 'PASS',
            '%d 张；首张 %dx%d %s stats=%s' % (len(good), good[0]['width'], good[0]['height'],
                                              os.path.basename(good[0]['path']), stats))
        # 复制一张规范命名的 GUI 证据
        src = os.path.join(PROJECT, good[0]['path'])
        dst = os.path.join(SHOTS, 'dsh-gui-window.png')
        try:
            shutil.copyfile(src, dst)
            artifacts['dsh_gui_png'] = os.path.relpath(dst, PROJECT)
        except Exception:  # noqa: BLE001
            pass
    else:
        add('dsh.gui_window2', 'DSH 主窗口截图（按标题 DeepSeek Harness）', 'WARN',
            '未抓到匹配窗口（可能标题不含该字样）: %s' % json.dumps(sm2['captured'], ensure_ascii=False)[:300])


# ---------------- pet pack 预览页 ----------------
PREVIEW_CSS = """
* { box-sizing: border-box; }
body { margin: 0; width: 1600px; height: 900px; overflow: hidden;
  background: radial-gradient(circle at 50% 20%, #2b3550 0%, #151a26 55%, #0b0d12 100%);
  font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif; color: #e8ecf6; }
h1 { margin: 0; padding: 18px 24px 6px; font-size: 26px; letter-spacing: 1px; }
h1 small { font-size: 14px; color: #8f9bb3; margin-left: 12px; font-weight: 400; }
.grid { display: grid; grid-template-columns: repeat(4, 1fr); grid-template-rows: repeat(2, 1fr);
  gap: 10px; padding: 8px 20px 18px; height: calc(900px - 64px); }
.card { position: relative; border-radius: 14px; overflow: hidden;
  background: rgba(255,255,255,0.035); border: 1px solid rgba(255,255,255,0.10);
  box-shadow: 0 8px 22px rgba(0,0,0,0.35); }
.card .name { position: absolute; left: 14px; top: 10px; font-size: 17px; font-weight: 600;
  text-shadow: 0 2px 6px #000; z-index: 2; }
.card .meta { position: absolute; right: 12px; top: 13px; font-size: 11px; color: #9fb0cc;
  z-index: 2; font-family: Consolas, monospace; }
.card .stage { position: absolute; inset: 34px 10px 10px; border-radius: 10px; overflow: hidden;
  background-image:
    linear-gradient(45deg, rgba(255,255,255,0.055) 25%, transparent 25%),
    linear-gradient(-45deg, rgba(255,255,255,0.055) 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, rgba(255,255,255,0.055) 75%),
    linear-gradient(-45deg, transparent 75%, rgba(255,255,255,0.055) 75%);
  background-size: 28px 28px;
  background-position: 0 0, 0 14px, 14px -14px, -14px 0px;
  background-color: rgba(12,16,24,0.35); }
.card video { position: absolute; left: 50%; bottom: 6px; transform: translateX(-50%);
  max-width: 96%; max-height: 92%; filter: drop-shadow(0 6px 14px rgba(0,0,0,0.55)); }
.card .corner { position: absolute; right: 10px; bottom: 6px; font-size: 10px; color: #7386a5;
  z-index: 2; font-family: Consolas, monospace; }
"""


def resolve_preview_entries(packs_dir, base):
    """优先用 plugin/packs 的 8 个 pack；否则回退活的 /config 中非 main 条目（阶段一自测）。"""
    confs = pack_configs(packs_dir)
    if len(confs) >= 1:
        return confs, 'packs'
    # fallback: live config
    r = http_get(base.rstrip('/') + '/dsh-pet-7340/config', timeout=15)
    entries = []
    if r['status'] == 200:
        try:
            cfg = json.loads((r.get('body') or b'').decode('utf-8'))
            for key, val in cfg.items():
                if key == 'main' or not isinstance(val, dict):
                    continue
                pets = val.get('pets') if isinstance(val.get('pets'), list) else []
                pet = pets[0] if pets else {}
                anims = val.get('animations') if isinstance(val.get('animations'), dict) else {}
                idle = [n for n in (anims.get('idle') or []) if isinstance(n, str)]
                entries.append({'prefix': key, 'id': str(pet.get('id') or key),
                                'name': str(pet.get('name') or key),
                                'size': pet.get('size') if isinstance(pet.get('size'), (int, float)) else 320,
                                'corner': str((pet.get('position') or {}).get('corner') or ''),
                                'display': str(pet.get('display') or ''),
                                'idle': idle, 'click': []})
        except Exception:  # noqa: BLE001
            pass
    return entries, 'live-fallback'


def build_preview_page(entries, assets_dir, out_html, base):
    os.makedirs(assets_dir, exist_ok=True)
    cards = []
    downloaded = []
    for e in entries:
        idle = (e.get('idle') or ['待机呼吸'])[0]
        url = (base.rstrip('/') + THUMB_ROUTE +
               urllib.parse.quote(e['prefix']) + '/' + urllib.parse.quote(idle + '.webm'))
        r = http_get(url, timeout=30)
        fn = '%s--%s.webm' % (re.sub(r'[^\w.-]+', '_', e['prefix']),
                              re.sub(r'[^\w.-]+', '_', idle))
        fp = os.path.join(assets_dir, fn)
        ok = r['status'] == 200 and 'video/webm' in (r.get('content_type') or '') and r.get('body')
        rec = {'prefix': e['prefix'], 'name': e.get('name'), 'idle': idle, 'url': url,
               'status': r['status'], 'content_type': r.get('content_type'),
               'content_length': r.get('content_length'),
               'saved': None, 'bytes': 0,
               'disk_size': None, 'size_match': None}
        if ok:
            with open(fp, 'wb') as f:
                f.write(r['body'])
            rec['bytes'] = len(r['body'])
            rec['saved'] = os.path.relpath(fp, PROJECT)
            # 对比 pack 源文件大小
            d = anim_dir_for(os.path.abspath(os.path.join(PROJECT, 'plugin', 'packs')), e['prefix'])
            src = os.path.join(d, idle + '.webm')
            if os.path.isfile(src):
                rec['disk_size'] = os.path.getsize(src)
                rec['size_match'] = rec['disk_size'] == rec['content_length']
            downloaded.append(rec)
            # size：视频显示宽度（dsh-pet 里 size = stage 宽度，高 = size*9/16）
            w = int(min(max(120, e.get('size') or 320), 360))
            h = int(w * 9 / 16)
            cards.append(
                '<div class="card"><div class="name">%s</div>'
                '<div class="meta">size=%s</div>'
                '<div class="stage"><video src="assets/%s" autoplay muted loop playsinline '
                'style="width:%dpx;height:%dpx"></video></div>'
                '<div class="corner">%s · %s</div></div>'
                % (e.get('name'), e.get('size'), fn, w, h, e.get('corner'), e.get('display')))
    if not cards:
        return None, downloaded
    html = ('<!DOCTYPE html><html><head><meta charset="utf-8"><style>%s</style></head><body>'
            '<h1>AI 娘桌宠 pet pack 预览 <small>dsh-pet-ai-girls · %d 个角色 · 待机动画（活路由 '
            '/thumb/&lt;prefix&gt;/&lt;名&gt;.webm 下载）</small></h1>'
            '<div class="grid">%s</div></body></html>'
            % (PREVIEW_CSS, len(cards), '\n'.join(cards)))
    os.makedirs(os.path.dirname(out_html), exist_ok=True)
    with open(out_html, 'w', encoding='utf-8') as f:
        f.write(html)
    return out_html, downloaded


def run_preview(chrome, base, packs_dir, args):
    entries, mode = resolve_preview_entries(packs_dir, base)
    artifacts['preview_mode'] = mode
    if not entries:
        add('preview.entries', 'pet pack 预览数据源', 'FAIL' if args.strict else 'SKIP',
            'packs 目录无 config，且活的 /config 也没有非 main 条目')
        return
    if len(entries) < 8:
        add('preview.entries', 'pet pack 预览数据源', 'FAIL' if args.strict else 'WARN',
            '仅发现 %d/8 个角色（mode=%s）：%s' % (len(entries), mode,
                                                  ', '.join(e['prefix'] for e in entries)))
    else:
        add('preview.entries', 'pet pack 预览数据源', 'PASS',
            '8/8 个角色（mode=%s）: %s' % (mode, ', '.join(e['prefix'] for e in entries)))
    assets_dir = os.path.join(PROJECT, 'build', 'verify', 'assets')
    out_html = os.path.join(PROJECT, 'build', 'verify', 'preview.html')
    page, downloaded = build_preview_page(entries, assets_dir, out_html, base)
    artifacts['preview_downloads'] = downloaded
    bad = [d for d in downloaded if d['status'] != 200 or not d['saved']]
    if bad:
        add('preview.download', '待机动画 /thumb 下载', 'FAIL',
            '; '.join('%s status=%s' % (b['prefix'], b['status']) for b in bad[:8]))
    else:
        mism = [d for d in downloaded if d['size_match'] is False]
        add('preview.download', '待机动画 /thumb 下载', 'PASS' if not mism else 'WARN',
            '%d 个 webm 全部 200 video/webm；content-length 与磁盘一致=%d 个%s' % (
                len(downloaded), len([d for d in downloaded if d['size_match'] is True]),
                ('；不一致: %s' % ', '.join(d['prefix'] for d in mism)) if mism else ''))
    if not page:
        add('preview.page', 'pet pack 预览页生成', 'FAIL', '无可用视频，未生成页面')
        return
    add('preview.page', 'pet pack 预览页生成', 'PASS', os.path.relpath(page, PROJECT))
    r = chrome_shot(chrome, 'file:///' + os.path.abspath(page).replace('\\', '/'),
                    os.path.join(SHOTS, 'petpack-preview.png'), (1600, 900), 15000)
    st = img_stats(os.path.join(SHOTS, 'petpack-preview.png')) if r['ok'] else None
    artifacts['preview_screenshot'] = {'shot': r, 'stats': st}
    if not r['ok']:
        add('preview.shot', 'pet pack 预览页截图', 'FAIL', 'size=%s %s' % (r['size'], r['error']))
    elif st and st['std'] < 5:
        add('preview.shot', 'pet pack 预览页截图', 'WARN',
            '截图近乎纯色: size=%s mean=%s std=%s' % (r['size'], st['mean'], st['std']))
    else:
        add('preview.shot', 'pet pack 预览页截图', 'PASS',
            'build/shots/petpack-preview.png size=%s %s' % (r['size'], st))


# ---------------- main ----------------
def main():
    global SHOTS
    ap = argparse.ArgumentParser(description='Screenshot evidence (Chrome + PrintWindow)')
    ap.add_argument('--chrome', default='')
    ap.add_argument('--packs-dir', default=os.path.join(PROJECT, 'plugin', 'packs'))
    ap.add_argument('--fallback-dir', default=os.path.join(PROJECT, 'build', 'anim_test'))
    ap.add_argument('--shots-dir', default=SHOTS_DEFAULT)
    ap.add_argument('--base-url', default=GUI_DEFAULT)
    ap.add_argument('--out', default=os.path.join(PROJECT, 'build', 'verify', 'verify_shots.json'))
    ap.add_argument('--budgets', default='8000,15000,25000')  # 兼容旧参数（当前不使用）
    ap.add_argument('--skip-alpha', action='store_true')
    ap.add_argument('--skip-gallery', action='store_true')
    ap.add_argument('--skip-gui', action='store_true')
    ap.add_argument('--skip-preview', action='store_true')
    ap.add_argument('--strict', action='store_true')
    args = ap.parse_args()

    SHOTS = os.path.abspath(args.shots_dir)
    os.makedirs(SHOTS, exist_ok=True)
    packs_dir = os.path.abspath(args.packs_dir)
    chrome = chrome_path(args.chrome)
    if not chrome:
        add('chrome', 'Chrome 可执行文件存在', 'FAIL', '未找到 Chrome: %s' % CHROME_DEFAULT)
        return write_out(args)
    add('chrome', 'Chrome 可执行文件存在', 'PASS', chrome)

    # ---------- (a) alpha ----------
    if args.skip_alpha:
        add('alpha.skip', 'alpha 测试', 'SKIP', '--skip-alpha')
    else:
        samples = gather_alpha_samples(packs_dir, os.path.abspath(args.fallback_dir))
        if not samples:
            add('alpha.samples', 'alpha 测试素材', 'SKIP', '未找到可用 webm（packs 与 fallback 均缺失）')
        else:
            add('alpha.samples', 'alpha 测试素材', 'PASS',
                '; '.join('%s/%s (%dB)' % (s['prefix'], s['name'], os.path.getsize(s['path'])) for s in samples))
            artifacts['alpha_samples'] = [{'prefix': s['prefix'], 'name': s['name'],
                                           'path': os.path.relpath(s['path'], PROJECT)} for s in samples]
            html_v, html_bg = build_alpha_pages(samples, SHOTS)
            win = (12 * 2 + 320 * len(samples) + 12 * (len(samples) - 1) + 20,
                   12 * 2 + 22 + 180 + 20)
            png_v = os.path.join(SHOTS, 'alpha-test.png')
            png_bg = os.path.join(SHOTS, 'alpha-bg.png')
            r1 = chrome_shot(chrome, 'file:///' + os.path.abspath(html_v).replace('\\', '/'),
                             png_v, win, 8000)
            r2 = chrome_shot(chrome, 'file:///' + os.path.abspath(html_bg).replace('\\', '/'),
                             png_bg, win, 6000)
            artifacts['alpha_screenshots'] = [r1, r2]
            add('alpha.shot.video', 'alpha 截图（视频页）', 'PASS' if r1['ok'] else 'FAIL',
                'size=%s ms=%s %s' % (r1['size'], r1['ms'], r1['error']))
            add('alpha.shot.bg', 'alpha 截图（背景页）', 'PASS' if r2['ok'] else 'FAIL',
                'size=%s ms=%s %s' % (r2['size'], r2['ms'], r2['error']))
            if r1['ok'] and r2['ok']:
                ana = analyze_alpha(png_v, png_bg, len(samples))
                artifacts['alpha_analysis'] = ana
                if 'error' in ana:
                    add('alpha.analysis', 'alpha 像素分析', 'WARN', ana['error'])
                else:
                    changed = [c for c in ana['cells'] if c['diff_ratio'] >= 0.02]
                    trans = [c for c in ana['cells']
                             if c['identical_ratio'] >= 0.30 and c['black_ratio'] <= 0.5]
                    opaque = [c for c in ana['cells']
                              if c['identical_ratio'] < 0.05 or c['black_ratio'] > 0.60]
                    detail = '; '.join('[%d] identical=%.2f black=%.2f checker=%.2f' % (
                        c['index'], c['identical_ratio'], c['black_ratio'],
                        c['checker_gray_ratio']) for c in ana['cells'])
                    if len(changed) < len(ana['cells']):
                        add('alpha.analysis', 'alpha 像素分析', 'FAIL',
                            '视频未渲染（截图与背景图几乎一致）: ' + detail)
                    elif len(trans) == len(ana['cells']):
                        add('alpha.analysis', 'alpha 像素分析（透明）', 'PASS',
                            '棋盘格在视频透明区透出，alpha 正常: ' + detail)
                    elif opaque:
                        add('alpha.analysis', 'alpha 像素分析（透明）', 'FAIL',
                            '视频背景不透明/发黑（alpha 可能丢失）: ' + detail)
                    else:
                        add('alpha.analysis', 'alpha 像素分析（透明）', 'WARN',
                            '透明证据不充分，需人工看图: ' + detail)
                    try:
                        from PIL import Image
                        im = Image.open(png_v)
                        for i, c in enumerate(ana['cells']):
                            x0, y0, x1, y1 = c['rect']
                            crop = im.crop((x0, y0, x1, y1))
                            name = re.sub(r'[^\w.-]+', '_', samples[i]['name'])[:40]
                            cp = os.path.join(SHOTS, 'alpha-crop-%d-%s.png' % (i, name))
                            crop.save(cp)
                            artifacts.setdefault('alpha_crops', []).append(os.path.relpath(cp, PROJECT))
                    except Exception as e:  # noqa: BLE001
                        add('alpha.crops', 'alpha 裁剪图', 'WARN', str(e))

    # ---------- (b) 图鉴页 ----------
    if args.skip_gallery:
        add('gallery.skip', '图鉴页截图', 'SKIP', '--skip-gallery')
    else:
        gallery_html = os.path.join(PROJECT, 'plugin', 'visual', 'index.html')
        if not os.path.isfile(gallery_html):
            add('gallery.exists', 'plugin/visual/index.html 存在', 'FAIL' if args.strict else 'SKIP',
                '文件不存在: plugin/visual/index.html')
        else:
            add('gallery.exists', 'plugin/visual/index.html 存在', 'PASS', '')
            png = os.path.join(SHOTS, 'gallery.png')
            r = chrome_shot(chrome, 'file:///' + os.path.abspath(gallery_html).replace('\\', '/'),
                            png, (1600, 1200), 12000)
            st = img_stats(png) if r['ok'] else None
            artifacts['gallery'] = {'screenshot': r, 'stats': st}
            if not r['ok']:
                add('gallery.shot', '图鉴页截图', 'FAIL', 'size=%s ms=%s %s' % (r['size'], r['ms'], r['error']))
            elif st and st['std'] < 3:
                add('gallery.shot', '图鉴页截图', 'WARN',
                    '截图近乎纯色（可能白屏）: size=%s mean=%s std=%s' % (r['size'], st['mean'], st['std']))
            else:
                add('gallery.shot', '图鉴页截图', 'PASS',
                    'build/shots/gallery.png size=%s stats=%s' % (r['size'], st))

    # ---------- (c) 真实窗口 ----------
    if args.skip_gui:
        add('dsh.skip', '真实窗口截图', 'SKIP', '--skip-gui')
    else:
        run_gui_evidence(chrome, args.base_url)

    # ---------- (d) pet pack 预览页 ----------
    if args.skip_preview:
        add('preview.skip', 'pet pack 预览页', 'SKIP', '--skip-preview')
    else:
        run_preview(chrome, args.base_url, packs_dir, args)

    return write_out(args)


def write_out(args):
    counts = {}
    for c in checks:
        counts[c['status']] = counts.get(c['status'], 0) + 1
    report = {
        'tool': 'tools/verify_shots.py',
        'generated_at': __import__('datetime').datetime.now().isoformat(timespec='seconds'),
        'shots_dir': SHOTS,
        'base_url': args.base_url,
        'summary': counts,
        'checks': checks,
        'artifacts': artifacts,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print('')
    print('=' * 86)
    print('verify_shots.py  |  shots: %s' % SHOTS)
    print('=' * 86)
    for c in checks:
        print('[%s] %-42s %s' % (c['status'], c['name'], c['detail']))
    print('-' * 86)
    print('结果: %s' % ','.join('%s=%d' % (k, counts.get(k, 0)) for k in ('PASS', 'FAIL', 'WARN', 'SKIP')))
    print('JSON: %s' % args.out)
    print('=' * 86)
    return 1 if any(c['status'] == 'FAIL' for c in checks) else 0


if __name__ == '__main__':
    sys.exit(main())
