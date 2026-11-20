# 从零制作两头身桌宠：v2图片 → 视频 → 透明动画 → 角色包

当前推荐版本为2026-11-17的两头身v2.1神态修订版。8个角色参考图与136条动作任务已经准备；**AI动作视频尚待生成**，plugin/packs中的动画仍是旧程序化版本。重绘原因、上游逐项映射与例外见[修订说明](CHIBI-V2-REVISION.md)。

![v2八角色](screenshots/chibi-v2-all8.png)

## 1. 使用正确的参考图

|文件|用途|
|---|---|
|reference/chibi-v2/portraits/<id>.png|单人透明立绘|
|reference/chibi-v2/turnarounds/<id>.png|正侧背外观辅助；不要直接当视频首帧|
|reference/chibi-v2/views/<id>-front、-side、-back、-drag.png|各姿势单独查看|
|reference/chibi-v2/firstframes/<id>.png|站姿S，1280×720纯绿幕|
|reference/chibi-v2/firstframes/<id>-drag.png|真实画出的悬空H，1280×720纯绿幕|
|reference/chibi-v2/firstframes/<id>-white.png、<id>-drag-white.png|白底外观核对；正式绿幕视频优先使用绿底版|
|reference/chibi-v2/sheets/<id>.png|原始四姿势生成图；不直接投喂为首帧|
|reference/chibi-v2/manifest.json|源图SHA256、路径、站姿与悬空几何参数|

S身高468像素、脚底y=612。H使用独立悬空姿势，保持与S相同的原始像素缩放，脚底y=590；姿势屈曲造成的自然身高变化记录在manifest中，不强行拉高至468。
v1图仍在reference/chibi，仅作历史对照。重新导出v2：

~~~powershell
python tools/prepare_chibi_v2.py
python tools/build_video_prompts.py
~~~

## 2. 准备依赖

~~~powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r tools/requirements.txt
~~~

Python3.8+；FFmpeg查找顺序：命令行--ffmpeg、PET_FFMPEG或FFMPEG_BIN、PATH、项目.tools目录、imageio-ffmpeg。
显式配置错误路径时会报错，不静默改用别的程序。

## 3. 逐动作生成视频：当前用Seedance v3

八位角色各有独立的动作编排，使用配套的[立绘与首帧](../reference/chibi-v2/)。见 [136 条索引](../prompts/chibi-v3/README.md) 和 [DeepSeek 试样流程](../prompts/chibi-v3/PILOT-DEEPSEEK.md)。

- 10秒、16:9。固定的是镜头；身体可以按动作屈膝、起跳、侧倾、扭转与回弹。
- 只有图生视频入口：单人S作输入，拖拽用H；复制对应「仅图片」提示词。
- 有全能参考/视频参考入口：图片1选角色单人图，视频1选[对应动作MP4](../reference/motion-dsh-pet/README.md)，复制「图片＋视频」提示词。图片只定义外观和构图，视频只借动作幅度与节奏。
- 多模态参考和严格首尾帧是不同模式；不要把reference_video和first_frame/last_frame字段混成一次API请求。
- 为诊断动作幅度，首轮先不额外锁同一张尾帧；文本仍要求最后回位。这是本轮试样策略，不表示同图首尾一定导致僵硬。主体动作合格后再单独处理尾帧精确衔接。
- 转圈可另附三视图作外观参考。图片1仍是单人图；素材标签以你界面插入的实际标签为准。
- 不把10秒源片硬加速成旧程序动画的1.3秒；保留完整蓄力、主动作、缓冲和收势。
- 视频导出后继续沿用下文抠像、归一化与打包命令。原片仍存video/chibi-v2，避免改动现有导入路径。

[Seedance v3 使用与诊断](SEEDANCE-V3-ACTIONS.md)。校验动作时同时看首帧所用造型和提示词版本。

## 4. 按上游完成抠像

**上游发布成片采用PR手工抠像；这是复现其干净边缘的重要环节。**
自动绿幕路线可快速预检，不能用提示词代替抠像修边。

推荐精修流程：

1. 导入源视频，使用抠像工具选择背景绿色，调整边缘、溢色与遮罩。
2. 检查眼睛、发饰、蕾丝、白裙、尾尖；Kimi彩虹中有绿色，必须用保留遮罩保护，避免一起抠掉。
3. 道具和特效有绿边时逐段修遮罩；不要扩大抠像阈值导致身体变透明。
4. 分别在黑、白背景上逐帧看边缘，消除白边/绿边，不要把地板或阴影留进alpha。
5. 导出真正带alpha的母版，例如ProRes4444 with Alpha的MOV，保留16:9，不烘焙背景。
6. 从透明母版导入；工具会真实解码alpha验收，扩展名或标签不能证明透明。

平台输出没有水印就无需上游的固定水印遮罩。自动抠像脚本使用软绿幕差值，并非上游HSV脚本的逐行复制；复杂边缘以人工母版为准。

## 5. 保存与导入

正式源片位置：

    video/chibi-v2/deepseek/待机呼吸.mp4
    video/chibi-v2/deepseek/被鼠标拖拽悬空反馈.mp4

MP4、MOV、WebM 均可。[八位角色的 136 条绿幕原片](../video/chibi-v2/)可供预览和导入。新生成的文件与中间产物默认由 Git 忽略。v2 的原片读取路径为 `video/chibi-v2/`。

~~~powershell
python tools/video_pipeline.py plan
~~~

进度写到build/video/chibi-v2/plan.json，逐项列出对应v2首帧。

自动绿幕预检：

~~~powershell
python tools/video_pipeline.py import --character deepseek --action "待机呼吸"
~~~

精修透明母版：

~~~powershell
python tools/video_pipeline.py import --character deepseek --action "待机呼吸" --input "D:\my-videos\idle.mov" --background alpha
~~~

自定义FFmpeg路径放在子命令之前：

~~~powershell
python tools/video_pipeline.py --ffmpeg "D:\tools\ffmpeg.exe" import --character deepseek --action "待机呼吸"
~~~

处理阶段：统一源尺寸1280×720和24fps → 自动抠像或保留alpha → 固定缩放与锚点 → VP9-alpha编码 → 解码验收。
原始画面必须16:9，工具不会把竖屏强行拉成横屏。

归一化目标跟随上游代码：2160×1215母版、站立身高900、脚底y=1115，最终640×360、24fps、无音轨。
一条片段使用同一固定变换，禁止每帧按包围盒重新拟合，避免跳跃时忽大忽小。
悬空H保留姿势导致的身高差与22像素源足线偏移。

结果写到：

    build/video/chibi-v2/step04/<id>/<动作名>.webm

同时生成report及黑白背景首尾审核图。旧build/video/chibi保留，不作为v2输入。

## 6. 验收

~~~powershell
python tools/video_pipeline.py verify --character deepseek --action "待机呼吸"
~~~

自动检查编码/尺寸/帧率/无音轨、真实alpha、空帧、边缘裁切、首尾位置和外观差异、S/H足线与姿势高度。
失败导入保存为.rejected.webm，不覆盖已经通过的版本。

人工仍须播放确认：

- 缩到约128像素人物高度，脸型、表情和动作仍看得清。
- 头身比、服装、耳角翼尾数量稳定；编发、异色瞳与非对称裙片不镜像。
- 手脚是自然的关节运动，发裙稍晚回落，不是把整张PNG缩放/摇摆。
- 首尾不闪、不跳位、不突然换姿态；连续看三轮循环。
- 黑白背景边缘均干净，没有绿边或被误抠的彩虹。
- 跳跃不过高、点击不拖沓、拖拽每轮不落地；必要时重生成。

自动检查不能判断语义、骨骼、美术质量，也不证明视频达到了上游实际效果。

## 7. 全量打包

~~~powershell
python tools/video_pipeline.py pack
~~~

136条齐全并重新验收通过后，才会生成build/video/chibi-v2/plugin/packs。
文件名与配置引用保持兼容。缺少一条也不会生成残缺发布包。

确认素材后，用现有命令更新仓库插件：

~~~powershell
python tools/video_pipeline.py pack --write-plugin
~~~

工具先备份旧packs及package.json到build/video/chibi-v2/backups，复制136条并递增插件补丁版本以触发部署标记。
这一步不直接修改本机.dsh。按仓库安装方式安装新plugin后重启DSH，再实际检查桌面行为。

不要把AI视频放到build/webm后运行旧build_assets.py；它会重新生成旧程序动画。
旧程序路线仍可保留使用，新AI路线统一使用video_pipeline.py。

## 8. 睡觉不是短打盹

原地小憩：S→短盹→S，结尾睁眼。
真正睡觉：另做入睡S→P、睡眠循环P→P、醒来P→S，三个连接点使用相同姿势与地面线，再增加animations.sleep配置。当前17类没有这组三段。

## 9. 测试与来源

~~~powershell
python -m unittest discover -s tests -v
~~~

测试使用实际FFmpeg编码/解码短合成视频检查导入，不等于验证136条尚未生成的AI视频或本机DSH运行。
[v2修订与上游对照](CHIBI-V2-REVISION.md) · [素材来源](../reference/chibi-v2/sources.md) · [署名与授权](../NOTICE.md)。
