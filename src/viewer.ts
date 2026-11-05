import ThreeView, { Color } from "@navaramap/three";
import { DefaultPlugin, type DefaultDescriptions } from "@navaramap/three-default-plugin";
import { getRecipe, RECIPES, PLACES, TIMES, MATERIALS, seededRank } from "./recipes";

const status = (message: string) => { document.getElementById("status")!.textContent = message; (window as any).__status = message; };
const finite = (n: unknown): n is number => typeof n === "number" && Number.isFinite(n);
const clamp = (n: number) => Math.max(0, Math.min(1, n));
const mix = (a: number, b: number, t: number) => {
  const ch = (s: number) => Math.round(((a >> s) & 255) * (1 - t) + ((b >> s) & 255) * t);
  return (ch(16) << 16) | (ch(8) << 8) | ch(0);
};

async function main() {
  // Declare shared state before initialization or event registration (including bfcache).
  let timer: ReturnType<typeof setInterval> | undefined;
  let cameraTimer: ReturnType<typeof setInterval> | undefined;
  let progress = -1;
  let startedAt = 0;
  let orbitElapsed = 0;
  let lastTick = 0;
  const evaluators = new Map<bigint, any>();
  const params = new URLSearchParams(location.search);
  if (params.get("ui") === "0") document.getElementById("ui")!.style.display = "none";
  const recipe = getRecipe(params.get("recipe"));
  const rawProgress = params.get("progress");
  const fixedProgress = recipe.mode === "growth" && rawProgress !== null && rawProgress.trim() !== "" && Number.isFinite(Number(rawProgress))
    ? clamp(Number(rawProgress)) : undefined;
  (window as any).__idle = false;
  const place = PLACES[recipe.place];
  const time = TIMES[recipe.time];
  const orbit = { ...place.camera };
  const container = document.getElementById("app")!;
  const play = document.getElementById("play") as HTMLButtonElement;
  const reset = document.getElementById("reset") as HTMLButtonElement;
  document.title = `CITY CONTENT LAB — ${recipe.title}`;
  document.getElementById("recipe-title")!.textContent = recipe.title;
  document.getElementById("note")!.textContent = `${place.note} / ${time.label} / seed ${recipe.seed} / v${recipe.codeVersion}。${recipe.mode === "growth" ? "芸術的な成長表現です。歴史的再現ではありません。" : recipe.mode === "lift" ? "LIFT-LITE（地形切断なし）。" : recipe.material ? MATERIALS[recipe.material].note + " クローム・氷・ガラスは近似表現（真の屈折・環境反射なし）。" : "白モデル。"}`;
  for (const r of RECIPES) {
    const link = document.createElement("a");
    const url = new URL(location.href); url.searchParams.set("recipe", r.id);
    link.href = url.href; link.textContent = r.title;
    if (r.id === recipe.id) link.setAttribute("aria-current", "page");
    document.getElementById("recipes")!.append(link);
  }
  if (recipe.mode === "lift") document.getElementById("ground-attribution")!.hidden = true;
  const view = new ThreeView<DefaultDescriptions>({ container, shadow: true, backgroundColor: new Color().setHex(0x06080e), atmosphere: { date: new Date(time.iso) } });
  const plugin = new DefaultPlugin(); view.addPlugin(plugin);
  status("WASM初期化中…"); await view.init();
  (window as any).__view = view;
  const scene = plugin.addDefaultPhotorealScene();
  scene.sun.update({ sun: { castShadow: true } } as any);
  view.addLight({ ambient: { intensity: time.ambient, color: new Color().setHex(0x93a7cc) } } as any);
  view.toneMappingExposure = time.exposure;
  if (recipe.mode === "lift") {
    scene.sky.update({ visible: false });
    scene.stars.update({ visible: false });
  }
  for (const effect of [
    { clouds: { coverage: 0.45, lightShafts: true, haze: true } },
    { id: "ccl-bloom", selectiveBloom: { strength: 0.85, radius: 0.6, threshold: 0.55, smoothing: 0.2 } },
  ]) { try { const handle = view.addEffect(effect as any); if (recipe.mode === "lift" && "clouds" in effect) handle.update({ visible: false } as any); } catch (error) { console.warn("Optional effect unavailable", error); } }
  if (recipe.mode !== "lift") {
    const source = view.addSource({ type: "quantized-mesh", url: "https://terrain.reearth.land/cesium-mesh/ellipsoid/{z}/{x}/{y}.terrain", maxZoom: 18, requestVertexNormals: true, requestWaterMask: true } as any);
    view.addLayer({ type: "terrain", source, terrain: { castShadow: true, receiveShadow: true } } as any);
    const photo = view.addSource({ type: "raster-tile", url: "https://cyberjapandata.gsi.go.jp/xyz/seamlessphoto/{z}/{x}/{y}.jpg", maxZoom: 18 } as any);
    view.addLayer({ type: "raster", source: photo, raster: { color: new Color().setHex(time.groundTint) } } as any);
  }
  const threshold = (p: Record<string, unknown> = {}) => {
    const h = p["bldg:measuredHeight"], x = p._x, y = p._y;
    if (!finite(h) || !finite(x) || !finite(y)) return 0.5;
    switch (recipe.growthOrder) {
      case "center-out": return clamp(Math.hypot((x - place.camera.lng) * 111320 * Math.cos(place.camera.lat * Math.PI / 180), (y - place.camera.lat) * 110540) / 1500);
      case "low-to-high": return clamp(h / 240);
      case "random": return seededRank(recipe.seed, x, y);
      case "giants-last": return h >= 150 ? 0.92 + 0.08 * clamp((h - 150) / 90) : clamp(h / 240);
      default: return 0.5;
    }
  };
  const style = ({ properties: p }: { properties?: Record<string, unknown> }) => {
    if (recipe.mode === "material" && recipe.material) {
      const m = MATERIALS[recipe.material];
      const height = p?.["bldg:measuredHeight"];
      const t = finite(height) ? clamp(height / 240) : 0;
      return { color: new Color().setHex(mix(...m.color, t)), emissive: new Color().setHex(mix(...m.emissive, t)), emissiveIntensity: m.emissiveIntensity, metalness: m.metalness, roughness: m.roughness, opacity: m.opacity, show: true };
    }
    return { color: new Color().setHex(0xffffff), emissive: new Color().setHex(recipe.mode === "lift" ? 0xffffff : 0), emissiveIntensity: recipe.mode === "lift" ? 0.15 : 0, opacity: 1, show: recipe.mode !== "growth" || threshold(p) <= progress };
  };
  const refresh = () => {
    for (const [id, ev] of evaluators) {
      try { ev.evaluate(style); } catch (error) { evaluators.delete(id); console.warn("Discarding evaluator", error); }
    }
    view.forceUpdate();
  };
  for (const url of place.tilesets) {
    const source = view.addSource({ type: "3d-tiles", url } as any);
    // Keep the tile object visible: per-feature show controls growth in the batch texture.
    // Metalness/roughness are uniform model properties in Navara 0.2.1.
    const layer = view.addLayer({ type: "3d-tiles", source, model: {
      color: new Color().setHex(0xffffff),
      effectIds: ["ccl-bloom"],
      metalness: recipe.mode === "material" && recipe.material ? MATERIALS[recipe.material].metalness : 0,
      roughness: recipe.mode === "material" && recipe.material ? MATERIALS[recipe.material].roughness : 1,
      ...(recipe.mode === "material" && recipe.material && MATERIALS[recipe.material].opacity < 1 ? { transparent: true } : {}),
    } } as any);
    const applyFeature = ({ featureSetId, evaluator }: any) => { evaluators.set(featureSetId, evaluator); evaluator.evaluate(style); };
    layer.on("featureCreated", applyFeature);
    layer.on("featureUpdated", applyFeature);
    try { layer.on("featureRemoved", ({ featureSetId }: any) => { evaluators.delete(featureSetId); }); }
    catch (error) { console.warn("featureRemoved unavailable", error); }
  }
  if (fixedProgress !== undefined) { progress = fixedProgress; refresh(); }
  try {
    (view as any).on("idle", () => {
      (window as any).__idle = true;
      status("読み込み完了（idle検知）");
    });
  } catch (error) { console.warn("idle event unavailable", error); }
  view.setCamera(place.camera);
  const showCamera = () => {
    const camera = view.camera;
    const p = camera.positionGeographic, o = camera.orientation;
    document.getElementById("cam")!.textContent = `cam ${p.lng.toFixed(5)}, ${p.lat.toFixed(5)} / h ${Math.round(p.height)}m / heading ${o.heading.toFixed(1)}° / pitch ${o.pitch.toFixed(1)}°`;
  };
  const stop = () => { if (timer !== undefined) clearInterval(timer); timer = undefined; play.textContent = "⏵ 再生"; play.setAttribute("aria-pressed", "false"); };
  const report = () => status(`${recipe.mode === "growth" ? progress >= 1 ? "完了" : progress < 0 ? "再生待ち" : `成長 ${Math.round(progress * 100)}%` : recipe.mode === "lift" ? timer === undefined ? "周回停止" : "周回中" : "設定完了"}。タイルは順次読み込み（描画完了は未確認）。`);
  const start = () => {
    stop(); startedAt = performance.now(); lastTick = startedAt;
    if (recipe.mode === "growth") { progress = -1; refresh(); }
    play.textContent = "⏸ 停止"; play.setAttribute("aria-pressed", "true");
    timer = setInterval(() => {
      const now = performance.now();
      if (recipe.mode === "growth") {
        progress = clamp((now - startedAt) / 12000); refresh();
        if (progress >= 1) stop();
      } else {
        const dt = now - lastTick; orbitElapsed += dt;
        orbit.heading = (orbit.heading + 0.02 * dt / (1000 / 60)) % 360;
        orbit.distance = place.camera.distance * (1 + 0.025 * Math.sin(orbitElapsed / 6000));
        view.setCamera({ ...orbit });
      }
      lastTick = now; report();
    }, 50);
    report();
  };
  play.addEventListener("click", () => { if (timer !== undefined) { stop(); report(); } else start(); });
  reset.addEventListener("click", () => {
    stop(); progress = -1; orbitElapsed = 0; Object.assign(orbit, place.camera);
    view.setCamera(place.camera); refresh(); showCamera(); report();
  });
  container.addEventListener("pointerdown", () => { if (recipe.mode === "lift") { stop(); report(); } });
  document.getElementById("capture")!.addEventListener("click", () => {
    try {
      view.forceUpdate();
      const captureFrame = () => {
        view.off("postRender", captureFrame);
        try {
          const canvas = container.querySelector("canvas"); if (!canvas) throw new Error("Canvas unavailable");
          const a = document.createElement("a"); a.href = canvas.toDataURL("image/png");
          a.download = `${recipe.id}-seed${recipe.seed}-v${recipe.codeVersion}-${Math.round(progress * 100)}.png`; a.click();
          status("キャプチャをダウンロードしました");
        } catch (error) { status(`キャプチャ失敗: ${error}`); }
      };
      view.on("postRender", captureFrame);
      view.forceUpdate();
    } catch (error) { status(`キャプチャ失敗: ${error}`); }
  });
  window.addEventListener("pagehide", () => { stop(); if (cameraTimer !== undefined) clearInterval(cameraTimer); cameraTimer = undefined; });
  window.addEventListener("pageshow", () => {
    stop(); progress = fixedProgress ?? -1; orbitElapsed = 0; Object.assign(orbit, place.camera);
    view.setCamera(place.camera); refresh(); showCamera();
    if (cameraTimer !== undefined) clearInterval(cameraTimer);
    cameraTimer = setInterval(showCamera, 2000);
    status("復帰しました。アニメーションはリセット済み。再生できます（描画は未確認）。");
  });
  cameraTimer = setInterval(showCamera, 2000); showCamera();
  play.disabled = reset.disabled = recipe.mode !== "growth" && recipe.mode !== "lift";
  (document.getElementById("capture") as HTMLButtonElement).disabled = false;
  if (recipe.mode === "lift") start(); else report();
}
main().catch(error => { console.error(error); status(`エラー: ${error?.message ?? error}`); });
