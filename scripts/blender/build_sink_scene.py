#!/usr/bin/env python3
"""CCL EXP-022 — Sunken city (Blender film lane).
One rule: only the water level rises. Buildings are ONE porcelain material
with the waterline split inside the shader (world Z vs a single Value node
named WATER_LEVEL): porcelain above, deep desaturated teal-dark below.
The water is a large translucent plane at Z = WATER_LEVEL over the GSI
photo basemap. Nishita sky is camera-only (EXP-009 Light Path pattern).

Datum (verified 2026-11-13 by scanning data/takeshiba/takeshiba.obj):
heights are metres above the height datum; building bases cluster at
Z = 2-3 m (mode 3 m, Shibaura ground), so scene ground datum ~= 2.5 m.
Hero bldg_4ab21821 (Tokyo Port City Takeshiba): z -2.5 .. 206.6 (209 m).

Usage:
  blender -b -noaudio -P build_sink_scene.py -- --level 8.5 \
      --out output/blender/exp022-still-w6.png [--samples 96] \
      [--cam X Y Z --target X Y Z --lens MM] [--sun RX RY RZ] \
      [--sky-elev D] [--sky-rot D] [--world-strength F] [--look NAME] \
      [--exposure F] [--width PX] [--height-px PX]
Levels used for the key stills: w0 = -0.05 (dry, plane under the photo),
w6 = 8.5 (ground 2.5 + 6), w12 = 14.5 (ground 2.5 + 12).
"""
import bpy, os, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def argval(flag, default):
    return argv[argv.index(flag) + 1] if flag in argv else default

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OBJ = argval("--obj", os.path.join(ROOT, "data/takeshiba/takeshiba.obj"))
BASEMAP = argval("--basemap", os.path.join(ROOT, "assets/basemap/takeshiba-photo.jpg"))
OUT = argval("--out", "/tmp/sink-check.png")
SAMPLES = int(argval("--samples", "96"))
LEVEL = float(argval("--level", "8.5"))
HERO = "bldg_4ab21821-b73b-4ef2-95b4-de2859999fc7"  # Tokyo Port City Takeshiba (LOD4)
HERO_CENTRE = Vector((-94, 7, 0))

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath=OBJ, up_axis='Z', forward_axis='Y')
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
print(f"CCL SINK: imported {len(meshes)} mesh objects", flush=True)

# --- Verify the Z datum from the imported data itself -------------------
import collections
hist = collections.Counter()
hero_top = None
for o in meshes:
    zmin = min((o.matrix_world @ Vector(c)).z for c in o.bound_box)
    hist[round(zmin)] += 1
    if o.name.startswith(HERO):
        hero_top = max((o.matrix_world @ Vector(c)).z for c in o.bound_box)
mode_z = hist.most_common(1)[0][0]
print(f"CCL SINK: building-base Z mode = {mode_z} m "
      f"(bases 1..5 m: {sum(v for k, v in hist.items() if 1 <= k <= 5)}/{len(meshes)} objects); "
      f"hero top Z = {hero_top:.1f} m; WATER_LEVEL = {LEVEL} m", flush=True)

# --- The one material: porcelain with an in-shader waterline split ------
def porcelain_sink_material():
    m = bpy.data.materials.new("CCL_sink_porcelain")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")

    wl = nt.nodes.new("ShaderNodeValue")
    wl.name = "WATER_LEVEL"
    wl.label = "WATER_LEVEL"
    wl.outputs[0].default_value = LEVEL

    # factor = clamp((WATER_LEVEL + 0.2 - worldZ) / 0.4, 0, 1)
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs["Vector"])
    add = nt.nodes.new("ShaderNodeMath"); add.operation = 'ADD'
    add.inputs[1].default_value = 0.2
    nt.links.new(wl.outputs[0], add.inputs[0])
    sub = nt.nodes.new("ShaderNodeMath"); sub.operation = 'SUBTRACT'
    nt.links.new(add.outputs[0], sub.inputs[0])
    nt.links.new(sep.outputs["Z"], sub.inputs[1])
    div = nt.nodes.new("ShaderNodeMath"); div.operation = 'DIVIDE'
    div.inputs[1].default_value = 0.4
    nt.links.new(sub.outputs[0], div.inputs[0])
    clamp = nt.nodes.new("ShaderNodeClamp")
    nt.links.new(div.outputs[0], clamp.inputs["Value"])

    def lit_branch(color, roughness, lift):
        b = nt.nodes.new("ShaderNodeBsdfPrincipled")
        b.inputs["Base Color"].default_value = color
        b.inputs["Metallic"].default_value = 0.0
        b.inputs["Roughness"].default_value = roughness
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = color
        em.inputs["Strength"].default_value = 1.0
        mix = nt.nodes.new("ShaderNodeMixShader")
        mix.inputs[0].default_value = lift
        nt.links.new(b.outputs[0], mix.inputs[1])
        nt.links.new(em.outputs[0], mix.inputs[2])
        return mix.outputs[0]

    above = lit_branch((0.92, 0.89, 0.83, 1.0), 0.35, 0.16)   # porcelain (EXP-003/008 family)
    below = lit_branch((0.030, 0.088, 0.098, 1.0), 0.55, 0.04)  # submerged: deep desaturated teal-dark
    split = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(clamp.outputs["Result"], split.inputs[0])
    nt.links.new(above, split.inputs[1])
    nt.links.new(below, split.inputs[2])
    nt.links.new(split.outputs[0], out.inputs["Surface"])
    return m

porcelain = porcelain_sink_material()
for o in meshes:
    o.data.materials.clear()
    o.data.materials.append(porcelain)
print("CCL SINK: one porcelain/waterline material on all buildings", flush=True)

# --- Basemap ground (GSI photo, same local frame as EXP-008) ------------
ex = [float(v) for v in argval("--basemap-extent", "-1250 1350 -700 1550").split()]
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
print(f"CCL SINK: basemap over x[{ex[0]},{ex[1]}] y[{ex[2]},{ex[3]}]", flush=True)

# --- Water: one translucent plane at the level ---------------------------
wm = bpy.data.materials.new("CCL_sink_water")
wm.use_nodes = True
wb = wm.node_tree.nodes["Principled BSDF"]
wb.inputs["Base Color"].default_value = (0.012, 0.070, 0.090, 1.0)
wb.inputs["Metallic"].default_value = 0.0
wb.inputs["Roughness"].default_value = 0.07
wb.inputs["Alpha"].default_value = 0.5
bpy.ops.mesh.primitive_plane_add(location=(0, 200, LEVEL))
w = bpy.context.active_object
w.name = "CCL_water"
w.scale = (6000, 6000, 1)
w.data.materials.append(wm)
print(f"CCL SINK: water plane at Z = {LEVEL} m (alpha 0.5, roughness 0.07)", flush=True)

# --- World: flat light + Nishita sky for the camera only (EXP-009) -------
world = bpy.data.worlds.new("CCL_world")
bpy.context.scene.world = world
world.use_nodes = True
nt = world.node_tree
bg = nt.nodes["Background"]
bg.inputs[0].default_value = (0.72, 0.78, 0.84, 1.0)
bg.inputs[1].default_value = float(argval("--world-strength", "0.30"))
sky = nt.nodes.new("ShaderNodeTexSky")
sky.sky_type = 'NISHITA'
sky.sun_elevation = float(argval("--sky-elev", "6")) * 3.14159265 / 180.0
sky.sun_rotation = float(argval("--sky-rot", "235")) * 3.14159265 / 180.0
sky.altitude = 0.0
bg_cam = nt.nodes.new("ShaderNodeBackground")
bg_cam.inputs[1].default_value = float(argval("--sky-strength", "1.0"))
nt.links.new(sky.outputs["Color"], bg_cam.inputs[0])
lp = nt.nodes.new("ShaderNodeLightPath")
wmix = nt.nodes.new("ShaderNodeMixShader")
out = nt.nodes["World Output"]
nt.links.new(lp.outputs["Is Camera Ray"], wmix.inputs[0])
nt.links.new(bg.outputs[0], wmix.inputs[1])
nt.links.new(bg_cam.outputs[0], wmix.inputs[2])
nt.links.new(wmix.outputs[0], out.inputs[0])
print("CCL SINK: nishita camera-sky, flat world lights (dramatic grade)", flush=True)

# --- Low warm sun ---------------------------------------------------------
sun_data = bpy.data.lights.new("Sun", 'SUN')
sun_data.energy = float(argval("--sun-energy", "3.5"))
sun_data.color = (1.0, 0.72, 0.47)
sun = bpy.data.objects.new("Sun", sun_data)
bpy.context.scene.collection.objects.link(sun)
if "--sun" in argv:
    si = argv.index("--sun")
    sun.rotation_euler = tuple(float(argv[si + k]) * 3.14159265 / 180.0 for k in range(1, 4))
else:
    sun.rotation_euler = tuple(d * 3.14159265 / 180.0 for d in (74, 6, -52))

# --- Grade ----------------------------------------------------------------
vs = bpy.context.scene.view_settings
try:
    vs.look = argval("--look", "AgX - High Contrast")
except Exception as e:
    print(f"CCL SINK: look set failed: {e}", flush=True)
vs.exposure = float(argval("--exposure", "0"))

# --- Camera: wide oblique from the bay, hero tower prominent --------------
cam_data = bpy.data.cameras.new("Cam")
cam = bpy.data.objects.new("Cam", cam_data)
bpy.context.scene.collection.objects.link(cam)
bpy.context.scene.camera = cam
if "--cam" in argv and "--target" in argv:
    ci, ti = argv.index("--cam"), argv.index("--target")
    cam.location = Vector(tuple(float(argv[ci + k]) for k in range(1, 4)))
    tgt = Vector(tuple(float(argv[ti + k]) for k in range(1, 4)))
else:
    cam.location = Vector((760, -790, 235))
    tgt = Vector((HERO_CENTRE.x, HERO_CENTRE.y, 25))
cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
cam_data.lens = float(argval("--lens", "35"))
cam_data.clip_end = 30000
print(f"CCL SINK: camera {tuple(round(v) for v in cam.location)} -> {tuple(round(v) for v in tgt)} lens {cam_data.lens}", flush=True)

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
print(f"CCL SINK: rendered {OUT}", flush=True)
