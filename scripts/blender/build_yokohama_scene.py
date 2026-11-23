#!/usr/bin/env python3
"""CCL EXP-024 — Yokohama Minatomirai porcelain test scene.
Minimal house-treatment still for the second-city verification: ONE
porcelain material on all buildings, GSI photo basemap in the same local
frame, the EXP-022 round-2 locked dramatic light (low warm sun, flat
world, camera-only Nishita sky, AgX High Contrast, exposure -0.3).
No water, no animation — the question is whether the LOD3 detail reads.

Usage:
  blender -b -noaudio -P build_yokohama_scene.py -- \
      --obj data/yokohama2024/yokohama-mm.obj \
      --basemap assets/basemap/yokohama-mm-photo.jpg \
      --basemap-extent "-750 1850 -800 700" \
      --cam 1350 -780 165 --target 40 -30 50 --lens 33 \
      --samples 96 --out output/blender/exp024-yokohama-mm-porcelain.png
OBJ vertices are (east, north, height) local metres, Z-up, anchored at
Yokohama Landmark Tower (35.4546, 139.6311), EPSG:6677 plane frame.
"""
import bpy, os, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def argval(flag, default):
    return argv[argv.index(flag) + 1] if flag in argv else default

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OBJ = argval("--obj", os.path.join(ROOT, "data/yokohama2024/yokohama-mm.obj"))
BASEMAP = argval("--basemap", os.path.join(ROOT, "assets/basemap/yokohama-mm-photo.jpg"))
OUT = argval("--out", "/tmp/yokohama-check.png")
SAMPLES = int(argval("--samples", "96"))

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath=OBJ, up_axis='Z', forward_axis='Y')
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
print(f"CCL YOKOHAMA: imported {len(meshes)} mesh objects", flush=True)

# --- Datum self-check from the imported data ----------------------------
import collections
hist = collections.Counter()
tallest = (None, -1e9)
for o in meshes:
    zs = [(o.matrix_world @ Vector(c)).z for c in o.bound_box]
    hist[round(min(zs))] += 1
    if max(zs) > tallest[1]:
        tallest = (o.name, max(zs))
mode_z = hist.most_common(1)[0][0]
print(f"CCL YOKOHAMA: building-base Z mode = {mode_z} m "
      f"(bases 0..6 m: {sum(v for k, v in hist.items() if 0 <= k <= 6)}/{len(meshes)}); "
      f"tallest = {tallest[0]} top {tallest[1]:.1f} m", flush=True)

# --- The one material: porcelain (EXP-003/008/022 family) ----------------
def porcelain_material():
    m = bpy.data.materials.new("CCL_yokohama_porcelain")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.92, 0.89, 0.83, 1.0)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Roughness"].default_value = 0.35
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0.92, 0.89, 0.83, 1.0)
    em.inputs["Strength"].default_value = 1.0
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.inputs[0].default_value = 0.16  # emission lift, house value
    nt.links.new(b.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], nt.nodes["Material Output"].inputs[0])
    return m

porcelain = porcelain_material()
for o in meshes:
    o.data.materials.clear()
    o.data.materials.append(porcelain)
print("CCL YOKOHAMA: one porcelain material on all buildings", flush=True)

# --- Basemap ground (GSI photo, same local frame) -------------------------
ex = [float(v) for v in argval("--basemap-extent", "-750 1850 -800 700").split()]
tex = bpy.data.images.load(os.path.abspath(BASEMAP))
bm = bpy.data.materials.new("CCL_basemap")
bm.use_nodes = True
bsdf = bm.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Roughness"].default_value = 1.0
node = bm.node_tree.nodes.new("ShaderNodeTexImage")
node.image = tex
bm.node_tree.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
bpy.ops.mesh.primitive_plane_add(location=((ex[0] + ex[1]) / 2, (ex[2] + ex[3]) / 2, 0.0))
g = bpy.context.active_object
g.name = "CCL_basemap"
g.scale = ((ex[1] - ex[0]) / 2, (ex[3] - ex[2]) / 2, 1)
g.data.materials.append(bm)
print(f"CCL YOKOHAMA: basemap over x[{ex[0]},{ex[1]}] y[{ex[2]},{ex[3]}]", flush=True)

# --- World: flat light + Nishita sky for the camera only (EXP-009) --------
world = bpy.data.worlds.new("CCL_world")
bpy.context.scene.world = world
world.use_nodes = True
nt = world.node_tree
bg = nt.nodes["Background"]
bg.inputs[0].default_value = (0.72, 0.78, 0.84, 1.0)
bg.inputs[1].default_value = 0.15
sky = nt.nodes.new("ShaderNodeTexSky")
sky.sky_type = 'NISHITA'
sky.sun_elevation = 4.5 * 3.14159265 / 180.0
sky.sun_rotation = 210 * 3.14159265 / 180.0
sky.altitude = 0.0
bg_cam = nt.nodes.new("ShaderNodeBackground")
bg_cam.inputs[1].default_value = 0.55
nt.links.new(sky.outputs["Color"], bg_cam.inputs[0])
lp = nt.nodes.new("ShaderNodeLightPath")
wmix = nt.nodes.new("ShaderNodeMixShader")
out = nt.nodes["World Output"]
nt.links.new(lp.outputs["Is Camera Ray"], wmix.inputs[0])
nt.links.new(bg.outputs[0], wmix.inputs[1])
nt.links.new(bg_cam.outputs[0], wmix.inputs[2])
nt.links.new(wmix.outputs[0], out.inputs[0])
print("CCL YOKOHAMA: nishita camera-sky, flat world 0.15 (locked grade)", flush=True)

# --- Low warm sun (EXP-022 round-2 locked values) --------------------------
sun_data = bpy.data.lights.new("Sun", 'SUN')
sun_data.energy = 4.5
sun_data.color = (1.0, 0.72, 0.47)
sun = bpy.data.objects.new("Sun", sun_data)
bpy.context.scene.collection.objects.link(sun)
sun.rotation_euler = tuple(d * 3.14159265 / 180.0 for d in (86.5, -25, 0))

# --- Grade ------------------------------------------------------------------
vs = bpy.context.scene.view_settings
try:
    vs.look = "AgX - High Contrast"
except Exception as e:
    print(f"CCL YOKOHAMA: look set failed: {e}", flush=True)
vs.exposure = -0.3

# --- Camera ------------------------------------------------------------------
cam_data = bpy.data.cameras.new("Cam")
cam = bpy.data.objects.new("Cam", cam_data)
bpy.context.scene.collection.objects.link(cam)
bpy.context.scene.camera = cam
if "--cam" in argv and "--target" in argv:
    ci, ti = argv.index("--cam"), argv.index("--target")
    cam.location = Vector(tuple(float(argv[ci + k]) for k in range(1, 4)))
    tgt = Vector(tuple(float(argv[ti + k]) for k in range(1, 4)))
else:
    cam.location = Vector((1350, -780, 165))
    tgt = Vector((40, -30, 50))
cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
cam_data.lens = float(argval("--lens", "33"))
cam_data.clip_end = 30000
print(f"CCL YOKOHAMA: camera {tuple(round(v) for v in cam.location)} -> {tuple(round(v) for v in tgt)} lens {cam_data.lens}", flush=True)

scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.use_adaptive_sampling = True
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.render.resolution_x = int(argval("--width", "1920"))
scene.render.resolution_y = int(argval("--height-px", "1080"))
scene.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print(f"CCL YOKOHAMA: rendered {OUT}", flush=True)
