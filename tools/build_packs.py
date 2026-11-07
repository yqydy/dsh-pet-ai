# -*- coding: utf-8 -*-
"""Generate the dsh-pet pet pack for the 8 AI girls and install it.

Usage:
  python tools/build_packs.py                 # build plugin/packs/ from build/webm/
  python tools/build_packs.py --deploy        # also copy into %USERPROFILE%/.dsh/dsh-pet/pet
  python tools/build_packs.py --deploy --force
"""
import argparse
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import spec  # noqa: E402


def check_sources(source_dir):
    missing = []
    for c in spec.CHARACTERS:
        for anim in spec.ANIM_NAMES:
            p = os.path.join(source_dir, c['id'], anim + '.webm')
            if not os.path.isfile(p) or os.path.getsize(p) < 20 * 1024:
                missing.append(os.path.relpath(p, ROOT))
    return missing


def build(source_dir, plugin_dir):
    packs_dir = os.path.join(plugin_dir, 'packs')
    os.makedirs(packs_dir, exist_ok=True)
    total = 0
    manifest = {'characters': [], 'animations': spec.ANIM_NAMES, 'generatedAt': ''}
    for c in spec.CHARACTERS:
        cfg = spec.config_for(c)
        cfg_path = os.path.join(packs_dir, c['prefix'] + '-config.json')
        with open(cfg_path, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
            f.write('\n')
        anim_dir = os.path.join(packs_dir, c['prefix'] + '-animation')
        os.makedirs(anim_dir, exist_ok=True)
        # drop stale webm files that are not part of this pack
        keep = {a + '.webm' for a in spec.ANIM_NAMES}
        for name in os.listdir(anim_dir):
            if name.endswith('.webm') and name not in keep:
                os.remove(os.path.join(anim_dir, name))
        files = {}
        for anim in spec.ANIM_NAMES:
            src = os.path.join(source_dir, c['id'], anim + '.webm')
            dst = os.path.join(anim_dir, anim + '.webm')
            shutil.copyfile(src, dst)
            size = os.path.getsize(dst)
            total += size
            files[anim] = size
        manifest['characters'].append({
            'id': c['id'], 'prefix': c['prefix'], 'name': c['name'],
            'config': os.path.basename(cfg_path),
            'animationDir': os.path.basename(anim_dir),
            'files': files, 'bytes': sum(files.values()),
        })
        print('%-10s %-18s %2d anims  %6.1f MB' % (
            c['id'], c['prefix'], len(files), sum(files.values()) / 1048576.0))
    manifest['generatedAt'] = __import__('datetime').datetime.now().isoformat(timespec='seconds')
    manifest['totalBytes'] = total
    manifest['totalFiles'] = len(spec.CHARACTERS) * len(spec.ANIM_NAMES)
    with open(os.path.join(ROOT, 'build', 'pack_manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2, default=str)
    print('TOTAL %.1f MB / %d files -> %s' % (total / 1048576.0, manifest['totalFiles'], packs_dir))
    return manifest


def _read_active_id(pet_root):
    """Read the persisted "currently displayed girl" from the active marker."""
    path = os.path.join(pet_root, '.dsh-pet-ai-girls-active.json')
    valid = {c['id'] for c in spec.CHARACTERS}
    try:
        with open(path, encoding='utf-8') as f:
            obj = json.load(f)
        if obj.get('active') in valid:
            return obj['active']
    except Exception:
        pass
    return spec.DEFAULT_ACTIVE_ID


def _apply_active(pet_root, active_id):
    """Rewrite deployed configs so exactly one girl is visible (rest none)."""
    target = next(c for c in spec.CHARACTERS if c['id'] == active_id)
    changed = 0
    for c in spec.CHARACTERS:
        path = os.path.join(pet_root, c['prefix'] + '-config.json')
        if not os.path.isfile(path):
            continue
        with open(path, encoding='utf-8') as f:
            cfg = json.load(f)
        pets = cfg.get('pets') or []
        if not pets:
            continue
        pets[0]['display'] = 'both' if c['id'] == target['id'] else 'none'
        pets[0]['size'] = spec.PET_SIZE
        pets[0]['position'] = {
            'corner': spec.PET_CORNER,
            'marginX': spec.PET_MARGIN_X,
            'marginY': spec.PET_MARGIN_Y,
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
            f.write('\n')
        changed += 1
    with open(os.path.join(pet_root, '.dsh-pet-ai-girls-active.json'), 'w', encoding='utf-8') as f:
        json.dump({'active': target['id'], 'prefix': target['prefix'], 'name': target['name'],
                   'updatedAt': __import__('datetime').datetime.now().isoformat(timespec='seconds')},
                  f, ensure_ascii=False, indent=2)
        f.write('\n')
    return changed


def deploy(plugin_dir):
    dsh_home = os.environ.get('DSH_HOME') or os.path.join(os.path.expanduser('~'), '.dsh')
    pet_root = os.path.join(dsh_home, 'dsh-pet', 'pet')
    if not os.path.isdir(os.path.join(dsh_home, 'dsh-pet')):
        print('SKIP deploy: %s not found (dsh-pet not installed?)' % os.path.join(dsh_home, 'dsh-pet'))
        return 0
    os.makedirs(pet_root, exist_ok=True)
    # remember the user's current choice before overwriting configs
    active_id = _read_active_id(pet_root)
    packs_dir = os.path.join(plugin_dir, 'packs')
    n = 0
    for name in sorted(os.listdir(packs_dir)):
        src = os.path.join(packs_dir, name)
        if not (name.endswith('-config.json') or name.endswith('-animation')):
            continue
        dst = os.path.join(pet_root, name)
        if os.path.isdir(src):
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        else:
            shutil.copyfile(src, dst)
        n += 1
    marker = {
        'version': '1.2.0',
        'installedAt': __import__('datetime').datetime.now().isoformat(timespec='seconds'),
        'chars': [c['prefix'] for c in spec.CHARACTERS],
        'source': 'dsh-pet-ai-girls',
    }
    with open(os.path.join(pet_root, '.dsh-pet-ai-girls.json'), 'w', encoding='utf-8') as f:
        json.dump(marker, f, ensure_ascii=False, indent=2)
    changed = _apply_active(pet_root, active_id)
    active = next(c for c in spec.CHARACTERS if c['id'] == active_id)
    print('DEPLOYED %d entries -> %s（当前显示：%s / %s，%d 份配置已同步）'
          % (n, pet_root, active['name'], active_id, changed))
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source-dir', default=os.path.join(ROOT, 'build', 'webm'))
    ap.add_argument('--plugin-dir', default=os.path.join(ROOT, 'plugin'))
    ap.add_argument('--deploy', action='store_true')
    args = ap.parse_args()
    missing = check_sources(args.source_dir)
    if missing:
        print('MISSING %d animation files:' % len(missing))
        for m in missing[:30]:
            print('  -', m)
        if len(missing) > 30:
            print('  ... and %d more' % (len(missing) - 30))
        sys.exit(1)
    build(args.source_dir, args.plugin_dir)
    if args.deploy:
        deploy(args.plugin_dir)


if __name__ == '__main__':
    main()
