"""Extract the accepted textured walk for cycle/contact analysis (read only)."""
from pathlib import Path
import json
import argparse,sys
import bpy
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,default=ROOT/'assets/peasant-material-masks/masked/peasant-walk.blend')
parser.add_argument('--output',type=Path,default=ROOT/'assets/peasant-walk-cycle')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
OUT=args.output.resolve();OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(args.source.resolve()))
arm=bpy.data.objects['Peasant rig'];body=bpy.data.objects['Peasant body'];scene=bpy.context.scene
names=[b.name for b in arm.pose.bones]
q=[];loc=[];mat=[];heads=[];vertices=[]
for frame in range(1,121):
    scene.frame_set(frame);bpy.context.view_layer.update()
    q.append([tuple(b.rotation_quaternion) for b in arm.pose.bones]);loc.append([tuple(b.location) for b in arm.pose.bones])
    mat.append([np.array(b.matrix) for b in arm.pose.bones]);heads.append([tuple(arm.matrix_world@b.head) for b in arm.pose.bones])
    ob=body.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ob.to_mesh();vertices.append([tuple(ob.matrix_world@v.co) for v in me.vertices]);ob.to_mesh_clear()
rest=np.array([tuple(v.co) for v in body.data.vertices]);weights=np.zeros((len(rest),len(names)))
for v in body.data.vertices:
    for g in v.groups:
        name=body.vertex_groups[g.group].name
        if name in names:weights[v.index,names.index(name)]=g.weight
np.savez_compressed(OUT/'source-samples.npz',quaternions=q,locations=loc,matrices=mat,heads=heads,vertices=vertices,
    names=names,rest_vertices=rest,weights=weights,rest_matrices=[np.array(b.matrix_local) for b in arm.data.bones],
    arm_matrix=np.array(arm.matrix_world),parents=[names.index(b.parent.name) if b.parent else -1 for b in arm.pose.bones])
info={'bones':{b.name:{'head':list(b.head_local),'tail':list(b.tail_local),'length':b.length} for b in arm.data.bones},
    'arm_matrix':np.array(arm.matrix_world).tolist(),'body_matrix':np.array(body.matrix_world).tolist()}
(OUT/'source-rig.json').write_text(json.dumps(info,indent=2)+'\n')
print('Saved read-only motion samples',OUT)
