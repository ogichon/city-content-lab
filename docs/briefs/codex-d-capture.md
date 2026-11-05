# Brief — Codex D: 自動キャプチャ基盤 (PR2, P0 / Issue #7)

Worktree: ~/workspace/ccl-wt-capture, branch feat/auto-capture. Read AGENTS.md first. Do NOT commit (Muse commits). Another branch (fix/controlled-comparison) is changing recipes/viewer camera lines in parallel — keep your viewer.ts edits minimal and localized to avoid merge conflicts: touch ONLY (a) the status() helper / window exposure, (b) an idle listener registration, (c) URL param handling at the top of main(). Do not refactor anything else.

## Background facts (verified)
- Proven capture pattern: ~/workspace/navara-tocho-proto/scripts/shoot.mjs — puppeteer-core + executablePath /opt/meta-chromium/chrome + SwiftShader args (--use-gl=angle --use-angle=swiftshader --enable-unsafe-swiftshader --no-sandbox). Tiles are slow under SwiftShader (tens of seconds).
- The viewer's status() currently writes only to the DOM and says 描画完了は未確認. There is no window.__ready hook yet.

## Deliverables
1. `src/viewer.ts` (minimal edits):
   - status(): also set (window as any).__status = text.
   - Expose (window as any).__view = view after init.
   - Register view idle event (try/catch like proto main.ts): on idle set (window as any).__idle = true and update status to 読み込み完了（idle検知）.
   - URL params: `ui=0` → hide the #ui panel (display:none). `progress=<0..1>` → for growth mode, set progress to that value once after layers are set up and do not animate; for lift mode, ignore. `cam=<lng,lat,distance,heading,pitch>` is NOT in scope.
2. `package.json`: add "puppeteer-core" to devDependencies (version ^25.16.0, matching the proto) and a script "capture": "node scripts/capture.mjs". (A parallel branch also edits package.json? No — it doesn't. Safe.)
3. `scripts/capture.mjs`:
   - Usage: `node scripts/capture.mjs <recipeId...> [--url-base http://127.0.0.1:4173] [--wait-extra 8000]`. Default: all recipes in public/recipes/index.json.
   - For each recipe: open `<base>/viewer.html?recipe=<id>&ui=0` (+ `&progress=0.55` for growth recipes), viewport 1280x760, wait for window.__idle === true (timeout 180s), then wait extra ms, then read window.__status and the camera readout if available, screenshot JPEG quality 82 to `public/captures/<id>.jpg`, and record {id, file, capturedAt ISO, status, bytes} into `public/captures/index.json` (create/merge, sorted by id).
   - Log progress per recipe; a failed recipe is recorded with error and the run continues; exit code non-zero if any failed. No infinite retries: one retry per recipe max, only on timeout.
   - IMPORTANT: serve from a local preview of the CURRENT worktree build (the caller will run `npx vite build && npx vite preview --port 4173` before invoking; document this in the script header comment).
4. `compare.html`: when rendering each recipe card, fetch `./captures/index.json`; if an entry exists for the recipe id, show the image (`./captures/<file>`) as the card thumbnail linking to the viewer; otherwise keep the existing 目視確認待ち placeholder text. Do not break when the manifest is missing (catch → placeholders).
5. `scripts/test-capture.cjs`: static contract tests — capture.mjs exists and references __idle, puppeteer-core, captures/index.json; viewer.ts contains __idle/__status exposure and ui=0 handling; compare.html references captures/index.json. Add it to package.json test script chain. Run all tests + full build and report honestly. Do NOT run the actual capture (Muse runs it after merge, to verify images personally).

Print a summary: files changed, test/build results, known risks.
