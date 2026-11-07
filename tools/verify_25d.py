#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
verify_25d.py —— dsh-pet-ai-girls v1.2「三视图 2.5D 转台」定量证据校验器。

背景：v1.2 用 reference/turnaround-<id>.png 拆分出 正面/侧面/背面 三视图，animlib.TurnCharacter
按 yaw 在 0°/90°/180°/270° 四段间切换（段边缘横向压缩 + 交叉淡化 + 运动模糊），6 个动画改为 2.5D：
  转圈展示(360° 转台 2.8s)、东张西望(左右转身 3.2s)、点击回应-开心跃动、点击回应-害羞惊讶、
  被鼠标拖拽悬空反馈、工作状态-雀跃庆祝。

本脚本只读 build/webm/，用 ffmpeg 解码抽帧 + PIL/numpy 定量分析（不依赖 animlib）：
  1) 转圈展示：0%/27%/52%/77% 四帧 + 0–95% 扫描，验证
     - 侧面剪影宽度明显小于正面（w_side_min / w_front <= 0.90）；
     - 背面帧与正面可区分（剪影 XOR 远大于待机呼吸基线）；
     - 360° 两段侧身窗口都变窄、结尾回到正面；
     - 帧间画面差异显著（换视角）。
  2) 东张西望（8 角色）+ 其余 5 个 2.5D 动画（deepseek）：剪影 XOR / 宽度变化 / 像素差
     显著大于待机呼吸基线 → 证明存在转身/换向，而非原地纸片人微动。
  3) 生成四帧 montage 证据图 build/verify/25d-*.png。
注意：ffmpeg 4.2.2 解码 VP9-alpha 会丢 alpha（背景变黑），剪影分析用亮度阈值，属已知限制。

输出 build/verify/verify_25d.json + stdout 表；有 FAIL 时 exit 1。
用法：python tools/verify_25d.py [--chars deepseek,...] [--out ...]
"""
import argparse
import json
import os
import re
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:  # noqa: BLE001
    pass

import numpy as np
from PIL import Image, ImageDraw

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD_WEBM = os.path.join(PROJECT, 'build', 'webm')
OUT_DIR = os.path.join(PROJECT, 'build', 'verify')
FF_CANDIDATES = [
    os.environ.get('DSH_FFMPEG', ''),
    r'C:\Users\20862\AppData\Roaming\Python\Python38\site-packages\imageio_ffmpeg\binaries\ffmpeg-win64-v4.2.2.exe',
    'ffmpeg',
]
CHARS = ['deepseek', 'gpt', 'claude', 'grok', 'gemini', 'kimi', 'glm', 'qwen']
SPIN = '转圈展示'
TURN_ANIMS = ['东张西望', '点击回应-害羞惊讶', '点击回应-开心跃动',
              '工作状态-雀跃庆祝', '被鼠标拖拽悬空反馈']
IDLE = '待机呼吸'

checks = []
frames_dir = ''


def find_ffmpeg():
    for c in FF_CANDIDATES:
        if c and (c == 'ffmpeg' or os.path.isfile(c)):
            return c
    return None


def add(cid, name, status, detail='', evidence=None):
    checks.append({'id': cid, 'name': name, 'status': status, 'detail': detail, 'evidence': evidence})
    print('[%s] %-52s %s' % (status, name, detail))


def probe_duration(ff, path):
    r = subprocess.run([ff, '-hide_banner', '-i', path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    err = (r.stderr or b'').decode('utf-8', errors='replace')
    m = re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', err)
    if not m:
        return None
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def grab(ff, path, t, tag):
    out = os.path.join(frames_dir, tag + '.png')
    subprocess.run([ff, '-hide_banner', '-loglevel', 'error', '-i', path,
                    '-ss', '%.3f' % t, '-frames:v', '1', '-y', out],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    a = np.asarray(Image.open(out).convert('RGB')).astype(np.int32)
    mask = a.max(axis=2) > 16
    cols = np.where(mask.any(axis=0))[0]
    rows = np.where(mask.any(axis=1))[0]
    return {
        't': round(t, 3),
        'arr': a, 'mask': mask,
        'w': int(cols.max() - cols.min() + 1) if len(cols) else 0,
        'h': int(rows.max() - rows.min() + 1) if len(rows) else 0,
        'area': round(float(mask.mean()), 4),
        'png': os.path.relpath(out, PROJECT),
    }


def chg(a, b):
    return round(float((np.abs(a['arr'] - b['arr']).max(axis=2) > 24).mean()), 4)


def mad(a, b):
    return round(float(np.abs(a['arr'] - b['arr']).mean()), 2)


def xorf(a, b):
    return round(float((a['mask'] ^ b['mask']).mean()), 4)


def iou(a, b):
    inter = int((a['mask'] & b['mask']).sum())
    union = int((a['mask'] | b['mask']).sum())
    return round(inter / union, 3) if union else 0.0


ANIM_ASCII = {
    '转圈展示': 'spin', '东张西望': 'look-around', '点击回应-害羞惊讶': 'click-shy',
    '点击回应-开心跃动': 'click-happy', '工作状态-雀跃庆祝': 'work-celebrate',
    '被鼠标拖拽悬空反馈': 'drag', '待机呼吸': 'idle',
}


def ascii_label(s):
    """PIL 7.2 默认字体只支持 latin-1；标签统一转 ASCII（用于 montage 标注）。"""
    try:
        return s.encode('ascii', 'replace').decode('ascii')
    except Exception:  # noqa: BLE001
        return 'label'


def build_montage(entries, out_path):
    """entries: [{'png':..., 'label':...}] 横向拼接并标注（ASCII 标签）。"""
    try:
        ims = [Image.open(os.path.join(PROJECT, e['png'])).convert('RGB') for e in entries]
    except Exception:  # noqa: BLE001
        return None
    H = 360
    pad, top = 10, 24
    scaled = [im.resize((int(im.width * H / im.height), H), Image.LANCZOS) for im in ims]
    W = pad * (len(scaled) + 1) + sum(i.width for i in scaled)
    canvas = Image.new('RGB', (W, H + top + pad), (14, 16, 22))
    x = pad
    draw = ImageDraw.Draw(canvas)
    for e, im in zip(entries, scaled):
        canvas.paste(im, (x, top))
        draw.text((x + 2, 6), ascii_label(e['label']), fill=(150, 220, 255))
        x += im.width + pad
    canvas.save(out_path, 'PNG')
    return os.path.relpath(out_path, PROJECT)


def analyze_idle(ff, char, tag_prefix):
    """待机呼吸基线：4 帧，返回 (xorf_max, width_var, chg_max, frames)。"""
    path = os.path.join(BUILD_WEBM, char, IDLE + '.webm')
    d = probe_duration(ff, path)
    if not d:
        return None
    fr = [grab(ff, path, f * d, '%s-idle-%d' % (tag_prefix, i)) for i, f in enumerate((0.15, 0.40, 0.65, 0.85))]
    xo = max(xorf(fr[0], fr[i]) for i in (1, 2, 3))
    cg = max(chg(fr[0], fr[i]) for i in (1, 2, 3))
    widths = [f['w'] for f in fr]
    return {'xorf_max': xo, 'chg_max': cg, 'width_var': round(max(widths) / max(1, min(widths)), 3),
            'widths': widths, 'frames': fr}


def analyze_spin(ff, char, idle, tag_prefix):
    path = os.path.join(BUILD_WEBM, char, SPIN + '.webm')
    d = probe_duration(ff, path)
    if not d:
        return None, None
    front = grab(ff, path, max(0.02, 0.02 * d), '%s-spin-front' % tag_prefix)
    pts = {}
    for pct in (0.27, 0.52, 0.77):
        fr = grab(ff, path, max(0.02, pct * d), '%s-spin-%d' % (tag_prefix, int(pct * 100)))
        pts[pct] = fr
    grid = []
    for pct in (0, 5, 10, 15, 20, 25, 27, 30, 35, 40, 45, 50, 52, 55, 60, 65, 70, 75, 77, 80, 85, 90, 95):
        t = max(0.02, pct / 100.0 * d)
        fr = grab(ff, path, t, '%s-spin-g%02d' % (tag_prefix, pct))
        fr['pct'] = pct
        fr['chg_vs_front'] = chg(front, fr)
        fr['xorf_vs_front'] = xorf(front, fr)
        fr['mad_vs_front'] = mad(front, fr)
        fr['iou_vs_front'] = iou(front, fr)
        grid.append(fr)
    side_win = [f for f in grid if 15 <= f['pct'] <= 35]
    back_win = [f for f in grid if 30 <= f['pct'] <= 65]
    side2_win = [f for f in grid if 65 <= f['pct'] <= 85]
    side_min = min(side_win, key=lambda f: f['w'])
    side2_min = min(side2_win, key=lambda f: f['w'])
    back_best = max(back_win, key=lambda f: f['xorf_vs_front'])
    end = [f for f in grid if f['pct'] >= 90]
    end_w = end[0]['w'] if end else 0
    metrics = {
        'duration': round(d, 3), 'front': {k: front[k] for k in ('t', 'w', 'h', 'area', 'png')},
        'at_27': {k: pts[0.27][k] for k in ('t', 'w', 'h', 'area', 'png')},
        'at_52': {k: pts[0.52][k] for k in ('t', 'w', 'h', 'area', 'png')},
        'at_77': {k: pts[0.77][k] for k in ('t', 'w', 'h', 'area', 'png')},
        'diff_front_27': chg(front, pts[0.27]), 'mad_front_27': mad(front, pts[0.27]),
        'xorf_front_27': xorf(front, pts[0.27]), 'iou_front_27': iou(front, pts[0.27]),
        'diff_front_52': chg(front, pts[0.52]), 'xorf_front_52': xorf(front, pts[0.52]),
        'side_min': {'pct': side_min['pct'], 'w': side_min['w'], 'png': side_min['png']},
        'side2_min': {'pct': side2_min['pct'], 'w': side2_min['w'], 'png': side2_min['png']},
        'back_best': {'pct': back_best['pct'], 'xorf': back_best['xorf_vs_front'],
                      'chg': back_best['chg_vs_front'], 'png': back_best['png']},
        'end_w': end_w,
        'width_ratio_27': round(pts[0.27]['w'] / max(1, front['w']), 3),
        'side_min_ratio': round(side_min['w'] / max(1, front['w']), 3),
        'side2_min_ratio': round(side2_min['w'] / max(1, front['w']), 3),
        'end_ratio': round(end_w / max(1, front['w']), 3),
        'grid': [{k: f[k] for k in ('pct', 'w', 'area', 'chg_vs_front', 'xorf_vs_front', 'iou_vs_front')} for f in grid],
    }
    montage = build_montage([
        {'png': metrics['front']['png'], 'label': '%s spin 0%%' % char},
        {'png': metrics['at_27']['png'], 'label': '27% (side min)'},
        {'png': metrics['at_52']['png'], 'label': '52% (back)'},
        {'png': metrics['at_77']['png'], 'label': '77% (side)'},
    ], os.path.join(OUT_DIR, '25d-montage-%s.png' % char))
    metrics['montage'] = montage
    return metrics, pts


def analyze_action(ff, char, anim, idle, tag_prefix):
    path = os.path.join(BUILD_WEBM, char, anim + '.webm')
    d = probe_duration(ff, path)
    if not d:
        return None
    fr = [grab(ff, path, f * d, '%s-act-%d' % (tag_prefix, i)) for i, f in enumerate((0.15, 0.40, 0.65))]
    xo = max(xorf(fr[0], fr[1]), xorf(fr[1], fr[2]), xorf(fr[0], fr[2]))
    cg = max(chg(fr[0], fr[1]), chg(fr[1], fr[2]), chg(fr[0], fr[2]))
    md = max(mad(fr[0], fr[1]), mad(fr[1], fr[2]), mad(fr[0], fr[2]))
    widths = [f['w'] for f in fr]
    return {
        'duration': round(d, 3), 'xorf': xo, 'chg': cg, 'mad': md,
        'width_var': round(max(widths) / max(1, min(widths)), 3), 'widths': widths,
        'frames': {k: {kk: fr[i][kk] for kk in ('t', 'w', 'h', 'area', 'png')}
                   for i, k in enumerate(('p15', 'p40', 'p65'))},
        'frame_pngs': [fr[0]['png'], fr[1]['png'], fr[2]['png']],
    }


def main():
    global frames_dir
    ap = argparse.ArgumentParser(description='v1.2 2.5D turntable quantitative verifier')
    ap.add_argument('--chars', default=','.join(CHARS))
    ap.add_argument('--out', default=os.path.join(OUT_DIR, 'verify_25d.json'))
    ap.add_argument('--ffmpeg', default='')
    args = ap.parse_args()
    ff = args.ffmpeg or find_ffmpeg()
    if not ff:
        print('ffmpeg not found')
        return 1
    frames_dir = os.path.join(OUT_DIR, '25d-frames')
    os.makedirs(frames_dir, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)
    chars = [c.strip() for c in args.chars.split(',') if c.strip()]

    spin_metrics = {}
    idle_metrics = {}
    ok_all = True
    for char in chars:
        idle = analyze_idle(ff, char, char)
        if idle is None:
            add('idle.%s' % char, '%s 待机呼吸可解码' % char, 'FAIL', 'webm 缺失或无法解码')
            ok_all = False
            continue
        idle_metrics[char] = {k: idle[k] for k in ('xorf_max', 'chg_max', 'width_var', 'widths')}
        m, _ = analyze_spin(ff, char, idle, char)
        if m is None:
            add('spin.%s' % char, '%s 转圈展示可解码' % char, 'FAIL', 'webm 缺失或无法解码')
            ok_all = False
            continue
        spin_metrics[char] = m
        # 检查 1：侧面剪影明显变窄（取 15–35% 窗口最窄帧）
        r = m['side_min_ratio']
        st = 'PASS' if r <= 0.90 else 'FAIL'
        ok_all &= st == 'PASS'
        add('spin.%s.side_width' % char, '%s 侧面剪影变窄（side_min/front ≤ 0.90）' % char, st,
            'side_min@%d%% w=%d / front w=%d = %.3f；27%% 帧 w=%d ratio=%.3f' % (
                m['side_min']['pct'], m['side_min']['w'], m['front']['w'], r,
                m['at_27']['w'], m['width_ratio_27']))
        # 检查 2：背面帧与正面可区分（剪影 XOR 远大于待机基线）
        back_ok = m['back_best']['xorf'] >= max(0.03, 2.0 * idle['xorf_max']) and m['back_best']['chg'] >= 0.10
        ok_all &= back_ok
        add('spin.%s.back_distinct' % char, '%s 背面与正面可区分（xorf ≥ max(0.03,2×待机) 且像素差≥0.10）' % char,
            'PASS' if back_ok else 'FAIL',
            'back_best@%d%% xorf=%.4f（待机 xorf_max=%.4f）chg=%.4f' % (
                m['back_best']['pct'], m['back_best']['xorf'], idle['xorf_max'], m['back_best']['chg']))
        # 检查 3：帧间画面差异显著（相对待机基线）
        motion_ok = (m['diff_front_27'] >= max(0.08, 1.25 * idle['chg_max'])
                     or m['xorf_front_27'] >= max(0.02, 1.8 * idle['xorf_max']))
        ok_all &= motion_ok
        add('spin.%s.motion' % char, '%s 27%% 帧画面差异显著（chg≥max(0.08,1.25×待机) 或 xorf≥max(0.02,1.8×待机)）' % char,
            'PASS' if motion_ok else 'FAIL',
            'chg(0→27%%)=%.4f mad=%.2f（待机 chg_max=%.4f）xorf=%.4f（待机 xorf_max=%.4f）' % (
                m['diff_front_27'], m['mad_front_27'], idle['chg_max'], m['xorf_front_27'], idle['xorf_max']))
        # 检查 4：360° 覆盖（两段侧身窗口都变窄 + 结尾回正）
        cover_ok = m['side2_min_ratio'] <= 0.92 and 0.93 <= m['end_ratio'] <= 1.07
        ok_all &= cover_ok
        add('spin.%s.360' % char, '%s 360° 转台覆盖（另一侧也变窄 + 结尾回正）' % char,
            'PASS' if cover_ok else 'FAIL',
            '另一侧 side_min@%d%% ratio=%.3f；结尾(≥90%%)w=%d / front w=%d = %.3f' % (
                m['side2_min']['pct'], m['side2_min_ratio'], m['end_w'], m['front']['w'], m['end_ratio']))

    # 转身动画（东张西望：全 8 角色；其余 5 个：deepseek）
    action_metrics = {}
    for char in chars:
        idle = idle_metrics.get(char)
        if not idle:
            continue
        anims = list(TURN_ANIMS) if char == 'deepseek' else ['东张西望']
        for anim in anims:
            tag = '%s-%s' % (char, anim.replace('点击回应-', 'click-').replace('工作状态-', 'work-')
                             .replace('被鼠标拖拽悬空反馈', 'drag'))
            am = analyze_action(ff, char, anim, None, tag[:80])
            if am is None:
                continue
            action_metrics.setdefault(char, {})[anim] = am
            xo_ratio = am['xorf'] / max(idle['xorf_max'], 1e-6)
            turn_ok = (am['xorf'] >= max(0.02, 2.0 * idle['xorf_max'])) or (am['width_var'] >= 1.10)
            ok_all &= turn_ok
            add('turn.%s.%s' % (char, tag), '%s %s 有转身/换向（剪影 XOR 或宽度变化显著）' % (char, anim),
                'PASS' if turn_ok else 'FAIL',
                'xorf=%.4f（待机 xorf_max=%.4f，%.1f×）chg=%.4f width_var=%.3f widths=%s' % (
                    am['xorf'], idle['xorf_max'], xo_ratio, am['chg'], am['width_var'], am['widths']))

    # deepseek 六动作 montage
    if 'deepseek' in action_metrics:
        entries = []
        for anim in [SPIN] + TURN_ANIMS:
            if anim in action_metrics['deepseek']:
                entries.append({'png': action_metrics['deepseek'][anim]['frame_pngs'][1],
                                'label': 'deepseek ' + ANIM_ASCII.get(anim, 'anim')})
        try:
            mt = build_montage(entries, os.path.join(OUT_DIR, '25d-actions-deepseek.png')) if entries else None
        except Exception as e:  # noqa: BLE001
            mt = None
            add('montage.actions', '动作 montage 生成', 'WARN', str(e))
    else:
        mt = None

    statuses = {}
    for c in checks:
        statuses[c['status']] = statuses.get(c['status'], 0) + 1
    report = {
        'tool': 'tools/verify_25d.py',
        'generated_at': __import__('datetime').datetime.now().isoformat(timespec='seconds'),
        'build_webm': BUILD_WEBM,
        'note': 'ffmpeg 4.2.2 解码 VP9-alpha 丢 alpha（背景黑），剪影用亮度阈值；帧时间按 0/27/52/77% 与 5% 扫描',
        'summary': dict(statuses),
        'idle': idle_metrics,
        'spin': spin_metrics,
        'actions': action_metrics,
        'montages': {'actions_deepseek': mt,
                     'spin': {c: m.get('montage') for c, m in spin_metrics.items()}},
        'checks': checks,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print('')
    print('=' * 88)
    print('verify_25d.py  |  2.5D 转台定量证据  |  chars=%s' % ','.join(chars))
    print('=' * 88)
    print('结果: %s' % ','.join('%s=%d' % (k, statuses.get(k, 0)) for k in ('PASS', 'FAIL', 'WARN', 'SKIP')))
    print('JSON: %s' % args.out)
    print('=' * 88)
    return 0 if not any(c['status'] == 'FAIL' for c in checks) else 1


if __name__ == '__main__':
    sys.exit(main())
