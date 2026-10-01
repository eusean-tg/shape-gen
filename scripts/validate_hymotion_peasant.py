"""Verify saved animated blend and all exported GLB frames against the rig source."""
import hashlib
import argparse
import json
from pathlib import Path
import sys
import bpy
import numpy as np
from mathutils.kdtree import KDTree
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'assets/peasant-hymotion';OUT=BASE/'walk/final'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--directory',type=Path,default=OUT)
parser.add_argument('--report',type=Path,default=BASE/'validation.json')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
OUT=args.directory.resolve()
SOURCE=ROOT/'assets/peasant-unirig/final/peasant-rigged.blend'
names=['Peasant body','Original BPT pouch']
def snap(obj):
    return {'vertices':np.array([tuple(v.co) for v in obj.data.vertices]),
        'faces':np.array([list(f.vertices) for f in obj.data.polygons]),
        'uv':np.array([tuple(x.uv) for x in obj.data.uv_layers.active.data]),
        'weights':[(v.index,g.group,g.weight) for v in obj.data.vertices for g in v.groups]}
def textures():
    return sorted(hashlib.sha256(n.image.packed_file.data).hexdigest()
        for name in names for s in bpy.data.objects[name].material_slots
        for n in s.material.node_tree.nodes if n.type=='TEX_IMAGE' and n.image)
def evaluated(obj):
    bpy.context.view_layer.update();ob=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ob.to_mesh()
    vertices=np.array([ob.matrix_world@v.co for v in me.vertices]);ob.to_mesh_clear();return vertices
def nearest(a,b):
    tree=KDTree(len(b))
    for i,v in enumerate(b):tree.insert(v,i)
    tree.balance();return max(tree.find(v)[2] for v in a)
bpy.ops.wm.open_mainfile(filepath=str(SOURCE));original={n:snap(bpy.data.objects[n]) for n in names};images=textures()
rest_bones={b.name:np.array(b.matrix_local) for b in bpy.data.objects['Peasant rig'].data.bones}
bpy.ops.wm.open_mainfile(filepath=str(OUT/'peasant-walk.blend'))
for n in names:
    actual=snap(bpy.data.objects[n])
    for key in original[n]:assert np.array_equal(original[n][key],actual[key]),(n,key)
assert images==textures()
for b in bpy.data.objects['Peasant rig'].data.bones:assert np.array_equal(np.array(b.matrix_local),rest_bones[b.name])
assert bpy.context.scene.render.fps==30 and bpy.context.scene.frame_end==120
assert 'HY-Motion' in bpy.data.objects['Peasant rig'].animation_data.action.name
reference={}
for frame in range(1,121):
    bpy.context.scene.frame_set(frame);reference[frame]={n:evaluated(bpy.data.objects[n]) for n in names}
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.render.fps=30
bpy.ops.import_scene.gltf(filepath=str(OUT/'peasant-walk.glb'))
arms=[o for o in bpy.data.objects if o.type=='ARMATURE'];assert len(arms)==1 and len(arms[0].data.bones)==28
assert arms[0].animation_data and arms[0].animation_data.action
errors={}
for frame in range(1,121):
    # Export slides Blender frame 1 to glTF t=0; Blender imports that at frame 0.
    bpy.context.scene.frame_set(frame-1);errors[frame]={}
    for n in names:
        actual=evaluated(bpy.data.objects[n]);expected=reference[frame][n]
        error=max(nearest(actual,expected),nearest(expected,actual));assert error<3e-5,(frame,n,error)
        errors[frame][n]=error
report={'blend_reopened':True,'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    'rest_vertices_faces_uvs_weights_bones_unchanged':True,'packed_texture_bytes_unchanged':True,
    'glb_reimported':True,'bones':28,'frames_checked':120,'fps':30,'glb_time_zero_matches_blender_frame':1,
    'max_world_vertex_error':max(e for row in errors.values() for e in row.values()),
    'per_frame_world_vertex_error':errors}
args.report.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='per_frame_world_vertex_error'},indent=2))
