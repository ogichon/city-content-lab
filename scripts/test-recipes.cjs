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
  const recipeBlock = block(/export const RECIPES: Recipe\[\] = \[([\s\S]*?)\n\];/, 'RECIPES');
  const recipes = [...recipeBlock.matchAll(/\{([^{}]*\bid:\s*"[^"]+"[^{}]*)\}/g)].map((match) => {
    const recipe = {};
    for (const field of match[1].matchAll(/(\w+):\s*("[^"]*"|[-+]?\d+(?:\.\d+)?|CODE_VERSION)/g)) {
      recipe[field[1]] = field[2] === 'CODE_VERSION' ? source.match(/export const CODE_VERSION = "([^"]+)"/)[1] : JSON.parse(field[2]);
    }
    return recipe;
  });
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
    check(`${name}: EXP-003 has six materials with fixed comparison intent and recorded time deviations`, () => {
      const comparison = list.filter(r => r.experiment === 'EXP-003');
      assert.equal(comparison.length, 6);
      assert.deepEqual(comparison.map(r => r.material).sort(), [...materials].sort());
      for (const r of comparison) {
        assert.equal(r.place, 'tokyo');
        assert.equal(r.mode, 'material');
        assert.equal(r.seed, comparison[0].seed);
        assert.equal(r.time, r.material === 'chrome' ? 'day' : r.material === 'crystal' ? 'night' : 'sunset');
      }
      const tokyo = block(/\btokyo:\s*\{([\s\S]*?)\n  \},/, 'tokyo place');
      const camera = tokyo.match(/camera:\s*\{([^}]+)\}/);
      assert.ok(camera, 'Tokyo must resolve a shared camera');
      for (const [key,value] of [['distance',520],['heading',55],['pitch',-48]]) {
        assert.ok(new RegExp(`\\b${key}:\\s*${value}(?=\\s*[,}])`).test(camera[1] + '}'), `Tokyo camera ${key} must be ${value}`);
      }
    });
  }
  check('Recipe fields mirror TypeScript definitions', () => {
    for (const r of manifest.recipes) {
      const original = recipes.find(candidate => candidate.id === r.id);
      for (const key of ['experiment','title','place','time','mode','material','growthOrder','seed']) assert.equal(r[key], original[key], `${r.id}.${key}`);
      assert.equal(manifest.codeVersion, original.codeVersion);
    }
  });
} catch (error) {
  failed++;
  console.error(`FAIL recipe input/extraction: ${error.message}`);
}
console.log(`Recipes: ${passed} PASS, ${failed} FAIL`);
process.exitCode = failed ? 1 : 0;
