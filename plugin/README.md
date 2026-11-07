# dsh-pet-ai-girls —— 8 位 AI 娘桌宠素材包

> 给 [dsh-pet](https://github.com/PC2005-cloud/dsh-pet)（DSH 桌宠插件）用的 **pet pack 自动部署插件**：
> 把 8 位 AI 拟人娘的透明动画宠物装进你的桌面，并附一个纯本地的**立绘 / 三视图图鉴页**。
>
> 原角色设计 **ZipZipPipe（上善无形 / DeepSeek）**，来源
> [genderswapai.com · AI 拟人角色图鉴](https://genderswapai.com/zh-TW/ai-gijinka)，
> 以 **CC BY-NC-SA 4.0** 授权 —— 本项目是**非官方同人**作品，仅供个人/非商业使用。

![插件图标](icon.png)

---

## 它是什么

**8 只 Q 版（大头短身）AI 娘桌宠**：这是由 [lmy414/ai-chan-sheets](https://github.com/lmy414/ai-chan-sheets)
完整设定图的三视图程序化 chibi 化后、重新渲染成 dsh-pet 透明动画素材的 **host-only 纯文件插件**
（没有浏览器半边、无需构建、零依赖）：

| 职责 | 说明 |
| --- | --- |
| 🐾 自动部署 pet pack | DSH 宿主启动时，把包内 `packs/` 的 8 组 `girl-<id>-config.json` + `girl-<id>-animation/*.webm` **幂等**复制进 dsh-pet 的用户数据目录 `%USERPROFILE%\.dsh\dsh-pet\pet\`（或 `$DSH_HOME/dsh-pet/pet/`），并写版本 marker `.dsh-pet-ai-girls.json`。 |
| 🎀 同一时间只显示一只 | 8 组 pack 默认只有 **DeepSeek 娘** 的 `pets[0].display` 是 `both`，其余为 `none`；不会一启动就 8 只糊满桌面。 |
| 🔁 自由切换 | `/petgirl <id\|名字>` 斜杠命令、图鉴页顶部「切换当前桌宠」按钮组、HTTP API 三种入口；选择持久化到 `.dsh-pet-ai-girls-active.json`，切换时自动重建桌面宠物窗口。 |
| 🖼️ 本地图鉴页 | 注册 `/dsh-pet-ai-girls/` 前缀静态路由，提供 8 位角色的立绘、三视图、Q 版形象、特征、17 个动画列表、灯箱切换；另有 `/dsh-pet-ai-girls/health` 健康检查与 `/api/current`、`/api/switch` 切换接口。 |
| 🎞️ Q 版 + 2.5D 三视图转台 | v1.3.0 起 8 只全部是 Q 版（大头、短身、短腿）。用 Q 版三视图的 **正面 / 侧面 / 背面** 做真正的转身动画：360° 转圈展示、左右转身、点击转身/跳起转圈、拖拽侧身、庆祝转圈。视角切换处做透视压缩与运动模糊，地面阴影随剪影变化 —— 不是一张平面立绘在晃。 |
| 🔄 刷新即生效 | pet pack 一旦落盘，dsh-pet 每次页面加载都会重新扫描 `pet/` 目录 —— **刷新页面即见宠物**，无需重启 DSH（插件本体的 host 代码只需在安装时加载一次）。 |

- 8 位角色 × 17 个 Q 版动画 = **136 个透明 webm**（640×360、24fps、VP9-alpha，约 66.7MB），其中 6 个动作是 2.5D 转台
- 图鉴页纯本地资源，**无 CDN、无外部字体、无网络请求**
- 失败只 `console.warn`，**绝不抛错、绝不阻塞 DSH 启动**

---

## 安装

**前置条件**：已安装并启用 [dsh-pet](https://github.com/PC2005-cloud/dsh-pet)（≥ 0.3.7，用户数据目录 `%USERPROFILE%\.dsh\dsh-pet\` 存在）；Node.js ≥ 20（DSH 自带）。

### 方式 A：插件管理器 / `dsh plugin`（推荐）

1. 把本仓库的 `plugin/` 目录整体作为一个插件包（目录名建议 `dsh-pet-ai-girls`，与 `package.json` 的 `name` 一致）。
2. 在 DSH 的插件管理器里选择「从本地目录安装」，或使用 CLI（子命令以你所用 DSH 版本的 `dsh plugin --help` 为准）：

   ```powershell
   dsh plugin add F:\ceshi\dsh-pet-ai-girls\plugin
   ```

3. 安装器会把包放进 profile 的 `node_modules`，并在 profile 的 `package.json` 里登记依赖与 `dsh.profile.bundles`。
4. **重启 DSH**（宿主代码只在启动时加载）。重启后日志会出现一行：

   ```text
   [dsh-pet-ai-girls] v1.3.0 已部署 8 只 AI 娘桌宠 → C:\Users\<你>\.dsh\dsh-pet\pet（144 个文件） · 当前显示：DeepSeek 娘（/petgirl 切换） · 图鉴：http://127.0.0.1:<端口>/dsh-pet-ai-girls/
   ```

### 方式 B：手工安装（等价于 `install_bundle` 的手工步骤）

1. 复制 `plugin/` 到 profile 的 `node_modules` 下并改名为包名：

   ```text
   %USERPROFILE%\.dsh\profiles\<profile>\node_modules\dsh-pet-ai-girls\
   ```

2. 编辑 profile 的 `package.json`：

   ```json
   {
     "dependencies": {
       "dsh-pet-ai-girls": "file:node_modules/dsh-pet-ai-girls"
     },
     "dsh": {
       "profile": {
         "bundles": [
           "...",
           "dsh-pet",
           "dsh-pet-ai-girls"
         ]
       }
     }
   }
   ```

3. **重启 DSH**。宿主启动时会自动完成 pet pack 部署，无需任何手工复制。

> 本插件没有 `dsh.client` 声明。插件管理器/商城若提示「无客户端半边」，属正常现象。

---

## 只显示一只 + 自由切换

1. 安装插件并重启 DSH 后，宿主已把素材复制进 `pet/`，并**只让 1 只 AI 娘可见**（默认 DeepSeek 娘）。
2. 三种切换方式（任选其一，切换即时生效）：
   - **DSH 斜杠命令**：在对话框输入 `/petgirl`（留空）查看当前桌宠与全部可选角色；输入 `/petgirl qwen` 或 `/petgirl "Qwen 娘"` 切换；
   - **图鉴页按钮**：打开 `http://127.0.0.1:<DSH 端口>/dsh-pet-ai-girls/`，顶部「切换当前桌宠」点选角色（当前角色带「当前」标记）；
   - **HTTP API**：`POST /dsh-pet-ai-girls/api/switch`，body `{"id":"qwen"}`；或 `GET /dsh-pet-ai-girls/api/switch?id=qwen`；当前状态见 `GET /dsh-pet-ai-girls/api/current`。
3. 切换时插件会重写 8 份配置（目标角色 `display=both`，其余 `none`），保存选择，并调用 dsh-pet 的 `POST /dsh-pet-7340/reload` 让**桌面宠物窗口立即重建**；网页里的桌宠刷新页面后同步。
4. 选择会持久化到 `pet/.dsh-pet-ai-girls-active.json`，下次启动仍是上次那只。
5. 交互方式（由 dsh-pet 提供）：
   - **拖拽**：拎起来会播放「被鼠标拖拽悬空反馈」动画，松手后按物理效果落下；
   - **点击**：随机播放 3 个点击回应（开心跃动 / 害羞惊讶 / 元气挥手）；
   - **右键**：打开宠物菜单（碎碎念、对话、回到初始位置、重载配置、动作等）；
   - **工作状态联动**：DSH 思考 / 忙碌 / 完成 / 出错时自动切换对应工作状态动画；
   - **碎碎念 / 对话**：需在对应 config 里开启 `whisperEnabled` 并配置模型（默认关闭，避免额外消耗）。

> 原 dsh-pet 的主宠物（蓝毛小女仆）不受本插件控制，可在 dsh-pet 设置页单独调整或隐藏。

图鉴页：`http://127.0.0.1:<DSH 端口>/dsh-pet-ai-girls/`（默认端口见 DSH 启动日志，例如本机为 `57076`）。

---

## 8 位角色

| # | 角色 | 特征 | pack 前缀 |
| --- | --- | --- | --- |
| 01 | **DeepSeek 娘** | 蓝发鲸鱼娘、黑白女仆裙、爱吃白米饭 | `girl-deepseek` |
| 02 | **GPT 娘** | 白发龙娘、龙角与翅膀、白色礼服、蓝色小团子 | `girl-gpt` |
| 03 | **Claude 娘** | 橙发与花朵发饰、黑橙长裙、手不释卷 | `girl-claude` |
| 04 | **Grok 娘** | 金发与黑色礼裙、大十字戟、傲娇毒舌 | `girl-grok` |
| 05 | **Gemini 娘** | 异色瞳、蓝紫猫耳、星星装饰 | `girl-gemini` |
| 06 | **Kimi 娘** | 银紫长发、非对称女仆装、安静可靠 | `girl-kimi` |
| 07 | **GLM 娘** | 黑发狐耳与女仆装、小恶魔毒舌 | `girl-glm` |
| 08 | **Qwen 娘** | 圆形发饰、团扇、蓝紫衣裙、古风温婉 | `girl-qwen` |

每位角色都带一句独立的 `whisperPrompt` 人设，性格与说话风格各不相同（见各自的 config）。

## 17 个动画

| 分组 | 动画名 | 触发方式 / 说明 |
| --- | --- | --- |
| 待机 | 待机呼吸 / 原地漂浮 / 原地小憩 | 空闲时按权重随机循环，`原地小憩` 头顶冒 Zzz（立绘纸片人渲染） |
| 互动 · 2.5D | 东张西望 | 向左/右转身看两侧（三视图正/侧面），再转回正面 |
| 互动 · 2.5D | 被鼠标拖拽悬空反馈 | 被拎起来时悬空摇摆，朝向在正面~侧面之间摆动 |
| 互动 · 2.5D | 点击回应-开心跃动 | 跳起来开心地转一圈（360°，2.5D 转台） |
| 互动 · 2.5D | 点击回应-害羞惊讶 | 害羞地转身躲开（侧身/背身）再转回来 |
| 互动 | 点击回应-元气挥手 | 元气满满地挥手打招呼 |
| 碎碎念 | 碎碎念-发呆碎碎念 | 开启 whisper 后碎碎念时播放 |
| 工作状态 · 2.5D | 工作状态-雀跃庆祝 | 完成任务时跳跃庆祝并转一圈 |
| 工作状态 | 工作状态-思考冒泡 / 忙碌点按 / 清点归档 / 原地踱步张望 / 垂头叹气冒汗 | 随 DSH 会话状态联动 |
| 小动作 · 2.5D | 转圈展示 | **360° 三视图转台**：正面 → 侧面 → 背面 → 侧面 → 正面 |
| 小动作 | 伸懒腰 | 自定义类别「小动作」，按权重随机插入 |

每只宠物共 **17 个 Q 版动画**（`girl-*-animation/` 下 17 个同名 `.webm`，全部是 v1.3.0 重新 Q 版化渲染的），其中
**6 个是 2.5D 三视图转台**（东张西望 / 拖拽 / 开心跃动 / 害羞惊讶 / 雀跃庆祝 / 转圈展示）。

### 2.5D 转台是怎么做的

1. `tools/threeview.py` 用连通域把 1536×1024 的三视图拆成正面 / 侧面 / 背面三张透明立绘，
   统一角色高度、脚底基线与旋转轴；
2. 渲染时按 yaw 角在四个视角段（正面 / 左侧面 / 背面 / 右侧面）之间切换，段边缘做横向压缩（透视），
   视角交界处做短交叉淡化，高速旋转时对相邻 yaw 采样做**运动模糊**；
3. 地面阴影宽度跟随当前剪影（正面/背面裙摆宽、侧面窄），增强立体感；
4. 点击宠物时约 75% 的回应会出现 2.5D 转身/转圈；空闲时「小动作」类别（24% 权重）也会随机触发转身/360° 转台。

---

## 配置

pet pack 的配置就是 dsh-pet 的额外宠物配置文件：

```text
%USERPROFILE%\.dsh\dsh-pet\pet\
├─ .dsh-pet-ai-girls.json          # 本插件的版本 marker（勿手改）
├─ .dsh-pet-ai-girls-active.json   # 当前显示的角色（切换时自动写）
├─ girl-deepseek-config.json       # 8 个配置文件
├─ girl-deepseek-animation\        # 8 个动画目录（每个 17 个 webm）
│  ├─ 待机呼吸.webm
│  └─ ...
└─ ...
```

> `$DSH_HOME` 非空时优先使用 `$DSH_HOME/dsh-pet/pet/`（与 `@deepseek-ai/dsh-home-paths` 同口径），否则为 `%USERPROFILE%\.dsh\dsh-pet\pet\`。

常用字段（以 `girl-deepseek-config.json` 为例）：

| 字段 | 说明 |
| --- | --- |
| `pets[0].size` | 宠物显示尺寸（像素）；v1.1 起统一切换为 340，切换时插件会把它重置回 340 |
| `pets[0].position.corner` | 初始角落：`bottom-left` / `top-left` / `bottom-right` / `top-right` |
| `pets[0].position.marginX` / `marginY` | 距角落的水平和垂直偏移（px） |
| `pets[0].whisperEnabled` | 是否允许碎碎念。dsh-pet 全局默认 true；本 pack 显式设为 `false`，避免默认产生模型调用（需要时自行改 true 并配好模型） |
| `pets[0].workStatusEnabled` | 是否随 DSH 工作状态切换动画 |
| `pets[0].fixedEnabled` | 是否固定位置（由 dsh-pet 读取的兼容字段；本 pack 设为 true） |
| `pets[0].display` | 显示范围：`web` / `desktop` / `both` / `none`。v1.1 起「当前角色」为 `both`，其余 7 组为 `none`（由 `/petgirl` 或切换 API 自动改写） |
| `whisperPrompt` | 该角色的人设与说话风格（碎碎念/对话用） |
| `workStatusTexts` | 6 组工作状态气泡文案 |

- **改完保存后刷新 DSH 页面即生效**（dsh-pet 每次加载重读配置）。
- 重新部署：删除 `pet/.dsh-pet-ai-girls.json`（或修改 config 后直接删 marker）即可在下次 DSH 启动时重拷贝；也可设环境变量 **`DSH_PET_AI_GIRLS_FORCE=1`** 强制覆盖重部署。
- 想恢复默认：删除对应 `girl-<id>-config.json` / `girl-<id>-animation/` 后重启 DSH（插件会因 marker 校验失败自动重新部署）。

---

## 图鉴与健康检查

| 路由 | 说明 |
| --- | --- |
| `GET /dsh-pet-ai-girls/` | 图鉴首页（`visual/index.html`） |
| `GET /dsh-pet-ai-girls/health` | JSON：`{ ok, name, version, packVersion, deployed, animationCount, characters[] }` |
| `GET /dsh-pet-ai-girls/portraits/<id>.webp` | 角色立绘（约 900×1600） |
| `GET /dsh-pet-ai-girls/turnarounds/<id>.webp` | 三视图（1280×853） |
| `GET /dsh-pet-ai-girls/data.json` | 图鉴数据（角色 / 动画 / 署名） |

- 只允许 `GET` / `HEAD`；扩展名白名单 `html/css/js/png/webp/jpg/svg/json/ico`；路径 `resolve` 后必须仍在 `visual/` 内（防目录穿越）；404 返回纯文本。
- 图鉴页是单文件（内联 CSS/JS + 内联 JSON 数据），图片走相对路径，因此也可直接用浏览器打开 `visual/index.html` 预览（`file://` 下健康检查会降级为「本地静态预览」）。

---

## 文件结构

```text
dsh-pet-ai-girls/                 # = plugin/ 目录（插件包根）
├─ package.json                   # name/version/main/icon/exports/files + dsh.bundle.patch
├─ cordis.patch.yml               # insert 一行：id / name = dsh-pet-ai-girls
├─ index.js                       # 宿主半侧：pet pack 部署 + 图鉴静态路由 + /health
├─ icon.png                       # 256×256 插件图标（8 头像拼贴，≤256 KiB）
├─ README.md
├─ packs/                         # 由 tools/build_packs.py 生成（8 组 config + animation）
│  ├─ girl-deepseek-config.json
│  ├─ girl-deepseek-animation/  （17 个 webm）
│  └─ … × 8
└─ visual/
   ├─ index.html                  # 图鉴页（内联数据）
   ├─ data.json                   # 图鉴元数据
   ├─ portraits/{<id>.webp, thumbs/<id>.webp}
   └─ turnarounds/{<id>.webp, thumbs/<id>.webp}
```

---

## 卸载

1. 从 profile 移除插件：删除 `node_modules/dsh-pet-ai-girls`，并从 profile 的 `package.json` 里去掉 `dsh-pet-ai-girls` 依赖与 `dsh.profile.bundles` 条目（使用插件管理器卸载可自动完成）。
2. 删除已部署的 pet pack（**8 个前缀目录/文件 + marker**）：

   ```powershell
   $pet = Join-Path $env:USERPROFILE '.dsh\dsh-pet\pet'
   $ids = 'deepseek','gpt','claude','grok','gemini','kimi','glm','qwen'
   foreach ($id in $ids) {
     Remove-Item (Join-Path $pet "girl-$id-config.json") -Force -ErrorAction SilentlyContinue
     Remove-Item (Join-Path $pet "girl-$id-animation") -Recurse -Force -ErrorAction SilentlyContinue
   }
   Remove-Item (Join-Path $pet '.dsh-pet-ai-girls.json') -Force -ErrorAction SilentlyContinue
   ```

3. 重启 DSH 并刷新页面。dsh-pet 的 `pet/` 是「扫描目录」式加载，删掉文件后刷新页面就不会再出现这 8 只宠物。

> 只删插件不删 pet 文件的话，宠物仍会留在桌面上（素材已经复制进 dsh-pet 用户数据，不依赖插件在线）。

---

## 开发与自检

```powershell
# 0) 渲染依赖：Pillow + numpy + scipy + imageio-ffmpeg（自带 libvpx-vp9）
pip install -r tools/requirements.txt

# 1) 完整设定图三视图 → 正面/侧面/背面透明视图（build/sheets/）
python tools/sheets.py

# 2) Q 版化：连续大头短身变形 → build/chibi/（含头像与 8 人 lineup）
python tools/chibi.py

# 3) 从 reference/ 重新生成图鉴素材 + Q 版预览 + 图标 + data.json
python tools/gallery_build.py

# 4) 全量渲染 136 个 Q 版透明动画（8 worker，含 2.5D 转台；自动检查/重跑 sheets+chibi）
python tools/build_assets.py

# 5) 宿主半侧冒烟测试：临时 DSH_HOME + fake ctx + 本地 HTTP，
#    覆盖部署、/health、图鉴首页、404、目录穿越，不碰真实用户数据
node tools/test_host.mjs
```

- `tools/sheets.py`：识别 ai-chan-sheets 设定板的三张卡片 → 去掉标题/页脚/边框 → 取正面/侧面/背面并统一高度/基线/转轴（需要 scipy）。
- `tools/chibi.py`：对三视图做连续的「大头短身」变形（头顶 ~1.7 倍 → 脚底 ~0.5 倍）输出 Q 版三视图 + Q 版正面头像。
- `tools/gallery_build.py`：立绘 / 三视图 / Q 版预览 → `visual/`；生成 Q 版大头图标与 `visual/data.json`，并把数据注入 `visual/index.html`。
- `tools/animlib.py`：Q 版纸片人引擎 + `TurnCharacter` 2.5D 转台渲染；`tools/spin_review.py` 可生成转台动画逐帧审核图。
- `tools/build_packs.py`（产线脚本）：把 `build/webm/` 的 8×17 动画组装成 `plugin/packs/`。
- 本插件是纯文件插件，**不需要任何构建步骤**：改完直接复制进 profile 重启即可。

---

## 版权与致谢

- **角色原案 / 立绘 / 三视图**：**ZipZipPipe（上善无形 / DeepSeek）**，来源
  [genderswapai.com · AI 拟人角色图鉴](https://genderswapai.com/zh-TW/ai-gijinka)。
  本插件使用的完整设定图（三视图补全）来自 [**lmy414/ai-chan-sheets**](https://github.com/lmy414/ai-chan-sheets)，
  Q 版形象由本项目脚本对该设定图做程序化 chibi 化生成。
  素材以 [**CC BY-NC-SA 4.0**](https://creativecommons.org/licenses/by-nc-sa/4.0/) 授权：
  需署名原作者、**不得用于商业用途**、修改/再分发需以相同协议共享。
- 本项目为**非官方同人**桌宠素材包，与上述 AI 厂商及原作者无隶属关系；角色原案版权归原作者所有。
- 本插件**代码**（`index.js` / 工具脚本）以 **MIT** 授权。
- 桌宠运行时由 [dsh-pet](https://github.com/PC2005-cloud/dsh-pet)（MIT，PC2005-cloud）提供，本包不包含其代码。

---

## 常见问题

| 现象 | 排查 |
| --- | --- |
| 刷新后没看到 AI 娘 | ① 确认 `%USERPROFILE%\.dsh\dsh-pet\` 存在（dsh-pet 已安装）；② 重启 DSH 看启动日志是否有 `[dsh-pet-ai-girls]` 行；③ 检查 `pet/` 下是否有 8 组 config + animation；④ 当前只显示 1 只（默认 DeepSeek 娘），用 `/petgirl` 或图鉴页切换到别的角色；⑤ 在 dsh-pet 设置里确认额外宠物未被禁用（`fixedEnabled` / 数量限制）。 |
| 日志显示「跳过 pet pack 部署」 | 常见原因：`dsh-pet` 用户目录不存在；或包内 `packs/` 未构建（需先跑 `tools/build_packs.py`）。以日志括号内原因为准。 |
| 图鉴 404 / 打不开 | 确认 DSH 端口与 URL；图鉴路由只在 `webServer` 服务可用时注册，host 侧注册失败会在日志里 warn。 |
| 想重新覆盖已部署素材 | 删除 `pet/.dsh-pet-ai-girls.json` 后重启 DSH，或设 `DSH_PET_AI_GIRLS_FORCE=1` 再重启。 |
| 中文乱码 | 本包所有文本文件均为 **UTF-8（无 BOM）**；Windows 记事本另存时注意编码。 |
