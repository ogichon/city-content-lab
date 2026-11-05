/**
 * Capture the CURRENT worktree build, served locally before running this script:
 *   npx vite build && npx vite preview --port 4173
 * In another terminal:
 *   node scripts/capture.mjs <recipeId...> [--url-base http://127.0.0.1:4173] [--wait-extra 8000]
 * With no IDs, capture all public/recipes/index.json recipes. Idle is a loading
 * signal only; screenshots still require human review for rendering and quality.
 */
import puppeteer from 'puppeteer-core';
import { readFile, mkdir, writeFile, rename } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const root = new URL('../', import.meta.url);
const output = new URL('public/captures/', root);
const manifestPath = new URL('public/captures/index.json', root);

async function main() {
  let base = 'http://127.0.0.1:4173';
  let waitExtra = 8000;
  const ids = [];
  const args = process.argv.slice(2);
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--url-base' || arg === '--wait-extra') {
      const value = args[++i];
      if (!value || value.startsWith('--')) throw new Error(`Missing value for ${arg}`);
      if (arg === '--url-base') base = value;
      else {
        waitExtra = Number(value);
        if (!Number.isFinite(waitExtra) || waitExtra < 0 || waitExtra > 2147483647) throw new Error('Invalid --wait-extra');
      }
    } else if (arg.startsWith('--')) throw new Error(`Unknown option: ${arg}`);
    else ids.push(arg);
  }
  const baseURL = new URL(base.endsWith('/') ? base : `${base}/`);
  if (!['http:', 'https:'].includes(baseURL.protocol) || !['localhost', '127.0.0.1', '[::1]'].includes(baseURL.hostname)) {
    throw new Error('--url-base must point to a local preview of this worktree');
  }
  const { recipes } = JSON.parse(await readFile(new URL('public/recipes/index.json', root), 'utf8'));
  const selected = ids.length ? [...new Set(ids)].map(id => {
    const recipe = recipes.find(recipe => recipe.id === id);
    if (!recipe) throw new Error(`Unknown recipe: ${id}`);
    return recipe;
  }) : recipes;
  for (const recipe of selected) {
    if (!/^[a-zA-Z0-9_-]+$/.test(recipe.id)) throw new Error(`Unsafe recipe ID: ${recipe.id}`);
  }
  let entries;
  try { entries = JSON.parse(await readFile(manifestPath, 'utf8')); }
  catch (error) { if (error.code !== 'ENOENT') throw error; entries = []; }
  if (!Array.isArray(entries)) throw new Error('Capture manifest must be an array');
  const manifest = new Map(entries.map(entry => [entry.id, entry]));
  await mkdir(output, { recursive: true });
  const save = async () => {
    const temporary = new URL('index.json.tmp', output);
    await writeFile(temporary, JSON.stringify([...manifest.values()].sort((a, b) => a.id.localeCompare(b.id)), null, 2) + '\n');
    await rename(temporary, manifestPath);
  };
  const browser = await puppeteer.launch({
    executablePath: '/opt/meta-chromium/chrome', headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--window-size=1280,760'],
  });
  let failed = false;
  try {
    for (const recipe of selected) {
      console.log(`[${recipe.id}] starting`);
      let entry;
      for (let attempt = 0; attempt < 2; attempt++) {
        let page;
        try {
          page = await browser.newPage();
          await page.setViewport({ width: 1280, height: 760 });
          const url = new URL('viewer.html', baseURL);
          url.searchParams.set('recipe', recipe.id);
          url.searchParams.set('ui', '0');
          if (recipe.mode === 'growth') url.searchParams.set('progress', '0.55');
          await page.goto(url.href, { waitUntil: 'domcontentloaded', timeout: 180000 });
          await page.waitForFunction(() => window.__idle === true, { timeout: 180000 });
          await new Promise(resolve => setTimeout(resolve, waitExtra));
          const metadata = await page.evaluate(() => ({ status: window.__status ?? '', camera: document.getElementById('cam')?.textContent ?? null }));
          const file = `${recipe.id}.jpg`;
          const bytes = await page.screenshot({ path: fileURLToPath(new URL(file, output)), type: 'jpeg', quality: 82 });
          entry = { id: recipe.id, file, capturedAt: new Date().toISOString(), ...metadata, bytes: bytes.length };
          console.log(`[${recipe.id}] saved ${file} (${entry.bytes} bytes); ${entry.status}; ${entry.camera ?? 'camera unavailable'}`);
          break;
        } catch (error) {
          if (error.name === 'TimeoutError' && attempt === 0) {
            console.warn(`[${recipe.id}] timeout; retrying once`);
          } else {
            failed = true;
            entry = { id: recipe.id, capturedAt: new Date().toISOString(), error: String(error) };
            console.error(`[${recipe.id}] failed: ${error}`);
            break;
          }
        } finally { if (page) await page.close().catch(() => {}); }
      }
      manifest.set(recipe.id, entry);
      await save();
    }
  } finally { await browser.close(); }
  if (failed) process.exitCode = 1;
}
main().catch(error => { console.error(error); process.exitCode = 1; });
