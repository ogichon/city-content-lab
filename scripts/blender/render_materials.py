#!/usr/bin/env python3
"""CITY CONTENT LAB — Blender offline material comparison (EXP-003 Blender track).

Opens the proven Tokyo Station scene blend from the plateau-tokyo-station
project and re-renders the SAME camera/lighting with all building materials
replaced by a single principled material. This is the offline counterpart of
the Navara controlled comparison: same geometry, same camera, material only.

Usage:
  blender -b tokyo_station_scene.blend -noaudio -P render_materials.py -- \
      --material gold --output out.png [--samples 32] [--resx 960] [--resy 540]
Materials: porcelain | gold | chrome | ice
The ground plane object (name contains 'Ground' or 'Plane') keeps its material.
"""
import bpy, sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def argval(flag, default):
    return argv[argv.index(flag) + 1] if flag in argv else default

MAT_NAME = argval("--material", "porcelain")
OUTPUT = argval("--output", "/tmp/blender-material.png")
SAMPLES = int(argval("--samples", "32"))
RESX = int(argval("--resx", "960"))
RESY = int(argval("--resy", "540"))

MATERIALS = {
    # name: (base_color RGBA, metallic, roughness)
    "porcelain": ((0.92, 0.89, 0.83, 1.0), 0.0, 0.35),
    "gold":      ((0.83, 0.55, 0.12, 1.0), 1.0, 0.30),
    "chrome":    ((0.72, 0.76, 0.80, 1.0), 1.0, 0.12),
    "ice":       ((0.62, 0.83, 0.91, 1.0), 0.1, 0.15),
    "ice2":      ((0.75, 0.88, 0.94, 1.0), 0.0, 0.22),
}
color, metallic, roughness = MATERIALS[MAT_NAME]

mat = bpy.data.materials.new(name=f"CCL_{MAT_NAME}")
mat.use_nodes = True
bsdf = mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = color
bsdf.inputs["Metallic"].default_value = metallic
bsdf.inputs["Roughness"].default_value = roughness
if MAT_NAME == "ice2":
    # Transmission is what makes it read as ice rather than pale porcelain.
    if "Transmission Weight" in bsdf.inputs:
        bsdf.inputs["Transmission Weight"].default_value = 0.65
    if "IOR" in bsdf.inputs:
        bsdf.inputs["IOR"].default_value = 1.31
    try:
        mat.surface_render_method = "DITHERED"
    except Exception as e:
        print(f"CCL: surface_render_method unavailable ({e})", flush=True)

# Optional sun override: --sun RX RY RZ (radians), --exposure F
if "--sun" in argv:
    i = argv.index("--sun")
    sun = bpy.data.objects.get("Sun")
    if sun:
        sun.rotation_euler = (float(argv[i + 1]), float(argv[i + 2]), float(argv[i + 3]))
        print(f"CCL: sun rotation set to {tuple(sun.rotation_euler)}", flush=True)

replaced = 0
for obj in bpy.data.objects:
    if obj.type != "MESH":
        continue
    if "ground" in obj.name.lower() or "plane" in obj.name.lower():
        continue
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    replaced += 1
print(f"CCL: material {MAT_NAME} applied to {replaced} mesh objects", flush=True)

scene = bpy.context.scene
if "--exposure" in argv:
    scene.view_settings.exposure = float(argval("--exposure", "0"))
    print(f"CCL: exposure set to {scene.view_settings.exposure}", flush=True)
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.use_adaptive_sampling = True
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.render.resolution_x = RESX
scene.render.resolution_y = RESY
scene.render.filepath = OUTPUT
bpy.ops.render.render(write_still=True)
print(f"CCL: rendered {OUTPUT}", flush=True)
