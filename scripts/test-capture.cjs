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
// Capture must also be enabled from the idle handler (mid-setup errors can
// otherwise leave it disabled forever — observed in managed-browser check).
// Bounded check: the enabling must occur INSIDE the idle handler window,
// not merely somewhere later in the file (review PR #13).
const idleAt = viewer.indexOf('on("idle"');
assert.ok(idleAt >= 0, 'idle handler exists');
const idleWindow = viewer.slice(idleAt, idleAt + 600);
assert.ok(idleWindow.includes('getElementById("capture")') && idleWindow.includes('.disabled = false'), 'idle handler enables capture');
