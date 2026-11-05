#!/usr/bin/env python3
"""Float a face-selected district while preserving its surrounding city.

Usage:
  blender -b scene.blend -P render_lift_split.py -- \
      --region -340 -120 120 280 --height 70 --output /tmp/lift-split.png
Optional: --object NAME --samples 32 --cam X Y Z --target X Y Z --debug

Selection uses world-space polygon centroids, not geometric clipping: boundary
faces stay whole. The slab top follows the lowest selected world-space vertex.
The ground plane is deliberately retained, not cut. The open pit has walls from
z=0.2 to -17.8 and a floor at -17.8; the unchanged ground can occlude its
interior. This is a visual approximation relying on the floating slab's shadow.
Debug renders color the selected faces red without separating or lifting them,
and omit the slab and pit so the region can be calibrated against the city.
The loaded scene is modified in memory only; the source .blend is never saved.
"""

import argparse
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--object', dest='object_name')
    parser.add_argument('--region', type=float, nargs=4, required=True,
                        metavar=('XMIN', 'XMAX', 'YMIN', 'YMAX'))
    parser.add_argument('--height', type=float, required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--samples', type=int, default=32)
    parser.add_argument('--cam', type=float, nargs=3)
    parser.add_argument('--target', type=float, nargs=3)
    parser.add_argument('--debug', action='store_true')
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    args = parser.parse_args(argv)
    xmin, xmax, ymin, ymax = args.region
    numbers = [*args.region, args.height, *(args.cam or []), *(args.target or [])]
    if not all(math.isfinite(value) for value in numbers):
        parser.error('coordinates and height must be finite')
    if xmax - xmin <= 2 or ymax - ymin <= 2:
        parser.error('region dimensions must exceed 2m for the 1m pit inset')
    if args.height < 0 or args.samples < 1:
        parser.error('height must be nonnegative and samples must be positive')
    if (args.cam is None) != (args.target is None):
        parser.error('--cam and --target must be supplied together')
    if args.cam is not None and args.cam == args.target:
        parser.error('camera and target must differ')
    return args


def material(name, color, roughness):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    shader = mat.node_tree.nodes['Principled BSDF']
    shader.inputs['Base Color'].default_value = (*color, 1.0)
    shader.inputs['Roughness'].default_value = roughness
    mat.diffuse_color = (*color, 1.0)
    return mat


def assign_material(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    for face in obj.data.polygons:
        face.material_index = 0


def add_slab(region, top, porcelain, earth):
    xmin, xmax, ymin, ymax = region
    bpy.ops.mesh.primitive_cube_add(
        location=((xmin + xmax) / 2, (ymin + ymax) / 2, top - 13))
    slab = bpy.context.object
    slab.name = 'CCL_lift_split_slab'
    slab.scale = ((xmax - xmin) / 2, (ymax - ymin) / 2, 13)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    slab.data.materials.append(earth)
    slab.data.materials.append(porcelain)
    for face in slab.data.polygons:
        face.material_index = 1 if face.normal.z > 0.5 else 0


def add_pit(region, earth):
    xmin, xmax, ymin, ymax = region
    xmin, xmax, ymin, ymax = xmin + 1, xmax - 1, ymin + 1, ymax - 1
    # Winding points the walls inward and the floor upward. No top face.
    vertices = [(xmin, ymin, -17.8), (xmax, ymin, -17.8),
                (xmax, ymax, -17.8), (xmin, ymax, -17.8),
                (xmin, ymin, 0.2), (xmax, ymin, 0.2),
                (xmax, ymax, 0.2), (xmin, ymax, 0.2)]
    faces = [(0, 1, 2, 3), (0, 4, 5, 1), (1, 5, 6, 2),
             (2, 6, 7, 3), (3, 7, 4, 0)]
    mesh = bpy.data.meshes.new('CCL_lift_split_pit_mesh')
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    pit = bpy.data.objects.new('CCL_lift_split_pit', mesh)
    bpy.context.scene.collection.objects.link(pit)
    mesh.materials.append(earth)


def main():
    args = parse_args()
    scene = bpy.context.scene
    meshes = [obj for obj in scene.objects
              if obj.type == 'MESH' and 'ground' not in obj.name.lower()]
    if args.object_name:
        target = scene.objects.get(args.object_name)
        if target is None or target.type != 'MESH':
            raise ValueError('--object must name a mesh in the current scene')
        if 'ground' in target.name.lower():
            raise ValueError('the ground must remain intact; select a city mesh')
    else:
        if not meshes:
            raise ValueError('no non-ground city mesh found')
        target = max(meshes, key=lambda obj: len(obj.data.polygons))
    if target.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    if target.data.users > 1:
        raise ValueError('target mesh data is shared; use a single-user city mesh')
    if scene.camera is None and args.cam is None:
        raise ValueError('scene needs a camera or explicit --cam and --target')

    xmin, xmax, ymin, ymax = args.region
    selected = []
    for face in target.data.polygons:
        center = target.matrix_world @ face.center
        if xmin <= center.x <= xmax and ymin <= center.y <= ymax:
            selected.append(face.index)
    if not selected:
        raise ValueError('region contains no face centroids; adjust --region')
    base = min((target.matrix_world @ target.data.vertices[index].co).z
               for face_index in selected
               for index in target.data.polygons[face_index].vertices)
    porcelain = material('CCL_lift_split_porcelain', (0.92, 0.89, 0.83), 0.35)
    earth = material('CCL_lift_split_earth', (0.23, 0.19, 0.16), 1.0)
    for obj in meshes:
        assign_material(obj, porcelain)

    if args.debug:
        target.data.materials.append(material('CCL_lift_split_debug', (1, 0, 0), 0.5))
        for index in selected:
            target.data.polygons[index].material_index = 1
        print(f'CCL: separated face count = 0 (debug; selected = {len(selected)})', flush=True)
    else:
        bpy.ops.object.select_all(action='DESELECT')
        target.hide_set(False)
        target.select_set(True)
        bpy.context.view_layer.objects.active = target
        # Clear vertex/edge selection too: inherited selection must not leak into
        # the separation when Blender switches to face selection mode.
        for vertex in target.data.vertices:
            vertex.select = False
        for edge in target.data.edges:
            edge.select = False
        for face in target.data.polygons:
            face.select = False
        for index in selected:
            target.data.polygons[index].select = True
        previous = set(scene.objects)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type='FACE')
        try:
            bpy.ops.mesh.separate(type='SELECTED')
        finally:
            bpy.ops.object.mode_set(mode='OBJECT')
        created = [obj for obj in scene.objects if obj not in previous]
        if len(created) != 1 or len(created[0].data.polygons) != len(selected):
            raise RuntimeError('face separation did not produce the expected mesh')
        lifted = created[0]
        lifted.name = 'CCL_lift_split_district'
        # World transform translation also works with rotated/scaled parents.
        matrix = lifted.matrix_world.copy()
        matrix.translation.z += args.height
        lifted.matrix_world = matrix
        add_slab(args.region, base + args.height, porcelain, earth)
        add_pit(args.region, earth)
        print(f'CCL: separated face count = {len(selected)}; lift = {args.height}m', flush=True)

    for obj in scene.objects:
        if obj.type == 'LIGHT' and obj.data.type == 'SUN':
            obj.data.energy = max(obj.data.energy, 4.0)
    if args.cam is not None:
        if scene.camera is None:
            camera = bpy.data.objects.new('CCL_lift_split_camera', bpy.data.cameras.new('CCL_camera'))
            scene.collection.objects.link(camera)
            scene.camera = camera
        camera = scene.camera
        matrix = (Vector(args.target) - Vector(args.cam)).to_track_quat('-Z', 'Y').to_matrix().to_4x4()
        matrix.translation = Vector(args.cam)
        camera.matrix_world = matrix
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.use_denoising = True
    scene.cycles.samples = args.samples
    scene.render.resolution_x = 960
    scene.render.resolution_y = 540
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(output)
    print(f'CCL: output path = {output}', flush=True)
    bpy.ops.render.render(write_still=True)
    print(f'CCL: rendered {output}', flush=True)


if __name__ == '__main__':
    main()
