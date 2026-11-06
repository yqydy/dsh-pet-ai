// Browser-based alpha-boundary check for every pet webm.
// Chrome's headless --dump-dom does not wait for async media work, so drive it
// over the DevTools protocol instead: navigate to a local checker page, then
// Runtime.evaluate an async function that seeks each video, draws it to a
// canvas and returns the alpha bounding box for several sampled frames.
//
// Usage: node tools/framecheck.mjs [--dir build/webm] [--out build/verify/framecheck.json]
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { readdirSync, readFileSync, writeFileSync, mkdirSync, statSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const getArg = (name, dflt) => {
  const i = args.indexOf(name);
  return i >= 0 ? args[i + 1] : dflt;
};
const SRC_DIR = resolve(ROOT, getArg('--dir', 'build/webm'));
const OUT = resolve(ROOT, getArg('--out', 'build/verify/framecheck.json'));
const CHROME = getArg('--chrome', 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe');
const PORT = Number(getArg('--port', '9337'));

function listVideos(dir) {
  const out = [];
  const walk = (d) => {
    for (const e of readdirSync(d, { withFileTypes: true })) {
      const p = join(d, e.name);
      if (e.isDirectory()) walk(p);
      else if (e.name.toLowerCase().endsWith('.webm')) out.push(relative(SRC_DIR, p).replace(/\\/g, '/'));
    }
  };
  walk(dir);
  return out.sort();
}

function httpJson(url) {
  return new Promise((res, rej) => {
    const req = createServer; // avoid unused warning
    import('node:http').then(({ get }) => {
      get(url, (r) => {
        let body = '';
        r.on('data', (c) => (body += c));
        r.on('end', () => {
          try { res(JSON.parse(body)); } catch (e) { rej(e); }
        });
      }).on('error', rej);
    }).catch(rej);
  });
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const PAGE = `<!DOCTYPE html><html><head><meta charset="utf-8"><style>body{background:#111}</style></head>
<body><canvas id="cv" width="640" height="360"></canvas>
<script>
const FILES = %FILES%;
const TIMES = [0.12, 0.35, 0.6, 0.88];
function aabb(data, w, h, threshold) {
  let minX = 9999, minY = 9999, maxX = -1, maxY = -1, count = 0;
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const a = data[(y * w + x) * 4 + 3];
    if (a > threshold) { count++; if (x < minX) minX = x; if (x > maxX) maxX = x; if (y < minY) minY = y; if (y > maxY) maxY = y; }
  }
  return { minX, minY, maxX, maxY, count };
}
function loadVideo(src) {
  return new Promise((resolve, reject) => {
    const v = document.createElement('video');
    v.muted = true; v.playsInline = true; v.preload = 'auto';
    v.onloadeddata = () => resolve(v);
    v.onerror = () => reject(new Error('video error'));
    v.src = src; v.load();
  });
}
function seek(v, t) {
  return new Promise((resolve) => {
    const done = () => { v.removeEventListener('seeked', done); resolve(); };
    v.addEventListener('seeked', done);
    v.currentTime = Math.max(0.01, Math.min(t, Math.max(0.02, (v.duration || 1) - 0.05)));
  });
}
window.__run = async () => {
  const cv = document.getElementById('cv');
  const ctx = cv.getContext('2d', { willReadFrequently: true });
  const all = [];
  for (let i = 0; i < FILES.length; i++) {
    const item = { file: FILES[i], frames: [], error: null };
    try {
      const v = await loadVideo('../webm/' + FILES[i]);
      item.duration = v.duration;
      for (const t of TIMES) {
        if (t > (v.duration || 0)) continue;
        await seek(v, t);
        ctx.clearRect(0, 0, 640, 360);
        ctx.drawImage(v, 0, 0, 640, 360);
        const d = ctx.getImageData(0, 0, 640, 360).data;
        const b = aabb(d, 640, 360, 8);
        const body = aabb(d, 640, 360, 120);
        item.frames.push({ t: Math.round(t * 100) / 100, minX: b.minX, minY: b.minY, maxX: b.maxX, maxY: b.maxY, alphaPixels: b.count,
                           bodyMinX: body.minX, bodyMinY: body.minY, bodyMaxX: body.maxX, bodyMaxY: body.maxY });
      }
      v.src = ''; v.load();
    } catch (e) { item.error = String((e && e.message) || e); }
    all.push(item);
    document.title = 'PROGRESS ' + (i + 1) + '/' + FILES.length;
  }
  return all;
};
</script></body></html>`;

async function main() {
  const files = listVideos(SRC_DIR);
  if (!files.length) throw new Error('no webm under ' + SRC_DIR);
  const checkDir = resolve(ROOT, 'build/framecheck');
  mkdirSync(checkDir, { recursive: true });
  const pagePath = join(checkDir, 'check2.html');
  writeFileSync(pagePath, PAGE.replace('%FILES%', JSON.stringify(files)), 'utf8');
  const profileDir = join(checkDir, 'chrome-profile2');
  const chrome = spawn(CHROME, [
    '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
    '--allow-file-access-from-files', '--autoplay-policy=no-user-gesture-required',
    '--remote-debugging-port=' + PORT, '--user-data-dir=' + profileDir,
    'about:blank',
  ], { stdio: 'ignore', windowsHide: true });
  const cleanup = () => { try { chrome.kill(); } catch {} };
  try {
    let target = null;
    for (let i = 0; i < 60 && !target; i++) {
      await sleep(250);
      try {
        const list = await httpJson('http://127.0.0.1:' + PORT + '/json/list');
        target = list.find((t) => t.type === 'page');
      } catch { /* not ready */ }
    }
    if (!target) throw new Error('chrome devtools not ready');
    const ws = new WebSocket(target.webSocketDebuggerUrl);
    let nextId = 1;
    const pending = new Map();
    const send = (method, params = {}) => new Promise((res, rej) => {
      const id = nextId++;
      pending.set(id, { res, rej });
      ws.send(JSON.stringify({ id, method, params }));
    });
    await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.id && pending.has(msg.id)) {
        const { res, rej } = pending.get(msg.id);
        pending.delete(msg.id);
        if (msg.error) rej(new Error(JSON.stringify(msg.error)));
        else res(msg.result);
      }
    };
    const evalJs = async (expression, awaitPromise = false) => {
      const r = await send('Runtime.evaluate', { expression, awaitPromise, returnByValue: true });
      if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails).slice(0, 500));
      return r.result ? r.result.value : undefined;
    };
    await send('Page.enable');
    await send('Runtime.enable');
    await send('Page.navigate', { url: 'file:///' + pagePath.replace(/\\/g, '/') });
    for (let i = 0; i < 40; i++) {
      await sleep(250);
      try { if (await evalJs('typeof window.__run === "function"')) break; } catch {}
    }
    console.log('running checker for %d clips ...', files.length);
    const all = JSON.parse(await evalJs('window.__run().then((x) => JSON.stringify(x))', true));
    const results = [];
    const clipFail = [];
    const mediaFail = [];
    for (const item of all) {
      if (item.error) { mediaFail.push(item.file + ': ' + item.error); continue; }
      const fr = item.frames || [];
      if (!fr.length) { mediaFail.push(item.file + ': no frames'); continue; }
      const minX = Math.min(...fr.map((f) => f.bodyMinX));
      const minY = Math.min(...fr.map((f) => f.bodyMinY));
      const maxX = Math.max(...fr.map((f) => f.bodyMaxX));
      const maxY = Math.max(...fr.map((f) => f.bodyMaxY));
      const clip = { top: minY <= 1, bottom: maxY >= 358, left: minX <= 1, right: maxX >= 638 };
      const rec = { file: item.file, duration: item.duration, bodyBbox: { minX, minY, maxX, maxY }, clip, ok: !Object.values(clip).some(Boolean) };
      results.push(rec);
      if (!rec.ok) clipFail.push(rec);
    }
    const summary = {
      total: files.length, checked: results.length, pass: results.length - clipFail.length,
      clip_fail: clipFail.map((r) => ({ file: r.file, clip: r.clip, bbox: r.bbox })),
      media_fail: mediaFail, results,
    };
    mkdirSync(dirname(OUT), { recursive: true });
    writeFileSync(OUT, JSON.stringify(summary, null, 1), 'utf8');
    console.log('checked %d clips: pass=%d clip_fail=%d media_fail=%d', summary.checked, summary.pass, summary.clip_fail.length, mediaFail.length);
    for (const c of clipFail.slice(0, 12)) console.log('CLIP', c.file, JSON.stringify(c.bbox), JSON.stringify(c.clip));
    for (const m of mediaFail.slice(0, 8)) console.log('MEDIA', m);
    console.log('report:', OUT);
    cleanup();
    process.exit(mediaFail.length || clipFail.length ? 3 : 0);
  } catch (e) {
    cleanup();
    console.error('ERROR:', e.message);
    process.exit(2);
  }
}
main();
