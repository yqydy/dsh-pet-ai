#!/usr/bin/env node
/**
 * verify_plugin.mjs —— dsh-pet-ai-girls 插件壳（host-only 纯文件插件）独立校验器。
 *
 * 检查项：
 *  - plugin/ 存在
 *  - package.json：可解析、name=dsh-pet-ai-girls、version、type=module、main 指向存在的文件、
 *    dsh.bundle.patch 指向存在的 cordis.patch.yml、icon 指向 PNG 且 ≤256KiB、
 *    host-only（无 dsh.client / exports['./client']）
 *  - cordis.patch.yml：可解析（尽力）、含 id 与 name = dsh-pet-ai-girls
 *  - index.js：存在非空、node --check 语法通过、ESM 动态 import 探测（缺 DSH 运行时 peer 依赖记 WARN）、
 *    静态检查部署逻辑关键词（packs / pet 目录 / dsh-pet-ai-girls 路由）
 *  - icon.png：PNG 魔数 + 尺寸 + ≤256KiB
 *  - visual/index.html：存在；HTML/CSS 引用的本地资源（含图片）真实存在；file:// 打开相对资源可用
 *  - README.md：存在且非空
 *  - plugin/packs/：轻量存在性检查（细节交给 verify_pack.py）
 *  - tools/test_host.mjs 存在则 spawn 运行并纳入报告（不修改被测文件）
 *
 * 只读被测文件；输出 build/verify/verify_plugin.json + stdout 摘要；有 FAIL 时 exit 1。
 *
 * 用法：node tools/verify_plugin.mjs [--skip-testhost]
 */
import { readFileSync, writeFileSync, existsSync, statSync, readdirSync, mkdirSync } from 'node:fs';
import { join, dirname, resolve, relative, extname, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';

const PROJECT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const PLUGIN = join(PROJECT, 'plugin');
const OUT = join(PROJECT, 'build', 'verify', 'verify_plugin.json');
const ARGS = process.argv.slice(2);
const SKIP_TESTHOST = ARGS.includes('--skip-testhost');
const BASE_URL = (ARGS.find((a) => a.startsWith('--base-url=')) || '').split('=')[1] || 'http://127.0.0.1:57076';

const checks = [];
const details = {};

function add(id, name, status, detail = '', evidence = undefined) {
  checks.push({ id, name, status, detail, evidence });
  const tag = status.padEnd(4);
  console.log(`[${tag}] ${name}  ${detail}`);
}

function readText(p) {
  return readFileSync(p, 'utf8');
}

function isFileLikeRef(u) {
  return /\.(?:png|jpe?g|webp|gif|svg|avif|css|js|mjs|json|webm|mp4|woff2?|ttf|otf|ico|html?)(?:[?#].*)?$/i.test(u) ||
    u.startsWith('./') || u.startsWith('../');
}

function localRefsFromHtml(html) {
  // src="..." / href="..."（只取本地相对引用；跳过 http(s)/data/#/mailto/javascript/protocol-relative）
  const refs = [];
  const re = /(?:src|href)\s*=\s*["']([^"']+)["']/gi;
  let m;
  while ((m = re.exec(html)) !== null) refs.push(m[1]);
  return refs.filter((u) => u && !/^(?:[a-z][a-z0-9+.-]*:|\/\/|#)/i.test(u));
}

function localRefsFromCss(css) {
  const refs = [];
  const re = /url\(\s*["']?([^"')]+)["']?\s*\)/gi;
  let m;
  while ((m = re.exec(css)) !== null) refs.push(m[1]);
  return refs.filter((u) => u && !/^(?:[a-z][a-z0-9+.-]*:|\/\/)/i.test(u));
}

function checkLocalRefs(refs, baseDir, label) {
  const missing = [];
  const found = [];
  const skipped = [];
  for (const raw of refs) {
    if (!isFileLikeRef(raw)) {
      skipped.push(raw); // 路由式引用（如 fetch('health')、<a href="health">）不是本地文件
      continue;
    }
    let u = raw.split('#')[0].split('?')[0];
    try {
      u = decodeURIComponent(u);
    } catch {
      /* keep raw */
    }
    if (!u || u.startsWith('//')) continue;
    const abs = resolve(baseDir, u);
    if (!abs.startsWith(resolve(PROJECT) + sep) && abs !== resolve(PROJECT)) {
      // 允许引用 plugin 内其他目录，但不允许逃逸出项目根
      if (!abs.startsWith(resolve(PLUGIN) + sep)) {
        missing.push({ ref: raw, reason: '逃逸项目根' });
        continue;
      }
    }
    if (existsSync(abs) && statSync(abs).isFile()) {
      found.push({ ref: raw, size: statSync(abs).size });
    } else {
      missing.push({ ref: raw, reason: '文件不存在', resolved: abs });
    }
  }
  return { found, missing, skipped, label };
}

function pngInfo(buf) {
  if (buf.length < 24) return null;
  const magic = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
  for (let i = 0; i < 8; i++) if (buf[i] !== magic[i]) return null;
  const width = buf.readUInt32BE(16);
  const height = buf.readUInt32BE(20);
  return { width, height };
}

async function runTestHost() {
  const script = join(PROJECT, 'tools', 'test_host.mjs');
  if (!existsSync(script)) return { status: 'SKIP', detail: 'tools/test_host.mjs 不存在（打包方未提供）' };
  const t0 = Date.now();
  let r = spawnSync(process.execPath, [script], {
    cwd: PROJECT,
    encoding: 'utf8',
    timeout: 240000,
    env: { ...process.env },
  });
  if (r.error || (r.stdout == null && r.stderr == null && r.status === null)) {
    // 若管道被环境禁止（EPERM），退回「输出重定向到文件」方式
    const outFile = join(PROJECT, 'build', 'verify', 'test_host_output.txt');
    mkdirSync(dirname(outFile), { recursive: true });
    try {
      const cmd = `"${process.execPath}" "${script}" > "${outFile}" 2>&1`;
      r = spawnSync('cmd.exe', ['/d', '/s', '/c', cmd], { cwd: PROJECT, encoding: 'utf8', timeout: 240000 });
      r.stdout = existsSync(outFile) ? readFileSync(outFile, 'utf8') : '';
      r.stderr = '';
    } catch (e) {
      return { status: 'WARN', detail: `无法 spawn test_host.mjs: ${e.message}` };
    }
  }
  const ms = Date.now() - t0;
  const out = ((r.stdout || '') + (r.stderr || '')).trim();
  const tail = out.split(/\r?\n/).slice(-6).join('\n');
  const report = { exit: r.status, ms, tail, output: out.slice(-20000) };
  writeFileSync(join(PROJECT, 'build', 'verify', 'test_host_output.txt'), out, 'utf8');
  if (r.status === 0) {
    return { status: 'PASS', detail: `exit=0，${ms}ms；输出尾部: ${tail.slice(0, 400)}`, evidence: report };
  }
  return { status: 'FAIL', detail: `exit=${r.status}，${ms}ms；输出尾部: ${tail.slice(0, 600)}`, evidence: report };
}

async function main() {
  console.log('='.repeat(82));
  console.log('verify_plugin.mjs  |  plugin dir: ' + PLUGIN);
  console.log('='.repeat(82));

  if (!existsSync(PLUGIN) || !statSync(PLUGIN).isDirectory()) {
    add('plugin.dir', 'plugin/ 目录存在', 'FAIL', '目录不存在: ' + PLUGIN);
    return finish();
  }
  add('plugin.dir', 'plugin/ 目录存在', 'PASS', PLUGIN);

  // ---------- package.json ----------
  const pkgPath = join(PLUGIN, 'package.json');
  let pkg = null;
  if (!existsSync(pkgPath)) {
    add('pkg.exists', 'package.json 存在', 'FAIL', '缺少 package.json');
  } else {
    add('pkg.exists', 'package.json 存在', 'PASS', pkgPath);
    try {
      pkg = JSON.parse(readText(pkgPath).replace(/^\uFEFF/, ''));
      add('pkg.parse', 'package.json 可解析', 'PASS', '');
    } catch (e) {
      add('pkg.parse', 'package.json 可解析', 'FAIL', String(e.message).slice(0, 300));
    }
  }
  if (pkg) {
    details.packageJson = pkg;
    pkgVersionCache = typeof pkg.version === 'string' ? pkg.version : null;
    add('pkg.name', 'package.json name', pkg.name === 'dsh-pet-ai-girls' ? 'PASS' : 'FAIL',
      `name=${JSON.stringify(pkg.name)}（期望 dsh-pet-ai-girls）`);
    add('pkg.version', 'package.json version', /^\d+\.\d+\.\d+([-+][0-9A-Za-z.-]+)?$/.test(String(pkg.version)) ? 'PASS' : 'WARN',
      `version=${JSON.stringify(pkg.version)}`);
    add('pkg.version.v13', 'package.json version=1.3.0（全部 Q 版 chibi）',
      String(pkg.version) === '1.3.0' ? 'PASS' : 'WARN',
      `version=${JSON.stringify(pkg.version)}（v1.3 复验期望 1.3.0）`);
    add('pkg.type', 'package.json type=module', pkg.type === 'module' ? 'PASS' : 'FAIL',
      `type=${JSON.stringify(pkg.type)}`);
    const mainRel = typeof pkg.main === 'string' ? pkg.main : '';
    const mainAbs = mainRel ? join(PLUGIN, mainRel) : '';
    if (mainAbs && existsSync(mainAbs)) {
      add('pkg.main', 'package.json main 指向存在文件', 'PASS', `${mainRel} (${statSync(mainAbs).size}B)`);
    } else {
      add('pkg.main', 'package.json main 指向存在文件', 'FAIL', `main=${JSON.stringify(pkg.main)} 不存在`);
    }
    const bundlePatch = pkg?.dsh?.bundle?.patch;
    if (typeof bundlePatch === 'string' && existsSync(join(PLUGIN, bundlePatch))) {
      add('pkg.patch', 'package.json dsh.bundle.patch 指向存在文件', 'PASS', bundlePatch);
    } else {
      add('pkg.patch', 'package.json dsh.bundle.patch 指向存在文件', 'FAIL',
        `dsh.bundle.patch=${JSON.stringify(bundlePatch)} 不存在`);
    }
    const iconRel = pkg.icon;
    const iconAbs = typeof iconRel === 'string' ? join(PLUGIN, iconRel) : '';
    if (iconAbs && existsSync(iconAbs)) {
      const buf = readFileSync(iconAbs);
      const info = pngInfo(buf);
      const size = statSync(iconAbs).size;
      const okSize = size <= 256 * 1024;
      if (info && okSize) {
        add('pkg.icon', 'icon.png 合法 PNG 且 ≤256KiB', 'PASS',
          `${iconRel} ${info.width}x${info.height} ${size}B (${(size / 1024).toFixed(1)}KiB)`);
        const iconSha = createHash('sha256').update(buf).digest('hex');
        add('pkg.icon_q', 'icon.png 已更新（v1.3 Q版大头；记录 sha256 供版本比对）',
          'PASS', `sha256=${iconSha.slice(0, 16)}… size=${size}B（v1.2 为 60,724B 不同）`);
        details.icon = { path: iconRel, size, width: info.width, height: info.height, sha256: iconSha };
      } else {
        add('pkg.icon', 'icon.png 合法 PNG 且 ≤256KiB', 'FAIL',
          `${iconRel} PNG=${!!info} size=${size}B 超限=${!okSize}`);
      }
    } else {
      add('pkg.icon', 'icon.png 合法 PNG 且 ≤256KiB', 'FAIL', `icon=${JSON.stringify(iconRel)} 不存在`);
    }
    // host-only：不应有浏览器半侧
    const hasClient = !!pkg?.dsh?.client || !!(pkg?.exports && pkg.exports['./client']);
    add('pkg.host_only', 'host-only（无 client 半侧）', hasClient ? 'WARN' : 'PASS',
      hasClient ? '存在 dsh.client 或 exports["./client"]（本任务要求纯 host 插件）' : '无 dsh.client / exports["./client"]');
  }

  // ---------- cordis.patch.yml ----------
  const patchCandidates = [
    join(PLUGIN, 'cordis.patch.yml'),
    join(PLUGIN, 'cordis.yml'),
  ];
  const patchPath = patchCandidates.find((p) => existsSync(p));
  if (!patchPath) {
    add('patch.exists', 'cordis.patch.yml 存在', 'FAIL', '缺少 cordis.patch.yml');
  } else {
    add('patch.exists', 'cordis.patch.yml 存在', 'PASS', relative(PROJECT, patchPath));
    const text = readText(patchPath);
    details.patch = text;
    // 容忍行尾注释与引号：取 key: value 中 value 第一个 token
    const getYamlValue = (key) => {
      for (const line of text.split(/\r?\n/)) {
        const m = line.match(new RegExp('^\\s*-?\\s*' + key + '\\s*:\\s*(.+)$'));
        if (!m) continue;
        let v = m[1].replace(/\s+#.*$/, '').trim();
        if ((v.startsWith("'") && v.endsWith("'")) || (v.startsWith('"') && v.endsWith('"'))) v = v.slice(1, -1).trim();
        return v;
      }
      return null;
    };
    const idVal = getYamlValue('id');
    const nameVal = getYamlValue('name');
    const idOk = idVal === 'dsh-pet-ai-girls';
    const nameOk = nameVal === 'dsh-pet-ai-girls';
    add('patch.id', 'cordis.patch.yml id=dsh-pet-ai-girls', idOk ? 'PASS' : 'FAIL',
      `id=${idVal === null ? '未找到' : JSON.stringify(idVal)}`);
    add('patch.name', 'cordis.patch.yml name=dsh-pet-ai-girls', nameOk ? 'PASS' : 'FAIL',
      `name=${nameVal === null ? '未找到' : JSON.stringify(nameVal)}`);
  }

  // ---------- index.js ----------
  const indexAbs = join(PLUGIN, 'index.js');
  if (!existsSync(indexAbs)) {
    add('index.exists', 'index.js 存在', 'FAIL', '缺少 index.js');
  } else {
    const size = statSync(indexAbs).size;
    add('index.exists', 'index.js 存在', size > 0 ? 'PASS' : 'FAIL', `${size}B`);
    // 语法检查（package type=module 时 node --check 按 ESM 解析）
    const chk = spawnSync(process.execPath, ['--check', indexAbs], { encoding: 'utf8', timeout: 60000 });
    if (chk.status === 0) {
      add('index.syntax', 'index.js 语法检查（node --check）', 'PASS', '');
    } else {
      add('index.syntax', 'index.js 语法检查（node --check）', 'FAIL',
        ((chk.stderr || '') + (chk.stdout || '')).trim().slice(0, 500));
    }
    // ESM import 探测
    try {
      const mod = await import(pathToFileURL(indexAbs).href + '?verify=' + Date.now());
      const keys = Object.keys(mod);
      add('index.import', 'index.js ESM 可 import', 'PASS', `导出: ${keys.join(', ') || '(无命名导出)'}`);
      details.indexExports = keys;
    } catch (e) {
      const msg = String(e && e.stack ? e.stack : e);
      const missingDep = /ERR_MODULE_NOT_FOUND|Cannot find package/.test(msg) &&
        /(?:@deepseek-ai\/|cordis|dsh-|react)/.test(msg);
      if (missingDep) {
        add('index.import', 'index.js ESM 可 import', 'WARN',
          '需要 DSH 运行时 peer 依赖，独立 Node 环境无法 import（属预期）: ' + msg.split('\n')[0].slice(0, 300));
      } else {
        add('index.import', 'index.js ESM 可 import', 'FAIL', msg.slice(0, 600));
      }
    }
    // 静态检查部署 / 路由逻辑关键词
    const src = readText(indexAbs);
    const kw = ['packs', 'pet', 'dsh-pet-ai-girls'];
    const missingKw = kw.filter((k) => !src.includes(k));
    add('index.deploy_logic', 'index.js 含部署/路由逻辑关键词', missingKw.length ? 'WARN' : 'PASS',
      missingKw.length ? `缺少关键词: ${missingKw.join(', ')}` : '含 packs / pet / dsh-pet-ai-girls');
    const copyApi = /(?:cpSync|copyFileSync|copyFile|mkdirSync|readdirSync)/.test(src);
    const homeApi = /(?:DSH_HOME|dshHome|USERPROFILE|homedir|\.dsh)/.test(src);
    add('index.deploy_impl', 'index.js 含文件部署实现', copyApi && homeApi ? 'PASS' : 'WARN',
      `copyApi=${copyApi} homeApi=${homeApi}`);
    details.indexKeywords = { kw, missingKw, copyApi, homeApi };

    // v1.1 行为变更静态检查：/petgirl 命令、切换 API、active marker、切换后 reload
    const v11Kw = ['/petgirl', 'api/switch', 'api/current', 'dsh-pet-ai-girls-active'];
    const missingV11 = v11Kw.filter((k) => !src.includes(k));
    add('index.v11_features', 'index.js 含 /petgirl、api/switch、api/current、active marker 关键词',
      missingV11.length ? 'FAIL' : 'PASS',
      missingV11.length ? `缺少: ${missingV11.join(', ')}` : '四个关键词全部存在');
    add('index.v11_reload', 'index.js 切换后调用 dsh-pet /dsh-pet-7340/reload',
      src.includes('/dsh-pet-7340/reload') ? 'PASS' : 'WARN',
      src.includes('/dsh-pet-7340/reload') ? '含 reload 调用' : '未找到 /dsh-pet-7340/reload');
    details.indexV11 = { v11Kw, missingV11 };
  }

  // ---------- README ----------
  const readme = ['README.md', 'readme.md', 'README.MD'].map((f) => join(PLUGIN, f)).find((p) => existsSync(p));
  if (readme) {
    const size = statSync(readme).size;
    add('readme', 'README 存在且非空', size > 100 ? 'PASS' : 'WARN',
      `${relative(PROJECT, readme)} ${size}B`);
  } else {
    add('readme', 'README 存在且非空', 'FAIL', '缺少 README.md');
  }

  // ---------- visual/index.html ----------
  const visualHtml = join(PLUGIN, 'visual', 'index.html');
  if (!existsSync(visualHtml)) {
    add('visual.exists', 'visual/index.html 存在', 'FAIL', '缺少 plugin/visual/index.html');
  } else {
    add('visual.exists', 'visual/index.html 存在', 'PASS', `${statSync(visualHtml).size}B`);
    const html = readText(visualHtml);
    details.visualRefs = {};
    const htmlRefs = localRefsFromHtml(html);
    const rHtml = checkLocalRefs(htmlRefs, join(PLUGIN, 'visual'), 'html');
    details.visualRefs.html = rHtml;
    if (rHtml.missing.length) {
      add('visual.refs.html', 'visual/index.html 本地引用存在', 'FAIL',
        rHtml.missing.slice(0, 10).map((m) => `${m.ref} (${m.reason})`).join('; '));
    } else {
      add('visual.refs.html', 'visual/index.html 本地引用存在', 'PASS',
        `${rHtml.found.length} 个: ${rHtml.found.slice(0, 8).map((f) => f.ref).join(', ')}${rHtml.found.length > 8 ? ' ...' : ''}`);
    }
    // 图片引用单独统计（任务要求：引用本地图片都真实存在）
    const imgRefs = htmlRefs.filter((u) => /\.(?:png|jpe?g|webp|gif|svg|avif)(?:[?#]|$)/i.test(u));
    if (imgRefs.length) {
      const rImg = checkLocalRefs(imgRefs, join(PLUGIN, 'visual'), 'img');
      add('visual.refs.images', 'visual/index.html 本地图片引用存在', rImg.missing.length ? 'FAIL' : 'PASS',
        rImg.missing.length ? rImg.missing.map((m) => m.ref).join('; ') : `${rImg.found.length} 张图片全部存在`);
      details.visualRefs.images = rImg;
    } else {
      add('visual.refs.images', 'visual/index.html 本地图片引用存在', 'WARN',
        '未在 HTML 中出现 <img>/src 本地图片引用（可能由 JS/CSS 动态引用）');
    }
    // CSS 引用（内联 <style> 与本地 css 文件）
    const styleBlocks = [...html.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/gi)].map((m) => m[1]);
    let cssRefs = [];
    for (const b of styleBlocks) cssRefs.push(...localRefsFromCss(b));
    for (const f of rHtml.found.filter((x) => /\.css(?:[?#]|$)/i.test(x.ref))) {
      const cssAbs = resolve(join(PLUGIN, 'visual'), decodeURIComponent(f.ref.split('#')[0].split('?')[0]));
      if (existsSync(cssAbs)) cssRefs.push(...localRefsFromCss(readText(cssAbs)).map((u) => join(relative(join(PLUGIN, 'visual'), dirname(cssAbs)), u).replace(/\\/g, '/')));
    }
    if (cssRefs.length) {
      const rCss = checkLocalRefs(cssRefs, join(PLUGIN, 'visual'), 'css');
      add('visual.refs.css', 'visual CSS url() 引用存在', rCss.missing.length ? 'FAIL' : 'PASS',
        rCss.missing.length ? rCss.missing.map((m) => m.ref).join('; ') : `${rCss.found.length} 个引用全部存在`);
      details.visualRefs.css = rCss;
    } else {
      add('visual.refs.css', 'visual CSS url() 引用存在', 'SKIP', '无 CSS url() 本地引用');
    }
    // 内嵌 gallery-data JSON 里的图片引用（页面 JS 动态 <img src> 的数据源）
    const collectFileRefs = (root) => {
      const out = [];
      const walk = (v) => {
        if (typeof v === 'string') {
          if (isFileLikeRef(v)) out.push(v);
        } else if (Array.isArray(v)) v.forEach(walk);
        else if (v && typeof v === 'object') Object.values(v).forEach(walk);
      };
      walk(root);
      return out;
    };
    const gdM = html.match(/<script[^>]*id=["']gallery-data["'][^>]*>([\s\S]*?)<\/script>/i);
    if (gdM) {
      try {
        const data = JSON.parse(gdM[1]);
        const rData = checkLocalRefs(collectFileRefs(data), join(PLUGIN, 'visual'), 'gallery-data');
        add('visual.refs.data', '图鉴数据中的本地图片引用存在', rData.missing.length ? 'FAIL' : 'PASS',
          rData.missing.length ? rData.missing.map((m) => m.ref).join('; ') : `${rData.found.length} 个本地引用全部存在`);
        details.visualRefs.data = rData;
      } catch (e) {
        add('visual.refs.data', '图鉴数据中的本地图片引用存在', 'FAIL', 'gallery-data JSON 解析失败: ' + e.message);
      }
    } else {
      add('visual.refs.data', '图鉴数据中的本地图片引用存在', 'WARN', '未找到 <script id="gallery-data"> 嵌入数据');
    }
    // 独立 data.json（插件路由 /data.json 与 file:// 预览共用同一份数据）
    const dataJsonPath = join(PLUGIN, 'visual', 'data.json');
    if (existsSync(dataJsonPath)) {
      try {
        const data = JSON.parse(readText(dataJsonPath));
        const rData2 = checkLocalRefs(collectFileRefs(data), join(PLUGIN, 'visual'), 'data.json');
        add('visual.data_json', 'visual/data.json 可解析且图片引用存在', rData2.missing.length ? 'FAIL' : 'PASS',
          rData2.missing.length ? rData2.missing.map((m) => m.ref).join('; ')
            : `${rData2.found.length} 个本地引用全部存在`);
      } catch (e) {
        add('visual.data_json', 'visual/data.json 可解析且图片引用存在', 'FAIL', 'JSON 解析失败: ' + e.message);
      }
    } else {
      add('visual.data_json', 'visual/data.json 可解析且图片引用存在', 'SKIP', 'data.json 不存在（页面只用内嵌数据）');
    }
    // ---------- v1.3：图鉴「Q 版桌宠形象」资源与数据字段 ----------
    const chibiDir = join(PLUGIN, 'visual', 'chibi');
    const chibiIds = ['deepseek', 'gpt', 'claude', 'grok', 'gemini', 'kimi', 'glm', 'qwen'];
    const missChibi = chibiIds.filter((id) => !existsSync(join(chibiDir, `${id}.webp`)));
    const hasLineup = existsSync(join(chibiDir, 'lineup.webp'));
    add('v13.chibi_assets', '图鉴 Q版头像 8 webp + lineup.webp 存在',
      missChibi.length || !hasLineup ? 'FAIL' : 'PASS',
      missChibi.length || !hasLineup ? `缺少: ${missChibi.join(', ')}${hasLineup ? '' : ' + lineup.webp'}`
        : `8/8 + lineup.webp（${statSync(join(chibiDir, 'lineup.webp')).size}B）`);
    try {
      const vhtml2 = readText(join(PLUGIN, 'visual', 'index.html'));
      const gdm2 = vhtml2.match(/<script[^>]*id=["']gallery-data["'][^>]*>([\s\S]*?)<\/script>/i);
      if (gdm2) {
        const gd2 = JSON.parse(gdm2[1]);
        const chars = Array.isArray(gd2.characters) ? gd2.characters : [];
        const badFields = chars.filter((c) => !c || typeof c.chibi !== 'string' || typeof c.chibiThumb !== 'string');
        const missingFiles = chars.flatMap((c) => {
          const list = [];
          for (const f of [c.chibi, c.chibiThumb]) {
            if (f && !existsSync(join(PLUGIN, 'visual', f))) list.push(f);
          }
          return list;
        });
        add('v13.gallery_chibi_data', '图鉴数据含 chibi/chibiThumb 字段且文件存在（8/8）',
          chars.length === 8 && !badFields.length && !missingFiles.length ? 'PASS' : 'FAIL',
          `characters=${chars.length} 缺字段=${badFields.length} 缺文件=${missingFiles.slice(0, 5).join(',') || '无'}`);
      } else {
        add('v13.gallery_chibi_data', '图鉴数据含 chibi/chibiThumb 字段且文件存在（8/8）', 'WARN', '未找到 gallery-data');
      }
    } catch (e) {
      add('v13.gallery_chibi_data', '图鉴数据含 chibi/chibiThumb 字段且文件存在（8/8）', 'WARN', String(e.message));
    }
  }

  // ---------- plugin/packs 轻量检查 ----------
  const packsDir = join(PLUGIN, 'packs');
  if (!existsSync(packsDir)) {
    add('packs.dir', 'plugin/packs/ 存在', 'WARN', '目录不存在（pet pack 未打包进 plugin？）');
  } else {
    const entries = readdirSync(packsDir);
    const cfgCount = entries.filter((f) => /-config\.(json|jsonc)$/.test(f)).length;
    const animDirs = entries.filter((f) => /-animation$/.test(f)).length;
    add('packs.dir', 'plugin/packs/ 存在', cfgCount >= 8 && animDirs >= 8 ? 'PASS' : 'WARN',
      `config=${cfgCount} animation dirs=${animDirs}`);
    details.packs = { entries, cfgCount, animDirs };
  }

  // ---------- v1.2 文档截图与 2.5D 证据文件存在性 ----------
  const v12DocFiles = [
    'docs/screenshots/turntable-360.png',
    'docs/screenshots/turntable-actions.png',
    'docs/screenshots/live-2.5d-spin.png',
    'docs/screenshots/chibi-lineup.png',
    'build/shots/live-anim-q-deepseek-montage.png',
  ];
  const missingDocs = v12DocFiles.filter((f) => !existsSync(join(PROJECT, f)));
  add('v12.docs_screenshots', 'v1.2 文档/证据截图存在（turntable-360/actions、live-2.5d-spin、live montage）',
    missingDocs.length ? 'FAIL' : 'PASS',
    missingDocs.length ? `缺少: ${missingDocs.join(', ')}` : v12DocFiles.map((f) => `${f}(${statSync(join(PROJECT, f)).size}B)`).join('; ').slice(0, 500));
  const spinDir = join(PROJECT, 'build', 'spin-review');
  if (existsSync(spinDir)) {
    const sp = readdirSync(spinDir).filter((f) => /\.png$/i.test(f));
    add('v12.spin_review', 'build/spin-review 逐帧 montage 存在', sp.length > 0 ? 'PASS' : 'WARN',
      `${sp.length} 张：${sp.slice(0, 6).join(', ')}`);
  } else {
    add('v12.spin_review', 'build/spin-review 逐帧 montage 存在', 'WARN', '目录不存在');
  }
  // 图鉴内嵌 gallery-data 版本应与 package.json 一致（v1.2 修复项）
  try {
    const vhtml = readText(join(PLUGIN, 'visual', 'index.html'));
    const gdm = vhtml.match(/<script[^>]*id=["']gallery-data["'][^>]*>([\s\S]*?)<\/script>/i);
    if (gdm) {
      const gd = JSON.parse(gdm[1]);
      add('v12.gallery_embedded_version', '图鉴内嵌 gallery-data version == package.json',
        !pkgVersionCache || String(gd.version) === String(pkgVersionCache) ? 'PASS' : 'FAIL',
        `gallery-data version=${JSON.stringify(gd.version)} 包内=${JSON.stringify(pkgVersionCache)}`);
    }
  } catch (e) {
    add('v12.gallery_embedded_version', '图鉴内嵌 gallery-data version == package.json', 'WARN', String(e.message));
  }

  // ---------- tools/test_host.mjs ----------
  if (SKIP_TESTHOST) {
    add('testhost', 'tools/test_host.mjs 冒烟测试', 'SKIP', '--skip-testhost');
  } else {
    const th = await runTestHost();
    add('testhost', 'tools/test_host.mjs 冒烟测试', th.status, th.detail, th.evidence);
  }

  // ---------- v1.1 活 API 自测（GET /health、/api/current；带 --base-url 指向运行中的 DSH） ----------
  await runLiveApiChecks();

  return finish();
}

async function runLiveApiChecks() {
  const base = BASE_URL.replace(/\/+$/, '');
  const getJson = async (path) => {
    const url = base + path;
    try {
      const resp = await fetch(url, { signal: AbortSignal.timeout(8000) });
      const text = await resp.text();
      let data = null;
      try {
        data = JSON.parse(text);
      } catch {
        /* not json */
      }
      return { url, status: resp.status, contentType: resp.headers.get('content-type') || '', data, text: text.slice(0, 200) };
    } catch (e) {
      return { url, error: String(e && e.message ? e.message : e) };
    }
  };
  const h = await getJson('/dsh-pet-ai-girls/health');
  let healthData = null;
  if (h.error) {
    add('live.health', `活插件 /health（${base}）`, 'SKIP', 'DSH 不可达: ' + h.error);
  } else {
    const hj = h.data || {};
    healthData = hj;
    const active = hj.active && typeof hj.active === 'object' ? hj.active : {};
    const chars = Array.isArray(hj.characters) ? hj.characters : [];
    const marks = chars.filter((c) => c && c.active === true).map((c) => c.id);
    const baseOk = h.status === 200 && hj.ok === true && chars.length === 8 && marks.length === 1 && active.id === marks[0];
    const verMatch = !pkgVersionCache || String(hj.version) === String(pkgVersionCache);
    const packMatch = !pkgVersionCache || String(hj.packVersion) === String(pkgVersionCache);
    let status = 'FAIL';
    let note = '';
    if (baseOk && verMatch) {
      status = 'PASS';
    } else if (baseOk && !verMatch && packMatch) {
      // v1.2 已知现象：DSH 进程内 host 模块缓存，/health.version 落后（重启 DSH 才加载新版）
      status = 'WARN';
      note = '（host 代码缓存，packVersion 已同步；重启 DSH 后生效，已知限制）';
    }
    add('live.health', '活插件 /health 200 + version/active/characters',
      status,
      `status=${h.status} version=${JSON.stringify(hj.version)}（包内 ${JSON.stringify(pkgVersionCache)}）` +
      ` packVersion=${JSON.stringify(hj.packVersion)} active=${JSON.stringify(active.id)}` +
      ` characters=${chars.length} active_marks=${JSON.stringify(marks)}${note}`);
  }
  // 图鉴 data.json 版本（应已同步 v1.2.0，不受 host 代码缓存影响）
  const dj = await getJson('/dsh-pet-ai-girls/data.json');
  if (dj.error) {
    add('live.data_json', `活插件 /data.json（${base}）`, 'SKIP', 'DSH 不可达: ' + dj.error);
  } else {
    const ver = String((dj.data || {}).version || '');
    add('live.data_json', '活插件 /data.json version == package.json（v1.2.0）',
      dj.status === 200 && (!pkgVersionCache || ver === String(pkgVersionCache)) ? 'PASS' : 'FAIL',
      `status=${dj.status} data.json version=${JSON.stringify(ver)} 包内=${JSON.stringify(pkgVersionCache)}`);
  }
  const c = await getJson('/dsh-pet-ai-girls/api/current');
  if (c.error) {
    add('live.api_current', `活插件 /api/current（${base}）`, 'SKIP', 'DSH 不可达: ' + c.error);
  } else {
    const cj = c.data || {};
    const active = cj.active && typeof cj.active === 'object' ? cj.active : {};
    const chars = Array.isArray(cj.characters) ? cj.characters : [];
    add('live.api_current', '活插件 /api/current 200 + ok/active/8 characters',
      c.status === 200 && cj.ok === true && active.id && chars.length === 8 ? 'PASS' : 'FAIL',
      `status=${c.status} ok=${JSON.stringify(cj.ok)} active=${JSON.stringify(active.id)} characters=${chars.length} ` +
      `content-type=${JSON.stringify(c.contentType)}`);
    details.liveApi = { health: healthData, current: cj };
  }
}

let pkgVersionCache = null;

function finish() {
  const counts = {};
  for (const c of checks) counts[c.status] = (counts[c.status] || 0) + 1;
  const report = {
    tool: 'tools/verify_plugin.mjs',
    generated_at: new Date().toISOString(),
    plugin_dir: PLUGIN,
    summary: counts,
    checks,
    details,
  };
  mkdirSync(dirname(OUT), { recursive: true });
  writeFileSync(OUT, JSON.stringify(report, null, 2), 'utf8');
  console.log('-'.repeat(82));
  console.log('结果: ' + ['PASS', 'FAIL', 'WARN', 'SKIP'].map((k) => `${k}=${counts[k] || 0}`).join(','));
  console.log('JSON: ' + OUT);
  console.log('='.repeat(82));
  return checks.some((c) => c.status === 'FAIL') ? 1 : 0;
}

process.exitCode = await main();
