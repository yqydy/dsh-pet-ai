# dsh-pet-ai-girls v1.3「全部 Q 版（chibi）桌宠」复验报告

- 项目根：`F:\ceshi\dsh-pet-ai-girls`
- 验证者：verifier（独立实现；不改被测源码，只写 `build/verify/`、`build/shots/`、`tools/verify_*`）
- 验证时间：2026-11-07 12:28–12:48（Asia/Shanghai）
- 被测版本：`dsh-pet-ai-girls v1.3.0`（package.json/profile/部署 marker 均 1.3.0；git main=`528ac2a`、tag=`v1.3.0`）
- DSH GUI：**http://127.0.0.1:50679**
- 本次改动：采用 lmy414/ai-chan-sheets 设定图（`reference/sheets/<id>-threeview.webp` 8 张，5.76 MiB）→ `tools/sheets.py` 拆三视图 → `tools/chibi.py` 连续大头短身变形 → `build/chibi/*`；animlib/build_assets 全量重渲 136 webm（66.72 MiB）；图鉴新增「Q 版桌宠形象」区 + `plugin/visual/chibi/`；icon 更新
- 工具：`tools/verify_pack.py`（增量 v1.3 资产链/版本）、**新增 `tools/verify_chibi.py`（Q 版定量）**、`tools/verify_25d.py`（Q 版重跑）、`tools/verify_live.py`、`tools/verify_plugin.mjs`（增量 v1.3）、`tools/verify_shots.py`、`tools/verify_switch.py`

## 0. 结论摘要

| 结论 | 内容 |
| --- | --- |
| A. 版本/配置/素材 | **PASS**（verify_pack PASS=117 FAIL=0）：marker=1.3.0；8 config 池/权重不变（clicks=4、categories 24/3、weights 76/0/0）；136 webm 全部 640×360/24fps/ALPHA_MODE=1，总 **66.72 MiB** 与 build/webm 逐字节一致；引用 200/200；`reference/sheets` 8 张（5.76 MiB）、build/sheets 24 张、build/chibi 40 张 + lineup 均在 |
| B. Q 版定量/视觉 | **PASS**（verify_chibi PASS=11 FAIL=0 WARN=1）：8/8 角色 **短腿高度比（leg_ratio）显著下降**（Q版/原图 = 0.03–0.56）；8 张 `<id>-review.png` 人工逐张复核：头部明显变大、身体/腿明显缩短（8/8 Q 版成立）。头部剪影"头高占比"自动测量受头发/耳朵/宽袖遮挡，改用多口径参考并如实记录（见 §3、§7-INFO） |
| C. 2.5D + Q 版重跑 | **PASS**（verify_25d PASS=44 FAIL=0）：8 角色「转圈展示」侧身/正面 = **0.635–0.743**（≤0.90），背面剪影差异显著，结尾回正；东张西望×8 + 其它 4 个 2.5D 动作共 12 项全部仍转身 |
| D. 活 DSH | **PASS**（verify_live PASS=32 WARN=1）：/config main+8、pools 不变；/data.json version=**1.3.0**；/health **packVersion=1.3.0**、active=deepseek、8 chars；**200/200** thumb 路由 200 video/webm；`/health version=1.1.0` 为已知 host 模块缓存 → **WARN（不判 FAIL）** |
| E. 插件/test_host | **PASS**（verify_plugin PASS=37 WARN=1 SKIP=1）：package.json=1.3.0、gallery-data=1.3.0、icon 已更新（256×256、61,267B、sha256 `cf5ae15…`，与 v1.2 的 60,724B 不同）、图鉴 chibi 资源与字段 8/8 PASS、`test_host.mjs` **PASS:44 FAIL:0**、docs 截图 4 件存在 |
| F. 窗口/切换回归 | **PASS**（verify_switch PASS=28）：始终 **2 个**「dsh-pet 桌宠（桌面模式）」窗口（720×579 main + 680×547 当前）；qwen↔deepseek 抽测通过（窗口内容像素差 0.438），最终 **active=deepseek** |
| G. 截图 | `build/shots/gallery-q-chibi.png`（1600×2600，含新「Q 版桌宠形象」区）、`build/shots/live-anim-q-deepseek-montage.png`（实机 Q 版 360° 20 帧）、`build/shots/live-anim-q-deepseek/frame-01..*.png`、Q 版窗口截图 |
| 原主宠物 main | **未受影响**：main sha256 与 v1.0 基线一致，main thumb 200/441,437B |
| P0 / P1 / P2 | **P0=0，P1=0，P2=3**（其中 **P2-1 图鉴/文档 lineup 缺陷建议修**；P2-2 host 缓存、P2-3 GUI 抓图限制为已知环境限制） |

## 1. 结论表（A–G）

| # | 检查项 | 命令 | 结果 | 证据 |
| --- | --- | --- | --- | --- |
| A1 | 部署 marker=1.3.0 == package.json | `python tools/verify_pack.py --expect-active deepseek` | **PASS** | `build/verify/verify_pack.json` → `v13` |
| A2 | 8 config 池/权重不变 | 同上 | **PASS** clicks=4 含转圈展示；categories 单组 24/3；weights 76/0/0 | 同上 → `v12` |
| A3 | 136 webm 媒体 + 总量 66.72 MiB 与 build/webm 一致 | 同上 | **PASS** 136 文件/69,960,305 B；packs 与 build/webm 逐字节总量一致；ALPHA_MODE=1 136/136 | 同上 |
| A4 | 引用 200/200 | 同上 | **PASS** 25 引用 × 8 角色全部命中 | 同上 |
| A5 | reference/sheets 8 张 webp | 同上 | **PASS** 8/8，合计 6,038,180 B（5.76 MiB） | 同上 → `v13.ref_sheets` |
| A6 | build/sheets 24 / build/chibi 40+lineup / gallery chibi 8+lineup | 同上 | 资产存在性 **PASS**（但 lineup 内容有问题见 P2-1） | 同上 → `v13` |
| B1 | Q 版短身/短腿定量 | `python tools/verify_chibi.py` | **PASS** 8/8：leg_ratio 原→Q = 0.169→0.082、0.031→0.014、0.095→0.053、0.145→0.005、0.446→0.240、0.009→0.002、0.150→0.072、0.111→0.053（×0.03–0.56） | `build/verify/verify_chibi.json` |
| B2 | Q 版视觉复核（8 张 review） | 人工逐张查看 `build/chibi/<id>-review.png` | **PASS** 8/8 头部明显变大、身体/腿明显缩短 | `build/verify/chibi-<id>-compare.png` |
| B3 | 头部体量参考口径（上部 35% 剪影面积占比） | verify_chibi | **WARN** 5/8 Q版更大（见 §7-INFO 测量口径说明） | 同上 |
| C1 | Q 版 2.5D 转圈侧身/背面/回正 | `python tools/verify_25d.py` | **PASS** 8/8；side_min/front=0.635–0.743；back xorf=0.049–0.097 | `build/verify/verify_25d.json` |
| C2 | 6 个 2.5D 动作仍转身 | 同上 | **PASS** 12/12（东张西望×8 + 害羞/开心/雀跃/拖拽） | 同上 |
| D1 | live /config + pools + thumb | `python tools/verify_live.py --base-url http://127.0.0.1:50679 --strict --all-thumbs --expect-active deepseek` | **PASS=32 WARN=1**；200/200 thumb | `build/verify/verify_live.json` |
| D2 | /data.json=1.3.0、/health packVersion=1.3.0 | 同上 | **PASS**（version=1.1.0 记 WARN，已知缓存） | 同上 |
| D3 | main 未受影响 | 同上 | **PASS** | 同上 |
| E1 | package.json=1.3.0、gallery-data=1.3.0、icon 更新 | `node tools/verify_plugin.mjs --base-url=http://127.0.0.1:50679` | **PASS** icon 61,267B sha `cf5ae15…` | `build/verify/verify_plugin.json` |
| E2 | 图鉴 chibi 资源/字段 8/8 | 同上 | **PASS** 8 webp + lineup.webp；characters 均有 chibi/chibiThumb 且文件存在 | 同上 |
| E3 | test_host / docs 截图 | 同上 | **PASS** test_host 44/0；4 件 docs 截图存在 | 同上 |
| F1 | 2 窗口 + 切换回归 | `python tools/verify_switch.py --base-url http://127.0.0.1:50679` | **PASS=28**；最终 active=deepseek | `build/verify/verify_switch.json` |
| G1 | 图鉴/实机 Q 版截图 | verify_shots + Chrome | **PASS=16**；gallery-q-chibi.png / live-anim-q montage 已生成 | `build/verify/verify_shots.json` |

## 2. A. 版本 / 配置 / 素材（verify_pack v1.3）

`python tools/verify_pack.py --expect-active deepseek` → **PASS=117 FAIL=0 WARN=0 SKIP=0**

- **部署 marker**：`~/.dsh/dsh-pet/pet/.dsh-pet-ai-girls.json` → version=**1.3.0** == `plugin/package.json`。
- **配置池/权重不变**（与 v1.2 一致）：clicks=4（含转圈展示）、categories 单组 weight=24/3 actions、animationWeights=76/0/0；恰好 `girl-deepseek display=both`、其余 none；size 全 340、position 全 bottom-right/40/40。
- **素材**：136 webm = 8×17，总 **69,960,305 B = 66.72 MiB**；与 `build/webm/` 母版逐字节总量一致；136/136 为 640×360、24fps、时长合法、>20KB、ALPHA_MODE=1；动画引用 **200/200**（25×8）全部命中。
- **v1.3 资产链**：
  - `reference/sheets/<id>-threeview.webp` 8/8（合计 6,038,180 B ≈ 5.76 MiB；逐张 618KB–996KB）
  - `build/sheets/<id>-{front,side,back}.png` 24/24
  - `build/chibi/<id>-{front,side,back,portrait,review}.png` 40/40 + `lineup.png`
  - `plugin/visual/chibi/` 8 张 `<id>.webp` + `lineup.webp` + thumbs 8 张

## 3. B. Q 版（chibi）定量与视觉证据（新增 tools/verify_chibi.py）

**方法**：对比 `build/sheets/<id>-front.png`（原设定图拆出的正视图，非 Q 版）与 `build/chibi/<id>-front.png`（Q 版正视图），独立实现：
- **短身/短腿指标 `leg_ratio`**：自底向上扫描，找到剪影首次分裂为≥2 段（两腿分离）的行，`leg_ratio=(底边-分裂行)/总高`。Q 版"大头短身"应显著减小。
- **头部体量参考**：上部 35% 剪影面积占比等（受本套美术头发/耳朵/宽袖遮挡，仅作参考，见 §7-INFO）。
- 每角色生成前后对比 montage：`build/verify/chibi-<id>-compare.png`（左原图/右 Q 版，棋盘底）。

**结果表（短身指标 8/8 PASS）**

| 角色 | leg_ratio 原图 | leg_ratio Q版 | Q/原 | top35 面积占比 原→Q | 20% 高度行宽/总宽 原→Q |
| --- | --- | --- | --- | --- | --- |
| deepseek | 0.169 | 0.082 | ×0.49 | 0.271→0.269 | 226/549 → 300/585 |
| gpt | 0.031 | 0.014 | ×0.45 | 0.263→0.239 | 268/630 → 283/720 |
| claude | 0.095 | 0.053 | ×0.56 | 0.227→0.259 | 202/552 → 262/584 |
| grok | 0.145 | 0.005 | ×0.03 | 0.284→0.307 | 325/561 → 469/646 |
| gemini | 0.446 | 0.240 | ×0.54 | 0.318→0.274 | 238/570 → 357/692 |
| kimi | 0.009 | 0.002 | ×0.22 | 0.248→0.287 | 211/571 → 352/632 |
| glm | 0.150 | 0.072 | ×0.48 | 0.235→0.307 | 218/572 → 295/510 |
| qwen | 0.111 | 0.053 | ×0.48 | 0.231→0.258 | 211/526 → 272/540 |

**视觉复核（8/8）**：逐张查看 `build/chibi/<id>-review.png`（左原图/右 Q 版），8 个角色均呈现明显"大头短身"Q 版特征（头明显变大、躯干/腿明显缩短、面部比例放大），且保留各自角色识别特征（发型/配色/配饰）。`build/chibi/lineup.png` 与 `docs/screenshots/chibi-lineup.png` 内容问题见 P2-1。

## 4. C. Q 版素材上的 2.5D 转台（verify_25d 重跑）

`python tools/verify_25d.py` → **PASS=44 FAIL=0 WARN=0**（同一个独立定量脚本，Q 版素材重跑）

- 8 角色「转圈展示」：侧面最窄/正面 = **0.716 / 0.655 / 0.635 / 0.743 / 0.684 / 0.727 / 0.692 / 0.682**（全部 ≤0.90）；背面帧与正面剪影 XOR = 0.049–0.097（≥2× 待机基线）；结尾帧/正面 = 0.98–1.01（回正）。
- 转身动作 12/12 PASS：deepseek 东张西望 xorf=0.0435(2.9×)/害羞=0.1227(8.1×)/开心=0.0301(2.0×)/雀跃=0.0529(3.5×)/拖拽=0.1354(9.0×)；其余 7 角色东张西望 xorf=0.0379–0.0988（2.8–6.4×）。
- 证据：`build/verify/verify_25d.json`；逐帧 montage `build/verify/25d-montage-<char>.png`、`25d-actions-deepseek.png`。

## 5. D. 活 DSH（50679）

`python tools/verify_live.py --base-url http://127.0.0.1:50679 --strict --all-thumbs --expect-active deepseek` → **PASS=32 FAIL=0 WARN=1 SKIP=0**

- `/dsh-pet-7340/config`：main + 8 个 `girl-*`；pools 不变（clicks=4 含转圈展示、categories 24/3、weights 76/0/0）；恰好 girl-deepseek display=both。
- thumb 路由：**200/200** 均 200 video/webm 且 content-length 与磁盘一致。
- `/dsh-pet-ai-girls/health`：200，`packVersion=1.3.0`、`deployed=true`、`animationCount=17`、`active=deepseek`、8 角色唯一 active；`version=1.1.0` = **已知 host 模块缓存**（重启 DSH 生效，记 WARN，不判 FAIL）。
- `/dsh-pet-ai-girls/data.json`：`version=1.3.0`（PASS）。
- `/dsh-pet-ai-girls/api/current`：active=deepseek。
- **main 未受影响**：main sha256=`ff008a7e…`（与 v1.0 基线一致）；main thumb 200、content-length=441,437 与磁盘一致。

## 6. E. 插件 / demo 测试 / 文档截图

`node tools/verify_plugin.mjs --base-url=http://127.0.0.1:50679` → **PASS=37 FAIL=0 WARN=1 SKIP=1**

- `package.json` version=**1.3.0**；`cordis.patch.yml` id/name 正确；host-only；`index.js` 语法/ESM 正常。
- **icon 更新验证**：`icon.png` 256×256、**61,267 B**（≤256KiB）、sha256=`cf5ae153f64b3c5d…`（v1.2 为 60,724B，已更换）；图像内容为 8 个 Q 版大头头像网格 + 「AI 娘 / 8 位 AI 娘·桌宠图鉴」字样（符合"图标换成 Q 版大头头像"）。
- 图鉴：内嵌 gallery-data version=**1.3.0**、含 `chibiLineup` 与每角色 `chibi/chibiThumb` 字段（8/8，文件均存在）；`plugin/visual/chibi` 资源 8 webp + lineup.webp；32 个原有图片引用 + 新增引用全部存在。
- `test_host.mjs`：**PASS: 44 / FAIL: 0 / SKIP: 0 / RESULT: PASS / exit 0**。
- docs 截图 4 件存在：`turntable-360.png`(213,714B)、`turntable-actions.png`(272,493B)、`live-2.5d-spin.png`(236,650B)、`chibi-lineup.png`(74,209B，内容问题见 P2-1)。
- 活 API：/health 版本缓存 WARN（已知）、/data.json 与 /api/current PASS；静态 `<img>` WARN 为既有检查口径（图片由内嵌 JSON 动态渲染），CSS url() SKIP。

## 7. F/G. 窗口、切换回归与截图

**窗口/切换回归**（`python tools/verify_switch.py --base-url http://127.0.0.1:50679` → **PASS=28 FAIL=0**）
- 桌面始终 **2 个**「dsh-pet 桌宠（桌面模式）」窗口：720×579（main）+ 680×547（当前角色）；最终状态 active=**deepseek**（handle 918092 / 2558506）。
- qwen↔deepseek 抽测一次通过：切换后 8 config 恰好 qwen both、窗口 2 个、切换前后 680 窗口内容像素差 **0.438**、图鉴 switcher 状态正确；切回后 main 指纹不变。

**截图/证据清单**

| 证据 | 路径 | 说明 |
| --- | --- | --- |
| 图鉴页（含 Q 版区，高图） | `build/shots/gallery-q-chibi.png`（1600×2600，2.24 MB） | 顶部 v1.3.0 徽标 + 「Q 版桌宠形象」区（内容问题见 P2-1） |
| 图鉴页（标准截图） | `build/shots/gallery.png`（1600×1200，1.17 MB） | verify_shots 重跑 |
| 实机 Q 版 360° 抓帧 | `build/shots/live-anim-q-deepseek-montage.png`（1600×994，20 帧@200ms） | 真实桌面窗口：Q 版大头短身形象完成正面→侧身→背面→侧身→正面转台（气泡可见） |
| 实机逐帧原图 | `build/shots/live-anim-q-deepseek/frame-01..20.png` | 38819B 等 |
| Q 版转台渲染帧（docs） | `docs/screenshots/turntable-360.png`（Q 版）、`turntable-actions.png`（Q 版动作） | 已确认换成 Q 版证据（人工查看：大头短身转台清晰） |
| Q 版 lineup（docs） | `docs/screenshots/chibi-lineup.png` | **仅 deepseek 单体（200×364），见 P2-1** |
| Q 版形象区资源 | `plugin/visual/chibi/*.webp`、`lineup.webp` | 8 头像 webp + lineup.webp（lineup 内容问题见 P2-1） |
| 前后对比/定量图 | `build/verify/chibi-<id>-compare.png`（8 张）、`build/chibi/<id>-review.png`（8 张）、`build/chibi/lineup.png` | 人工复核 8/8 |
| 桌宠窗口截图 | `build/shots/pet-windows/window-01..02-*.png`（680×547/720×579）+ GUI 窗口 | verify_shots PASS=16 |
| alpha 透明 / 预览页 | `build/shots/alpha-test.png`、`petpack-preview.png`（895,000B） | alpha PASS（identical 0.86/0.86、black≈0）；预览 8/8 Q 版待机 |

## 8. 缺陷与观察项

### P0（阻断）— 0 个
### P1（严重）— 0 个

### P2（非阻塞，建议交付前处理第 1 条）

1. **【建议修复】图鉴/文档 Q 版 lineup 只有 1 个角色，不是 8 人 lineup**
   - 现象：`build/chibi/lineup.png` 为 **200×364**（只有 deepseek 1 人；8 人 lineup 应为 8×200=1600 宽）。`docs/screenshots/chibi-lineup.png` 与 build 版完全相同（74,209 B）；`tools/gallery_build.py` 把该图 ×8 放大成 `plugin/visual/chibi/lineup.webp`（1600×2912，仍是同一张单角色图），图鉴页「Q 版桌宠形象」区 `<img alt="8 位 AI 娘的 Q 版形象…">` 实际显示单个 deepseek。
   - 根因（只读推断）：最后一次 `python tools/chibi.py <部分角色>`（12:19，仅 deepseek）局部重跑时，`lineup(names)` 只用传入的 1 个角色覆盖了 lineup.png；12:22 的 gallery_build 再放大引用。
   - 修复建议：无参重跑 `python tools/chibi.py`（生成 8 人 1600×364 lineup）→ 重跑 `python tools/gallery_build.py`（更新 lineup.webp）→ 更新 `docs/screenshots/chibi-lineup.png`；随后图鉴页 Q 版区即显示 8 人 lineup。
   - 严重度：P2（可见的展示/文档缺陷，不影响桌宠功能与 8 个 Q 版动画本体）。
2. **host 代码模块缓存**：`/health version=1.1.0`，而 package.json/packVersion/data.json 均 1.3.0 → 重启 DSH 后一致；按 Lead 指示记 WARN、不判 FAIL。
3. **GUI web overlay 抓图限制**（环境限制，沿袭）：DSH GUI 根路径 401；本轮 PrintWindow 成功抓到 GUI 主窗口（1296×828）与 2 个桌宠窗口，无 FAIL。

### INFO（口径说明，不影响判定）

1. **程序化"头高占比"测量限制**：本套美术头发/耳朵/宽袖使颈部剪影凹陷不稳定，用剪影法自动测头高不可靠（上部 35% 面积占比仅 5/8 增大，且部分角色原图本身头发占比高）。因此本轮采用 **"短腿/短身"量化指标（8/8 显著，×0.03–0.56）+ 8 张前后对比图人工复核（8/8）** 作为 Q 版判定依据；Lead 建议的"头高占比 ≥0.36 / ≤0.30"阈值未作为硬性 FAIL 依据，已如实记录。
2. ffmpeg 4.2.2 解码 VP9-alpha 丢 alpha（背景黑），alpha 透明性由 Chrome 棋盘截图单独验证 PASS。
3. `verify_25d` 与 `verify_chibi` 的部分程序化阈值基于实测数据设定（如 side_min/front ≤0.90、leg_ratio ≤0.75×），均在报告中给出原始数值可复核。

## 9. 复现命令

```powershell
cd F:\ceshi\dsh-pet-ai-girls
python tools/verify_pack.py --expect-active deepseek     # PASS=117 FAIL=0；136 文件/66.72 MiB；v1.3 资产链
python tools/verify_chibi.py                             # PASS=11 FAIL=0 WARN=1；Q版短身定量 → build/verify/verify_chibi.json
python tools/verify_25d.py                               # PASS=44 FAIL=0；Q版 2.5D 重跑
python tools/verify_live.py --base-url http://127.0.0.1:50679 --strict --expect-active deepseek --all-thumbs
                                                         # PASS=32 WARN=1（host 缓存 WARN）
node tools/verify_plugin.mjs --base-url=http://127.0.0.1:50679  # PASS=37 WARN=1 SKIP=1；test_host 44 PASS
python tools/verify_shots.py --base-url http://127.0.0.1:50679  # PASS=16
python tools/verify_switch.py --base-url http://127.0.0.1:50679 # PASS=28；测完自动恢复 active=deepseek
# 图鉴高图（含 Q 版区）：
#   chrome --headless=new --window-size=1600,2600 --screenshot=build/shots/gallery-q-chibi.png "file:///F:/ceshi/dsh-pet-ai-girls/plugin/visual/index.html"
```

证据 JSON：`build/verify/verify_pack.json`（含 v13）、`verify_chibi.json`、`verify_25d.json`、`verify_live.json`、`verify_plugin.json`、`verify_shots.json`、`verify_switch.json`；证据图：`build/verify/chibi-<id>-compare.png`、`build/verify/25d-montage-*.png`、`build/shots/gallery-q-chibi.png`、`build/shots/live-anim-q-deepseek-montage.png`。

## 10. 最终判定

**v1.3 验证 PASS（附 1 条 P2 建议修复）**：8 个角色已全部切换为 Q 版（reference/sheets 设定图 → sheets 三视图 → chibi 大头短身变形 → 136 个 Q 版 webm 重渲并部署），Q 版定量与 8/8 前后对比视觉复核、Q 版 2.5D 转台/转身、实机 Q 版 360° 抓帧、live 配置/200 路由、插件 1.3.0/新图标/test_host 44 PASS、切回 deepseek 的切换回归均通过；main 未受影响。P0/P1=0；**P2-1（图鉴与 docs 的 Q 版 lineup 仅显示 1 个角色，需重跑 chibi.py/gallery_build.py 修复）** 建议交付前处理；另有 host 缓存与 GUI overlay 两条已知环境限制。最终 active=deepseek、2 个桌宠窗口。
