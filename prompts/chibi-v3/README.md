# 豆包 Seedance 2.0：dsh-pet动作提示词 v3

使用确认的八角色正眼立绘和配套首帧。DeepSeek 与 GPT 分别采用逐动作的性格编排，其余角色在共享动作上加入各自的神态约束。

[DeepSeek 试样流程](PILOT-DEEPSEEK.md)涵盖挥手、跳跃、忙碌点按。新版绿幕原片各 17 条，见[大肥鱼](../../video/chibi-v2/deepseek/)与[龙娘](../../video/chibi-v2/gpt/)。

有全能参考/视频参考入口：图片1选本角色单人绿幕图，视频1选本动作MP4，复制「图片＋视频」版本。只有图生视频入口：只上传该角色图，复制「仅图片」版本。两种模式不要混成一个API请求。

默认 10 秒、16:9。站姿先用单张角色图试拍，拖拽可用相同的悬空首尾帧帮助接回循环。多模态参考模式中把图片作为外观参考。

主体会蓄力、抬臂、扭肩、屈膝和回弹，固定的是镜头与画幅。不是所有动作都变成大跳：待机舒缓，挥手/跳跃/庆祝明显舒展。

[使用与诊断指南](../../docs/SEEDANCE-V3-ACTIONS.md) · [17段上游参考](../../reference/motion-dsh-pet/README.md) · [全部提示词](ALL-PROMPTS.md)

|角色|17条双模式提示词|站姿S|悬空H|
|---|---|---|---|
|DeepSeek 娘|[打开](roles/deepseek.md)|[S](../../reference/chibi-v2/firstframes/deepseek.png)|[H](../../reference/chibi-v2/firstframes/deepseek-drag.png)|
|GPT 娘|[打开](roles/gpt.md)|[S](../../reference/chibi-v2/firstframes/gpt.png)|[H](../../reference/chibi-v2/firstframes/gpt-drag.png)|
|Claude 娘|[打开](roles/claude.md)|[S](../../reference/chibi-v2/firstframes/claude.png)|[H](../../reference/chibi-v2/firstframes/claude-drag.png)|
|Grok 娘|[打开](roles/grok.md)|[S](../../reference/chibi-v2/firstframes/grok.png)|[H](../../reference/chibi-v2/firstframes/grok-drag.png)|
|Gemini 娘|[打开](roles/gemini.md)|[S](../../reference/chibi-v2/firstframes/gemini.png)|[H](../../reference/chibi-v2/firstframes/gemini-drag.png)|
|Kimi 娘|[打开](roles/kimi.md)|[S](../../reference/chibi-v2/firstframes/kimi.png)|[H](../../reference/chibi-v2/firstframes/kimi-drag.png)|
|GLM 娘|[打开](roles/glm.md)|[S](../../reference/chibi-v2/firstframes/glm.png)|[H](../../reference/chibi-v2/firstframes/glm-drag.png)|
|Qwen 娘|[打开](roles/qwen.md)|[S](../../reference/chibi-v2/firstframes/qwen.png)|[H](../../reference/chibi-v2/firstframes/qwen-drag.png)|
