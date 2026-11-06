# dsh-pet-ai-girls v1.1「单角色显示 + 自由切换」复验报告

- 项目根：`F:\ceshi\dsh-pet-ai-girls`
- 验证者：verifier（独立实现；不改被测源码，只写 `build/verify/`、`build/shots/`、`tools/verify_*`）
- 验证时间：2026-11-06 11:22–11:34（Asia/Shanghai）
- 被测版本：`dsh-pet-ai-girls v1.1.0`（plugin/package.json、profile 已安装、DSH 已热加载）
- 变更摘要：8 组 pet pack 仍全部部署，但同一时间只有 1 组 `display='both'`（其余 7 组 `display='none'`）；统一 `size=340 / bottom-right / 40,40`（原地换人）；持久化 `.dsh-pet/pet/.dsh-pet-ai-girls-active.json`；插件新增 `/petgirl` 命令、`GET /api/current`、`POST|GET /api/switch`、`/health.active`；图鉴页顶部新增「切换当前桌宠」按钮组。
- 工具：`tools/verify_pack.py`（已增量加入 v1.1 契约检查）、`tools/verify_live.py`（已加入 /health + /api/current 检查）、`tools/verify_plugin.mjs`（已加入 v1.1 静态检查 + 活 API 自测）、`tools/verify_switch.py`（**新增**，端到端切换验证）、`tools/verify_shots.py`、`tools/verify_shots.ps1`

## 0. 结论摘要

| 结论 | 内容 |
| --- | --- |
| 单角色显示契约 | **PASS**：8 份 config 恰好 `girl-deepseek` 一个 `display=both`，其余 7 个 `display=none`；size 全部 340；position 全部 bottom-right/40/40 |
| 切换端到端（qwen ↔ deepseek） | **PASS=28 FAIL=0**：POST/GET 切换 API、8 份 config 立即改写、active marker、live /config、2 个桌面窗口、图鉴页 UI 状态全部正确；测完已切回 deepseek |
| 桌面窗口数量 | **PASS**：切换后只有 **2 个**「dsh-pet 桌宠（桌面模式）」窗口（main 720×579 + 当前角色 680×547），不再一次出现 9 个 |
| 插件 v1.1 结构 / 活 API | 静态检查 PASS、活 `/health`+`/api/current` PASS；但 packager 自带 `tools/test_host.mjs` **FAIL（3 条断言仍写死 1.0.0，测试文件未同步 v1.1）** → P2 |
| 图鉴页切换 UI | **PASS**：实机路由渲染「切换当前桌宠」+ 8 chips，两个状态截图验证 chip「当前」与 note 文案随 API 变化 |
| 原主宠物 main | **未受影响**：main 条目 sha256 与 v1.0 部署前快照一致（`ff008a7e…`），main 窗口 720×579 始终存在 |
| 最终状态 | **active=deepseek**（API、marker、8 份 config、窗口均已确认恢复；未把状态留在 qwen） |
| P0 / P1 / P2 | **P0=0，P1=0，P2 剩余 1**（GUI web overlay 抓图限制，环境限制）；**P2-1（test_host 版本过期）与 P2-2（图鉴内嵌版本号 1.0.0）已修复并复验 PASS**（2026-11-06 11:37） |

## 1. 结论表（v1.1 重点项）

| # | 检查项 | 命令/方式 | 结果 | 证据 |
| --- | --- | --- | --- | --- |
| A1 | 8 config 恰好 1 个 display=both + 7 个 none | `python tools/verify_pack.py --expect-active deepseek` | **PASS** both=['girl-deepseek']，none=7 | `build/verify/verify_pack.json` → `v11` |
| A2 | 8 config 统一 size=340 | 同上 | **PASS** sizes=['340'] | 同上 |
| A3 | 8 config 统一 position=bottom-right/40/40 | 同上 | **PASS** | 同上 |
| A4 | `.dsh-pet-ai-girls-active.json` 存在且 active=deepseek 并与 both 一致 | 同上（读部署目录） | **PASS** active='deepseek'，both_prefix='girl-deepseek' | 同上 |
| A5 | 每份 config pets[0].id == 文件名前缀 | 同上 | **PASS** | 同上 |
| A6 | 动画引用/媒体仍全量合法（136/136） | 同上 | **PASS** 引用 184/184，媒体 136/136，总 77.65 MiB | 同上 |
| B1 | /config 仍 main + 8 条目、animations 完整 | `python tools/verify_live.py --strict --expect-active deepseek` | **PASS=30 FAIL=0** | `build/verify/verify_live.json` |
| B2 | /health version=1.1.0、active=deepseek、characters 8 个且 active 标记正确 | verify_live 内置探测 | **PASS** chars=8，active_marks=['deepseek'] | 同上 → `plugin_meta.health` |
| B3 | GET /api/current 200 且 active=deepseek | 同上 | **PASS** active='deepseek'，8 characters | 同上 → `plugin_meta.api_current` |
| C1 | POST /api/switch {"id":"qwen"} → ok/active=qwen/reloading=true | `python tools/verify_switch.py` | **PASS** status=200 ok=true active='qwen' reloading=true | `build/verify/verify_switch.json` |
| C2 | 切换后立即读 8 份 config：恰好 girl-qwen both、其余 none | 同上 | **PASS** both=['girl-qwen']，none=7/7，marker.active='qwen' | 同上 |
| C3 | 切换后 live /config 同步 | 同上 | **PASS** display=both 的条目 ['girl-qwen'] | 同上 |
| C4 | 桌面宠物窗口仅 2 个（720×579 main + 680×547 当前） | `verify_shots.ps1` PrintWindow | **PASS** qwen 状态 2 个（等待约 1.8s 窗口重建完成） | `build/shots/switch-windows/qwen/` |
| C5 | 680×547 窗口内容真的换成 Qwen 娘 | 抓图 + 内容区裁剪像素 diff | **PASS** diff_ratio=0.493（阈值 0.10），人工复核为 Qwen 娘（蓝紫衣裙+团扇） | `build/shots/switcher-qwen.png` |
| C6 | GET /api/switch?id=deepseek 切回 | 同上 | **PASS** ok=true active='deepseek' reloading=true | `build/verify/verify_switch.json` |
| C7 | 切回后 config/marker/live/window 全部恢复、窗口仍 2 个 | 同上 | **PASS** both=['girl-deepseek']；2 窗口（等待约 3.0s） | `build/shots/switcher-deepseek.png` |
| D1 | 图鉴页实机路由渲染「切换当前桌宠」区块 + 8 chips + 目标 chip「当前」 | Chrome headless 截图 + `--dump-dom` | **PASS** 两种状态均 PASS（DOM: `class="switch-chip is-active"` 的 data-id 分别为 qwen / deepseek；`当前桌宠：<b>Qwen 娘</b>` / `DeepSeek 娘`） | `build/shots/gallery-switcher-qwen.png`、`gallery-switcher.png`、`build/verify/gallery_*_dom.html` |
| E1 | package.json version=1.1.0 | `node tools/verify_plugin.mjs` | **PASS** | `build/verify/verify_plugin.json` |
| E2 | index.js 含 /petgirl、api/switch、api/current、active marker 关键词 | 同上 | **PASS**（四个关键词全部存在 + 含 `/dsh-pet-7340/reload`） | 同上 |
| E3 | 活插件 /health、/api/current 自测（verify_plugin 内置 fetch） | 同上 | **PASS** health version=1.1.0 active=deepseek；api/current ok=true active=deepseek | 同上 → `live.health` / `live.api_current` |
| E4 | `node tools/test_host.mjs` | verify_plugin 自动 spawn | **FAIL**（PASS=37 FAIL=3，3 条均为期望 1.0.0 的过期断言，见 §5-P2-1） | `build/verify/test_host_output.txt` |
| F1 | 截图证据齐备 | — | `switcher-qwen.png` / `switcher-deepseek.png` / `gallery-switcher.png` / `gallery-switcher-qwen.png` + 每状态窗口原图 | `build/shots/` |

## 2. A. pet pack v1.1 配置与持久化（verify_pack）

`python tools/verify_pack.py --expect-active deepseek` → **PASS=107 FAIL=0 WARN=0 SKIP=0**

- 8 个 `<prefix>-config.json`（前缀 `girl-<id>`）严格 JSON 可解析、`pets[0]` 字段完整合法。
- **单角色显示契约**：`display` 分布 = `{girl-deepseek: both, 其余 7 个: none}`（PASS）。
- **原地换人统一参数**：8 份 config `size=340`、`position={corner:'bottom-right', marginX:40, marginY:40}`（PASS）。
- **持久化 marker**：`C:\Users\20862\.dsh\dsh-pet\pet\.dsh-pet-ai-girls-active.json` 存在，内容
  `{"active":"deepseek","prefix":"girl-deepseek","name":"DeepSeek 娘","updatedAt":"2026-11-06T03:26:22.334Z"}`，与 `display=both` 的 pack 一致（PASS）。
- 动画引用/媒体回归：每角色 23 处引用全部命中 17 个 webm（引用 ⊆ 文件）；136/136 媒体参数仍合法（640×360 / 24fps / >0.8s / >20KB），ALPHA_MODE=1 136/136，总大小 81,419,973 B（77.65 MiB）。
- 部署目录检查（只读）：8 个 `girl-*-config.json` + 8 个 `girl-*-animation`（各 17 webm）+ `.dsh-pet-ai-girls.json`（version=1.1.0）+ `.dsh-pet-ai-girls-active.json`。

## 3. B. 活 DSH 状态（verify_live --strict）

`python tools/verify_live.py --strict --expect-active deepseek` → **PASS=30 FAIL=0 WARN=0 SKIP=0**

- `/dsh-pet-7340/config`：条目 = `main` + 8 个 `girl-*`（无多余条目）；8 条目 pets/animations/weights/events 完整；恰好 `girl-deepseek display=both`、其余 7 个 `none`；size 统一 340、position 统一 bottom-right/40/40。
- `/dsh-pet-ai-girls/health`：200 JSON，`version=1.1.0`、`packVersion=1.1.0`、`deployed=true`、`animationCount=17`、`active={id:deepseek,…}`、`characters` 8 个且**恰好 1 个 `active=true`（deepseek）**。
- `GET /dsh-pet-ai-girls/api/current`：200 JSON，`ok=true`、`active.id=deepseek`、`characters` 8 个，与 /health 一致。
- 插件静态路由 `/dsh-pet-ai-girls/`、`/health`、`/data.json` 均 200。
- thumb 路由抽检（每角色 3 个）+ main 路由：全部 200 video/webm，content-length 与磁盘一致。
- **main 未受影响**：main 条目 sha256 = `ff008a7e9fa056a7dabefd7676b0c70644ec9532ac45fc324a04beb68f432d1a`，与 v1.0 部署前 10:53 快照完全一致；main.pets=1(id=main)、animations(5 clicks/5 categories/3 events) 完整。

## 4. C. 切换端到端（verify_switch，本轮核心新增）

`python tools/verify_switch.py`（默认 deepseek → qwen → deepseek，失败也会 finally 切回）→ **PASS=28 FAIL=0 WARN=0 SKIP=0**，用时约 25s。

| 步骤 | 结果 |
| --- | --- |
| 初始状态 | `/api/current active=deepseek`；桌面窗口 2 个（680×547 当前 + 720×579 main）；截图 `switcher-initial.png` |
| `POST /dsh-pet-ai-girls/api/switch` body `{"id":"qwen"}` | 200 `{"ok":true,"active":{"id":"qwen","prefix":"girl-qwen","name":"Qwen 娘"},"reloading":true,...}` |
| 切换后**立即**读部署目录 8 份 config | 恰好 `girl-qwen display=both`，其余 7 份 `display=none`；size/position 统一；marker `active=qwen` |
| live `/dsh-pet-7340/config` | 恰好 `girl-qwen display=both`（与磁盘一致） |
| `/api/current` / `/health` | active=qwen；health active=qwen 且唯一 active 标记 qwen |
| 桌面窗口（reload 后） | 恰好 **2 个**「dsh-pet 桌宠（桌面模式）」窗口：680×547（当前 Qwen）+ 720×579（main），等待约 1.8s 重建完成；抓图 `build/shots/switch-windows/qwen/`，合成 `build/shots/switcher-qwen.png`（内容区裁剪，Qwen 娘：蓝紫衣裙 + 团扇） |
| 图鉴页（qwen 状态） | `gallery-switcher-qwen.png` 截图正常；DOM 校验 `switch-chip is-active data-id="qwen"`，`当前桌宠：Qwen 娘` |
| `GET /api/switch?id=deepseek` 切回 | 200 ok=true active=deepseek reloading=true |
| 切回后校验 | 8 份 config 恰好 `girl-deepseek both`、其余 none；marker active=deepseek；live /config 一致；`/api/current`、`/health` 均 deepseek；窗口仍 2 个（等待约 3.0s），合成 `switcher-deepseek.png`（DeepSeek 娘 蓝发女仆） |
| 换人证据 | 两次 680×547 窗口内容区像素 diff_ratio=**0.493**（阈值 0.10）→ 窗口内容确实从 Qwen 换成 DeepSeek |
| main 未受影响 | 全程 main 配置 sha256 不变（`ff008a7e…`）；main 窗口 720×579 始终存在 |
| 最终状态 | 已确认恢复 **active=deepseek**（API / marker / config / 窗口一致），未污染用户状态 |

## 5. D/E. 图鉴页切换 UI 与插件结构

**图鉴页（实机路由 `http://127.0.0.1:57076/dsh-pet-ai-girls/`，headless Chrome 1600×1200）**
- 「切换当前桌宠」区块渲染：标题 + 8 个角色 chip（DeepSeek/GPT/Claude/Grok/Gemini/Kimi/GLM/Qwen）+ note 文案。
- 状态 A（active=deepseek）：`gallery-switcher.png`，DeepSeek 娘 chip 带「当前」，`当前桌宠：DeepSeek 娘`。
- 状态 B（active=qwen，由切换 API 驱动）：`gallery-switcher-qwen.png`，Qwen 娘 chip 带「当前」，`当前桌宠：Qwen 娘`。
- DOM 校验（dump-dom）：`class="switch-chip is-active" data-id="<active>"` 与当前角色一致、`switch-note` 文案含当前角色名——该文案由页面 `fetch('/dsh-pet-ai-girls/api/current')` 渲染，证明 **GET /api/current 被页面消费**；两种状态都 PASS。

**插件结构（verify_plugin.mjs）**：PASS=29 FAIL=1 WARN=1 SKIP=1
- `package.json` version=1.1.0、type=module、main/cordis.patch/icon(≤256KiB PNG)/host-only 均 PASS。
- `index.js`（25,952 B）：`node --check` PASS、ESM import 导出 `apply,default,inject,name`；含 `/petgirl`、`api/switch`、`api/current`、`.dsh-pet-ai-girls-active`、`/dsh-pet-7340/reload` 实现（PASS）。
- 图鉴数据引用 32 个本地图片全部存在（PASS）。
- **活 API 自测**（verify_plugin 内置 fetch，新增）：/health 200 version=1.1.0 active=deepseek 8 角色唯一 active；/api/current 200 ok active=deepseek 8 characters（PASS）。
- **FAIL：`tools/test_host.mjs` 过期断言**（详见 §6-P2-1）。
- 安装确认：profile `node_modules/dsh-pet-ai-girls` = v1.1.0，`dependencies` 为 `file:node_modules/dsh-pet-ai-girls`，`dsh.profile.bundles` 含 `dsh-pet-ai-girls`；部署 marker `.dsh-pet-ai-girls.json` version=1.1.0。

## 6. 缺陷与观察项

### P0（阻断）— 0 个
### P1（严重）— 0 个

### P2（非阻塞）

> **修复复验记录（2026-11-06 11:37）**：P2-1、P2-2 已由 packager 修复，verifier 独立复验 PASS；P2-3 为环境限制保留。复验证据：
> `build/verify/test_host_output.txt`（PASS:44 FAIL:0 SKIP:0 / RESULT:PASS / exit 0）、
> `build/verify/verify_plugin.json`（PASS=30 FAIL=0 exit 0）、
> `build/verify/gallery_deepseek_dom_after_fix.html`（DOM: gallery-data version=1.1.0、v1.0 残留 0 处、badge `pet pack 已就绪 · v1.1.0`、switcher + DeepSeek「当前」）、
> `build/shots/gallery-switcher.png`（重新截图，徽标 v1.1.0）、`build/verify/gallery-badge-zoom.png`（徽标放大）、`build/verify/windows_final_v11fix.json`（最终仍 2 个桌宠窗口）。

1. **【已修复并复验 PASS】`tools/test_host.mjs` 曾写死 1.0.0（修复前 3 条 FAIL）**
   - 修复前实测：`PASS: 37 FAIL: 3 RESULT: FAIL`（`部署：版本 marker version=1.0.0`、`/health version=1.0.0`、`/health packVersion=1.0.0` 与实际 1.1.0 不符）。
   - 修复方式：期望值改为从 `plugin/package.json` 动态读取版本，并补 `/health.active`、`/api/current` 断言。
   - **修复后复验（独立执行 `node tools/test_host.mjs`，2026-11-06 11:36）**：`PASS: 44  FAIL: 0  SKIP: 0`、`RESULT: PASS`、`exit 0`（与 Lead 报告一致）；`node tools/verify_plugin.mjs` 复跑也变为 **PASS=30 FAIL=0, exit 0**。
2. **【已修复并复验 PASS】图鉴页内嵌版本号曾为 1.0.0**
   - 修复方式：`tools/gallery_build.py` 改为读 `plugin/package.json`，重新生成 `plugin/visual/data.json` 与 `index.html` 的 gallery-data，并同步到 profile 已安装插件。
   - **修复后复验**：`plugin/visual/data.json` version=**1.1.0**；`index.html` gallery-data version=**1.1.0**；**live `GET /dsh-pet-ai-girls/data.json` version=1.1.0**；profile 已安装 `visual/data.json` version=1.1.0；live 图鉴页 DOM 中 gallery-data version=1.1.0、`v1.0` 残留 **0 处**、状态徽标 `pet pack 已就绪 · v1.1.0`；「切换当前桌宠」区块仍正常、DeepSeek 娘 chip 带「当前」、`当前桌宠：DeepSeek 娘`；截图 `build/shots/gallery-switcher.png` 已更新。
3. **GUI web overlay 仍无法直接截图（继承 v1.0 环境限制，保留）**
   - DSH GUI 根路径 401（需 dsh web token），headless 无法带鉴权；PrintWindow 抓 Chromium 窗口时 web 侧桌宠 overlay 不可见。
   - 本轮 v1.1 的「同时只显示一只/切换生效」证据改用：真实桌面窗口数量（2 个）+ 窗口内容像素变化 + 图鉴页 switcher DOM + 活 API，已足够闭环；非功能缺陷。另：本轮 verify_shots 做 GUI 窗口抓图时该窗口处于最小化/未匹配状态，记为 WARN（可用 v1.0 的 `dsh-gui-window.png`，或下次窗口可见时重跑）。
4. （沿袭 v1.0，INFO）PrintWindow 抓透明桌宠窗口背景为纯黑、图鉴图片为 JS 动态引用；均非缺陷。

## 7. F. 截图与证据清单（v1.1 新增/更新）

| 证据 | 路径 | 说明 |
| --- | --- | --- |
| 切换前（deepseek）两窗口合成 | `build/shots/switcher-deepseek.png`（253,361 B） | 左：main 720×579；右：当前 DeepSeek 娘 680×547（内容区裁剪） |
| 切换到 qwen 后两窗口合成 | `build/shots/switcher-qwen.png`（197,736 B） | 左：main；右：当前 Qwen 娘（蓝紫衣裙+团扇） |
| 初始状态合成 | `build/shots/switcher-initial.png`（240,120 B） | 流程起始状态留证 |
| 图鉴页（qwen 为当前） | `build/shots/gallery-switcher-qwen.png`（1,024,661 B） | Qwen chip 带「当前」；当前桌宠：Qwen 娘 |
| 图鉴页（deepseek 为当前，最终主图） | `build/shots/gallery-switcher.png`（1,025,380 B） | DeepSeek chip 带「当前」；最终状态 |
| 每状态窗口原图 | `build/shots/switch-windows/{initial,qwen,deepseek}/window-01..*.png` | PrintWindow 原图（680×547 当前角色 + 720×579 main + GUI 窗口） |
| 图鉴页 DOM | `build/verify/gallery_qwen_dom.html`、`gallery_deepseek_dom.html` | switcher 状态与 /api/current 消费证据 |
| **P2 修复复验证据** | `build/verify/test_host_output.txt`、`build/verify/verify_plugin.json`、`build/verify/gallery_deepseek_dom_after_fix.html`、`build/verify/gallery-badge-zoom.png`、`build/verify/windows_final_v11fix.json`、`build/shots/gallery-switcher.png`（已更新徽标 v1.1.0） | test_host 44 PASS / data.json 1.1.0 / DOM 无 v1.0 残留 / 最终 active=deepseek 且 2 窗口 |
| v1.0 基线对照 | `build/shots/alpha-*.png`、`gallery.png`、`petpack-preview.png`、`pet-windows/` 等 | 素材/透明/图鉴回归证据（本轮 verify_shots 重跑：PASS=14，仅 GUI 窗口抓图 WARN） |

## 8. 复现命令

```powershell
cd F:\ceshi\dsh-pet-ai-girls
python tools/verify_pack.py --expect-active deepseek            # PASS=107 FAIL=0
python tools/verify_live.py --strict --expect-active deepseek   # PASS=30 FAIL=0
node tools/verify_plugin.mjs                                    # PASS=29 FAIL=1（test_host 3 条过期断言）
python tools/verify_switch.py                                   # PASS=28 FAIL=0（qwen ↔ deepseek，自动恢复）
python tools/verify_shots.py                                    # PASS=14 WARN=1（GUI 窗口抓图）
# 只列窗口：powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools\verify_shots.ps1 -TitleMatch "dsh-pet" -ListOnly
```

证据 JSON：`build/verify/verify_pack.json`、`verify_live.json`、`verify_plugin.json`、`verify_switch.json`、`verify_shots.json`、`test_host_output.txt`、`switch_final_windows.json`、`gallery_*_dom.html`。

## 9. 最终判定

**v1.1 行为变更验证 PASS，可交付**：「同一时间只显示 1 只 + 自由切换当前桌宠」全部链路（8 份 config 单 both、active marker 持久化、/petgirl/switch API、reload 后仅 2 个桌面窗口、图鉴页 switcher 与状态同步、切回恢复）实测通过；原主宠物 main 未受影响；最终状态已恢复 `active=deepseek`。P0/P1=0。**P2-1（test_host 版本过期，修复后 44 PASS/0 FAIL）与 P2-2（图鉴内嵌版本号，修复后 data.json=1.1.0、DOM 无 v1.0 残留）均已修复并复验 PASS；仅 P2-3（GUI web overlay 抓图属环境限制）保留，不阻塞交付。**

**P2 修复后最终状态复核（11:37）**：live `/config` 条目 = main + 8 个 girl-*，恰好 `girl-deepseek display=both`；`/api/current` active=deepseek；`/health` version=1.1.0 active=deepseek；main sha256=`ff008a7e…` 与 v1.0 快照一致；桌宠窗口恰好 2 个（720×579 main + 680×547 当前 DeepSeek 娘）。
