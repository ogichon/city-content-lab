// Recipe system — the core of the batch-prototyping engine.
// Every render must be reproducible from a recipe: place + camera + time
// grading + visual mode + animation + seed + code version.
// public/recipes/*.json mirrors these definitions as the durable record.

export type Mode = "material" | "growth" | "lift" | "standard";
export type GrowthOrder = "center-out" | "low-to-high" | "random" | "giants-last";

export interface PlaceDef {
  label: string;
  note: string;
  tilesets: string[];
  camera: { lng: number; lat: number; distance: number; heading: number; pitch: number; roll: number };
}

export const PLACES: Record<string, PlaceDef> = {
  tokyo: {
    label: "東京駅",
    note: "PLATEAU 千代田区+中央区 LOD2（テクスチャなし・白モデル）",
    tilesets: [
      "https://assets.cms.plateau.reearth.io/assets/db/070026-aa27-431b-8d53-7cc6b03244f8/13101_chiyoda-ku_pref_2023_citygml_1_op_bldg_3dtiles_13101_chiyoda-ku_lod2_no_texture/tileset.json",
      "https://assets.cms.plateau.reearth.io/assets/4c/f2436a-e2be-40e2-83da-f1781f36e30b/13102_chuo-ku_pref_2023_citygml_1_op_bldg_3dtiles_13102_chuo-ku_lod2_no_texture/tileset.json",
    ],
    camera: { lng: 139.7671, lat: 35.6812, distance: 520, heading: 55, pitch: -48, roll: 0 },
  },
  tocho: {
    label: "都庁（新宿）",
    note: "PLATEAU 新宿区 LOD2（テクスチャなし・白モデル）",
    tilesets: [
      "https://assets.cms.plateau.reearth.io/assets/f0/840fc4-114c-41e4-9a65-67768efd3629/13104_shinjuku-ku_pref_2023_citygml_2_op_bldg_3dtiles_13104_shinjuku-ku_lod2_no_texture/tileset.json",
    ],
    camera: { lng: 139.6917, lat: 35.6896, distance: 560, heading: 40, pitch: -46, roll: 0 },
  },
};

// Time grading presets. Ground photo is baked daylight, so grading is done
// via photo tint + ambient + exposure. Night values never go below the
// v14-proven floor (tint 0x51628c / ambient 0.6 / exposure 1.7 family).
export const TIMES: Record<string, { label: string; iso: string; groundTint: number; ambient: number; exposure: number }> = {
  day: { label: "昼 12:00 JST", iso: "2026-11-05T12:00:00+09:00", groundTint: 0xffffff, ambient: 0, exposure: 1.0 },
  sunset: { label: "夕 17:40 JST", iso: "2026-11-05T17:40:00+09:00", groundTint: 0xd8a878, ambient: 0.15, exposure: 1.05 },
  night: { label: "夜 21:00 JST", iso: "2026-11-05T21:00:00+09:00", groundTint: 0x51628c, ambient: 0.6, exposure: 1.7 },
};

// Material definitions for EXP-003. Each material is expressed ONLY with
// what Navara's FeatureEvaluator can actually do (color / metalness /
// roughness / opacity / emissive). Anything needing true refraction or
// environment-mapped reflection beyond this is recorded as NOT achieved
// and routed to the Blender track — never reported as implemented.
export interface MaterialDef {
  label: string;
  // color may be height-graded: [lowHex, highHex] interpolated by height.
  color: [number, number];
  metalness: number;
  roughness: number;
  opacity: number;
  emissive: [number, number];
  emissiveIntensity: number;
  note: string;
}

export const MATERIALS: Record<string, MaterialDef> = {
  porcelain: {
    label: "陶器 Porcelain",
    color: [0xe8e2d4, 0xf7f2e6], metalness: 0.0, roughness: 0.35, opacity: 1,
    emissive: [0x000000, 0x000000], emissiveIntensity: 0,
    note: "白磁のような均一な質感。形状が最も読みやすいはず、という仮説の基準案。",
  },
  gold: {
    label: "黄金 Gold",
    color: [0x9d510e, 0xffe8a0], metalness: 0.85, roughness: 0.3, opacity: 1,
    emissive: [0x201003, 0x694a12], emissiveIntensity: 0.35,
    note: "AWAKENING Goldの実証パレットを素材として再解釈。高さグラデーションで形状を保持。",
  },
  chrome: {
    label: "クローム Chrome",
    color: [0x8a939c, 0xe8eef2], metalness: 1.0, roughness: 0.12, opacity: 1,
    emissive: [0x000000, 0x000000], emissiveIntensity: 0,
    note: "金属反射は環境マップ依存。Navara上では近似に留まる可能性を明記する。",
  },
  ice: {
    label: "氷 Ice",
    color: [0x9fd4e8, 0xeaf7ff], metalness: 0.1, roughness: 0.15, opacity: 0.82,
    emissive: [0x0a2432, 0x1d4a5e], emissiveIntensity: 0.4,
    note: "半透明+微発光で氷の冷たさを近似。真の屈折は未実装（Blender候補）。",
  },
  glass: {
    label: "ガラス Glass",
    color: [0xbfe3dd, 0xf2fffc], metalness: 0.2, roughness: 0.08, opacity: 0.45,
    emissive: [0x000000, 0x000000], emissiveIntensity: 0,
    note: "透明度が高いほど建物形状が溶けるリスク。形状可読性とのトレードオフを測る案。",
  },
  crystal: {
    label: "発光クリスタル Crystal",
    color: [0x2a1a4a, 0x7a4ae8], metalness: 0.3, roughness: 0.2, opacity: 0.95,
    emissive: [0x4a1a8a, 0xb47aff], emissiveIntensity: 1.4,
    note: "選択的ブルームで発光させる。夜景前提。派手さと形状保持のバランスを測る。",
  },
};

export interface Recipe {
  id: string;
  experiment: string;
  title: string;
  place: keyof typeof PLACES;
  time: keyof typeof TIMES;
  mode: Mode;
  group?: "controlled" | "best";
  cameraOverride?: Partial<PlaceDef["camera"]>;
  material?: keyof typeof MATERIALS;
  growthOrder?: GrowthOrder;
  performance?: {
    shots: Array<{ camera: Partial<PlaceDef["camera"]> & { lng?: number; lat?: number }; durationSec: number; ease?: "linear" | "inout" | "out" }>;
    timeFrom?: string;
    timeTo?: string;
    loop?: boolean;
    progressCurve?: "linear" | "tide";
  };
  seed: number;
  codeVersion: string;
}

export const CODE_VERSION = "0.1.0";

// EXP-003: Controlled isolates material at sunset; Best Look explores lighting.
// Both sets share the Tokyo base camera.
export const RECIPES: Recipe[] = [
  { id: "exp021-breath-core", experiment: "EXP-021", title: "BREATHING CITY（試作）/ 街は自分の時間で呼吸する", place: "tokyo", time: "sunset", mode: "growth", growthOrder: "center-out", cameraOverride: { lng: 139.7585, lat: 35.6858, distance: 2100, heading: 320, pitch: -52 }, performance: { loop: true, progressCurve: "tide", shots: [{ camera: { lng: 139.7585, lat: 35.6858, distance: 2100, heading: 320, pitch: -52 }, durationSec: 24, ease: "inout" }, { camera: { lng: 139.7585, lat: 35.6858, distance: 1300, heading: 285, pitch: -38 }, durationSec: 24, ease: "inout" }] }, seed: 42, codeVersion: CODE_VERSION },
  { id: "exp003-porcelain", experiment: "EXP-003", title: "MATERIAL TOKYO / 陶器", place: "tokyo", time: "sunset", mode: "material", group: "controlled", material: "porcelain", seed: 1, codeVersion: CODE_VERSION },
  { id: "exp003-gold", experiment: "EXP-003", title: "MATERIAL TOKYO / 黄金", place: "tokyo", time: "sunset", mode: "material", group: "controlled", material: "gold", performance: { shots: [{ camera: { distance: 360, pitch: -22, heading: 30 }, durationSec: 8, ease: "inout" }, { camera: { distance: 500, pitch: -32, heading: 55 }, durationSec: 8, ease: "inout" }, { camera: { distance: 660, pitch: -45, heading: 78 }, durationSec: 8, ease: "inout" }], loop: true }, seed: 1, codeVersion: CODE_VERSION },
  { id: "exp003-chrome", experiment: "EXP-003", title: "MATERIAL TOKYO / クローム", place: "tokyo", time: "sunset", mode: "material", group: "controlled", material: "chrome", seed: 1, codeVersion: CODE_VERSION },
  { id: "exp003-ice", experiment: "EXP-003", title: "MATERIAL TOKYO / 氷", place: "tokyo", time: "sunset", mode: "material", group: "controlled", material: "ice", seed: 1, codeVersion: CODE_VERSION },
  { id: "exp003-glass", experiment: "EXP-003", title: "MATERIAL TOKYO / ガラス", place: "tokyo", time: "sunset", mode: "material", group: "controlled", material: "glass", seed: 1, codeVersion: CODE_VERSION },
  { id: "exp003-crystal", experiment: "EXP-003", title: "MATERIAL TOKYO / 発光クリスタル", place: "tokyo", time: "sunset", mode: "material", group: "controlled", material: "crystal", seed: 1, codeVersion: CODE_VERSION },
  // EXP-003: Best Look lighting by material.
  { id: "exp003-best-porcelain", experiment: "EXP-003", title: "MATERIAL TOKYO [Best] / 陶器", place: "tokyo", time: "sunset", mode: "material", group: "best", material: "porcelain", seed: 1, codeVersion: CODE_VERSION },
  { id: "exp003-best-gold", experiment: "EXP-003", title: "MATERIAL TOKYO [Best] / 黄金", place: "tokyo", time: "sunset", mode: "material", group: "best", material: "gold", seed: 1, codeVersion: CODE_VERSION },
  { id: "exp003-best-chrome", experiment: "EXP-003", title: "MATERIAL TOKYO [Best] / クローム", place: "tokyo", time: "day", mode: "material", group: "best", material: "chrome", seed: 1, codeVersion: CODE_VERSION },
  { id: "exp003-best-ice", experiment: "EXP-003", title: "MATERIAL TOKYO [Best] / 氷", place: "tokyo", time: "day", mode: "material", group: "best", material: "ice", seed: 1, codeVersion: CODE_VERSION },
  { id: "exp003-best-glass", experiment: "EXP-003", title: "MATERIAL TOKYO [Best] / ガラス", place: "tokyo", time: "day", mode: "material", group: "best", material: "glass", seed: 1, codeVersion: CODE_VERSION },
  { id: "exp003-best-crystal", experiment: "EXP-003", title: "MATERIAL TOKYO [Best] / 発光クリスタル", place: "tokyo", time: "night", mode: "material", group: "best", material: "crystal", seed: 1, codeVersion: CODE_VERSION },
  // EXP-002: growth orders. Duration is fixed in the viewer (12s) so orders compare fairly.
  { id: "exp002-center-out", experiment: "EXP-002", title: "CITY GROWTH / 中心→外側", place: "tokyo", time: "sunset", mode: "growth", growthOrder: "center-out", performance: { shots: [{ camera: { distance: 400, pitch: -30, heading: 30 }, durationSec: 8, ease: "inout" }, { camera: { distance: 540, pitch: -42, heading: 55 }, durationSec: 8, ease: "inout" }, { camera: { distance: 680, pitch: -50, heading: 78 }, durationSec: 8, ease: "inout" }], loop: true }, seed: 42, codeVersion: CODE_VERSION },
  { id: "exp002-low-to-high", experiment: "EXP-002", title: "CITY GROWTH / 低→高", place: "tokyo", time: "sunset", mode: "growth", growthOrder: "low-to-high", seed: 42, codeVersion: CODE_VERSION },
  { id: "exp002-random", experiment: "EXP-002", title: "CITY GROWTH / ランダム", place: "tokyo", time: "sunset", mode: "growth", growthOrder: "random", seed: 42, codeVersion: CODE_VERSION },
  { id: "exp002-giants-last", experiment: "EXP-002", title: "CITY GROWTH / 巨大ビル最後", place: "tokyo", time: "sunset", mode: "growth", growthOrder: "giants-last", seed: 42, codeVersion: CODE_VERSION },
  // EXP-004: change only the camera with gold at sunset.
  { id: "exp004-standard", experiment: "EXP-004", title: "CAMERA / 標準", place: "tokyo", time: "sunset", mode: "material", material: "gold", group: "controlled", seed: 1, codeVersion: CODE_VERSION },
  { id: "exp004-low-angle", experiment: "EXP-004", title: "CAMERA / ローアングル", place: "tokyo", time: "sunset", mode: "material", material: "gold", group: "controlled", cameraOverride: { distance: 380, pitch: -18 }, seed: 1, codeVersion: CODE_VERSION },
  { id: "exp004-top-down", experiment: "EXP-004", title: "CAMERA / 真俯瞰", place: "tokyo", time: "sunset", mode: "material", material: "gold", group: "controlled", cameraOverride: { distance: 700, pitch: -85 }, seed: 1, codeVersion: CODE_VERSION },
  { id: "exp004-diorama", experiment: "EXP-004", title: "CAMERA / ジオラマ俯瞰", place: "tokyo", time: "sunset", mode: "material", material: "gold", group: "controlled", cameraOverride: { distance: 900, pitch: -55 }, seed: 1, codeVersion: CODE_VERSION },
  // EXP-001: LIFT-LITE. True geometric cutting is out of Navara's reach;
  // this isolates the building cluster in a dark void (no terrain/photo)
  // to test the floating-diorama composition. Recorded as LITE, not LIFT.
  { id: "exp001-lift-tokyo", experiment: "EXP-001", title: "CITY LIFT-LITE / 東京駅・浮遊ジオラマ", place: "tokyo", time: "night", mode: "lift", performance: { shots: [{ camera: { distance: 520, pitch: -38, heading: 30 }, durationSec: 8, ease: "inout" }, { camera: { distance: 620, pitch: -44, heading: 55 }, durationSec: 8, ease: "inout" }, { camera: { distance: 720, pitch: -48, heading: 78 }, durationSec: 8, ease: "inout" }], loop: true }, seed: 7, codeVersion: CODE_VERSION },
  { id: "exp001-lift-tocho", experiment: "EXP-001", title: "CITY LIFT-LITE / 都庁・浮遊ジオラマ", place: "tocho", time: "night", mode: "lift", seed: 7, codeVersion: CODE_VERSION },
];

export function effectiveCamera(recipe: Recipe): PlaceDef["camera"] {
  return { ...PLACES[recipe.place].camera, ...recipe.cameraOverride };
}

export function getRecipe(id: string | null): Recipe {
  return RECIPES.find((r) => r.id === id) ?? RECIPES[0];
}

// Deterministic hash for the "random" growth order: same seed + same
// building centroid must always give the same rank (reproducibility).
export function seededRank(seed: number, x: number, y: number): number {
  let h = seed * 374761393 + Math.round(x * 1e6) * 668265263 + Math.round(y * 1e6) * 974634211;
  h = (h ^ (h >> 13)) * 1274126177;
  return ((h ^ (h >> 16)) >>> 0) / 4294967295;
}
