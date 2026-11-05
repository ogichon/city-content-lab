#!/usr/bin/env python3
"""CCL EXP-008 — Takeshiba scene from the converted OBJ.
District = porcelain, Tokyo Port City Takeshiba (the dataset's only LOD4,
BIM-derived) = gold. Basemap = GSI aerial photo in the same local frame.

Usage:
  blender -b -noaudio -P build_takeshiba_scene.py -- --obj takeshiba.obj \
      [--basemap takeshiba-photo-pale-faded.jpg] [--nadir] \
      [--cam X Y Z --target X Y Z --lens MM] \
      [--samples N] [--width W] [--height-px H] --out render.png
OBJ vertices are (east, north, height) local metres, Z-up data.
"""
import bpy, os, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def argval(flag, default):
    return argv[argv.index(flag) + 1] if flag in argv else default

OBJ = argval("--obj", "")
OUT = argval("--out", "/tmp/takeshiba-check.png")
SAMPLES = int(argval("--samples", "8"))
HERO = "bldg_4ab21821-b73b-4ef2-95b4-de2859999fc7"  # Tokyo Port City Takeshiba (LOD4)
CENTRE = Vector((-94, 7, 0))  # hero centre from the conversion scan

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath=OBJ, up_axis='Z', forward_axis='Y')
print(f"CCL: imported {len(bpy.context.scene.objects)} objects", flush=True)

def make_mat(name, color, metallic, roughness, lift=0.16):
    m = bpy.data.materials.new(name=name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = color
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = roughness
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = color
    em.inputs["Strength"].default_value = 1.0
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.inputs[0].default_value = lift
    nt.links.new(b.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], nt.nodes["Material Output"].inputs[0])
    return m

porcelain = make_mat("CCL_tk_porcelain", (0.92, 0.89, 0.83, 1.0), 0.0, 0.35)
gold = make_mat("CCL_tk_gold", (0.83, 0.55, 0.12, 1.0), 1.0, 0.30)
ground_mat = make_mat("CCL_tk_ground", (0.72, 0.74, 0.75, 1.0), 0.0, 0.95, lift=0.0)

hero = None
for obj in bpy.context.scene.objects:
    if obj.type != 'MESH':
        continue
    obj.data.materials.clear()
    if obj.name.startswith(HERO):
        obj.data.materials.append(gold)
        hero = obj
    else:
        obj.data.materials.append(porcelain)
if hero is None:
    raise SystemExit("Port City Takeshiba object not found after import")
print(f"CCL: hero dims=({hero.dimensions.x:.0f}x{hero.dimensions.y:.0f}x{hero.dimensions.z:.0f})", flush=True)

if "--basemap" in argv:
    ex = [float(v) for v in argval("--basemap-extent", "-1250 1350 -700 1550").split()]
    tex = bpy.data.images.load(os.path.abspath(argval("--basemap", "")))
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
    print(f"CCL: basemap over x[{ex[0]},{ex[1]}] y[{ex[2]},{ex[3]}]", flush=True)
else:
    bpy.ops.mesh.primitive_plane_add(location=(0, 0, 0))
    g = bpy.context.active_object
    g.name = "CCL_ground"
    g.scale = (4000, 4000, 1)
    g.data.materials.append(ground_mat)

world = bpy.data.worlds.new("CCL_world")
bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.72, 0.78, 0.84, 1.0)
bg.inputs[1].default_value = 1.0

sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", 'SUN'))
bpy.context.scene.collection.objects.link(sun)
sun.rotation_euler = (0.9, 0.2, -0.6)

cam_data = bpy.data.cameras.new("Cam")
cam = bpy.data.objects.new("Cam", cam_data)
bpy.context.scene.collection.objects.link(cam)
bpy.context.scene.camera = cam
if "--nadir" in argv:
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = float(argval("--ortho-scale", "2700"))
    cam.location = (CENTRE.x, CENTRE.y + 300, 1500)
    cam.rotation_euler = (0, 0, 0)
    print("CCL: nadir ortho camera", flush=True)
elif "--cam" in argv and "--target" in argv:
    ci, ti = argv.index("--cam"), argv.index("--target")
    cam.location = Vector(tuple(float(argv[ci + k]) for k in range(1, 4)))
    tgt = Vector(tuple(float(argv[ti + k]) for k in range(1, 4)))
    cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam_data.lens = float(argval("--lens", "32"))
    print(f"CCL: camera {tuple(round(v) for v in cam.location)} -> {tuple(round(v) for v in tgt)} lens {cam_data.lens}", flush=True)
else:
    # Default: from Tokyo Bay (south-east), hero tower against the district.
    cam.location = (950, -950, 430)
    direction = Vector((CENTRE.x, CENTRE.y, 60)) - cam.location
    cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    cam_data.lens = 32
cam_data.clip_end = 20000

scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.use_adaptive_sampling = True
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.render.resolution_x = int(argval("--width", "640"))
scene.render.resolution_y = int(argval("--height-px", "360"))
scene.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print(f"CCL: rendered {OUT}", flush=True)
