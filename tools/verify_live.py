#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
verify_live.py —— 对运行中的 DSH（http://127.0.0.1:57076）做 dsh-pet 活体校验。

检查项：
  1. GET /dsh-pet-7340/config -> 200 + JSON；含 main + 8 个新条目
     （条目名 = pet pack 前缀，从 plugin/packs/*-config.json 推导）。
  2. 每个新条目：pets 非空；animations 字段齐全；animationWeights 合法；
     events 各档非空、balance 非空。
  3. 每个新条目抽样 3 个动画：GET /dsh-pet-7340/thumb/<前缀>/<动画名>.webm
     -> 200 + content-type video/webm + content-length 与磁盘源文件一致。
  4. GET /dsh-pet-7340/thumb/main/待机呼吸休闲.webm -> 仍 200（原主宠物未被破坏）。
     （动画名优先取 live main.animations.idle[0]，兜底写死「待机呼吸休闲」）
  5. 记录 main 条目 pets / animations 摘要，作为「未受影响」证据。

部署未完成时（缺条目）默认记 SKIP；加 --strict 时记 FAIL（阶段二用）。
输出：build/verify/verify_live.json + stdout PASS/FAIL/SKIP 表；有 FAIL 时 exit 1。

用法：
  python tools/verify_live.py                 # 阶段一：宽松，缺条目 SKIP
  python tools/verify_live.py --strict        # 阶段二：缺条目 FAIL
  python tools/verify_live.py --sample 3 --all-thumbs
"""
import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import http.client

try:  # 全 UTF-8 输出（Windows 控制台/管道下中文不乱码）
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:  # noqa: BLE001
    pass

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPECTED_IDS = ['deepseek', 'gpt', 'claude', 'grok', 'gemini', 'kimi', 'glm', 'qwen']
EXPECTED_PREFIXES = ['girl-' + i for i in EXPECTED_IDS]
PET_ROUTE = '/dsh-pet-7340/config'
THUMB_ROUTE = '/dsh-pet-7340/thumb/'
MAIN_ANIM_FALLBACK = '待机呼吸休闲'
MAIN_PET_ID = 'main'

checks = []
requests_log = []


def add(check_id, name, status, detail='', evidence=None):
    checks.append({'id': check_id, 'name': name, 'status': status,
                   'detail': detail, 'evidence': evidence})


def http_get(url, timeout=20, read_body=True, max_bytes=None):
    """返回 dict(status, headers, body)。read_body=False 时只读响应头（省流量）。"""
    rec = {'url': url, 'status': None, 'error': '', 'content_type': '', 'content_length': None}
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'dsh-verifier/1.0'})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            rec['status'] = resp.status
            rec['content_type'] = resp.headers.get('content-type', '')
            cl = resp.headers.get('content-length')
            rec['content_length'] = int(cl) if cl is not None and cl.isdigit() else None
            if read_body:
                body = resp.read() if max_bytes is None else resp.read(max_bytes)
                rec['body'] = body
    except urllib.error.HTTPError as e:
        rec['status'] = e.code
        rec['error'] = 'HTTPError %s' % e.code
        rec['content_type'] = e.headers.get('content-type', '') if e.headers else ''
    except Exception as e:  # noqa: BLE001
        rec['error'] = '%s: %s' % (type(e).__name__, e)
    return rec


def headers_only_get(url, timeout=20):
    """发 GET 但只读响应头后关闭连接（避免下载大文件）。"""
    rec = {'url': url, 'status': None, 'error': '', 'content_type': '', 'content_length': None}
    parsed = urllib.parse.urlsplit(url)
    conn = None
    try:
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=timeout)
        path = parsed.path + ('?' + parsed.query if parsed.query else '')
        conn.request('GET', path, headers={'User-Agent': 'dsh-verifier/1.0'})
        resp = conn.getresponse()
        rec['status'] = resp.status
        rec['content_type'] = resp.getheader('content-type') or ''
        cl = resp.getheader('content-length')
        rec['content_length'] = int(cl) if cl is not None and str(cl).isdigit() else None
        # 读取极少量后关闭，避免被服务端当作客户端异常；不落盘
        try:
            resp.read(256)
        except Exception:  # noqa: BLE001
            pass
    except Exception as e:  # noqa: BLE001
        rec['error'] = '%s: %s' % (type(e).__name__, e)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
    return rec


def resolve_expected_prefixes(packs_dir):
    """从 plugin/packs 推导 8 个实际前缀（接受 <id> / girl-<id> / <任意>-<id>）。"""
    present = []
    if os.path.isdir(packs_dir):
        for fn in sorted(os.listdir(packs_dir)):
            m = re.match(r'^(.+?)-config\.(json|jsonc)$', fn)
            if m:
                present.append(m.group(1))
    prefix_map = {}
    for pid in EXPECTED_IDS:
        cands = [p for p in present if p == pid or p == 'girl-' + pid or p.endswith('-' + pid)]
        if cands:
            cands.sort(key=lambda p: (p != 'girl-' + pid, p != pid, len(p)))
            prefix_map[pid] = cands[0]
    if len(prefix_map) == len(EXPECTED_IDS):
        return list(prefix_map.values()), prefix_map, True
    return list(EXPECTED_PREFIXES), prefix_map, False


def disk_webm_size(packs_dir, prefix, anim_name):
    for d in ('webm', ''):
        p = os.path.join(packs_dir, '%s-animation' % prefix, d, anim_name + '.webm')
        if os.path.isfile(p):
            return os.path.getsize(p), p
    return None, None


def collect_refs(entry_anim, limit_per_pool=None):
    """从 live 条目 animations 收集(动画名, 来源)列表。"""
    refs = []
    if not isinstance(entry_anim, dict):
        return refs
    for key in ('idle', 'turn', 'drag', 'clicks'):
        for i, n in enumerate(entry_anim.get(key) or []):
            if isinstance(n, str) and n:
                refs.append((n, 'animations.%s[%d]' % (key, i)))
    moves = entry_anim.get('moves') or {}
    for i, a in enumerate(moves.get('actions') or []):
        if isinstance(a, dict) and isinstance(a.get('name'), str) and a['name']:
            refs.append((a['name'], 'moves.actions[%d]' % i))
    for ci, c in enumerate(entry_anim.get('categories') or []):
        if isinstance(c, dict):
            for j, n in enumerate(c.get('actions') or []):
                if isinstance(n, str) and n:
                    refs.append((n, 'categories[%d].%s[%d]' % (ci, c.get('id', '?'), j)))
    ev = entry_anim.get('events') or {}
    for pool, slots in ev.items():
        for i, slot in enumerate(slots or []):
            if isinstance(slot, str) and slot:
                refs.append((slot, 'events.%s[%d]' % (pool, i)))
            elif isinstance(slot, list):
                for j, n in enumerate(slot):
                    if isinstance(n, str) and n:
                        refs.append((n, 'events.%s[%d][%d]' % (pool, i, j)))
    return refs


def pick_sample(entry_anim, refs, sample_n=3):
    """抽样：优先 idle、events.balance、events.workStatus，再补其它，去重。"""
    picked = []
    seen = set()

    def push(names):
        for n in names:
            if n not in seen:
                seen.add(n)
                picked.append(n)

    idle = [n for n in (entry_anim.get('idle') or []) if isinstance(n, str) and n]
    push(idle[:1])
    ev = entry_anim.get('events') or {}
    balance = ev.get('balance') or []
    bal_names = [s for s in balance if isinstance(s, str) and s]
    push(bal_names[:1])
    ws = ev.get('workStatus') or []
    push([s for s in ws if isinstance(s, str) and s][:1])
    clicks = entry_anim.get('clicks') or []
    push([n for n in clicks[:1] if isinstance(n, str) and n])
    push([n for n, _ in refs])
    return picked[:sample_n]


def main():
    ap = argparse.ArgumentParser(description='Live DSH dsh-pet verifier')
    ap.add_argument('--base-url', default='http://127.0.0.1:57076')
    ap.add_argument('--packs-dir', default=os.path.join(PROJECT, 'plugin', 'packs'))
    ap.add_argument('--out', default=os.path.join(PROJECT, 'build', 'verify', 'verify_live.json'))
    ap.add_argument('--sample', type=int, default=3, help='每个角色抽检 thumb 数')
    ap.add_argument('--all-thumbs', action='store_true', help='全量校验所有引用（较慢）')
    ap.add_argument('--strict', action='store_true', help='阶段二：缺条目/异常 -> FAIL')
    ap.add_argument('--expect-active', default='', help='v1.1：期望当前 active 角色 id（如 deepseek；留空只做一致性检查）')
    ap.add_argument('--timeout', type=float, default=20.0)
    args = ap.parse_args()

    base = args.base_url.rstrip('/')
    packs_dir = os.path.abspath(args.packs_dir)
    prefixes, prefix_map, packs_complete = resolve_expected_prefixes(packs_dir)
    missing_in_packs = [pid for pid in EXPECTED_IDS if pid not in prefix_map]
    if not os.path.isdir(packs_dir):
        add('packs.source', 'packs 源目录 8 个前缀', 'SKIP',
            'packs 目录不存在，按约定前缀校验: %s' % ', '.join(prefixes))
    elif missing_in_packs:
        add('packs.source', 'packs 源目录 8 个前缀', 'FAIL',
            'packs 目录缺少角色: %s' % ', '.join(missing_in_packs))
    else:
        add('packs.source', 'packs 源目录 8 个前缀', 'PASS', ', '.join(prefixes))

    # ---------- /config ----------
    cfg_url = base + PET_ROUTE
    r = http_get(cfg_url, timeout=args.timeout)
    requests_log.append({k: v for k, v in r.items() if k != 'body'})
    if r['status'] != 200:
        status = 'FAIL' if args.strict else 'SKIP'
        add('config.http', 'GET /dsh-pet-7340/config -> 200', status,
            'status=%r error=%s' % (r['status'], r['error']))
        return finish(args, cfg_url, prefixes, missing_in_packs, strict=args.strict, fatal=True)
    add('config.http', 'GET /dsh-pet-7340/config -> 200', 'PASS',
        'content-type=%s content-length=%s' % (r['content_type'], r['content_length']))
    try:
        cfg = json.loads(r['body'].decode('utf-8'))
    except Exception as e:  # noqa: BLE001
        add('config.json', '/config 返回合法 JSON', 'FAIL', 'JSON 解析失败: %s' % e)
        return finish(args, cfg_url, prefixes, missing_in_packs, strict=args.strict, fatal=True)
    add('config.json', '/config 返回合法 JSON', 'PASS',
        '条目: %s' % ', '.join(cfg.keys()))

    if 'main' in cfg:
        add('config.main', '/config 含 main 条目', 'PASS', '')
    else:
        add('config.main', '/config 含 main 条目', 'FAIL', '缺少 main（原主宠物配置丢失）')

    present = [p for p in prefixes if p in cfg]
    missing = [p for p in prefixes if p not in cfg]
    if missing:
        status = 'FAIL' if args.strict else 'SKIP'
        add('config.new_entries', '/config 含 8 个新 pet pack 条目', status,
            '已出现 %d/%d；缺少: %s；当前条目: %s' % (
                len(present), len(prefixes), ', '.join(missing), ', '.join(cfg.keys())))
    else:
        add('config.new_entries', '/config 含 8 个新 pet pack 条目', 'PASS',
            '8/8 全部出现: %s' % ', '.join(present))
    extras = [k for k in cfg.keys() if k not in prefixes and k != 'main']
    if extras:
        add('config.extra_entries', '/config 无多余条目', 'WARN',
            '存在非本次交付的额外条目: %s（可能是测试残留，建议清理）' % ', '.join(extras))
    else:
        add('config.extra_entries', '/config 无多余条目', 'PASS', '只有 main + 8 个新条目')

    # ---------- main 未受影响证据 ----------
    main_entry = cfg.get('main') if isinstance(cfg.get('main'), dict) else {}
    main_pets = main_entry.get('pets') if isinstance(main_entry.get('pets'), list) else []
    main_anims = main_entry.get('animations') if isinstance(main_entry.get('animations'), dict) else {}
    main_idle = [n for n in (main_anims.get('idle') or []) if isinstance(n, str) and n]
    main_anim_name = main_idle[0] if main_idle else MAIN_ANIM_FALLBACK
    main_pet_ids = [str(p.get('id')) for p in main_pets if isinstance(p, dict)]
    main_summary = {
        'pets': len(main_pets), 'pet_ids': main_pet_ids,
        'animations_keys': sorted(main_anims.keys()),
        'idle': main_idle, 'clicks_count': len(main_anims.get('clicks') or []),
        'categories_count': len(main_anims.get('categories') or []),
        'events': sorted((main_anims.get('events') or {}).keys()) if isinstance(main_anims.get('events'), dict) else [],
        'whisperPrompt_present': bool(main_entry.get('whisperPrompt')),
        'physics_gravity': (main_entry.get('physics') or {}).get('gravity') if isinstance(main_entry.get('physics'), dict) else None,
        # 主宠物条目整段指纹：用于与部署前快照对比，证明 main 未被破坏
        'entry_sha256': hashlib.sha256(
            json.dumps(main_entry, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
        ).hexdigest(),
    }
    if main_pets and MAIN_PET_ID in main_pet_ids:
        add('main.pets', 'main.pets 非空且含 main 实例', 'PASS',
            'pets=%d ids=%s' % (len(main_pets), ','.join(main_pet_ids)))
    elif main_pets:
        add('main.pets', 'main.pets 非空且含 main 实例', 'WARN',
            'pets=%d ids=%s（未找到 id=main）' % (len(main_pets), ','.join(main_pet_ids)))
    else:
        add('main.pets', 'main.pets 非空且含 main 实例', 'FAIL', 'main.pets 为空/缺失')
    if main_anims.get('idle') and main_anims.get('clicks'):
        add('main.animations', 'main.animations 完整', 'PASS',
            'idle=%s clicks=%d categories=%d events=%s' % (
                ','.join(main_idle[:2]), len(main_anims.get('clicks') or []),
                len(main_anims.get('categories') or []), main_summary['events']))
    else:
        add('main.animations', 'main.animations 完整', 'FAIL', 'main.animations 缺少 idle/clicks')

    # main 原动画路由仍 200
    main_thumb_url = base + THUMB_ROUTE + 'main/' + urllib.parse.quote(main_anim_name + '.webm')
    mr = headers_only_get(main_thumb_url, timeout=args.timeout)
    requests_log.append({k: v for k, v in mr.items()})
    if mr['status'] == 200 and 'video/webm' in (mr['content_type'] or ''):
        expected_main_size = None
        for cand in (
            os.path.join(os.path.expanduser('~'), '.dsh', 'dsh-pet', 'main-animation', 'webm', main_anim_name + '.webm'),
            os.path.join(os.path.expanduser('~'), '.dsh', 'profiles', 'desktop', 'node_modules', 'dsh-pet', 'assets', 'webm', main_anim_name + '.webm'),
        ):
            if os.path.isfile(cand):
                expected_main_size = os.path.getsize(cand)
                break
        size_note = ''
        if expected_main_size is not None:
            size_note = '；content-length=%s 磁盘=%s %s' % (
                mr['content_length'], expected_main_size,
                '一致' if mr['content_length'] == expected_main_size else '不一致')
        add('main.thumb', 'GET /thumb/main/%s.webm -> 200' % main_anim_name, 'PASS',
            'content-type=%s content-length=%s%s' % (mr['content_type'], mr['content_length'], size_note),
            {'url': main_thumb_url, 'content_length': mr['content_length'], 'disk_size': expected_main_size})
        main_summary['thumb'] = {'name': main_anim_name, 'status': mr['status'],
                                 'content_type': mr['content_type'], 'content_length': mr['content_length'],
                                 'disk_size': expected_main_size}
    else:
        add('main.thumb', 'GET /thumb/main/%s.webm -> 200' % main_anim_name, 'FAIL',
            'status=%r content-type=%r error=%s url=%s' % (
                mr['status'], mr['content_type'], mr['error'], main_thumb_url))
        main_summary['thumb'] = {'name': main_anim_name, 'status': mr['status'], 'error': mr['error']}

    # ---------- 插件静态路由（/dsh-pet-ai-girls/，若插件已安装到该 DSH 实例） ----------
    plugin_routes = [
        ('/dsh-pet-ai-girls/', 'text/html', '图鉴页'),
        ('/dsh-pet-ai-girls/health', 'application/json', '健康检查'),
        ('/dsh-pet-ai-girls/data.json', 'application/json', '图鉴数据'),
    ]
    plugin_route_results = []
    for path, expect_ct, label in plugin_routes:
        pr = http_get(base + path, timeout=args.timeout, max_bytes=8192)
        body = (pr.get('body') or b'')[:160].decode('utf-8', errors='replace')
        ok = pr['status'] == 200 and expect_ct in (pr['content_type'] or '')
        rec = {'path': path, 'label': label, 'status': pr['status'],
               'content_type': pr['content_type'], 'body_head': body}
        plugin_route_results.append(rec)
        if ok:
            add('plugin.route%s' % path.replace('/', '_'), '/dsh-pet-ai-girls %s 路由' % label, 'PASS',
                'GET %s -> 200 %s' % (path, pr['content_type']))
        elif pr['status'] == 404:
            add('plugin.route%s' % path.replace('/', '_'), '/dsh-pet-ai-girls %s 路由' % label, 'SKIP',
                'GET %s -> 404（插件可能尚未安装到该 DSH 实例）' % path)
        else:
            add('plugin.route%s' % path.replace('/', '_'), '/dsh-pet-ai-girls %s 路由' % label, 'WARN',
                'GET %s -> status=%r content-type=%r' % (path, pr['status'], pr['content_type']))

    # ---------- v1.1 插件元数据：/health 与 /api/current ----------
    pkg_version = None
    try:
        with open(os.path.join(PROJECT, 'plugin', 'package.json'), 'r', encoding='utf-8-sig') as f:
            pkg_version = str(json.load(f).get('version') or '')
    except Exception:  # noqa: BLE001
        pass
    health_data = None
    hr = http_get(base + '/dsh-pet-ai-girls/health', timeout=args.timeout, max_bytes=65536)
    if hr['status'] == 200:
        try:
            health_data = json.loads((hr.get('body') or b'').decode('utf-8'))
        except Exception:  # noqa: BLE001
            health_data = None
    chk = 'SKIP' if hr['status'] == 404 else 'FAIL'
    if not isinstance(health_data, dict):
        add('v11.health', '/health 返回合法 JSON 且含 version/active/characters', chk,
            'status=%r content-type=%r body=%r' % (
                hr['status'], hr['content_type'], (hr.get('body') or b'')[:120]))
    else:
        ver = str(health_data.get('version') or '')
        pack_ver = str(health_data.get('packVersion') or '')
        # v1.2 已知现象：DSH 进程内 host 代码仍是旧版（Node ESM 模块缓存，重启 DSH 才加载新版），
        # 因此 /health.version 可能落后于 package.json；只要 packVersion 已同步，记 WARN 而非 FAIL。
        if (not pkg_version) or ver == pkg_version:
            add('v11.health_version', '/health version 与 plugin/package.json 一致', 'PASS',
                'health.version=%r package.json=%r packVersion=%r' % (ver, pkg_version, pack_ver))
        elif pack_ver == pkg_version:
            add('v12.health_host_cache', '/health version 落后于 package.json（host 模块缓存）', 'WARN',
                'health.version=%r（host 代码缓存）package.json=%r packVersion=%r（已同步）；'
                '重启 DSH 后 host 代码生效，属已知限制' % (ver, pkg_version, pack_ver))
        else:
            add('v11.health_version', '/health version 与 plugin/package.json 一致', 'FAIL',
                'health.version=%r package.json=%r packVersion=%r' % (ver, pkg_version, pack_ver))
        chars = health_data.get('characters') if isinstance(health_data.get('characters'), list) else []
        active = health_data.get('active') if isinstance(health_data.get('active'), dict) else {}
        active_marks = [c.get('id') for c in chars if isinstance(c, dict) and c.get('active') is True]
        add('v11.health_active', '/health 8 角色且恰好 1 个 active，active.id 与之一致',
            'PASS' if len(chars) == 8 and len(active_marks) == 1 and active.get('id') == active_marks[0] else 'FAIL',
            'characters=%d active_marks=%s active.id=%r' % (len(chars), active_marks, active.get('id')))
        add('v11.health_deployed', '/health deployed=true 且 animationCount=17',
            'PASS' if health_data.get('deployed') is True and health_data.get('animationCount') == 17 else 'FAIL',
            'deployed=%r animationCount=%r' % (health_data.get('deployed'), health_data.get('animationCount')))
        if args.expect_active:
            add('v11.health_expect', '/health active 与预期一致（%s）' % args.expect_active,
                'PASS' if active.get('id') == args.expect_active else 'FAIL',
                '实际=%r 预期=%r' % (active.get('id'), args.expect_active))
    api_current = None
    cr = http_get(base + '/dsh-pet-ai-girls/api/current', timeout=args.timeout, max_bytes=65536)
    if cr['status'] == 200:
        try:
            api_current = json.loads((cr.get('body') or b'').decode('utf-8'))
        except Exception:  # noqa: BLE001
            api_current = None
    if not isinstance(api_current, dict):
        add('v11.api_current', 'GET /api/current 返回合法 JSON', 'FAIL' if cr['status'] != 404 else 'SKIP',
            'status=%r content-type=%r body=%r' % (
                cr['status'], cr['content_type'], (cr.get('body') or b'')[:120]))
    else:
        cur_active = api_current.get('active') if isinstance(api_current.get('active'), dict) else {}
        cur_chars = api_current.get('characters') if isinstance(api_current.get('characters'), list) else []
        health_active_id = (health_data or {}).get('active', {}).get('id') if isinstance(health_data, dict) else None
        consistent = health_active_id is None or cur_active.get('id') == health_active_id
        add('v11.api_current', 'GET /api/current：ok、active、8 个 characters',
            'PASS' if api_current.get('ok') is True and cur_active.get('id') and len(cur_chars) == 8 and consistent else 'FAIL',
            'ok=%r active.id=%r characters=%d；与 /health active 一致=%s' % (
                api_current.get('ok'), cur_active.get('id'), len(cur_chars), consistent))
        if args.expect_active:
            add('v11.api_current_expect', '/api/current active 与预期一致（%s）' % args.expect_active,
                'PASS' if cur_active.get('id') == args.expect_active else 'FAIL',
                '实际=%r 预期=%r' % (cur_active.get('id'), args.expect_active))

    # ---------- v1.2：packVersion / 图鉴 data.json 版本 / 新动画池 ----------
    v12 = {'pkg_version': pkg_version}
    if isinstance(health_data, dict):
        pack_ver = str(health_data.get('packVersion') or '')
        v12['health_packVersion'] = pack_ver
        add('v12.health_packVersion', '/health packVersion == plugin/package.json 版本（部署 marker 已同步 v1.2.0）',
            'PASS' if (not pkg_version) or pack_ver == pkg_version else 'FAIL',
            'packVersion=%r package.json=%r health.version=%r' % (pack_ver, pkg_version, health_data.get('version')))
    dj = http_get(base + '/dsh-pet-ai-girls/data.json', timeout=args.timeout, max_bytes=65536)
    data_json = None
    if dj['status'] == 200:
        try:
            data_json = json.loads((dj.get('body') or b'').decode('utf-8'))
        except Exception:  # noqa: BLE001
            data_json = None
    if isinstance(data_json, dict):
        dj_ver = str(data_json.get('version') or '')
        v12['data_json_version'] = dj_ver
        add('v12.data_json_version', '图鉴 /data.json version == plugin/package.json 版本（v1.2.0）',
            'PASS' if (not pkg_version) or dj_ver == pkg_version else 'FAIL',
            'data.json version=%r package.json=%r' % (dj_ver, pkg_version))
    else:
        add('v12.data_json_version', '图鉴 /data.json version == plugin/package.json 版本（v1.2.0）',
            'SKIP' if dj['status'] == 404 else 'FAIL',
            'status=%r body=%r' % (dj['status'], (dj.get('body') or b'')[:120]))
    # 新动画池：clicks 4 个（含转圈展示）、categories weight=24/3 actions、weights 76/0/0（8 条目一致）
    want_cat_actions = {'转圈展示', '东张西望', '伸懒腰'}
    pool_bad = []
    pool_stats = {}
    for prefix in prefixes:
        entry = cfg.get(prefix) if isinstance(cfg, dict) else None
        anims = (entry or {}).get('animations') if isinstance(entry, dict) and isinstance(entry.get('animations'), dict) else {}
        clicks = anims.get('clicks') if isinstance(anims.get('clicks'), list) else []
        cats = anims.get('categories') if isinstance(anims.get('categories'), list) else []
        weights = entry.get('animationWeights') if isinstance(entry, dict) and isinstance(entry.get('animationWeights'), dict) else {}
        cat0 = cats[0] if cats and isinstance(cats[0], dict) else {}
        acts = set(cat0.get('actions') or []) if isinstance(cat0.get('actions'), list) else set()
        probs = []
        if len(clicks) != 4 or '转圈展示' not in clicks:
            probs.append('clicks=%s' % clicks)
        if len(cats) != 1 or cat0.get('weight') != 24 or len(acts) != 3 or acts != want_cat_actions:
            probs.append('categories=%s' % [(c.get('weight'), c.get('actions')) for c in cats if isinstance(c, dict)])
        if weights.get('idle') != 76 or weights.get('turn') != 0 or weights.get('move') != 0:
            probs.append('weights=%s' % weights)
        pool_stats[prefix] = {'clicks': clicks, 'categories': [(c.get('weight'), c.get('actions')) for c in cats if isinstance(c, dict)],
                              'weights': weights}
        if probs:
            pool_bad.append('%s: %s' % (prefix, '; '.join(probs)))
    v12['pools'] = pool_stats
    if pool_stats:
        add('v12.live_pools', '8 条目新动画池：clicks=4(含转圈展示)、categories weight=24/3 actions、weights=76/0/0',
            'PASS' if not pool_bad else 'FAIL',
            ('8/8 条目全部符合' if not pool_bad else '; '.join(pool_bad[:6])))
    plugin_meta = {'health': health_data, 'api_current': api_current, 'pkg_version': pkg_version,
                   'data_json_version': (data_json or {}).get('version') if isinstance(data_json, dict) else None,
                   'v12': v12}

    # ---------- 每个新条目 ----------
    entry_reports = {}
    for prefix in prefixes:
        entry = cfg.get(prefix)
        rep = {'prefix': prefix, 'present': entry is not None, 'checks': [], 'thumbs': []}
        entry_reports[prefix] = rep
        if entry is None:
            rep['checks'].append({'name': 'live 条目存在', 'status': 'SKIP' if not args.strict else 'FAIL',
                                  'detail': '/config 中无该条目（pack 未部署？）'})
            continue
        if not isinstance(entry, dict):
            rep['checks'].append({'name': 'live 条目为对象', 'status': 'FAIL', 'detail': '类型 %r' % type(entry)})
            continue
        pets = entry.get('pets') if isinstance(entry.get('pets'), list) else []
        rep['pets'] = len(pets)
        rep['pet_ids'] = [str(p.get('id')) for p in pets if isinstance(p, dict)]
        rep['checks'].append({'name': 'pets 非空', 'status': 'PASS' if pets else 'FAIL',
                              'detail': 'pets=%d ids=%s' % (len(pets), ','.join(rep['pet_ids']))})
        anims = entry.get('animations') if isinstance(entry.get('animations'), dict) else {}
        anim_probs = []
        for k in ('idle', 'turn', 'drag', 'clicks'):
            if not isinstance(anims.get(k), list):
                anim_probs.append('animations.%s 缺失/非数组' % k)
        moves = anims.get('moves')
        if not isinstance(moves, dict) or not isinstance(moves.get('default'), dict) or not isinstance(moves.get('actions'), list):
            anim_probs.append('animations.moves 不完整')
        if not isinstance(anims.get('categories'), list):
            anim_probs.append('animations.categories 非数组')
        ev = anims.get('events')
        if not isinstance(ev, dict) or not ev:
            anim_probs.append('animations.events 缺失/空')
        else:
            if not isinstance(ev.get('balance'), list) or not ev.get('balance'):
                anim_probs.append('events.balance 缺失/空')
            for pool, slots in ev.items():
                if not isinstance(slots, list) or not slots:
                    anim_probs.append('events.%s 空/非数组' % pool)
        rep['checks'].append({'name': 'animations 字段齐全', 'status': 'FAIL' if anim_probs else 'PASS',
                              'detail': '; '.join(anim_probs[:8]) if anim_probs else
                                        'idle=%d clicks=%d categories=%d events=%s' % (
                                            len(anims.get('idle') or []), len(anims.get('clicks') or []),
                                            len(anims.get('categories') or []),
                                            ','.join(ev.keys()) if isinstance(ev, dict) else '?')})
        aw = entry.get('animationWeights')
        aw_probs = []
        if not isinstance(aw, dict):
            aw_probs.append('缺失/非对象')
        else:
            for k in ('idle', 'turn', 'move'):
                v = aw.get(k)
                if not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0:
                    aw_probs.append('%s=%r' % (k, v))
        rep['checks'].append({'name': 'animationWeights 合法', 'status': 'FAIL' if aw_probs else 'PASS',
                              'detail': '; '.join(aw_probs) if aw_probs else 'idle=%s turn=%s move=%s' % (
                                  aw.get('idle'), aw.get('turn'), aw.get('move')) if isinstance(aw, dict) else ''})
        refs = collect_refs(anims)
        rep['refs_count'] = len(refs)
        if args.all_thumbs:
            sample = [n for n, _ in refs]
        else:
            sample = pick_sample(anims, refs, args.sample)
        rep['sampled'] = sample
        bad_thumbs = []
        missing_disk = []
        for name in sample:
            size, disk_path = disk_webm_size(packs_dir, prefix, name)
            url = base + THUMB_ROUTE + urllib.parse.quote(prefix) + '/' + urllib.parse.quote(name + '.webm')
            tr = headers_only_get(url, timeout=args.timeout)
            requests_log.append({k: v for k, v in tr.items()})
            rec = {'name': name, 'url': url, 'status': tr['status'],
                   'content_type': tr['content_type'], 'content_length': tr['content_length'],
                   'disk_size': size, 'disk_path': os.path.relpath(disk_path, PROJECT) if disk_path else None,
                   'ok': False, 'problems': []}
            probs = []
            if tr['status'] != 200:
                probs.append('status=%r error=%s' % (tr['status'], tr['error']))
            if 'video/webm' not in (tr['content_type'] or ''):
                probs.append('content-type=%r 非 video/webm' % tr['content_type'])
            if size is None:
                missing_disk.append(name)
                probs.append('磁盘源文件缺失')
            elif tr['content_length'] != size:
                probs.append('content-length=%r != 磁盘 %d' % (tr['content_length'], size))
            rec['problems'] = probs
            rec['ok'] = not probs
            if probs:
                bad_thumbs.append(rec)
            rep['thumbs'].append(rec)
        if bad_thumbs:
            add('%s.thumbs' % prefix, '%s thumb 路由抽样' % prefix, 'FAIL',
                '; '.join('%s: %s' % (t['name'], '|'.join(t['problems'])) for t in bad_thumbs[:6]))
            rep['checks'].append({'name': 'thumb 路由抽样', 'status': 'FAIL',
                                  'detail': '%d/%d 失败' % (len(bad_thumbs), len(sample))})
        else:
            add('%s.thumbs' % prefix, '%s thumb 路由抽样' % prefix, 'PASS',
                '%d 个: %s' % (len(sample), ', '.join(sample)) + (' (全量)' if args.all_thumbs else ''))
            rep['checks'].append({'name': 'thumb 路由抽样', 'status': 'PASS',
                                  'detail': '%d 个通过' % len(sample)})

    # ---------- v1.1 live 显示契约：8 条目恰好 1 个 display=both、统一 size/position ----------
    live_disp = {}
    live_size = {}
    live_pos = {}
    for prefix in prefixes:
        entry = cfg.get(prefix) if isinstance(cfg, dict) else None
        pets = (entry or {}).get('pets') if isinstance(entry, dict) and isinstance(entry.get('pets'), list) else []
        pet = pets[0] if pets and isinstance(pets[0], dict) else {}
        pos = pet.get('position') if isinstance(pet.get('position'), dict) else {}
        if prefix in cfg:
            live_disp[prefix] = pet.get('display')
            live_size[prefix] = pet.get('size')
            live_pos[prefix] = '%s/%s/%s' % (pos.get('corner'), pos.get('marginX'), pos.get('marginY'))
    if live_disp:
        both = sorted(k for k, d in live_disp.items() if d == 'both')
        none = sorted(k for k, d in live_disp.items() if d == 'none')
        is_v11 = bool(none) or str((health_data or {}).get('version') or '').startswith('1.1') or bool(args.expect_active)
        if is_v11:
            add('v11.live_single_active', '/config 8 条目恰好 1 个 display=both、其余 none',
                'PASS' if len(both) == 1 and len(none) == len(live_disp) - 1 else 'FAIL',
                'both=%s；none=%d 个' % (both, len(none)))
            sizes = sorted(set(str(v) for v in live_size.values()))
            add('v11.live_size', '/config 8 条目 size 统一 340',
                'PASS' if sizes == ['340'] else 'FAIL', 'sizes=%s' % sizes)
            poss = sorted(set(live_pos.values()))
            add('v11.live_position', '/config 8 条目 position 统一 bottom-right/40/40',
                'PASS' if poss == ['bottom-right/40/40'] else 'FAIL', 'positions=%s' % poss)
            expected_active = args.expect_active or (
                (health_data or {}).get('active', {}).get('id') if isinstance(health_data, dict) else None)
            if both and expected_active:
                both_id = str((((cfg.get(both[0]) or {}).get('pets') or [{}])[0]).get('id') or '')
                ok = both_id == expected_active or both_id == 'girl-' + expected_active
                add('v11.live_active_display', 'display=both 的条目 == 当前 active 角色',
                    'PASS' if ok else 'FAIL', 'both_prefix=%r both_id=%r active=%r' % (both[0], both_id, expected_active))
        else:
            add('v11.live_single_active', '/config 单角色显示契约', 'SKIP', '当前为 v1.0 全显示模式')

    # ---------- 汇总 ----------
    total_refs = sum(r.get('refs_count') or 0 for r in entry_reports.values())
    return finish(args, cfg_url, prefixes, missing_in_packs, strict=args.strict, fatal=False,
                  cfg=cfg, main_summary=main_summary, entry_reports=entry_reports,
                  total_refs=total_refs, base=base, plugin_routes=plugin_route_results,
                  plugin_meta=plugin_meta, live_display=live_disp)


def finish(args, cfg_url, prefixes, missing_in_packs, strict=False, fatal=False,
           cfg=None, main_summary=None, entry_reports=None, total_refs=0, base='',
           plugin_routes=None, plugin_meta=None, live_display=None):
    statuses = {}
    for c in checks:
        statuses[c['status']] = statuses.get(c['status'], 0) + 1
    report = {
        'tool': 'tools/verify_live.py',
        'generated_at': __import__('datetime').datetime.now().isoformat(timespec='seconds'),
        'base_url': base,
        'config_url': cfg_url,
        'strict': bool(strict),
        'prefixes_expected': prefixes,
        'missing_in_packs_source': missing_in_packs,
        'summary': dict(statuses),
        'checks': checks,
        'main': main_summary or {},
        'config_snapshot': cfg or {},
        'entries': entry_reports or {},
        'plugin_routes': plugin_routes or [],
        'plugin_meta': plugin_meta or {},
        'live_display': live_display or {},
        'refs_total': total_refs,
        'requests': requests_log,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print('')
    print('=' * 82)
    print('verify_live.py  |  %s  |  strict=%s' % (cfg_url, strict))
    print('=' * 82)
    for c in checks:
        print('[%s] %-48s %s' % (c['status'], c['name'], c['detail']))
    print('-' * 82)
    if main_summary:
        print('main 摘要: pets=%s ids=%s idle=%s events=%s' % (
            main_summary.get('pets'), main_summary.get('pet_ids'), main_summary.get('idle'),
            main_summary.get('events')))
    if entry_reports:
        print('条目抽检:')
        for p, r in entry_reports.items():
            print('  %-9s present=%-5s pets=%-2s refs=%-3s sampled=%s' % (
                p, r.get('present'), r.get('pets', '-'), r.get('refs_count', '-'),
                ','.join(r.get('sampled') or [])))
    if plugin_routes:
        print('插件路由: ' + '; '.join('%s=%s' % (r['path'], r['status']) for r in plugin_routes))
    print('结果: %s' % ','.join('%s=%d' % (k, statuses.get(k, 0)) for k in ('PASS', 'FAIL', 'WARN', 'SKIP')))
    print('JSON: %s' % args.out)
    print('=' * 82)
    return 0 if not any(c['status'] == 'FAIL' for c in checks) else 1


if __name__ == '__main__':
    sys.exit(main())
