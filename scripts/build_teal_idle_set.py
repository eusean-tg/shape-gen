"""Clean generated idle motions, pin standing feet, and export five actions."""
import hashlib,json,math
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix,Quaternion,Vector

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'assets/teal-peasant/idle-set'
SOURCE=ROOT/'assets/teal-peasant/collar-fix/final/peasant-walk.blend'
FPS=60;N=240
samples={k:dict(np.load(BASE/'generated'/k/'samples/source-samples.npz'))
         for k in ['breathe','look-around','weight-shift','adjust-sleeve']}
bpy.ops.wm.open_mainfile(filepath=str(SOURCE));scene=bpy.context.scene
arm=bpy.data.objects['Peasant rig'];body=bpy.data.objects['Peasant body']
walk=arm.animation_data.action;walk.name='Walk';walk.use_fake_user=True
for action in list(bpy.data.actions):
    if action!=walk:bpy.data.actions.remove(action)
names=[b.name for b in arm.pose.bones];idx={n:i for i,n in enumerate(names)}
rest={b.name:b.matrix_local.copy() for b in arm.data.bones}
root_rest=rest['pelvis'].to_3x3();raw=samples['breathe']
scene.render.fps=FPS;scene.frame_start=1;scene.frame_end=N+1
scene.use_preview_range=False;scene.timeline_markers.clear()

def normalize(q):return q/np.linalg.norm(q,axis=-1,keepdims=True)
def continuous(q):
    q=q.copy()
    for i in range(1,len(q)):q[i,np.sum(q[i]*q[i-1],axis=-1)<0]*=-1
    return q

qraw=continuous(raw['quaternions'])
base=normalize(np.mean(qraw[20:100],axis=0))
for name in ['pelvis','neck','head']:
    base[idx[name]]=[1,0,0,0]
lower=[i for i,n in enumerate(names) if n.startswith(('thigh.','shin.','foot.','toe.'))]
base[lower]=[1,0,0,0]
# Author a relaxed common stance in armature space (forward is -Y). The
# generated breathing mean places both wrists behind the back. Aim the upper
# arms slightly forward and add a gentle elbow bend, retaining generated twist.
arm.animation_data_clear()
for j,pb in enumerate(arm.pose.bones):
    pb.rotation_mode='QUATERNION';pb.rotation_quaternion=Quaternion(base[j]);pb.location=(0,0,0);pb.scale=(1,1,1)
bpy.context.view_layer.update()
stance={}
for side,sign in [('L',1),('R',-1)]:
    for name,direction in [('upper_arm',(sign*.080,-.020,-.274)),('forearm',(sign*.040,-.075,-.308))]:
        pb=arm.pose.bones[name+'.'+side]
        old=pb.tail-pb.head
        rotation=old.rotation_difference(Vector(direction))@pb.matrix.to_quaternion()
        pb.matrix=Matrix.LocRotScale(pb.head.copy(),rotation,Vector((1,1,1)))
        bpy.context.view_layer.update()
        base[idx[pb.name]]=pb.rotation_quaternion[:]
    stance[side]={n:list(arm.pose.bones[n+'.'+side].head) for n in ['upper_arm','forearm','hand']}
# A periodic low-frequency fit keeps the generated subtle body/arm motion.
phase=np.arange(120)/120;target=np.arange(N+1)/N
design=lambda x:np.column_stack([np.ones_like(x),np.sin(2*np.pi*x),np.cos(2*np.pi*x),np.sin(4*np.pi*x),np.cos(4*np.pi*x)])
residual=qraw-qraw.mean(0)
fitted=(design(target)@np.linalg.lstsq(design(phase),residual.reshape(120,-1),rcond=None)[0]).reshape(N+1,len(names),4)
breath=normalize(base[None]+fitted*.65)
breath[:,lower]=base[lower];breath[:,idx['pelvis']]=base[idx['pelvis']]
# Keep the face facing forward in the quiet idle; looking is an accent.
for name in ['neck','head']:breath[:,idx[name]]=normalize(base[idx[name]]+fitted[:,idx[name]]*.25)
breath[-1]=breath[0]
anchors={s:arm.data.bones['foot.'+s].head_local.copy()+Vector((0,0,.001)) for s in ['L','R']}
sole={s:np.load(ROOT/'assets/teal-peasant/collar-fix/cycle-analysis.npz')['sole_'+s] for s in ['L','R']}

def evaluated():
    obj=body.evaluated_get(bpy.context.evaluated_depsgraph_get());me=obj.to_mesh()
    result=np.array([(obj.matrix_world@v.co)[:] for v in me.vertices]);obj.to_mesh_clear();return result

def solve_leg(side,target):
    thigh,shin,foot,toe=[arm.pose.bones[n+'.'+side] for n in ['thigh','shin','foot','toe']]
    H,K,A=thigh.head.copy(),shin.head.copy(),foot.head.copy()
    upper,lower=thigh.matrix.to_3x3(),shin.matrix.to_3x3()
    l1,l2=(K-H).length,(A-K).length
    axis=target-H;distance=axis.length;axis.normalize();distance=min(distance,l1+l2-1e-6)
    along=(l1*l1-l2*l2+distance*distance)/(2*distance)
    height=math.sqrt(max(l1*l1-along*along,0))
    forward=Vector((0,-1,0));bend=(forward-axis*forward.dot(axis)).normalized()
    knee=H+axis*along+bend*height;ankle=H+axis*distance
    thigh.matrix=Matrix.LocRotScale(H,((K-H).rotation_difference(knee-H).to_matrix()@upper).to_quaternion(),Vector((1,1,1)))
    bpy.context.view_layer.update()
    shin.matrix=Matrix.LocRotScale(knee,((A-K).rotation_difference(ankle-knee).to_matrix()@lower).to_quaternion(),Vector((1,1,1)))
    bpy.context.view_layer.update()
    foot.matrix=Matrix.LocRotScale(foot.head.copy(),rest[foot.name].to_quaternion(),Vector((1,1,1)))
    bpy.context.view_layer.update()
    toe.matrix=Matrix.LocRotScale(toe.head.copy(),rest[toe.name].to_quaternion(),Vector((1,1,1)))
    bpy.context.view_layer.update()

actions=[walk];report={};analysis={}
for key,action_name in [('breathe','Idle_Breathe'),('look-around','Idle_LookAround'),('weight-shift','Idle_WeightShift'),('adjust-sleeve','Idle_HandCheck')]:
    arm.animation_data_clear();src=continuous(samples[key]['quaternions']);all_q=[];all_l=[];vertices=[]
    for i in range(N+1):
        t=i/FPS;u=min(i/N*119,119);a=int(u);b=min(a+1,119);frac=u-a
        q=breath[i].copy();ramp=min(1,t/.75,(4-t)/.85);ramp=max(0,ramp);envelope=ramp*ramp*(3-2*ramp)
        if key!='breathe':
            selected=['spine','chest','upper_chest','neck','head']
            if key=='adjust-sleeve':selected += [n for n in names if n.startswith(('clavicle.','upper_arm.','forearm.','hand.'))]
            for name in selected:
                j=idx[name];motion=Quaternion(src[a,j]).slerp(Quaternion(src[b,j]),frac)
                if key!='adjust-sleeve':
                    delta=Quaternion(src[0,j]).inverted()@motion
                    motion=Quaternion(base[j])@delta
                amount=envelope*(.8 if key=='weight-shift' else 1.)
                q[j]=Quaternion(q[j]).slerp(motion,amount)
        for j,pb in enumerate(arm.pose.bones):
            pb.rotation_mode='QUATERNION';pb.rotation_quaternion=Quaternion(q[j]);pb.location=(0,0,0);pb.scale=(1,1,1)
        shift=.025*math.sin(2*math.pi*i/N)*envelope if key=='weight-shift' else 0
        arm.pose.bones['pelvis'].location=root_rest.transposed()@Vector((shift,0,-.018))
        bpy.context.view_layer.update()
        targets={s:anchors[s].copy() for s in anchors}
        for s in anchors:solve_leg(s,targets[s])
        for _ in range(2):
            verts=evaluated()
            for s in anchors:
                targets[s].z+=.001-float(verts[sole[s],2].min());solve_leg(s,targets[s])
        all_q.append([pb.rotation_quaternion[:] for pb in arm.pose.bones]);all_l.append([pb.location[:] for pb in arm.pose.bones]);vertices.append(evaluated())
    all_q=continuous(np.array(all_q));all_l=np.array(all_l);all_q[-1]=all_q[0];all_l[-1]=all_l[0]
    for i in range(N+1):
        for j,pb in enumerate(arm.pose.bones):
            pb.rotation_quaternion=Quaternion(all_q[i,j]);pb.location=all_l[i,j]
            pb.keyframe_insert('rotation_quaternion',frame=i+1,group=pb.name);pb.keyframe_insert('location',frame=i+1,group=pb.name)
    action=arm.animation_data.action;action.name=action_name;action.use_fake_user=True
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    for point in curve.keyframe_points:point.interpolation='LINEAR'
    actions.append(action);vertices=np.array(vertices)
    report[action_name]={'duration':4,'frames':N+1,'source':str(BASE/'generated'/key/'motion.npz'),
       'endpoint_vertex_error':float(abs(vertices[-1]-vertices[0]).max()),
       'sole_drift':{s:float(np.linalg.norm(np.ptp(vertices[:,sole[s]],axis=0),axis=1).max()) for s in sole}}
    analysis[action_name]=vertices
    scene.frame_set(1)
    print(action_name,report[action_name],flush=True)

arm.animation_data.action=actions[1]
# NLA references make all actions discoverable without blending them in Blender.
for action in actions:
    track=arm.animation_data.nla_tracks.new();track.name=action.name
    track.strips.new(action.name,1,action);track.mute=True
arm.animation_data.action=actions[1];scene.frame_set(1)
bpy.ops.object.select_all(action='DESELECT');body.select_set(True);arm.select_set(True);bpy.context.view_layer.objects.active=arm
out=BASE/'final';out.mkdir(exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'teal-character.blend'))
bpy.ops.export_scene.gltf(filepath=str(out/'teal-character.glb'),export_format='GLB',use_selection=True,
 export_yup=True,export_skins=True,export_animations=True,export_frame_range=False,
 export_force_sampling=True,export_def_bones=True,export_materials='EXPORT',
 export_animation_mode='ACTIONS',export_merge_animation='NONE',export_anim_slide_to_zero=True,export_extras=True)
np.savez_compressed(BASE/'idle-analysis.npz',**analysis)
(BASE/'build.json').write_text(json.dumps({'source':str(SOURCE),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
 'fps':FPS,'clips':report,'walk_preserved':True,'geometry_weights_uvs_textures_changed':False,
 'neutral_arm_joints':stance,
 'cleanup':'Periodic breathing fit; relaxed forward arm stance with gentle elbow bend, stable leg IK, .75/.85s accent entry/exit envelopes; weight-shift pelvis sway authored.'},indent=2)+'\n')
