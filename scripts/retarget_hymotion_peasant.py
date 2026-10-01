"""Retarget HY-Motion's world-space joint rotations to the existing UniRig peasant."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import bpy
import numpy as np
from mathutils import Matrix,Vector,Quaternion

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--motion',type=Path,default=ROOT/'assets/peasant-hymotion/walk/motion.npz')
parser.add_argument('--output',type=Path,default=ROOT/'assets/peasant-hymotion/walk/retarget')
parser.add_argument('--arm-clearance',type=float,default=0,help='Additional shoulder abduction in degrees for this character.')
parser.add_argument('--ground-feet',action='store_true',help='Walking-only root-height correction so the lowest foot touches the ground.')
parser.add_argument('--level-foot-rest',action='store_true',help='Align foot/toe rest headings horizontally, avoiding pitch from different ankle heights.')
parser.add_argument('--source',type=Path,default=ROOT/'assets/peasant-unirig/final/peasant-rigged.blend')
parser.add_argument('--no-pouch',action='store_true')
parser.add_argument('--skip-renders',action='store_true')
parser.add_argument('--clip-name',default='HY-Motion - relaxed walk - seed 12345')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
OUT=args.output.resolve();OUT.mkdir(parents=True,exist_ok=True)
if (OUT/'peasant-walk.blend').exists():raise FileExistsError(OUT/'peasant-walk.blend')
source=args.source.resolve()
bpy.ops.wm.open_mainfile(filepath=str(source))
arm=bpy.data.objects['Peasant rig'];body=bpy.data.objects['Peasant body'];pouch=None if args.no_pouch else bpy.data.objects['Original BPT pouch']
scene=bpy.context.scene
arm.animation_data_clear();scene.timeline_markers.clear()
motion=np.load(args.motion);local=motion['rotations'][0];trans=motion['transl'][0]
sj=motion['rest_joints'];parents=motion['parents'];frames=len(local)
mapping={'pelvis':0,'spine':3,'chest':6,'upper_chest':9,'neck':12,'head':15,
    'clavicle.L':13,'upper_arm.L':16,'forearm.L':18,'hand.L':20,
    'clavicle.R':14,'upper_arm.R':17,'forearm.R':19,'hand.R':21,
    'thigh.L':1,'shin.L':4,'foot.L':7,'toe.L':10,
    'thigh.R':2,'shin.R':5,'foot.R':8,'toe.R':11}
endpoints={0:3,3:6,6:9,9:12,12:15,13:16,16:18,18:20,20:25,
           14:17,17:19,19:21,21:40,1:4,4:7,7:10,2:5,5:8,8:11}
# HY-Motion Y-up / +Z forward -> Blender Z-up / -Y forward.
C=Matrix(((1,0,0),(0,0,-1),(0,1,0)))
rest={b.name:b.matrix_local.to_3x3() for b in arm.data.bones}
align={}
foot_rest_corrections={}
for name,i in mapping.items():
    bone=arm.data.bones[name]
    vector=Vector(sj[endpoints[i]]-sj[i]) if i in endpoints else Vector(sj[i]-sj[parents[i]])
    # Root rotations control the body's overall frame, not a tilted spine segment.
    align[name]=Matrix.Identity(3) if name=='pelvis' else (bone.tail_local-bone.head_local).rotation_difference(C@vector).to_matrix()
    if args.level_foot_rest and name.startswith(('foot.','toe.')):
        import math
        target=bone.tail_local-bone.head_local;reference=C@vector
        old_forward=align[name]@Vector((0,-1,0))
        target.z=0;reference.z=0
        assert min(target.length,reference.length)>.001
        align[name]=target.rotation_difference(reference).to_matrix()
        foot_rest_corrections[name]={
            'previous_rest_forward_pitch_degrees':math.degrees(math.atan2(old_forward.z,math.hypot(old_forward.x,old_forward.y))),
            'new_rest_forward_pitch_degrees':0.,
        }
def chain_length(j,a,b,c):return float(np.linalg.norm(j[a]-j[b])+np.linalg.norm(j[b]-j[c]))
target_j=np.array([arm.data.bones[n].head_local for n in ['thigh.L','shin.L','foot.L','thigh.R','shin.R','foot.R']])
scale=(chain_length(target_j,0,1,2)+chain_length(target_j,3,4,5))/(chain_length(sj,1,4,7)+chain_length(sj,2,5,8))
root_origin=arm.data.bones['pelvis'].head_local.copy()
scene.render.fps=30;scene.frame_start=1;scene.frame_end=frames
previous={}
for frame in range(frames):
    global_rot=[]
    for i in range(22):global_rot.append(Matrix(local[frame,i]) if parents[i]<0 else global_rot[parents[i]]@Matrix(local[frame,i]))
    deform={}
    for pb in arm.pose.bones:
        if pb.name in mapping:
            deform[pb.name]=C@global_rot[mapping[pb.name]]@C.transposed()@align[pb.name]
            if args.arm_clearance and pb.name.startswith(('upper_arm.','forearm.','hand.')):
                import math
                axis=C@global_rot[9]@C.transposed()@Vector((0,1,0))
                angle=math.radians(args.arm_clearance)*(-1 if pb.name.endswith('.L') else 1)
                deform[pb.name]=Quaternion(axis,angle).to_matrix()@deform[pb.name]
        else:deform[pb.name]=deform[pb.parent.name].copy()
        parent_deform=deform[pb.parent.name] if pb.parent else Matrix.Identity(3)
        basis=rest[pb.name].transposed()@parent_deform.transposed()@deform[pb.name]@rest[pb.name]
        q=basis.to_quaternion();q.normalize()
        if pb.name in previous and q.dot(previous[pb.name])<0:q.negate()
        previous[pb.name]=q.copy();pb.rotation_mode='QUATERNION';pb.rotation_quaternion=q
        pb.location=(rest[pb.name].transposed()@(C@Vector(trans[frame]-trans[0])*scale)) if not pb.parent else Vector((0,0,0))
        pb.scale=(1,1,1)
        pb.keyframe_insert('rotation_quaternion',frame=frame+1,group=pb.name)
        if not pb.parent:pb.keyframe_insert('location',frame=frame+1,group=pb.name)
action=arm.animation_data.action;action.name=args.clip_name
def evaluated(obj):
    if obj is None:return np.empty((0,3))
    ob=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ob.to_mesh()
    v=np.array([ob.matrix_world@x.co for x in me.vertices]);ob.to_mesh_clear();return v
# Place the entire clip on the ground once; preserve generated root trajectory.
minimum=1e10
for frame in range(1,frames+1):
    scene.frame_set(frame);minimum=min(minimum,float(evaluated(body)[:,2].min()))
root=arm.pose.bones['pelvis'];offset=rest['pelvis'].transposed()@Vector((0,0,-minimum))
for frame in range(1,frames+1):
    scene.frame_set(frame);root.location+=offset;root.keyframe_insert('location',frame=frame,group=root.name)
ground_corrections=[]
if args.ground_feet:
    for frame in range(1,frames+1):
        scene.frame_set(frame);height=float(evaluated(body)[:,2].min())
        root.location+=rest['pelvis'].transposed()@Vector((0,0,-height))
        root.keyframe_insert('location',frame=frame,group=root.name);ground_corrections.append(-height)
for layer in action.layers:
    for strip in layer.strips:
        for bag in strip.channelbags:
            for curve in bag.fcurves:
                for key in curve.keyframe_points:key.interpolation='LINEAR'
# Record all evaluated frames for collision and foot-contact review.
allv=[];allp=[];heads=[]
for frame in range(1,frames+1):
    scene.frame_set(frame);allv.append(evaluated(body));allp.append(evaluated(pouch))
    heads.append([tuple(pb.head) for pb in arm.pose.bones])
allv=np.array(allv);allp=np.array(allp)
np.savez_compressed(OUT/'evaluated-motion.npz',vertices=allv,pouch_vertices=allp,
    faces=np.array([list(f.vertices) for f in body.data.polygons]),
    pouch_faces=np.array([list(f.vertices) for f in pouch.data.polygons]) if pouch else np.empty((0,3),dtype=int),
    joint_heads=np.array(heads),bone_names=np.array([b.name for b in arm.pose.bones]))
scene.render.threads_mode='FIXED';scene.render.threads=6
scene.render.engine='CYCLES';scene.cycles.samples=12;scene.cycles.use_denoising=True
scene.render.resolution_x=640;scene.render.resolution_y=640;scene.render.resolution_percentage=100
cam=scene.camera;cam.data.type='ORTHO';cam.data.ortho_scale=2.7
# Render a stationary ground grid to make sliding / root motion visible.
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.007))
floor=bpy.context.object;floor.name='Motion review ground'
mat=bpy.data.materials.new('Motion ground');mat.use_nodes=True
nodes=mat.node_tree.nodes;bsdf=nodes.get('Principled BSDF');bsdf.inputs['Roughness'].default_value=.9
tex=nodes.new('ShaderNodeTexChecker');tex.inputs['Color1'].default_value=(.11,.13,.16,1);tex.inputs['Color2'].default_value=(.15,.17,.2,1);tex.inputs['Scale'].default_value=2
coord=nodes.new('ShaderNodeTexCoord');mat.node_tree.links.new(coord.outputs['Object'],tex.inputs['Vector']);mat.node_tree.links.new(tex.outputs['Color'],bsdf.inputs['Base Color']);floor.data.materials.append(mat)
for frame in ([] if args.skip_renders else [1,16,31,46,61,76,91,106,120]):
    scene.frame_set(frame)
    center=(allv[frame-1].min(0)+allv[frame-1].max(0))/2
    cam.location=Vector(center)+Vector((-2.5,-4,1.1))
    cam.rotation_euler=(Vector(center)-cam.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(OUT/f'frame-{frame:03}.png');bpy.ops.render.render(write_still=True)
scene.frame_set(1)
center=(allv[0].min(0)+allv[0].max(0))/2
cam.location=Vector(center)+Vector((-2.5,-4,1.1));cam.rotation_euler=(Vector(center)-cam.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.select_all(action='DESELECT')
for o in [arm,body,pouch]:
    if o:o.select_set(True)
bpy.context.view_layer.objects.active=arm
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':area.spaces.active.region_3d.view_location=center;area.spaces.active.region_3d.view_distance=3.5
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'peasant-walk.blend'))
bpy.ops.export_scene.gltf(filepath=str(OUT/'peasant-walk.glb'),export_format='GLB',use_selection=True,
    export_yup=True,export_skins=True,export_animations=True,export_frame_range=True,
    export_force_sampling=True,export_def_bones=True,export_materials='EXPORT',
    export_animation_mode='ACTIVE_ACTIONS',export_anim_slide_to_zero=True,
    export_nla_strips_merged_animation_name=args.clip_name)
report={'source_blend':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
    'frames':frames,'fps':30,'motion_source':str(args.motion),'mapping':mapping,'leg_length_scale':scale,
    'ground_offset':-minimum,'method':'World rotation transfer with per-bone rest-direction correction; Y-up to Z-up; leg-scaled root displacement.',
    'horizontal_root_motion_preserved':True,'arm_clearance_degrees':args.arm_clearance,
    'level_foot_rest':args.level_foot_rest,'foot_rest_corrections':foot_rest_corrections,
    'ground_height_corrections':ground_corrections,'foot_ik':False,'looped':False,'geometry_and_weights_changed':False,
    'minimum_foot_height_range':[float(allv[:,:,2].min(1).min()),float(allv[:,:,2].min(1).max())]}
(OUT/'retarget.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
