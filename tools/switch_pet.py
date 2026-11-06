# -*- coding: utf-8 -*-
"""Switch the currently displayed AI-girl pet (standalone helper for the CLI / scripts).

Mirrors what plugin/index.js does when you use ``/petgirl`` or the gallery buttons:
  1. rewrite the 8 deployed ``girl-*-config.json`` so only the chosen one has
     ``pets[0].display = 'both'`` (the rest become ``'none'``);
  2. persist the choice in ``.dsh-pet-ai-girls-active.json``;
  3. call dsh-pet ``POST /dsh-pet-7340/reload`` so the desktop helper rebuilds the
     pet windows immediately (web overlay picks it up on the next page refresh).

Usage:
  python tools/switch_pet.py                 # show current + choices
  python tools/switch_pet.py qwen            # switch to Qwen 娘
  python tools/switch_pet.py --list
  python tools/switch_pet.py qwen --no-reload
  python tools/switch_pet.py --port 57076 qwen
"""
import argparse
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import spec  # noqa: E402

ACTIVE_MARKER = '.dsh-pet-ai-girls-active.json'
SIZE = spec.PET_SIZE
POSITION = {'corner': spec.PET_CORNER, 'marginX': spec.PET_MARGIN_X, 'marginY': spec.PET_MARGIN_Y}
DEFAULT_ACTIVE = spec.DEFAULT_ACTIVE_ID


def pet_root():
    dsh_home = os.environ.get('DSH_HOME') or os.path.join(os.path.expanduser('~'), '.dsh')
    return os.path.join(dsh_home, 'dsh-pet', 'pet')


def resolve(name):
    value = str(name or '').strip().lower()
    if not value:
        return None
    for c in spec.CHARACTERS:
        if value in (c['id'], c['prefix'], c['prefix'].replace('girl-', ''), c['name'].lower()):
            return c
    for c in spec.CHARACTERS:
        if value in c['name'].lower():
            return c
    return None


def read_active(root):
    try:
        obj = json.load(open(os.path.join(root, ACTIVE_MARKER), encoding='utf-8'))
        if obj.get('active') in {c['id'] for c in spec.CHARACTERS}:
            return obj['active']
    except Exception:
        pass
    return DEFAULT_ACTIVE


def apply_active(active_id):
    root = pet_root()
    if not os.path.isdir(root):
        return False, 'pet pack 目录不存在：%s（dsh-pet 未安装？）' % root
    target = next((c for c in spec.CHARACTERS if c['id'] == active_id), None)
    if target is None:
        return False, '未知角色：%s' % active_id
    changed = 0
    for c in spec.CHARACTERS:
        path = os.path.join(root, c['prefix'] + '-config.json')
        if not os.path.isfile(path):
            continue
        try:
            cfg = json.load(open(path, encoding='utf-8'))
        except Exception as e:
            print('WARN 读取失败 %s: %s' % (path, e))
            continue
        pets = cfg.get('pets') or []
        if not pets:
            continue
        pets[0]['display'] = 'both' if c['id'] == target['id'] else 'none'
        pets[0]['size'] = SIZE
        pets[0]['position'] = dict(POSITION)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
            f.write('\n')
        changed += 1
    with open(os.path.join(root, ACTIVE_MARKER), 'w', encoding='utf-8') as f:
        json.dump({'active': target['id'], 'prefix': target['prefix'], 'name': target['name'],
                   'updatedAt': __import__('datetime').datetime.now().isoformat(timespec='seconds')},
                  f, ensure_ascii=False, indent=2)
        f.write('\n')
    return True, '已切换为 %s（写入 %d 份配置）' % (target['name'], changed)


def reload_desktop(port):
    url = 'http://127.0.0.1:%d/dsh-pet-7340/reload' % port
    req = urllib.request.Request(url, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status == 200, 'HTTP %d' % r.status
    except Exception as e:
        return False, str(e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('character', nargs='?', default='')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--port', type=int, default=57076)
    ap.add_argument('--no-reload', action='store_true')
    ap.add_argument('--status', action='store_true')
    args = ap.parse_args()
    root = pet_root()
    current = read_active(root)
    names = '；'.join('%s=%s' % (c['id'], c['name']) for c in spec.CHARACTERS)
    if args.list or args.status or not args.character:
        cur = next(c for c in spec.CHARACTERS if c['id'] == current)
        print('当前桌宠：%s（%s）' % (cur['name'], cur['prefix']))
        print('可选：' + names)
        print('用法：python tools/switch_pet.py <id 或名字>')
        return 0
    target = resolve(args.character)
    if target is None:
        print('找不到角色「%s」。可选：%s' % (args.character, names))
        return 2
    ok, msg = apply_active(target['id'])
    print(('OK  ' if ok else 'ERR ') + msg)
    if not ok:
        return 1
    if not args.no_reload:
        rok, rmsg = reload_desktop(args.port)
        print(('OK  ' if rok else 'WARN') + ' dsh-pet 桌面重建：' + rmsg +
              ('' if rok else '（桌面窗口会在下次刷新/重启时同步）'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
