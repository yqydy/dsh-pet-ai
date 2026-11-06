# -*- coding: utf-8 -*-
"""Install the dsh-pet-ai-girls plugin into a DSH profile (desktop).

Steps (all idempotent, backups first):
  1. copy plugin/ -> <profile>/node_modules/dsh-pet-ai-girls
  2. add "file:node_modules/dsh-pet-ai-girls" to profile package.json dependencies
  3. add the bundle to dsh.profile.bundles (right after dsh-pet)
  4. run `pnpm install --lockfile-only --ignore-scripts` (offline; updates pnpm-lock.yaml)
  5. verify lockfile/package.json and plugin import

Usage:
  python tools/install_profile.py --dry-run
  python tools/install_profile.py
  python tools/install_profile.py --uninstall
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN_SRC = os.path.join(ROOT, 'plugin')
PROFILE = os.path.join(os.path.expanduser('~'), '.dsh', 'profiles', 'desktop')
PKG_NAME = 'dsh-pet-ai-girls'
NODE = r'D:\node\node.exe'
PNPM = r'E:\xiazai\dsh\resources\runtime\primary-runtime\dependencies\pnpm\bin\pnpm.mjs'


def backup(path):
    if not os.path.exists(path):
        return None
    dst = path + '.bak-dshpetgirls-' + time.strftime('%Y%m%d-%H%M%S')
    shutil.copyfile(path, dst)
    return dst


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def dump_json(path, obj):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write('\n')


def patch_package_json(path, dry):
    pkg = load_json(path)
    changed = []
    deps = pkg.setdefault('dependencies', {})
    spec = 'file:node_modules/' + PKG_NAME
    if deps.get(PKG_NAME) != spec:
        deps[PKG_NAME] = spec
        changed.append('dependency')
    bundles = pkg.get('dsh', {}).get('profile', {}).get('bundles')
    if not isinstance(bundles, list):
        raise SystemExit('profile package.json missing dsh.profile.bundles: ' + path)
    if PKG_NAME not in bundles:
        idx = bundles.index('dsh-pet') + 1 if 'dsh-pet' in bundles else len(bundles)
        bundles.insert(idx, PKG_NAME)
        changed.append('bundle')
    if changed and not dry:
        dump_json(path, pkg)
    return changed, bundles


def uninstall_package_json(path):
    pkg = load_json(path)
    deps = pkg.get('dependencies', {})
    deps.pop(PKG_NAME, None)
    bundles = pkg.get('dsh', {}).get('profile', {}).get('bundles', [])
    if PKG_NAME in bundles:
        bundles.remove(PKG_NAME)
    dump_json(path, pkg)


def copy_plugin(dry):
    dst = os.path.join(PROFILE, 'node_modules', PKG_NAME)
    if not dry:
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        shutil.copytree(PLUGIN_SRC, dst)
    return dst, sum(len(files) for _, _, files in os.walk(PLUGIN_SRC)), \
        sum(os.path.getsize(os.path.join(dp, f)) for dp, _, files in os.walk(PLUGIN_SRC) for f in files)


def run_pnpm_lockfile_only(dry):
    cmd = [NODE, PNPM, 'install', '--lockfile-only', '--ignore-scripts', '--dir', PROFILE]
    if dry:
        return 0, ' '.join(cmd)
    r = subprocess.run(cmd, cwd=PROFILE, capture_output=True, timeout=600)
    out = ((r.stdout or b'') + (r.stderr or b'')).decode('utf-8', errors='replace')
    return r.returncode, out[-2000:]


def verify():
    problems = []
    pkg_path = os.path.join(PROFILE, 'package.json')
    lock_path = os.path.join(PROFILE, 'pnpm-lock.yaml')
    with open(lock_path, encoding='utf-8') as f:
        lock = f.read()
    if PKG_NAME not in lock:
        problems.append('lockfile missing ' + PKG_NAME)
    pkg = load_json(pkg_path)
    if pkg.get('dependencies', {}).get(PKG_NAME) != 'file:node_modules/' + PKG_NAME:
        problems.append('package.json dependency missing')
    if PKG_NAME not in pkg.get('dsh', {}).get('profile', {}).get('bundles', []):
        problems.append('bundle entry missing')
    dst = os.path.join(PROFILE, 'node_modules', PKG_NAME)
    for rel in ['package.json', 'index.js', 'cordis.patch.yml', 'visual/index.html']:
        if not os.path.exists(os.path.join(dst, rel)):
            problems.append('installed file missing: ' + rel)
    if not os.path.isdir(os.path.join(dst, 'packs')):
        problems.append('installed packs/ missing')
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--uninstall', action='store_true')
    args = ap.parse_args()
    if not os.path.isdir(PROFILE):
        raise SystemExit('profile not found: ' + PROFILE)
    pkg_path = os.path.join(PROFILE, 'package.json')
    lock_path = os.path.join(PROFILE, 'pnpm-lock.yaml')

    print('profile :', PROFILE)
    print('dry-run :', args.dry_run)
    b1 = b2 = None
    if not args.dry_run:
        b1 = backup(pkg_path)
        b2 = backup(lock_path)
        print('backups :', b1, '|', b2)

    if args.uninstall:
        dst = os.path.join(PROFILE, 'node_modules', PKG_NAME)
        if not args.dry_run:
            uninstall_package_json(pkg_path)
            shutil.rmtree(dst, ignore_errors=True)
            code, out = run_pnpm_lockfile_only(False)
            print('pnpm rc :', code)
            print('pnpm out:', out[-800:])
        print('UNINSTALLED', PKG_NAME)
        return

    changed, bundles = patch_package_json(pkg_path, args.dry_run)
    print('package.json changes:', changed or 'none')
    print('bundles:', bundles)
    dst, nfiles, nbytes = copy_plugin(args.dry_run)
    print('plugin copy: %s (%d files, %.1f MB)%s' % (dst, nfiles, nbytes / 1048576.0,
                                                    ' [dry-run skipped]' if args.dry_run else ''))
    code, out = run_pnpm_lockfile_only(args.dry_run)
    print('pnpm rc:', code)
    try:
        print('pnpm out:', out[-1200:])
    except UnicodeEncodeError:
        print('pnpm out:', out[-1200:].encode('ascii', 'replace').decode('ascii'))
    if not args.dry_run and code != 0:
        print('WARN: pnpm lockfile-only failed; lockfile may be stale (manual entries may be needed)')
    if not args.dry_run:
        problems = verify()
        print('verify:', 'PASS' if not problems else 'FAIL ' + '; '.join(problems))
        sys.exit(0 if not problems else 2)
    else:
        print('DRY-RUN OK')


if __name__ == '__main__':
    main()
