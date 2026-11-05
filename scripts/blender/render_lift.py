#!/usr/bin/env python3
"""CITY CONTENT LAB — CITY LIFT spike: cut a rectangular district out of the
city and float it above its hole on a visible slab.

Works on per-object scenes (Tokyo Station scene). Meshes whose bbox centre
falls inside the region are lifted by --height; a concrete slab box is added
under them and a dark pit plate in the hole to sell the depth.

Usage:
  blender -b tokyo_station_scene.blend -noaudio -P render_lift.py -- \
      --region XMIN XMAX YMIN YMAX --height 60 --output out.png [--samples 32]
Calibrated station district: region -420 -120 120 300.
"""
import bpy, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def argval(flag, default):
    return argv[argv.index(flag) + 1] if flag in argv else default

OUTPUT = argval("--output", "/tmp/lift.png")
SAMPLES = int(argval("--samples", "32"))
HEIGHT = float(argval("--height", "60"))
SLAB = 30.0  # slab thickness (m)
ri = argv.index("--region")
XMIN, XMAX, YMIN, YMAX = (float(argv[ri + k]) for k in range(1, 5))

def make_mat(name, color, metallic=0.0, roughness=0.4):
    m = bpy.data.materials.new(name=name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = roughness
    return m

porcelain = make_mat("CCL_lift_porcelain", (0.92, 0.89, 0.83), 0.0, 0.35)
concrete = make_mat("CCL_lift_concrete", (0.42, 0.38, 0.34), 0.0, 0.9)
pit_mat = make_mat("CCL_lift_pit", (0.015, 0.018, 0.028), 0.0, 1.0)

VOID = "--void" in argv  # hide everything outside the region (EXP-001 lesson)
lifted = 0
for obj in bpy.data.objects:
    if obj.type != "MESH":
        continue
    if "ground" in obj.name.lower():
        if VOID:
            obj.hide_render = True
        continue
    bb = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    cen = sum(bb, Vector()) / 8
    obj.data.materials.clear()
    obj.data.materials.append(porcelain)
    if XMIN <= cen.x <= XMAX and YMIN <= cen.y <= YMAX:
        obj.location.z += HEIGHT
        lifted += 1
    elif VOID:
        obj.hide_render = True
print(f"CCL: lifted meshes = {lifted} by {HEIGHT}m (void={VOID})", flush=True)

cx, cy = (XMIN + XMAX) / 2, (YMIN + YMAX) / 2
sx, sy = XMAX - XMIN, YMAX - YMIN

def add_box(name, loc, scale, mat):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    box = bpy.context.active_object
    box.name = name
    box.scale = scale
    bpy.ops.object.transform_apply(scale=True)
    box.data.materials.append(mat)
    return box

# Slab under the lifted district: top at building base + HEIGHT - small inset
add_box("CCL_slab", (cx, cy, HEIGHT - SLAB / 2), (sx / 2, sy / 2, SLAB / 2), concrete)
# Optional basemap: a georeferenced photo plane at z=0.05 (below the pit
# plate's top at 0.8, so the hole stays dark). Extent = the scene coords the
# image covers. Skipped in void mode (no ground context by definition).
BASEMAP = argval("--basemap", None)
if BASEMAP and not VOID:
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

# Pit plate in the hole (dark, at ground level) — meaningless in void mode.
if not VOID:
    add_box("CCL_pit", (cx, cy, 0.4), (sx / 2, sy / 2, 0.4), pit_mat)
else:
    # Shadow catcher at z=0: the slab's soft shadow below is what makes the
    # float height readable when the surroundings are gone.
    bpy.ops.mesh.primitive_plane_add(location=(cx, cy, 0))
    catcher = bpy.context.active_object
    catcher.name = "CCL_shadow_catcher"
    catcher.scale = (sx * 1.6, sy * 1.6, 1)
    try:
        catcher.is_shadow_catcher = True
    except Exception as e:
        print(f"CCL: shadow catcher unavailable ({e})", flush=True)
    scene0 = bpy.context.scene
    scene0.render.film_transparent = False

scene = bpy.context.scene
if "--cam" in argv and "--target" in argv:
    ci, ti = argv.index("--cam"), argv.index("--target")
    cam = scene.camera
    cam.location = Vector(tuple(float(argv[ci + k]) for k in range(1, 4)))
    tgt = Vector(tuple(float(argv[ti + k]) for k in range(1, 4)))
    direction = tgt - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    print(f"CCL: camera set to {tuple(round(v) for v in cam.location)} -> target {tuple(round(v) for v in tgt)}", flush=True)
if "--pullback" in argv:
    d = float(argval("--pullback", "0"))
    cam = scene.camera
    look = cam.rotation_euler.to_matrix() @ Vector((0, 0, -1))
    look.normalize()
    cam.location = cam.location - look * d
    print(f"CCL: camera pulled back {d}m", flush=True)
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
