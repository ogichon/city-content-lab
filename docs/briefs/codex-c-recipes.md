# Brief — Codex C: Controlled vs Best Look 分離 + GROWTH統一 + EXP-004カメラ (PR1)

Worktree: ~/workspace/ccl-wt-recipes, branch fix/controlled-comparison. Read AGENTS.md and src/recipes.ts first. Do NOT commit (git metadata is outside your sandbox; Muse commits). Do not touch src/viewer.ts except the single camera-override change below, and do not touch compare/index/gallery HTML.

## Changes
1. `src/recipes.ts`:
   - Add optional `cameraOverride?: Partial<PlaceDef["camera"]>` to Recipe, and a helper `effectiveCamera(recipe)` returning {...place.camera, ...recipe.cameraOverride}.
   - EXP-003 Controlled set (keep existing ids exp003-*): set ALL six to time "sunset" (chrome day→sunset, crystal night→sunset). Add `group: "controlled"` field to Recipe (type: "controlled" | "best" | undefined) and set it on these.
   - Add Best Look set with group "best", place tokyo, same base camera: exp003-best-porcelain (sunset), exp003-best-gold (sunset), exp003-best-chrome (day), exp003-best-ice (day), exp003-best-glass (day), exp003-best-crystal (night). Titles: "MATERIAL TOKYO [Best] / 陶器" etc.
   - EXP-002: change exp002-giants-last place from "tocho" to "tokyo" so all four growth recipes share place+camera.
   - EXP-004 (CAMERA LANGUAGE): add 4 recipes, experiment "EXP-004", mode "material", material "gold", place tokyo, time sunset, group "controlled": exp004-standard (no override), exp004-low-angle (cameraOverride {distance:380, pitch:-18}), exp004-top-down ({distance:700, pitch:-85}), exp004-diorama ({distance:900, pitch:-55}). Titles "CAMERA / 標準" "CAMERA / ローアングル" "CAMERA / 真俯瞰" "CAMERA / ジオラマ俯瞰".
2. `src/viewer.ts` (ONE change only): use effectiveCamera(recipe) wherever place.camera is used for the initial setCamera and growth center-out reference and lift orbit base. Keep behavior identical when no override.
3. `public/recipes/index.json`: mirror ALL recipes (now 22) with the same fields incl. group and cameraOverride where present.
4. `scripts/test-recipes.cjs`: update assertions — controlled EXP-003: exactly 6, all place tokyo + time sunset; best set: exactly 6 with the specified times; EXP-002: all 4 place tokyo; EXP-004: 4 recipes with cameraOverride on 3; id sync TS↔JSON still enforced. Run it.
5. `docs/experiments/EXP-003.md`: add a section recording the Controlled/Best separation and why (user direction 2026-11-05). Create `docs/experiments/EXP-004.md` with PLAN for camera comparison. Update EXP-002.md PLAN note about unified place.
6. Run `npm test` (test-viewer may reference things you didn't change — it should still pass) and a full `npx vite build`. Report results honestly. Print summary at the end.
