// Static contract tests: these do not establish browser rendering or visual quality.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const read = name => fs.readFileSync(path.join(root, name), 'utf8');
const recipes = read('src/recipes.ts');
const viewer = read('src/viewer.ts');
const html = read('viewer.html');
const manifest = JSON.parse(read('public/recipes/index.json'));
// Inspect source contracts without maintaining a second copy of the rank algorithm.
assert.ok(recipes.includes('export function seededRank('));
for (const marker of ['featureCreated', 'featureRemoved', 'evaluators.delete(featureSetId)', 'pageshow', 'pagehide', '歴史的再現ではありません', 'LIFT-LITE（地形切断なし）', '12000', 'seededRank(recipe.seed, x, y)', 'postRender']) assert.ok(viewer.includes(marker), marker);
for (const order of ['center-out', 'low-to-high', 'random', 'giants-last']) {
  assert.ok(viewer.includes(`case "${order}"`), order);
  assert.ok(recipes.includes(`"${order}"`), order);
}
for (const item of manifest.recipes) {
  assert.ok(recipes.includes(`id: "${item.id}"`), item.id);
  if (item.material) assert.ok(recipes.includes(`  ${item.material}: {`), item.material);
}
const ids = recipes.split('id: "').slice(1).map(s => s.slice(0, s.indexOf('"')));
assert.deepEqual(ids.slice().sort(), manifest.recipes.map(r => r.id).sort());
assert.ok(viewer.includes('MATERIALS[recipe.material]'));
// Regression: parent-tile visibility must not block per-feature growth reveal.
const layerModel = viewer.slice(viewer.indexOf('const layer = view.addLayer'), viewer.indexOf('const applyFeature'));
assert.match(viewer, /id: "ccl-bloom", selectiveBloom:/);
assert.match(layerModel, /model: \{[\s\S]*effectIds: \["ccl-bloom"\]/);
assert.ok(layerModel.includes('...(recipe.mode === "material" && recipe.material && MATERIALS[recipe.material].opacity < 1 ? { transparent: true } : {})'));
assert.ok(!layerModel.includes('show:'));
for (const field of ['metalness', 'roughness']) assert.ok(layerModel.includes(`MATERIALS[recipe.material].${field}`));
for (const id of ['app', 'recipe-title', 'note', 'play', 'reset', 'capture', 'status', 'cam', 'recipes', 'ground-attribution']) assert.ok(html.includes(`id="${id}"`), id);
console.log('PASS: viewer static contract tests (no rendering claims)');
// Node 24 can strip TS without dependencies. Evaluate the real recipe module,
// keeping the hash implementation solely in src/recipes.ts.
const { stripTypeScriptTypes } = require('node:module');
const code = stripTypeScriptTypes(recipes).split('export ').join('');
const actual = vm.runInNewContext(`${code}\n({seededRank, RECIPES, getRecipe});`);
for (let seed = -5; seed < 10; seed++) {
  for (const [x, y] of [[139.7671,35.6812], [0,0], [-180,-90], [180,90]]) {
    const a = actual.seededRank(seed,x,y);
    assert.equal(a, actual.seededRank(seed,x,y));
    assert.ok(a >= 0 && a <= 1 && Number.isFinite(a));
  }
}
assert.equal(actual.getRecipe(null).id, actual.RECIPES[0].id);
assert.equal(actual.getRecipe('unknown').id, actual.RECIPES[0].id);
assert.ok(new Set(Array.from({length:10}, (_, i) => actual.seededRank(i,139,35))).size > 1);
console.log('PASS: actual seededRank determinism/range and recipe fallback logic');

// Execute the real timeline implementation: camera semantics, easing, loop/hold.
const stageCode = stripTypeScriptTypes(read('src/stage.ts')).replace(/^import .*;$/m, '').replaceAll('export ', '');
const recipeCode = stripTypeScriptTypes(recipes).replaceAll('export ', '');
const timeline = vm.runInNewContext(recipeCode + '\n' + stageCode + '\n({stageFrame, RECIPES, PLACES});');
const performances = timeline.RECIPES.filter(r => r.performance);
assert.equal(performances.length, 4);
for (const recipe of performances.filter(r => r.performance.progressCurve !== 'tide')) {
  assert.equal(recipe.performance.shots.length, 3);
  const total = recipe.performance.shots.reduce((n, shot) => {
    assert.ok(Number.isFinite(shot.durationSec) && shot.durationSec > 0);
    for (const value of Object.values(shot.camera)) assert.ok(Number.isFinite(value));
    return n + shot.durationSec;
  }, 0);
  assert.ok(total >= 18 && total <= 30);
  assert.equal(timeline.stageFrame(recipe, total + 1).progress, 1 / total);
  const once = {...recipe, performance: {...recipe.performance, loop: false}};
  const end = timeline.stageFrame(once, total + 10);
  assert.equal(end.playing, false); assert.equal(end.progress, 1); assert.equal(end.shotIndex, 2);
  assert.equal(JSON.stringify(end), JSON.stringify(timeline.stageFrame(once, total + 100)));
}
const tide = performances.find(r => r.id === 'exp021-breath-core');
assert.ok(tide);
assert.equal(tide.performance.shots.length, 2);
const tideTotal = tide.performance.shots.reduce((sum, shot) => sum + shot.durationSec, 0);
assert.equal(tideTotal, 48);
assert.equal(timeline.stageFrame(tide, 0).progress, 0);
assert.equal(timeline.stageFrame(tide, tideTotal / 2).progress, 1);
assert.ok(Math.abs(timeline.stageFrame(tide, tideTotal).progress) < 1e-12);
let previous = 0;
for (let elapsed = 1; elapsed <= tideTotal; elapsed++) {
  const progress = timeline.stageFrame(tide, elapsed).progress;
  assert.ok(elapsed <= tideTotal / 2 ? progress >= previous : progress <= previous);
  previous = progress;
}
const tideOnce = {...tide, performance: {...tide.performance, loop: false}};
const tideEnd = timeline.stageFrame(tideOnce, tideTotal);
assert.equal(tideEnd.progress, 0);
assert.equal(tideEnd.playing, false);
assert.equal(JSON.stringify(tideEnd), JSON.stringify(timeline.stageFrame(tideOnce, tideTotal + 100)));
const linear = {...tide, performance: {...tide.performance, progressCurve: 'linear'}};
const defaultLinear = {...tide, performance: {...tide.performance, progressCurve: undefined}};
for (const elapsed of [0, 12, 24, 36, 48, 49]) {
  assert.equal(timeline.stageFrame(linear, elapsed).progress, (elapsed % tideTotal) / tideTotal);
  assert.equal(JSON.stringify(timeline.stageFrame(linear, elapsed)), JSON.stringify(timeline.stageFrame(defaultLinear, elapsed)));
}
for (const elapsed of [0, 12, 24, 36, 48]) {
  const frame = timeline.stageFrame(tide, elapsed);
  assert.equal(JSON.stringify(frame.camera), JSON.stringify(timeline.stageFrame(linear, elapsed).camera));
  assert.equal(frame.camera.lng, 139.7585);
  assert.equal(frame.camera.lat, 35.6858);
}
console.log('PASS: tide rise/fall, loop wrap, single-pass hold, linear default and shot lng/lat overrides');
const base = timeline.PLACES.tokyo.camera;
const sample = {place:'tokyo', mode:'standard', cameraOverride:{heading:350}, performance:{shots:[{camera:{heading:10,distance:720},durationSec:10}]}};
const middle = timeline.stageFrame(sample,5);
assert.equal(middle.camera.heading,0); assert.equal(middle.camera.distance,(base.distance+720)/2);
assert.equal(middle.camera.lng,base.lng); assert.equal(middle.camera.lat,base.lat);
assert.equal(timeline.stageFrame(sample,10).camera.heading,10);
sample.performance.shots[0].ease = 'out';
assert.ok(timeline.stageFrame(sample,5).camera.distance > middle.camera.distance);
assert.ok(viewer.includes('stage && stageReady && !stageStarted'));
assert.ok(viewer.includes('view.setCamera(frame.camera)'));
console.log('PASS: stage definitions, interpolation, heading wrap, easing, loop and final hold');
assert.ok(viewer.includes('transmittance: false'), 'stage disables aerial-perspective transmittance');
assert.ok(viewer.includes('lit: false'), 'stage runs terrain unlit');
assert.ok(viewer.includes('hazeDensityScale: 0'), 'stage zeroes cloud haze density');
assert.ok(viewer.includes('stage-probe') && viewer.includes('sampleProbe'), 'stage luminance probe present');
console.log('PASS: EXP-016 stage grade (unlit ground, no transmittance, no haze) + luminance probe');
