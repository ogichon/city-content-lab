# Brief — Codex G: render_lift_split.py（単一メッシュ用 面分割リフター）

Read AGENTS.md and docs/experiments/EXP-006.md (in-context design) first. Do NOT commit (Muse commits). Create `scripts/blender/render_lift_split.py`:

- Purpose: on single-mesh scenes (whole city = one mesh object, e.g. skytree_scene.blend / shinjuku_tocho_scene.blend), cut a rectangular region out by FACE selection and float it, in-context (surroundings stay).
- Args: --object NAME (default: largest non-ground mesh), --region XMIN XMAX YMIN YMAX (world coords, polygon-centroid test via matrix_world), --height H, --output PATH, --samples N (default 32), --cam X Y Z --target X Y Z (optional), --debug (region faces red, no lift).
- Steps: duplicate nothing; work on the given object: select faces whose centroid is in region (bmesh or polygon selection + bpy.ops.mesh.separate(type='SELECTED') in edit mode), yielding a new object; assign porcelain to all city faces/objects; lift the new object by H; add slab box under the region (top at base+H, thickness 26m, sides+bottom in an "earth" material: dark brown-gray (0.23,0.19,0.16), roughness 1.0); add pit: an open-top box (4 inner walls + floor) sunk into the ground under the region with the same earth material, inner size = region inset by 1m, depth 18m; strengthen the Sun if present (energy max(current, 4.0)).
- Ground handling: the ground plane stays (it is the context); the pit box sits in a visual recess — since the plane can't be holed cheaply, place the pit walls from z=0.2 down and a dark floor at z=-17.8, and rely on the slab shadow. Document this approximation in the header.
- Render settings: Cycles CPU, adaptive, denoise, 960×540. Print CCL: lines for separated face count and output path.
- Also write a short usage note section into docs/experiments/EXP-006.md? No — doc updates are Muse's. Only the script.
- You cannot run Blender renders that need the real scene files if unavailable in your sandbox; at minimum syntax-check the script with python3 -m py_compile and state clearly what you could and could not verify.
Print a summary at the end.
