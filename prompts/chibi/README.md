# 两头身桌宠：136条优化动作提示词（v2.1神态修订）


先用对应角色的**单人绿幕首帧**图生视频。默认10秒、16:9、固定镜头；支持首尾帧时，两端上传同一张S（站姿）或H（悬空）。

每条先复制「精简投喂版」；「详细分镜版」是替代稿，二选一。图形画不好时用「无叠加图形版」，后期再加图标，归档保留必要纸卡。

三视图仅作外观辅助；不要把三人/四姿势图直接当首帧，否则容易生成多个人。只有转圈必须加三视图。

第一轮先做DeepSeek的待机、挥手、跳跃、忙碌点按、悬空5条，通过后再扩展其余角色。建议先做没有转身的动作。

日常首帧是清醒、有焦点且各具神态的；眉眼口型可随动作变化，外观锁定不等于冻结表情。小憩/发呆中段允许指定的困倦或放空。

上游并非只靠提示词：其成片使用PR手工抠像，再统一大小/足线并编码。提示词无法保证消除绿边或让任意模型逐帧复现。


[重绘与上游对照](../../docs/CHIBI-V2-REVISION.md) · [制作与导入](../../docs/MAKE-CHIBI-PET.md)


|角色|17条优化提示词|S|H|三视图|

|---|---|---|---|---|

|DeepSeek 娘|[打开](roles/deepseek.md)|[PNG](../../reference/chibi-v2/firstframes/deepseek.png)|[PNG](../../reference/chibi-v2/firstframes/deepseek-drag.png)|[PNG](../../reference/chibi-v2/turnarounds/deepseek.png)|

|GPT 娘|[打开](roles/gpt.md)|[PNG](../../reference/chibi-v2/firstframes/gpt.png)|[PNG](../../reference/chibi-v2/firstframes/gpt-drag.png)|[PNG](../../reference/chibi-v2/turnarounds/gpt.png)|

|Claude 娘|[打开](roles/claude.md)|[PNG](../../reference/chibi-v2/firstframes/claude.png)|[PNG](../../reference/chibi-v2/firstframes/claude-drag.png)|[PNG](../../reference/chibi-v2/turnarounds/claude.png)|

|Grok 娘|[打开](roles/grok.md)|[PNG](../../reference/chibi-v2/firstframes/grok.png)|[PNG](../../reference/chibi-v2/firstframes/grok-drag.png)|[PNG](../../reference/chibi-v2/turnarounds/grok.png)|

|Gemini 娘|[打开](roles/gemini.md)|[PNG](../../reference/chibi-v2/firstframes/gemini.png)|[PNG](../../reference/chibi-v2/firstframes/gemini-drag.png)|[PNG](../../reference/chibi-v2/turnarounds/gemini.png)|

|Kimi 娘|[打开](roles/kimi.md)|[PNG](../../reference/chibi-v2/firstframes/kimi.png)|[PNG](../../reference/chibi-v2/firstframes/kimi-drag.png)|[PNG](../../reference/chibi-v2/turnarounds/kimi.png)|

|GLM 娘|[打开](roles/glm.md)|[PNG](../../reference/chibi-v2/firstframes/glm.png)|[PNG](../../reference/chibi-v2/firstframes/glm-drag.png)|[PNG](../../reference/chibi-v2/turnarounds/glm.png)|

|Qwen 娘|[打开](roles/qwen.md)|[PNG](../../reference/chibi-v2/firstframes/qwen.png)|[PNG](../../reference/chibi-v2/firstframes/qwen-drag.png)|[PNG](../../reference/chibi-v2/turnarounds/qwen.png)|

Q版AI动作视频尚待生成；当前plugin/packs是旧程序动画。v1图片在reference/chibi保留，新任务只使用reference/chibi-v2。
