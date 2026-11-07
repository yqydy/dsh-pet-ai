# dsh-pet-ai-girls v1.2「三视图 2.5D 转台」复验报告

- 项目根：`F:\ceshi\dsh-pet-ai-girls`
- 验证者：verifier（独立实现；不改被测源码，只写 `build/verify/`、`build/shots/`、`tools/verify_*`）
- 验证时间：2026-11-07 11:38–11:52（Asia/Shanghai）
- 被测版本：`dsh-pet-ai-girls v1.2.0`（plugin/package.json + profile 已安装 + pet pack 已部署 + `POST /dsh-pet-7340/reload` 已执行）
- 运行环境变化：DSH GUI 端口本次为 **http://127.0.0.1:50679**（verify_live/verify_plugin/verify_shots/verify_switch 均以 `--base-url http://127.0.0.1:50679` 运行）
- 本次改动：`tools/threeview.py` 拆三视图 → `build/threeview/<id>-{front,side,back}.png`；`animlib.TurnCharacter` 2.5D 转台；6 个动画改 2.5D；136 webm 重渲（72.77 MiB）；clicks 增「转圈展示」、categories weight=24/3 actions、weights=76/0/0；插件/图鉴 1.2.0。
- 工具：`tools/verify_pack.py`（增量 v1.2 契约）、`tools/verify_live.py`（增量 v1.2 pools/版本）、`tools/verify_plugin.mjs`（增量 v1.2 文档截图/版本/活 API）、**新增 `tools/verify_25d.py`（2.5D 定量证据）**、`tools/verify_shots.py`、`tools/verify_switch.py`、`tools/verify_shots.ps1`

## 0. 结论摘要

| 结论 | 内容 |
| --- | --- |
| A. pet pack / 配置 / marker | **PASS**（verify_pack PASS=112 FAIL=0）：marker=1.2.0；8 config clicks=4 含「转圈展示」、categories weight=24/3 actions、weights=76/0/0；136 webm 全部 640×360/24fps/ALPHA_MODE=1，总 72.77 MiB 与 build/webm 母版一致 |
| B. 2.5D 转台定量证据 | **PASS**（verify_25d PASS=44 FAIL=0）：8 角色「转圈展示」侧面剪影 min/front=**0.649–0.843**；背面 vs 正面剪影 XOR 为待机基线 **2.6–8.6×**；27% 帧画面差异为待机 **1.5–2.1×**；两侧窗口均变窄且结尾回正；东张西望等 12 个转身动作全部有显著换向 |
| C. 活 DSH（50679） | **PASS**（verify_live PASS=32 WARN=1，WARN 为已知 host 代码缓存）：/config 仍 main+8 条、新 pools 生效；/data.json version=1.2.0；/health packVersion=1.2.0、active=deepseek、characters 8；**/health version=1.1.0 属已知模块缓存（重启 DSH 生效）**；200 条 thumb 路由全 200 |
| D. 插件 / 测试 | **PASS**（verify_plugin PASS=33 WARN=2 SKIP=1）：version=1.2.0；`test_host.mjs` **PASS:44 FAIL:0**；图鉴 gallery-data version=1.2.0；docs 截图齐全；活 /health 版本缓存按 WARN 记录 |
| E. 桌面窗口 & 切换回归 | **PASS**（verify_switch PASS=28）：仍只有 **2 个**「dsh-pet 桌宠（桌面模式）」窗口（main 720×579 + 当前 680×547）；切换/切回抽测一次 PASS；测完 active 已恢复 **deepseek** |
| F. 截图/证据 | `build/shots/live-anim-deepseek-montage.png`（实机 360° 抓帧）、`build/spin-review/*.png`（12 张逐帧 montage）、`docs/screenshots/turntable-360.png`、`turntable-actions.png`、`live-2.5d-spin.png` 均存在；我方另生成 `build/verify/25d-montage-*.png` 等 |
| 原主宠物 main | **未受影响**：main 条目 sha256=`ff008a7e…` 与 v1.0/v1.1 基线一致；main thumb 200 且 content-length=441,437 与磁盘一致 |
| 最终状态 | **active=deepseek**（API/marker/config/窗口一致），2 个桌宠窗口，未把状态留在其他角色 |
| P0 / P1 / P2 | **P0=0，P1=0，P2=2**（均为已知环境/缓存限制，不阻塞交付）+ 2 条 INFO |

## 1. 结论表（v1.2 复验项 A–F）

| # | 检查项 | 命令/方式 | 结果 | 证据 |
| --- | --- | --- | --- | --- |
| A1 | 部署 marker version=1.2.0 == package.json | `python tools/verify_pack.py --expect-active deepseek` | **PASS** marker.version=1.2.0，pkg=1.2.0 | `build/verify/verify_pack.json` → `v12` |
| A2 | 8 config clicks=4 且含「转圈展示」 | 同上 | **PASS** 8/8：[开心跃动, 害羞惊讶, 元气挥手, 转圈展示] | 同上 |
| A3 | 8 config categories 单组 weight=24 actions=3 | 同上 | **PASS** 8/8：`[{"weight":24,"actions":["转圈展示","东张西望","伸懒腰"]}]` | 同上 |
| A4 | 8 config animationWeights=76/0/0 | 同上 | **PASS** 8/8 | 同上 |
| A5 | 136 webm 媒体校验（640×360/24fps/ALPHA_MODE=1） | 同上（ffmpeg 全量） | **PASS** 136/136，总 **76,302,568 B=72.77 MiB** | 同上 |
| A6 | packs 媒体与 build/webm 母版一致 / 引用全命中 | 同上 | **PASS** 136 个/72.77 MiB 完全一致；引用 200/200 | 同上 |
| B1 | 转圈展示：侧面剪影明显变窄 | `python tools/verify_25d.py` | **PASS** 8/8（side_min/front = 0.649–0.843，阈值≤0.90） | `build/verify/verify_25d.json` |
| B2 | 转圈展示：背面与正面可区分 | 同上 | **PASS** 8/8（xorf=0.056–0.096，为待机基线 2.6–8.6×；chg 0.126–0.191） | 同上 |
| B3 | 转圈展示：27% 帧画面差异显著 | 同上 | **PASS** 8/8（chg 0→27%=0.123–0.160，待机 1.5–2.1×） | 同上 |
| B4 | 转圈展示：360° 覆盖（两侧变窄+结尾回正） | 同上 | **PASS** 8/8（另一侧 ratio 0.619–0.886；结尾/front 0.967–1.006） | 同上 |
| B5 | 东张西望（8 角色）+ 其余 4 个 2.5D 动作（deepseek） | 同上 | **PASS** 12/12（xorf 1.5–10.0× 待机 或 width_var 1.06–1.44） | 同上 |
| C1 | live /config：main+8 条目、新 pools 生效 | `python tools/verify_live.py --base-url http://127.0.0.1:50679 --strict --expect-active deepseek --all-thumbs` | **PASS**（PASS=32 WARN=1）：8 条目 pools 全对；恰好 girl-deepseek both | `build/verify/verify_live.json` |
| C2 | 200 条 thumb 路由 | 同上 `--all-thumbs` | **PASS** 200/200（每角色 25 引用）200 video/webm 且 content-length 与磁盘一致 | 同上 |
| C3 | /health：packVersion=1.2.0、active=deepseek、8 chars | 同上 | **PASS**（version=1.1.0 记 WARN，见 P2-1） | 同上 |
| C4 | 图鉴 /data.json version=1.2.0 | 同上 | **PASS** | 同上 |
| C5 | main 未受影响 | 同上 | **PASS** main sha256 与基线一致；main thumb 200/441,437B | 同上 |
| D1 | 插件 version=1.2.0 / gallery-data=1.2.0 | `node tools/verify_plugin.mjs --base-url=http://127.0.0.1:50679` | **PASS** | `build/verify/verify_plugin.json` |
| D2 | docs 截图/证据文件存在 | 同上 | **PASS** turntable-360/actions、live-2.5d-spin、live montage 均存在 | 同上 → `v12.docs_screenshots` |
| D3 | `tools/test_host.mjs` | 同上（自动 spawn） | **PASS: 44 / FAIL: 0 / SKIP: 0 / RESULT: PASS** | `build/verify/test_host_output.txt` |
| D4 | 活插件 /health、/api/current、/data.json | 同上 | /data.json、/api/current **PASS**；/health 版本缓存 **WARN**（已知） | 同上 → `live.*` |
| E1 | 桌面窗口仍只有 2 个 | verify_switch + verify_shots PrintWindow | **PASS** 2 个（720×579 main + 680×547 当前） | `build/verify/verify_switch.json` |
| E2 | 切换/切回抽测 | `python tools/verify_switch.py --base-url http://127.0.0.1:50679` | **PASS**（PASS=28 FAIL=0）：qwen↔deepseek 一次通过，测完恢复 deepseek | 同上 |
| F1 | 关键截图可读/引用 | 人工查看 + 文件存在性 | **PASS**（见 §7） | `build/shots/`、`docs/screenshots/`、`build/spin-review/` |

## 2. A. pet pack / 配置 / marker（verify_pack v1.2）

`python tools/verify_pack.py --expect-active deepseek` → **PASS=112 FAIL=0 WARN=0 SKIP=0**

- **部署 marker**：`C:\Users\20862\.dsh\dsh-pet\pet\.dsh-pet-ai-girls.json` → `version=1.2.0`，与 `plugin/package.json` 一致；active marker 仍 active=deepseek。
- **配置**（8/8 完全一致）：
  - `clicks = [点击回应-开心跃动, 点击回应-害羞惊讶, 点击回应-元气挥手, 转圈展示]`（4 个）
  - `categories = [{id:小动作, weight:24, actions:[转圈展示, 东张西望, 伸懒腰]}]`
  - `animationWeights = {idle:76, turn:0, move:0}`
  - v1.1 契约保持：恰好 `girl-deepseek display=both`、其余 none；size 全 340；position 全 bottom-right/40/40。
- **素材**：136 个 webm（8×17），总 **76,302,568 B = 72.77 MiB**，与 `build/webm/` 母版逐字节总量一致（重渲后打包一致）；全部 640×360、24fps、时长合法、>20KB、`ALPHA_MODE=1` 136/136；每角色 25 处动画引用全部命中（200/200），8 pack 动画名集合一致。
- `build/threeview/`：32 张 PNG（8 角色 × front/side/back + 8 张 review），三视图拆分产物齐全。

## 3. B. 2.5D 转台定量证据（verify_25d，独立实现）

方法：用 ffmpeg（libvpx-vp9）从 `build/webm/<char>/转圈展示.webm`（2.79s）按 0%/27%/52%/77% 抽帧，并做 5% 步进扫描；同时取 `待机呼吸.webm` 4 帧作为「普通纸片人微动」基线。指标：
- `side_min/front`：15–35% 窗口最窄剪影宽度 / 正面剪影宽度（侧面应明显窄）；
- `back xorf`：30–65% 窗口内与正面剪影 XOR 最大帧（背面应与正面可区分），并对比待机基线；
- `chg`：像素差（max-channel diff>24 的比例）；
- `end ratio`：≥90% 帧宽度 / 正面宽度（应回正）。
> 已知限制：ffmpeg 4.2.2 解码 VP9-alpha 会丢 alpha（背景变黑），剪影用亮度阈值提取，属方法学限制，不影响相对比较；alpha 透明性另由 Chrome 棋盘截图验证（§6-F）。

**逐角色「转圈展示」结果（全部 PASS）**

| 角色 | 正面宽 | 侧身最窄帧 | side_min/front | 27%帧 ratio | 背面帧 | back xorf | 背面/待机 | chg 0→27% | 待机 chg | 结尾/front |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| deepseek | 166 | 25% w=140 | **0.843** | 0.916 | 35% | 0.0560 | 3.8× | 0.1232 | 0.0692 | 1.006 |
| gpt | 177 | 27% w=121 | **0.684** | 0.684 | 60% | 0.0601 | 3.5× | 0.1383 | 0.0757 | 1.000 |
| claude | 185 | 30% w=120 | **0.649** | 0.697 | 30% | 0.0630 | 5.0× | 0.1432 | 0.0935 | 1.005 |
| grok | 187 | 27% w=130 | **0.695** | 0.695 | 60% | 0.0690 | 2.8× | 0.1443 | 0.0864 | 0.995 |
| gemini | 183 | 30% w=120 | **0.656** | 0.721 | 40% | 0.0842 | 4.4× | 0.1462 | 0.0954 | 0.995 |
| kimi | 184 | 30% w=128 | **0.696** | 0.766 | 50% | 0.0958 | 8.6× | 0.1597 | 0.0778 | 0.984 |
| glm | 182 | 27% w=138 | **0.758** | 0.758 | 65% | 0.0578 | 2.6× | 0.1297 | 0.0747 | 0.967 |
| qwen | 176 | 30% w=115 | **0.653** | 0.676 | 30% | 0.0642 | 5.4× | 0.1489 | 0.0829 | 0.983 |

结论：8/8 角色「正面→侧面（剪影明显变窄）→背面（剪影与正面差异大）→另一侧→回正」完整；逐帧 montage 见 `build/verify/25d-montage-<char>.png`（如 `25d-montage-deepseek.png` 四帧为 正面/侧身/背面/侧身）。

**其它 2.5D 动作（12/12 PASS）**

| 角色 | 动画 | 剪影 XOR | 待机倍数 | width_var | 判定 |
| --- | --- | --- | --- | --- | --- |
| deepseek | 东张西望 | 0.0462 | 3.1× | 1.124 | PASS |
| deepseek | 点击回应-害羞惊讶 | 0.1082 | 7.3× | 1.034 | PASS |
| deepseek | 点击回应-开心跃动 | 0.0229 | 1.5× | 1.347 | PASS（宽度变化） |
| deepseek | 工作状态-雀跃庆祝 | 0.0508 | 3.4× | 1.160 | PASS |
| deepseek | 被鼠标拖拽悬空反馈 | 0.1474 | 10.0× | 1.308 | PASS |
| gpt / claude / grok / gemini / kimi / glm / qwen | 东张西望 | 0.0463–0.0647 | 2.3–4.5× | 1.057–1.443 | PASS |

`build/verify/25d-actions-deepseek.png` 为 5 个动作的中段帧 montage（可见明显侧身/背身）。

## 4. C. 活 DSH 状态（http://127.0.0.1:50679）

`python tools/verify_live.py --base-url http://127.0.0.1:50679 --strict --expect-active deepseek --all-thumbs` → **PASS=32 FAIL=0 WARN=1 SKIP=0**

- `/dsh-pet-7340/config`：条目 = `main` + 8 个 `girl-*`（无多余）；8 条目 animations 完整且**新 pools 全部生效**：clicks=4（含转圈展示）、categories=24/3、weights=76/0/0；恰好 `girl-deepseek display=both`、其余 none；size/position 统一。
- thumb 路由：**200/200**（8 角色 × 25 引用）全部 200 video/webm，content-length 与磁盘一致。
- `/dsh-pet-ai-girls/health`：`packVersion=1.2.0`、`deployed=true`、`animationCount=17`、`active=deepseek`、8 角色且唯一 active；`version=1.1.0` 为 host 模块缓存（P2-1，WARN）。
- `/dsh-pet-ai-girls/data.json`：`version=1.2.0`（PASS）。
- `/dsh-pet-ai-girls/api/current`：200，active=deepseek，8 characters。
- `/health`/`/dsh-pet-ai-girls/`/`/data.json` 路由均 200。
- **main 未受影响**：main sha256=`ff008a7e9fa056a7dabefd7676b0c70644ec9532ac45fc324a04beb68f432d1a`（与 v1.0 部署前快照一致）；main idle 路由 200，content-length=441,437 与磁盘一致。

## 5. D. 插件 / 测试（verify_plugin v1.2）

`node tools/verify_plugin.mjs --base-url=http://127.0.0.1:50679` → **PASS=33 FAIL=0 WARN=2 SKIP=1**

- `package.json` version=**1.2.0**、type=module、main/cordis.patch/icon（256×256 PNG 60,724B）/host-only 全部 PASS。
- `index.js` 语法/E​SM import 正常；含 packs 部署、`/petgirl`、`api/switch`、`api/current`、active marker、`/dsh-pet-7340/reload` 实现。
- 图鉴：内嵌 gallery-data version=**1.2.0**、`visual/data.json` 与 32 个图片引用全部存在；`docs/screenshots/{turntable-360,turntable-actions,live-2.5d-spin}.png` 与 `build/shots/live-anim-deepseek-montage.png` 全部存在（`v12.docs_screenshots` PASS）；`build/spin-review/` 12 张 montage 存在。
- **`node tools/test_host.mjs`：PASS: 44 / FAIL: 0 / SKIP: 0 / RESULT: PASS / exit 0**（临时 DSH_HOME 部署 + HTTP 路由 mock，含新断言）。
- 活 API：`/data.json` version=1.2.0 PASS、`/api/current` PASS；`/health` 因 host 模块缓存 version=1.1.0 → **WARN（已知，重启 DSH 生效）**。
- WARN/SKIP 其余为既有检查口径：静态 `<img>` 由内嵌 JSON 动态渲染（WARN）、无 CSS url()（SKIP），均非缺陷。

## 6. E/F. 桌面窗口、切换回归与截图证据

**桌面窗口 & 切换回归**
- 复验期间桌面始终只有 **2 个**「dsh-pet 桌宠（桌面模式）」窗口：**720×579（main）+ 680×547（当前角色）**；`POST /dsh-pet-7340/reload` 后新素材生效（窗口内可见 2.5D 动作）。
- `python tools/verify_switch.py --base-url http://127.0.0.1:50679` → **PASS=28 FAIL=0**：qwen↔deepseek 抽测一次通过（切换后 8 config 恰好 qwen both、窗口 2 个、切换前后 680 窗口内容像素差 0.38、图鉴 switcher 状态正确）；**测完最终 active=deepseek**，main 指纹全程不变。
- 最终状态：`/api/current active=deepseek`；marker active=deepseek；`/config` 恰好 girl-deepseek both；窗口 2 个（680×547 handle 3212182 + 720×579 handle 4917440）。

**截图/证据清单（v1.2）**

| 证据 | 路径 | 说明 |
| --- | --- | --- |
| 实机 360° 转台抓帧 | `build/shots/live-anim-deepseek-montage.png`（200,258 B，1600×954，20 帧 @200ms） | 真实桌面窗口逐帧：正面→侧身→背面→侧身→正面，含气泡，证明实机 2.5D 生效 |
| 同一证据（docs） | `docs/screenshots/live-2.5d-spin.png`（200,258 B，与上同图） | 已入文档 |
| 渲染帧转台 | `docs/screenshots/turntable-360.png`（193,565 B，1600×460，10 帧 0.00–2.74s） | 正面/侧身/背面随 t 变化清晰 |
| 2.5D 动作帧 | `docs/screenshots/turntable-actions.png`（250,814 B，1600×644） | 东张西望/害羞转身/拖拽侧身/雀跃转圈 逐帧 |
| 逐帧 montage（Lead 生成） | `build/spin-review/` 12 张（deepseek×6、grok×6，各 186–234 KB） | 转圈/东张西望/害羞/开心/雀跃/拖拽 |
| 我方定量 montage | `build/verify/25d-montage-<char>.png`（8 张）、`build/verify/25d-actions-deepseek.png`、`build/verify/25d-frames/` 原帧 | 四帧/动作帧证据，标注 ASCII 便于复核 |
| 图鉴页（v1.2，file://） | `build/shots/gallery.png`（1,167,535 B，1600×1200） | 含「2.5D 三视图转台」说明区与全部角色 |
| 图鉴页切换 UI（实机路由） | `build/shots/gallery-switcher.png` / `gallery-switcher-qwen.png`（254,008 / 267,539 B） | 切换 UI + DeepSeek/Qwen「当前」徽标 |
| alpha 透明 | `build/shots/alpha-test.png`、`alpha-bg.png`、`alpha-crop-*.png` | 2 个 pack webm 棋盘对比：identical 0.86/0.85，black≈0，棋盘透出 → PASS |
| pet pack 预览页 | `build/shots/petpack-preview.png`（879,460 B） | 8/8 待机动画来自活路由，棋盘+深色底预览 |
| 桌宠真实窗口 | `build/shots/pet-windows/window-01..02-*.png`（680×547 当前 + 720×579 main） | PrintWindow 实截图（verify_shots PASS=14 WARN=1） |
| 图鉴静态说明 | `plugin/visual/index.html` §「2.5D 三视图转台」说明（含正面→侧面→背面→侧面→正面描述） | 页面内可见（file:// 与实机路由同一文件） |

## 7. 缺陷与观察项

### P0（阻断）— 0 个
### P1（严重）— 0 个

### P2（非阻塞，均为已知限制）

1. **host 代码模块缓存：`/health.version` 仍为 1.1.0，而 package.json/packVersion=1.2.0**
   - 原因：当前 DSH 进程内插件 host 代码是 v1.1.0（Node ESM 模块缓存），重启 DSH 才会加载 v1.2.0 host 代码；pet pack 与图鉴数据（不走 host 代码缓存）已是 1.2.0。
   - 影响：`/health` 的 version 字段滞后；切换/部署/图鉴等实际功能均为 v1.2.0（packVersion、data.json、config 均 1.2.0）。按 Lead 指示记 **WARN**（verify_live / verify_plugin 各 1 条），不判 FAIL。
   - 验证：`packVersion=1.2.0`、`data.json version=1.2.0`、8 config 新 pools 全生效、test_host 44 PASS。
2. **GUI web overlay 无法直接截图（环境限制，沿袭 v1.0/v1.1）**
   - DSH GUI 根路径 401（需 dsh web token），headless 无法直抓；PrintWindow 抓 Chromium 窗口时 web 侧桌宠 overlay 不可见。
   - 本轮证据替代：实机桌面窗口逐帧抓图（`live-anim-deepseek-montage.png`）+ 2 个桌宠窗口 + 图鉴页 + 活 API；verify_shots 的 GUI 主窗口抓图因窗口当前最小化记 WARN（非缺陷）。

### INFO（观察，不影响判定）

1. ffmpeg 4.2.2 解码 VP9-alpha 丢 alpha（背景黑），2.5D 剪影指标基于亮度阈值；alpha 透明性由 Chrome 棋盘截图单独验证 PASS（identical 0.86、black≈0）。
2. deepseek「转圈展示」精确 27% 帧宽度比 0.916 略高于其它角色（0.68–0.77），但其侧身最窄在 25%（ratio 0.843）；按「27% 附近侧面变窄」判定 PASS，记录该差异供后续微调参考。

## 8. 复现命令

```powershell
cd F:\ceshi\dsh-pet-ai-girls
python tools/verify_pack.py --expect-active deepseek          # PASS=112 FAIL=0；136 文件/72.77 MiB
python tools/verify_25d.py                                    # PASS=44 FAIL=0；2.5D 定量证据 → build/verify/verify_25d.json
python tools/verify_live.py --base-url http://127.0.0.1:50679 --strict --expect-active deepseek --all-thumbs
                                                              # PASS=32 WARN=1（host 缓存 WARN）
node tools/verify_plugin.mjs --base-url=http://127.0.0.1:50679 # PASS=33 WARN=2 SKIP=1；test_host 44 PASS
python tools/verify_shots.py --base-url http://127.0.0.1:50679  # PASS=14 WARN=1
python tools/verify_switch.py --base-url http://127.0.0.1:50679 # PASS=28；测完自动恢复 active=deepseek
```

证据 JSON：`build/verify/verify_pack.json`（含 v11/v12）、`verify_live.json`、`verify_plugin.json`、`verify_25d.json`、`verify_shots.json`、`verify_switch.json`、`test_host_output.txt`、`windows_v12_final.json`；转台帧：`build/verify/25d-frames/`、`build/verify/25d-montage-*.png`、`build/verify/25d-actions-deepseek.png`。

## 9. 最终判定

**v1.2 验证 PASS，可交付**：三视图拆分与 2.5D 转台在素材层（136 webm 重渲、new pools 生效）、定量层（8 角色转圈侧面剪影 0.649–0.843、背面剪影差异 2.6–8.6× 待机基线、12 个转身动作全部显著换向）、实机层（live 200ms 抓帧 360° 转台、2 个桌宠窗口、切换回归 PASS）均得到独立证据支持；原主宠物 main 未受影响；插件/图鉴版本 1.2.0 与测试（test_host 44 PASS）正常。P0/P1=0，仅 P2 两条已知限制（host 模块缓存版本显示滞后、GUI overlay 抓图限制），不阻塞交付。最终 active=deepseek 已确认。
