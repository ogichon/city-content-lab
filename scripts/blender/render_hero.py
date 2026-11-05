#!/usr/bin/env python3
"""CITY CONTENT LAB — hero-material test (H4): base material everywhere,
hero material only on meshes whose bbox centre falls inside a region.

Usage:
  blender -b scene.blend -noaudio -P render_hero.py -- \
      --base porcelain --hero gold --region XMIN XMAX YMIN YMAX \
      --output out.png [--samples 32] [--debug]
--debug colours the hero region pure red (region calibration).
Region is in scene coordinates (metres, centred origin, ground z=0).
"""
import bpy, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def argval(flag, default):
    return argv[argv.index(flag) + 1] if flag in argv else default

BASE = argval("--base", "porcelain")
HERO = argval("--hero", "gold")
OUTPUT = argval("--output", "/tmp/hero.png")
SAMPLES = int(argval("--samples", "32"))
DEBUG = "--debug" in argv
ri = argv.index("--region")
XMIN, XMAX, YMIN, YMAX = (float(argv[ri + k]) for k in range(1, 5))

SPECS = {
    "porcelain": ((0.92, 0.89, 0.83, 1.0), 0.0, 0.35),
    "gold":      ((0.83, 0.55, 0.12, 1.0), 1.0, 0.30),
    "chrome":    ((0.72, 0.76, 0.80, 1.0), 1.0, 0.12),
    "red":       ((1.0, 0.0, 0.0, 1.0), 0.0, 0.5),
}
def make_mat(name):
    color, metallic, roughness = SPECS[name]
    m = bpy.data.materials.new(name=f"CCL_hero_{name}")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = color
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = roughness
    return m

base_mat = make_mat(BASE)
hero_mat = make_mat("red" if DEBUG else HERO)
hero_count = 0
for obj in bpy.data.objects:
    if obj.type != "MESH":
        continue
    if "ground" in obj.name.lower():
        continue
    bb = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    cen = sum(bb, Vector()) / 8
    obj.data.materials.clear()
    if XMIN <= cen.x <= XMAX and YMIN <= cen.y <= YMAX:
        obj.data.materials.append(hero_mat)
        hero_count += 1
    else:
        obj.data.materials.append(base_mat)
print(f"CCL: hero meshes = {hero_count} (region x[{XMIN},{XMAX}] y[{YMIN},{YMAX}])", flush=True)

scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.use_adaptive_sampling = True
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.render.resolution_x = 960
scene.render.resolution_y = 540
scene.render.filepath = OUTPUT
bpy.ops.render.render(write_still=True)
print(f"CCL: rendered {OUTPUT}", flush=True)
