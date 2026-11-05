#!/usr/bin/env python3
"""CITY CONTENT LAB — hero material for SINGLE-MESH scenes (e.g. Tocho).

Some saved scenes merge the whole city into one mesh object, so materials
cannot be assigned per building object. This variant assigns two materials
to the same mesh and selects faces by polygon-centroid region (world coords).

Usage:
  blender -b scene.blend -noaudio -P render_hero_split.py -- \
      --object 53394525_bldg_6677 --base porcelain --hero gold \
      --region XMIN XMAX YMIN YMAX --output out.png [--samples 32] [--debug]
--debug colours the hero faces pure red (region calibration).
Calibrated regions:
  Tokyo Station scene: use render_hero.py (per-object) instead.
  Tocho (shinjuku_tocho_scene.blend): region -340 -120 120 280 = the
  Metropolitan Government Building twin towers (verified by debug render).
"""
import bpy, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def argval(flag, default):
    return argv[argv.index(flag) + 1] if flag in argv else default

OBJ_NAME = argval("--object", "")
BASE = argval("--base", "porcelain")
HERO = argval("--hero", "gold")
OUTPUT = argval("--output", "/tmp/hero-split.png")
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
    m = bpy.data.materials.new(name=f"CCL_split_{name}")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = color
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = roughness
    return m

base_mat = make_mat(BASE)
hero_mat = make_mat("red" if DEBUG else HERO)

target = bpy.data.objects.get(OBJ_NAME) if OBJ_NAME else None
if target is None:
    meshes = [o for o in bpy.data.objects if o.type == "MESH" and "ground" not in o.name.lower()]
    target = max(meshes, key=lambda o: len(o.data.polygons))
me = target.data
me.materials.clear()
me.materials.append(base_mat)
me.materials.append(hero_mat)
mw = target.matrix_world
hero_faces = 0
for p in me.polygons:
    c = mw @ p.center
    if XMIN <= c.x <= XMAX and YMIN <= c.y <= YMAX:
        p.material_index = 1
        hero_faces += 1
    else:
        p.material_index = 0
print(f"CCL: hero faces = {hero_faces} / {len(me.polygons)} on {target.name}", flush=True)

for o in bpy.data.objects:
    if o.type == "MESH" and o != target and "ground" not in o.name.lower():
        o.data.materials.clear()
        o.data.materials.append(base_mat)

scene = bpy.context.scene
if "--pullback" in argv:
    d = float(argval("--pullback", "0"))
    cam = scene.camera
    look = cam.rotation_euler.to_matrix() @ Vector((0, 0, -1))
    look.normalize()
    cam.location = cam.location - look * d
    print(f"CCL: camera pulled back {d}m -> {tuple(round(v) for v in cam.location)}", flush=True)
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
