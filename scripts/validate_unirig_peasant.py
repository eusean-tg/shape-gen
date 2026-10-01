"""Reopen the final blend, compare source data, and reimport animated GLB."""
import hashlib
import json
from pathlib import Path
import bpy
import numpy as np
from mathutils.kdtree import KDTree

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'assets/peasant-unirig';OUT=BASE/'final'
SOURCE=ROOT/'assets/peasant-hypaint-experiment/hypaint-imagegen/peasant-hypaint-imagegen.blend'
NAMES=['Peasant body','Original BPT pouch']
def snapshot(obj):
    return {'vertices':np.array([tuple(v.co) for v in obj.data.vertices]),
            'faces':np.array([list(p.vertices) for p in obj.data.polygons]),
            'uv':np.array([tuple(v.uv) for v in obj.data.uv_layers.active.data]),
            'matrix':np.array(obj.matrix_world)}
def textures():
    result={}
    for name in NAMES:
        for slot in bpy.data.objects[name].material_slots:
            for node in slot.material.node_tree.nodes:
                if node.type=='TEX_IMAGE' and node.image:
                    assert node.image.packed_file
                    result[name+':'+node.name]=hashlib.sha256(node.image.packed_file.data).hexdigest()
    return result
def evaluated(obj):
    bpy.context.view_layer.update()
    ob=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ob.to_mesh()
    v=np.array([ob.matrix_world@x.co for x in mesh.vertices]);ob.to_mesh_clear();return v
def nearest_error(a,b):
    tree=KDTree(len(b))
    for i,v in enumerate(b):tree.insert(v,i)
    tree.balance()
    return max(tree.find(v)[2] for v in a)
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
source={n:snapshot(bpy.data.objects[n]) for n in NAMES};images=textures()
bpy.ops.wm.open_mainfile(filepath=str(OUT/'peasant-rigged.blend'))
assert bpy.context.scene.frame_current==1
for n in NAMES:
    actual=snapshot(bpy.data.objects[n])
    for k in source[n]:assert np.array_equal(actual[k],source[n][k]),(n,k)
assert images==textures()
arm=bpy.data.objects['Peasant rig'];assert len(arm.data.bones)==28
for n in NAMES:
    obj=bpy.data.objects[n]
    for v in obj.data.vertices:
        assert 1<=len(v.groups)<=4
        assert abs(sum(g.weight for g in v.groups)-1)<2e-6
    assert any(m.type=='ARMATURE' and m.object==arm for m in obj.modifiers)
frames=[1]+[m.frame for m in bpy.context.scene.timeline_markers]
reference={}
for frame in frames:
    bpy.context.scene.frame_set(frame)
    reference[frame]={n:evaluated(bpy.data.objects[n]) for n in NAMES}
np.savez(OUT/'rest-mesh.npz',vertices=reference[1][NAMES[0]],faces=source[NAMES[0]]['faces'],
         pouch_vertices=reference[1][NAMES[1]],pouch_faces=source[NAMES[1]]['faces'])
assert max(nearest_error(reference[1][n],source[n]['vertices']) for n in NAMES)<2e-6
assert np.max(abs(reference[13][NAMES[0]]-reference[1][NAMES[0]]))>.1
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.fps=24
bpy.ops.import_scene.gltf(filepath=str(OUT/'peasant-rigged.glb'))
assert len([o for o in bpy.data.objects if o.type=='ARMATURE'])==1
assert len(next(o for o in bpy.data.objects if o.type=='ARMATURE').data.bones)==28
assert len(bpy.data.actions)>0
errors={}
for frame in frames:
    bpy.context.scene.frame_set(frame)
    errors[frame]={}
    for n in NAMES:
        obj=bpy.data.objects.get(n)
        assert obj and obj.type=='MESH',n
        imported=evaluated(obj);expected=reference[frame][n]
        err=max(nearest_error(imported,expected),nearest_error(expected,imported))
        errors[frame][n]=err
        assert err<2e-5,(frame,n,err)
report={'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'blend_reopened':True,'original_mesh_faces_uvs_transforms_exact':True,
        'used_packed_texture_bytes_exact':True,'used_texture_hashes':images,
        'all_vertices_weighted':True,'max_influences':4,'bones':28,
        'glb_reimported':True,'glb_animation_poses_checked':len(frames),
        'glb_world_vertex_error_by_frame':errors,
        'note':'GLB UV seams split vertices; bidirectional nearest positions compared at rest and every test peak. This does not prove absence of collisions.'}
(BASE/'saved-file-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
