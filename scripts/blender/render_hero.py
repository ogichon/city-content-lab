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
# Optional sun/exposure overrides (same contract as render_materials.py).
if "--sun" in argv:
    i = argv.index("--sun")
    sun = bpy.data.objects.get("Sun")
    if sun:
        sun.rotation_euler = (float(argv[i + 1]), float(argv[i + 2]), float(argv[i + 3]))
        print(f"CCL: sun rotation set to {tuple(sun.rotation_euler)}", flush=True)
if "--exposure" in argv:
    scene.view_settings.exposure = float(argval("--exposure", "0"))
    print(f"CCL: exposure set to {scene.view_settings.exposure}", flush=True)
# Optional georeferenced basemap plane (z=0.05), same contract as render_lift.py.
BASEMAP = argval("--basemap", None)
if BASEMAP:
    bi = argv.index("--basemap-extent")
    BXMIN, BXMAX, BYMIN, BYMAX = (float(argv[bi + k]) for k in range(1, 5))
    bpy.ops.mesh.primitive_plane_add(location=((BXMIN + BXMAX) / 2, (BYMIN + BYMAX) / 2, 0.05))
    plane = bpy.context.active_object
    plane.name = "CCL_basemap"
    plane.scale = ((BXMAX - BXMIN) / 2, (BYMAX - BYMIN) / 2, 1)
    bpy.ops.object.transform_apply(scale=True)
    mm = bpy.data.materials.new(name="CCL_basemap_mat")
    mm.use_nodes = True
    tex = mm.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(BASEMAP)
    mm.node_tree.links.new(tex.outputs["Color"], mm.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    mm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.95
    plane.data.materials.append(mm)
    print(f"CCL: basemap {BASEMAP} over x[{BXMIN},{BXMAX}] y[{BYMIN},{BYMAX}]", flush=True)

if "--cam" in argv and "--target" in argv:
    ci, ti = argv.index("--cam"), argv.index("--target")
    cam = scene.camera
    cam.location = Vector(tuple(float(argv[ci + k]) for k in range(1, 4)))
    tgt = Vector(tuple(float(argv[ti + k]) for k in range(1, 4)))
    cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
    print(f"CCL: camera set to {tuple(round(v) for v in cam.location)} -> target {tuple(round(v) for v in tgt)}", flush=True)
if "--lens" in argv:
    scene.camera.data.lens = float(argval("--lens", "50"))
    print(f"CCL: lens set to {scene.camera.data.lens}mm", flush=True)

scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.use_adaptive_sampling = True
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.render.resolution_x = int(argval("--width", "960"))
scene.render.resolution_y = int(argval("--height-px", "540"))
scene.render.filepath = OUTPUT
bpy.ops.render.render(write_still=True)
print(f"CCL: rendered {OUTPUT}", flush=True)
