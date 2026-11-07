# -*- coding: utf-8 -*-
"""dsh-pet-ai-girls 图鉴素材构建脚本（Pillow 7.2 兼容）。

用法（在项目根 F:\\ceshi\\dsh-pet-ai-girls 下）:
    python tools/gallery_build.py

输入（只读，绝不修改）:
    reference/portrait-<id>.webp      立绘原图（约 900×1600）
    reference/turnaround-<id>.png     三视图原图（1536×1024）

输出:
    plugin/icon.png                           256×256 插件图标（≤ 256 KiB）
    plugin/visual/portraits/<id>.webp         立绘（约 900×1600，webp q86）
    plugin/visual/portraits/thumbs/<id>.webp  卡片缩略图（高 640，q76）
    plugin/visual/turnarounds/<id>.webp       三视图（宽 1280，webp q82）
    plugin/visual/turnarounds/thumbs/<id>.webp 卡片缩略图（宽 640，q76）
    plugin/visual/data.json                   图鉴数据（角色 / 17 个动画 / 署名）
    plugin/visual/index.html                  把 data.json 注入 GALLERY-DATA 区块

说明:
  - 本脚本是图鉴元数据的唯一生成源；index.html 只负责渲染，角色文案不要手改 HTML。
  - 素材版权：原角色设计 ZipZipPipe（上善无形 / DeepSeek），CC BY-NC-SA 4.0，
    来源 https://genderswapai.com/zh-TW/ai-gijinka 。本项目为非官方同人桌宠素材包。
  - 只写 plugin/ 下文件（plugin/packs/ 不归本脚本管）。
"""

import datetime
import json
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF_DIR = os.path.join(ROOT, 'reference')
PLUGIN_DIR = os.path.join(ROOT, 'plugin')
VISUAL_DIR = os.path.join(PLUGIN_DIR, 'visual')

def _plugin_version():
    """图鉴内嵌版本号与插件 package.json 保持同步。"""
    try:
        with open(os.path.join(PLUGIN_DIR, 'package.json'), encoding='utf-8') as f:
            return json.load(f).get('version') or '0.0.0'
    except Exception:
        return '0.0.0'


PLUGIN_VERSION = _plugin_version()
SOURCE_URL = 'https://genderswapai.com/zh-TW/ai-gijinka'
CREDIT = {
    'author': 'ZipZipPipe（上善无形 / DeepSeek）',
    'license': 'CC BY-NC-SA 4.0',
    'licenseUrl': 'https://creativecommons.org/licenses/by-nc-sa/4.0/',
    'source': 'genderswapai.com AI 拟人角色图鉴',
    'sourceUrl': SOURCE_URL,
    'note': '非官方同人作品：角色原案版权归原作者所有，本项目仅作个人桌宠/图鉴展示。',
}

# ---------------------------------------------------------------------------
# 角色元数据（8 位 AI 娘；与 tools/spec.py 保持一致，本脚本是图鉴展示用的副本）
# ---------------------------------------------------------------------------
CHARACTERS = [
    {
        'id': 'deepseek',
        'prefix': 'girl-deepseek',
        'name': 'DeepSeek 娘',
        'subtitle': '蓝发鲸鱼娘',
        'accent': '#4d6bfe',
        'traits': ['蓝色长发', '鲸鱼尾巴', '黑白女仆裙', '爱吃白米饭'],
        'description': 'DeepSeek 的非官方拟人娘化形象，中文社群常叫她「蓝色大肥鱼」。蓝发女仆配鲸鱼尾巴，温柔聪明又有点爱摸鱼。',
    },
    {
        'id': 'gpt',
        'prefix': 'girl-gpt',
        'name': 'GPT 娘',
        'subtitle': '白发龙娘',
        'accent': '#10b981',
        'traits': ['白发龙娘', '龙角与翅膀', '白色礼服', '蓝色小团子'],
        'description': 'ChatGPT 的非官方拟人娘化形象：白发的龙族少女，穿白色礼服、长着小龙角和龙翼，身边总跟着一只蓝色小团子。',
    },
    {
        'id': 'claude',
        'prefix': 'girl-claude',
        'name': 'Claude 娘',
        'subtitle': '橙发与花朵发饰',
        'accent': '#e07a5f',
        'traits': ['橙色长发', '花朵发饰', '黑橙长裙', '手不释卷'],
        'description': 'Claude 的非官方拟人娘化形象：橙色长发配花朵发饰，穿黑橙相间的长裙，总是捧着书，温和又细心。',
    },
    {
        'id': 'grok',
        'prefix': 'girl-grok',
        'name': 'Grok 娘',
        'subtitle': '金发与黑色礼服',
        'accent': '#d4af37',
        'traits': ['金色长发', '黑色礼服', '大十字戟', '傲娇毒舌'],
        'description': 'Grok 的非官方拟人娘化形象：金发配黑色哥特礼服，手持黑色大十字戟，傲娇毒舌但其实心软。',
    },
    {
        'id': 'gemini',
        'prefix': 'girl-gemini',
        'name': 'Gemini 娘',
        'subtitle': '异色瞳与蓝紫猫耳',
        'accent': '#8b5cf6',
        'traits': ['蓝紫渐变发', '猫耳', '异色瞳', '星星装饰'],
        'description': 'Gemini 的非官方拟人娘化形象：蓝紫渐变的头发、猫耳与异色瞳，活泼好奇，身上点缀着星星和闪光。',
    },
    {
        'id': 'kimi',
        'prefix': 'girl-kimi',
        'name': 'Kimi 娘',
        'subtitle': '银紫长发与非对称女仆装',
        'accent': '#a78bfa',
        'traits': ['银紫长发', '非对称女仆装', '安静可靠', '擅长整理'],
        'description': 'Kimi 的非官方拟人娘化形象：银紫色长发，穿不对称设计的女仆装，安静可靠、擅长把复杂的事理清楚。',
    },
    {
        'id': 'glm',
        'prefix': 'girl-glm',
        'name': 'GLM 娘',
        'subtitle': '黑发狐耳与女仆装',
        'accent': '#f472b6',
        'traits': ['黑色长发', '狐耳', '黑白女仆裙', '小恶魔毒舌'],
        'description': 'GLM 的非官方拟人娘化形象：黑发狐耳配黑白女仆长裙，冷静聪慧，有点小恶魔式的毒舌。',
    },
    {
        'id': 'qwen',
        'prefix': 'girl-qwen',
        'name': 'Qwen 娘',
        'subtitle': '圆形发饰与蓝紫衣裙',
        'accent': '#38bdf8',
        'traits': ['蓝色长发', '圆形发饰', '团扇', '蓝紫衣裙'],
        'description': 'Qwen 的非官方拟人娘化形象：蓝发配圆形发饰，执一把团扇，穿蓝紫色衣裙，温婉典雅带点古风。',
    },
]

# 17 个动画：名字与 tools/spec.py 的 ANIMATIONS 完全一致（分组只用于展示）
ANIMATION_GROUPS = [
    ('待机', ['待机呼吸', '原地漂浮', '原地小憩']),
    ('互动', ['东张西望', '被鼠标拖拽悬空反馈',
              '点击回应-开心跃动', '点击回应-害羞惊讶', '点击回应-元气挥手']),
    ('碎碎念', ['碎碎念-发呆碎碎念']),
    ('工作状态', ['工作状态-思考冒泡', '工作状态-忙碌点按', '工作状态-清点归档',
                  '工作状态-原地踱步张望', '工作状态-雀跃庆祝', '工作状态-垂头叹气冒汗']),
    ('小动作', ['转圈展示', '伸懒腰']),
]
ANIM_NAMES = [n for _g, names in ANIMATION_GROUPS for n in names]
assert len(ANIM_NAMES) == 17, '动画数量必须是 17，当前 %d' % len(ANIM_NAMES)

# 头像裁切参数（居中比例；个别角色可单独覆盖 cx）
FACE_DEFAULT = {'cx': 0.5, 'cy': 0.115, 'side': 0.44, 'y0': 0.012}
FACE_TUNING = {
    'grok': {'cx': 0.565},
    'claude': {'cx': 0.53},
    'kimi': {'cx': 0.47},
    'glm': {'cx': 0.47},
}


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------
def log(msg):
    print('[gallery] %s' % msg)


def ensure_dirs():
    for sub in ('visual/portraits/thumbs', 'visual/turnarounds/thumbs'):
        path = os.path.join(PLUGIN_DIR, *sub.split('/'))
        if not os.path.isdir(path):
            os.makedirs(path)


def open_rgb(path):
    img = Image.open(path)
    img.load()
    if img.mode == 'RGBA':
        canvas = Image.new('RGB', img.size, (255, 255, 255))
        canvas.paste(img, (0, 0), img)
        img = canvas
    elif img.mode != 'RGB':
        img = img.convert('RGB')
    return img


def resize_to_height(img, height):
    w, h = img.size
    if h == height:
        return img
    nw = max(1, int(round(w * height / float(h))))
    return img.resize((nw, height), Image.LANCZOS)


def resize_to_width(img, width):
    w, h = img.size
    if w == width:
        return img
    nh = max(1, int(round(h * width / float(w))))
    return img.resize((width, nh), Image.LANCZOS)


def save_webp(img, path, quality):
    img.save(path, 'WEBP', quality=quality, method=6, exact=True)


def rounded_mask(size, radius):
    """PIL 7.2 没有 rounded_rectangle：用矩形 + 四角圆片拼一个圆角蒙版。"""
    w, h = size
    mask = Image.new('L', (w, h), 0)
    d = ImageDraw.Draw(mask)
    d.rectangle([radius, 0, w - radius - 1, h - 1], fill=255)
    d.rectangle([0, radius, w - 1, h - radius - 1], fill=255)
    d.ellipse([0, 0, 2 * radius - 1, 2 * radius - 1], fill=255)
    d.ellipse([w - 2 * radius, 0, w - 1, 2 * radius - 1], fill=255)
    d.ellipse([0, h - 2 * radius, 2 * radius - 1, h - 1], fill=255)
    d.ellipse([w - 2 * radius, h - 2 * radius, w - 1, h - 1], fill=255)
    return mask


def circle_mask(size):
    mask = Image.new('L', (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse([0, 0, size - 1, size - 1], fill=255)
    return mask


def text_size(draw, text, font):
    try:
        return draw.textbbox((0, 0), text, font=font)[2:]
    except Exception:
        try:
            return draw.textsize(text, font=font)
        except Exception:
            return font.getsize(text)


def find_font(size, bold=True):
    candidates = [
        r'C:\Windows\Fonts\msyhbd.ttc' if bold else r'C:\Windows\Fonts\msyh.ttc',
        r'C:\Windows\Fonts\msyh.ttc',
        r'C:\Windows\Fonts\simhei.ttf',
        r'C:\Windows\Fonts\simsun.ttc',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc',
        '/System/Library/Fonts/PingFang.ttc',
    ]
    for path in candidates:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# 立绘 / 三视图 / 缩略图
# ---------------------------------------------------------------------------
def build_images():
    portrait_dir = os.path.join(VISUAL_DIR, 'portraits')
    portrait_thumb_dir = os.path.join(portrait_dir, 'thumbs')
    turnaround_dir = os.path.join(VISUAL_DIR, 'turnarounds')
    turnaround_thumb_dir = os.path.join(turnaround_dir, 'thumbs')
    report = []
    for char in CHARACTERS:
        cid = char['id']
        src_p = os.path.join(REF_DIR, 'portrait-%s.webp' % cid)
        src_t = os.path.join(REF_DIR, 'turnaround-%s.png' % cid)
        if not os.path.isfile(src_p) or not os.path.isfile(src_t):
            raise SystemExit('缺少素材：%s 或 %s' % (src_p, src_t))

        # 立绘：保持约 900×1600，q86
        img = open_rgb(src_p)
        img_p = resize_to_height(img, 1600)
        out_p = os.path.join(portrait_dir, cid + '.webp')
        save_webp(img_p, out_p, 86)
        # 卡片缩略图：高 640，q76
        out_pt = os.path.join(portrait_thumb_dir, cid + '.webp')
        save_webp(resize_to_height(img_p, 640), out_pt, 76)

        # 三视图：1536×1024 → 宽 1280，q82
        img_t = resize_to_width(open_rgb(src_t), 1280)
        out_t = os.path.join(turnaround_dir, cid + '.webp')
        save_webp(img_t, out_t, 82)
        out_tt = os.path.join(turnaround_thumb_dir, cid + '.webp')
        save_webp(resize_to_width(img_t, 640), out_tt, 76)

        report.append((cid, os.path.getsize(out_p), os.path.getsize(out_pt),
                       os.path.getsize(out_t), os.path.getsize(out_tt)))
    return report


# ---------------------------------------------------------------------------
# 插件图标：深色圆角底 + 顶部「AI 娘」+ 8 个角色头像拼贴
# ---------------------------------------------------------------------------
def face_crop(img, char):
    """按比例裁一张接近头像的方形图（白底原图，无 alpha 需求）。"""
    w, h = img.size
    tune = dict(FACE_DEFAULT)
    tune.update(FACE_TUNING.get(char['id'], {}))
    side = int(round(w * tune['side']))
    side = min(side, w, h)
    cx = int(round(w * tune['cx']))
    x0 = max(0, min(w - side, cx - side // 2))
    y0 = max(0, min(h - side, int(round(h * tune['y0']))))
    return img.crop((x0, y0, x0 + side, y0 + side))


def build_chibi_images():
    """Q版 (chibi) previews: per-character front image + an 8-character lineup."""
    import numpy as np  # noqa: F401  (kept for parity with other helpers)

    chibi_dir = os.path.join(VISUAL_DIR, 'chibi')
    thumb_dir = os.path.join(chibi_dir, 'thumbs')
    os.makedirs(chibi_dir, exist_ok=True)
    os.makedirs(thumb_dir, exist_ok=True)
    src_dir = os.path.join(ROOT, 'build', 'chibi')
    report = []
    for char in CHARACTERS:
        src = os.path.join(src_dir, '%s-portrait.png' % char['id'])
        if not os.path.isfile(src):
            raise SystemExit('缺少 Q 版素材：%s（先跑 tools/sheets.py + tools/chibi.py）' % src)
        img = Image.open(src).convert('RGBA')
        h = 760
        img_s = img.resize((max(1, int(round(img.width * h / img.height))), h), Image.LANCZOS)
        out = os.path.join(chibi_dir, char['id'] + '.webp')
        img_s.save(out, 'WEBP', quality=90, method=6)
        out_t = os.path.join(thumb_dir, char['id'] + '.webp')
        th = 420
        img_t = img.resize((max(1, int(round(img.width * th / img.height))), th), Image.LANCZOS)
        img_t.save(out_t, 'WEBP', quality=82, method=6)
        report.append((char['id'], os.path.getsize(out), os.path.getsize(out_t)))
    lineup = os.path.join(src_dir, 'lineup.png')
    if os.path.isfile(lineup):
        im = Image.open(lineup).convert('RGB')
        im = resize_to_width(im, 1600)
        save_webp(im, os.path.join(chibi_dir, 'lineup.webp'), 88)
    return report


def chibi_face(path, char):
    """Q版头像：从透明 Q 版立绘里裁出头部，衬一个角色主色浅底圆。"""
    img = Image.open(path).convert('RGBA')
    bbox = img.getbbox()
    if not bbox:
        return Image.new('RGB', (128, 128), (40, 46, 70))
    x0, y0, x1, y1 = bbox
    h = y1 - y0
    side = max(1, int(round(h * 0.56)))
    cx = (x0 + x1) // 2
    sx = max(0, cx - side // 2)
    sy = max(0, y0 - int(round(h * 0.015)))
    crop = img.crop((sx, sy, min(img.width, sx + side), min(img.height, sy + side)))
    accent = char.get('accent') or '#7c8cff'
    color = tuple(int(accent[i:i + 2], 16) for i in (1, 3, 5))
    tint = tuple(min(255, c + 178) for c in color)
    bg = Image.new('RGBA', (crop.width, crop.height), tint + (255,))
    d = ImageDraw.Draw(bg)
    d.ellipse([0, 0, crop.width - 1, crop.height - 1], fill=tint + (255,))
    bg.alpha_composite(crop, (0, 0))
    return bg.convert('RGB')


def build_icon():
    import numpy as np

    size = 256
    top = (10, 15, 32)
    bottom = (30, 40, 76)
    rows = np.linspace(0.0, 1.0, size, dtype=np.float32).reshape(size, 1)
    arr = np.zeros((size, size, 3), dtype=np.float32)
    for c in range(3):
        arr[..., c] = top[c] * (1.0 - rows) + bottom[c] * rows

    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)

    def glow(cx, cy, radius, color, strength):
        d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / float(radius)
        a = np.clip(1.0 - d, 0.0, 1.0) ** 2 * strength
        for i in range(3):
            arr[..., i] = np.clip(arr[..., i] + a * color[i], 0.0, 255.0)

    glow(38.0, 44.0, 190.0, (77, 107, 254), 0.42)
    glow(222.0, 210.0, 200.0, (139, 92, 246), 0.38)
    glow(128.0, 240.0, 170.0, (56, 189, 248), 0.16)
    base = Image.fromarray(np.clip(arr, 0, 255).astype('uint8'), 'RGB')

    # 细网格纹理（每 16px 一条，低对比度）
    grid = Image.new('RGB', (size, size), (0, 0, 0))
    gd = ImageDraw.Draw(grid)
    for i in range(0, size, 16):
        gd.line([(i, 0), (i, size)], fill=(6, 10, 22))
        gd.line([(0, i), (size, i)], fill=(6, 10, 22))
    base = Image.blend(base, grid, 0.10)

    mask = rounded_mask((size, size), 54)
    canvas = Image.new('RGB', (size, size), (24, 30, 52))
    canvas.paste(base, (0, 0), mask)

    draw = ImageDraw.Draw(canvas)
    # 圆角描边：外圆角 - 内圆角 = 1px 描边环
    outer = rounded_mask((size, size), 54)
    inner_small = rounded_mask((size - 2, size - 2), 52)
    inner = Image.new('L', (size, size), 0)
    inner.paste(inner_small, (1, 1))
    border_mask = ImageChops.subtract(outer, inner)
    edge = Image.new('RGBA', (size, size), (150, 180, 255, 120))
    canvas.paste(edge, (0, 0), border_mask)

    # 顶部标题「AI 娘」
    font_title = find_font(27, bold=True)
    tw, th = text_size(draw, 'AI 娘', font_title)
    draw.text(((size - tw) // 2, 12), 'AI 娘', font=font_title, fill=(238, 243, 255))

    # 8 个头像：4 列 × 2 行（v1.3 起用 Q 版大头头像）
    tile, gap = 52, 8
    col_x = [12 + i * (tile + gap) for i in range(4)]
    row_y = [74, 134]
    av_mask = circle_mask(tile)
    for idx, char in enumerate(CHARACTERS):
        cx = col_x[idx % 4]
        cy = row_y[idx // 4]
        chibi_src = os.path.join(ROOT, 'build', 'chibi', '%s-portrait.png' % char['id'])
        if os.path.isfile(chibi_src):
            face = chibi_face(chibi_src, char).resize((tile, tile), Image.LANCZOS)
        else:
            src = os.path.join(REF_DIR, 'portrait-%s.webp' % char['id'])
            face = face_crop(open_rgb(src), char).resize((tile, tile), Image.LANCZOS)
        canvas.paste(face, (cx, cy), av_mask)
        accent = char['accent']
        color = tuple(int(accent[i:i + 2], 16) for i in (1, 3, 5))
        d2 = ImageDraw.Draw(canvas)
        d2.ellipse([cx, cy, cx + tile - 1, cy + tile - 1], outline=color, width=2)

    # 底部小字
    font_sub = find_font(12, bold=False)
    sub = '8 位 AI 娘 · 桌宠图鉴'
    sw, _sh = text_size(draw, sub, font_sub)
    draw.text(((size - sw) // 2, 212), sub, font=font_sub, fill=(150, 168, 205))

    out = os.path.join(PLUGIN_DIR, 'icon.png')
    canvas.save(out, 'PNG', optimize=True)
    if os.path.getsize(out) > 256 * 1024:
        # 兜底：256 色量化（≤256 KiB 是 DSH 插件图标的硬限制）
        q = canvas.convert('P', palette=Image.ADAPTIVE, colors=256)
        q.save(out, 'PNG', optimize=True)
    if os.path.getsize(out) > 256 * 1024:
        raise SystemExit('icon.png 超过 256 KiB：%d bytes' % os.path.getsize(out))
    return out


# ---------------------------------------------------------------------------
# data.json + 注入 index.html
# ---------------------------------------------------------------------------
def build_data():
    data = {
        'plugin': 'dsh-pet-ai-girls',
        'version': PLUGIN_VERSION,
        'title': 'AI 娘桌宠图鉴',
        'subtitle': 'dsh-pet-ai-girls · 8 位 AI 拟人角色 · Q版透明动画桌面宠物',
        'generatedAt': datetime.datetime.now().isoformat(timespec='seconds'),
        'chibiLineup': 'chibi/lineup.webp',
        'animationGroups': [{'group': g, 'names': names} for g, names in ANIMATION_GROUPS],
        'animationCount': len(ANIM_NAMES),
        'credit': CREDIT,
        'characters': [],
    }
    for char in CHARACTERS:
        item = dict(char)
        item['portrait'] = 'portraits/%s.webp' % char['id']
        item['portraitThumb'] = 'portraits/thumbs/%s.webp' % char['id']
        item['turnaround'] = 'turnarounds/%s.webp' % char['id']
        item['turnaroundThumb'] = 'turnarounds/thumbs/%s.webp' % char['id']
        item['chibi'] = 'chibi/%s.webp' % char['id']
        item['chibiThumb'] = 'chibi/thumbs/%s.webp' % char['id']
        item['animationCount'] = len(ANIM_NAMES)
        item['animations'] = ANIM_NAMES
        data['characters'].append(item)
    data_path = os.path.join(VISUAL_DIR, 'data.json')
    with open(data_path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')
    return data_path, data


DATA_START = '<!-- GALLERY-DATA-START -->'
DATA_END = '<!-- GALLERY-DATA-END -->'


def inject_into_html(data):
    html_path = os.path.join(VISUAL_DIR, 'index.html')
    if not os.path.isfile(html_path):
        log('index.html 尚不存在，跳过数据注入（先写好 HTML 再重跑本脚本）')
        return False
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()
    start = html.find(DATA_START)
    end = html.find(DATA_END)
    if start < 0 or end < 0 or end < start:
        raise SystemExit('index.html 缺少 GALLERY-DATA 标记块，无法注入')
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    payload = payload.replace('</', '<\\/')
    block = (DATA_START + '\n<script id="gallery-data" type="application/json">'
             + payload + '</script>\n' + DATA_END)
    new_html = html[:start] + block + html[end + len(DATA_END):]
    with open(html_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(new_html)
    log('已把 %d 位角色数据注入 index.html' % len(data['characters']))
    return True


def human(nbytes):
    return '%.1f KiB' % (nbytes / 1024.0) if nbytes < 1024 * 1024 else '%.2f MiB' % (nbytes / 1048576.0)


def main():
    ensure_dirs()
    log('项目根：%s' % ROOT)
    rows = build_images()
    total = 0
    for cid, p, pt, t, tt in rows:
        total += p + pt + t + tt
        log('%-9s 立绘 %7s · 缩略 %6s · 三视图 %7s · 缩略 %6s'
            % (cid, human(p), human(pt), human(t), human(tt)))
    log('图片合计：%s' % human(total))
    chibi_rows = build_chibi_images()
    for cid, c, ct in chibi_rows:
        log('%-9s Q版 %7s · 缩略 %6s' % (cid, human(c), human(ct)))
    icon = build_icon()
    log('icon.png：%s（上限 256 KiB）' % human(os.path.getsize(icon)))
    data_path, data = build_data()
    log('data.json：%s（%d 位角色 / %d 个动画）'
        % (human(os.path.getsize(data_path)), len(data['characters']), data['animationCount']))
    inject_into_html(data)
    log('完成。')


if __name__ == '__main__':
    main()
