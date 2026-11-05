const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
let passed = 0;
let failed = 0;
function check(name, fn) {
  try { fn(); passed++; console.log(`PASS ${name}`); }
  catch (error) { failed++; console.error(`FAIL ${name}: ${error.message}`); }
}
try {
  const source = fs.readFileSync(path.join(root, 'src/recipes.ts'), 'utf8');
  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'public/recipes/index.json'), 'utf8'));
  const block = (pattern, name) => {
    const match = source.match(pattern);
    assert.ok(match, `Could not extract ${name}`);
    return match[1];
  };
  const { stripTypeScriptTypes } = require('node:module');
  const vm = require('node:vm');
  const actual = vm.runInNewContext(stripTypeScriptTypes(source).replaceAll('export ', '') + '\n({RECIPES, PLACES, effectiveCamera});');
  const recipes = JSON.parse(JSON.stringify(actual.RECIPES));
  const materials = [...block(/export const MATERIALS:[^=]+=[ \t]*\{([\s\S]*?)\n\};/, 'MATERIALS').matchAll(/^  (\w+):\s*\{/gm)].map(m => m[1]);
  const orders = [...block(/export type GrowthOrder = ([^;]+);/, 'GrowthOrder').matchAll(/"([^"]+)"/g)].map(m => m[1]);
  const ids = list => list.map(r => r.id).sort();
  check('IDs match exactly in both directions, without duplicates', () => {
    assert.ok(recipes.length > 0);
    assert.deepEqual(ids(manifest.recipes), ids(recipes));
    for (const list of [manifest.recipes, recipes]) assert.equal(new Set(ids(list)).size, list.length);
  });
  for (const [name, list] of [['JSON',manifest.recipes],['TypeScript',recipes]]) {
    check(`${name}: every material exists in MATERIALS`, () => {
      assert.ok(materials.length > 0);
      for (const r of list) {
        if (r.mode === 'material') assert.ok(r.material, `${r.id}: missing material`);
        if (r.material !== undefined) assert.ok(materials.includes(r.material), `${r.id}: unknown material ${r.material}`);
      }
    });
    check(`${name}: every growth order exists`, () => {
      assert.ok(orders.length > 0);
      for (const r of list) {
        if (r.mode === 'growth') assert.ok(r.growthOrder, `${r.id}: missing growthOrder`);
        if (r.growthOrder !== undefined) assert.ok(orders.includes(r.growthOrder), `${r.id}: unknown growthOrder`);
      }
    });
    check(`${name}: seeds are finite numbers`, () => {
      for (const r of list) assert.ok(typeof r.seed === 'number' && Number.isFinite(r.seed), `${r.id}: invalid seed`);
    });
    check(`${name}: EXP-003 has six materials with fixed comparison intent and Controlled conditions`, () => {
      const comparison = list.filter(r => r.experiment === 'EXP-003' && r.group === 'controlled');
      assert.equal(comparison.length, 6);
      assert.deepEqual(comparison.map(r => r.material).sort(), [...materials].sort());
      for (const r of comparison) {
        assert.equal(r.place, 'tokyo');
        assert.equal(r.mode, 'material');
        assert.equal(r.seed, comparison[0].seed);
        assert.equal(r.time, 'sunset');
        assert.equal(r.cameraOverride, undefined);
      }
      const tokyo = block(/\btokyo:\s*\{([\s\S]*?)\n  \},/, 'tokyo place');
      const camera = tokyo.match(/camera:\s*\{([^}]+)\}/);
      assert.ok(camera, 'Tokyo must resolve a shared camera');
      for (const [key,value] of [['distance',520],['heading',55],['pitch',-48]]) {
        assert.ok(new RegExp(`\\b${key}:\\s*${value}(?=\\s*[,}])`).test(camera[1] + '}'), `Tokyo camera ${key} must be ${value}`);
      }
    });
  }
  for (const [name, list] of [['JSON', manifest.recipes], ['TypeScript', recipes]]) {
    check(`${name}: 22 recipes and six Best Look lighting presets`, () => {
      assert.equal(list.length, 22);
      const best = list.filter(r => r.experiment === 'EXP-003' && r.group === 'best');
      assert.equal(best.length, 6);
      assert.deepEqual(best.map(r => r.material).sort(), [...materials].sort());
      for (const r of best) {
        assert.equal(r.id, `exp003-best-${r.material}`);
        assert.equal(r.place, 'tokyo');
        assert.equal(r.mode, 'material');
        assert.equal(r.cameraOverride, undefined);
        assert.equal(r.time, ({porcelain:'sunset', gold:'sunset', chrome:'day', ice:'day', glass:'day', crystal:'night'})[r.material]);
      }
    });
    check(`${name}: all four growth orders share Tokyo`, () => {
      const growth = list.filter(r => r.experiment === 'EXP-002');
      assert.equal(growth.length, 4);
      assert.deepEqual(growth.map(r => r.growthOrder).sort(), [...orders].sort());
      for (const r of growth) {
        assert.equal(r.place, 'tokyo');
        assert.equal(r.cameraOverride, undefined);
      }
    });
    check(`${name}: four controlled camera recipes with three overrides`, () => {
      const cameras = list.filter(r => r.experiment === 'EXP-004');
      assert.equal(cameras.length, 4);
      assert.equal(cameras.filter(r => r.cameraOverride).length, 3);
      const expected = {'exp004-standard': undefined, 'exp004-low-angle': {distance:380,pitch:-18}, 'exp004-top-down': {distance:700,pitch:-85}, 'exp004-diorama': {distance:900,pitch:-55}};
      assert.deepEqual(ids(cameras), Object.keys(expected).sort());
      for (const r of cameras) {
        assert.equal(r.place, 'tokyo');
        assert.equal(r.time, 'sunset');
        assert.equal(r.mode, 'material');
        assert.equal(r.material, 'gold');
        assert.equal(r.group, 'controlled');
        assert.deepEqual(r.cameraOverride, expected[r.id]);
      }
    });
  }
  check('effectiveCamera inherits defaults without mutating the shared place', () => {
    const before = JSON.stringify(actual.PLACES);
    for (const r of recipes) {
      const camera = actual.effectiveCamera(r);
      assert.deepEqual(JSON.parse(JSON.stringify(camera)), {...actual.PLACES[r.place].camera, ...r.cameraOverride});
      camera.distance = 0;
    }
    assert.equal(JSON.stringify(actual.PLACES), before);
  });
  check('Recipe fields mirror TypeScript definitions', () => {
    for (const r of manifest.recipes) {
      const original = recipes.find(candidate => candidate.id === r.id);
      assert.deepEqual(r, original, `${r.id}: all fields must match`);
      assert.equal(manifest.codeVersion, original.codeVersion);
    }
  });
} catch (error) {
  failed++;
  console.error(`FAIL recipe input/extraction: ${error.message}`);
}
console.log(`Recipes: ${passed} PASS, ${failed} FAIL`);
process.exitCode = failed ? 1 : 0;
