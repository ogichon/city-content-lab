import { defineConfig } from "vite";
import { copyFileSync, cpSync, existsSync } from "node:fs";
import { resolve } from "node:path";

// @navaramap/three ships runtime wasm assets next to its dist JS and
// resolves them relative to the module/worker URL at runtime. Vite does
// not copy them when bundling, so fetches 404 — which silently kills
// Draco decoding and therefore ALL PLATEAU B3DM tiles. Copy explicitly.
// (Inherited from navara-plateau-proto, where this was the root cause of
// the v1-v10 invisible-buildings failure.)
const RUNTIME_ASSETS = [
  "draco_decoder-DsQ12WqX.wasm",
  "navara_wasm_font_worker_bg-B4MRzeuT.wasm",
];
const RUNTIME_ASSET_DIRS = ["cloud", "noise", "water"];
const copyRuntimeAssets = {
  name: "copy-navara-runtime-assets",
  closeBundle() {
    for (const name of RUNTIME_ASSETS) {
      const src = resolve("node_modules/@navaramap/three/dist/assets", name);
      if (existsSync(src)) {
        copyFileSync(src, resolve("dist/assets", name));
        console.log(`copied runtime asset: ${name}`);
      } else {
        console.warn(`runtime asset NOT FOUND: ${src}`);
      }
    }
    for (const dir of RUNTIME_ASSET_DIRS) {
      const src = resolve("node_modules/@navaramap/three/dist/assets", dir);
      if (existsSync(src)) {
        cpSync(src, resolve("dist/assets", dir), { recursive: true });
        console.log(`copied runtime asset dir: ${dir}`);
      } else {
        console.warn(`runtime asset dir NOT FOUND: ${src}`);
      }
    }
  },
};

export default defineConfig({
  base: "./",
  server: { host: "0.0.0.0", port: 5174, allowedHosts: true },
  plugins: [copyRuntimeAssets],
  build: {
    target: "es2022",
    rollupOptions: {
      input: {
        main: "index.html",
        viewer: "viewer.html",
        compare: "compare.html",
        gallery: "gallery.html",
        batch: "batch.html",
      },
    },
  },
});
