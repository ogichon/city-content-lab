const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'public/recipes/index.json'), 'utf8'));
const pages = ['index.html', 'compare.html', 'gallery.html'];
const sources = pages.map(name => fs.readFileSync(path.join(root, name), 'utf8'));
for (const [index, html] of sources.entries()) {
  assert.match(html, /<html lang="ja">/);
  for (const credit of ['PLATEAU', 'MLIT', 'GSI', 'Re:Earth Terrain']) assert.ok(html.includes(credit), `${pages[index]}: ${credit}`);
  for (const [, href] of html.matchAll(/href="([^"]+)"/g)) {
    if (/^https:\/\//.test(href)) continue;
    const [file, hash] = href.split('#');
    assert.ok(fs.existsSync(path.join(root, file)), `${pages[index]}: missing ${file}`);
    if (hash) assert.ok(manifest.recipes.some(r => r.experiment === hash), `Unknown experiment ${hash}`);
  }
}
const script = sources[1].match(/<script type="module">([\s\S]*?)<\/script>/)[1];
new vm.SourceTextModule(script); // Parse as a browser module, including top-level await.
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.textContent = ''; this.style = {}; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  scrollIntoView() { this.scrolled = true; }
}
async function render(ok, captures = null) {
  const container = new Element('div');
  const status = new Element('p');
  let fragment;
  const context = {
    document: {
      querySelector: selector => selector === '#experiments' ? container : status,
      createElement: tag => new Element(tag),
      createDocumentFragment: () => (fragment = new Element('fragment')),
      getElementById: id => fragment?.children.find(child => child.id === id),
    },
    location: {hash:'#EXP-003'},
    fetch: async url => {
      if (url === './captures/index.json') {
        if (captures === null) throw new Error('Missing capture manifest');
        return {ok: true, json: async () => captures};
      }
      assert.equal(url, './recipes/index.json');
      return {ok, status:503, json:async () => manifest};
    },
    console: {error() {}}, encodeURIComponent, decodeURIComponent,
  };
  await vm.runInNewContext(`(async () => {${script}\n})()`, context);
  return {container, status, fragment};
}
(async () => {
  const {container, status, fragment} = await render(true);
  assert.equal(container.children[0], fragment);
  assert.equal(fragment.children.length, 3);
  const walk = node => [node, ...node.children.flatMap(walk)];
  const nodes = walk(fragment);
  const links = nodes.filter(node => node.tag === 'a');
  assert.deepEqual(links.map(node => node.href).sort(), manifest.recipes.map(r => `viewer.html?recipe=${encodeURIComponent(r.id)}`).sort());
  // viewer.html is intentionally supplied by Codex A, never fabricated here.
  assert.equal(nodes.filter(n => n.className === 'thumbnail').length, manifest.recipes.length);
  assert.ok(nodes.filter(n => n.className === 'thumbnail').every(n => n.textContent === '目視確認待ち — サムネイルはユーザーのChrome確認後に差し替え'));
  assert.ok(fragment.children.find(n => n.id === 'EXP-003').scrolled);
  assert.match(status.textContent, /12案/);
  const captured = await render(true, [{id: manifest.recipes[0].id, file: `${manifest.recipes[0].id}.jpg`}]);
  const images = walk(captured.fragment).filter(node => node.tag === 'img');
  assert.equal(images.length, 1);
  assert.equal(images[0].src, `./captures/${manifest.recipes[0].id}.jpg`);
  assert.equal(images[0].alt, manifest.recipes[0].title);
  const capturedLink = walk(captured.fragment).find(node => node.children.includes(images[0]));
  assert.equal(capturedLink.href, `viewer.html?recipe=${manifest.recipes[0].id}`);
  const failure = await render(false);
  assert.match(failure.status.textContent, /読み込めませんでした/);
  console.log('PASS: three HTML pages, local links, attributions, module syntax, 12 recipe cards, expected viewer links, deep links, and fetch error state');
})().catch(error => { console.error('FAIL:', error); process.exitCode = 1; });
