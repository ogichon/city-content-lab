#!/usr/bin/env python3
"""CCL EXP-007 — build the Expo 2025 scene from the converted OBJ and take a
verification render. Ring object: frn_600e2980-7014-40b6-86eb-396abd0a14b8
(677x677m footprint, BIM). Venue = porcelain, ring = gold (hero pattern).

Usage:
  blender -b -noaudio -P build_expo_scene.py -- --obj expo.obj \
      --out /tmp/expo-check.png [--samples 8] [--width 640] [--height-px 360]
OBJ vertices are (east, north, height) local metres, Z-up data.
"""
import bpy, os, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def argval(flag, default):
    return argv[argv.index(flag) + 1] if flag in argv else default

OBJ = argval("--obj", "")
OUT = argval("--out", "/tmp/expo-check.png")
SAMPLES = int(argval("--samples", "8"))
RING = "frn_600e2980-7014-40b6-86eb-396abd0a14b8"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath=OBJ, up_axis='Z', forward_axis='Y')
print(f"CCL: imported {len(bpy.context.scene.objects)} objects", flush=True)

def make_mat(name, color, metallic, roughness, lift=0.16):
    """Principled + a small same-colour emission lift. This dataset carries
    open point-cloud shells whose interiors receive no light in Cycles and
    render pure black (either winding); the lift keeps them readable as
    matte surface without changing their position or silhouette."""
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

porcelain = make_mat("CCL_expo_porcelain", (0.92, 0.89, 0.83, 1.0), 0.0, 0.35)
gold = make_mat("CCL_expo_gold", (0.83, 0.55, 0.12, 1.0), 1.0, 0.30)
ground_mat = make_mat("CCL_expo_ground", (0.72, 0.74, 0.75, 1.0), 0.0, 0.95)

ring = None
# frn_5ce668fc is the Water Plaza basin: an open shell of mostly vertical
# faces whose interior receives no light in Cycles and renders pure black
# (verified by isolation renders + emission test, 2026-11-06). It is a real
# feature — the plaza is water — so hide the shell and let the basemap
# photo's actual water show through.
HIDE = {"frn_5ce668fc-3ee6-4830-a70a-ae9e6ae5276e"}
for obj in bpy.context.scene.objects:
    if obj.type != 'MESH':
        continue
    if obj.name in HIDE:
        obj.hide_render = True
        print(f"CCL: hidden (water-plaza basin shell): {obj.name}", flush=True)
        continue
    if "--textured" in argv:
        # EXP-014: keep the OBJ importer's MTL materials (real PLATEAU
        # appearance textures, converted with --textures). No porcelain,
        # no gold — the full-texture direction chosen by the owner.
        if obj.name.startswith(RING):
            ring = obj
        continue
    obj.data.materials.clear()
    if obj.name.startswith(RING):
        obj.data.materials.append(gold)
        ring = obj
    else:
        obj.data.materials.append(porcelain)
if "--textured" in argv:
    # EXP-014 lift: some LOD3 shells are wound so their outward faces get
    # no light at all and textured surfaces render pure black (verified:
    # world 2.0 + flipped sun changes nothing). The porcelain route hid
    # this with its 16% emission lift; give textured materials the same
    # floor — emission fed by their own texture (or base colour).
    lift = float(argval("--lift", "0.18"))
    done = set()
    for mat in bpy.data.materials:
        if mat is None or mat.name in done or not mat.use_nodes:
            continue
        done.add(mat.name)
        nt = mat.node_tree
        out = next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'), None)
        princ = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if out is None or princ is None or not out.inputs['Surface'].links:
            continue
        tex = next((n for n in nt.nodes if n.type == 'TEX_IMAGE'), None)
        emis = nt.nodes.new('ShaderNodeEmission')
        emis.inputs['Strength'].default_value = lift
        if tex is not None:
            nt.links.new(tex.outputs['Color'], emis.inputs['Color'])
        else:
            emis.inputs['Color'].default_value = princ.inputs['Base Color'].default_value
        add = nt.nodes.new('ShaderNodeAddShader')
        nt.links.new(princ.outputs['BSDF'], add.inputs[0])
        nt.links.new(emis.outputs['Emission'], add.inputs[1])
        nt.links.new(add.outputs['Shader'], out.inputs['Surface'])
    print(f"CCL: texture lift {lift} applied to {len(done)} materials", flush=True)

if ring is None:
    raise SystemExit("ring object not found after import")
bb = [ring.matrix_world @ Vector(c) for c in ring.bound_box]
cen = sum(bb, Vector()) / 8
print(f"CCL: ring centre=({cen.x:.0f},{cen.y:.0f},{cen.z:.0f}) dims=({ring.dimensions.x:.0f}x{ring.dimensions.y:.0f}x{ring.dimensions.z:.0f})", flush=True)

# Ground: basemap photo plane at z=6.3 (OBJ heights carry a ~6.4m datum
# offset) when --basemap is given, else a plain big plane.
if "--surround" in argv:
    # Surrounding city (EXP-012): a second OBJ in the same local frame
    # (standard PLATEAU Osaka meshes around Yumeshima, converted with the
    # same anchor/CRS), rendered porcelain like the venue's non-ring
    # buildings. It fills the frame edges the venue-only photo plane
    # leaves empty in high/wide shots.
    before = set(bpy.context.scene.objects)
    bpy.ops.wm.obj_import(filepath=os.path.abspath(argval("--surround", "")), up_axis='Z', forward_axis='Y')
    n_sur = 0
    for obj in set(bpy.context.scene.objects) - before:
        if obj.type != 'MESH':
            continue
        obj.data.materials.clear()
        obj.data.materials.append(porcelain)
        n_sur += 1
    print(f"CCL: surroundings imported: {n_sur} objects", flush=True)

if "--terrain" in argv:
    # DEM terrain (scripts/convert_dem.py, same local frame): photo-draped
    # relief that rises through the flat basemap plane where the real
    # ground does (island rim, mounds). UVs are generated from x/y in the
    # basemap extent so the drape matches the flat plane seamlessly.
    tex_path = os.path.abspath(argval("--basemap", ""))
    tex = bpy.data.images.load(tex_path)
    ex = [float(v) for v in argval("--basemap-extent", "-850 860 -760 640").split()]
    tm = bpy.data.materials.new("CCL_terrain")
    tm.use_nodes = True
    tbsdf = tm.node_tree.nodes["Principled BSDF"]
    tbsdf.inputs["Roughness"].default_value = 1.0
    tnode = tm.node_tree.nodes.new("ShaderNodeTexImage")
    tnode.image = tex
    tm.node_tree.links.new(tnode.outputs["Color"], tbsdf.inputs["Base Color"])
    before = set(bpy.context.scene.objects)
    bpy.ops.wm.obj_import(filepath=os.path.abspath(argval("--terrain", "")), up_axis='Z', forward_axis='Y')
    for obj in set(bpy.context.scene.objects) - before:
        if obj.type != 'MESH':
            continue
        obj.data.materials.clear()
        obj.data.materials.append(tm)
        uv = obj.data.uv_layers.new(name="drape")
        for loop in obj.data.loops:
            v = obj.data.vertices[loop.vertex_index].co
            uv.data[loop.index].uv = ((v.x - ex[0]) / (ex[1] - ex[0]),
                                      (v.y - ex[2]) / (ex[3] - ex[2]))
        print(f"CCL: terrain draped: {obj.name} ({len(obj.data.vertices)} verts)", flush=True)

if "--basemap" in argv:
    ex = [float(v) for v in argval("--basemap-extent", "-850 860 -760 640").split()]
    import os
    tex = bpy.data.images.load(os.path.abspath(argval("--basemap", "")))
    bm = bpy.data.materials.new("CCL_basemap")
    bm.use_nodes = True
    bsdf = bm.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 1.0
    node = bm.node_tree.nodes.new("ShaderNodeTexImage")
    node.image = tex
    bm.node_tree.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
    bpy.ops.mesh.primitive_plane_add(location=((ex[0] + ex[1]) / 2, (ex[2] + ex[3]) / 2, 6.3))
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

# World sky (the saved PLATEAU scenes carry one; an empty scene has none and
# renders black under a lone sun).
world = bpy.data.worlds.new("CCL_world")
bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.72, 0.78, 0.84, 1.0)
bg.inputs[1].default_value = 1.0
if argval("--sky", "flat") == "nishita":
    # Camera-only physical sky (EXP-009): the world doubles as the IBL, so
    # feeding the sky into lighting blows the scene out. Light Path splits
    # it — flat world lights, sky only where the camera looks.
    sky = world.node_tree.nodes.new("ShaderNodeTexSky")
    sky.sky_type = 'NISHITA'
    sky.sun_elevation = float(argval("--sky-elev", "28")) * 3.14159265 / 180.0
    sky.sun_rotation = float(argval("--sky-rot", "210")) * 3.14159265 / 180.0
    sky.altitude = 0.0
    nt = world.node_tree
    bg_cam = nt.nodes.new("ShaderNodeBackground")
    bg_cam.inputs[1].default_value = float(argval("--sky-strength", "1.0"))
    nt.links.new(sky.outputs["Color"], bg_cam.inputs[0])
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    out = nt.nodes["World Output"]
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    nt.links.new(bg.outputs[0], mix.inputs[1])
    nt.links.new(bg_cam.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    print("CCL: nishita camera-sky", flush=True)

# Sun + camera: high oblique from the sea (south-west), whole venue in frame
sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", 'SUN'))
bpy.context.scene.collection.objects.link(sun)
if "--sun" in argv:
    si = argv.index("--sun")
    sun.rotation_euler = tuple(float(argv[si + k]) * 3.14159265 / 180.0 for k in range(1, 4))
else:
    sun.rotation_euler = (0.9, 0.2, -0.6)
if "--world-strength" in argv:
    # Dramatic grade (user direction 2026-11-06): dim the ambient fill so
    # shadows sink and forms read by light, not by overall brightness.
    bg.inputs[1].default_value = float(argval("--world-strength", "1.0"))
if "--look" in argv:
    try:
        bpy.context.scene.view_settings.look = argval("--look", "None")
        print(f"CCL: look = {bpy.context.scene.view_settings.look}", flush=True)
    except Exception as e:
        print(f"CCL: look set failed: {e}", flush=True)
if "--exposure" in argv:
    bpy.context.scene.view_settings.exposure = float(argval("--exposure", "0"))
cam_data = bpy.data.cameras.new("Cam")
cam = bpy.data.objects.new("Cam", cam_data)
bpy.context.scene.collection.objects.link(cam)
bpy.context.scene.camera = cam
if "--nadir" in argv:
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = float(argval("--ortho-scale", "1900"))
    cam.location = (cen.x, cen.y, 1500)
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
    cam.location = (cen.x - 1500, cen.y - 1500, 950)
    direction = Vector((cen.x, cen.y, 10)) - cam.location
    cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    cam_data.lens = 32
cam_data.clip_end = 20000  # default 1000m clips the whole venue at this range

scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.use_adaptive_sampling = True
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.render.resolution_x = int(argval("--width", "640"))
scene.render.resolution_y = int(argval("--height-px", "360"))
if "--anim" in argv:
    # Motion check: keyframe the camera between --cam/--target (frame 1)
    # and --cam2/--target2 (last frame), render a PNG sequence into OUT
    # (a directory). Stills judge LOD1/flat scenes too harshly; parallax
    # is part of the work. Assemble with ffmpeg afterwards.
    frames = int(argval("--frames", "96"))
    ci = argv.index("--cam2")
    ti = argv.index("--target2")
    cam2 = Vector(tuple(float(argv[ci + k]) for k in range(1, 4)))
    tgt2 = Vector(tuple(float(argv[ti + k]) for k in range(1, 4)))
    # --frame-start lets a killed long render resume mid-sequence:
    # keyframes live on absolute frames, so the motion is unchanged.
    scene.frame_start, scene.frame_end = int(argval("--frame-start", "1")), frames
    # The builder has already applied --cam/--target: that pose is frame 1.
    cam.keyframe_insert("location", frame=1)
    cam.keyframe_insert("rotation_euler", frame=1)
    cam.location = cam2
    cam.rotation_euler = (tgt2 - cam2).to_track_quat('-Z', 'Y').to_euler()
    cam.keyframe_insert("location", frame=frames)
    cam.keyframe_insert("rotation_euler", frame=frames)
    if "--cam-mid" in argv and "--target-mid" in argv:
        # Optional mid pose (three-act moves: detail -> rise -> reveal).
        mi = argv.index("--cam-mid")
        ti2 = argv.index("--target-mid")
        mid = Vector(tuple(float(argv[mi + k]) for k in range(1, 4)))
        tm = Vector(tuple(float(argv[ti2 + k]) for k in range(1, 4)))
        cam.location = mid
        cam.rotation_euler = (tm - mid).to_track_quat('-Z', 'Y').to_euler()
        cam.keyframe_insert("location", frame=frames // 2)
        cam.keyframe_insert("rotation_euler", frame=frames // 2)
    os.makedirs(OUT, exist_ok=True)
    scene.render.filepath = os.path.join(OUT, "f_")
    scene.render.image_settings.file_format = 'PNG'
    bpy.ops.render.render(animation=True)
    print(f"CCL: animated {frames} frames -> {OUT}", flush=True)
else:
    scene.render.filepath = OUT
    bpy.ops.render.render(write_still=True)
    print(f"CCL: rendered {OUT}", flush=True)
