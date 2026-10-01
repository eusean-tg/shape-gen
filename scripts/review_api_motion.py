"""Validate a candidate against its source and GLB, then render fixed-camera samples."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source', type=Path, required=True)
p.add_argument('--directory', type=Path, required=True)
p.add_argument('--clip-name', required=True)
p.add_argument('--frames', type=int, required=True)
args = p.parse_args(sys.argv[sys.argv.index('--') + 1:])


def snapshot():
    body = bpy.data.objects['Peasant body']
    arm = bpy.data.objects['Peasant rig']
    return {
        'vertices': np.array([v.co[:] for v in body.data.vertices]),
        'faces': np.array([p.vertices[:] for p in body.data.polygons]),
        'uv': np.array([p.uv[:] for p in body.data.uv_layers.active.data]),
        'weights': np.array([(v.index, g.group, g.weight) for v in body.data.vertices for g in v.groups]),
        'rest_bones': np.array([b.matrix_local[:] for b in arm.data.bones]),
        'materials': np.array([p.material_index for p in body.data.polygons]),
        'textures': np.array([hashlib.sha256(n.image.packed_file.data).hexdigest()
                             for m in body.data.materials for n in m.node_tree.nodes if n.type == 'TEX_IMAGE'])}


def evaluate():
    obj = bpy.data.objects['Peasant body'].evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = obj.to_mesh()
    vertices = np.array([(obj.matrix_world @ v.co)[:] for v in mesh.vertices])
    obj.to_mesh_clear()
    assert np.isfinite(vertices).all(), 'Non-finite deformed vertices'
    return vertices


def nearest(a, b):
    tree = KDTree(len(b))
    for i, v in enumerate(b):
        tree.insert(v, i)
    tree.balance()
    return max(tree.find(v)[2] for v in a)


bpy.ops.wm.open_mainfile(filepath=str(args.source))
original = snapshot()
bpy.ops.wm.open_mainfile(filepath=str(args.directory / 'peasant-walk.blend'))
current = snapshot()
for key in original:
    assert np.array_equal(original[key], current[key]), f'Source changed: {key}'
scene = bpy.context.scene
arm = bpy.data.objects['Peasant rig']
assert arm.animation_data.action.name == args.clip_name
assert scene.frame_end == args.frames and scene.render.fps == 30
reference = []
sample_frames = np.arange(1, args.frames + .01, .5)
for frame in sample_frames:
    scene.frame_set(int(frame), subframe=float(frame % 1))
    reference.append(evaluate())
reference = np.array(reference)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.fps = 30
bpy.ops.import_scene.gltf(filepath=str(args.directory / 'peasant-walk.glb'))
arm = bpy.data.objects['Peasant rig']
assert len(arm.data.bones) == len(current['rest_bones'])
assert arm.animation_data.action.name == args.clip_name or arm.animation_data.action.name.startswith(args.clip_name + '_')
errors = []
for frame, expected in zip(sample_frames, reference):
    t = frame - 1
    bpy.context.scene.frame_set(int(t), subframe=float(t % 1))
    actual = evaluate()
    error = max(nearest(actual, expected), nearest(expected, actual))
    assert error < 3e-5, (frame, error)
    errors.append(error)
report = {'status': 'passed', 'clip_name': args.clip_name, 'frames': args.frames, 'fps': 30,
          'duration_seconds': (args.frames - 1) / 30, 'samples_checked': len(errors),
          'max_glb_vertex_error': max(errors), 'source_geometry_uv_weights_rest_bones_materials_textures_preserved': True,
          'finite_vertices': True, 'minimum_surface_height': float(reference[:, :, 2].min()),
          'visual_acceptance': 'pending', 'looped': False, 'contact_locked': False,
          'note': 'Raw retargeted candidate. No loop or foot-contact assertions are applied to arbitrary motions.'}

# Render the native candidate with a fixed camera covering the entire trajectory.
bpy.ops.wm.open_mainfile(filepath=str(args.directory / 'peasant-walk.blend'))
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 8
scene.render.threads_mode = 'FIXED'
scene.render.threads = 4
scene.render.resolution_x = scene.render.resolution_y = 512
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.view_settings.view_transform = 'Standard'
low = reference.min(axis=(0, 1))
high = reference.max(axis=(0, 1))
center = Vector((low + high) / 2)
extent = float((high - low).max())
cam = scene.camera
cam.data.type = 'ORTHO'
cam.data.ortho_scale = extent * 1.3
cam.location = center + Vector((-2.5, -4, 1.1))
cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y').to_euler()
for frame in sorted(set([1, args.frames // 3, args.frames * 2 // 3, args.frames])):
    scene.frame_set(frame)
    scene.render.filepath = str(args.directory / f'review-{frame:03}.png')
    bpy.ops.render.render(write_still=True)
(args.directory / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2), flush=True)
