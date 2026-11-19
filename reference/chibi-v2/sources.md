# v2素材来源与用途

记录日期：2026-11-17。此目录为依据用户指定风格及既有角色制作的AI辅助二创。

|素材|来源|作者/平台|时间|用途与授权状态|
|---|---|---|---|---|
|style-target.png|用户本聊天上传参考图|用户提供，原图作者未核实|2026-11-17保存|仅作本次画风参考；上传不等于授予原图著作权，不宣称原创|
|八角色身份参考|../turnaround-<id>.png|既有仓库角色，来源和署名见../../NOTICE.md|既有素材|沿用原二创署名及 CC BY-NC-SA 4.0|
|fronts/*.png|内置 ImageGen，以此前的 Q 版和大版形象为参考|AI 辅助重绘|2026-11-19|用户确认的正眼立绘原图|
|sheets/*.png|内置 ImageGen，以确认的正眼立绘和旧四姿势图为参考|AI 辅助重绘|2026-11-19|按同一造型配齐正、侧、背、悬空四姿势|
|portraits、views、turnarounds、firstframes|由 fronts 和 sheets 导出|tools/prepare_chibi_v2.py|2026-11-19|裁切、缩放、排版与绿幕首帧|
|动作配方与流程|https://github.com/PC2005-cloud/dsh-pet/tree/ef174beecc79df76baf9ca06ed152237bbb96875|PC2005-cloud/dsh-pet|2026-11-17查阅|分析、对应及改写；原作者链接保留于README、NOTICE及修订说明|

实际图像生成提示词、身份参考相对路径及SHA256见image-generation.json。每角色四姿势原图的SHA256也记录在manifest.json。
正面站姿使用 fronts 内的确认图，侧面、背面和悬空使用 sheets 的相应姿势。提示词及文件 SHA256 记录在 [image-generation.json](image-generation.json)，各姿势路径见 [manifest.json](manifest.json)。旧 Q 版和原配方可在预先记录的 Git 提交中查阅。
