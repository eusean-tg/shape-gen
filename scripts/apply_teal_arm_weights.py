"""Apply reviewed arm weights to a copy of an existing Blender scene/action."""
import argparse
import sys
from pathlib import Path
import bpy
import numpy as np

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args(sys.argv[sys.argv.index('--')+1:])
base = Path(__file__).resolve().parents[1]/'assets/teal-peasant'
data = np.load(base/'rig/refined-rig-data.npz')
bpy.ops.wm.open_mainfile(filepath=str(a.source.resolve()))
body = bpy.data.objects['Peasant body']
assert np.max(abs(np.array([v.co[:] for v in body.data.vertices])-data['vertices'])) < 1e-7
ids = list(range(len(body.data.vertices)))
for group in body.vertex_groups:
    group.remove(ids)
for i, row in enumerate(data['weights']):
    for j in np.flatnonzero(row):
        body.vertex_groups[str(data['names'][j])].add([i], float(row[j]), 'REPLACE')
body['arm_weight_note'] = 'Topology-isolated sleeves/hands, smooth joint bands; raw learned weights preserved separately.'
arm = bpy.data.objects['Peasant rig']
bpy.ops.object.select_all(action='DESELECT')
body.select_set(True); arm.select_set(True)
bpy.context.view_layer.objects.active = arm
bpy.context.scene.frame_set(1)
a.output.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(a.output.resolve()))
bpy.ops.export_scene.gltf(filepath=str(a.output.with_suffix('.glb').resolve()),
    export_format='GLB', use_selection=True, export_yup=True, export_skins=True,
    export_animations=bool(arm.animation_data and arm.animation_data.action),
    export_frame_range=True, export_force_sampling=True, export_def_bones=True,
    export_materials='EXPORT', export_animation_mode='ACTIVE_ACTIONS',
    export_anim_slide_to_zero=True, export_extras=True)
