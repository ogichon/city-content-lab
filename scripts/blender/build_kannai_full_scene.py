#!/usr/bin/env python3
"""CCL EXP-025 FULL PIECE — 『窓の数だけ』 Kannai ignition wave, 75 s.
Sibling of build_kannai_ignition_scene.py (same porcelain / blue-hour
recipe, same Kannai data, same distance-ordered ignition rule). What
changes vs the 72-frame motion test, per the EXP-025 design lock:

- Timeline: 1800 frames @ 24 fps (75 s), 1920x1080, 64 samples.
- Ignition: WAVE_FIRST=24, WAVE_LAST=1320 — the front crosses the full
  788 m in 55 s (constant speed 0.608 m/frame, linear in real measured
  distance from Kannai Station, 3-frame ramp, stays on). All 845
  openings lit by frame 1320; Act 3 plays fully lit.
- Palette cap (motion-test finding: strongest buckets blow out to
  cream/white): any bucket with strength > 1.7 is capped to 1.6 and its
  colour deepened toward amber (g -0.06, b -0.07). Buckets <= 1.7 keep
  the EXP-025 md5 palette verbatim.
- Camera, three acts (cuts at act boundaries; Act 2 -> 3 continuous):
  Act 1 (f1-360, 0-15 s): street level on the open plaza south of the
    node, slow 12 m push north toward the node heart — the wave is born
    here. (Two earlier candidates failed on sight: (395,-1055) is inside
    a 32.6 m tower; the NW context axis at street level faces a wall at
    ~10 m and its visible bases ignite only after Act 1. The plaza
    camera sits inside the ignition zone: the near complex's panes light
    ~f170-220, the pilotis row follows by f300 — progression in frame.)
  Act 2 (f361-1440, 15-60 s): Bashamichi corridor, starting further SE
    than the street still ((352,-749) vs still (322,-731); the first
    candidate (369,-760) proved to be inside a 12.6 m block and the
    Act 1 candidate (395,-1055) inside a 32.6 m tower — both replaced
    with downward-raycast-verified open street points), retreating
    NW at walking pace to the still's own composition (326,-733) while
    looking SE down the corridor — the front sweeps far->near and
    overtakes the retreating camera around f960-1000.
  Act 3 (f1441-1800, 60-75 s): the only rise — continuous from Act 2's
    end pose, up to ~39 m, target easing from the corridor to the
    district's northern cluster (465,-980); lens widens 42 -> 36 during
    the rise. Closes on the fully lit district (the count 845).

Usage (sequence, Mac GPU):
  blender -b -noaudio -P build_kannai_full_scene.py -- --device GPU \
      --frames-dir output/blender/exp025-full-frames
Usage (single frame):
  ... --frame 846 --out /tmp/act2.png
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
FRAMES_DIR = argval("--frames-dir", os.path.join(ROOT, "output/blender/exp025-full-frames"))
OUT = argval("--out", "")
FRAME_ONLY = int(argval("--frame", "0"))
SAMPLES = int(argval("--samples", "64"))
N_FRAMES = int(argval("--n-frames", "1800"))
STATION = tuple(float(v) for v in argval("--station", "553.0 -1281.3").split())
WAVE_FIRST = int(argval("--wave-first", "24"))    # frame at which d=0 ignites
WAVE_LAST = int(argval("--wave-last", "1320"))    # frame at which d=dmax ignites
RAMP = int(argval("--ramp", "3"))                 # frames per opening fade-on
LIFT = float(argval("--lift", "0.04"))
SUN_ENERGY = float(argval("--sun-energy", "0.3"))
SUN_ROT = tuple(float(v) for v in argval("--sun", "80 -15 140").split())
WORLD_STRENGTH = float(argval("--world-strength", "0.06"))
EXPOSURE = float(argval("--exposure", "-0.2"))
CAP_STRENGTH = float(argval("--cap-strength", "1.6"))   # palette cap (see docstring)
CAP_ABOVE = float(argval("--cap-above", "1.7"))         # cap applies above this
def vec3(flag, default):
    return Vector(tuple(float(v) for v in argval(flag, default).split()))
A1_START = vec3("--a1-start", "533 -1202 4.2")   # south plaza, preview-verified (SB2)
A1_END = vec3("--a1-end", "529 -1190 4.2")
A1_TARGET = vec3("--a1-target", "498 -1092 5")
A3_END = vec3("--a3-end", "294 -702 37")
A3_TARGET = vec3("--a3-target", "465 -980 0")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath=OBJ, up_axis='Z', forward_axis='Y')
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
print(f"CCL FULL: imported {len(meshes)} building objects", flush=True)

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
print(f"CCL FULL: porcelain on all buildings (lift {LIFT})", flush=True)

# --- Openings: per-opening material, md5 palette (capped), distance ignition
PALETTE = [
    ((1.0, 0.78, 0.50), 0.35), ((1.0, 0.73, 0.44), 0.7),
    ((1.0, 0.71, 0.41), 1.1),  ((1.0, 0.68, 0.37), 1.5),
    ((1.0, 0.66, 0.35), 1.9),  ((1.0, 0.63, 0.32), 2.2),
    ((1.0, 0.60, 0.29), 2.4),  ((1.0, 0.58, 0.27), 2.4),
    ((1.0, 0.75, 0.47), 1.3),  ((1.0, 0.65, 0.34), 1.7),
    ((1.0, 0.70, 0.39), 2.1),  ((1.0, 0.62, 0.31), 0.5),
]

def cap_palette(col, strength):
    """Motion-test fix: cap the blow-out tier, deepen toward amber."""
    if strength > CAP_ABOVE:
        return (col[0], max(col[1] - 0.06, 0.0), max(col[2] - 0.07, 0.0)), CAP_STRENGTH
    return col, strength

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
print(f"CCL FULL: {len(records)} openings; distance {min(d for _,_,d in records):.0f}..{dmax:.0f} m from station {STATION}", flush=True)

n_capped = 0
for o, c, d in records:
    h = int(hashlib.md5(o.name.encode()).hexdigest(), 16)
    col, strength = PALETTE[h % len(PALETTE)]
    col, strength = cap_palette(col, strength)
    if strength == CAP_STRENGTH:
        n_capped += 1
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
print(f"CCL FULL: ignition keyed for {len(sidecar)} openings "
      f"(frames {WAVE_FIRST}..{WAVE_LAST}, ramp {RAMP}); palette-capped {n_capped}", flush=True)

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
print(f"CCL FULL: basemap over x[{ex[0]},{ex[1]}] y[{ex[2]},{ex[3]}]", flush=True)

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
    print(f"CCL FULL: look set failed: {e}", flush=True)
vs.exposure = EXPOSURE

# --- Camera: three acts --------------------------------------------------------
# (frame, location, look-at target, lens)
CORRIDOR_DIR = Vector((0.852, -0.524, 0.0))  # Bashamichi axis, NW -> SE
A2_START = Vector((352.0, -749.0, 4.2))  # raycast-verified open; (369,-760) is inside a 12.6 m block
A2_END = Vector((326.0, -733.0, 4.2))
CAM_KEYS = [
    # Act 1 — station-south node, street level, slow push down the open NW corridor
    (1,    A1_START, A1_TARGET, 42.0),
    (360,  A1_END,   A1_TARGET, 42.0),
    # Act 2 — Bashamichi: start further SE, retreat NW to the still composition
    (361,  A2_START, A2_START + CORRIDOR_DIR * 170 + Vector((0, 0, 2.3)), 42.0),
    (1440, A2_END,   A2_END + CORRIDOR_DIR * 170 + Vector((0, 0, 2.3)), 42.0),
    # Act 3 — the only rise: continuous from Act 2's end pose, to ~39 m
    (1441, A2_END,   A2_END + CORRIDOR_DIR * 170 + Vector((0, 0, 2.3)), 42.0),
    (1560, Vector((312.0, -722.0, 13.0)), Vector((472.0, -895.0, 3.0)), 40.0),
    (1680, Vector((301.0, -712.0, 25.0)), Vector((468.0, -955.0, 0.0)), 37.0),
    (1800, A3_END,   A3_TARGET, 36.0),
]
cam_data = bpy.data.cameras.new("Cam")
cam = bpy.data.objects.new("Cam", cam_data)
bpy.context.scene.collection.objects.link(cam)
bpy.context.scene.camera = cam
cam_data.clip_end = 30000
for frame, loc, tgt, lens in CAM_KEYS:
    cam.location = loc
    cam.rotation_euler = (tgt - loc).to_track_quat('-Z', 'Y').to_euler()
    cam.keyframe_insert(data_path="location", frame=frame)
    cam.keyframe_insert(data_path="rotation_euler", frame=frame)
    cam_data.lens = lens
    cam_data.keyframe_insert(data_path="lens", frame=frame)
if cam.animation_data and cam.animation_data.action:
    for fc in cam.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
if cam_data.animation_data and cam_data.animation_data.action:
    for fc in cam_data.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
print(f"CCL FULL: camera acts — A1 f1-360 node street push {tuple(A1_START)}->{tuple(A1_END)} "
      f"target {tuple(A1_TARGET)}; A2 f361-1440 Bashamichi retreat (352,-749)->(326,-733); "
      f"A3 f1441-1800 rise to {tuple(A3_END)} target {tuple(A3_TARGET)}, lens 42->36", flush=True)

scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.use_adaptive_sampling = True
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.render.resolution_x = int(argval("--width", "1920"))
scene.render.resolution_y = int(argval("--height-px", "1080"))
scene.render.fps = 24
scene.frame_start = 1
scene.frame_end = N_FRAMES

if argval("--device", "CPU") == "GPU":
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'METAL'
    prefs.get_devices()
    for dev in prefs.devices:
        dev.use = True
        print(f"CCL FULL: cycles device available: {dev.name} ({dev.type})", flush=True)
    scene.cycles.device = 'GPU'
    print("CCL FULL: cycles device = GPU (METAL)", flush=True)

os.makedirs(FRAMES_DIR, exist_ok=True)
with open(os.path.join(FRAMES_DIR, "ignition-order.json"), "w") as fh:
    json.dump({"station_local_m": list(STATION), "station_latlon": [35.44306, 139.63722],
               "wave_first_frame": WAVE_FIRST, "wave_last_frame": WAVE_LAST,
               "ramp_frames": RAMP, "dmax_m": round(dmax, 1),
               "palette_cap": {"above": CAP_ABOVE, "strength": CAP_STRENGTH,
                               "deepen_g": -0.06, "deepen_b": -0.07, "capped_openings": n_capped},
               "acts": {"act1_frames": [1, 360], "act2_frames": [361, 1440],
                        "act3_frames": [1441, 1800]},
               "openings": sidecar}, fh, indent=1)

if FRAME_ONLY:
    scene.frame_set(FRAME_ONLY)
    scene.render.filepath = OUT
    bpy.ops.render.render(write_still=True)
    print(f"CCL FULL: preview frame {FRAME_ONLY} -> {OUT}", flush=True)
else:
    scene.render.filepath = os.path.join(FRAMES_DIR, "frame_")
    bpy.ops.render.render(animation=True)
    print(f"CCL FULL: rendered {N_FRAMES} frames -> {FRAMES_DIR}", flush=True)
