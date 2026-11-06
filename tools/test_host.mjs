#!/usr/bin/env node
/**
 * dsh-pet-ai-girls 宿主半侧冒烟测试（不碰真实用户数据）
 *
 * 覆盖：
 *   1. 模块导出契约：name / inject=['webServer'] / apply
 *   2. 自动部署：用临时目录当 DSH_HOME（内含空 dsh-pet/），跑 apply 后检查
 *      8 组 girl-<id>-config.json + girl-<id>-animation/ 与版本 marker
 *      —— 若 plugin/packs/ 尚未生成（Lead 产线还没跑完），这部分打印 SKIP 并继续
 *   3. 容错：DSH_HOME 下没有 dsh-pet/ 时 apply 不抛错、不创建目录
 *   4. 图鉴静态路由：把 captured.handler 挂到 node:http server 上，验证
 *      /health、/、data.json、图片 200，404、目录穿越 404/400、HEAD、405
 *
 * 运行：node tools/test_host.mjs
 * 退出码：全部通过 0；有失败 1。临时目录在结束时清理。
 */

import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, statSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import http from 'node:http';

const TOOLS_DIR = dirname(fileURLToPath(import.meta.url));
const ROOT = dirname(TOOLS_DIR);
const PLUGIN_DIR = join(ROOT, 'plugin');
const PACKS_DIR = join(PLUGIN_DIR, 'packs');
const VISUAL_DIR = join(PLUGIN_DIR, 'visual');

const CHAR_IDS = ['deepseek', 'gpt', 'claude', 'grok', 'gemini', 'kimi', 'glm', 'qwen'];
const PREFIXES = CHAR_IDS.map((id) => 'girl-' + id);
const EXPECTED_ANIMS = 17;
// 期望版本从 plugin/package.json 读取（避免升级后测试文件忘记同步）
const PLUGIN_VERSION = JSON.parse(readFileSync(join(PLUGIN_DIR, 'package.json'), 'utf8')).version;

let failures = 0;
let passes = 0;
const skipped = [];

function pass(name, detail) {
  passes += 1;
  console.log('PASS  ' + name + (detail ? ' · ' + detail : ''));
}
function fail(name, detail) {
  failures += 1;
  console.log('FAIL  ' + name + (detail ? ' · ' + detail : ''));
}
function skip(name, detail) {
  skipped.push(name + (detail ? ' · ' + detail : ''));
  console.log('SKIP  ' + name + (detail ? ' · ' + detail : ''));
}
function check(name, cond, detail) {
  if (cond) pass(name, detail);
  else fail(name, detail);
  return Boolean(cond);
}

function countEntries(dir) {
  try {
    return readdirSync(dir);
  } catch {
    return [];
  }
}

const packReady =
  existsSync(PACKS_DIR) &&
  PREFIXES.every(
    (p) => existsSync(join(PACKS_DIR, p + '-config.json')) && existsSync(join(PACKS_DIR, p + '-animation')),
  );

const tempHome = mkdtempSync(join(tmpdir(), 'dsh-pet-ai-girls-test-'));
const tempHomeNoPet = mkdtempSync(join(tmpdir(), 'dsh-pet-ai-girls-nopet-'));
const savedDshHome = process.env.DSH_HOME;
const savedForce = process.env.DSH_PET_AI_GIRLS_FORCE;

let server = null;
async function httpReq(url, method = 'GET') {
  const res = await fetch(url, { method, cache: 'no-store', redirect: 'manual' });
  const text = await res.text();
  return { status: res.status, headers: res.headers, text };
}

async function main() {
  console.log('== dsh-pet-ai-girls host smoke test ==');
  console.log('项目根: ' + ROOT);
  console.log('packs 就绪: ' + (packReady ? '是' : '否（部署检查将 SKIP）'));
  console.log('临时 DSH_HOME: ' + tempHome);

  // 1) 模块导出契约 ---------------------------------------------------------
  const entryUrl = pathToFileURL(join(PLUGIN_DIR, 'index.js')).href;
  const mod = await import(entryUrl);
  check('导出 name === "dsh-pet-ai-girls"', mod.name === 'dsh-pet-ai-girls', String(mod.name));
  check(
    '导出 inject 含 "webServer"',
    Array.isArray(mod.inject) && mod.inject.includes('webServer'),
    JSON.stringify(mod.inject),
  );
  check('具名导出 apply 是函数', typeof mod.apply === 'function');
  check('default 导出含 name/inject/apply', Boolean(mod.default) && typeof mod.default.apply === 'function' && mod.default.name === 'dsh-pet-ai-girls');
  check('index.js 不引用非内置依赖', !/from\s+['"](?!node:)[^'"]+['"]/.test(readFileSync(join(PLUGIN_DIR, 'index.js'), 'utf8')));

  // 2) 自动部署（临时 DSH_HOME 内放一个空的 dsh-pet 目录）------------------
  mkdirSync(join(tempHome, 'dsh-pet'), { recursive: true });
  process.env.DSH_HOME = tempHome;
  delete process.env.DSH_PET_AI_GIRLS_FORCE;

  let captured = null;
  const makeCtx = () => ({
    webServer: {
      port: 0,
      register(def) {
        captured = def;
        return () => {};
      },
    },
    effect(fn) {
      const d = fn();
      return () => {};
    },
  });

  let applyError = null;
  try {
    await mod.apply(makeCtx());
  } catch (e) {
    applyError = e;
  }
  check('apply 在正常环境下不抛错', applyError === null, applyError ? String(applyError) : '');
  check('apply 注册了图鉴路由（captured 有 handler）', Boolean(captured && typeof captured.handler === 'function'));
  check('路由声明为 prefix + /dsh-pet-ai-girls', Boolean(captured) && captured.kind === 'prefix' && captured.path === '/dsh-pet-ai-girls');

  const petRoot = join(tempHome, 'dsh-pet', 'pet');
  if (packReady) {
    const configs = PREFIXES.filter((p) => existsSync(join(petRoot, p + '-config.json')));
    const animDirs = PREFIXES.filter((p) => existsSync(join(petRoot, p + '-animation')));
    check('部署：8 个 <前缀>-config.json', configs.length === 8, configs.length + '/8');
    check('部署：8 个 <前缀>-animation 目录', animDirs.length === 8, animDirs.length + '/8');
    let animFileTotal = 0;
    for (const p of PREFIXES) {
      const dir = join(petRoot, p + '-animation');
      if (existsSync(dir)) animFileTotal += countEntries(dir).filter((f) => f.endsWith('.webm')).length;
    }
    check(
      '部署：动画 webm 共 8×17=136 个',
      animFileTotal === 8 * EXPECTED_ANIMS,
      String(animFileTotal) + '/' + 8 * EXPECTED_ANIMS,
    );
    const markerPath = join(petRoot, '.dsh-pet-ai-girls.json');
    let marker = null;
    try {
      marker = JSON.parse(readFileSync(markerPath, 'utf8'));
    } catch {
      /* 下面断言会失败 */
    }
    check('部署：版本 marker 存在且 version=' + PLUGIN_VERSION, Boolean(marker) && marker.version === PLUGIN_VERSION, marker ? String(marker.version) : '缺失');
    check(
      '部署：marker.chars 覆盖 8 个前缀',
      Boolean(marker) && Array.isArray(marker.chars) && PREFIXES.every((p) => marker.chars.includes(p)),
      marker && Array.isArray(marker.chars) ? marker.chars.length + ' 个' : '缺失',
    );
    // 再跑一次 apply 应命中「已是最新」且不改 marker 的 installedAt
    const firstInstalledAt = marker ? marker.installedAt : null;
    await mod.apply(makeCtx());
    let marker2 = null;
    try {
      marker2 = JSON.parse(readFileSync(markerPath, 'utf8'));
    } catch {
      /* ignore */
    }
    check(
      '幂等：重复 apply 不重复部署（marker.installedAt 不变）',
      Boolean(marker2) && marker2.installedAt === firstInstalledAt,
      marker2 ? String(marker2.installedAt) : '缺失',
    );
  } else {
    skip('部署：8 组 pet pack 写入临时 DSH_HOME', 'plugin/packs/ 尚未生成，等产线生成后重跑本测试');
  }

  // 3) 容错：DSH_HOME 下没有 dsh-pet/ 时只 warn、不抛错、不建目录 -----------
  process.env.DSH_HOME = tempHomeNoPet;
  let applyErrorNoPet = null;
  try {
    await mod.apply(makeCtx());
  } catch (e) {
    applyErrorNoPet = e;
  }
  check('dsh-pet 不存在时 apply 不抛错', applyErrorNoPet === null, applyErrorNoPet ? String(applyErrorNoPet) : '');
  check('dsh-pet 不存在时不创建 dsh-pet/ 目录', !existsSync(join(tempHomeNoPet, 'dsh-pet')));

  // 4) 图鉴静态路由 ----------------------------------------------------------
  process.env.DSH_HOME = tempHome;
  captured = null;
  await mod.apply(makeCtx()); // health 从 tempHome 的 marker 读 packVersion
  if (!captured || typeof captured.handler !== 'function') {
    fail('无法挂载图鉴路由（captured.handler 缺失）');
    return;
  }

  server = http.createServer((req, res) => {
    Promise.resolve(captured.handler(req, res)).catch((e) => {
      try {
        res.writeHead(500);
        res.end(String(e));
      } catch {
        /* ignore */
      }
    });
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  const base = 'http://127.0.0.1:' + port + '/dsh-pet-ai-girls';
  console.log('测试服务: ' + base + '/');

  // /health
  try {
    const r = await httpReq(base + '/health');
    check('/health 返回 200', r.status === 200, 'HTTP ' + r.status);
    check('/health Content-Type 为 JSON', /application\/json/.test(r.headers.get('content-type') || ''), r.headers.get('content-type') || '');
    let health = null;
    try {
      health = JSON.parse(r.text);
    } catch {
      /* 下面断言会失败 */
    }
    check('/health ok=true', Boolean(health) && health.ok === true);
    check('/health characters 为 8 位', Boolean(health) && Array.isArray(health.characters) && health.characters.length === 8, health && health.characters ? health.characters.length + ' 位' : '');
    check('/health version=' + PLUGIN_VERSION, Boolean(health) && health.version === PLUGIN_VERSION, health ? String(health.version) : '');
    check(
      '/health animationCount=17',
      Boolean(health) && health.animationCount === 17,
      health ? String(health.animationCount) : '',
    );
    if (packReady) {
      check('/health packVersion=' + PLUGIN_VERSION + '（读到部署 marker）', Boolean(health) && health.packVersion === PLUGIN_VERSION, health ? String(health.packVersion) : '');
    } else {
      check('/health packVersion=null（packs 未生成）', Boolean(health) && health.packVersion === null, health ? String(health.packVersion) : '');
    }
    check('/health active 指向 8 位角色之一', Boolean(health) && health.active && CHAR_IDS.includes(health.active.id), health && health.active ? String(health.active.id) : '');
  } catch (e) {
    fail('/health 请求异常', String(e));
  }

  // /api/current：当前显示角色（v1.1 新增）
  try {
    const r = await httpReq(base + '/api/current');
    check('/api/current 返回 200', r.status === 200, 'HTTP ' + r.status);
    let cur = null;
    try {
      cur = JSON.parse(r.text);
    } catch {
      /* 下面断言会失败 */
    }
    check('/api/current ok=true 且 active 存在', Boolean(cur) && cur.ok === true && Boolean(cur.active && cur.active.id), cur && cur.active ? String(cur.active.id) : '');
    check('/api/current characters 为 8 位', Boolean(cur) && Array.isArray(cur.characters) && cur.characters.length === 8, cur && cur.characters ? cur.characters.length + ' 位' : '');
  } catch (e) {
    fail('/api/current 请求异常', String(e));
  }

  // 图鉴首页
  try {
    const r = await httpReq(base + '/');
    check('/ 返回 200', r.status === 200, 'HTTP ' + r.status);
    check('/ 内容包含「AI 娘」', r.text.includes('AI 娘'));
    check('/ 内容包含 8 位角色数据', r.text.includes('gallery-data') && r.text.includes('DeepSeek 娘') && r.text.includes('Qwen 娘'));
  } catch (e) {
    fail('/ 请求异常', String(e));
  }

  // data.json / 图片
  try {
    const r = await httpReq(base + '/data.json');
    check('/data.json 返回 200', r.status === 200, 'HTTP ' + r.status);
    let data = null;
    try {
      data = JSON.parse(r.text);
    } catch {
      /* ignore */
    }
    check('/data.json characters 为 8 位', Boolean(data) && Array.isArray(data.characters) && data.characters.length === 8);
  } catch (e) {
    fail('/data.json 请求异常', String(e));
  }
  try {
    const r = await httpReq(base + '/portraits/thumbs/deepseek.webp');
    check('/portraits 缩略图返回 200 + image/webp', r.status === 200 && /image\/webp/.test(r.headers.get('content-type') || ''), 'HTTP ' + r.status + ' ' + r.headers.get('content-type'));
  } catch (e) {
    fail('/portraits 请求异常', String(e));
  }

  // 404 / 目录穿越 / HEAD / 405
  try {
    const r = await httpReq('http://127.0.0.1:' + port + '/dsh-pet-ai-girls');
    check('无尾斜杠 /dsh-pet-ai-girls 也返回图鉴首页', r.status === 200 && r.text.includes('AI 娘'), 'HTTP ' + r.status);
  } catch (e) {
    fail('无尾斜杠检查异常', String(e));
  }
  try {
    const r = await httpReq(base + '/nope.css');
    check('未知文件返回 404', r.status === 404, 'HTTP ' + r.status);
  } catch (e) {
    fail('404 检查异常', String(e));
  }
  try {
    const r = await httpReq(base + '/..%2f..%2fpackage.json');
    check('目录穿越（..%2f）返回 404/400', r.status === 404 || r.status === 400, 'HTTP ' + r.status);
  } catch (e) {
    fail('目录穿越检查异常', String(e));
  }
  try {
    const r = await httpReq(base + '/%2e%2e%2f%2e%2e%2fpackage.json');
    check('目录穿越（%2e%2e）返回 404/400', r.status === 404 || r.status === 400, 'HTTP ' + r.status);
  } catch (e) {
    fail('%2e 穿越检查异常', String(e));
  }
  try {
    const r = await httpReq(base + '/..%5c..%5cpackage.json');
    check('目录穿越（Windows ..%5c）返回 404/400', r.status === 404 || r.status === 400, 'HTTP ' + r.status);
  } catch (e) {
    fail('%5c 穿越检查异常', String(e));
  }
  try {
    const r = await httpReq(base + '/', 'HEAD');
    check('HEAD / 返回 200 且无响应体', r.status === 200 && r.text.length === 0, 'HTTP ' + r.status + ' body=' + r.text.length);
  } catch (e) {
    fail('HEAD 检查异常', String(e));
  }
  try {
    const r = await httpReq(base + '/', 'POST');
    check('POST 返回 405', r.status === 405, 'HTTP ' + r.status);
  } catch (e) {
    fail('POST 检查异常', String(e));
  }

  // 视觉资源存在性（file 级，防止只注册路由却漏了素材）
  check('visual/index.html 存在', existsSync(join(VISUAL_DIR, 'index.html')));
  check('visual/data.json 存在', existsSync(join(VISUAL_DIR, 'data.json')));
  check(
    'visual 立绘/三视图共 16 张原图',
    existsSync(VISUAL_DIR) &&
      countEntries(join(VISUAL_DIR, 'portraits')).filter((f) => f.endsWith('.webp')).length === 8 &&
      countEntries(join(VISUAL_DIR, 'turnarounds')).filter((f) => f.endsWith('.webp')).length === 8,
  );
  check('plugin/icon.png 存在且 ≤ 256 KiB', existsSync(join(PLUGIN_DIR, 'icon.png')) && statSync(join(PLUGIN_DIR, 'icon.png')).size <= 256 * 1024, existsSync(join(PLUGIN_DIR, 'icon.png')) ? statSync(join(PLUGIN_DIR, 'icon.png')).size + ' B' : '缺失');
}

let fatal = null;
try {
  await main();
} catch (e) {
  fatal = e;
  fail('测试执行期间出现未捕获异常', e && e.stack ? e.stack : String(e));
} finally {
  if (server) {
    await new Promise((resolve) => server.close(() => resolve()));
  }
  if (savedDshHome === undefined) delete process.env.DSH_HOME;
  else process.env.DSH_HOME = savedDshHome;
  if (savedForce === undefined) delete process.env.DSH_PET_AI_GIRLS_FORCE;
  else process.env.DSH_PET_AI_GIRLS_FORCE = savedForce;
  try {
    rmSync(tempHome, { recursive: true, force: true });
    rmSync(tempHomeNoPet, { recursive: true, force: true });
  } catch (e) {
    console.log('WARN  临时目录清理失败: ' + String(e));
  }
}

console.log('');
console.log('---- 结果 ----');
console.log('PASS: ' + passes + '  FAIL: ' + failures + '  SKIP: ' + skipped.length);
for (const s of skipped) console.log('  SKIP: ' + s);
if (packReady) console.log('部署检查：已覆盖（packs 就绪）');
else console.log('部署检查：已跳过（plugin/packs/ 尚未生成，Lead 产线完成后重跑本测试即可）');
if (failures > 0 || fatal) {
  console.log('RESULT: FAIL');
  process.exitCode = 1;
} else {
  console.log('RESULT: PASS');
  process.exitCode = 0;
}
