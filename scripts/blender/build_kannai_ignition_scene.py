#!/usr/bin/env python3
"""CCL EXP-025 motion test — 『窓の数だけ』 Kannai ignition wave.
Extends build_yokohama_glow_scene.py (same porcelain / blue-hour recipe,
Kannai data) with ONE rule animated: every real opening (845 bldg:Window /
bldg:Door elements extracted from the CityGML) ignites in strict order of
its real measured distance from Kannai Station, and stays on. The wave is
a constant-speed front: ignition frame is linear in distance. Per-opening
brightness/colour keep the EXP-025 deterministic md5 palette (variation
only — the SET of lights and their ORDER are both pure data).

Kannai Station (JR) reference point: lat 35.44306, lon 139.63722,
transformed EPSG:6697 -> EPSG:6677 with the Landmark Tower anchor
(35.4546, 139.6311) subtracted, exactly as the converter does:
local (east, north) = (553.0, -1281.3) m.

Camera: Bashamichi street level, the exp025-kannai-street still's axis
(322,-731) -> (470,-822), lowered to 4 m; a slow 6 m glide along the same
axis over the shot. Never above the rooftops.

Usage (sequence):
  blender -b -noaudio -P build_kannai_ignition_scene.py -- \
      --frames-dir output/blender/exp025-kannai-wave-frames \
      --samples 32 --width 1280 --height-px 720
Usage (single preview frame):
  ... --frame 45 --out /tmp/prev45.png
OBJ vertices are (east, north, height) local metres, Z-up, anchored at
Yokohama Landmark Tower (35.4546, 139.6311), EPSG:6677 plane frame.
"""
import bpy, os, sys, json, math, hashlib
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def argval(flag, default):
    return argv[argv.index(flag) + 1] if flag in argv else default

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OBJ = argval("--obj", os.path.join(ROOT, "data/yokohama2024/yokohama-kannai.obj"))
OPENINGS = argval("--openings", os.path.join(ROOT, "data/yokohama2024/yokohama-kannai-openings.obj"))
BASEMAP = argval("--basemap", os.path.join(ROOT, "assets/basemap/yokohama-kannai-photo.jpg"))
BASEMAP_EXTENT = argval("--basemap-extent", "-620 660 -1500 -440")
FRAMES_DIR = argval("--frames-dir", os.path.join(ROOT, "output/blender/exp025-kannai-wave-frames"))
OUT = argval("--out", "")
FRAME_ONLY = int(argval("--frame", "0"))
SAMPLES = int(argval("--samples", "32"))
N_FRAMES = int(argval("--n-frames", "72"))
STATION = tuple(float(v) for v in argval("--station", "553.0 -1281.3").split())
WAVE_FIRST = int(argval("--wave-first", "4"))    # frame at which d=0 ignites
WAVE_LAST = int(argval("--wave-last", "62"))     # frame at which d=dmax ignites
RAMP = int(argval("--ramp", "3"))                # frames per opening fade-on
LIFT = float(argval("--lift", "0.04"))
SUN_ENERGY = float(argval("--sun-energy", "0.3"))
SUN_ROT = tuple(float(v) for v in argval("--sun", "80 -15 140").split())
WORLD_STRENGTH = float(argval("--world-strength", "0.06"))
EXPOSURE = float(argval("--exposure", "-0.2"))
GLIDE_M = float(argval("--glide", "6.0"))

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath=OBJ, up_axis='Z', forward_axis='Y')
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
print(f"CCL WAVE: imported {len(meshes)} building objects", flush=True)

# --- Porcelain (identical to EXP-025 Kannai stills) -------------------------
def porcelain_material():
    m = bpy.data.materials.new("CCL_yokohama_porcelain_dusk")
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
    mix.inputs[0].default_value = LIFT
    nt.links.new(b.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], nt.nodes["Material Output"].inputs[0])
    return m

porcelain = porcelain_material()
for o in meshes:
    o.data.materials.clear()
    o.data.materials.append(porcelain)
print(f"CCL WAVE: porcelain on all buildings (lift {LIFT})", flush=True)

# --- Openings: per-opening material, md5 palette, distance-ordered ignition -
PALETTE = [
    ((1.0, 0.78, 0.50), 0.35), ((1.0, 0.73, 0.44), 0.7),
    ((1.0, 0.71, 0.41), 1.1),  ((1.0, 0.68, 0.37), 1.5),
    ((1.0, 0.66, 0.35), 1.9),  ((1.0, 0.63, 0.32), 2.2),
    ((1.0, 0.60, 0.29), 2.4),  ((1.0, 0.58, 0.27), 2.4),
    ((1.0, 0.75, 0.47), 1.3),  ((1.0, 0.65, 0.34), 1.7),
    ((1.0, 0.70, 0.39), 2.1),  ((1.0, 0.62, 0.31), 0.5),
]

before = set(bpy.context.scene.objects)
bpy.ops.wm.obj_import(filepath=OPENINGS, up_axis='Z', forward_axis='Y')
op_objects = [o for o in bpy.context.scene.objects if o not in before and o.type == 'MESH']

def centroid(o):
    cs = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return sum(cs, Vector()) / 8.0

records = []
for o in op_objects:
    c = centroid(o)
    d = math.hypot(c.x - STATION[0], c.y - STATION[1])
    records.append((o, c, d))
dmax = max(d for _, _, d in records)
print(f"CCL WAVE: {len(records)} openings; distance {min(d for _,_,d in records):.0f}..{dmax:.0f} m from station {STATION}", flush=True)

for o, c, d in records:
    h = int(hashlib.md5(o.name.encode()).hexdigest(), 16)
    col, strength = PALETTE[h % len(PALETTE)]
    m = bpy.data.materials.new(f"CCL_glow_{o.name}")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*col, 1.0)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs[0], out.inputs[0])
    o.data.materials.clear()
    o.data.materials.append(m)
    f_ig = WAVE_FIRST + round((WAVE_LAST - WAVE_FIRST) * d / dmax)
    s = em.inputs["Strength"]
    s.default_value = 0.0
    s.keyframe_insert(data_path="default_value", frame=1)
    s.keyframe_insert(data_path="default_value", frame=f_ig)
    s.default_value = strength
    s.keyframe_insert(data_path="default_value", frame=min(f_ig + RAMP, N_FRAMES))
    if nt.animation_data and nt.animation_data.action:
        for fc in nt.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
    o["dist_m"] = round(d, 1)
    o["ignite_frame"] = f_ig

sidecar = [{"name": o.name, "dist_m": round(d, 1),
            "ignite_frame": WAVE_FIRST + round((WAVE_LAST - WAVE_FIRST) * d / dmax)}
           for o, _, d in sorted(records, key=lambda r: r[2])]
print(f"CCL WAVE: ignition keyed for {len(sidecar)} openings "
      f"(frames {WAVE_FIRST}..{WAVE_LAST}, ramp {RAMP})", flush=True)

# --- Basemap ground, darkened + cooled for dusk (identical to stills) -------
ex = [float(v) for v in BASEMAP_EXTENT.split()]
tex = bpy.data.images.load(os.path.abspath(BASEMAP))
bm = bpy.data.materials.new("CCL_basemap_dusk")
bm.use_nodes = True
nt = bm.node_tree
bsdf = nt.nodes["Principled BSDF"]
bsdf.inputs["Roughness"].default_value = 1.0
node = nt.nodes.new("ShaderNodeTexImage")
node.image = tex
mul = nt.nodes.new("ShaderNodeMixRGB")
mul.blend_type = 'MULTIPLY'
mul.inputs[0].default_value = 1.0
mul.inputs[2].default_value = (0.30, 0.34, 0.46, 1.0)
nt.links.new(node.outputs["Color"], mul.inputs[1])
nt.links.new(mul.outputs["Color"], bsdf.inputs["Base Color"])
bpy.ops.mesh.primitive_plane_add(location=((ex[0] + ex[1]) / 2, (ex[2] + ex[3]) / 2, 0.0))
g = bpy.context.active_object
g.name = "CCL_basemap"
g.scale = ((ex[1] - ex[0]) / 2, (ex[3] - ex[2]) / 2, 1)
g.data.materials.append(bm)
print(f"CCL WAVE: basemap over x[{ex[0]},{ex[1]}] y[{ex[2]},{ex[3]}]", flush=True)

# --- World: deep-blue ambient + Nishita band for the camera only ------------
world = bpy.data.worlds.new("CCL_world")
bpy.context.scene.world = world
world.use_nodes = True
nt = world.node_tree
bg = nt.nodes["Background"]
bg.inputs[0].default_value = (0.16, 0.22, 0.34, 1.0)
bg.inputs[1].default_value = WORLD_STRENGTH
sky = nt.nodes.new("ShaderNodeTexSky")
sky.sky_type = 'NISHITA'
sky.sun_elevation = 2.0 * 3.14159265 / 180.0
sky.sun_rotation = 235 * 3.14159265 / 180.0
sky.altitude = 0.0
bg_cam = nt.nodes.new("ShaderNodeBackground")
bg_cam.inputs[1].default_value = 0.35
nt.links.new(sky.outputs["Color"], bg_cam.inputs[0])
lp = nt.nodes.new("ShaderNodeLightPath")
wmix = nt.nodes.new("ShaderNodeMixShader")
out = nt.nodes["World Output"]
nt.links.new(lp.outputs["Is Camera Ray"], wmix.inputs[0])
nt.links.new(bg.outputs[0], wmix.inputs[1])
nt.links.new(bg_cam.outputs[0], wmix.inputs[2])
nt.links.new(wmix.outputs[0], out.inputs[0])

# --- Weak warm sun, low in the west ------------------------------------------
sun_data = bpy.data.lights.new("Sun", 'SUN')
sun_data.energy = SUN_ENERGY
sun_data.color = (1.0, 0.62, 0.38)
sun = bpy.data.objects.new("Sun", sun_data)
bpy.context.scene.collection.objects.link(sun)
sun.rotation_euler = tuple(d * 3.14159265 / 180.0 for d in SUN_ROT)

# --- Grade ---------------------------------------------------------------------
vs = bpy.context.scene.view_settings
try:
    vs.look = "AgX - High Contrast"
except Exception as e:
    print(f"CCL WAVE: look set failed: {e}", flush=True)
vs.exposure = EXPOSURE

# --- Camera: street-still axis, 4 m height, slow glide along the axis --------
cam_data = bpy.data.cameras.new("Cam")
cam = bpy.data.objects.new("Cam", cam_data)
bpy.context.scene.collection.objects.link(cam)
bpy.context.scene.camera = cam
cam_start = Vector((322.0, -731.0, 4.0))
target = Vector((470.0, -822.0, 5.0))
axis = Vector((target.x - cam_start.x, target.y - cam_start.y, 0.0))
axis.normalize()
cam_end = cam_start + axis * GLIDE_M
cam.location = cam_start
cam.rotation_euler = (target - cam_start).to_track_quat('-Z', 'Y').to_euler()
cam_data.lens = 42.0
cam_data.clip_end = 30000
cam.keyframe_insert(data_path="location", frame=1)
cam.location = cam_end
cam.keyframe_insert(data_path="location", frame=N_FRAMES)
if cam.animation_data and cam.animation_data.action:
    for fc in cam.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
print(f"CCL WAVE: camera {tuple(round(v,1) for v in cam_start)} -> glide {GLIDE_M} m to "
      f"{tuple(round(v,1) for v in cam_end)}, lens 42", flush=True)

scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.use_adaptive_sampling = True
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.render.resolution_x = int(argval("--width", "1280"))
scene.render.resolution_y = int(argval("--height-px", "720"))
scene.render.fps = 24
scene.frame_start = 1
scene.frame_end = N_FRAMES

os.makedirs(FRAMES_DIR, exist_ok=True)
with open(os.path.join(FRAMES_DIR, "ignition-order.json"), "w") as fh:
    json.dump({"station_local_m": list(STATION), "station_latlon": [35.44306, 139.63722],
               "wave_first_frame": WAVE_FIRST, "wave_last_frame": WAVE_LAST,
               "ramp_frames": RAMP, "dmax_m": round(dmax, 1),
               "openings": sidecar}, fh, indent=1)

if FRAME_ONLY:
    scene.frame_set(FRAME_ONLY)
    scene.render.filepath = OUT
    bpy.ops.render.render(write_still=True)
    print(f"CCL WAVE: preview frame {FRAME_ONLY} -> {OUT}", flush=True)
else:
    scene.render.filepath = os.path.join(FRAMES_DIR, "frame_")
    bpy.ops.render.render(animation=True)
    print(f"CCL WAVE: rendered {N_FRAMES} frames -> {FRAMES_DIR}", flush=True)
