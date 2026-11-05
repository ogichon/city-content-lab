# Brief — Codex B: site shell + contact sheet + tests (index/compare/gallery)

Repo: ~/workspace/city-content-lab-wt-site (worktree, branch exp/site)
Read first: AGENTS.md, src/recipes.ts, public/recipes/index.json, docs/architecture.md.
Another agent (Codex A) is building viewer.html + src/viewer.ts in a separate worktree. DO NOT create viewer.html or src/viewer.ts.

## Deliverables
1. `index.html` — LAB top (no JS framework, inline CSS, dark, Japanese): concept one-liner, how it works （作る→比較する→学ぶ→改善する）, experiment cards for EXP-001/002/003 with status, links to compare.html and gallery.html and to the sister tech repo. Attribution footer (PLATEAU MLIT / GSI / Re:Earth Terrain).
2. `compare.html` — contact sheet: fetch `./recipes/index.json`, group by experiment, render a card per recipe: title, experiment, place/time/mode/material meta, and a link `viewer.html?recipe=<id>`. EXP-003 section header must state the fixed comparison conditions （東京駅・同一カメラ distance 520/heading 55/pitch -48） and note the two recorded deviations (chrome=day for metal readability, crystal=night for bloom). Cards have an empty thumbnail slot with text 「目視確認待ち — サムネイルはユーザーのChrome確認後に差し替え」 (do NOT generate fake screenshots or placeholder images that look like renders).
3. `gallery.html` — adopted-works gallery: honest empty state 「採用作品はまだありません。最初のPDCA（EXP-003）のユーザ評価後に掲載します」 + list of current candidates linking to compare.html.
4. `scripts/test-recipes.cjs` — plain node: parse public/recipes/index.json; extract recipe ids/material keys/growth orders from src/recipes.ts by regex; assert: ids match exactly both ways, EXP-003 has exactly 6 material recipes all place=tokyo with identical comparison intent, every material key exists in MATERIALS, every growthOrder exists, seeds are numbers. Print PASS/FAIL summary, exit non-zero on failure.
5. Run the test and `npx vite build` — NOTE: build will fail in this worktree because viewer.html/src/viewer.ts come from Codex A's branch. If build fails ONLY due to missing viewer entry, record that explicitly and verify the three HTML files individually by a lightweight check (e.g. node script asserting links/files referenced exist or are expected-from-A). Do not fake a passing build.

## Constraints
- Do not edit AGENTS.md, docs/*, src/recipes.ts, vite.config.ts, package.json.
- No new dependencies, no images generated, no fake render claims.
- Commit on the branch; report files, test result, build caveat.
