// Static contracts only. Never launch a browser or fetch tiles.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const read = name => fs.readFileSync(path.resolve(__dirname, '..', name), 'utf8');
const batch = read('src/batch.ts');
for (const marker of ["fetch('./recipes/index.json')", 'TIMEOUT_MS = 120_000', 'POLL_MS = 500', 'viewer().__idle !== true', 'SAMPLE_GAP_MS = 1500', 'const first = await rendered(sample', 'const second = await rendered', 'compareSamples(first, second.pixels)', 'stabilityMeanDiff) >= 2.0', 'backgroundFraction) >= 0.85', 'Math.abs(b[i] - 6) <= 12', 'Math.abs(b[i + 1] - 8) <= 12', 'Math.abs(b[i + 2] - 14) <= 12', "new Error('timeout')", "new Error('unstable')", "new Error('blank')", 'crcTable', 'function crc32', '0xedb88320', 'async function zipStore', '0x04034b50', '0x02014b50', '0x06054b50', 'lv.setUint16(8, 0, true)', 'cv.setUint16(10, 0, true)', "name: 'metadata.json'", "result: 'failed'", "result: 'success'", "canvas.toDataURL('image/png')", "url.searchParams.set('progress', '0.55')", "view.on('postRender', frame)", 'cameraText:', 'statusText:', 'idleWaitMs', 'capturedAt:', 'userAgent:', 'pageUrl:']) assert.ok(batch.includes(marker), marker);
const failure = batch.slice(batch.indexOf('  } catch (error) {\n    const reason'), batch.indexOf('// Minimal classic ZIP'));
assert.ok(failure.includes('entries.push('), 'failures recorded');
assert.ok(!failure.includes('images.push('), 'failures never store PNGs');
assert.ok(batch.indexOf('images.push(') > batch.indexOf("new Error('blank')"), 'image stored only after checks');
assert.match(read('vite.config.ts'), /batch:\s*"batch.html"/);
assert.match(read('package.json'), /test-capture.cjs && node scripts\/test-batch.cjs/);
const html = read('batch.html');
assert.match(html, /width="1280" height="760"/);
assert.match(html, /src="\/src\/batch.ts"/);
assert.match(read('index.html'), /href="batch.html">一括撮影/);
const recipes = JSON.parse(read('public/recipes/index.json')).recipes;
const defaults = recipes.filter(r => r.experiment === 'EXP-003' ? r.group === 'controlled' : ['EXP-001', 'EXP-002', 'EXP-004'].includes(r.experiment));
assert.equal(defaults.length, 16, '16 default recipes');
console.log('PASS: batch static contracts (no browser capture or rendering claims)');

// Exercise the actual pure implementations without a DOM or browser.
const vm = require('node:vm');
const { stripTypeScriptTypes } = require('node:module');
const pure = batch.slice(batch.indexOf('function compareSamples('), batch.indexOf('function pngBlob(')) + '\n' + batch.slice(batch.indexOf('const crcTable ='), batch.indexOf("runButton.addEventListener('click'"));
const context = vm.createContext({ Blob, TextEncoder, Uint8Array, Uint32Array, DataView, Math, Error });
vm.runInContext(stripTypeScriptTypes(pure) + '\nglobalThis.pure = { compareSamples, crc32, zipStore };', context);
(async () => {
  const { compareSamples, crc32, zipStore } = context.pure;
  assert.equal(crc32(new TextEncoder().encode('123456789')), 0xcbf43926, 'standard CRC32 vector');
  const bg = new Uint8ClampedArray([6, 8, 14, 255]);
  assert.equal(compareSamples(bg, bg).stabilityMeanDiff, 0);
  assert.equal(compareSamples(bg, bg).backgroundFraction, 1);
  const edge = new Uint8ClampedArray([18, 20, 26, 255]);
  assert.equal(compareSamples(bg, edge).backgroundFraction, 1, 'background tolerance inclusive');
  assert.equal(compareSamples(bg, new Uint8ClampedArray([19, 20, 26, 255])).backgroundFraction, 0);
  assert.equal(compareSamples(bg, new Uint8ClampedArray([8, 10, 16, 255])).stabilityMeanDiff, 2, 'RGB mean difference');
  const bytes = new Uint8Array(await (await zipStore([{ name: 'metadata.json', blob: new Blob(['{}']) }])).arrayBuffer());
  const view = new DataView(bytes.buffer);
  assert.equal(view.getUint32(0, true), 0x04034b50);
  assert.equal(view.getUint16(8, true), 0, 'STORE');
  const nameLength = view.getUint16(26, true);
  const size = view.getUint32(18, true);
  const payload = bytes.slice(30 + nameLength, 30 + nameLength + size);
  assert.equal(view.getUint32(14, true), crc32(payload), 'payload CRC');
  const central = 30 + nameLength + size;
  assert.equal(view.getUint32(central, true), 0x02014b50);
  assert.equal(view.getUint32(central + 42, true), 0, 'local offset');
  assert.equal(view.getUint32(bytes.length - 22, true), 0x06054b50);
  assert.equal(view.getUint16(bytes.length - 12, true), 1, 'entry count');
  console.log('PASS: actual batch pixel metrics, CRC32 vector and ZIP STORE structure');
})().catch(error => { console.error(error); process.exitCode = 1; });
// PR #11 review fix: resumed-loading defenses
assert.match(batch, /confirmMeanDiff/, 'third-sample confirmation recorded');
assert.match(batch, /delay\(2500\)/, 'confirmation sample uses a longer gap');
assert.match(read('src/viewer.ts'), /__idle = false/, 'viewer clears __idle when loading resumes');
