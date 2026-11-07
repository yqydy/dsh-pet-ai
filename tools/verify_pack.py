#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
verify_pack.py —— dsh-pet-ai-girls pet pack 独立校验器（不依赖 animlib.py）。

校验对象：plugin/packs/ 下 8 个 AI 娘 pet pack
  <prefix>-config.json
  <prefix>-animation/webm/<动画名>.webm

检查项：
  A. 结构：config JSON 可解析；pets[] 实例字段合法；animations 各段结构合法；
     events 各档非空、balance 存在且非空；animationWeights 三项非负；
     配置中引用的所有动画名都能在同前缀 animation/webm 找到（引用 ⊆ 文件）；
     每个 pack 的 webm 数量、与其他 pack 的动画名集合一致性。
  B. 媒体：每个 webm 用 ffmpeg -i 解析：640x360、24fps(±0.5)、时长 >0.8s、
     文件大小 >20KB；统计文件数与总大小；附带 ALPHA_MODE 元数据信息。

输出：机器可读 JSON（默认 build/verify/verify_pack.json）+ stdout 人类可读摘要。
有任何 FAIL 时 exit 1；只有 WARN 时 exit 0。

用法：
  python tools/verify_pack.py
  python tools/verify_pack.py --packs-dir <dir> --out <json>
  python tools/verify_pack.py --no-media        # 只做结构检查
"""
import argparse
import json
import os
import re
import subprocess
import sys

try:  # 全 UTF-8 输出（Windows 控制台/管道下中文不乱码）
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:  # noqa: BLE001
    pass

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 8 个角色的 id；pet pack 前缀约定为 girl-<id>（源文件 spec.CHARACTERS.prefix）。
# 校验时按 id 解析实际前缀：接受 <id> 或 girl-<id> 或 <任意>-<id>，其余前缀算多余。
EXPECTED_IDS = ['deepseek', 'gpt', 'claude', 'grok', 'gemini', 'kimi', 'glm', 'qwen']
EXPECTED_PREFIXES = ['girl-' + i for i in EXPECTED_IDS]

# task-1 的 17 个固定动画名（build/anim_smoke 现行集合；优先读 build/webm/manifest.json）
FALLBACK_ANIM_NAMES = [
    '东张西望', '伸懒腰', '原地小憩', '原地漂浮',
    '工作状态-原地踱步张望', '工作状态-垂头叹气冒汗', '工作状态-忙碌点按',
    '工作状态-思考冒泡', '工作状态-清点归档', '工作状态-雀跃庆祝',
    '待机呼吸', '点击回应-元气挥手', '点击回应-害羞惊讶', '点击回应-开心跃动',
    '碎碎念-发呆碎碎念', '被鼠标拖拽悬空反馈', '转圈展示',
]

DISPLAYS = {'web', 'desktop', 'both', 'none'}
CORNERS = {'top-left', 'top-right', 'bottom-left', 'bottom-right'}
ID_FORBIDDEN = re.compile(r'[\\/:\x00-\x1f]')

FFMPEG_CANDIDATES = [
    os.environ.get('DSH_FFMPEG', ''),
    r'C:\Users\20862\AppData\Roaming\Python\Python38\site-packages\imageio_ffmpeg\binaries\ffmpeg-win64-v4.2.2.exe',
    'ffmpeg',
]

checks = []      # [{id, name, status, detail, evidence}]
files_report = []  # 每个 webm 的解析结果


def add(check_id, name, status, detail='', evidence=None):
    checks.append({
        'id': check_id,
        'name': name,
        'status': status,   # PASS / FAIL / WARN / SKIP
        'detail': detail,
        'evidence': evidence,
    })


def find_ffmpeg():
    for c in FFMPEG_CANDIDATES:
        if c and (c == 'ffmpeg' or os.path.isfile(c)):
            return c
    return None


def ffmpeg_probe(ffmpeg, path):
    """用 ffmpeg -i 解析媒体信息（v4.2.2 对 VP9-alpha 会解不出 alpha，属已知限制）。"""
    info = {
        'file': path,
        'name': os.path.basename(path),
        'size': os.path.getsize(path),
        'ok': False, 'error': '',
        'width': None, 'height': None, 'fps': None, 'duration': None,
        'video_codec': '', 'pix_fmt': '', 'alpha_mode': None,
    }
    if not ffmpeg:
        info['error'] = 'ffmpeg not found'
        return info
    try:
        p = subprocess.run(
            [ffmpeg, '-hide_banner', '-i', path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=60,
        )
        err = (p.stderr or b'').decode('utf-8', errors='replace')
    except Exception as e:  # noqa: BLE001
        info['error'] = 'ffmpeg exec failed: %s' % e
        return info
    m_dur = re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', err)
    if m_dur:
        info['duration'] = int(m_dur.group(1)) * 3600 + int(m_dur.group(2)) * 60 + float(m_dur.group(3))
    m_vid = re.search(r'Stream #0:0.*?Video:\s*([a-z0-9_]+).*?,\s*(\d{2,5})x(\d{2,5})', err)
    if m_vid:
        info['video_codec'] = m_vid.group(1)
        info['width'] = int(m_vid.group(2))
        info['height'] = int(m_vid.group(3))
    m_fps = re.search(r'(\d+(?:\.\d+)?)\s*fps', err)
    if m_fps:
        info['fps'] = float(m_fps.group(1))
    m_pix = re.search(r'Video:\s*[a-z0-9_]+[^\n]*?,\s*([a-z0-9]+(?:\([a-z]+\))?)', err)
    m_alpha = re.search(r'ALPHA_MODE\s*:\s*(\d+)', err)
    if m_alpha:
        info['alpha_mode'] = int(m_alpha.group(1))
    if info['width'] is not None and info['duration'] is not None:
        info['ok'] = True
    else:
        info['error'] = err.strip().splitlines()[-1][:300] if err.strip() else 'no media info parsed'
    return info


def read_expected_anim_names(packs_dir):
    # 优先 task-1/产线 manifest：build/pack_manifest.json（animations 列表）或 build/webm/manifest.json
    for manifest in (os.path.join(PROJECT, 'build', 'pack_manifest.json'),
                     os.path.join(PROJECT, 'build', 'webm', 'manifest.json')):
        if not os.path.isfile(manifest):
            continue
        try:
            with open(manifest, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
            names = set()
            if isinstance(data, dict):
                if isinstance(data.get('animations'), list):
                    names.update(str(x) for x in data['animations'] if isinstance(x, str))
                for char, val in data.items():
                    if isinstance(val, dict):
                        for k in ('animations', 'files'):
                            if isinstance(val.get(k), dict):
                                names.update(val[k].keys())
                            elif isinstance(val.get(k), list):
                                names.update(os.path.splitext(os.path.basename(str(x)))[0] for x in val[k])
            if len(names) >= 10:
                return sorted(names), manifest
        except Exception:  # noqa: BLE001
            pass
    return list(FALLBACK_ANIM_NAMES), None


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validate_pet(pet, idx, seen_ids, label):
    """返回 (ok, details)。字段缺失视为不完整（pack 交付要求 fields 齐全）。"""
    problems = []
    if not isinstance(pet, dict):
        return False, ['pets[%d] 不是对象' % idx]
    pet_id = pet.get('id')
    if not isinstance(pet_id, str) or not pet_id.strip():
        problems.append('id 缺失/非字符串')
    else:
        pid = pet_id.strip()
        if len(pid) > 64:
            problems.append('id 长度 >64')
        if ID_FORBIDDEN.search(pid):
            problems.append('id 含非法字符 [\\\\/:控制符]')
        if pid in seen_ids:
            problems.append('id 重复: %s' % pid)
        else:
            seen_ids.add(pid)
    name = pet.get('name')
    if not isinstance(name, str) or not name.strip():
        problems.append('name 缺失/空')
    size = pet.get('size')
    if not is_num(size) or size < 1:
        problems.append('size 缺失/非数字/小于1')
    be = pet.get('balanceEnabled')
    if not isinstance(be, bool):
        problems.append('balanceEnabled 缺失/非布尔')
    disp = pet.get('display')
    if disp not in DISPLAYS:
        problems.append('display 缺失/非法: %r' % (disp,))
    pos = pet.get('position')
    if not isinstance(pos, dict):
        problems.append('position 缺失/非对象')
    else:
        if pos.get('corner') not in CORNERS:
            problems.append('position.corner 缺失/非法: %r' % (pos.get('corner'),))
        for k in ('marginX', 'marginY'):
            if not is_num(pos.get(k)):
                problems.append('position.%s 缺失/非数字' % k)
    return (not problems), problems


def validate_animations(anim, label):
    """返回 (problems, refs)。结构规则对齐 dsh-pet host 的 animationsValid + pack 交付要求。"""
    problems = []
    refs = []
    if not isinstance(anim, dict):
        return ['animations 缺失/非对象'], refs
    for key in ('idle', 'turn', 'drag', 'clicks'):
        v = anim.get(key)
        if not isinstance(v, list):
            problems.append('animations.%s 缺失/非数组' % key)
        else:
            for i, n in enumerate(v):
                if not isinstance(n, str) or not n:
                    problems.append('animations.%s[%d] 非空字符串非法' % (key, i))
                else:
                    refs.append((n, 'animations.%s[%d]' % (key, i)))
    moves = anim.get('moves')
    if not isinstance(moves, dict):
        problems.append('animations.moves 缺失/非对象')
    else:
        d = moves.get('default')
        if not isinstance(d, dict):
            problems.append('animations.moves.default 缺失/非对象')
        else:
            for k in ('minDist', 'maxDist', 'margin', 'leadSec', 'tailSec'):
                if k in d and not is_num(d[k]):
                    problems.append('animations.moves.default.%s 非数字' % k)
            for k in ('minDist', 'maxDist'):
                if k not in d:
                    problems.append('animations.moves.default.%s 缺失' % k)
        actions = moves.get('actions')
        if not isinstance(actions, list):
            problems.append('animations.moves.actions 缺失/非数组')
        else:
            for i, a in enumerate(actions):
                if not isinstance(a, dict) or not isinstance(a.get('name'), str) or not a.get('name'):
                    problems.append('animations.moves.actions[%d] 缺少 name' % i)
                else:
                    refs.append((a['name'], 'animations.moves.actions[%d]' % i))
                if isinstance(a, dict) and 'params' in a and not isinstance(a['params'], dict):
                    problems.append('animations.moves.actions[%d].params 非对象' % i)
    cats = anim.get('categories')
    if not isinstance(cats, list):
        problems.append('animations.categories 缺失/非数组')
    else:
        for i, c in enumerate(cats):
            if not isinstance(c, dict):
                problems.append('animations.categories[%d] 非对象' % i)
                continue
            if not isinstance(c.get('id'), str) or not c.get('id'):
                problems.append('animations.categories[%d].id 缺失/空' % i)
            if not is_num(c.get('weight')) or c.get('weight') < 0:
                problems.append('animations.categories[%d].weight 非数字/负数' % i)
            acts = c.get('actions')
            if not isinstance(acts, list):
                problems.append('animations.categories[%d].actions 缺失/非数组' % i)
            else:
                for j, n in enumerate(acts):
                    if not isinstance(n, str) or not n:
                        problems.append('animations.categories[%d].actions[%d] 非字符串/空' % (i, j))
                    else:
                        refs.append((n, 'animations.categories[%d].actions[%d]' % (i, j)))
    ev = anim.get('events')
    if not isinstance(ev, dict) or not ev:
        problems.append('animations.events 缺失/非对象/空')
    else:
        if 'balance' not in ev:
            problems.append('animations.events.balance 缺失')
        for pool_name, pool in ev.items():
            if not isinstance(pool, list) or len(pool) == 0:
                problems.append('animations.events.%s 非数组或空' % pool_name)
                continue
            if pool_name == 'balance' and len(pool) == 0:
                problems.append('animations.events.balance 为空')
            for i, slot in enumerate(pool):
                if isinstance(slot, str):
                    if not slot:
                        problems.append('events.%s[%d] 空字符串' % (pool_name, i))
                    else:
                        refs.append((slot, 'animations.events.%s[%d]' % (pool_name, i)))
                elif isinstance(slot, list):
                    if not slot:
                        problems.append('events.%s[%d] 空候选数组' % (pool_name, i))
                    for j, n in enumerate(slot):
                        if not isinstance(n, str) or not n:
                            problems.append('events.%s[%d][%d] 非法' % (pool_name, i, j))
                        else:
                            refs.append((n, 'animations.events.%s[%d][%d]' % (pool_name, i, j)))
                else:
                    problems.append('events.%s[%d] 槽位类型非法' % (pool_name, i))
    return problems, refs


def load_pack_config(path):
    with open(path, 'r', encoding='utf-8-sig') as f:
        text = f.read()
    try:
        return json.loads(text), 'json'
    except Exception:  # noqa: BLE001
        stripped = re.sub(r'/\*[\s\S]*?\*/', '', text)
        stripped = re.sub(r'(^|[^\\:])//.*$', r'\1', stripped, flags=re.M)
        return json.loads(stripped), 'jsonc'


def v11_checks(packs_dir, pet_dir, expect_active=''):
    """v1.1 行为契约：8 份 config 恰好 1 个 display=both + 7 个 none；统一 size/position；
    持久化 active marker 存在且与 display=both 的角色一致（原地换人，不一次全显示）。"""
    configs = {}
    for fn in sorted(os.listdir(packs_dir)):
        m = re.match(r'^(.+?)-config\.(json|jsonc)$', fn)
        if not m:
            continue
        prefix = m.group(1)
        try:
            cfg, _ = load_pack_config(os.path.join(packs_dir, fn))
        except Exception:  # noqa: BLE001
            continue
        pets = cfg.get('pets') if isinstance(cfg.get('pets'), list) else []
        pet = pets[0] if pets and isinstance(pets[0], dict) else {}
        pos = pet.get('position') if isinstance(pet.get('position'), dict) else {}
        configs[prefix] = {
            'id': pet.get('id'), 'display': pet.get('display'), 'size': pet.get('size'),
            'corner': pos.get('corner'), 'marginX': pos.get('marginX'), 'marginY': pos.get('marginY'),
        }
    marker = None
    marker_path = None
    for cand in (os.path.join(pet_dir, '.dsh-pet-ai-girls-active.json'),
                 os.path.join(packs_dir, '.dsh-pet-ai-girls-active.json')):
        if os.path.isfile(cand):
            marker_path = cand
            try:
                with open(cand, 'r', encoding='utf-8-sig') as f:
                    marker = json.load(f)
            except Exception:  # noqa: BLE001
                marker = {'_parse_error': True}
            break

    displays = {k: v['display'] for k, v in configs.items()}
    is_v11 = any(d == 'none' for d in displays.values()) or marker is not None
    info = {'mode': 'v1.1' if is_v11 else 'v1.0', 'configs': configs,
            'marker': marker, 'marker_path': marker_path,
            'active_id': marker.get('active') if isinstance(marker, dict) else None}
    if not is_v11:
        add('v11.mode', 'v1.1 单角色显示契约', 'SKIP',
            '检测为 v1.0 全显示模式（无 display=none、无 active marker）')
        return info

    both = sorted(k for k, d in displays.items() if d == 'both')
    none = sorted(k for k, d in displays.items() if d == 'none')
    other = sorted(k for k, d in displays.items() if d not in ('both', 'none'))
    add('v11.single_active', '恰好 1 个 pack display=both、其余 display=none',
        'PASS' if len(both) == 1 and len(none) == len(configs) - 1 and not other else 'FAIL',
        'both=%s；none=%d 个%s' % (both, len(none), ('；非法 display=%s' % other) if other else ''))

    if marker_path is None:
        add('v11.marker', 'active marker 存在且合法', 'FAIL',
            '未找到 .dsh-pet-ai-girls-active.json（pet_dir=%s）' % pet_dir)
    elif not isinstance(marker, dict) or marker.get('_parse_error'):
        add('v11.marker', 'active marker 存在且合法', 'FAIL',
            '解析失败: %s' % marker_path)
    else:
        active_id = str(marker.get('active') or '')
        both_prefix = both[0] if both else None
        both_id = str((configs.get(both_prefix) or {}).get('id') or '')
        consistent = bool(active_id) and both_prefix is not None and (
            both_id == active_id or both_id == 'girl-' + active_id or both_id.endswith('-' + active_id))
        add('v11.marker', 'active marker 存在且与 display=both 一致',
            'PASS' if consistent else 'FAIL',
            'active=%r both_prefix=%r both_id=%r path=%s' % (
                active_id, both_prefix, both_id, marker_path))
        if expect_active:
            add('v11.expect_active', '当前 active 与预期一致（%s）' % expect_active,
                'PASS' if active_id == expect_active else 'FAIL',
                '实际 active=%r，预期=%r' % (active_id, expect_active))

    sizes = sorted(set(str(v['size']) for v in configs.values()))
    add('v11.size', '8 个 pack size 统一（原地换人）',
        'PASS' if sizes == ['340'] else 'FAIL',
        'sizes=%s（期望统一 340）' % sizes)
    poss = sorted(set('%s/%s/%s' % (v['corner'], v['marginX'], v['marginY']) for v in configs.values()))
    add('v11.position', '8 个 pack position 统一（原地换人）',
        'PASS' if poss == ['bottom-right/40/40'] else 'FAIL',
        'positions=%s（期望 bottom-right/40/40）' % poss)
    bad_ids = [k for k, v in configs.items() if str(v['id']) != k]
    add('v11.instance_ids', '每份 config pets[0].id == 文件名前缀',
        'PASS' if not bad_ids else 'FAIL', '不一致: %s' % bad_ids)
    return info


def v12_checks(packs_dir, pet_dir, plugin_dir):
    """v1.2 契约：部署 marker=1.2.0；clicks=4（含转圈展示）；categories 单组 weight=24/3 actions；
    animationWeights=76/0/0；packs 媒体总大小与 build/webm 母版一致。"""
    pkg_version = None
    try:
        with open(os.path.join(plugin_dir, 'package.json'), 'r', encoding='utf-8-sig') as f:
            pkg_version = str(json.load(f).get('version') or '')
    except Exception:  # noqa: BLE001
        pass
    marker = None
    marker_path = os.path.join(pet_dir, '.dsh-pet-ai-girls.json')
    if os.path.isfile(marker_path):
        try:
            with open(marker_path, 'r', encoding='utf-8-sig') as f:
                marker = json.load(f)
        except Exception:  # noqa: BLE001
            marker = {'_parse_error': True}
    configs = {}
    for fn in sorted(os.listdir(packs_dir)):
        m = re.match(r'^(.+?)-config\.(json|jsonc)$', fn)
        if not m:
            continue
        try:
            cfg, _ = load_pack_config(os.path.join(packs_dir, fn))
        except Exception:  # noqa: BLE001
            continue
        pet = (cfg.get('pets') or [{}])[0] if isinstance(cfg.get('pets'), list) else {}
        anims = cfg.get('animations') if isinstance(cfg.get('animations'), dict) else {}
        cats = anims.get('categories') if isinstance(anims.get('categories'), list) else []
        configs[m.group(1)] = {
            'clicks': anims.get('clicks') if isinstance(anims.get('clicks'), list) else [],
            'categories': [{'weight': c.get('weight'), 'actions': c.get('actions')}
                           for c in cats if isinstance(c, dict)],
            'weights': cfg.get('animationWeights') if isinstance(cfg.get('animationWeights'), dict) else {},
        }
    marker_version = str((marker or {}).get('version') or '')
    is_v12 = marker_version.startswith('1.2') or any('转圈展示' in c['clicks'] for c in configs.values()) \
        or any(c['weights'].get('idle') == 76 for c in configs.values())
    info = {'mode': 'v1.2' if is_v12 else 'v1.1/other', 'package_json_version': pkg_version,
            'marker_version': marker_version, 'configs': configs}
    if not is_v12:
        add('v12.mode', 'v1.2 三视图 2.5D 转台契约', 'SKIP', '检测为 v1.1 或更早配置（无 2.5D 动画池特征）')
        return info

    # 1) 部署 marker 版本
    if marker is None:
        add('v12.marker', '部署 marker .dsh-pet-ai-girls.json 存在且 version=1.2.0', 'FAIL',
            '未找到 %s' % marker_path)
    else:
        ok = bool(pkg_version) and marker_version == pkg_version
        add('v12.marker', '部署 marker .dsh-pet-ai-girls.json version == package.json',
            'PASS' if ok else 'FAIL',
            'marker.version=%r package.json=%r path=%s' % (marker_version, pkg_version, marker_path))

    # 2) clicks = 4 且含转圈展示
    bad = [k for k, c in configs.items() if len(c['clicks']) != 4 or '转圈展示' not in c['clicks']]
    add('v12.clicks', '8 config clicks=4 且含「转圈展示」', 'PASS' if not bad else 'FAIL',
        ('8/8 符合（%s）' % configs[list(configs)[0]]['clicks']) if not bad else '异常: %s' % bad)

    # 3) categories 单组 weight=24/3 actions（转圈展示/东张西望/伸懒腰）
    want = {'转圈展示', '东张西望', '伸懒腰'}
    bad_cat = []
    for k, c in configs.items():
        cats = c['categories']
        if len(cats) != 1 or cats[0].get('weight') != 24 or len(set(cats[0].get('actions') or [])) != 3 \
                or set(cats[0].get('actions') or []) != want:
            bad_cat.append('%s: %s' % (k, cats))
    add('v12.categories', '8 config categories 单组 weight=24 actions=3（转圈展示/东张西望/伸懒腰）',
        'PASS' if not bad_cat else 'FAIL',
        ('8/8 符合（%s）' % json.dumps(configs[list(configs)[0]]['categories'], ensure_ascii=False))
        if not bad_cat else '; '.join(bad_cat[:4]))

    # 4) animationWeights = 76/0/0
    bad_w = [k for k, c in configs.items()
             if c['weights'].get('idle') != 76 or c['weights'].get('turn') != 0 or c['weights'].get('move') != 0]
    add('v12.weights', '8 config animationWeights=76/0/0', 'PASS' if not bad_w else 'FAIL',
        ('8/8 符合（%s）' % json.dumps(configs[list(configs)[0]]['weights'], ensure_ascii=False))
        if not bad_w else '异常: %s' % bad_w)

    # 5) packs 媒体总数/总大小 == build/webm 母版（证明重渲后打包一致）
    build_webm = os.path.join(PROJECT, 'build', 'webm')
    packs_files = packs_bytes = 0
    for prefix in configs:
        d = os.path.join(packs_dir, '%s-animation' % prefix)
        if os.path.isdir(os.path.join(d, 'webm')):
            d = os.path.join(d, 'webm')
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            fp = os.path.join(d, fn)
            if fn.lower().endswith('.webm') and os.path.isfile(fp):
                packs_files += 1
                packs_bytes += os.path.getsize(fp)
    info['packs_files'] = packs_files
    info['packs_bytes'] = packs_bytes
    if os.path.isdir(build_webm):
        b_files = b_bytes = 0
        for ch in os.listdir(build_webm):
            chd = os.path.join(build_webm, ch)
            if not os.path.isdir(chd):
                continue
            for fn in os.listdir(chd):
                fp = os.path.join(chd, fn)
                if fn.lower().endswith('.webm') and os.path.isfile(fp):
                    b_files += 1
                    b_bytes += os.path.getsize(fp)
        info['build_files'] = b_files
        info['build_bytes'] = b_bytes
        add('v12.media_total', 'packs 媒体总数/总大小与 build/webm 母版一致（重渲后打包一致）',
            'PASS' if (packs_files == b_files and packs_bytes == b_bytes) else 'FAIL',
            'packs=%d 个/%.2f MiB；build/webm=%d 个/%.2f MiB' % (
                packs_files, packs_bytes / 1048576.0, b_files, b_bytes / 1048576.0))
    else:
        add('v12.media_total', 'packs 媒体总数/总大小与 build/webm 母版一致', 'SKIP',
            'build/webm 母版不存在，packs=%d 个/%.2f MiB' % (packs_files, packs_bytes / 1048576.0))
    return info


def v13_checks(packs_dir, pet_dir, plugin_dir):
    """v1.3 契约：Q 版（chibi）资产链 + marker=package.json 版本 + 媒体总量。"""
    pkg_version = None
    try:
        with open(os.path.join(plugin_dir, 'package.json'), 'r', encoding='utf-8-sig') as f:
            pkg_version = str(json.load(f).get('version') or '')
    except Exception:  # noqa: BLE001
        pass
    info = {'package_json_version': pkg_version,
            'ref_sheets': {}, 'sheets': {}, 'chibi': {}, 'gallery_chibi': {}}
    ref_dir = os.path.join(PROJECT, 'reference', 'sheets')
    sheet_dir = os.path.join(PROJECT, 'build', 'sheets')
    chibi_dir = os.path.join(PROJECT, 'build', 'chibi')
    vis_chibi = os.path.join(plugin_dir, 'visual', 'chibi')
    ids = EXPECTED_IDS
    # 1) reference/sheets 8 张设定图
    missing_ref = []
    for cid in ids:
        p = os.path.join(ref_dir, '%s-threeview.webp' % cid)
        if os.path.isfile(p):
            info['ref_sheets'][cid] = os.path.getsize(p)
        else:
            missing_ref.append(cid)
    ref_bytes = sum(info['ref_sheets'].values())
    info['ref_total_bytes'] = ref_bytes
    add('v13.reference_sheets', 'reference/sheets 8 张 ai-chan-sheets 设定图存在（webp）',
        'PASS' if not missing_ref else 'FAIL',
        ('8/8，合计 %.2f MiB' % (ref_bytes / 1048576.0)) if not missing_ref else '缺少: %s' % missing_ref)
    # 2) build/sheets 原始三视图 & 3) build/chibi Q版三视图
    miss_sheets = []
    for cid in ids:
        for v in ('front', 'side', 'back'):
            if not os.path.isfile(os.path.join(sheet_dir, '%s-%s.png' % (cid, v))):
                miss_sheets.append('%s-%s' % (cid, v))
    add('v13.sheets_split', 'build/sheets 原始三视图 front/side/back 齐全（24 张）',
        'PASS' if not miss_sheets else 'FAIL', '24/24' if not miss_sheets else '缺少: %s' % miss_sheets[:8])
    miss_chibi = []
    for cid in ids:
        for v in ('front', 'side', 'back', 'portrait', 'review'):
            p = os.path.join(chibi_dir, '%s-%s.png' % (cid, v))
            if os.path.isfile(p):
                info['chibi']['%s-%s' % (cid, v)] = os.path.getsize(p)
            else:
                miss_chibi.append('%s-%s' % (cid, v))
    lineup = os.path.join(chibi_dir, 'lineup.png')
    add('v13.chibi_assets', 'build/chibi Q版三视图/头像/对比图 齐全（40 张）+ lineup.png',
        'PASS' if not miss_chibi and os.path.isfile(lineup) else 'FAIL',
        ('40/40 + lineup（%dB）' % os.path.getsize(lineup)) if not miss_chibi and os.path.isfile(lineup)
        else '缺少: %s%s' % (miss_chibi[:8], '' if os.path.isfile(lineup) else ' + lineup'))
    # 4) 图鉴 Q 版资源
    miss_gal = []
    for cid in ids:
        for name in ('%s.webp' % cid,):
            p = os.path.join(vis_chibi, name)
            if os.path.isfile(p):
                info['gallery_chibi'][cid] = os.path.getsize(p)
            else:
                miss_gal.append(name)
    gl = os.path.join(vis_chibi, 'lineup.webp')
    gal_ok = not miss_gal and os.path.isfile(gl)
    add('v13.gallery_chibi', 'plugin/visual/chibi Q版头像/lineup 资源齐全',
        'PASS' if gal_ok else 'FAIL',
        '8 webp + lineup.webp' if gal_ok else '缺少: %s%s' % (miss_gal, '' if os.path.isfile(gl) else ' + lineup.webp'))
    # 5) marker 版本（明确 1.3.x == package.json）
    marker_version = None
    mp = os.path.join(pet_dir, '.dsh-pet-ai-girls.json')
    if os.path.isfile(mp):
        try:
            with open(mp, 'r', encoding='utf-8-sig') as f:
                marker_version = str((json.load(f) or {}).get('version') or '')
        except Exception:  # noqa: BLE001
            pass
    info['marker_version'] = marker_version
    add('v13.marker', '部署 marker version == package.json（v1.3.0）',
        'PASS' if marker_version and pkg_version and marker_version == pkg_version else 'FAIL',
        'marker=%r package.json=%r' % (marker_version, pkg_version))
    return info


def main():
    ap = argparse.ArgumentParser(description='Independent pet pack verifier')
    ap.add_argument('--packs-dir', default=os.path.join(PROJECT, 'plugin', 'packs'))
    ap.add_argument('--pet-dir', default=os.path.join(os.path.expanduser('~'), '.dsh', 'dsh-pet', 'pet'),
                    help='已部署的 pet 目录（读 active marker；默认用户 .dsh）')
    ap.add_argument('--expect-active', default='', help='期望当前 active 角色 id（如 deepseek；留空则只比对 marker 一致性）')
    ap.add_argument('--plugin-dir', default=os.path.join(PROJECT, 'plugin'), help='插件目录（读取 package.json 版本）')
    ap.add_argument('--out', default=os.path.join(PROJECT, 'build', 'verify', 'verify_pack.json'))
    ap.add_argument('--no-media', action='store_true', help='skip ffmpeg media probing')
    ap.add_argument('--ffmpeg', default='')
    args = ap.parse_args()

    packs_dir = os.path.abspath(args.packs_dir)
    out_path = os.path.abspath(args.out)
    ffmpeg = args.ffmpeg or find_ffmpeg()
    expected_names, manifest_path = read_expected_anim_names(packs_dir)

    # ---------- 目录级 ----------
    if not os.path.isdir(packs_dir):
        add('packs.dir', 'packs 目录存在', 'FAIL', '目录不存在: %s' % packs_dir)
        write_out(out_path, packs_dir, ffmpeg, expected_names)
        return 1
    add('packs.dir', 'packs 目录存在', 'PASS', packs_dir)

    present_prefixes = []
    for fn in sorted(os.listdir(packs_dir)):
        if fn.endswith('-config.json') or fn.endswith('-config.jsonc'):
            present_prefixes.append(re.sub(r'-config\.(json|jsonc)$', '', fn))
    # 按角色 id 解析实际前缀（接受 <id> / girl-<id> / <任意>-<id>）
    prefix_map = {}
    for pid in EXPECTED_IDS:
        cands = [p for p in present_prefixes if p == pid or p == 'girl-' + pid or p.endswith('-' + pid)]
        if cands:
            cands.sort(key=lambda p: (p != 'girl-' + pid, p != pid, len(p)))
            prefix_map[pid] = cands[0]
    missing_prefixes = [pid for pid in EXPECTED_IDS if pid not in prefix_map]
    mapped = list(prefix_map.values())
    extra_prefixes = [p for p in present_prefixes if p not in mapped]
    if missing_prefixes:
        add('packs.prefixes', '8 个角色前缀齐全', 'FAIL',
            '缺少角色: %s；已发现: %s' % (', '.join(missing_prefixes), ', '.join(present_prefixes)))
    else:
        add('packs.prefixes', '8 个角色前缀齐全', 'PASS',
            '发现: %s' % ', '.join(mapped))
    if extra_prefixes:
        add('packs.extra', '无多余角色前缀', 'WARN', '多余: %s' % ', '.join(extra_prefixes))
    else:
        add('packs.extra', '无多余角色前缀', 'PASS', '')

    pack_summaries = {}
    name_sets = {}
    all_refs_total = 0
    all_files_total = 0
    all_bytes_total = 0
    # 实例 id 必须全局唯一（含 main 条目与全部 pack）
    seen_ids_global = {'main'}

    for pid in EXPECTED_IDS:
        prefix = prefix_map.get(pid)
        if not prefix:
            add('%s.pack' % pid, '%s pet pack 存在' % pid, 'FAIL',
                'packs/ 下未找到 %s-config.json（也接受 girl-%s-config.json）' % (pid, pid))
            continue
        cfg_json = os.path.join(packs_dir, '%s-config.json' % prefix)
        cfg_jsonc = os.path.join(packs_dir, '%s-config.jsonc' % prefix)
        cfg_path = cfg_json if os.path.isfile(cfg_json) else (cfg_jsonc if os.path.isfile(cfg_jsonc) else '')
        anim_dir = os.path.join(packs_dir, '%s-animation' % prefix)
        summary = {'id': pid, 'prefix': prefix, 'config': '', 'animations': 0, 'bytes': 0,
                   'refs': 0, 'missing_refs': [], 'extra_files': [], 'media_fail': 0}
        pack_summaries[pid] = summary

        if not cfg_path:
            add('%s.config.exists' % prefix, '%s config 存在' % prefix, 'FAIL',
                '缺少 %s-config.json' % prefix)
            continue
        summary['config'] = os.path.relpath(cfg_path, PROJECT)
        if cfg_path.endswith('.jsonc'):
            add('%s.config.ext' % prefix, '%s config 扩展名' % prefix, 'WARN',
                '使用 .jsonc；pet pack 部署规范为 <prefix>-config.json（host 也认 jsonc）')
        else:
            add('%s.config.ext' % prefix, '%s config 扩展名' % prefix, 'PASS', '.json')

        # ---- 解析（严格 JSON；失败再按 JSONC 剥注释重试并 WARN）----
        raw = None
        parse_mode = ''
        try:
            with open(cfg_path, 'r', encoding='utf-8-sig') as f:
                text = f.read()
            cfg = json.loads(text)
            parse_mode = 'json'
            raw = cfg
        except Exception as e_strict:  # noqa: BLE001
            try:
                with open(cfg_path, 'r', encoding='utf-8-sig') as f:
                    text = f.read()
                stripped = re.sub(r'/\*[\s\S]*?\*/', '', text)
                stripped = re.sub(r'(^|[^\\:])//.*$', r'\1', stripped, flags=re.M)
                cfg = json.loads(stripped)
                raw = cfg
                parse_mode = 'jsonc'
                add('%s.config.parse' % prefix, '%s config 可解析' % prefix, 'WARN',
                    '严格 JSON 解析失败（%s），JSONC 兼容解析成功（host 可读）' % str(e_strict)[:120])
            except Exception as e:  # noqa: BLE001
                add('%s.config.parse' % prefix, '%s config 可解析' % prefix, 'FAIL',
                    '解析失败: %s' % str(e)[:300])
                continue
        if parse_mode == 'json':
            add('%s.config.parse' % prefix, '%s config 可解析' % prefix, 'PASS', '严格 JSON')
        if not isinstance(raw, dict):
            add('%s.config.object' % prefix, '%s config 顶层对象' % prefix, 'FAIL', '顶层不是对象')
            continue
        add('%s.config.object' % prefix, '%s config 顶层对象' % prefix, 'PASS', '')

        # ---- pets ----
        pets = raw.get('pets')
        if not isinstance(pets, list) or not pets:
            add('%s.pets' % prefix, '%s pets 非空数组' % prefix, 'FAIL',
                'pets 缺失或为空' if not isinstance(pets, list) else 'pets 为空数组')
        else:
            add('%s.pets' % prefix, '%s pets 非空数组' % prefix, 'PASS',
                '%d 个实例: %s' % (len(pets), ', '.join(str(p.get('id')) for p in pets if isinstance(p, dict))))
            for i, pet in enumerate(pets):
                ok, probs = validate_pet(pet, i, seen_ids_global, prefix)
                if ok:
                    add('%s.pet[%d]' % (prefix, i), '%s pets[%d] 字段合法' % (prefix, i), 'PASS',
                        'id=%s name=%s size=%s' % (pet.get('id'), pet.get('name'), pet.get('size')))
                else:
                    add('%s.pet[%d]' % (prefix, i), '%s pets[%d] 字段合法' % (prefix, i), 'FAIL',
                        '; '.join(probs))
            summary['pets'] = len(pets)

        # ---- animations ----
        anim = raw.get('animations')
        probs, refs = validate_animations(anim, prefix)
        if probs:
            add('%s.animations' % prefix, '%s animations 结构合法' % prefix, 'FAIL',
                '; '.join(probs[:12]) + (' ...共%d项' % len(probs) if len(probs) > 12 else ''))
        else:
            add('%s.animations' % prefix, '%s animations 结构合法' % prefix, 'PASS',
                'idle=%d turn=%d drag=%d clicks=%d moves.actions=%d categories=%d events=%s' % (
                    len(anim.get('idle', [])), len(anim.get('turn', [])), len(anim.get('drag', [])),
                    len(anim.get('clicks', [])), len(anim.get('moves', {}).get('actions', [])),
                    len(anim.get('categories', [])),
                    ','.join(anim.get('events', {}).keys()) if isinstance(anim.get('events'), dict) else '?'))

        # ---- animationWeights ----
        aw = raw.get('animationWeights')
        if not isinstance(aw, dict):
            add('%s.weights' % prefix, '%s animationWeights 合法' % prefix, 'FAIL', '缺失/非对象')
        else:
            wprobs = []
            for k in ('idle', 'turn', 'move'):
                v = aw.get(k)
                if not is_num(v) or v < 0:
                    wprobs.append('%s 缺失/非数字/负数: %r' % (k, v))
            if wprobs:
                add('%s.weights' % prefix, '%s animationWeights 合法' % prefix, 'FAIL', '; '.join(wprobs))
            else:
                add('%s.weights' % prefix, '%s animationWeights 合法' % prefix, 'PASS',
                    'idle=%s turn=%s move=%s' % (aw.get('idle'), aw.get('turn'), aw.get('move')))

        # ---- 引用 ⊆ 素材文件 ----
        if not os.path.isdir(anim_dir):
            add('%s.animdir' % prefix, '%s animation 目录存在' % prefix, 'FAIL',
                '目录不存在: %s' % os.path.relpath(anim_dir, PROJECT))
            continue
        add('%s.animdir' % prefix, '%s animation 目录存在' % prefix, 'PASS',
            os.path.relpath(anim_dir, PROJECT))
        # 素材布局两种兼容：host 原生是 <prefix>-animation/<动画名>.webm（扁平）；
        # 交付规范若用 <prefix>-animation/webm/<动画名>.webm（子目录），部署时必须扁平化。
        webm_sub = os.path.join(anim_dir, 'webm')
        if os.path.isdir(webm_sub):
            webm_dir = webm_sub
            summary['layout'] = 'webm-subdir'
        else:
            webm_dir = anim_dir
            summary['layout'] = 'flat'
        if not os.path.isdir(webm_dir):
            add('%s.webmdir' % prefix, '%s webm 目录存在' % prefix, 'FAIL',
                '目录不存在: %s' % os.path.relpath(webm_dir, PROJECT))
            continue
        disk_files = sorted(fn for fn in os.listdir(webm_dir)
                            if fn.lower().endswith('.webm') and os.path.isfile(os.path.join(webm_dir, fn)))
        disk_names = set(os.path.splitext(fn)[0] for fn in disk_files)
        name_sets[prefix] = disk_names
        summary['animations'] = len(disk_files)
        summary['refs'] = len(refs)
        summary['bytes'] = sum(os.path.getsize(os.path.join(webm_dir, f)) for f in disk_files)
        all_files_total += len(disk_files)
        all_bytes_total += summary['bytes']

        if len(disk_files) < len(expected_names):
            add('%s.webm.count' % prefix, '%s webm 数量' % prefix, 'FAIL',
                '%d 个，少于预期的 %d 个' % (len(disk_files), len(expected_names)))
        elif len(disk_files) > len(expected_names):
            add('%s.webm.count' % prefix, '%s webm 数量' % prefix, 'WARN',
                '%d 个，多于预期的 %d 个（多余文件允许）' % (len(disk_files), len(expected_names)))
        else:
            add('%s.webm.count' % prefix, '%s webm 数量' % prefix, 'PASS', '%d 个' % len(disk_files))

        missing_refs = sorted(set(n for n, _ in refs) - disk_names)
        summary['missing_refs'] = missing_refs
        if missing_refs:
            where = {}
            for n, loc in refs:
                if n in missing_refs:
                    where.setdefault(n, []).append(loc)
            detail = '; '.join('%s <- %s' % (n, ','.join(where[n][:3])) for n in missing_refs[:10])
            add('%s.refs' % prefix, '%s 动画引用全部存在' % prefix, 'FAIL',
                '缺失 %d 个: %s' % (len(missing_refs), detail))
        else:
            add('%s.refs' % prefix, '%s 动画引用全部存在' % prefix, 'PASS',
                '%d 处引用全部命中 %d 个素材文件' % (len(refs), len(disk_files)))
        all_refs_total += len(refs)

        expected_missing = sorted(set(expected_names) - disk_names)
        if expected_missing:
            add('%s.webm.expected' % prefix, '%s 预期动画名齐全' % prefix, 'WARN',
                '缺少预期动画: %s' % ', '.join(expected_missing[:8]))
        else:
            add('%s.webm.expected' % prefix, '%s 预期动画名齐全' % prefix, 'PASS',
                '预期 %d 个动画名全部存在' % len(expected_names))

        # ---- 媒体解析 ----
        if not args.no_media:
            if not ffmpeg:
                add('%s.media' % prefix, '%s 媒体校验' % prefix, 'SKIP', '未找到 ffmpeg')
            else:
                bad = []
                for fn in disk_files:
                    fp = os.path.join(webm_dir, fn)
                    info = ffmpeg_probe(ffmpeg, fp)
                    info['prefix'] = prefix
                    files_report.append(info)
                    probs = []
                    if not info['ok']:
                        probs.append('ffmpeg 解析失败: %s' % info['error'])
                    else:
                        if info['width'] != 640 or info['height'] != 360:
                            probs.append('分辨率 %sx%s != 640x360' % (info['width'], info['height']))
                        if info['fps'] is None or abs(info['fps'] - 24.0) > 0.5:
                            probs.append('帧率 %s 不在 24±0.5' % info['fps'])
                        if info['duration'] is None or info['duration'] <= 0.8:
                            probs.append('时长 %ss <= 0.8s' % info['duration'])
                    if info['size'] <= 20 * 1024:
                        probs.append('文件大小 %d <= 20KB' % info['size'])
                    if probs:
                        bad.append({'file': fn, 'problems': probs})
                summary['media_fail'] = len(bad)
                if bad:
                    detail = '; '.join('%s: %s' % (b['file'], '|'.join(b['problems'])) for b in bad[:8])
                    if len(bad) > 8:
                        detail += ' ...共 %d 个文件有问题' % len(bad)
                    add('%s.media' % prefix, '%s 媒体参数合法' % prefix, 'FAIL', detail)
                else:
                    add('%s.media' % prefix, '%s 媒体参数合法' % prefix, 'PASS',
                        '%d 个 webm 全部 640x360/24fps/>0.8s/>20KB' % len(disk_files))

    # ---------- v1.1 行为契约（单角色显示 + active marker + 统一 size/position） ----------
    v11 = v11_checks(packs_dir, os.path.abspath(args.pet_dir), args.expect_active)

    # ---------- v1.2 契约（三视图 2.5D 转台：marker/动画池/权重/媒体总量） ----------
    v12 = v12_checks(packs_dir, os.path.abspath(args.pet_dir), os.path.abspath(args.plugin_dir))

    # ---------- v1.3 契约（Q 版 chibi 资产链） ----------
    v13 = v13_checks(packs_dir, os.path.abspath(args.pet_dir), os.path.abspath(args.plugin_dir))

    # ---------- 跨 pack 一致性与汇总 ----------
    if len(name_sets) == len(EXPECTED_IDS):
        base_prefix = prefix_map[EXPECTED_IDS[0]]
        base_set = name_sets.get(base_prefix, set())
        diffs = []
        for p in list(prefix_map.values())[1:]:
            if name_sets[p] != base_set:
                diffs.append('%s 与 %s 的动画名集合不同（多: %s 少: %s）' % (
                    p, base_prefix,
                    ','.join(sorted(name_sets[p] - base_set)[:5]) or '-',
                    ','.join(sorted(base_set - name_sets[p])[:5]) or '-'))
        if diffs:
            add('packs.consistency', '8 个 pack 动画名集合一致', 'WARN', '; '.join(diffs))
        else:
            add('packs.consistency', '8 个 pack 动画名集合一致', 'PASS',
                '%d 个动画名 × 8 角色' % len(base_set))

    if ffmpeg:
        alpha_ok = sum(1 for f in files_report if f.get('alpha_mode') == 1)
        if files_report:
            add('media.alpha', 'ALPHA_MODE 元数据', 'PASS' if alpha_ok == len(files_report) else 'WARN',
                '%d/%d 个文件 ALPHA_MODE=1（ffmpeg 4.2.2 解码 VP9-alpha 会丢 alpha，属已知限制；'
                'alpha 最终以 Chrome 截图验证）' % (alpha_ok, len(files_report)))

    summary = {
        'packs_dir': packs_dir,
        'expected_ids': EXPECTED_IDS,
        'prefix_map': prefix_map,
        'present_prefixes': present_prefixes,
        'expected_anim_names': expected_names,
        'expected_anim_names_source': manifest_path or 'fallback (build/anim_smoke)',
        'packs': pack_summaries,
        'files_total': all_files_total,
        'bytes_total': all_bytes_total,
        'refs_total': all_refs_total,
        'v11': v11,
        'v12': v12,
        'v13': v13,
    }
    write_out(out_path, packs_dir, ffmpeg, expected_names, summary)
    return 0 if not any(c['status'] == 'FAIL' for c in checks) else 1


def write_out(out_path, packs_dir, ffmpeg, expected_names, summary=None):
    statuses = {}
    for c in checks:
        statuses[c['status']] = statuses.get(c['status'], 0) + 1
    report = {
        'tool': 'tools/verify_pack.py',
        'generated_at': __import__('datetime').datetime.now().isoformat(timespec='seconds'),
        'packs_dir': packs_dir,
        'ffmpeg': ffmpeg,
        'expected_anim_names': expected_names,
        'summary': dict(statuses, files_total=(summary or {}).get('files_total'),
                        bytes_total=(summary or {}).get('bytes_total')),
        'packs': (summary or {}).get('packs', {}),
        'v11': (summary or {}).get('v11'),
        'v12': (summary or {}).get('v12'),
        'v13': (summary or {}).get('v13'),
        'checks': checks,
        'files': files_report,
    }
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print('')
    print('=' * 78)
    print('verify_pack.py  |  packs_dir: %s' % packs_dir)
    print('=' * 78)
    for c in checks:
        mark = {'PASS': 'PASS', 'FAIL': 'FAIL', 'WARN': 'WARN', 'SKIP': 'SKIP'}[c['status']]
        print('[%s] %-46s %s' % (mark, c['name'], c['detail']))
    print('-' * 78)
    print('结果: %s' % ','.join('%s=%d' % (k, statuses.get(k, 0)) for k in ('PASS', 'FAIL', 'WARN', 'SKIP')))
    if summary:
        print('文件数: %d  总大小: %.2f MiB  引用数: %d' % (
            summary['files_total'], summary['bytes_total'] / 1024.0 / 1024.0, summary['refs_total']))
    print('JSON: %s' % out_path)
    print('=' * 78)


if __name__ == '__main__':
    sys.exit(main())
