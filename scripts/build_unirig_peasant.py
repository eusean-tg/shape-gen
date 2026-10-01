"""Build an editable Blender rig on the original mesh, render probes and export GLB."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector,Quaternion

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'assets/peasant-unirig'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,default=BASE/'raw-rig')
parser.add_argument('--weights',type=Path,default=BASE/'rig-data.npz')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
OUT=args.output.resolve();OUT.mkdir(parents=True,exist_ok=True)
if (OUT/'peasant-rigged.blend').exists():raise FileExistsError(OUT/'peasant-rigged.blend')
SOURCE=ROOT/'assets/peasant-hypaint-experiment/hypaint-imagegen/peasant-hypaint-imagegen.blend'
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
body=bpy.data.objects['Peasant body'];pouch=bpy.data.objects['Original BPT pouch']
data=np.load(args.weights,allow_pickle=False)
names=data['names'].tolist();joints=data['joints'];tails=data['tails'];parents=data['parents'];weights=data['weights']
assert np.array_equal(np.array([body.matrix_world@v.co for v in body.data.vertices]),data['vertices'])
source_uv=np.array([tuple(x.uv) for x in body.data.uv_layers.active.data])
source_faces=np.array([list(f.vertices) for f in body.data.polygons])
arm_data=bpy.data.armatures.new('UniRig skeleton')
arm=bpy.data.objects.new('Peasant rig',arm_data);bpy.context.scene.collection.objects.link(arm)
bpy.ops.object.select_all(action='DESELECT');arm.select_set(True);bpy.context.view_layer.objects.active=arm
bpy.ops.object.mode_set(mode='EDIT')
for i,name in enumerate(names):
    bone=arm_data.edit_bones.new(name);bone.head=joints[i];bone.tail=tails[i]
    if bone.length<.001:bone.tail=bone.head+Vector((0,0,.025))
    if parents[i]>=0:bone.parent=arm_data.edit_bones[names[parents[i]]]
    bone.use_connect=False
bpy.ops.object.mode_set(mode='OBJECT')
arm.show_in_front=True;arm.data.display_type='OCTAHEDRAL'
for bone in arm.data.bones:
    bone['unirig_original_index']=names.index(bone.name)
    try:bone.color.palette='THEME04' if bone.name.endswith('.L') else 'THEME03' if bone.name.endswith('.R') else 'THEME02'
    except AttributeError:pass
for obj in [body,pouch]:
    mat=obj.matrix_world.copy();obj.parent=arm;obj.matrix_world=mat
    modifier=obj.modifiers.new('UniRig skinning','ARMATURE');modifier.object=arm
    modifier.use_deform_preserve_volume=False # glTF uses linear blend skinning.
    for group in list(obj.vertex_groups):obj.vertex_groups.remove(group)
    for name in names:obj.vertex_groups.new(name=name)
    if obj==body:
        for i,row in enumerate(weights):
            for j in np.flatnonzero(row>0):obj.vertex_groups[names[j]].add([i],float(row[j]),'REPLACE')
    else:obj.vertex_groups['pelvis'].add(list(range(len(obj.data.vertices))),1.0,'REPLACE')
arm['rig_note']='UniRig skeleton and learned body weights. Pouch rigid to pelvis. FK controls; no IK or HY-Motion generated clip.'
scene=bpy.context.scene;scene.render.threads_mode='FIXED';scene.render.threads=6
scene.render.resolution_x=scene.render.resolution_y=800;scene.render.resolution_percentage=100
scene.cycles.samples=24;scene.render.fps=24
camera=scene.camera
wire=body.copy();wire.data=body.data.copy();wire.name='Temporary wire overlay';scene.collection.objects.link(wire)
wf=wire.modifiers.new('Topology edges','WIREFRAME');wf.thickness=.0011;wf.use_replace=True;wf.offset=1
wire.color=(.012,.02,.025,1);body.color=(.63,.68,.73,1);pouch.color=(.4,.45,.5,1)
def reset():
    for p in arm.pose.bones:p.rotation_mode='QUATERNION';p.rotation_quaternion=Quaternion()
def rotate(name,axis,degrees):
    import math
    bone=arm.pose.bones[name]
    local_axis=bone.bone.matrix_local.to_3x3().inverted()@Vector(axis)
    bone.rotation_quaternion=Quaternion(local_axis,math.radians(degrees))
def render(name,center,direction,scale,texture=True):
    camera.data.type='ORTHO';camera.data.ortho_scale=scale
    camera.location=Vector(center)+Vector(direction).normalized()*4
    camera.rotation_euler=(Vector(center)-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.engine='CYCLES' if texture else 'BLENDER_WORKBENCH'
    wire.hide_render=texture
    scene.display.shading.light='STUDIO';scene.display.shading.color_type='OBJECT'
    scene.display.shading.show_cavity=True;scene.display.shading.cavity_type='BOTH'
    scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
def evaluated(obj):
    bpy.context.view_layer.update()
    ob=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ob.to_mesh()
    v=np.array([ob.matrix_world@x.co for x in mesh.vertices]);ob.to_mesh_clear();return v
reset()
assert np.max(np.abs(evaluated(body)-data['vertices']))<2e-6
render('rest',[-.022,.06,-.008],[-.4,-1,.07],2.35)
tests=[
 ('shoulder-raise-60','upper_arm.R',(0,1,0),60,[-.27,.09,.46],.95,[-.6,-1,.05]),
 ('elbow-bend-60','forearm.R',(1,0,0),-60,[-.365,-.04,.245],.68,[-1,-.25,.1]),
 ('elbow-bend-90','forearm.R',(1,0,0),-90,[-.365,-.04,.245],.68,[-1,-.25,.1]),
 ('hip-lift-45','thigh.R',(1,0,0),-45,[-.12,.04,-.14],.87,[-1,-.65,.12]),
 ('knee-bend-60','shin.R',(1,0,0),60,[-.15,.14,-.50],.62,[-1,-.25,.08]),
 ('knee-bend-90','shin.R',(1,0,0),90,[-.15,.14,-.50],.62,[-1,-.25,.08]),
]
mid=-.022240788
for name,bone,axis,deg,center,scale,direction in list(tests):
    if name in ('elbow-bend-60','knee-bend-60'):continue
    center=list(center);center[0]=2*mid-center[0]
    direction=list(direction);direction[0]*=-1
    tests.append((name+'-opposite',bone.replace('.R','.L'),axis,-deg if axis==(0,1,0) else deg,center,scale,direction))
tests.extend([
 ('hip-lift-20','thigh.R',(1,0,0),-20,[-.12,.04,-.14],.87,[-1,-.65,.12]),
 ('hip-lift-20-opposite','thigh.L',(1,0,0),-20,[.08,.04,-.14],.87,[1,-.65,.12]),
 ('head-turn-30','head',(0,0,1),30,[-.022,.05,.73],.65,[-.4,-1,.07]),
 ('chest-turn-20','upper_chest',(0,0,1),20,[-.022,.05,.4],1.4,[-.4,-1,.07]),
])
report={'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'bones':len(names),'body_vertices':len(body.data.vertices),
        'total_triangles':len(body.data.polygons)+len(pouch.data.polygons),'tests':[]}
for name,bone,axis,deg,center,scale,direction in tests:
    reset();rotate(bone,axis,deg);bpy.context.view_layer.update()
    np.savez(OUT/(name+'-mesh.npz'),vertices=evaluated(body),faces=source_faces,
             pouch_vertices=evaluated(pouch),pouch_faces=np.array([list(f.vertices) for f in pouch.data.polygons]))
    render(name+'-texture',center,direction,scale)
    render(name+'-wire',center,direction,scale,False)
    if name in ('shoulder-raise-60','hip-lift-45'):render(name+'-full',[-.08,.06,-.008],[-.4,-1,.07],2.45)
    report['tests'].append({'name':name,'bone':bone,'axis':axis,'degrees':deg})
bpy.data.objects.remove(wire,do_unlink=True)
# Add a simple reproducible pose-check action. It is a validation clip, not a
# generated performance; the actual HY-Motion integration remains a later step.
def key(frame):
    for pb in arm.pose.bones:pb.keyframe_insert(data_path='rotation_quaternion',frame=frame,group=pb.name)
reset();key(1)
for i,(name,bone,axis,deg,*_) in enumerate(tests):
    reset();key(i*24+1);rotate(bone,axis,deg);key(i*24+13)
    scene.timeline_markers.new(name,frame=i*24+13)
    reset();key(i*24+25)
action=arm.animation_data.action;action.name='Deformation checks'
for layer in action.layers:
    for strip in layer.strips:
        for bag in strip.channelbags:
            for fc in bag.fcurves:
                for k in fc.keyframe_points:k.interpolation='LINEAR'
scene.frame_start=1;scene.frame_end=len(tests)*24+1;scene.frame_set(1)
reset();bpy.context.view_layer.update()
assert np.array_equal(source_uv,np.array([tuple(x.uv) for x in body.data.uv_layers.active.data]))
assert np.array_equal(source_faces,np.array([list(f.vertices) for f in body.data.polygons]))
assert np.max(np.abs(evaluated(body)-data['vertices']))<2e-6
scene.render.engine='CYCLES'
camera.data.ortho_scale=2.35;camera.location=(-1.3,-3,.2)
camera.rotation_euler=(Vector((-.022,.06,-.008))-camera.location).to_track_quat('-Z','Y').to_euler()
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.shading.type='MATERIAL'
            area.spaces.active.overlay.show_extras=False
            area.spaces.active.region_3d.view_location=(-.022,.06,-.008)
            area.spaces.active.region_3d.view_distance=3.2
bpy.ops.object.select_all(action='DESELECT')
for obj in [body,pouch,arm]:obj.select_set(True)
bpy.context.view_layer.objects.active=arm
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'peasant-rigged.blend'))
bpy.ops.export_scene.gltf(filepath=str(OUT/'peasant-rigged.glb'),export_format='GLB',use_selection=True,
    export_yup=True,export_skins=True,export_animations=True,export_frame_range=True,export_force_sampling=True,
    export_def_bones=True,export_materials='EXPORT')
report.update(rest_mesh_uvs_unchanged=True,action='Deformation checks',action_frames=[1,scene.frame_end],
              weights_source=str(args.weights),pouch_binding='rigid pelvis')
(OUT/'rig-build.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
