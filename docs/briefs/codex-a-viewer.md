# Brief — Codex A: recipe-driven viewer (src/viewer.ts + viewer.html)

Repo: ~/workspace/city-content-lab-wt-viewer (worktree, branch exp/viewer)
Read first: AGENTS.md, src/recipes.ts (DO NOT change its exported shapes), and the proven patterns in ~/workspace/navara-tocho-proto/src/awakening.ts and src/main.ts (reference only, do not edit that repo).

## Deliverables
1. `viewer.html` — dark UI like the proto's index.html: title, recipe title, status line, camera readout, buttons: ⏵/↺ for growth & lift animation, 📸 capture (canvas download), recipe switcher (links preserving ?recipe=), place note + attribution. Loads `/src/viewer.ts`.
2. `src/viewer.ts` — Navara viewer driven ENTIRELY by the recipe from `?recipe=<id>` (fallback getRecipe(null)):
   - ThreeView + DefaultPlugin + addDefaultPhotorealScene, volumetric clouds + selectiveBloom (try/catch), Re:Earth terrain + GSI seamlessphoto raster, PLATEAU 3d-tiles layers from recipe place.
   - Time grading from TIMES[recipe.time]: atmosphere.date, photo tint, ambient, exposure. Never below the night floor defined there.
   - mode=material: FeatureEvaluator styling per MATERIALS[recipe.material]: height-interpolated color & emissive (use bldg:measuredHeight, clamp 0..240m), metalness/roughness/opacity from the def. White/standard before styling applies is fine.
   - mode=growth: buildings start hidden (show:false). ⏵ plays a 12s reveal: each building's threshold by growthOrder — center-out: distance of centroid (_x/_y) from place camera target, normalized 0..1 over 1500m; low-to-high: height/240; random: seededRank(recipe.seed,_x,_y); giants-last: height/240 but buildings >=150m get threshold 0.92..1. Progress drives show = threshold <= progress. Missing centroid/height: threshold 0.5. ↺ resets. On completion status shows 完了. This is an artistic growth, NOT historical reconstruction — put that disclaimer in the UI note for growth recipes.
   - mode=lift (LIFT-LITE): do NOT add terrain/photo layers (dark void), background near-black, buildings in night grading with slight emissive white; slow auto-orbit: animate camera heading +0.02deg/frame-equivalent via interval 50ms and a gentle distance breathing (sin). ⏵/⏸ toggles orbit. UI note must say LIFT-LITE（地形切断なし）.
   - Robustness (mandatory, from prior reviews): evaluators stored in a Map keyed by feature id, removed on layer featureRemoved event if available; pageshow listener resets timers/animation state and status to a non-frozen message; shared state declared at top of main() (no TDZ); late-arriving tiles get current animation state because styling reads shared state.
3. `scripts/test-viewer.cjs` — plain node, no deps: static behavior tests with mocks/regex-free logic tests where feasible. At minimum: (a) seededRank determinism & range, duplicated here as a pure function copy is NOT allowed — instead extract the rank logic by importing? TS cannot be imported by node cjs. Compromise: test by reading src/recipes.ts text and asserting seededRank exists and growth orders/material keys referenced in viewer.ts all exist in recipes.ts; assert viewer.ts contains featureRemoved cleanup, pageshow handler, growth disclaimer string, LIFT-LITE string; assert all RECIPES ids in recipes.ts appear in public/recipes/index.json. Keep tests honest: label them static contract tests.
4. Run `npm install` (reuse versions from package.json) and `npx vite build` in the worktree; fix build errors. Do NOT commit node_modules or dist.

## Constraints
- Do not edit: AGENTS.md, docs/*, src/recipes.ts shapes, vite.config.ts, package.json (scripts already include test entries referencing your test file).
- No new dependencies. No Grok. No external paid services.
- Commit on the branch with a clear message and report: files changed, build result, test result, known limitations (esp. material fidelity: chrome/ice/glass are approximations without true refraction/env reflection).
