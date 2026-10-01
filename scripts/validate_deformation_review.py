"""Reopen the review blends and compare untouched rest geometry/UVs/textures."""
import hashlib
import json
from pathlib import Path
import bpy
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets/peasant-deformation-check'
SOURCE=ROOT/'assets/peasant-hypaint-experiment/hypaint-imagegen/peasant-hypaint-imagegen.blend'
def snapshot(path):
    bpy.ops.wm.open_mainfile(filepath=str(path))
    objects={}
    for o in bpy.context.scene.objects:
        if o.type!='MESH':continue
        objects[o.name]={
            'vertices':np.array([tuple(v.co) for v in o.data.vertices]),
            'faces':[tuple(p.vertices) for p in o.data.polygons],
            'uv':np.array([tuple(l.uv) for l in o.data.uv_layers.active.data]),
            'matrix':np.array(o.matrix_world),
        }
    # Blender drops orphan images on save; compare the images actually used by
    # the character materials rather than unrelated zero-user import leftovers.
    used_images={node.image for o in bpy.context.scene.objects if o.type=='MESH'
                 for mat in o.data.materials if mat and mat.use_nodes
                 for node in mat.node_tree.nodes if node.type=='TEX_IMAGE' and node.image}
    assert all(i.packed_file for i in used_images)
    packed={i.name:hashlib.sha256(bytes(i.packed_file.data)).hexdigest() for i in used_images}
    return objects,packed
original,images=snapshot(SOURCE)
report={}
for name in ['topology-review.blend','poses/bend-probes.blend']:
    objects,packed=snapshot(OUT/name)
    assert set(objects)==set(original)
    for obj,data in objects.items():
        ref=original[obj]
        assert np.array_equal(data['vertices'],ref['vertices']),obj
        assert data['faces']==ref['faces'],obj
        assert np.array_equal(data['uv'],ref['uv']),obj
        assert np.array_equal(data['matrix'],ref['matrix']),obj
    assert packed==images
    keys=bpy.data.objects['Peasant body'].data.shape_keys
    count=len(keys.key_blocks)-1 if keys else 0
    if count:
        assert count==10
        assert all(k.value==0 for k in list(keys.key_blocks)[1:])
        assert np.array_equal(np.array([tuple(v.co) for v in keys.key_blocks['Basis'].data]),original['Peasant body']['vertices'])
    report[name]={'rest_positions_faces_uvs_transforms_match_source':True,
                  'packed_texture_bytes_match_source':True,'diagnostic_shape_keys':count,
                  'all_probes_saved_at_zero':True}
expected=json.loads((OUT/'topology.json').read_text())['source_sha256']
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==expected
report['source_blend_unchanged']=True
(OUT/'saved-file-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
