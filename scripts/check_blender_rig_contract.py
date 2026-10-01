"""Check the reference retargeter's local Blender prerequisites without modifying the source."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils import Matrix

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source', type=Path, required=True)
p.add_argument('--contract', type=Path, required=True)
p.add_argument('--report', type=Path, required=True)
args = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
contract = json.loads(args.contract.read_text())
bpy.ops.wm.open_mainfile(filepath=str(args.source))
errors = []
body = bpy.data.objects.get(contract['objects']['body'])
arm = bpy.data.objects.get(contract['objects']['armature'])
if body is None or body.type != 'MESH':
    errors.append('Required body mesh is missing')
if arm is None or arm.type != 'ARMATURE':
    errors.append('Required armature is missing')
if bpy.context.scene.camera is None:
    errors.append('An active scene camera is required, including with --skip-renders')
if body and body.type == 'MESH':
    if not body.data.polygons or any(len(f.vertices) != 3 for f in body.data.polygons):
        errors.append('Body must be nonempty and triangulated')
    if not body.data.uv_layers.active:
        errors.append('An active UV layer is required by the review helper')
    for material in body.data.materials:
        if material is None or not material.use_nodes:
            errors.append('Review helper requires node-based materials')
            continue
        for node in material.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and (not node.image or not node.image.packed_file):
                errors.append('Review helper requires packed image textures')
if arm and arm.type == 'ARMATURE':
    for name in contract['target_to_source_joint']:
        if name not in arm.data.bones:
            errors.append('Missing semantic bone: ' + name)
    seen = set()
    for bone in arm.data.bones:
        if bone.parent and bone.parent.name not in seen:
            errors.append('Bones must be ordered parent before child')
        if bone.parent is None and bone.name != 'pelvis':
            errors.append('Expected a single pelvis root')
        seen.add(bone.name)
    identity = Matrix.Identity(4)
    if max(abs(arm.matrix_world[i][j] - identity[i][j]) for i in range(4) for j in range(4)) > 1e-6:
        errors.append('Reference retargeter requires identity armature world transform')
if body and arm and not any(m.type == 'ARMATURE' and m.object == arm for m in body.modifiers):
    errors.append('Body must have an Armature modifier targeting the named rig')
report = {'status': 'failed' if errors else 'passed', 'errors': errors,
          'contract_id': contract['id'], 'contract_version': contract['version'],
          'blender_version': bpy.app.version_string,
          'source_sha256': hashlib.sha256(args.source.read_bytes()).hexdigest(),
          'semantic_mapping_review': 'required; name checks cannot establish anatomical correctness',
          'visual_acceptance': 'pending'}
with args.report.open('x') as f:
    json.dump(report, f, indent=2)
    f.write('\n')
print(json.dumps(report, indent=2))
if errors:
    raise RuntimeError('Rig contract failed; see report')
