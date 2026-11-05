# Fix brief — Codex A (from independent review FAIL, 2 HIGH findings)

Work in this worktree (branch exp/viewer). Only edit src/viewer.ts and scripts/test-viewer.cjs.

## Finding 1: selective bloom never selects buildings
Proven pattern from navara-plateau-proto src/underwater.ts:63,92:
- addEffect with an id: view.addEffect({ id: "underwater-bloom", selectiveBloom: {...} })
- building layer model gets effectIds: ["underwater-bloom"]
Apply the same: give the bloom effect id "ccl-bloom" and add effectIds: ["ccl-bloom"] to every 3d-tiles building layer model. Keep try/catch around addEffect; if the effect fails to add, log a warning (do not fake bloom).

## Finding 2: ice/glass opacity without transparency
When the recipe material has opacity < 1, the building layer model must include transparent: true. When opacity == 1, omit it (avoid sorting artifacts for opaque materials). Compute this from MATERIALS[recipe.material].opacity in material mode; other modes stay opaque.

## Tests
Extend scripts/test-viewer.cjs static contract tests: assert viewer.ts contains the bloom id string, effectIds usage on the model, and the transparent condition tied to opacity < 1. Run node scripts/test-viewer.cjs and a viewer-only vite build (temp config like before is fine, delete it after). Do NOT commit (git metadata is outside your sandbox; Muse commits). Print summary.
