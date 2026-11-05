# Brief — Codex F: ビューア内一括撮影 batch.html (通常Chromeで動作)

Worktree: ~/workspace/ccl-wt-batch, branch feat/batch-capture. Read AGENTS.md first. Do NOT commit (Muse commits). Goal: the USER opens this page in their normal Mac Chrome, clicks 一括撮影 once, and gets a ZIP of verified PNGs + metadata.json. No browser-policy workarounds, no permission changes — plain same-origin web tech only.

## Deliverables
1. `batch.html` + `src/batch.ts`:
   - On load, fetch `./recipes/index.json` and render grouped checkboxes (by experiment, and by group controlled/best where present). Default checked: EXP-003 controlled (6), EXP-002 (4), EXP-001 (2), EXP-004 (4). Show recipe count.
   - A stage area with an iframe sized 1280×760 (scaled to fit via CSS transform if needed, but the iframe's internal viewport must stay 1280×760).
   - 「一括撮影」 button runs the queue sequentially. For each recipe:
     a. Set iframe src to `viewer.html?recipe=<id>&ui=0` (growth recipes add `&progress=0.55`).
     b. Wait for readiness — NOT fixed seconds alone: poll every 500ms for iframe `contentWindow.__idle === true`, timeout 120s → failure reason "timeout".
     c. Stability check: sample the iframe canvas twice, 1500ms apart. Sampling = draw canvas into a 64×38 offscreen canvas, read pixels, compute (i) mean absolute difference between the two samples, (ii) fraction of pixels near the viewer background color #06080e (per-channel within 12). Pass requires: idle reached AND mean-diff < 2.0 (stable) AND background fraction < 0.85 (not blank). Otherwise failure with reason "unstable" or "blank". Record the measured values either way.
     d. On pass: capture PNG via canvas.toDataURL("image/png") → blob; store with metadata: {id, experiment, group, title, place, time, material, growthOrder, cameraText (iframe #cam textContent), statusText (iframe __status), idleWaitMs, stabilityMeanDiff, backgroundFraction, capturedAt ISO, canvas: {w,h}}.
     e. On failure: metadata entry {id, result:"failed", reason, statusText if any} — no image stored.
   - Per-recipe live status list （待機/読込中/安定確認中/成功/失敗+理由） and a summary line.
   - 「ZIPをダウンロード」 button (enabled when the run finishes): build a ZIP with a hand-written minimal ZIP writer (STORE method + CRC32 table implementation, no new dependencies) containing `<id>.png` for each success and `metadata.json` (all entries incl. failures, plus run info {startedAt, userAgent, pageUrl}). Download as `city-content-lab-captures-<YYYYMMDD-HHmm>.zip`.
   - Notes in the UI: runs entirely in this browser; keep the tab in front; failures are recorded, not mixed into successes.
2. `vite.config.ts`: add `batch: "batch.html"` to build inputs.
3. `index.html`: add one link to batch.html （一括撮影） in the nav. Touch nothing else there.
4. `scripts/test-batch.cjs`: static contract tests — batch.ts references __idle polling, two-sample stability comparison, background-fraction blank check, per-recipe timeout, CRC32 + ZIP STORE writer, metadata.json, failures recorded without images; vite config includes batch; package.json test chain gains test-batch. Run full `npm test` + `npx vite build` and report honestly. Do NOT attempt to run a real browser capture.
Print a summary at the end.
