# 素材版权与致谢（NOTICE）

本项目是 **非官方同人作品**，与任何 AI 产品官方团队无关。角色形象版权归原作者所有。

## 角色原案 / 立绘 / 三视图

- 原角色设计：**ZipZipPipe**（DeepSeek 娘的原角色为 **上善无形**）
- 来源：[Gender Swap AI · AI 拟人角色图鉴](https://genderswapai.com/zh-TW/ai-gijinka)
- 授权：**CC BY-NC-SA 4.0** — <https://creativecommons.org/licenses/by-nc-sa/4.0/>
- 涉及角色：DeepSeek 娘 / GPT 娘 / Claude 娘 / Grok 娘 / Gemini 娘 / Kimi 娘 / GLM 娘 / Qwen 娘
- 本仓库中的 `reference/` 与 `plugin/visual/` 包含上述立绘与三视图的副本；
  `plugin/packs/` 中的动画素材是基于立绘由本项目脚本生成的二创派生作品。

**禁止商用。** 二次使用请保留原作者署名并以相同方式共享（CC BY-NC-SA 4.0）。

## 桌宠引擎

- [dsh-pet](https://github.com/PC2005-cloud/dsh-pet)（MIT）：桌宠运行时与动画播放契约
- [DeepSeek Harness](https://github.com/deepseek-ai)：插件宿主平台

## 本项目代码

本项目自行编写的代码（`tools/`、`plugin/index.js`、`plugin/visual/` 页面代码等）
以 MIT 许可证发布，详见 `LICENSE`。


## Q版衍生素材（2026-11-08）

reference/chibi/为基于上述原角色及三视图、使用内置imagegen制作的Q版二创，原角色署名和CC BY-NC-SA 4.0说明继续适用。prompts/chibi/image-generation.json记录生成提示词与参考输入。缩放、拆分和绿幕首帧由tools/prepare_chibi.py导出，未把原角色设计声明为本项目原创。


## 两头身v2衍生素材（2026-11-17）

reference/chibi-v2/基于既有角色及用户上传风格参考，使用内置imagegen重绘。实际生成与修订提示词见reference/chibi-v2/image-generation.json，来源与用途见reference/chibi-v2/sources.md。原角色署名和衍生素材限制继续沿用上述说明。用户风格参考的原作者未核实，不将该原图声明为本项目原创。

动作提示词按[PC2005-cloud/dsh-pet](https://github.com/PC2005-cloud/dsh-pet)的实际配方分析、改写；版本与逐项适配见docs/CHIBI-V2-REVISION.md。v2只交付静态参考图与视频生成配方，新AI动作视频仍待生成。
