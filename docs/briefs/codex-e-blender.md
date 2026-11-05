# Brief — Codex E: Blender切断経路 実現性スパイク (Issue #6, ドキュメントのみ)

Worktree: ~/workspace/ccl-wt-blender, branch docs/blender-spike. Read AGENTS.md and docs/experiments/EXP-001.md. Deliverable is ONE file: `docs/research/blender-lift-spike.md`. No code, no installs, no downloads larger than HEAD requests. Do NOT commit (Muse commits).

## Content required
1. Goal restated: true CITY LIFT = cut a rectangular/circular district out of PLATEAU data, show a cut section (strata-like side), float it. Why Navara cannot do it (streaming tiles, no geometry clipping/section generation).
2. Data route: PLATEAU CityGML for Chiyoda-ku (and Shinjuku-ku) FY2023 — where it is distributed (MLIT PLATEAU portal / G空間情報センター), format (zip of CityGML), how to verify size/format with HEAD requests only if reachable; if not reachable, say so explicitly and mark unverified.
3. Pipeline design: CityGML → Blender (import path options: CityJSON conversion, plateau-blender-importer type add-ons, or OBJ/FBX via FME-less open tools — compare 2-3 realistic options with maintenance status as far as you can verify from local knowledge; mark uncertain items as 要検証 rather than inventing facts) → boolean cut / clipping by bounding box → section material → render still.
4. Environment: Blender is NOT installed in this VM (`which blender` empty — verify). Options: apt package, official tarball (~300MB class), headless rendering feasibility on CPU-only VM (SwiftShader irrelevant; Cycles vs Eevee cost), rough download/disk figures marked as estimates.
5. Effort estimate per step (person-hours class: S/M/L), risks, and a minimal first spike definition: "Chiyoda 1km square, white material, one cut, one still" with explicit success criteria.
6. Go/No-Go recommendation criteria tied to EXP-001 LITE's visual verdict (if LITE reads as floating, Blender cut is polish; if LITE fails, the cut section is the missing ingredient and priority rises).
Write in Japanese, concise, with a 結論 section at top. Mark every unverified claim with 要検証.
