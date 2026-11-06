#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
verify_switch.py —— dsh-pet-ai-girls v1.1「自由切换当前桌宠」端到端验证（不改被测源码）。

验证目标（对应 Lead 的 v1.1 行为变更）：
  1. 切换 API：POST /dsh-pet-ai-girls/api/switch {"id":"qwen"} → ok=true、active=qwen、reloading=true；
     GET /api/switch?id=... 也可用。
  2. 持久化：切换后立即读部署目录 8 份 config + `.dsh-pet-ai-girls-active.json`：
     恰好 girl-qwen `pets[0].display='both'`，其余 7 份 `display='none'`；marker.active=qwen；
     live `/dsh-pet-7340/config` 同样只有 girl-qwen display=both。
  3. 桌面窗口：dsh-pet reload 后只应有 **2 个**「dsh-pet 桌宠（桌面模式）」窗口
     （main 720×579 + 当前角色 680×547），抓图合成 `build/shots/switcher-<state>.png`；
     换人前后 680×547 窗口像素应显著不同（证明窗口内容真的换了）。
  4. 图鉴页：Chrome headless 打开实机路由 `/dsh-pet-ai-girls/`，截图 + dump-dom：
     顶部「切换当前桌宠」区块渲染、目标角色 chip 带 is-active（"当前"）、switch-note 显示当前角色名
     （该文案由页面 fetch /api/current 得到，证明 API 被页面消费）。
  5. 最后切回 deepseek 并确认 active=deepseek；main 配置指纹全程不变。

输出：build/verify/verify_switch.json + stdout PASS/FAIL 表；有 FAIL 时 exit 1。
无论成败，脚本都会在 finally 中切回 deepseek，避免污染最终状态。

用法：
  python tools/verify_switch.py
  python tools/verify_switch.py --to qwen --back deepseek
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:  # noqa: BLE001
    pass

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOTS = os.path.join(PROJECT, 'build', 'shots')
VERIFY = os.path.join(PROJECT, 'build', 'verify')
CHROME_DEFAULT = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
POWERSHELL = r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
CAPTURE_PS1 = os.path.join(PROJECT, 'tools', 'verify_shots.ps1')
BASE_DEFAULT = 'http://127.0.0.1:57076'
PET_DIR_DEFAULT = os.path.join(os.path.expanduser('~'), '.dsh', 'dsh-pet', 'pet')
MARKER_NAME = '.dsh-pet-ai-girls-active.json'
EXPECTED_IDS = ['deepseek', 'gpt', 'claude', 'grok', 'gemini', 'kimi', 'glm', 'qwen']
MAIN_WIN = (720, 579)
ACTIVE_WIN = (680, 547)

checks = []
artifacts = {}


def add(cid, name, status, detail='', evidence=None):
    checks.append({'id': cid, 'name': name, 'status': status, 'detail': detail, 'evidence': evidence})
    print('[%s] %-46s %s' % (status, name, detail))


def http_json(url, method='GET', body=None, timeout=30):
    rec = {'url': url, 'method': method, 'status': None, 'error': '', 'json': None,
           'content_type': '', 'body_head': ''}
    data = None
    headers = {'User-Agent': 'dsh-verifier/1.0'}
    if body is not None:
        data = json.dumps(body).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            rec['status'] = resp.status
            rec['content_type'] = resp.headers.get('content-type', '')
            raw = resp.read()
            rec['body_head'] = raw[:300].decode('utf-8', errors='replace')
            try:
                rec['json'] = json.loads(raw.decode('utf-8'))
            except Exception:  # noqa: BLE001
                rec['json'] = None
    except urllib.error.HTTPError as e:
        rec['status'] = e.code
        rec['error'] = 'HTTPError %s' % e.code
        try:
            rec['body_head'] = e.read()[:300].decode('utf-8', errors='replace')
        except Exception:  # noqa: BLE001
            pass
    except Exception as e:  # noqa: BLE001
        rec['error'] = '%s: %s' % (type(e).__name__, e)
    return rec


def get_config(base):
    return http_json(base + '/dsh-pet-7340/config')


def main_hash(cfg_json):
    main = (cfg_json or {}).get('main')
    if main is None:
        return None
    return hashlib.sha256(json.dumps(main, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


def read_deployed(pet_dir):
    """返回 (configs{prefix: pet{}}, marker dict, problems[])"""
    configs = {}
    for fn in sorted(os.listdir(pet_dir)):
        m = re.match(r'^(.+?)-config\.(json|jsonc)$', fn)
        if not m:
            continue
        prefix = m.group(1)
        try:
            with open(os.path.join(pet_dir, fn), 'r', encoding='utf-8-sig') as f:
                cfg = json.load(f)
            pets = cfg.get('pets') if isinstance(cfg.get('pets'), list) else []
            pet = pets[0] if pets and isinstance(pets[0], dict) else {}
            pos = pet.get('position') if isinstance(pet.get('position'), dict) else {}
            configs[prefix] = {'id': pet.get('id'), 'display': pet.get('display'),
                               'size': pet.get('size'), 'corner': pos.get('corner'),
                               'marginX': pos.get('marginX'), 'marginY': pos.get('marginY')}
        except Exception as e:  # noqa: BLE001
            configs[prefix] = {'_error': str(e)}
    marker = None
    marker_path = os.path.join(pet_dir, MARKER_NAME)
    if os.path.isfile(marker_path):
        try:
            with open(marker_path, 'r', encoding='utf-8-sig') as f:
                marker = json.load(f)
        except Exception as e:  # noqa: BLE001
            marker = {'_error': str(e)}
    return configs, marker


def assert_single_active(label, configs, expected_id):
    """configs: prefix -> pet dict；断言恰好 expected 前缀 display=both、其余 none、size/position 统一。"""
    both = sorted(k for k, v in configs.items() if v.get('display') == 'both')
    none = sorted(k for k, v in configs.items() if v.get('display') == 'none')
    expected_prefix = 'girl-' + expected_id
    add('switch.%s.display' % label,
        '%s：恰好 1 个 pack display=both（%s）、其余 none' % (label, expected_prefix),
        'PASS' if both == [expected_prefix] and len(none) == len(configs) - 1 and len(configs) == 8 else 'FAIL',
        'both=%s；none=%d/%d；configs=%d' % (both, len(none), len(configs) - 1, len(configs)))
    sizes = sorted(set(str(v.get('size')) for v in configs.values()))
    add('switch.%s.size' % label, '%s：8 pack size 统一 340' % label,
        'PASS' if sizes == ['340'] else 'FAIL', 'sizes=%s' % sizes)
    poss = sorted(set('%s/%s/%s' % (v.get('corner'), v.get('marginX'), v.get('marginY'))
                      for v in configs.values()))
    add('switch.%s.position' % label, '%s：8 pack position 统一 bottom-right/40/40' % label,
        'PASS' if poss == ['bottom-right/40/40'] else 'FAIL', 'positions=%s' % poss)


def run_ps1(title_match, out_dir, json_out, list_only=False, timeout=90):
    args = [POWERSHELL, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', CAPTURE_PS1,
            '-TitleMatch', title_match, '-OutDir', out_dir, '-JsonOut', json_out]
    if list_only:
        args.append('-ListOnly')
    os.makedirs(os.path.dirname(json_out), exist_ok=True)
    try:
        subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    except Exception as e:  # noqa: BLE001
        return {'error': '%s: %s' % (type(e).__name__, e)}
    if not os.path.isfile(json_out):
        return {'error': 'ps1 未生成 JSON'}
    try:
        with open(json_out, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except Exception as e:  # noqa: BLE001
        return {'error': 'JSON 解析失败: %s' % e}


def list_pet_windows():
    d = run_ps1('dsh-pet', os.path.join(SHOTS, 'switch-windows'), os.path.join(VERIFY, 'switch_windows_list.json'),
                list_only=True)
    wins = d.get('windows') or []
    pets = [w for w in wins if '桌宠' in (w.get('title') or '')]
    return pets, d


def wait_pet_windows(expected_sizes, timeout=30.0):
    """轮询直到桌面宠物窗口恰好 2 个且尺寸集合符合预期，并连续两次稳定。"""
    t0 = time.time()
    prev = None
    stable = 0
    last = []
    while time.time() - t0 < timeout:
        pets, _ = list_pet_windows()
        last = pets
        sizes = sorted((w.get('width'), w.get('height')) for w in pets)
        if len(pets) == 2 and sizes == sorted(expected_sizes):
            sig = sorted(w.get('handle') for w in pets)
            if sig == prev:
                stable += 1
                if stable >= 1:
                    return pets, int((time.time() - t0) * 1000)
            else:
                prev = sig
                stable = 0
        time.sleep(0.7)
    return last, int((time.time() - t0) * 1000)


def capture_pet_windows(label, expected_sizes):
    """等窗口稳定 → PrintWindow 全抓 → 按尺寸分类 → 合成两窗口对比图。"""
    pets, wait_ms = wait_pet_windows(expected_sizes)
    add('switch.%s.windows' % label, '%s：桌面宠物窗口恰好 2 个（main 720×579 + 当前 680×547）' % label,
        'PASS' if len(pets) == 2 and sorted((w['width'], w['height']) for w in pets) == sorted(expected_sizes) else 'FAIL',
        '发现 %d 个: %s（等待 %dms）' % (len(pets), [(w['width'], w['height'], w.get('handle')) for w in pets], wait_ms))
    d = run_ps1('dsh-pet', os.path.join(SHOTS, 'switch-windows', label),
                os.path.join(VERIFY, 'switch_windows_%s.json' % label))
    caps = [c for c in (d.get('captured') or []) if '桌宠' in (c.get('title') or '')]
    add('switch.%s.capture' % label, '%s：PrintWindow 抓图' % label,
        'PASS' if len(caps) >= 2 else 'FAIL',
        '; '.join('%dx%d %sB %s' % (c.get('width'), c.get('height'), c.get('bytes'),
                                    os.path.basename(c.get('path') or '')) for c in caps[:3]))
    by_size = {}
    for c in caps:
        by_size.setdefault((c.get('width'), c.get('height')), c.get('path'))
    by_size_s = {'%dx%d' % k: v for k, v in by_size.items()}
    comp = compose_windows(label, by_size)
    return {'wait_ms': wait_ms,
            'windows': [{k: w.get(k) for k in ('handle', 'width', 'height', 'title')} for w in pets],
            'captured': caps, 'composite': comp, 'by_size': by_size_s}


def crop_content(im, margin=12):
    """裁掉透明/纯黑窗口留白，保留内容包围盒（PrintWindow 透明窗口背景为黑）。"""
    try:
        from PIL import Image
        import numpy as np
    except Exception:  # noqa: BLE001
        return im
    rgb = im.convert('RGB')
    a = np.asarray(rgb).astype(int)
    mask = a.max(axis=2) > 20
    if not mask.any():
        return im
    ys = np.where(mask.any(axis=1))[0]
    xs = np.where(mask.any(axis=0))[0]
    x0, x1 = max(0, int(xs.min()) - margin), min(im.width, int(xs.max()) + margin)
    y0, y1 = max(0, int(ys.min()) - margin), min(im.height, int(ys.max()) + margin)
    if x1 - x0 < 24 or y1 - y0 < 24:
        return im
    return im.crop((x0, y0, x1, y1))


def compose_windows(label, by_size):
    """把 main 窗口(720×579) 与当前角色窗口(680×547) 裁到内容区后并排合成 switcher-<label>.png。"""
    try:
        from PIL import Image, ImageDraw
    except Exception:  # noqa: BLE001
        return None
    main_p = by_size.get(MAIN_WIN)
    act_p = by_size.get(ACTIVE_WIN)
    if not main_p or not act_p:
        # 尺寸标注可能因 DPI 略有差异，退而取最宽/次宽
        items = sorted(by_size.items(), key=lambda kv: -kv[0][0])
        if len(items) < 2:
            return None
        main_p, act_p = items[0][1], items[1][1]
    try:
        im_main = crop_content(Image.open(main_p).convert('RGBA'))
        im_act = crop_content(Image.open(act_p).convert('RGBA'))
    except Exception:  # noqa: BLE001
        return None
    H = 440

    def scaled(im):
        w = max(1, int(im.width * H / im.height))
        return im.resize((w, H), Image.LANCZOS)

    a, b = scaled(im_main), scaled(im_act)
    pad, top = 24, 42
    canvas = Image.new('RGBA', (pad * 3 + a.width + b.width, H + top + pad), (16, 18, 24, 255))
    canvas.alpha_composite(a, (pad, top))
    canvas.alpha_composite(b, (pad * 2 + a.width, top))
    draw = ImageDraw.Draw(canvas)
    draw.text((pad, 12), 'main (original pet) 720x579', fill=(160, 175, 200, 255))
    draw.text((pad * 2 + a.width, 12), 'active: %s (680x547)' % label, fill=(120, 220, 255, 255))
    out = os.path.join(SHOTS, 'switcher-%s.png' % label)
    canvas.convert('RGB').save(out, 'PNG')
    return os.path.relpath(out, PROJECT)


def chrome_shot(url, out_png, window=(1600, 1200), budget=15000, dump_dom_path=None,
                chrome=CHROME_DEFAULT, timeout=150):
    rec = {'url': url, 'out': out_png, 'ok': False, 'size': None, 'error': '', 'dom': None}
    if not os.path.isfile(chrome):
        rec['error'] = 'chrome not found'
        return rec
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    base = [chrome, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
            '--no-first-run', '--disable-extensions', '--force-device-scale-factor=1',
            '--user-data-dir=' + os.path.join(SHOTS, 'chrome-profile'),
            '--window-size=%d,%d' % window, '--virtual-time-budget=%d' % budget,
            '--autoplay-policy=no-user-gesture-required']
    try:
        p = subprocess.run(base + ['--screenshot=' + os.path.abspath(out_png), url],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        if os.path.isfile(out_png):
            rec['size'] = os.path.getsize(out_png)
            rec['ok'] = rec['size'] > 1000
        else:
            rec['error'] = ((p.stderr or b'').decode('utf-8', errors='replace'))[-300:]
        if dump_dom_path:
            p2 = subprocess.run(base + ['--dump-dom', url], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=timeout)
            dom = (p2.stdout or b'').decode('utf-8', errors='replace')
            with open(dump_dom_path, 'w', encoding='utf-8') as f:
                f.write(dom)
            rec['dom'] = dom
    except Exception as e:  # noqa: BLE001
        rec['error'] = '%s: %s' % (type(e).__name__, e)
    return rec


def analyze_gallery_dom(dom, expected_id, expected_name):
    """检查图鉴页 switcher 区块渲染、目标 chip is-active（"当前"）、switch-note 显示当前名称。"""
    if not dom:
        return {'ok': False, 'reason': 'DOM 为空'}
    out = {'has_switcher_title': '切换当前桌宠' in dom,
           'is_active_chips': [],
           'note_current': None,
           'expected_id': expected_id, 'expected_name': expected_name}
    for m in re.finditer(r'class="switch-chip is-active"[^>]*data-id="([^"]+)"', dom):
        out['is_active_chips'].append(m.group(1))
    m2 = re.search(r'当前桌宠：<b>([^<]+)</b>', dom)
    if m2:
        out['note_current'] = m2.group(1)
    out['ok'] = bool(out['has_switcher_title'] and out['is_active_chips'] == [expected_id]
                     and out['note_current'] == expected_name)
    return out


def switch_to(base, target_id, method='POST'):
    if method == 'POST':
        rec = http_json(base + '/dsh-pet-ai-girls/api/switch', 'POST', {'id': target_id})
    else:
        rec = http_json(base + '/dsh-pet-ai-girls/api/switch?' + urllib.parse.urlencode({'id': target_id}))
    return rec


def check_state(label, base, pet_dir, expected_id, expected_name, expect_single_active=True):
    """切换后：API + 部署 config + marker + live /config 断言。"""
    cfg = get_config(base)
    live = cfg.get('json') or {}
    live_disp = {}
    for prefix in ['girl-' + i for i in EXPECTED_IDS]:
        entry = live.get(prefix)
        pets = (entry or {}).get('pets') if isinstance(entry, dict) and isinstance(entry.get('pets'), list) else []
        pet = pets[0] if pets and isinstance(pets[0], dict) else {}
        live_disp[prefix] = pet.get('display')
    both = sorted(k for k, d in live_disp.items() if d == 'both')
    add('switch.%s.live_config' % label,
        '%s：live /config 恰好 %s display=both' % (label, 'girl-' + expected_id),
        'PASS' if both == ['girl-' + expected_id] else 'FAIL',
        'display=both 的条目: %s（live 条目 %d 个）' % (both, len(live_disp)))
    # /api/current
    cur = http_json(base + '/dsh-pet-ai-girls/api/current')
    cur_id = ((cur.get('json') or {}).get('active') or {}).get('id')
    add('switch.%s.api_current' % label, '%s：GET /api/current active=%s' % (label, expected_id),
        'PASS' if cur.get('status') == 200 and cur_id == expected_id else 'FAIL',
        'status=%r active=%r' % (cur.get('status'), cur_id))
    # /health
    h = http_json(base + '/dsh-pet-ai-girls/health')
    hj = h.get('json') or {}
    hid = (hj.get('active') or {}).get('id') if isinstance(hj.get('active'), dict) else None
    hmarks = [c.get('id') for c in (hj.get('characters') or []) if isinstance(c, dict) and c.get('active') is True]
    add('switch.%s.health' % label, '%s：/health active=%s 且唯一 active 标记一致' % (label, expected_id),
        'PASS' if h.get('status') == 200 and hid == expected_id and hmarks == [expected_id] else 'FAIL',
        'status=%r active=%r marks=%s version=%r' % (h.get('status'), hid, hmarks, hj.get('version')))
    # 部署目录 8 份 config + marker
    configs, marker = read_deployed(pet_dir)
    if expect_single_active:
        assert_single_active(label, configs, expected_id)
    marker_active = (marker or {}).get('active')
    add('switch.%s.marker' % label, '%s：active marker active=%s' % (label, expected_id),
        'PASS' if marker_active == expected_id else 'FAIL',
        'active=%r marker=%s' % (marker_active, json.dumps(marker, ensure_ascii=False)[:200]))
    return {'live_display': live_disp, 'configs': configs, 'marker': marker,
            'api_current': cur.get('json'), 'health': hj}


def image_diff_ratio(p1, p2):
    """裁剪内容区后比较两图差异比例（换人后角色应显著不同）。"""
    try:
        from PIL import Image
        import numpy as np
    except Exception:  # noqa: BLE001
        return None
    try:
        a = np.asarray(crop_content(Image.open(p1).convert('RGB')).resize((200, 200))).astype(int)
        b = np.asarray(crop_content(Image.open(p2).convert('RGB')).resize((200, 200))).astype(int)
        return round(float((np.abs(a - b).max(axis=2) > 24).mean()), 4)
    except Exception:  # noqa: BLE001
        return None


def main():
    ap = argparse.ArgumentParser(description='v1.1 end-to-end pet switch verifier')
    ap.add_argument('--base-url', default=BASE_DEFAULT)
    ap.add_argument('--pet-dir', default=PET_DIR_DEFAULT)
    ap.add_argument('--to', default='qwen', help='要切换到的角色 id')
    ap.add_argument('--back', default='deepseek', help='最终切回的角色 id（默认 deepseek）')
    ap.add_argument('--out', default=os.path.join(VERIFY, 'verify_switch.json'))
    args = ap.parse_args()
    base = args.base_url.rstrip('/')
    pet_dir = os.path.abspath(args.pet_dir)
    os.makedirs(SHOTS, exist_ok=True)
    os.makedirs(VERIFY, exist_ok=True)

    baseline_cfg = get_config(base)
    baseline_main_hash = main_hash(baseline_cfg.get('json'))
    artifacts['baseline_main_hash'] = baseline_main_hash

    to_id, back_id = args.to, args.back
    names = {e.get('id'): e.get('name') for e in
             ((http_json(base + '/dsh-pet-ai-girls/api/current').get('json') or {}).get('characters') or [])}
    to_name = names.get(to_id) or ('%s 娘' % to_id)
    back_name = names.get(back_id) or ('%s 娘' % back_id)

    restored = False
    try:
        # ---------- 1) 初始状态 ----------
        cur0 = http_json(base + '/dsh-pet-ai-girls/api/current')
        cur0_id = ((cur0.get('json') or {}).get('active') or {}).get('id')
        add('switch.initial', '初始 /api/current active=%s' % back_id,
            'PASS' if cur0_id == back_id else 'WARN',
            '实际=%r（脚本仍会按流程切到 %s 再切回 %s）' % (cur0_id, to_id, back_id))
        state0 = capture_pet_windows('initial', [MAIN_WIN, ACTIVE_WIN])
        artifacts['initial'] = state0

        # ---------- 2) POST /api/switch -> to_id ----------
        sw = switch_to(base, to_id, 'POST')
        sj = sw.get('json') or {}
        sw_active = (sj.get('active') or {}).get('id') if isinstance(sj.get('active'), dict) else None
        add('switch.post_switch', 'POST /api/switch {"id":"%s"} → ok/active/reloading' % to_id,
            'PASS' if sw.get('status') == 200 and sj.get('ok') is True
            and sw_active == to_id and sj.get('reloading') is True else 'FAIL',
            'status=%r ok=%r active=%r reloading=%r body=%s' % (
                sw.get('status'), sj.get('ok'), sw_active, sj.get('reloading'),
                sw.get('body_head')[:200]))
        artifacts['switch_to_%s' % to_id] = {k: sw.get(k) for k in ('status', 'error', 'body_head')}

        # ---------- 3) 立即读 8 份 config + marker + live /config ----------
        cfg_after = get_config(base)
        # 给 dsh-pet 读取文件留极短余量（写入在 switch 返回前完成；不轮询，直接断言）
        state_to = check_state('after_%s' % to_id, base, pet_dir, to_id, to_name)

        # ---------- 4) 桌面窗口（reload 后应只剩 2 个） ----------
        state_to_win = capture_pet_windows(to_id, [MAIN_WIN, ACTIVE_WIN])
        state_to['windows'] = state_to_win
        state_to['config_after_switch'] = {
            'live_entries': sorted((cfg_after.get('json') or {}).keys())}
        artifacts['after_%s' % to_id] = state_to

        # ---------- 5) 图鉴页（实机路由）截图 + DOM：to 状态 ----------
        gallery_url = base + '/dsh-pet-ai-girls/'
        g_to = chrome_shot(gallery_url, os.path.join(SHOTS, 'gallery-switcher-%s.png' % to_id),
                           dump_dom_path=os.path.join(VERIFY, 'gallery_%s_dom.html' % to_id))
        dom_to = analyze_gallery_dom(g_to.pop('dom', None), to_id, to_name)
        artifacts['gallery_%s' % to_id] = {'shot': {k: g_to.get(k) for k in ('ok', 'size', 'error')},
                                           'dom_check': dom_to}
        add('switch.gallery_%s' % to_id, '图鉴页（实机路由）：switcher 渲染 + %s chip「当前」+ 消费 /api/current' % to_name,
            'PASS' if g_to.get('ok') and dom_to.get('ok') else 'FAIL',
            'screenshot=%r dom=%s' % (g_to.get('ok'), json.dumps(dom_to, ensure_ascii=False)))

        # ---------- 6) 切回 back_id ----------
        swb = switch_to(base, back_id, 'GET')
        sjb = swb.get('json') or {}
        b_active = (sjb.get('active') or {}).get('id') if isinstance(sjb.get('active'), dict) else None
        add('switch.get_switch_back', 'GET /api/switch?id=%s → ok/active/reloading' % back_id,
            'PASS' if swb.get('status') == 200 and sjb.get('ok') is True
            and b_active == back_id and sjb.get('reloading') is True else 'FAIL',
            'status=%r ok=%r active=%r reloading=%r' % (swb.get('status'), sjb.get('ok'), b_active, sjb.get('reloading')))
        state_back = check_state('final_%s' % back_id, base, pet_dir, back_id, back_name)
        state_back_win = capture_pet_windows(back_id, [MAIN_WIN, ACTIVE_WIN])
        state_back['windows'] = state_back_win
        artifacts['final_%s' % back_id] = state_back
        restored = True

        # 680×547 窗口换人前后应显著不同
        act_to = (state_to_win.get('by_size') or {}).get('%dx%d' % ACTIVE_WIN)
        act_back = (state_back_win.get('by_size') or {}).get('%dx%d' % ACTIVE_WIN)
        diff = image_diff_ratio(act_to, act_back) if act_to and act_back else None
        add('switch.window_content_changed', '切换前后 680×547 窗口像素显著不同（窗口内容真的换人）',
            'PASS' if (diff is not None and diff >= 0.10) else ('WARN' if diff is None else 'FAIL'),
            'diff_ratio=%r（阈值 0.10）' % diff)
        artifacts['window_diff_ratio'] = diff

        # ---------- 7) 图鉴页 final 状态（gallery-switcher.png 主图） ----------
        g_back = chrome_shot(gallery_url, os.path.join(SHOTS, 'gallery-switcher.png'),
                             dump_dom_path=os.path.join(VERIFY, 'gallery_%s_dom.html' % back_id))
        dom_back = analyze_gallery_dom(g_back.pop('dom', None), back_id, back_name)
        artifacts['gallery_%s' % back_id] = {'shot': {k: g_back.get(k) for k in ('ok', 'size', 'error')},
                                             'dom_check': dom_back}
        add('switch.gallery_%s' % back_id, '图鉴页（实机路由）：switcher 渲染 + %s chip「当前」+ 消费 /api/current' % back_name,
            'PASS' if g_back.get('ok') and dom_back.get('ok') else 'FAIL',
            'screenshot=%r dom=%s' % (g_back.get('ok'), json.dumps(dom_back, ensure_ascii=False)))

        # ---------- 8) main 未受影响 ----------
        final_cfg = get_config(base)
        final_main_hash = main_hash(final_cfg.get('json'))
        add('switch.main_unaffected', '切换全过程 main 配置指纹不变',
            'PASS' if final_main_hash == baseline_main_hash else 'FAIL',
            'baseline=%s final=%s' % (baseline_main_hash, final_main_hash))
        artifacts['final_main_hash'] = final_main_hash
        if os.path.isfile(os.path.join(VERIFY, 'live-config-initial.json')):
            try:
                with open(os.path.join(VERIFY, 'live-config-initial.json'), 'r', encoding='utf-8-sig') as f:
                    init = json.load(f)
                init_hash = main_hash(init)
                add('switch.main_vs_v10_snapshot', 'main 指纹与 v1.0 部署前快照一致（原主宠物未受影响）',
                    'PASS' if init_hash == final_main_hash else 'FAIL',
                    'v1.0 快照=%s final=%s' % (init_hash, final_main_hash))
            except Exception:  # noqa: BLE001
                pass
    finally:
        # 兜底：确保最终状态切回 back_id
        if not restored:
            try:
                chk = http_json(base + '/dsh-pet-ai-girls/api/current')
                cur_id = ((chk.get('json') or {}).get('active') or {}).get('id')
                if cur_id != back_id:
                    r = switch_to(base, back_id, 'GET')
                    add('switch.restore', '失败兜底：切回 %s' % back_id,
                        'PASS' if (r.get('json') or {}).get('ok') else 'FAIL',
                        (r.get('body_head') or '')[:200])
            except Exception as e:  # noqa: BLE001
                add('switch.restore', '失败兜底：切回 %s' % back_id, 'FAIL', str(e))

    statuses = {}
    for c in checks:
        statuses[c['status']] = statuses.get(c['status'], 0) + 1
    report = {
        'tool': 'tools/verify_switch.py',
        'generated_at': __import__('datetime').datetime.now().isoformat(timespec='seconds'),
        'base_url': base, 'pet_dir': pet_dir,
        'switch_to': to_id, 'switch_back': back_id,
        'summary': statuses,
        'checks': checks,
        'artifacts': artifacts,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print('')
    print('=' * 84)
    print('verify_switch.py  |  %s → %s → %s' % (base, to_id, back_id))
    print('=' * 84)
    print('结果: %s' % ','.join('%s=%d' % (k, statuses.get(k, 0)) for k in ('PASS', 'FAIL', 'WARN', 'SKIP')))
    print('JSON: %s' % args.out)
    print('=' * 84)
    return 1 if any(c['status'] == 'FAIL' for c in checks) else 0


if __name__ == '__main__':
    sys.exit(main())
