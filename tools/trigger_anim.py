# -*- coding: utf-8 -*-
"""Trigger a dsh-pet animation for a pet via the host HTTP action endpoint.

Usage:
  python tools/trigger_anim.py [petId] [animationName]

Defaults: petId=girl-deepseek, animationName=转圈展示 (the 2.5D turntable).
"""
import json
import sys
import urllib.parse
import urllib.request

PORT = 50679
BASE = 'http://127.0.0.1:%d/dsh-pet-7340/anim' % PORT


def main():
    pet = sys.argv[1] if len(sys.argv) > 1 else 'girl-deepseek'
    anim = sys.argv[2] if len(sys.argv) > 2 else '转圈展示'
    url = BASE + '?pet=' + urllib.parse.quote(pet)
    data = json.dumps({'name': anim}, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='POST',
                                 headers={'content-type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            print(r.status, r.read().decode('utf-8', 'replace'))
    except Exception as e:
        print('ERR', e)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
