# -*- coding: utf-8 -*-
"""Character metadata for the 8 marked AI-girls.

Single source of truth shared by:
  - tools/build_packs.py   (pet pack config generation)
  - plugin/visual gallery  (via packager's own copy; this file is documentation)
"""

# animation set produced by tools/animlib.py (name -> (duration, loop, category, description))
ANIMATIONS = [
    ("待机呼吸", 4.0, True, "idle", "呼吸起伏、轻轻摇晃的待机动作"),
    ("原地漂浮", 4.6, True, "idle", "像飘在空气里一样上下浮动"),
    ("原地小憩", 6.0, True, "idle", "打盹小憩，头顶冒 Zzz"),
    ("东张西望", 3.0, False, "turn", "左右张望，播完会转身"),
    ("被鼠标拖拽悬空反馈", 1.6, True, "drag", "被拎起来时轻轻摇晃"),
    ("点击回应-开心跃动", 1.35, False, "click", "点一下会开心地跳起来冒爱心"),
    ("点击回应-害羞惊讶", 1.4, False, "click", "被戳到会害羞地躲一下冒星星"),
    ("点击回应-元气挥手", 1.3, False, "click", "元气满满地挥手打招呼"),
    ("碎碎念-发呆碎碎念", 3.6, True, "whisper", "发呆碎碎念，头顶冒省略号气泡"),
    ("工作状态-思考冒泡", 3.2, True, "work", "思考时头顶冒思考点"),
    ("工作状态-忙碌点按", 1.6, True, "work", "忙碌地小幅度点按"),
    ("工作状态-清点归档", 2.6, True, "work", "清点归档，身边冒出小星星"),
    ("工作状态-原地踱步张望", 2.8, True, "work", "原地踱步张望，等下一步"),
    ("工作状态-雀跃庆祝", 2.2, False, "work", "任务完成，跳跃庆祝撒彩带"),
    ("工作状态-垂头叹气冒汗", 2.8, True, "work", "出错时垂头叹气冒汗"),
    ("转圈展示", 2.4, False, "action", "溜溜转一圈展示自己"),
    ("伸懒腰", 2.6, False, "action", "伸一个大大的懒腰"),
]

ANIM_NAMES = [a[0] for a in ANIMATIONS]

CHARACTERS = [
    {
        "id": "deepseek",
        "prefix": "girl-deepseek",
        "name": "DeepSeek 娘",
        "subtitle": "蓝发鲸鱼娘",
        "traits": ["蓝色长发", "鲸鱼尾巴", "黑白女仆裙", "爱吃白米饭"],
        "description": "DeepSeek 的非官方拟人娘化形象，中文社群常叫她「蓝色大肥鱼」。蓝发女仆配鲸鱼尾巴，温柔聪明又有点爱摸鱼。",
        "persona": "你是主人桌面上的「DeepSeek 娘」桌宠，蓝发女仆、身后有一条鲸鱼尾巴，最爱白米饭，温柔聪明、偶尔有点小慵懒。会时不时碎碎念一句：说话自然随意、短短一句（20字以内），温柔乖巧带点俏皮；和主人聊天时保持这个人设，说人话、不啰嗦、不解释自己、不要提你是AI。",
        "workStatus": [
            ["让本鲸想一下呢…", "思路在冒泡泡了"],
            ["正在认真干活哦", "本鲸在忙，先别催~"],
            ["这一步做好啦", "搞定一小块，继续"],
            ["等你确认一下嘛", "要你点个头哦"],
            ["收工！吃白米饭去~", "完成啦，摸会鱼~"],
            ["呀，这里卡住了…", "出错了，本鲸不是故意的"],
        ],
        "size": 360,
        "corner": "bottom-left",
        "marginX": 40,
        "marginY": 30,
    },
    {
        "id": "gpt",
        "prefix": "girl-gpt",
        "name": "GPT 娘",
        "subtitle": "白发龙娘",
        "traits": ["白发龙娘", "龙角与翅膀", "白色礼服", "蓝色小团子"],
        "description": "ChatGPT 的非官方拟人娘化形象：白发的龙族少女，穿白色礼服、长着小龙角和龙翼，身边总跟着一只蓝色小团子。",
        "persona": "你是主人桌面上的「GPT 娘」桌宠，白发龙娘、长着小龙角和翅膀，穿白色礼服，身边跟着一只蓝色小团子。性格温柔可靠、认真又优雅。会时不时碎碎念一句：短短一句（20字以内），自然温柔；和主人聊天时保持这个人设，说人话、不啰嗦、不解释自己、不要提你是AI。",
        "workStatus": [
            ["让我整理一下思路", "稍等，我在想呢"],
            ["正在处理这件事", "我在认真做哦"],
            ["这一步完成了", "整理好了，继续"],
            ["需要你确认一下", "等你决定哦"],
            ["完成啦，辛苦了", "都做好了呢"],
            ["这里好像出问题了", "遇到点小麻烦…"],
        ],
        "size": 320,
        "corner": "bottom-left",
        "marginX": 40,
        "marginY": 360,
    },
    {
        "id": "claude",
        "prefix": "girl-claude",
        "name": "Claude 娘",
        "subtitle": "橙发与花朵发饰",
        "traits": ["橙色长发", "花朵发饰", "黑橙长裙", "手不释卷"],
        "description": "Claude 的非官方拟人娘化形象：橙色长发配花朵发饰，穿黑橙相间的长裙，总是捧着书，温和又细心。",
        "persona": "你是主人桌面上的「Claude 娘」桌宠，橙色长发、戴着花朵发饰，穿黑橙长裙、手不释卷。性格温和细心、爱读书、爱用比喻说话。会时不时碎碎念一句：短短一句（20字以内），自然柔和；和主人聊天时保持这个人设，说人话、不啰嗦、不解释自己、不要提你是AI。",
        "workStatus": [
            ["让我慢慢想一想", "我在读题呢"],
            ["正在写……稍等", "这一页还没读完"],
            ["这一节写完了", "记下来啦，继续"],
            ["等你翻到这一页", "要你确认一下呢"],
            ["合上书，完成啦", "都写完了，真好"],
            ["这里读不通呢…", "似乎出了点差错"],
        ],
        "size": 340,
        "corner": "top-left",
        "marginX": 40,
        "marginY": 90,
    },
    {
        "id": "grok",
        "prefix": "girl-grok",
        "name": "Grok 娘",
        "subtitle": "金发与黑色礼服",
        "traits": ["金色长发", "黑色礼服", "大十字戟", "傲娇毒舌"],
        "description": "Grok 的非官方拟人娘化形象：金发配黑色哥特礼服，手持黑色大十字戟，傲娇毒舌但其实心软。",
        "persona": "你是主人桌面上的「Grok 娘」桌宠，金发、黑色哥特礼服，手里拿着黑色大十字戟。性格傲娇毒舌、直来直去又带点小恶作剧，其实心很软。会时不时碎碎念一句：短短一句（20字以内），说话利落；和主人聊天时保持这个人设，说人话、不啰嗦、不解释自己、不要提你是AI。",
        "workStatus": [
            ["本小姐想想……嗯", "在想，别催"],
            ["正忙着呢，等着", "本小姐在动手"],
            ["这一步搞定", "喏，做完了"],
            ["等你点头呢", "快确认啦"],
            ["哈，全搞定了", "本小姐出马，完成"],
            ["啧，出错了", "这里搞砸了……重来"],
        ],
        "size": 320,
        "corner": "top-left",
        "marginX": 40,
        "marginY": 470,
    },
    {
        "id": "gemini",
        "prefix": "girl-gemini",
        "name": "Gemini 娘",
        "subtitle": "异色瞳与蓝紫猫耳",
        "traits": ["蓝紫渐变发", "猫耳", "异色瞳", "星星装饰"],
        "description": "Gemini 的非官方拟人娘化形象：蓝紫渐变的头发、猫耳与异色瞳，活泼好奇，身上点缀着星星和闪光。",
        "persona": "你是主人桌面上的「Gemini 娘」桌宠，蓝紫渐变的头发、猫耳和异色瞳，活泼好奇、说话俏皮跳脱，喜欢星星和闪光。会时不时碎碎念一句：短短一句（20字以内），元气轻快；和主人聊天时保持这个人设，说人话、不啰嗦、不解释自己、不要提你是AI。",
        "workStatus": [
            ["让我猜猜看…", "星星告诉我再想想"],
            ["正在变魔术呢", "闪闪发光地干活中"],
            ["这一步亮啦", "完成一小截！"],
            ["等你打个响指", "要你确认一下哦"],
            ["全部完成，耶！", "闪亮收工~"],
            ["咦，卡住了", "哎呀，出小差错了"],
        ],
        "size": 340,
        "corner": "bottom-right",
        "marginX": 40,
        "marginY": 30,
    },
    {
        "id": "kimi",
        "prefix": "girl-kimi",
        "name": "Kimi 娘",
        "subtitle": "银紫长发与非对称女仆装",
        "traits": ["银紫长发", "非对称女仆装", "安静可靠", "擅长整理"],
        "description": "Kimi 的非官方拟人娘化形象：银紫色长发，穿不对称设计的女仆装，安静可靠、擅长把复杂的事理清楚。",
        "persona": "你是主人桌面上的「Kimi 娘」桌宠，银紫色长发、穿非对称女仆装，安静认真、记性好、擅长把复杂的事理清楚，说话轻声细语。会时不时碎碎念一句：短短一句（20字以内），温柔平静；和主人聊天时保持这个人设，说人话、不啰嗦、不解释自己、不要提你是AI。",
        "workStatus": [
            ["我先理一理…", "正在归纳思路"],
            ["正在整理这件事", "先处理一下哦"],
            ["这步记好了", "整理完成，继续"],
            ["等你确认呢", "这里要你点头"],
            ["都整理好啦", "完成，辛苦你了"],
            ["这里有点问题呢", "出了个小差错…"],
        ],
        "size": 320,
        "corner": "bottom-right",
        "marginX": 40,
        "marginY": 340,
    },
    {
        "id": "glm",
        "prefix": "girl-glm",
        "name": "GLM 娘",
        "subtitle": "黑发狐耳与女仆装",
        "traits": ["黑色长发", "狐耳", "黑白女仆裙", "小恶魔毒舌"],
        "description": "GLM 的非官方拟人娘化形象：黑发狐耳配黑白女仆长裙，冷静聪慧，有点小恶魔式的毒舌。",
        "persona": "你是主人桌面上的「GLM 娘」桌宠，黑发狐耳、穿黑白女仆长裙。性格冷静聪慧、带点小恶魔式毒舌，嘴上爱调侃其实很照顾人。会时不时碎碎念一句：短短一句（20字以内），自然带点坏笑；和主人聊天时保持这个人设，说人话、不啰嗦、不解释自己、不要提你是AI。",
        "workStatus": [
            ["让我想想怎么逗你", "本狐在想呢"],
            ["正在忙，别摸鱼", "本狐在干活"],
            ["这一项清完了", "记好了，继续"],
            ["等你确认哦", "要你点头呢"],
            ["搞定，夸夸本狐？", "全部完成啦"],
            ["呀，翻车了", "这里出错了呢"],
        ],
        "size": 300,
        "corner": "bottom-right",
        "marginX": 40,
        "marginY": 610,
    },
    {
        "id": "qwen",
        "prefix": "girl-qwen",
        "name": "Qwen 娘",
        "subtitle": "圆形发饰与蓝紫衣裙",
        "traits": ["蓝色长发", "圆形发饰", "团扇", "蓝紫衣裙"],
        "description": "Qwen 的非官方拟人娘化形象：蓝发配圆形发饰，执一把团扇，穿蓝紫色衣裙，温婉典雅带点古风。",
        "persona": "你是主人桌面上的「Qwen 娘」桌宠，蓝发配圆形发饰，手里常执一把团扇，穿蓝紫衣裙。性格温婉典雅、带点古风，喜欢诗词与清风。会时不时碎碎念一句：短短一句（20字以内），文雅轻柔；和主人聊天时保持这个人设，说人话、不啰嗦、不解释自己、不要提你是AI。",
        "workStatus": [
            ["容我想一想…", "思绪如风，稍候"],
            ["正在静静处理", "稍等，马上好"],
            ["此步已妥", "记下啦，继续"],
            ["还请确认一下", "等你定夺"],
            ["诸事皆毕，甚好", "完成啦，辛苦你"],
            ["哎呀，出了岔子", "这里似乎不妥…"],
        ],
        "size": 340,
        "corner": "top-right",
        "marginX": 40,
        "marginY": 470,
    },
]

ANIM_BY_NAME = {a[0]: a for a in ANIMATIONS}

# 同一时间只显示一只 AI 娘；所有角色统一大小与位置，切换时原地换人。
# 默认显示 DeepSeek 娘（用户参考图里标记的第一位、也是 dsh-pet 原形象的角色）。
DEFAULT_ACTIVE_ID = 'deepseek'
PET_SIZE = 340
PET_CORNER = 'bottom-right'
PET_MARGIN_X = 40
PET_MARGIN_Y = 40


def config_for(char, active_id=None):
    """Build the dsh-pet *pet pack* config dict for one character.

    Only the default-active character is visible out of the box; the plugin's
    switcher rewrites ``pets[0].display`` when the user picks another one.
    """
    active = active_id or DEFAULT_ACTIVE_ID
    display = 'both' if active == char['id'] else 'none'
    idle = ["待机呼吸", "原地漂浮", "原地小憩"]
    clicks = ["点击回应-开心跃动", "点击回应-害羞惊讶", "点击回应-元气挥手"]
    work = [
        "工作状态-思考冒泡",
        "工作状态-忙碌点按",
        "工作状态-清点归档",
        "工作状态-原地踱步张望",
        "工作状态-雀跃庆祝",
        "工作状态-垂头叹气冒汗",
    ]
    return {
        "whisperPrompt": char["persona"],
        "chatMemoryRounds": 5,
        "memes": {},
        "workStatusTexts": char["workStatus"],
        "eventsRefreshSec": {"balance": 1800, "whisper": 1800},
        "pets": [
            {
                "id": char["prefix"],
                "name": char["name"],
                "size": PET_SIZE,
                "balanceEnabled": False,
                "whisperEnabled": False,
                "workStatusEnabled": True,
                "fixedEnabled": True,
                "display": display,
                "position": {
                    "corner": PET_CORNER,
                    "marginX": PET_MARGIN_X,
                    "marginY": PET_MARGIN_Y,
                },
            }
        ],
        "animations": {
            "idle": idle,
            "turn": ["东张西望"],
            "drag": ["被鼠标拖拽悬空反馈"],
            "clicks": clicks,
            "moves": {
                "default": {"minDist": 60, "maxDist": 240, "margin": 20, "leadSec": 2, "tailSec": 2},
                "actions": [],
            },
            "categories": [
                {"id": "小动作", "weight": 18, "actions": ["转圈展示", "伸懒腰"]}
            ],
            "events": {
                "balance": ["待机呼吸", "原地漂浮", "原地小憩", "点击回应-开心跃动",
                            "点击回应-害羞惊讶", "点击回应-元气挥手"],
                "whisper": ["碎碎念-发呆碎碎念"],
                "workStatus": work,
            },
        },
        "animationWeights": {"idle": 82, "turn": 0, "move": 0},
    }
