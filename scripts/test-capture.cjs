// Static contracts only: no browser launch, tile fetch, or actual capture.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const read = name => fs.readFileSync(path.resolve(__dirname, '..', name), 'utf8');
const capture = read('scripts/capture.mjs');
const viewer = read('src/viewer.ts');
for (const marker of ['__idle', 'puppeteer-core', 'public/captures/index.json', '180000', "error.name === 'TimeoutError'", 'attempt < 2', "set('progress', '0.55')", "quality: 82", 'process.exitCode = 1']) assert.ok(capture.includes(marker), marker);
for (const marker of ['__idle = true', '__status = message', '__view = view', 'params.get("ui") === "0"', 'style.display = "none"', 'fixedProgress !== undefined', 'progress = fixedProgress; refresh()']) assert.ok(viewer.includes(marker), marker);
assert.match(viewer, /window\.addEventListener\("pageshow",\s*\(\) => \{[^}]*progress = fixedProgress \?\? -1;/, 'pageshow restores fixed URL progress');
assert.ok(read('compare.html').includes('./captures/index.json'));
console.log('PASS: capture static contracts (no capture or rendering claims)');
