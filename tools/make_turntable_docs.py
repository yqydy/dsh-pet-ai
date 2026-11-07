# -*- coding: utf-8 -*-
"""Compose the 2.5D turntable evidence images used by README / docs."""
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REVIEW = os.path.join(ROOT, 'build', 'spin-review')
OUT = os.path.join(ROOT, 'docs', 'screenshots')


def font(size):
    for p in [r'C:\Windows\Fonts\msyh.ttc', r'C:\Windows\Fonts\simhei.ttf']:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def actions_sheet():
    names = ['东张西望', '点击回应-害羞惊讶', '被鼠标拖拽悬空反馈', '工作状态-雀跃庆祝']
    labels = ['东张西望：左右转身', '点击回应-害羞：转身躲开',
              '被拖拽：悬空侧身', '雀跃庆祝：跳跃+转圈']
    cells = []
    for n in names:
        p = os.path.join(REVIEW, 'deepseek-%s.png' % n)
        im = Image.open(p).convert('RGB')
        # drop the source montage's own header row so our labels don't overlap
        im = im.crop((0, 34, im.width, im.height))
        im.thumbnail((790, 240))
        cells.append(im)
    cell_w, cell_h = 800, 300
    W, H = 1600, 44 + 2 * cell_h
    sheet = Image.new('RGB', (W, H), (20, 21, 32))
    d = ImageDraw.Draw(sheet)
    d.text((10, 8), '2.5D 三视图转身动作（DeepSeek 娘，逐帧取样）',
           fill=(240, 242, 255), font=font(20))
    for i, (im, label) in enumerate(zip(cells, labels)):
        x = (i % 2) * cell_w
        y = 44 + (i // 2) * cell_h
        d.text((x + 14, y + 4), label, fill=(255, 226, 120), font=font(18))
        sheet.paste(im, (x + (cell_w - im.width) // 2, y + 30))
    sheet.save(os.path.join(OUT, 'turntable-actions.png'))
    print('saved turntable-actions.png', sheet.size)


def main():
    os.makedirs(OUT, exist_ok=True)
    # 360° turntable frame strip
    src = os.path.join(REVIEW, 'deepseek-转圈展示.png')
    im = Image.open(src).convert('RGB')
    im.save(os.path.join(OUT, 'turntable-360.png'))
    print('saved turntable-360.png', im.size)
    actions_sheet()
    # live desktop capture during a spin
    live = os.path.join(ROOT, 'build', 'shots', 'live-anim-deepseek-montage.png')
    if os.path.exists(live):
        Image.open(live).convert('RGB').save(os.path.join(OUT, 'live-2.5d-spin.png'))
        print('saved live-2.5d-spin.png')


if __name__ == '__main__':
    main()
