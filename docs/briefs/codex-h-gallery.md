# Brief — Codex H: ギャラリー候補セクション

Worktree: ~/workspace/ccl-wt-gallery, branch feat/gallery-candidates. Read AGENTS.md first. Do NOT commit (Muse commits). Four web images are already placed in `public/gallery/` (do not modify them):
- hero-tokyo-station-gold.jpg / hero-tocho-gold.jpg / specimen-yaesu-block.jpg / lift-skytree-context.jpg

## Deliverables
1. `public/gallery/works.json` — manifest array of 4 objects with fields {id, title, file, experiment, technique, status, note}:
   - id "hero-tokyo-station-gold", title "金の東京駅", experiment "EXP-003/005", technique "Blender ヒーロー素材（地=磁器、駅舎=金）", status "candidate", note "素材比較から生まれた最有力作。白い街に金の駅舎が浮く。"
   - id "hero-tocho-gold", title "金の都庁", experiment "EXP-005", technique "Blender ヒーロー素材（地=磁器、都庁舎=金）", status "candidate", note "双塔のノッチが金で際立つ。シリーズ2作目。"
   - id "specimen-yaesu-block", title "都市標本・八重洲", experiment "EXP-006", technique "Blender 切断+void 孤立", status "candidate", note "街区を台座ごと虚空へ。清潔なジオラマ標本。"
   - id "lift-skytree-context", title "浮く街区・スカイツリーの足元", experiment "EXP-006", technique "Blender 切断リフト（in-context）", status "candidate", note "タワーの足元の街区が剥がれて浮く。ピットと下面が見える。"
   All status values must be exactly "candidate" — nothing here is an adopted work yet.
2. `gallery.html` — keep the existing adopted-works area and its honest empty state. Add a section 「採用候補（ユーザーの掲載判断待ち）」 that fetches `./gallery/works.json` and renders each entry: image (loading="lazy", alt=title), title, technique + experiment line, note, and a visible 「候補」 badge. On fetch failure show a plain fallback sentence. Include a data credit line: 3D都市モデル: 国土交通省 PLATEAU.
3. `scripts/test-gallery.cjs` — static/data tests: works.json parses; exactly 4 entries; every status === "candidate"; every referenced file exists under public/gallery/ and is a JPEG (check magic bytes FF D8); gallery.html contains the candidate section heading, the works.json fetch, and the PLATEAU credit. Wire into package.json test chain. Run full `npm test` + `npx vite build` and report honestly.
Print a summary at the end.
