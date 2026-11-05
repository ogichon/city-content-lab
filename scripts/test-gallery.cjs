const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const galleryDir = path.join(root, 'public/gallery');
const works = JSON.parse(fs.readFileSync(path.join(galleryDir, 'works.json'), 'utf8'));
assert.ok(Array.isArray(works), 'manifest is an array');
assert.equal(works.length, 5, 'exactly five candidates');
assert.equal(new Set(works.map(work => work.id)).size, 5, 'unique candidate IDs');
for (const work of works) {
  for (const key of ['id', 'title', 'file', 'experiment', 'technique', 'status', 'note']) {
    assert.equal(typeof work[key], 'string', `${work.id}: ${key} is a string`);
    assert.ok(work[key].trim(), `${work.id}: ${key} is not empty`);
  }
  assert.equal(work.status, 'candidate', `${work.id}: awaiting adoption`);
  assert.match(work.file, /^[a-z0-9-]+\.jpg$/, 'local JPEG filename');
  const file = path.resolve(galleryDir, work.file);
  assert.equal(path.dirname(file), galleryDir, 'image stays under public/gallery');
  const bytes = fs.readFileSync(file);
  assert.ok(bytes.length >= 2 && bytes[0] === 0xff && bytes[1] === 0xd8, `${work.file}: JPEG magic bytes`);
}
const html = fs.readFileSync(path.join(root, 'gallery.html'), 'utf8');
assert.ok(html.includes('採用候補（ユーザーの掲載判断待ち）'));
assert.ok(html.includes("fetch('./gallery/works.json')"));
assert.ok(html.includes('3D都市モデル: 国土交通省 PLATEAU.'));
assert.ok(html.includes('採用作品はまだありません。最初のPDCA（EXP-003）のユーザ評価後に掲載します'));
assert.ok(html.includes("image.loading = 'lazy'"));
assert.ok(html.includes('image.alt = work.title'));
assert.ok(html.includes("badge.textContent = '候補'"));
assert.ok(html.includes('候補作品を読み込めませんでした。'));
console.log('PASS: gallery manifest, five candidate JPEGs, and page static contracts');
