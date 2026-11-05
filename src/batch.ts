import type { Recipe } from './recipes';

type ViewerWindow = Window & { __idle?: boolean; __status?: string; __view?: {
  on(event: string, handler: () => void): void;
  off(event: string, handler: () => void): void;
  forceUpdate(): void;
} };
type Entry = Record<string, unknown> & { id: string; result: 'success' | 'failed' };
const iframe = document.querySelector<HTMLIFrameElement>('#viewer')!;
const runButton = document.querySelector<HTMLButtonElement>('#run')!;
const downloadButton = document.querySelector<HTMLButtonElement>('#download')!;
const choices = document.querySelector<HTMLDivElement>('#choices')!;
const summary = document.querySelector<HTMLParagraphElement>('#summary')!;
const results = document.querySelector<HTMLOListElement>('#results')!;
const TIMEOUT_MS = 120_000;
const POLL_MS = 500;
const SAMPLE_GAP_MS = 1500;
const delay = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms));
let recipes: Recipe[] = [];
let entries: Entry[] = [];
let images: { name: string; blob: Blob }[] = [];
let runInfo: { startedAt: string; userAgent: string; pageUrl: string };

function resizeStage() {
  const stage = document.querySelector<HTMLDivElement>('#stage')!;
  const scale = Math.min(1, stage.clientWidth / 1280);
  iframe.style.transform = `scale(${scale})`;
  stage.style.height = `${760 * scale}px`;
}
new ResizeObserver(resizeStage).observe(document.querySelector('#stage')!);
resizeStage();
function selected() {
  const ids = new Set(Array.from(choices.querySelectorAll<HTMLInputElement>('input:checked'), input => input.value));
  return recipes.filter(recipe => ids.has(recipe.id));
}
function updateCount() {
  const count = selected().length;
  document.querySelector('#count')!.textContent = `${count} / ${recipes.length} レシピ選択`;
  runButton.disabled = count === 0;
}
function viewer() { return iframe.contentWindow as ViewerWindow; }

// Read inside postRender: WebGL's drawing buffer may be cleared after presentation.
function rendered<T>(read: (canvas: HTMLCanvasElement) => T, deadline: number): Promise<T> {
  return new Promise((resolve, reject) => {
    const win = viewer();
    const view = win.__view;
    if (!view) { reject(new Error('canvas-unavailable')); return; }
    const timeout = setTimeout(() => { view.off('postRender', frame); reject(new Error('timeout')); }, Math.max(0, deadline - performance.now()));
    const frame = () => {
      clearTimeout(timeout);
      view.off('postRender', frame);
      try {
        const canvas = win.document.querySelector<HTMLCanvasElement>('#app canvas');
        if (!canvas || !canvas.width || !canvas.height) throw new Error('canvas-unavailable');
        resolve(read(canvas));
      } catch (error) { reject(error); }
    };
    try { view.on('postRender', frame); view.forceUpdate(); }
    catch (error) { clearTimeout(timeout); view.off('postRender', frame); reject(error); }
  });
}
function sample(canvas: HTMLCanvasElement) {
  const small = document.createElement('canvas'); small.width = 64; small.height = 38;
  const ctx = small.getContext('2d', { willReadFrequently: true })!;
  ctx.drawImage(canvas, 0, 0, 64, 38);
  return ctx.getImageData(0, 0, 64, 38).data;
}
function compareSamples(a: Uint8ClampedArray, b: Uint8ClampedArray) {
  let difference = 0, background = 0;
  for (let i = 0; i < b.length; i += 4) {
    for (let c = 0; c < 3; c++) difference += Math.abs(a[i + c] - b[i + c]);
    if (Math.abs(b[i] - 6) <= 12 && Math.abs(b[i + 1] - 8) <= 12 && Math.abs(b[i + 2] - 14) <= 12) background++;
  }
  return { stabilityMeanDiff: difference / (b.length / 4 * 3), backgroundFraction: background / (b.length / 4) };
}
function pngBlob(dataUrl: string) {
  const bytes = Uint8Array.from(atob(dataUrl.split(',')[1]), c => c.charCodeAt(0));
  return new Blob([bytes], { type: 'image/png' });
}
async function capture(recipe: Recipe, row: HTMLLIElement) {
  const started = performance.now();
  const deadline = started + TIMEOUT_MS;
  const measured: Record<string, unknown> = {};
  try {
    row.textContent = `${recipe.id} — 読込中`;
    const url = new URL('viewer.html', location.href);
    url.searchParams.set('recipe', recipe.id); url.searchParams.set('ui', '0');
    if (recipe.mode === 'growth') url.searchParams.set('progress', '0.55');
    // Await navigation first so the previous recipe's idle flag cannot pass.
    await new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => { iframe.onload = null; reject(new Error('timeout')); }, TIMEOUT_MS);
      iframe.onload = () => { clearTimeout(timeout); iframe.onload = null; resolve(); };
      iframe.src = url.href;
    });
    while (viewer().__idle !== true) {
      if (performance.now() >= deadline) throw new Error('timeout');
      await delay(Math.min(POLL_MS, deadline - performance.now()));
    }
    measured.idleWaitMs = Math.round(performance.now() - started);
    // LIFT starts orbiting automatically. Stop it before the stability samples.
    const play = viewer().document.querySelector<HTMLButtonElement>('#play');
    if (play?.getAttribute('aria-pressed') === 'true') play.click();
    row.textContent = `${recipe.id} — 安定確認中`;
    const first = await rendered(sample, deadline);
    await delay(SAMPLE_GAP_MS);
    const second = await rendered(canvas => ({ pixels: sample(canvas), dataUrl: canvas.toDataURL('image/png'), w: canvas.width, h: canvas.height }), deadline);
    Object.assign(measured, compareSamples(first, second.pixels));
    if (performance.now() >= deadline) throw new Error('timeout');
    if (viewer().__idle !== true || Number(measured.stabilityMeanDiff) >= 2.0) throw new Error('unstable');
    if (Number(measured.backgroundFraction) >= 0.85) throw new Error('blank');
    const blob = pngBlob(second.dataUrl);
    entries.push({ ...recipe, group: recipe.group ?? null, material: recipe.material ?? null, growthOrder: recipe.growthOrder ?? null, result: 'success', cameraText: viewer().document.querySelector('#cam')?.textContent ?? '', statusText: viewer().__status ?? '', ...measured, capturedAt: new Date().toISOString(), canvas: { w: second.w, h: second.h } });
    images.push({ name: `${recipe.id}.png`, blob });
    row.textContent = `${recipe.id} — 成功`;
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    entries.push({ id: recipe.id, result: 'failed', reason, statusText: viewer()?.__status ?? '', ...measured });
    row.textContent = `${recipe.id} — 失敗: ${reason}`;
  }
}

// Minimal classic ZIP writer: CRC32, UTF-8 filenames, STORE (method 0), no dependencies.
const crcTable = Uint32Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});
function crc32(bytes: Uint8Array) {
  let crc = 0xffffffff;
  for (const byte of bytes) crc = crcTable[(crc ^ byte) & 255] ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
}
async function zipStore(files: { name: string; blob: Blob }[]) {
  const locals: BlobPart[] = [], central: BlobPart[] = [];
  let offset = 0, centralSize = 0;
  for (const file of files) {
    const name = new TextEncoder().encode(file.name);
    const bytes = new Uint8Array(await file.blob.arrayBuffer());
    const crc = crc32(bytes);
    if (offset + bytes.length + name.length + 30 > 0xffffffff) throw new Error('ZIP size limit');
    const local = new Uint8Array(30), lv = new DataView(local.buffer);
    lv.setUint32(0, 0x04034b50, true); lv.setUint16(4, 20, true); lv.setUint16(6, 0x800, true);
    lv.setUint16(8, 0, true); lv.setUint16(12, 33, true); // STORE, 1980-01-01
    lv.setUint32(14, crc, true); lv.setUint32(18, bytes.length, true); lv.setUint32(22, bytes.length, true); lv.setUint16(26, name.length, true);
    locals.push(local, name, bytes);
    const header = new Uint8Array(46), cv = new DataView(header.buffer);
    cv.setUint32(0, 0x02014b50, true); cv.setUint16(4, 20, true); cv.setUint16(6, 20, true); cv.setUint16(8, 0x800, true);
    cv.setUint16(10, 0, true); cv.setUint16(14, 33, true); cv.setUint32(16, crc, true); cv.setUint32(20, bytes.length, true); cv.setUint32(24, bytes.length, true); cv.setUint16(28, name.length, true); cv.setUint32(42, offset, true);
    central.push(header, name); centralSize += header.length + name.length;
    offset += local.length + name.length + bytes.length;
  }
  if (files.length > 65535 || offset + centralSize > 0xffffffff) throw new Error('ZIP size limit');
  const end = new Uint8Array(22), ev = new DataView(end.buffer);
  ev.setUint32(0, 0x06054b50, true); ev.setUint16(8, files.length, true); ev.setUint16(10, files.length, true); ev.setUint32(12, centralSize, true); ev.setUint32(16, offset, true);
  return new Blob([...locals, ...central, end], { type: 'application/zip' });
}
runButton.addEventListener('click', async () => {
  const queue = selected();
  runButton.disabled = downloadButton.disabled = true;
  choices.querySelectorAll('input').forEach(input => { input.disabled = true; });
  entries = []; images = []; results.replaceChildren();
  runInfo = { startedAt: new Date().toISOString(), userAgent: navigator.userAgent, pageUrl: location.href };
  const rows = queue.map(recipe => { const row = document.createElement('li'); row.textContent = `${recipe.id} — 待機`; results.append(row); return row; });
  for (const [index, recipe] of queue.entries()) {
    summary.textContent = `${index + 1} / ${queue.length} 処理中`;
    await capture(recipe, rows[index]);
  }
  iframe.src = 'about:blank';
  summary.textContent = `完了: 成功 ${images.length} / 失敗 ${entries.length - images.length} / 全 ${queue.length}`;
  choices.querySelectorAll('input').forEach(input => { input.disabled = false; });
  updateCount(); downloadButton.disabled = false;
});
downloadButton.addEventListener('click', async () => {
  downloadButton.disabled = true;
  try {
    const metadata = new Blob([JSON.stringify({ ...runInfo, entries }, null, 2)], { type: 'application/json' });
    const zip = await zipStore([...images, { name: 'metadata.json', blob: metadata }]);
    const url = URL.createObjectURL(zip), link = document.createElement('a');
    const stamp = runInfo.startedAt.replace(/[-:]/g, '').replace('T', '-').slice(0, 13);
    link.href = url; link.download = `city-content-lab-captures-${stamp}.zip`;
    document.body.append(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  } catch (error) { summary.textContent = `ZIP作成失敗: ${error}`; }
  finally { downloadButton.disabled = false; }
});
async function main() {
  const response = await fetch('./recipes/index.json');
  if (!response.ok) throw new Error(`レシピ取得失敗: ${response.status}`);
  recipes = (await response.json()).recipes;
  const groups = new Map<string, HTMLFieldSetElement>();
  for (const recipe of recipes) {
    const key = `${recipe.experiment}${recipe.group ? ` / ${recipe.group}` : ''}`;
    let fieldset = groups.get(key);
    if (!fieldset) {
      fieldset = document.createElement('fieldset');
      const legend = document.createElement('legend'); legend.textContent = key;
      fieldset.append(legend); choices.append(fieldset); groups.set(key, fieldset);
    }
    const label = document.createElement('label'), input = document.createElement('input');
    input.type = 'checkbox'; input.value = recipe.id;
    input.checked = recipe.experiment === 'EXP-003' ? recipe.group === 'controlled' : ['EXP-001', 'EXP-002', 'EXP-004'].includes(recipe.experiment);
    input.addEventListener('change', updateCount);
    label.append(input, ` ${recipe.title} (${recipe.id})`); fieldset.append(label);
  }
  updateCount();
}
main().catch(error => { document.querySelector('#count')!.textContent = String(error); });
