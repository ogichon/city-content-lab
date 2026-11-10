import { stageFrame } from "./stage";
import ThreeView, { Color } from "@navaramap/three";
import { DefaultPlugin, type DefaultDescriptions } from "@navaramap/three-default-plugin";
import { getRecipe, RECIPES, PLACES, TIMES, MATERIALS, seededRank, effectiveCamera } from "./recipes";

const status = (message: string) => { document.getElementById("status")!.textContent = message; (window as any).__status = message; };
const finite = (n: unknown): n is number => typeof n === "number" && Number.isFinite(n);
const clamp = (n: number) => Math.max(0, Math.min(1, n));
const mix = (a: number, b: number, t: number) => {
  const ch = (s: number) => Math.round(((a >> s) & 255) * (1 - t) + ((b >> s) & 255) * t);
  return (ch(16) << 16) | (ch(8) << 8) | ch(0);
};
// EXP-022: PLATEAU/terrain heights are ellipsoid metres. The Sumida east-bank
// ground is ~0-2 m above sea level, i.e. roughly +37 m ellipsoid in this part
// of Tokyo (the proto flooded Tokyo Station at a 42 m ellipsoid plane), so
// the water plane height is this datum + the stage's current water level.
const WATER_GROUND_DATUM = 37;

async function main() {
  // Declare shared state before initialization or event registration (including bfcache).
  let timer: ReturnType<typeof setInterval> | undefined;
  let cameraTimer: ReturnType<typeof setInterval> | undefined;
  let progress = -1;
  let waterLevel = 0;
  let waterPlane: any;
  let waterPlaneLevel = Number.NaN;
  let startedAt = 0;
  let orbitElapsed = 0;
  let lastTick = 0;
  const evaluators = new Map<bigint, any>();
  const params = new URLSearchParams(location.search);
  if (params.get("ui") === "0") document.getElementById("ui")!.style.display = "none";
  const recipe = getRecipe(params.get("stage") ?? params.get("recipe"));
  const stage = params.has("stage") && !!recipe.performance?.shots.length;
  let stageStarted = false;
  let stageReady = false;
  let stageReadyAt = 0;
  let beginStage = () => {};
  const stageState = { playing: false, shotIndex: 0, progress: 0 };
  if (stage) {
    (window as any).__stage = stageState;
    document.getElementById("ui")!.style.display = "none";
    const caption = document.createElement("p");
    caption.id = "stage-caption"; caption.textContent = recipe.title;
    document.body.append(caption);
    const credits = document.createElement("p"); credits.id = "stage-credits";
    credits.textContent = recipe.mode === "lift" ? "都市データ: PLATEAU / 国土交通省" : "都市データ: PLATEAU / 国土交通省 · 地理院タイル · Re:Earth Terrain";
    document.body.append(credits);
    const probe = document.createElement("p"); probe.id = "stage-probe"; probe.textContent = "probe init";
    document.body.append(probe);
    // Time presets configure the scene at initialization only. Live time drift
    // is unsupported; timeFrom/timeTo remain part of the durable recipe.
  }
  const rawProgress = params.get("progress");
  const fixedProgress = !stage && recipe.mode === "growth" && rawProgress !== null && rawProgress.trim() !== "" && Number.isFinite(Number(rawProgress))
    ? clamp(Number(rawProgress)) : undefined;
  (window as any).__idle = false;
  const place = PLACES[recipe.place];
  const time = TIMES[recipe.time];
  const camera = effectiveCamera(recipe);
  const orbit = { ...camera };
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
  if (stage) {
    // EXP-016 structural grade: the default photoreal scene extinguishes
    // light with distance (aerial-perspective transmittance), which is the
    // main "pull back and it goes black" path at sunset/night. Performances
    // opt out; the tuned static recipes keep the stock atmosphere.
    try { (scene as any).aerialPerspective?.update({ aerialPerspective: { transmittance: false } } as any); }
    catch (error) { console.warn("aerialPerspective unavailable", error); }
  }
  view.addLight({ ambient: { intensity: time.ambient, color: new Color().setHex(0x93a7cc) } } as any);
  // Stage mode reads darker than the tuned static framings (wide shots at
  // sunset/night fall off a cliff), so performances get a modest exposure
  // lift. Only ever raises exposure; the static viewer is unchanged.
  view.toneMappingExposure = time.exposure * (stage ? 1.25 : 1);
  if (recipe.mode === "lift") {
    scene.sky.update({ visible: false });
    scene.stars.update({ visible: false });
  }
  let cloudsHandle: any;
  for (const effect of [
    { clouds: { coverage: 0.45, lightShafts: true, haze: true } },
    { id: "ccl-bloom", selectiveBloom: { strength: 0.85, radius: 0.6, threshold: 0.55, smoothing: 0.2 } },
  ]) { try { const handle = view.addEffect(effect as any); if ("clouds" in effect) cloudsHandle = handle; if ((recipe.mode === "lift" || recipe.performance?.clouds === "off") && "clouds" in effect) handle.update({ visible: false } as any); } catch (error) { console.warn("Optional effect unavailable", error); } }
  if (stage && cloudsHandle && recipe.mode !== "lift") {
    // EXP-016: cloud haze is the second distance-darkening path; zero it for
    // performances (the proto measured haze density as a real factor).
    try { cloudsHandle.update({ clouds: { hazeDensityScale: 0 } } as any); }
    catch (error) { console.warn("cloud haze update unavailable", error); }
  }
  if (recipe.mode !== "lift") {
    const source = view.addSource({ type: "quantized-mesh", url: "https://terrain.reearth.land/cesium-mesh/ellipsoid/{z}/{x}/{y}.terrain", maxZoom: 18, requestVertexNormals: true, requestWaterMask: true } as any);
    const terrainLayer = view.addLayer({ type: "terrain", source, terrain: { castShadow: true, receiveShadow: true } } as any);
    if (stage) {
      // EXP-016: at a 1.5-degree sun a lit ground receives ~3% direct light
      // and the photo basemap crushes to black. Performances run the ground
      // unlit so its brightness is governed by the recipe tint alone.
      try { terrainLayer.update({ type: "terrain", source, terrain: { castShadow: true, receiveShadow: true, lit: false } } as any); }
      catch (error) { console.warn("terrain lit update unavailable", error); }
    }
    const photo = view.addSource({ type: "raster-tile", url: "https://cyberjapandata.gsi.go.jp/xyz/seamlessphoto/{z}/{x}/{y}.jpg", maxZoom: 18 } as any);
    view.addLayer({ type: "raster", source: photo, raster: { color: new Color().setHex(time.groundTint) } } as any);
  }
  const threshold = (p: Record<string, unknown> = {}) => {
    const h = p["bldg:measuredHeight"], x = p._x, y = p._y;
    if (!finite(h) || !finite(x) || !finite(y)) return 0.5;
    switch (recipe.growthOrder) {
      case "center-out": return clamp(Math.hypot((x - camera.lng) * 111320 * Math.cos(camera.lat * Math.PI / 180), (y - camera.lat) * 110540) / 1500);
      case "low-to-high": return clamp(h / 240);
      case "random": return seededRank(recipe.seed, x, y);
      case "giants-last": return h >= 150 ? 0.92 + 0.08 * clamp((h - 150) / 90) : clamp(h / 240);
      default: return 0.5;
    }
  };
  const style = ({ properties: p }: { properties?: Record<string, unknown> }) => {
    if (recipe.performance?.water) {
      // EXP-022: one porcelain material for every building; a building whose
      // measured height is at or below the current water level reads as
      // submerged (dark blue-green, unlit). Ground elevation is not a tile
      // attribute, so the split is keyed on height vs level — the lowland
      // approximation recorded in EXP-022. Per-frame: waterLevel is updated
      // by the stage tick and refresh() re-evaluates this callback.
      const m = MATERIALS.porcelain;
      const height = p?.["bldg:measuredHeight"];
      const t = finite(height) ? clamp(height / 240) : 0;
      if (finite(height) && height <= waterLevel) {
        return { color: new Color().setHex(0x2e4d4a), emissive: new Color().setHex(0x000000), emissiveIntensity: 0, metalness: 0, roughness: 1, opacity: 1, show: true };
      }
      return { color: new Color().setHex(mix(...m.color, t)), emissive: new Color().setHex(mix(...m.emissive, t)), emissiveIntensity: m.emissiveIntensity, metalness: m.metalness, roughness: m.roughness, opacity: m.opacity, show: true };
    }
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
  if (stage && recipe.performance?.water) {
    // EXP-022: ONE translucent water plane centred on the recipe target; its
    // height is driven per frame by the stage tick (addMesh shape proven in
    // the sibling UNDERWATER prototype).
    try {
      waterPlane = view.addMesh({
        geodetic: { lng: camera.lng, lat: camera.lat, height: WATER_GROUND_DATUM, heightReference: "ellipsoid" },
        rotation: { x: -Math.PI / 2, y: 0, z: 0 },
        plane: { width: 9000, height: 9000, color: new Color().setHex(0x14424f), transparent: true, opacity: 0.55, castShadow: false, receiveShadow: false },
      } as any);
      waterPlaneLevel = 0;
    } catch (error) { console.warn("water plane unavailable", error); }
  }
  if (fixedProgress !== undefined) { progress = fixedProgress; refresh(); }
  try {
    (view as any).on("idle", () => {
      (window as any).__idle = true;
      if (stage && stageReady && !stageStarted) beginStage();
      status("読み込み完了（idle検知）");
      // Enable capture here as well: a mid-setup error can abort the tail of
      // setup (where the button is normally enabled) while this handler,
      // registered earlier, still runs — capture only needs view + canvas.
      (document.getElementById("capture") as HTMLButtonElement).disabled = false;
    });
    // Loading can resume after an idle (further tile streaming): readiness
    // must reflect the CURRENT state, so clear __idle on any loading signal.
    for (const ev of ["loading", "tile-loading", "rendering"]) {
      try { (view as any).on(ev, () => { (window as any).__idle = false; }); } catch { /* event may not exist */ }
    }
    // NOTE: no status-text fallback here — report() legitimately overwrites
    // the status after setup ("設定完了" etc.), which would wedge readiness.
  } catch (error) { console.warn("idle event unavailable", error); }
  view.setCamera(camera);
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
        orbit.distance = camera.distance * (1 + 0.025 * Math.sin(orbitElapsed / 6000));
        view.setCamera({ ...orbit });
      }
      lastTick = now; report();
    }, 50);
    report();
  };
  // EXP-016/017/018 luminance probe. v3 is diagnostic-first: a plain 1s
  // interval heartbeat rewrites the element unconditionally, a bare counter
  // handler tells whether postRender reaches us at all, and the sampler
  // records either values or the error name. One screenshot after a few
  // seconds of playback separates every failure mode.
  const probeCanvas = document.createElement("canvas"); probeCanvas.width = 48; probeCanvas.height = 27;
  const probeCtx = probeCanvas.getContext("2d", { willReadFrequently: true });
  const probeState = { frames: 0, samples: 0, text: "init" };
  const sampleProbe = () => {
    try {
      const canvas = container.querySelector("canvas"); if (!canvas || !probeCtx) { probeState.text = "no-canvas"; return; }
      probeCtx.drawImage(canvas as HTMLCanvasElement, 0, 0, 48, 27);
      const data = probeCtx.getImageData(0, 0, 48, 27).data;
      const n = 48 * 27; let sum = 0, black = 0, groundSum = 0;
      for (let i = 0; i < n; i++) {
        const lum = (0.2126 * data[i * 4] + 0.7152 * data[i * 4 + 1] + 0.0722 * data[i * 4 + 2]) / 255;
        sum += lum; if (lum < 0.05) black++;
        if (i >= n / 2) groundSum += lum;
      }
      const probe = { mean: +(sum / n).toFixed(3), blackFrac: +(black / n).toFixed(3), groundMean: +(groundSum / (n / 2)).toFixed(3) };
      (stageState as any).probe = probe;
      probeState.samples++;
      probeState.text = `shot ${stageState.shotIndex + 1} mean ${probe.mean} ground ${probe.groundMean} black ${Math.round(probe.blackFrac * 100)}%`;
    } catch (error) {
      (stageState as any).probeError = String((error as any)?.name ?? error);
      probeState.text = `err ${(error as any)?.name ?? "unknown"}`;
    }
  };
  const probeHandler = () => { probeState.frames++; if (probeState.frames % 30 === 0) sampleProbe(); };
  if (stage) {
    try { (view as any).on("postRender", probeHandler); } catch (error) { probeState.text = `on-err ${(error as any)?.name ?? "unknown"}`; }
    let probeSecs = 0;
    setInterval(() => {
      probeSecs++;
      // EXP-019/020 watchdog: idle can take very long on heavy LOD2 tilesets
      // (continuous streaming), which left performances stuck on the static
      // first frame. Start on a bounded wait instead; tiles keep refining
      // during the show. EXP-020: the EXP-019 condition depended on a
      // setup-completion timestamp that not every start path sets (probe
      // showed wait at 26s), so the watchdog now counts this interval's own
      // ticks — the heartbeat that provably runs.
      if (!stageStarted && probeSecs >= 5) beginStage();
      const el = document.getElementById("stage-probe");
      if (el) el.textContent = `probe ${probeSecs}s f${probeState.frames} ${stageStarted ? "run" : "wait"} · ${probeState.text}`;
    }, 1000);
  }
  beginStage = () => {
    stop(); stageStarted = true; startedAt = performance.now();
    document.getElementById("stage-caption")?.classList.add("playing");
    const tick = () => {
      const frame = stageFrame(recipe, (performance.now() - startedAt) / 1000);
      Object.assign(stageState, { playing: frame.playing, shotIndex: frame.shotIndex, progress: frame.progress });
      view.setCamera(frame.camera);
      if (recipe.mode === "growth") { progress = frame.progress; refresh(); }
      if (recipe.performance?.water) {
        // EXP-022: same per-frame pattern as growth — publish the level,
        // move the plane, and re-evaluate feature styles against it.
        waterLevel = frame.waterLevel;
        (stageState as any).waterLevel = frame.waterLevel;
        if (waterPlane && Math.abs(waterLevel - waterPlaneLevel) > 0.001) {
          waterPlaneLevel = waterLevel;
          try { waterPlane.update({ geodetic: { height: WATER_GROUND_DATUM + waterLevel } } as any); }
          catch (error) { console.warn("water plane update unavailable", error); }
        }
        refresh();
      }
      if (!frame.playing) stop();
    };
    timer = setInterval(tick, 50); tick();
  };
  play.addEventListener("click", () => { if (timer !== undefined) { stop(); report(); } else start(); });
  reset.addEventListener("click", () => {
    stop(); progress = -1; orbitElapsed = 0; Object.assign(orbit, camera);
    view.setCamera(camera); refresh(); showCamera(); report();
  });
  container.addEventListener("pointerdown", () => { if (!stage && recipe.mode === "lift") { stop(); report(); } });
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
  window.addEventListener("pagehide", () => { stop(); if (stage) { stageState.playing = false; stageStarted = false; stageReady = false; } if (cameraTimer !== undefined) clearInterval(cameraTimer); cameraTimer = undefined; });
  window.addEventListener("pageshow", () => {
    progress = fixedProgress ?? -1;
    if (stage) {
      stop(); stageStarted = false; stageReady = true;
      Object.assign(stageState, { playing: false, shotIndex: 0, progress: 0 });
      document.getElementById("stage-caption")?.classList.remove("playing");
      view.setCamera(camera); progress = -1; waterLevel = 0;
      if (waterPlane) {
        waterPlaneLevel = 0;
        try { waterPlane.update({ geodetic: { height: WATER_GROUND_DATUM } } as any); }
        catch (error) { console.warn("water plane reset unavailable", error); }
      }
      refresh();
      if ((window as any).__idle) beginStage();
      return;
    }
    stop(); progress = fixedProgress ?? -1; orbitElapsed = 0; Object.assign(orbit, camera);
    view.setCamera(camera); refresh(); showCamera();
    if (cameraTimer !== undefined) clearInterval(cameraTimer);
    cameraTimer = setInterval(showCamera, 2000);
    status("復帰しました。アニメーションはリセット済み。再生できます（描画は未確認）。");
  });
  cameraTimer = setInterval(showCamera, 2000); showCamera();
  play.disabled = reset.disabled = recipe.mode !== "growth" && recipe.mode !== "lift";
  (document.getElementById("capture") as HTMLButtonElement).disabled = false;
  if (stage) {
    stageReady = true; stageReadyAt = performance.now();
    if ((window as any).__idle) beginStage(); else report();
  } else if (recipe.mode === "lift") start(); else report();
}
main().catch(error => { console.error(error); status(`エラー: ${error?.message ?? error}`); });
