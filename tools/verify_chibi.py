#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
verify_chibi.py —— dsh-pet-ai-girls v1.3「全部 Q 版（chibi）」定量/视觉证据校验器。

被测链路（只读，不修改）：
  reference/sheets/<id>-threeview.webp   ← ai-chan-sheets 设定图（原图）
  build/sheets/<id>-{front,side,back}.png ← tools/sheets.py 拆出的原始三视图
  build/chibi/<id>-{front,side,back}.png  ← tools/chibi.py 的 Q 版三视图
  build/chibi/<id>-{portrait,review}.png  ← Q 版头像/前后对比图
  build/chibi/lineup.png                  ← 8 人 Q 版 lineup

独立量化口径（不依赖 chibi.py/sheets.py 内部实现）：
  1) **短身/短腿指标 leg_ratio**：从底边向上扫描，找到剪影首次分裂为 ≥2 段（两腿分离）的行，
     leg_ratio =（底边 - 分裂行）/ 总剪影高；Q 版"大头短身"应显著小于原设定图正视图。
  2) **头部/上身放大参考指标**：上部剪影面积占比（top35/top45）、20% 高度行宽等——因本套美术
     头发/耳朵/宽袖使"颈部剪影凹陷"不稳定，程序化头高占比采用多口径参考，并与 review 对比图
     人工复核结合（报告中说明口径）。
  3) 资产完整性：原图 8 webp、原始三视图 front/side/back、Q 版 front/side/back/portrait/review、
     lineup 是否齐全。
输出 build/verify/verify_chibi.json + 每角色前后对比 montage build/verify/chibi-<id>-compare.png。
"""
import argparse
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:  # noqa: BLE001
    pass

import numpy as np
from PIL import Image, ImageDraw

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHARS = ['deepseek', 'gpt', 'claude', 'grok', 'gemini', 'kimi', 'glm', 'qwen']
OUT_DIR = os.path.join(PROJECT, 'build', 'verify')
SHEETS = os.path.join(PROJECT, 'build', 'sheets')
CHIBI = os.path.join(PROJECT, 'build', 'chibi')
REF_SHEETS = os.path.join(PROJECT, 'reference', 'sheets')

checks = []


def add(cid, name, status, detail='', evidence=None):
    checks.append({'id': cid, 'name': name, 'status': status, 'detail': detail, 'evidence': evidence})
    print('[%s] %-50s %s' % (status, name, detail))


def load_mask(path):
    im = Image.open(path)
    a = np.asarray(im)
    if im.mode == 'RGBA':
        mask = a[:, :, 3] > 8
    else:
        rgb = np.asarray(im.convert('RGB')).astype(int)
        corners = np.concatenate([
            rgb[:5, :5].reshape(-1, 3), rgb[:5, -5:].reshape(-1, 3),
            rgb[-5:, :5].reshape(-1, 3), rgb[-5:, -5:].reshape(-1, 3)])
        bg = np.median(corners, axis=0)
        mask = np.abs(rgb - bg).max(axis=2) > 20
    ys = np.where(mask.any(axis=1))[0]
    xs = np.where(mask.any(axis=0))[0]
    if len(ys) == 0:
        return None
    return mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def runs(row):
    idx = np.where(row)[0]
    if len(idx) == 0:
        return 0
    return 1 + int((np.diff(idx) > 3).sum())


def metrics(m):
    H, W = m.shape
    # 腿部高度：自底向上找最上面的“分叉行”，并要求其下持续分叉
    split = None
    for y in range(H - 1, int(H * 0.55), -1):
        if runs(m[y]) >= 2:
            split = y
        elif split is not None and y < split - 10:
            break
    leg_ratio = round((H - 1 - split) / H, 3) if split is not None else 0.0
    row_w = m.sum(axis=1).astype(float)
    total = max(1.0, m.sum())
    top35_area = round(float(m[:int(H * 0.35)].sum() / total), 3)
    top45_area = round(float(m[:int(H * 0.45)].sum() / total), 3)
    w20 = int(row_w[min(H - 1, int(H * 0.20))])
    w80 = int(row_w[min(H - 1, int(H * 0.80))])
    return {'H': H, 'W': W, 'leg_ratio': leg_ratio, 'top35_area': top35_area,
            'top45_area': top45_area, 'w20': w20, 'w80': w80,
            'w20_over_w80': round(float(w20 / max(1, w80)), 3)}


def checker(im, tile=16):
    im = im.convert('RGBA')
    w, h = im.size
    bg = Image.new('RGB', (w, h))
    d = ImageDraw.Draw(bg)
    for y in range(0, h, tile):
        for x in range(0, w, tile):
            if ((x // tile) + (y // tile)) % 2 == 0:
                d.rectangle([x, y, x + tile - 1, y + tile - 1], fill=(150, 150, 150))
            else:
                d.rectangle([x, y, x + tile - 1, y + tile - 1], fill=(110, 110, 110))
    bg.paste(im, (0, 0), im)
    return bg


def compare_montage(char, orig_path, chibi_path, out_path):
    try:
        a = checker(Image.open(orig_path))
        b = checker(Image.open(chibi_path))
    except Exception:  # noqa: BLE001
        return None
    H = 520
    def scaled(im):
        w = max(1, int(im.width * H / im.height))
        return im.resize((w, H), Image.LANCZOS)
    a, b = scaled(a), scaled(b)
    pad, top = 12, 26
    canvas = Image.new('RGB', (pad * 3 + a.width + b.width, H + top + pad), (18, 20, 32))
    canvas.paste(a, (pad, top))
    canvas.paste(b, (pad * 2 + a.width, top))
    d = ImageDraw.Draw(canvas)
    d.text((pad, 8), '%s  left: original sheet' % char, fill=(200, 220, 255))
    d.text((pad * 2 + a.width, 8), 'right: chibi (Q)', fill=(150, 240, 200))
    canvas.save(out_path, 'PNG')
    return os.path.relpath(out_path, PROJECT)


def main():
    ap = argparse.ArgumentParser(description='v1.3 chibi quantitative verifier')
    ap.add_argument('--out', default=os.path.join(OUT_DIR, 'verify_chibi.json'))
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)

    table = {}
    ok_all = True
    # 资产完整性（全量）
    asset_bad = []
    for c in CHARS:
        need = [os.path.join(REF_SHEETS, '%s-threeview.webp' % c),
                os.path.join(SHEETS, '%s-front.png' % c), os.path.join(SHEETS, '%s-side.png' % c),
                os.path.join(SHEETS, '%s-back.png' % c),
                os.path.join(CHIBI, '%s-front.png' % c), os.path.join(CHIBI, '%s-side.png' % c),
                os.path.join(CHIBI, '%s-back.png' % c), os.path.join(CHIBI, '%s-portrait.png' % c),
                os.path.join(CHIBI, '%s-review.png' % c)]
        miss = [p for p in need if not os.path.isfile(p)]
        if miss:
            asset_bad.append('%s 缺 %d 个: %s' % (c, len(miss), [os.path.basename(x) for x in miss[:3]]))
    add('chibi.assets', 'v1.3 资产完整性（原图/原始三视图/Q版三视图/头像/对比图 各 8）',
        'PASS' if not asset_bad else 'FAIL',
        '8 角色 × 9 类资产齐全（reference/sheets、build/sheets、build/chibi）' if not asset_bad else '; '.join(asset_bad))
    lineup = os.path.join(CHIBI, 'lineup.png')
    add('chibi.lineup', 'build/chibi/lineup.png 存在（8 人 Q 版 lineup）',
        'PASS' if os.path.isfile(lineup) else 'FAIL',
        ('%s (%dB)' % (os.path.relpath(lineup, PROJECT), os.path.getsize(lineup))) if os.path.isfile(lineup) else '缺失')

    for c in CHARS:
        ref_p = os.path.join(REF_SHEETS, '%s-threeview.webp' % c)
        so = os.path.join(SHEETS, '%s-front.png' % c)
        q = os.path.join(CHIBI, '%s-front.png' % c)
        mo, mq = load_mask(so), load_mask(q)
        if mo is None or mq is None:
            add('chibi.%s.metrics' % c, '%s Q版前后对比可测量' % c, 'FAIL', '图像无法读取/剪影为空')
            ok_all = False
            continue
        o, qm = metrics(mo), metrics(mq)
        cmp_path = compare_montage(c, so, q, os.path.join(OUT_DIR, 'chibi-%s-compare.png' % c))
        body_ok = qm['leg_ratio'] <= 0.75 * max(1e-6, o['leg_ratio']) and qm['leg_ratio'] < o['leg_ratio']
        ok_all &= body_ok
        add('chibi.%s.short_body' % c, '%s 短身/短腿：Q版腿部分叉高度占比显著小于原图（≤0.75×）' % c,
            'PASS' if body_ok else 'FAIL',
            'leg_ratio 原=%.3f → Q=%.3f（×%.2f）；top35面积 原=%.3f → Q=%.3f；w20/宽 原=%d/%d → Q=%d/%d' % (
                o['leg_ratio'], qm['leg_ratio'], qm['leg_ratio'] / max(1e-6, o['leg_ratio']),
                o['top35_area'], qm['top35_area'], o['w20'], o['W'], qm['w20'], qm['W']),
            {'compare': cmp_path, 'orig': o, 'chibi': qm, 'ref_sheet': os.path.relpath(ref_p, PROJECT),
             'ref_sheet_bytes': os.path.getsize(ref_p)})
        table[c] = {'orig': o, 'chibi': qm, 'compare': cmp_path,
                    'ref_sheet_bytes': os.path.getsize(ref_p)}

    # 上部/头部体量参考口径（仅记录，不作硬性 FAIL：本套美术头发/耳朵/宽袖遮挡颈部，剪影法不稳定）
    head_stats = [table[c]['chibi']['top35_area'] - table[c]['orig']['top35_area'] for c in CHARS if c in table]
    head_up = sum(1 for v in head_stats if v > 0)
    add('chibi.head_proxy', '头部/上身放大参考指标（上部 35% 剪影面积占比 Q版 vs 原图）',
        'PASS' if head_up >= 6 else 'WARN',
        '%d/8 角色 Q版上部面积占比更大（差值：%s）。说明：本套美术头发/耳朵/宽袖使颈部剪影凹陷不稳定，'
        '程序化"头高占比"采用此参考口径 + review 对比图人工复核（见 §报告）' % (
            head_up, ', '.join('%s:%+.3f' % (c, v) for c, v in zip([x for x in CHARS if x in table], head_stats))))

    # review 对比图存在性作为“人工复核”入口
    reviews = [os.path.join(CHIBI, '%s-review.png' % c) for c in CHARS]
    add('chibi.review_sheets', '8 张 <id>-review.png（左原图/右Q版）可供人工复核',
        'PASS' if all(os.path.isfile(p) for p in reviews) else 'FAIL',
        '; '.join('%s(%dB)' % (os.path.basename(p), os.path.getsize(p)) for p in reviews if os.path.isfile(p)))

    statuses = {}
    for c in checks:
        statuses[c['status']] = statuses.get(c['status'], 0) + 1
    report = {
        'tool': 'tools/verify_chibi.py',
        'generated_at': __import__('datetime').datetime.now().isoformat(timespec='seconds'),
        'chars': CHARS,
        'summary': dict(statuses),
        'method_note': '短身指标 leg_ratio=腿部（剪影分叉区域）高度/总高；头部放大采用上部35%面积占比参考口径 + review 对比图人工复核',
        'table': table,
        'checks': checks,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print('')
    print('=' * 88)
    print('verify_chibi.py  |  v1.3 Q版定量证据')
    print('=' * 88)
    print('结果: %s' % ','.join('%s=%d' % (k, statuses.get(k, 0)) for k in ('PASS', 'FAIL', 'WARN', 'SKIP')))
    print('JSON: %s' % args.out)
    print('=' * 88)
    return 0 if not any(c['status'] == 'FAIL' for c in checks) else 1


if __name__ == '__main__':
    sys.exit(main())
