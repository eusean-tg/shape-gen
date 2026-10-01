"""Verify targeted weight repair preserves geometry, textures and all motion.

Also refresh cycle analysis for the existing export/contact validator.
"""
import hashlib
import json
from pathlib import Path
import bpy
import numpy as np

BASE = Path(__file__).resolve().parents[1]/'assets/teal-peasant'
OUT = BASE/'arm-repair'
raw = np.load(BASE/'rig/rig-data.npz')
fixed = np.load(BASE/'rig/refined-rig-data.npz')
untouched = np.all(raw['weights'] == fixed['weights'], axis=1)

def snapshot(path):
    bpy.ops.wm.open_mainfile(filepath=str(path))
    body = bpy.data.objects['Peasant body']; arm = bpy.data.objects['Peasant rig']
    surface = {
        'rest_vertices': np.array([v.co[:] for v in body.data.vertices]),
        'faces': np.array([p.vertices[:] for p in body.data.polygons]),
        'uv': np.array([uv.uv[:] for uv in body.data.uv_layers.active.data]),
        'materials': np.array([p.material_index for p in body.data.polygons]),
        'bones': np.array([b.matrix_local[:] for b in arm.data.bones]),
        'texture_hashes': np.array([hashlib.sha256(n.image.packed_file.data).hexdigest()
            for m in body.data.materials for n in m.node_tree.nodes if n.type == 'TEX_IMAGE']),
    }
    matrices, vertices = [], []
    scene = bpy.context.scene
    frames = range(scene.frame_start, scene.frame_end+1) if arm.animation_data else [1]
    for frame in frames:
        scene.frame_set(frame)
        matrices.append([p.matrix[:] for p in arm.pose.bones])
        obj = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh = obj.to_mesh()
        vertices.append([(obj.matrix_world @ v.co)[:] for v in mesh.vertices])
        obj.to_mesh_clear()
    return surface, np.array(matrices), np.array(vertices)

analysis = dict(np.load(BASE/'walk-cycle/cycle-analysis.npz'))
report = {}
for old, new, key in [
    ('model/rigged.blend', 'rest/rigged.blend', None),
    ('walk-source/peasant-walk.blend', 'source/peasant-walk.blend', None),
    ('walk-cycle/before-foot-lock/peasant-walk.blend', 'before-foot-lock/peasant-walk.blend', 'base_vertices'),
    ('walk-cycle/final/peasant-walk.blend', 'final/peasant-walk.blend', 'final_vertices'),
    ('walk-cycle/travel-check/peasant-walk.blend', 'travel-check/peasant-walk.blend', None),
]:
    a, am, av = snapshot(BASE/old)
    b, bm, bv = snapshot(OUT/new)
    for name in a:
        assert np.array_equal(a[name], b[name]), (new, name)
    assert np.array_equal(am, bm), (new, 'bone animation changed')
    delta = float(np.max(abs(av[:, untouched] - bv[:, untouched])))
    assert delta < 1e-7, (new, 'non-arm motion changed', delta)
    report[new] = {'frames': len(bv), 'geometry_uvs_materials_textures_rest_bones_unchanged': True,
                   'all_bone_motion_unchanged': True, 'untouched_vertex_max_motion_difference': delta}
    if key:
        analysis[key] = bv
        if key == 'final_vertices':
            np.savez_compressed(OUT/'repair-comparison.npz', before=av, after=bv)
np.savez_compressed(OUT/'cycle-analysis.npz', **analysis)
config = json.loads((BASE/'walk-cycle/cycle.json').read_text())
config['source_blend'] = str(OUT/'source/peasant-walk.blend')
config['source_sha256'] = hashlib.sha256((OUT/'source/peasant-walk.blend').read_bytes()).hexdigest()
config['arm_weight_repair'] = '../rig/arm-weight-repair.json'
(OUT/'cycle.json').write_text(json.dumps(config, indent=2)+'\n')
(OUT/'preservation.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
