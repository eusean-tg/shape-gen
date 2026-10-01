"""Compare the five-action export against Blender, including half frames."""
import hashlib,json
from pathlib import Path
import bpy
import numpy as np
from mathutils.kdtree import KDTree
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'assets/teal-peasant/idle-set'
SOURCE=ROOT/'assets/teal-peasant/collar-fix/final/peasant-walk.blend'

def geometry():
    body=bpy.data.objects['Peasant body'];arm=bpy.data.objects['Peasant rig']
    return {'vertices':np.array([v.co[:] for v in body.data.vertices]),
      'faces':np.array([p.vertices[:] for p in body.data.polygons]),
      'uv':np.array([v.uv[:] for v in body.data.uv_layers.active.data]),
      'weights':np.array([(v.index,g.group,g.weight) for v in body.data.vertices for g in v.groups]),
      'rest_bones':np.array([b.matrix_local[:] for b in arm.data.bones]),
      'materials':np.array([p.material_index for p in body.data.polygons]),
      'textures':np.array([hashlib.sha256(n.image.packed_file.data).hexdigest() for m in body.data.materials for n in m.node_tree.nodes if n.type=='TEX_IMAGE'])}
def time(t):bpy.context.scene.frame_set(int(t),subframe=float(t%1))
def evaluated():
    body=bpy.data.objects['Peasant body'];ob=body.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ob.to_mesh()
    v=np.array([(ob.matrix_world@p.co)[:] for p in me.vertices]);ob.to_mesh_clear();return v
def nearest(a,b):
    tree=KDTree(len(b))
    for i,p in enumerate(b):tree.insert(p,i)
    tree.balance();return max(tree.find(p)[2] for p in a)
def assign(action):
    arm=bpy.data.objects['Peasant rig'];arm.animation_data.action=action
    if len(action.slots):arm.animation_data.action_slot=action.slots[0]

bpy.ops.wm.open_mainfile(filepath=str(SOURCE));original=geometry();walk=[]
for i in range(79):time(i+1);walk.append(evaluated())
bpy.ops.wm.open_mainfile(filepath=str(BASE/'final/teal-character.blend'));now=geometry()
for key in original:assert np.array_equal(original[key],now[key]),key
expected={};report={};common=[]
for name in ['Idle_Breathe','Idle_LookAround','Idle_WeightShift','Idle_HandCheck','Walk']:
    assign(bpy.data.actions[name]);end=78 if name=='Walk' else 240
    values=[]
    for t in np.arange(0,end+.01,.5):time(t+1);values.append(evaluated())
    values=np.array(values);expected[name]=values
    assert abs(values[-1]-values[0]).max()<2e-6,(name,'loop seam')
    if name=='Walk':
        walk_error=float(abs(values[::2]-np.array(walk)).max())
        assert walk_error<1e-5,('Accepted walk changed',walk_error)
    else:common.append(values[0])
    report[name]={'samples':len(values),'duration':end/60,'endpoint_max_vertex_error':float(abs(values[-1]-values[0]).max()),'minimum_surface_height':float(values[:,:,2].min())}
assert max(abs(v-common[0]).max() for v in common)<2e-6,'Idle entry poses differ'
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.render.fps=60
bpy.ops.import_scene.gltf(filepath=str(BASE/'final/teal-character.glb'))
print('Imported actions:',[a.name for a in bpy.data.actions],flush=True)
for name,values in expected.items():
    choices=[a for a in bpy.data.actions if a.name==name or a.name.startswith(name+'_') or a.name.startswith(name+'|')]
    assert len(choices)==1,(name,[a.name for a in bpy.data.actions]);assign(choices[0]);errors=[]
    for i,b in enumerate(values):
        time(i*.5);a=evaluated();err=max(nearest(a,b),nearest(b,a));assert err<3e-5,(name,i,err);errors.append(err)
    report[name]['max_glb_vertex_error']=max(errors)
out={'geometry_uv_weights_bones_materials_texture_bytes_unchanged':True,'accepted_walk_max_vertex_difference':walk_error,
     'common_idle_entry_exit_pose':True,'clips':report,'total_export_samples':sum(x['samples'] for x in report.values())}
(BASE/'validation.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
