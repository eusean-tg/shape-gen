"""Temporary one-joint bend probes; deliberately not a production rig or UniRig test."""
import hashlib
import json
import math
from pathlib import Path
import argparse
import sys

import bpy
import numpy as np
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,default=ROOT/'assets/peasant-deformation-check/poses')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
OUT=args.output.resolve()
OUT.mkdir(parents=True,exist_ok=True)
if (OUT/'bend-probes.blend').exists():raise FileExistsError(OUT/'bend-probes.blend')
SOURCE=ROOT/'assets/peasant-hypaint-experiment/hypaint-imagegen/peasant-hypaint-imagegen.blend'
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
scene=bpy.context.scene
body=bpy.data.objects['Peasant body']
pouch=bpy.data.objects['Original BPT pouch']
v=np.array([x.co for x in body.data.vertices],dtype=float)
f=np.array([list(p.vertices) for p in body.data.polygons])
edges=np.array([list(e.vertices) for e in body.data.edges])
edge_rest=np.linalg.norm(v[edges[:,1]]-v[edges[:,0]],axis=1)
uv_before=np.array([tuple(x.uv) for x in body.data.uv_layers.active.data])
body.shape_key_add(name='Basis')
mid=-.022240788
x,y,z=v.T
def smooth(a,b,value):
    t=np.clip((value-a)/(b-a),0,1)
    return t*t*(3-2*t)
arm=smooth(-.045,.055,(mid-x)-np.minimum(.255,.205+.40*(.40-z)))*(1-smooth(.58,.67,z))*smooth(-.34,-.27,z)
# Separate the distal arm by mesh connectivity. A spatial mask alone can catch
# nearby belt/pouch attachment vertices, despite their belonging to the torso.
neighbors={i:set() for i in range(len(v))}
for a,b in edges:
    neighbors[a].add(b);neighbors[b].add(a)
allowed=set(np.flatnonzero(z<.37))
seed=int(np.linalg.norm(v-[-.49,.1,-.05],axis=1).argmin())
distal={seed};queue=[seed]
while queue:
    for j in neighbors[queue.pop()]:
        if j in allowed and j not in distal:
            distal.add(j);queue.append(j)
arm[z<.37]=0
arm[list(distal)]=1
forearm_dir=np.array([-.12,0,-.30]);forearm_dir/=np.linalg.norm(forearm_dir)
elbow_weight=arm*smooth(-.06,.06,(v-np.array([-.365,.085,.245]))@forearm_dir)
leftleg=1-smooth(mid-.035,mid+.035,x)
hip_weight=leftleg*(1-smooth(-.25,.02,z))*(1-smooth(.26,.30,np.abs(x-mid)))
knee_weight=leftleg*(1-smooth(-.585,-.435,z))

def matrix(axis,degrees):
    c,s=math.cos(math.radians(degrees)),math.sin(math.radians(degrees))
    if axis=='X':return np.array([[1,0,0],[0,c,-s],[0,s,c]])
    if axis=='Y':return np.array([[c,0,s],[0,1,0],[-s,0,c]])
    raise ValueError(axis)

tests=[
    ('shoulder-raise-60',[-.255,.10,.51],'Y',60,arm,[-.27,.09,.46],.93,[-.6,-1,.05]),
    ('elbow-bend-60',[-.365,.085,.245],'X',-60,elbow_weight,[-.365,-.04,.245],.68,[-1,-.25,.1]),
    ('elbow-bend-90',[-.365,.085,.245],'X',-90,elbow_weight,[-.365,-.04,.245],.68,[-1,-.25,.1]),
    ('hip-lift-45',[-.14,.105,-.115],'X',-45,hip_weight,[-.12,.04,-.14],.87,[-1,-.65,.12]),
    ('knee-bend-60',[-.15,.10,-.51],'X',60,knee_weight,[-.15,.14,-.50],.62,[-1,-.25,.08]),
    ('knee-bend-90',[-.15,.10,-.51],'X',90,knee_weight,[-.15,.14,-.50],.62,[-1,-.25,.08]),
]
# Repeat the main probes on the opposite side. Find the corresponding vertices
# for masks using the nearly symmetric rest mesh; retain the actual geometry.
mirror=v.copy();mirror[:,0]=2*mid-mirror[:,0]
match=np.argmin(np.linalg.norm(mirror[:,None,:]-v[None,:,:],axis=2),axis=1)
for name,pivot,axis,angle,weight,center,scale,direction in list(tests):
    if name in ('elbow-bend-60','knee-bend-60'):continue
    pivot=list(pivot);pivot[0]=2*mid-pivot[0]
    center=list(center);center[0]=2*mid-center[0]
    direction=list(direction);direction[0]*=-1
    tests.append((name+'-opposite',pivot,axis,-angle if axis=='Y' else angle,
                  weight[match],center,scale,direction))

report={'method':'One-joint linear blend bend probes with hand-estimated pivots and smooth spatial masks. Not UniRig output, automatic weights, or a production armature.',
        'interpretation':'Results depend on pivot/weight choices. Pinching alone cannot distinguish topology from weights. Each test is independent; pouch stays rigid in pelvis space.',
        'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'tests':[]}
wiremesh=body.data.copy()
wire=bpy.data.objects.new('Bend-probe wire overlay',wiremesh)
scene.collection.objects.link(wire)
wire.data.shape_keys and wire.shape_key_clear()
wm=wire.modifiers.new('Thin topology lines','WIREFRAME');wm.thickness=.0012;wm.use_replace=True;wm.offset=1
wire.color=(.01,.015,.02,1)
body.color=(.63,.68,.73,1);pouch.color=(.40,.45,.50,1)
scene.render.resolution_x=scene.render.resolution_y=800
scene.render.resolution_percentage=100
scene.render.threads_mode='FIXED';scene.render.threads=6
scene.cycles.samples=16
camera=scene.camera
def render(name,center,direction,scale,texture):
    camera.data.ortho_scale=scale
    camera.location=Vector(center)+Vector(direction).normalized()*4
    camera.rotation_euler=(Vector(center)-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.engine='CYCLES' if texture else 'BLENDER_WORKBENCH'
    wire.hide_render=texture
    scene.display.shading.light='STUDIO';scene.display.shading.color_type='OBJECT'
    scene.display.shading.show_cavity=True;scene.display.shading.cavity_type='BOTH'
    scene.render.filepath=str(OUT/(name+'.png'))
    bpy.ops.render.render(write_still=True)

for name,pivot,axis,angle,weight,center,scale,direction in tests:
    p=np.array(pivot)
    rotated=(v-p)@matrix(axis,angle).T+p
    posed=v+weight[:,None]*(rotated-v)
    key=body.shape_key_add(name=name)
    key.data.foreach_set('co',posed.ravel());key.value=1
    wire.data.vertices.foreach_set('co',posed.ravel());wire.data.update()
    posed_lengths=np.linalg.norm(posed[edges[:,1]]-posed[edges[:,0]],axis=1)
    ratios=posed_lengths/np.maximum(edge_rest,1e-12)
    # Count only edges crossing a non-rigid blend zone; rigid segments do not change length.
    affected=(weight[edges].max(1)>.01)&(weight[edges].min(1)<.99)
    signed_areas=np.linalg.norm(np.cross(posed[f[:,1]]-posed[f[:,0]],posed[f[:,2]]-posed[f[:,0]]),axis=1)/2
    orig_areas=np.linalg.norm(np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]),axis=1)/2
    report['tests'].append({'name':name,'pivot':pivot,'axis':axis,'degrees':angle,
        'affected_vertices':int((weight>.01).sum()),'transition_edges':int(affected.sum()),
        'transition_edge_length_ratio_min':float(ratios[affected].min()),
        'transition_edge_length_ratio_max':float(ratios[affected].max()),
        'faces_below_25_percent_rest_area':int((signed_areas<orig_areas*.25).sum()),
        'zero_area_faces':int((signed_areas<1e-10).sum())})
    (OUT/(name+'-mesh.json')).write_text(json.dumps({'vertices':posed.tolist(),'faces':f.tolist()}))
    render(name+'-wire',center,direction,scale,False)
    render(name+'-texture',center,direction,scale,True)
    if name in ('shoulder-raise-60','hip-lift-45'):
        render(name+'-full',[-.08,.06,-.008],[-.4,-1,.07],2.45,True)
    key.value=0

bpy.data.objects.remove(wire,do_unlink=True)
assert np.array_equal(v,np.array([x.co for x in body.data.vertices]))
assert np.array_equal(uv_before,np.array([tuple(x.uv) for x in body.data.uv_layers.active.data]))
assert np.array_equal(f,np.array([list(p.vertices) for p in body.data.polygons]))
report['basis_positions_faces_uvs_unchanged']=True
(OUT/'bend-probes.json').write_text(json.dumps(report,indent=2)+'\n')
scene.render.engine='CYCLES'
camera.data.ortho_scale=2.3;camera.location=(-1.3,-3,.2)
camera.rotation_euler=(Vector((-.022,.06,-.008))-camera.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.select_all(action='DESELECT');body.select_set(True);bpy.context.view_layer.objects.active=body
body['review_note']='Temporary bend probes in Shape Keys. All default to zero. This is NOT the final rig. See README.md.'
target=OUT/'bend-probes.blend'
if target.exists():raise FileExistsError(target)
bpy.ops.wm.save_as_mainfile(filepath=str(target))
print(json.dumps(report,indent=2))
