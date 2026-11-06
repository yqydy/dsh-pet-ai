/**
 * dsh-pet-ai-girls —— 宿主半侧（host-only，纯 ESM，只用 Node 内置模块）
 *
 * 职责：
 *
 *  1) 自动部署 pet pack：把包内 `packs/` 里的 8 组
 *     `girl-<id>-config.json` + `girl-<id>-animation/` **幂等**复制进
 *     dsh-pet 的用户数据目录（`$DSH_HOME/dsh-pet/pet/`，DSH_HOME 缺省为 `~/.dsh`），
 *     并写版本 marker `.dsh-pet-ai-girls.json`。
 *
 *  2) **同一时间只显示一只 AI 娘**：8 组 pack 全部装好，但只有「当前角色」的
 *     `pets[0].display = both`，其余为 `none`。启动时按持久化 marker
 *     `.dsh-pet-ai-girls-active.json` 还原上次选择（默认 DeepSeek 娘）。
 *     切换时重写 8 份 config 并调用 dsh-pet 的 `POST /dsh-pet-7340/reload`
 *     让桌面宠物窗口立即重建（网页 overlay 刷新页面后同步）。
 *
 *  3) 切换入口：
 *     - DSH 斜杠命令 `/petgirl [id|名字]`（留空查看当前与可选角色）
 *     - HTTP API：`GET /dsh-pet-ai-girls/api/current`、
 *       `POST /dsh-pet-ai-girls/api/switch`（body `{"id":"qwen"}`）或
 *       `GET /dsh-pet-ai-girls/api/switch?id=qwen`（图鉴页按钮用）
 *     - 图鉴页 `/dsh-pet-ai-girls/` 顶部「切换当前桌宠」按钮组
 *
 *  4) 图鉴静态路由：`/dsh-pet-ai-girls/*` → 包内 `visual/` 静态文件
 *     （图鉴页 index.html、立绘 / 三视图 webp、data.json），外加 `/health` JSON。
 *     防目录穿越、扩展名白名单、正确 MIME。
 *
 * 任何异常都只 console.warn，绝不抛错、绝不阻塞 DSH 启动。
 */

import {
  cpSync,
  createReadStream,
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  statSync,
  writeFileSync,
} from 'node:fs';
import { extname, dirname, join, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { homedir } from 'node:os';

/** 插件名（= package.json name = cordis.patch.yml 的行 id / 行名） */
export const name = 'dsh-pet-ai-girls';

/** webServer：图鉴/切换路由；commands：/petgirl 斜杠命令 */
export const inject = ['webServer', 'commands'];

const PACKAGE_ROOT = dirname(fileURLToPath(import.meta.url));
const PACKS_ROOT = join(PACKAGE_ROOT, 'packs');
const VISUAL_ROOT = resolve(PACKAGE_ROOT, 'visual');
const VISUAL_ROOT_PREFIX = VISUAL_ROOT.endsWith(sep) ? VISUAL_ROOT : VISUAL_ROOT + sep;
const ROUTE_PREFIX = '/dsh-pet-ai-girls';
const MARKER_NAME = '.dsh-pet-ai-girls.json';
const ACTIVE_MARKER_NAME = '.dsh-pet-ai-girls-active.json';
const DEFAULT_ACTIVE_ID = 'deepseek';
const LOG_PREFIX = '[dsh-pet-ai-girls]';

/** 8 位角色（与 tools/spec.py 的 CHARACTERS 一一对应） */
const CHARACTERS = [
  { id: 'deepseek', prefix: 'girl-deepseek', name: 'DeepSeek 娘' },
  { id: 'gpt', prefix: 'girl-gpt', name: 'GPT 娘' },
  { id: 'claude', prefix: 'girl-claude', name: 'Claude 娘' },
  { id: 'grok', prefix: 'girl-grok', name: 'Grok 娘' },
  { id: 'gemini', prefix: 'girl-gemini', name: 'Gemini 娘' },
  { id: 'kimi', prefix: 'girl-kimi', name: 'Kimi 娘' },
  { id: 'glm', prefix: 'girl-glm', name: 'GLM 娘' },
  { id: 'qwen', prefix: 'girl-qwen', name: 'Qwen 娘' },
];

const ANIMATION_COUNT = 17;
/** 切换时统一大小与位置（原地换人，不跳角落） */
const SWITCH_SIZE = 340;
const SWITCH_POSITION = { corner: 'bottom-right', marginX: 40, marginY: 40 };

/** 静态文件扩展名白名单 → Content-Type */
const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.png': 'image/png',
  '.webp': 'image/webp',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.json': 'application/json; charset=utf-8',
  '.ico': 'image/x-icon',
};

// ---------------------------------------------------------------------------
// 小工具
// ---------------------------------------------------------------------------
function readPluginVersion() {
  try {
    const raw = readFileSync(join(PACKAGE_ROOT, 'package.json'), 'utf8');
    const pkg = JSON.parse(raw);
    if (typeof pkg.version === 'string' && pkg.version.length > 0) return pkg.version;
  } catch {
    /* ignore：版本只用于 marker 与日志，读不到就退回 0.0.0 */
  }
  return '0.0.0';
}

const PLUGIN_VERSION = readPluginVersion();

/** 与 @deepseek-ai/dsh-home-paths 同口径：优先 $DSH_HOME，其次 ~/.dsh */
function resolveDshHome() {
  const fromEnv = typeof process.env.DSH_HOME === 'string' ? process.env.DSH_HOME.trim() : '';
  if (fromEnv.length > 0) return fromEnv;
  return join(homedir(), '.dsh');
}

function petRootDir() {
  return join(resolveDshHome(), 'dsh-pet', 'pet');
}

function readMarker(markerPath) {
  try {
    const raw = readFileSync(markerPath, 'utf8');
    const obj = JSON.parse(raw);
    return obj && typeof obj === 'object' ? obj : null;
  } catch {
    return null;
  }
}

/** marker 是否可信：版本一致、8 个角色齐全、每个 config 与 animation 目录都在 */
function markerCoversEverything(marker, petRoot) {
  if (!marker || marker.version !== PLUGIN_VERSION) return false;
  if (!Array.isArray(marker.chars) || marker.chars.length !== CHARACTERS.length) return false;
  const declared = new Set(marker.chars);
  for (const c of CHARACTERS) {
    if (!declared.has(c.prefix)) return false;
    if (!existsSync(join(petRoot, c.prefix + '-config.json'))) return false;
    if (!existsSync(join(petRoot, c.prefix + '-animation'))) return false;
  }
  return true;
}

function countFiles(dir, depth = 0) {
  if (depth > 8) return 0;
  let n = 0;
  let entries;
  try {
    entries = readdirSync(dir, { withFileTypes: true });
  } catch {
    return 0;
  }
  for (const entry of entries) {
    if (entry.isDirectory()) n += countFiles(join(dir, entry.name), depth + 1);
    else if (entry.isFile()) n += 1;
  }
  return n;
}

// ---------------------------------------------------------------------------
// 角色查询 / 当前显示角色
// ---------------------------------------------------------------------------
function characterById(id) {
  return CHARACTERS.find((c) => c.id === id) || null;
}

/** 接受 id / 前缀 / 显示名（大小写不敏感，名字可部分匹配） */
function resolveCharacter(input) {
  const value = String(input || '').trim().toLowerCase();
  if (!value) return null;
  for (const c of CHARACTERS) {
    const names = [c.id, c.prefix, c.prefix.replace(/^girl-/, ''), c.name.toLowerCase()];
    if (names.includes(value)) return c;
  }
  for (const c of CHARACTERS) {
    if (c.name.toLowerCase().includes(value)) return c;
  }
  return null;
}

function activeMarkerPath() {
  return join(petRootDir(), ACTIVE_MARKER_NAME);
}

/** 上次选中的角色 id（marker 缺失/非法 → 默认 DeepSeek 娘） */
function readActiveId() {
  const marker = readMarker(activeMarkerPath());
  if (marker && typeof marker.active === 'string' && characterById(marker.active)) {
    return marker.active;
  }
  return DEFAULT_ACTIVE_ID;
}

/**
 * 把「当前角色」写进 8 份 pet pack 配置：
 * 只有目标角色 `display = both`，其余 `display = none`；同时统一 size/position，
 * 这样切换时是原地换人而不是跳到别的角落。返回部署后的当前角色信息。
 */
function applyActiveSelection(id) {
  const root = petRootDir();
  if (!existsSync(root)) return { ok: false, reason: 'pet-dir-missing' };
  const target = characterById(id) || characterById(DEFAULT_ACTIVE_ID);
  let changed = 0;
  for (const c of CHARACTERS) {
    const file = join(root, c.prefix + '-config.json');
    if (!existsSync(file)) continue;
    let cfg;
    try {
      cfg = JSON.parse(readFileSync(file, 'utf8'));
    } catch (err) {
      console.warn(LOG_PREFIX + ' 读取配置失败（跳过 ' + c.prefix + '）：' + (err instanceof Error ? err.message : String(err)));
      continue;
    }
    const pets = Array.isArray(cfg.pets) ? cfg.pets : [];
    if (!pets.length) continue;
    pets[0].display = c.id === target.id ? 'both' : 'none';
    pets[0].size = SWITCH_SIZE;
    pets[0].position = { ...SWITCH_POSITION };
    try {
      writeFileSync(file, JSON.stringify(cfg, null, 2) + '\n', 'utf8');
      changed += 1;
    } catch (err) {
      console.warn(LOG_PREFIX + ' 写入配置失败（' + c.prefix + '）：' + (err instanceof Error ? err.message : String(err)));
    }
  }
  if (!changed) return { ok: false, reason: 'no-config-written' };
  try {
    writeFileSync(
      activeMarkerPath(),
      JSON.stringify(
        { active: target.id, prefix: target.prefix, name: target.name, updatedAt: new Date().toISOString() },
        null,
        2,
      ) + '\n',
      'utf8',
    );
  } catch (err) {
    console.warn(LOG_PREFIX + ' 写入 active marker 失败：' + (err instanceof Error ? err.message : String(err)));
  }
  return { ok: true, active: target, changed };
}

function listCharacters() {
  return CHARACTERS.map((c) => ({ id: c.id, prefix: c.prefix, name: c.name }));
}

/** 让 dsh-pet 的桌面 Helper 按最新配置重建所有宠物窗口（每只一个透明小窗） */
async function reloadDshPetDesktop(port) {
  if (!port) return false;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10000);
  try {
    const res = await fetch('http://127.0.0.1:' + port + '/dsh-pet-7340/reload', {
      method: 'POST',
      signal: controller.signal,
    });
    return res.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

// ---------------------------------------------------------------------------
// 1) 自动部署 pet pack
// ---------------------------------------------------------------------------
/**
 * 把 packs/ 幂等部署到 dsh-pet 用户数据目录。
 * @returns {{ status: 'deployed'|'up-to-date'|'skipped', reason?: string, target: string, files: number }}
 */
function deployPetPack() {
  const dshHome = resolveDshHome();
  const dshPetRoot = join(dshHome, 'dsh-pet');
  const petRoot = join(dshPetRoot, 'pet');

  // dsh-pet 没装（没有用户数据目录）：静默跳过，不当成错误
  if (!existsSync(dshPetRoot)) {
    return {
      status: 'skipped',
      reason: '未发现 dsh-pet 用户数据目录（' + dshPetRoot + '），跳过 pet pack 部署',
      target: petRoot,
      files: 0,
    };
  }
  if (!existsSync(PACKS_ROOT)) {
    return {
      status: 'skipped',
      reason: '包内 packs/ 目录不存在（' + PACKS_ROOT + '），跳过 pet pack 部署',
      target: petRoot,
      files: 0,
    };
  }

  const markerPath = join(petRoot, MARKER_NAME);
  const force = process.env.DSH_PET_AI_GIRLS_FORCE === '1';
  if (!force) {
    const marker = readMarker(markerPath);
    if (markerCoversEverything(marker, petRoot)) {
      return { status: 'up-to-date', target: petRoot, files: 0 };
    }
  }

  mkdirSync(petRoot, { recursive: true });

  let files = 0;
  let deployedChars = 0;
  for (const c of CHARACTERS) {
    const srcConfig = join(PACKS_ROOT, c.prefix + '-config.json');
    const srcAnimDir = join(PACKS_ROOT, c.prefix + '-animation');
    const dstConfig = join(petRoot, c.prefix + '-config.json');
    const dstAnimDir = join(petRoot, c.prefix + '-animation');
    if (!existsSync(srcConfig) || !existsSync(srcAnimDir)) {
      // packs 不完整（例如还没构建完）：跳过这个角色，不写半套素材
      console.warn(
        LOG_PREFIX + ' packs 缺少 ' + c.prefix + ' 的素材，跳过该角色（等 packs 完整后重启 DSH 或设 DSH_PET_AI_GIRLS_FORCE=1 重试）',
      );
      continue;
    }
    cpSync(srcConfig, dstConfig, { force: true });
    files += 1;
    // 递归覆盖：目标已存在时合并（幂等），旧版多余文件也不会被误删
    cpSync(srcAnimDir, dstAnimDir, { recursive: true, force: true });
    try {
      if (statSync(dstAnimDir).isDirectory()) files += countFiles(dstAnimDir);
    } catch {
      /* 统计失败不影响部署 */
    }
    deployedChars += 1;
  }

  if (deployedChars === 0) {
    return {
      status: 'skipped',
      reason: 'packs/ 中没有可用的角色素材（' + PACKS_ROOT + '）',
      target: petRoot,
      files: 0,
    };
  }

  writeFileSync(
    markerPath,
    JSON.stringify(
      {
        version: PLUGIN_VERSION,
        installedAt: new Date().toISOString(),
        chars: CHARACTERS.map((c) => c.prefix),
        files,
      },
      null,
      2,
    ) + '\n',
    'utf8',
  );
  return { status: 'deployed', target: petRoot, files, chars: deployedChars };
}

// ---------------------------------------------------------------------------
// 2) 图鉴 / 切换 API 路由
// ---------------------------------------------------------------------------
function sendText(res, status, body, headers = {}) {
  const buf = Buffer.from(body, 'utf8');
  res.writeHead(status, {
    'content-type': 'text/plain; charset=utf-8',
    'content-length': buf.length,
    ...headers,
  });
  res.end(buf);
}

function sendJson(res, status, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'content-length': Buffer.byteLength(body),
    'cache-control': 'no-store',
  });
  res.end(body);
}

/** 读取请求体（限 64KB，仅供 /api/switch 用） */
function readBody(req) {
  return new Promise((resolveBody, rejectBody) => {
    let size = 0;
    const chunks = [];
    req.on('data', (chunk) => {
      size += chunk.length;
      if (size > 64 * 1024) {
        rejectBody(new Error('body too large'));
        try {
          req.destroy();
        } catch {
          /* ignore */
        }
        return;
      }
      chunks.push(chunk);
    });
    req.on('end', () => resolveBody(Buffer.concat(chunks).toString('utf8')));
    req.on('error', rejectBody);
  });
}

/**
 * 流式发送文件（HEAD 只发头）。
 * 用 open 事件后再写头，避免文件在 stat 与 open 之间被删导致写头后立刻报错。
 */
function sendFile(req, res, file, contentType) {
  let size;
  try {
    size = statSync(file).size;
  } catch {
    sendText(res, 404, 'dsh-pet-ai-girls: not found');
    return;
  }
  const headers = {
    'content-type': contentType,
    'content-length': size,
    'cache-control': /index\.html$/.test(file) ? 'no-cache' : 'public, max-age=3600',
  };
  if ((req.method || 'GET') === 'HEAD') {
    res.writeHead(200, headers);
    res.end();
    return;
  }
  const stream = createReadStream(file);
  stream.once('open', () => {
    if (res.destroyed || res.writableEnded) {
      stream.destroy();
      return;
    }
    res.writeHead(200, headers);
    stream.pipe(res);
  });
  stream.once('error', () => {
    if (!res.headersSent) {
      sendText(res, 500, 'dsh-pet-ai-girls: read error');
    } else {
      res.destroy();
    }
  });
}

/** 把 `/dsh-pet-ai-girls/...` 的剩余路径映射到 visual/ 内的安全路径 */
function resolveVisualPath(rest) {
  let decoded;
  try {
    decoded = decodeURIComponent(rest);
  } catch {
    return { error: 400 };
  }
  // Windows 上 %5C 解出的反斜杠也是分隔符，resolve 后统一做前缀校验
  const target = resolve(VISUAL_ROOT, decoded);
  if (target !== VISUAL_ROOT && !target.startsWith(VISUAL_ROOT_PREFIX)) {
    return { error: 404 };
  }
  const ext = extname(target).toLowerCase();
  if (!Object.prototype.hasOwnProperty.call(MIME, ext)) return { error: 404 };
  return { target, contentType: MIME[ext] };
}

/** 构造图鉴 / 切换路由的请求处理器（挂到 ctx.webServer.register 上） */
function createGalleryHandler(getPort) {
  return async function galleryHandler(req, res) {
    try {
      const method = (req.method || 'GET').toUpperCase();
      let pathname = '/';
      let search = null;
      try {
        const parsed = new URL(req.url || '/', 'http://127.0.0.1');
        pathname = parsed.pathname;
        search = parsed.searchParams;
      } catch {
        sendText(res, 400, 'dsh-pet-ai-girls: bad request');
        return;
      }

      // ---- 切换 API：当前角色 ----
      if (pathname === ROUTE_PREFIX + '/api/current') {
        if (method !== 'GET' && method !== 'HEAD') {
          sendText(res, 405, 'dsh-pet-ai-girls: method not allowed', { allow: 'GET, HEAD' });
          return;
        }
        const activeId = readActiveId();
        const active = characterById(activeId);
        sendJson(res, 200, {
          ok: true,
          active: { id: active.id, prefix: active.prefix, name: active.name },
          characters: listCharacters(),
        });
        return;
      }

      // ---- 切换 API：POST {"id":"qwen"} 或 GET ?id=qwen ----
      if (pathname === ROUTE_PREFIX + '/api/switch') {
        if (method !== 'GET' && method !== 'POST') {
          sendText(res, 405, 'dsh-pet-ai-girls: method not allowed', { allow: 'GET, POST' });
          return;
        }
        let id = search ? String(search.get('id') || '') : '';
        if (!id && method === 'POST') {
          try {
            const body = await readBody(req);
            const obj = body ? JSON.parse(body) : {};
            id = String((obj && (obj.id || obj.prefix)) || '');
          } catch {
            sendJson(res, 400, { ok: false, error: 'invalid JSON body' });
            return;
          }
        }
        const target = resolveCharacter(id);
        if (!target) {
          sendJson(res, 400, { ok: false, error: '未知角色：' + id, characters: listCharacters() });
          return;
        }
        const result = applyActiveSelection(target.id);
        if (!result.ok) {
          sendJson(res, 409, { ok: false, error: 'pet pack 目录不存在，无法切换（dsh-pet 未安装？）' });
          return;
        }
        const reloading = await reloadDshPetDesktop(getPort());
        sendJson(res, 200, {
          ok: true,
          active: { id: target.id, prefix: target.prefix, name: target.name },
          reloading,
          characters: listCharacters(),
        });
        return;
      }

      // ---- 静态文件只允许 GET / HEAD ----
      if (method !== 'GET' && method !== 'HEAD') {
        sendText(res, 405, 'dsh-pet-ai-girls: method not allowed', { allow: 'GET, HEAD' });
        return;
      }

      if (pathname === ROUTE_PREFIX) {
        sendFile(req, res, join(VISUAL_ROOT, 'index.html'), MIME['.html']);
        return;
      }
      if (!pathname.startsWith(ROUTE_PREFIX + '/')) {
        sendText(res, 404, 'dsh-pet-ai-girls: not found');
        return;
      }
      const rest = pathname.slice(ROUTE_PREFIX.length + 1);

      // 健康检查：给图鉴页与外部探针用
      if (rest === 'health') {
        const markerPath = join(petRootDir(), MARKER_NAME);
        const marker = readMarker(markerPath);
        const activeId = readActiveId();
        const active = characterById(activeId);
        sendJson(res, 200, {
          ok: true,
          name,
          version: PLUGIN_VERSION,
          packVersion: marker && typeof marker.version === 'string' ? marker.version : null,
          deployed: Boolean(marker),
          animationCount: ANIMATION_COUNT,
          active: { id: active.id, prefix: active.prefix, name: active.name },
          characters: CHARACTERS.map((c) => ({
            id: c.id,
            prefix: c.prefix,
            name: c.name,
            config: c.prefix + '-config.json',
            animationDir: c.prefix + '-animation',
            animations: ANIMATION_COUNT,
            active: c.id === active.id,
          })),
        });
        return;
      }

      if (rest === '' || rest === 'index.html') {
        sendFile(req, res, join(VISUAL_ROOT, 'index.html'), MIME['.html']);
        return;
      }

      const mapped = resolveVisualPath(rest);
      if (mapped.error !== undefined) {
        sendText(res, mapped.error, mapped.error === 400 ? 'dsh-pet-ai-girls: bad path' : 'dsh-pet-ai-girls: not found');
        return;
      }
      sendFile(req, res, mapped.target, mapped.contentType);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      try {
        if (!res.headersSent) sendJson(res, 500, { ok: false, error: message });
        else res.destroy();
      } catch {
        /* 响应已断开：忽略 */
      }
    }
  };
}

// ---------------------------------------------------------------------------
// 插件入口
// ---------------------------------------------------------------------------
/**
 * Cordis 插件入口。
 * @param {any} ctx DSH 注入的上下文（webServer / commands / effect 等，无静态类型）
 */
export function apply(ctx) {
  const getPort = () =>
    ctx && ctx.webServer && typeof ctx.webServer.port === 'number' ? ctx.webServer.port : 0;

  // ---- a) 自动部署 pet pack（失败只 warn，绝不影响 DSH 启动）----
  let deploy;
  try {
    deploy = deployPetPack();
    if (deploy.status === 'skipped' && deploy.reason) {
      console.warn(LOG_PREFIX + ' ' + deploy.reason);
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.warn(LOG_PREFIX + ' pet pack 部署失败（不影响 DSH 启动）：' + message);
    deploy = { status: 'skipped', reason: 'deploy-failed', target: '', files: 0 };
  }

  // ---- b) 恢复「当前显示角色」：只留一只有 display=both ----
  let active = characterById(DEFAULT_ACTIVE_ID);
  try {
    const applied = applyActiveSelection(readActiveId());
    if (applied.ok) active = applied.active;
  } catch (err) {
    console.warn(LOG_PREFIX + ' 恢复当前显示角色失败（不影响 DSH 启动）：' + (err instanceof Error ? err.message : String(err)));
  }

  // ---- c) 图鉴 / 切换 API 静态路由 ----
  let routeNote = '未注册（webServer 不可用）';
  try {
    if (ctx && ctx.webServer && typeof ctx.webServer.register === 'function') {
      const handler = createGalleryHandler(getPort);
      ctx.effect(
        () => ctx.webServer.register({ kind: 'prefix', path: ROUTE_PREFIX, handler }),
        'dsh-pet-ai-girls: gallery route',
      );
      routeNote = '图鉴：http://127.0.0.1:' + (getPort() || '?') + ROUTE_PREFIX + '/';
    } else {
      console.warn(LOG_PREFIX + ' ctx.webServer 不可用，跳过图鉴路由注册');
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.warn(LOG_PREFIX + ' 图鉴路由注册失败（不影响 DSH 启动）：' + message);
  }

  // ---- d) /petgirl 斜杠命令：切换当前显示的 AI 娘 ----
  try {
    if (ctx && ctx.commands && typeof ctx.commands.register === 'function') {
      ctx.effect(
        () =>
          ctx.commands.register({
            name: 'petgirl',
            description: '切换当前显示的 AI 娘桌宠（留空查看当前与可选角色）',
            input: { hint: '[id 或名字]（留空=查看）' },
            handler: ({ rawInput }) => {
              const arg = String(rawInput || '').trim();
              const currentId = readActiveId();
              const current = characterById(currentId);
              if (!arg) {
                return {
                  kind: 'success',
                  text:
                    '当前桌宠：' + current.name + '（' + current.prefix + '）；可选：' +
                    CHARACTERS.map((c) => c.id + '=' + c.name).join('；') +
                    '。切换示例：/petgirl qwen',
                };
              }
              if (arg === 'list' || arg === '列表') {
                return {
                  kind: 'success',
                  text: '可选：' + CHARACTERS.map((c) => c.id + '=' + c.name).join('；'),
                };
              }
              const target = resolveCharacter(arg);
              if (!target) {
                return {
                  kind: 'error',
                  text: '找不到角色「' + arg + '」。可选：' + CHARACTERS.map((c) => c.id).join('、'),
                };
              }
              const result = applyActiveSelection(target.id);
              if (!result.ok) {
                return { kind: 'error', text: 'pet pack 目录不存在，无法切换（dsh-pet 未安装？）' };
              }
              void reloadDshPetDesktop(getPort()).then((reloading) => {
                if (!reloading) {
                  console.warn(LOG_PREFIX + ' 桌面宠物重建请求失败（网页端刷新后仍会同步）');
                }
              });
              return {
                kind: 'success',
                text: '已切换为「' + target.name + '」，桌面桌宠正在重建…（网页里的桌宠刷新页面后同步）',
              };
            },
          }),
        'dsh-pet-ai-girls: /petgirl command',
      );
    } else {
      console.warn(LOG_PREFIX + ' ctx.commands 不可用，跳过 /petgirl 命令注册');
    }
  } catch (err) {
    console.warn(LOG_PREFIX + ' /petgirl 命令注册失败（不影响 DSH 启动）：' + (err instanceof Error ? err.message : String(err)));
  }

  // ---- e) 启动日志（一行：部署结果 + 当前角色 + 图鉴地址）----
  let deployNote;
  if (deploy.status === 'deployed') {
    deployNote =
      '已部署 ' + (deploy.chars ?? CHARACTERS.length) + ' 只 AI 娘桌宠 → ' + deploy.target + '（' + deploy.files + ' 个文件）';
  } else if (deploy.status === 'up-to-date') {
    deployNote = 'pet pack 已是最新 v' + PLUGIN_VERSION + '，跳过部署 → ' + deploy.target;
  } else {
    deployNote = '跳过 pet pack 部署（' + (deploy.reason || '未知原因') + '）';
  }
  console.log(
    LOG_PREFIX + ' v' + PLUGIN_VERSION + ' ' + deployNote +
    ' · 当前显示：' + active.name + '（/petgirl 切换） · ' + routeNote,
  );
}

export default { name, inject, apply };
