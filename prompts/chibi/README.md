# Q版角色动画提示词

已保存8个角色单人透明立绘、正侧背三视图、站立首帧S和悬空首帧H。本目录的136条提示词均已展开，可独立复制；每次给视频模型上传对应角色的单人首帧。

普通动作首尾用同一张S；拖拽首尾用同一张H。转身再补充三视图。10秒是源视频方案，后续可按交互需求剪短；不支持10秒的平台可按比例压缩时间分段。

源视频按 video/chibi/<角色id>/<原动画名>.mp4 保存，再依照[制作指南](../../docs/MAKE-CHIBI-PET.md)导入。

| 角色 | 17条提示词 | 立绘 | 三视图 | S | H |
| --- | --- | --- | --- | --- | --- |
| DeepSeek 娘 | [打开](roles/deepseek.md) | [PNG](../../reference/chibi/portraits/deepseek.png) | [PNG](../../reference/chibi/turnarounds/deepseek.png) | [站立](../../reference/chibi/firstframes/deepseek.png) | [悬空](../../reference/chibi/firstframes/deepseek-drag.png) |
| GPT 娘 | [打开](roles/gpt.md) | [PNG](../../reference/chibi/portraits/gpt.png) | [PNG](../../reference/chibi/turnarounds/gpt.png) | [站立](../../reference/chibi/firstframes/gpt.png) | [悬空](../../reference/chibi/firstframes/gpt-drag.png) |
| Claude 娘 | [打开](roles/claude.md) | [PNG](../../reference/chibi/portraits/claude.png) | [PNG](../../reference/chibi/turnarounds/claude.png) | [站立](../../reference/chibi/firstframes/claude.png) | [悬空](../../reference/chibi/firstframes/claude-drag.png) |
| Grok 娘 | [打开](roles/grok.md) | [PNG](../../reference/chibi/portraits/grok.png) | [PNG](../../reference/chibi/turnarounds/grok.png) | [站立](../../reference/chibi/firstframes/grok.png) | [悬空](../../reference/chibi/firstframes/grok-drag.png) |
| Gemini 娘 | [打开](roles/gemini.md) | [PNG](../../reference/chibi/portraits/gemini.png) | [PNG](../../reference/chibi/turnarounds/gemini.png) | [站立](../../reference/chibi/firstframes/gemini.png) | [悬空](../../reference/chibi/firstframes/gemini-drag.png) |
| Kimi 娘 | [打开](roles/kimi.md) | [PNG](../../reference/chibi/portraits/kimi.png) | [PNG](../../reference/chibi/turnarounds/kimi.png) | [站立](../../reference/chibi/firstframes/kimi.png) | [悬空](../../reference/chibi/firstframes/kimi-drag.png) |
| GLM 娘 | [打开](roles/glm.md) | [PNG](../../reference/chibi/portraits/glm.png) | [PNG](../../reference/chibi/turnarounds/glm.png) | [站立](../../reference/chibi/firstframes/glm.png) | [悬空](../../reference/chibi/firstframes/glm-drag.png) |
| Qwen 娘 | [打开](roles/qwen.md) | [PNG](../../reference/chibi/portraits/qwen.png) | [PNG](../../reference/chibi/turnarounds/qwen.png) | [站立](../../reference/chibi/firstframes/qwen.png) | [悬空](../../reference/chibi/firstframes/qwen-drag.png) |

jobs.json是厂商无关的任务清单，不是某个平台的直接API请求格式。当前Q版AI动作视频尚待生成；仓库原有plugin/packs动画保持可用。
