"""Check material-only changes, original motion preservation and GLB reimport."""
import hashlib,json
from pathlib import Path
import bpy
import numpy as np
from mathutils.kdtree import KDTree
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'assets/peasant-material-masks'
SOURCE=ROOT/'assets/peasant-hymotion/walk/final/peasant-walk.blend';names=['Peasant body','Original BPT pouch']
def snapshot(obj):
    return {'vertices':np.array([tuple(v.co) for v in obj.data.vertices]),'faces':np.array([list(p.vertices) for p in obj.data.polygons]),'uv':np.array([tuple(v.uv) for v in obj.data.uv_layers.active.data]),'weights':[(v.index,g.group,g.weight) for v in obj.data.vertices for g in v.groups]}
def evaluated(obj):
    bpy.context.view_layer.update();ob=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ob.to_mesh();v=np.array([ob.matrix_world@p.co for p in me.vertices]);ob.to_mesh_clear();return v
def nearest(a,b):
    tree=KDTree(len(b))
    for i,v in enumerate(b):tree.insert(v,i)
    tree.balance();return max(tree.find(v)[2] for v in a)
bpy.ops.wm.open_mainfile(filepath=str(SOURCE));original={n:snapshot(bpy.data.objects[n]) for n in names};bones={b.name:np.array(b.matrix_local) for b in bpy.data.objects['Peasant rig'].data.bones};expected={}
for frame in range(1,121):
    bpy.context.scene.frame_set(frame);expected[frame]={n:evaluated(bpy.data.objects[n]) for n in names}
for variant in ['regions','flat','masked']:
    bpy.ops.wm.open_mainfile(filepath=str(BASE/variant/'peasant-walk.blend'))
    for n in names:
        now=snapshot(bpy.data.objects[n])
        for k in now:assert np.array_equal(now[k],original[n][k]),(variant,n,k)
        assert len(bpy.data.objects[n].data.attributes['material_region'].data)==len(original[n]['faces'])
    for b in bpy.data.objects['Peasant rig'].data.bones:assert np.array_equal(np.array(b.matrix_local),bones[b.name])
    for frame in range(1,121):
        bpy.context.scene.frame_set(frame)
        for n in names:assert np.max(abs(evaluated(bpy.data.objects[n])-expected[frame][n]))<2e-6,(variant,frame,n)
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.render.fps=30
bpy.ops.import_scene.gltf(filepath=str(BASE/'masked/peasant-walk.glb'))
errors={}
for frame in range(1,121):
    bpy.context.scene.frame_set(frame-1);errors[frame]={}
    for n in names:
        a=evaluated(bpy.data.objects[n]);b=expected[frame][n];err=max(nearest(a,b),nearest(b,a));assert err<3e-5,(frame,n,err);errors[frame][n]=err
report={'source':str(SOURCE),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'variants_reopened':['regions','flat','masked'],'rest_geometry_uvs_weights_bones_unchanged':True,'evaluated_animation_matches_source':True,'frames_checked_per_variant':120,'masked_glb_reimported':True,'max_glb_world_vertex_error':max(e for row in errors.values() for e in row.values()),'per_frame_glb_error':errors}
(BASE/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='per_frame_glb_error'},indent=2))
