import { PLACES, type Recipe, type PlaceDef } from "./recipes";

const smoothstep = (x: number) => { const t = Math.max(0, Math.min(1, x)); return t * t * (3 - 2 * t); };

// EXP-022: the water level is the performance's only moving part besides the
// camera. Over the total duration it rises 0 -> maxHeight during 0-45%
// (smoothstep), holds 45-65%, then falls back to 0 during 65-100%.
// Pure and deterministic: same elapsed time always yields the same level.
export function waterLevelAt(water: { maxHeight: number }, ratio: number): number {
  if (ratio < 0.45) return water.maxHeight * smoothstep(ratio / 0.45);
  if (ratio < 0.65) return water.maxHeight;
  return water.maxHeight * (1 - smoothstep((ratio - 0.65) / 0.35));
}

// ?stage=<recipeId> is the sole autoplay convention. Each shot is a travel
// from the preceding target (initially effectiveCamera) to base + overrides.
export function stageFrame(recipe: Recipe, elapsedSec: number) {
  const performance = recipe.performance!;
  const total = performance.shots.reduce((sum, shot) => sum + shot.durationSec, 0);
  const finished = !performance.loop && elapsedSec >= total;
  const elapsed = finished ? total : Math.max(0, elapsedSec) % total;
  const base = PLACES[recipe.place].camera;
  let from = { ...base, ...recipe.cameraOverride };
  let remaining = elapsed;
  for (let i = 0; i < performance.shots.length; i++) {
    const shot = performance.shots[i];
    const to = { ...base, ...shot.camera };
    if (remaining <= shot.durationSec || i === performance.shots.length - 1) {
      const t = Math.min(1, remaining / shot.durationSec);
      const eased = shot.ease === "inout" ? t * t * (3 - 2 * t) : shot.ease === "out" ? 1 - (1 - t) ** 3 : t;
      const camera = { ...from };
      for (const key of Object.keys(camera) as Array<keyof PlaceDef["camera"]>) {
        const delta = key === "heading" ? ((to[key] - from[key]) % 360 + 540) % 360 - 180 : to[key] - from[key];
        camera[key] = from[key] + delta * eased;
      }
      camera.heading = (camera.heading % 360 + 360) % 360;
      // EXP-017: stage choreography is authoritative for lift too. The old
      // extra orbit (+1.2 deg/s) and distance breathing compounded with the
      // shot interpolation and pushed the camera into the lifted slab field,
      // so they are no longer applied during performances.
      return { camera, shotIndex: i, progress: performance.progressCurve === "tide" ? 0.5 - 0.5 * Math.cos(2 * Math.PI * (elapsed / total)) : elapsed / total, waterLevel: performance.water ? waterLevelAt(performance.water, elapsed / total) : 0, playing: !finished };
    }
    remaining -= shot.durationSec;
    from = to;
  }
  throw new Error("Stage requires at least one shot");
}
