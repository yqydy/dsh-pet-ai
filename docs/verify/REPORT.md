# dsh-pet-ai-girls 独立验证报告

- 项目根：`F:\ceshi\dsh-pet-ai-girls`
- 验证者：verifier（独立实现，不复用 animlib.py / build_packs.py）
- 验证时间：2026-11-06 10:51–11:25（Asia/Shanghai）
- 被测对象：`plugin/packs/`（8 个 AI 娘 pet pack）+ `plugin/`（dsh-pet-ai-girls 插件壳）+ 已部署的活 DSH 实例 `http://127.0.0.1:57076` + 真实 dsh-pet 桌面窗口
- 验证脚本（全部只读被测文件，输出仅在 `build/verify/`、`build/shots/`）：
  `tools/verify_pack.py`、`tools/verify_live.py`、`tools/verify_plugin.mjs`、`tools/verify_shots.py` + 辅助 `tools/verify_shots.ps1`（Win32 PrintWindow 窗口抓图）

## 0. 结论摘要

| 结论 | 内容 |
| --- | --- |
| 核心功能 | **全部 PASS**（见 §2 结论表） |
| P0 缺陷 | **0 个** |
| P1 缺陷 | **0 个** |
| 原主宠物 main | **未受影响**：main 条目 sha256 与部署前快照完全一致；`/thumb/main/待机呼吸休闲.webm` 仍 200 且 content-length 与磁盘一致（§5） |
| P2 观察项 | 4 条（GUI 401 抓图限制、脚底阴影触底规范差异、PrintWindow 黑底、静态 `<img>` 检查口径），均不阻塞交付（§7） |
| 证据 | `build/verify/*.json` + `build/shots/*.png`（§8、§9） |

## 1. 验证环境

| 项 | 值 |
| --- | --- |
| OS | Windows（本机，中文路径 UTF-8） |
| DSH Web GUI | `http://127.0.0.1:57076`（根路径需 token，未授权返回 401；dsh-pet 与插件前缀路由免鉴权） |
| Chrome | `C:\Program Files\Google\Chrome\Application\chrome.exe` 156.0.8078.80（headless=new） |
| ffmpeg | `imageio_ffmpeg` 内置 `ffmpeg-win64-v4.2.2.exe`（**已知限制：解码 VP9-alpha 会丢 alpha 通道**，故 alpha 以 Chrome 截图验证） |
| Python / Node | Python 3.8.6（PIL 7.2.0 / numpy 1.24.4） / Node v22.23.1 |
| pet pack 部署位置 | `C:\Users\20862\.dsh\dsh-pet\pet\`（只读探测，未修改） |
| 插件安装位置 | `C:\Users\20862\.dsh\profiles\desktop\node_modules\dsh-pet-ai-girls`（profile bundles 已含 `dsh-pet-ai-girls`） |

## 2. 结论表（检查项 | 命令 | 结果 | 证据）

| 检查项 | 命令 | 结果 | 证据/路径 |
| --- | --- | --- | --- |
| pet pack 结构 + 媒体（8 角色 × 17 动画） | `python tools/verify_pack.py` | **PASS**（PASS=101, FAIL=0, WARN=0, SKIP=0） | `build/verify/verify_pack.json` |
| 活 /config：main + 8 条目、pets/animations/weights | `python tools/verify_live.py --strict` | **PASS**（PASS=20, FAIL=0, WARN=0, SKIP=0） | `build/verify/verify_live.json` |
| 全量 thumb 路由（8 角色 × 23 引用 = 184 条） | `python tools/verify_live.py --strict --all-thumbs` | **PASS**（184/184 HTTP 200 video/webm，PASS=20） | `build/verify/verify_live_full.json` |
| 插件壳结构 / ESM / 图鉴引用 / test_host | `node tools/verify_plugin.mjs` | **PASS**（PASS=25, WARN=1→口径问题, SKIP=1） | `build/verify/verify_plugin.json`、`build/verify/test_host_output.txt` |
| 插件 mock 部署 + HTTP 路由冒烟 | `node tools/test_host.mjs`（verify_plugin 自动 spawn） | **PASS=40 FAIL=0 SKIP=0** | 同上输出尾部 |
| 插件活路由 `/dsh-pet-ai-girls/`、`/health`、`/data.json` | verify_live 内置探测 | **PASS**：均 200 text/html / application/json | `build/verify/verify_live.json` → `plugin_routes` |
| alpha 透明（Chrome 棋盘截图 + 像素对比） | `python tools/verify_shots.py` | **PASS**：identical=0.86/0.86，black≈0.001，棋盘透出 | `build/shots/alpha-test.png`、`alpha-bg.png`、`alpha-crop-*.png` |
| 图鉴页（file:// 与实机 200 路由） | `python tools/verify_shots.py` + Chrome | **PASS**：1600×1200 正常渲染 | `build/shots/gallery.png`、`build/shots/gallery-live.png` |
| 真实窗口（9 个桌宠窗口 + 1 个 DSH GUI） | `python tools/verify_shots.py`（内部调 verify_shots.ps1） | **PASS**：标题匹配 dsh-pet 共 10 窗口，全部抓图成功 | `build/shots/pet-windows/window-01..10*.png`、`build/verify/windows_pet.json` |
| pet pack 预览页（8/8 待机动画来自活路由） | `python tools/verify_shots.py` | **PASS**：8/8 下载 200 video/webm 且 content-length 与磁盘一致；截图正常 | `build/shots/petpack-preview.png`、`build/verify/preview.html`、`build/verify/assets/` |
| 母版预检（build/webm，打包前） | 独立 ffmpeg 全量解析 | **PASS**：136/136 媒体合法、ALPHA_MODE=1 | `build/verify/precheck_build_webm.json` |

> 说明：插件安装完成前实测 `/dsh-pet-ai-girls/*` 为 404（DSH 未热加载），最终复测已全部 200，故最终结论为 PASS；早期 404 只作过程记录。

## 3. pet pack 清单（8 角色 × 17 动画 = 136 webm，81,419,973 B ≈ 77.65 MiB）

部署/打包目录：`plugin/packs/` 与 `~/.dsh/dsh-pet/pet/` 一致；素材布局为 host 原生**扁平布局** `<prefix>-animation/<动画名>.webm`（非 webm/ 子目录），校验脚本两种布局均兼容。

| # | 角色 id | 实际前缀 | 名称 | size | display | corner/margins | 动画数 | 大小 (B) | 媒体 FAIL |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | deepseek | girl-deepseek | DeepSeek 娘 | 360 | both | bottom-left 40/30 | 17 | 9,492,276 | 0 |
| 2 | gpt | girl-gpt | GPT 娘 | 320 | both | bottom-left 40/360 | 17 | 11,408,073 | 0 |
| 3 | claude | girl-claude | Claude 娘 | 340 | both | top-left 40/90 | 17 | 10,257,187 | 0 |
| 4 | grok | girl-grok | Grok 娘 | 320 | both | top-left 40/470 | 17 | 11,068,776 | 0 |
| 5 | gemini | girl-gemini | Gemini 娘 | 340 | both | bottom-right 40/30 | 17 | 12,129,456 | 0 |
| 6 | kimi | girl-kimi | Kimi 娘 | 320 | both | bottom-right 40/340 | 17 | 9,439,051 | 0 |
| 7 | glm | girl-glm | GLM 娘 | 300 | both | bottom-right 40/610 | 17 | 8,723,861 | 0 |
| 8 | qwen | girl-qwen | Qwen 娘 | 340 | both | top-right 40/470 | 17 | 8,901,293 | 0 |

结构/契约校验（全部 PASS）：8 个 `<prefix>-config.json` 严格 JSON 可解析；`pets[]` 非空、id/name/size/balanceEnabled/display/position 字段齐全合法且 id 全局唯一（不与 main 冲突）；`animations` 的 idle/turn/drag/clicks/moves/default/actions/categories/events 结构合法；`events.balance` 及 whisper/workStatus 各档非空；`animationWeights.idle/turn/move` 非负（idle=82/turn=0/move=0）；每角色 23 处动画引用全部命中 17 个素材文件（引用 ⊆ 文件）；8 个 pack 的动画名集合完全一致（17 个中文动画名）。

媒体参数（全部 PASS）：136/136 webm 均为 **640×360、24 fps、时长 1.29–6.0 s（>0.8s）、文件 >20KB**；ALPHA_MODE=1 共 136/136（ffmpeg 元数据；alpha 真正透明另由 Chrome 棋盘截图为证）。

## 4. 活 /config 摘要（main + 8 个 girl-* 条目，无多余条目）

- 条目集合：`main, girl-claude, girl-deepseek, girl-gemini, girl-glm, girl-gpt, girl-grok, girl-kimi, girl-qwen`（testgirl 测试条目已清除，额外条目检查 PASS）。
- 8 个新条目：`pets` 均 1 个实例（id=前缀、name=对应 AI 娘名、size 300–360、display=both、position 合法）；animations 齐全（idle=3, turn=1, drag=1, clicks=3, moves.actions=0, categories=1 组[小动作]，events=balance/whisper/workStatus 三档非空）；animationWeights 合法。
- thumb 抽检（每角色 3 个：待机呼吸 / 工作状态-思考冒泡 / 点击回应-开心跃动）：**24/24 全部 200 + content-type=video/webm + content-length 与磁盘源文件一致**。
- 全量路由（--all-thumbs）：**184/184 引用全部 200 video/webm 且 content-length 一致**。
- 预览页下载的 8 个待机动画 content-length 与磁盘完全一致：claude 752,738 / deepseek 721,619 / gemini 925,339 / glm 643,393 / gpt 859,382 / grok 841,784 / kimi 709,232 / qwen 660,531（B）。

## 5. 原主宠物 main 未受影响（明确结论）

| 证据 | 结果 |
| --- | --- |
| main 条目整段 sha256（部署前 10:53 快照 vs 部署后实测） | `ff008a7e9fa056a7dabefd7676b0c70644ec9532ac45fc324a04beb68f432d1a` **完全相同** |
| `GET /dsh-pet-7340/thumb/main/待机呼吸休闲.webm` | **200**，content-type=video/webm，content-length=441,437 与磁盘一致 |
| main.pets | 1 个实例 id=main；whisperPrompt/physics/idle/clicks(5)/categories(5)/events(balance,whisper,workStatus) 完整 |
| 部署前快照 | `build/verify/live-config-initial.json`（仅 main 条目，10:53 抓取） |

**结论：原主宠物 main 配置与素材路由均未被本次交付破坏。**

## 6. 插件壳（dsh-pet-ai-girls v1.0.0，host-only）

- `package.json`：name=dsh-pet-ai-girls、version=1.0.0、type=module、main=./index.js 存在、`dsh.bundle.patch=./cordis.patch.yml` 存在、icon=./icon.png（PNG 256×256，60,724 B ≤256KiB）；无 `dsh.client` / `exports['./client']`（host-only 符合设计）。
- `cordis.patch.yml`：id 与 name 均为 `dsh-pet-ai-girls`（PASS；首轮正则因行尾注释误报 FAIL，已修正验证脚本后复测 PASS）。
- `index.js`：15,481 B；`node --check` 语法 PASS；ESM 动态 import 成功（导出 `apply, default, inject, name`）；含 packs 部署 / pet 目录 / dsh-pet-ai-girls 路由实现关键词。
- `visual/index.html` + `visual/data.json`：图鉴数据内嵌 JSON 的 **32 个本地图片引用全部存在**（立绘/三视图各 8，含 thumbs）；`data.json` 可解析且 32 引用全存在；无静态本地 `<img src>`（图片由内嵌 JSON+JS 动态渲染，属设计，见 §7-P2-4）。
- `tools/test_host.mjs`（packager 提供）：**PASS=40 FAIL=0 SKIP=0**（临时 DSH_HOME 幂等部署 + HTTP 路由 mock，含 GET/HEAD/POST 405、visual 16 张原图、icon ≤256KiB 等）。
- 活路由（插件已安装进 profile 后）：`/dsh-pet-ai-girls/` → 200 text/html；`/health` → 200 JSON（`ok:true, deployed:true, animationCount:17, characters: 8`）；`/data.json` → 200 JSON。
- 安装痕迹：`C:\Users\20862\.dsh\profiles\desktop\node_modules\dsh-pet-ai-girls`（v1.0.0），profile `dependencies` 为 `file:node_modules/dsh-pet-ai-girls`，`dsh.profile.bundles` 已包含 `dsh-pet-ai-girls`。

## 7. 缺陷清单与观察项

### P0（阻断交付）— 0 个
### P1（严重）— 0 个

### P2（非阻塞：环境限制 / 检查口径 / 设计观察）

1. **DSH GUI 根路径 401，headless 无法直接截 GUI 网页**
   - 现象：`GET http://127.0.0.1:57076/` → `401 dsh web authentication required; reopen the URL printed by dsh web.`（该 URL 需携带 dsh web 启动时打印的 token）。
   - 处理：GUI 证据改用 Win32 PrintWindow 抓真实窗口（`build/shots/dsh-gui-window.png`，1936×1048，真实 DSH 界面内容）。不影响用户实际使用。
   - 另：GUI 主窗口 PrintWindow 截图中未看到 web 侧桌宠 overlay（Chromium 合成层抓取限制），真实桌宠渲染证据以 9 个「dsh-pet 桌宠（桌面模式）」窗口截图为准。
2. **脚底接触阴影触及视频底边（Lead framecheck.json 判 fail，复核为 P2）**
   - `build/verify/framecheck.json`：136/136 动画 `bbox.maxY=359`、clip.bottom=true、pass=0。
   - 独立复核：触边像素是**脚底接触阴影**（见 `build/verify/frame-claude-bottom-zoom.png`），不是人物主体被裁；alpha 棋盘截图、9 个桌面窗口截图、预览页均未见角色被裁切。
   - 但 dsh-pet 内置素材脚底线为 `FEET_Y=330`（底部约 29px 余量），本 pack 内容延伸到 359；客户端按 330 计算 `bottomPad` 定位，理论上脚底/阴影相对地面落点会略低（约 10–16px 视 size 而定）。
   - 建议：下轮若追求与内置素材完全一致，可在 animlib 输出时底部预留 ~24–30px 再打包；本轮不建议为此重渲 136 个文件（不阻塞交付）。
3. **PrintWindow 抓透明桌宠窗口时背景为纯黑**
   - 属 DWM/透明窗口截图限制（每宠物一个透明置顶窗口），非交付缺陷；字符本体与气泡、挂件清晰可见。透明性已由 alpha 棋盘截图（§2）和预览页单独证明。
4. **verify_plugin 的静态 `<img>` 检查 WARN / CSS url() SKIP（检查口径，不是缺陷）**
   - 图鉴页图片引用集中在 `<script id="gallery-data">` 内嵌 JSON 并由 JS 动态渲染，静态 HTML 无 `<img src>`；已对 gallery-data 与 data.json 的 32 个引用逐一验证存在，且 Chrome 两种方式（file:// 与实机 200 路由）截图渲染正常。
5. **其他设计观察（INFO）**：8 个 pack 的 `events.balance` 复用 idle/clicks 素材（6 项），`balanceEnabled=false`、`whisperEnabled=false`、`memes={}`——与 spec.py/config 设计一致，host 规则允许；17 个动画全部为 pack 私有素材，host 侧确认不回落 main 素材（`/thumb/girl-*/...` 只查自身目录）。

## 8. 截图与视觉证据清单

| 证据 | 路径 | 说明 |
| --- | --- | --- |
| alpha 视频页 | `build/shots/alpha-test.png` | 2 个 pack webm 置于棋盘格，字符与棋盘清晰 |
| alpha 背景页 | `build/shots/alpha-bg.png` | 同布局无视频（像素对比基准） |
| alpha 裁剪 | `build/shots/alpha-crop-0-待机呼吸.png`、`alpha-crop-1-点击回应-开心跃动.png` | 视频区域裁剪，透明可见 |
| 图鉴页（file://） | `build/shots/gallery.png` | 1600×1200，8 角色立绘/三视图/特征/动画表渲染正常 |
| 图鉴页（实机路由） | `build/shots/gallery-live.png` | `http://127.0.0.1:57076/dsh-pet-ai-girls/` 200 渲染，与 file:// 一致 |
| pet pack 预览页 | `build/shots/petpack-preview.png` | 1600×900，8/8 角色待机动画（活路由下载）+ 名字/size/corner/棋盘底 |
| 真实桌宠窗口 ×9 | `build/shots/pet-windows/window-01..09-*.png` | 9 个「dsh-pet 桌宠（桌面模式）」窗口：720×579×2(main+DeepSeek)、680×547×3(Claude/Gemini/Qwen)、640×515×3(GPT/Grok/Kimi)、600×483×1(GLM) |
| 真实 DSH GUI 窗口 | `build/shots/dsh-gui-window.png`、`.../window-10-*.png` | PrintWindow 1936×1048，真实 DSH 界面 |
| 窗口枚举 JSON | `build/verify/windows_pet.json`、`build/verify/windows_gui.json` | 句柄/尺寸/标题/抓图路径 |
| （Lead 生成，供交叉引用） | `build/shots/pets/pet-01..10.png`、`build/shots/pets/windows.json`、`mapping.json` | 与我的 10 窗口抓图一致（8 新宠 + main + GUI） |
| 帧复核 | `build/verify/frame-claude-idle.png`、`frame-main-idle.png`、`frame-claude-bottom-zoom.png` | 脚底阴影触底的独立复核 |

## 9. 复现命令

```powershell
cd F:\ceshi\dsh-pet-ai-girls
python tools/verify_pack.py                                   # PASS=101 FAIL=0
python tools/verify_live.py --strict                          # PASS=20 FAIL=0
python tools/verify_live.py --strict --all-thumbs --out build\verify\verify_live_full.json   # 184/184 thumb 路由
node tools/verify_plugin.mjs                                  # PASS=25（内部 spawn test_host.mjs: 40 PASS）
python tools/verify_shots.py                                  # PASS=16（alpha/图鉴/窗口/预览）
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools\verify_shots.ps1 `
  -TitleMatch "dsh-pet" -OutDir build\shots\pet-windows -JsonOut build\verify\windows_pet.json
```

证据 JSON：`build/verify/verify_pack.json`、`verify_live.json`、`verify_live_full.json`、`verify_plugin.json`、`verify_shots.json`、`precheck_build_webm.json`、`live-config-initial.json`、`test_host_output.txt`、`windows_pet.json`、`windows_gui.json`、`framecheck.json`（Lead）；以及 `verify_shots.ps1` 生成的 `windows_pet.json`。

## 10. 最终判定

**PASS（可交付）**。8 个 AI 娘 pet pack 的结构、媒体参数、引用完整性、8 条 live 条目与 184 条 thumb 路由、插件壳与图鉴页、真实桌面窗口渲染、alpha 透明与 pet pack 预览页全部通过；原主宠物 main 配置指纹与动画路由完全未受影响。仅存 P2 级环境限制/检查口径/视觉细节观察，无 P0/P1。

---

## 11. v1.1 增补（2026-11-06 11:34）

> v1.1 行为变更（同一时间只显示 1 只 + 自由切换当前桌宠）的复验结果见独立报告：
> **`build/verify/REPORT-v1.1.md`**（新增工具 `tools/verify_switch.py`；验证项 A–F 全部覆盖）。
> 摘要：切换端到端 PASS=28 FAIL=0；8 config 恰好 1 个 `display=both`、marker active=deepseek；
> reload 后仅 2 个桌面宠物窗口；图鉴页 switcher 双状态验证通过；最终状态已恢复 active=deepseek；
> main 未受影响。v1.1 遗留 P2：`tools/test_host.mjs` 3 条断言仍写死 1.0.0（测试文件过期，产品正常）、
> 图鉴内嵌 data 版本号仍为 1.0.0、GUI web overlay 抓图限制。
