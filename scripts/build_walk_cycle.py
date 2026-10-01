"""Build a periodic in-place peasant walk, then bake stance-aware two-bone IK.

The source export is only read. This is character-specific animation cleanup,
not a general motion retargeter. All output poses are ordinary editable FK keys.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'assets/peasant-walk-cycle'
SOURCE = ROOT / 'assets/peasant-material-masks/masked/peasant-walk.blend'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--inspect-base', action='store_true')
parser.add_argument('--asset-dir',type=Path,default=BASE)
parser.add_argument('--source',type=Path,default=SOURCE)
parser.add_argument('--no-pouch',action='store_true')
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
BASE=args.asset_dir.resolve();SOURCE=args.source.resolve()
BASE.mkdir(exist_ok=True)
data = np.load(BASE / 'source-samples.npz')
names = list(data['names'])
source_period = 39.1
source_fps = 30
cycle_frames = 78
fps = 60  # Denser FK bake keeps the IK contact accurate between exported keys.
period_seconds = cycle_frames / fps
phase_origin = 40  # source zero-based sample, inside a stable middle stride
sample_ids = np.arange(20, 120)
source_phase = (sample_ids - phase_origin) / source_period
phases = np.arange(cycle_frames + 1) / cycle_frames

def fourier_design(phase, harmonics):
    return np.column_stack([np.ones_like(phase)] + [f(2 * np.pi * k * phase)
        for k in range(1, harmonics + 1) for f in (np.sin, np.cos)])

def periodic_fit(values, harmonics=6):
    # Downweight the first/last samples while averaging the repeated source strides.
    weights = np.sqrt(.2 + .8 * np.sin(np.linspace(0, np.pi, len(sample_ids))) ** 2)
    design = fourier_design(source_phase, harmonics)
    coefficient = np.linalg.lstsq(design * weights[:, None],
        values[sample_ids].reshape(len(sample_ids), -1) * weights[:, None], rcond=None)[0]
    result = fourier_design(phases, harmonics) @ coefficient
    return result.reshape((len(phases),) + values.shape[1:])

q = data['quaternions'].copy()
for i in range(1, len(q)):
    q[i, np.sum(q[i] * q[i-1], axis=-1) < 0] *= -1
periodic_q = periodic_fit(q)
periodic_q /= np.linalg.norm(periodic_q, axis=-1, keepdims=True)
source_root = data['heads'][:, names.index('pelvis')]
trend = np.polyfit(sample_ids / source_fps, source_root[sample_ids, :2], 1)
velocity = trend[0]
heading = math.atan2(velocity[0], -velocity[1])
straighten = Matrix.Rotation(-heading, 3, 'Z')
root_path = source_root.copy()
root_path[:, :2] -= np.column_stack([np.arange(120) / source_fps, np.ones(120)]) @ trend
periodic_root = periodic_fit(root_path, harmonics=4)
periodic_root[:, :2] -= periodic_root[:-1, :2].mean(0)
periodic_root = np.array([straighten @ Vector(p) for p in periodic_root])
# Period is rounded to an integral number of frames; retain source stride length.
speed = float(np.linalg.norm(velocity) * (source_period / source_fps) / period_seconds)
virtual_velocity = np.array([0., -speed, 0.])

bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
scene = bpy.context.scene
arm = bpy.data.objects['Peasant rig']
body = bpy.data.objects['Peasant body']
pouch = None if args.no_pouch else bpy.data.objects['Original BPT pouch']
assert np.max(abs(np.array(arm.matrix_world) - np.eye(4))) < 1e-6
arm.animation_data_clear()
scene.timeline_markers.clear()
scene.render.fps = fps
scene.frame_start = 1
scene.frame_end = cycle_frames + 1
scene.use_preview_range = True
scene.frame_preview_start = 1
scene.frame_preview_end = cycle_frames
rest = {b.name: b.matrix_local.copy() for b in arm.data.bones}
rest_root = rest['pelvis'].to_3x3()
root_origin = arm.data.bones['pelvis'].head_local.copy()
# Rotate the entire character so average travel is forward (-Y in Blender).
root_basis_offset = rest_root.transposed() @ straighten @ rest_root
for i in range(len(phases)):
    periodic_q[i, 0] = tuple((root_basis_offset @ Quaternion(periodic_q[i, 0]).to_matrix()).to_quaternion())
periodic_q[-1] = periodic_q[0]
periodic_root[-1] = periodic_root[0]

def set_base(index, pelvis_drop=0.):
    for j, pb in enumerate(arm.pose.bones):
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = Quaternion(periodic_q[index, j])
        pb.location = (0, 0, 0)
        pb.scale = (1, 1, 1)
    position = Vector(periodic_root[index]); position.z -= pelvis_drop
    arm.pose.bones['pelvis'].location = rest_root.transposed() @ (position - root_origin)
    bpy.context.view_layer.update()

def evaluated(obj):
    ob = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = ob.to_mesh()
    vertices = np.array([tuple(ob.matrix_world @ v.co) for v in mesh.vertices])
    ob.to_mesh_clear()
    return vertices

base_matrices = []
base_vertices = []
for i in range(len(phases)):
    set_base(i)
    base_matrices.append([np.array(b.matrix) for b in arm.pose.bones])
    base_vertices.append(evaluated(body))
base_matrices = np.array(base_matrices)
base_vertices = np.array(base_vertices)
sole_ids = {}
for side in ['L', 'R']:
    foot_weights = data['weights'][:, [names.index('foot.' + side), names.index('toe.' + side)]].sum(1)
    sole_limit = (data['rest_vertices'][:,2].min()+np.ptp(data['rest_vertices'][:,2])*.015) if args.no_pouch else -.97
    sole_ids[side] = np.flatnonzero((foot_weights > .8) & (data['rest_vertices'][:, 2] < sole_limit))
    assert len(sole_ids[side])>2,('No sole vertices',side)
np.savez_compressed(BASE / 'base-analysis.npz',matrices=base_matrices,vertices=base_vertices,
    root=periodic_root,virtual_velocity=virtual_velocity,names=names,
    sole_L=sole_ids['L'],sole_R=sole_ids['R'])
print('BASE',json.dumps({'source_period_frames':source_period,'output_period_frames':cycle_frames,'speed':speed,'heading_degrees':math.degrees(heading)}))
if args.inspect_base:
    sys.exit(0)

# Contact intervals are authored from the extracted sole heights and ankle speeds.
# Indices may exceed the period: left stance wraps through the loop boundary.
contacts = {'L': {'start': 24., 'end': 47., 'ramp': 4.},
            'R': {'start': 5., 'end': 28., 'ramp': 4.}}
for settings in contacts.values():
    for key in settings: settings[key] *= fps / source_fps

def smoothstep(t):
    t = max(0., min(1., t))
    return t * t * (3 - 2 * t)

def contact_at(index, settings):
    midpoint = (settings['start'] + settings['end']) / 2
    local = (index - midpoint + cycle_frames / 2) % cycle_frames - cycle_frames / 2 + midpoint
    influence = smoothstep((local - settings['start']) / settings['ramp']) * smoothstep((settings['end'] - local) / settings['ramp'])
    return local, influence

for side, settings in contacts.items():
    foot_index = names.index('foot.' + side)
    core = [i for i in range(cycle_frames) if contact_at(i, settings)[1] > .999]
    mid = (settings['start'] + settings['end']) / 2
    # Fit a fixed support anchor in a virtually translating character's world.
    anchors = [base_matrices[i, foot_index, :3, 3] + virtual_velocity * (contact_at(i, settings)[0] - mid) / fps for i in core]
    anchor = np.mean(anchors, axis=0)
    # Flat sole orientation from the stance heading; the foot bone itself is tilted
    # in the rest rig, so flatten the mesh deformation, not the bone's Y axis.
    deformations = [Matrix(base_matrices[i, foot_index, :3, :3]) @ rest['foot.' + side].to_3x3().transposed() for i in core]
    headings = [d @ Vector((0, -1, 0)) for d in deformations]
    yaw = math.atan2(float(np.mean([v.x for v in headings])), -float(np.mean([v.y for v in headings])))
    flat_deform = Matrix.Rotation(yaw, 3, 'Z')
    sole_offset = data['rest_vertices'][sole_ids[side]] - np.array(arm.data.bones['foot.' + side].head_local)
    flat_sole = np.array([flat_deform @ Vector(v) for v in sole_offset])
    anchor[2] = -flat_sole[:, 2].min() + .001
    settings.update(anchor=anchor.tolist(), midpoint=mid, flat_yaw_radians=yaw, core_frames=[i+1 for i in core])

# Center each planted step within the leg's reachable range. Keeping the raw
# slipping anchor would require an unnecessarily deep crouch at heel strike.
for side, settings in contacts.items():
    hi = names.index('thigh.'+side); fi = names.index('foot.'+side)
    length = arm.data.bones['thigh.'+side].length + arm.data.bones['shin.'+side].length
    def required_drop(shift):
        anchor = np.array(settings['anchor']) + np.array([0., shift, 0.])
        worst = 0.
        for i in range(cycle_frames):
            local, weight = contact_at(i, settings)
            support = anchor - virtual_velocity * (local-settings['midpoint']) / fps
            target = base_matrices[i,fi,:3,3]*(1-weight)+support*weight
            hip = base_matrices[i,hi,:3,3]
            reach = math.sqrt(max((length*.995)**2-float(np.sum((hip[:2]-target[:2])**2)),.001))
            worst = max(worst,float(hip[2]-target[2]-reach))
        return worst
    shift = min(np.linspace(-.12,.12,241),key=required_drop)
    settings['anchor'][1] += float(shift)
    settings['reach_centering_shift_units'] = float(shift)

# Plan desired foot positions/orientations before solving the leg chain.
target_positions = {};target_rotations = {};toe_rotations = {};influences = {}
for side, settings in contacts.items():
    fi = names.index('foot.'+side); ti = names.index('toe.'+side)
    flat = Matrix.Rotation(settings['flat_yaw_radians'], 3, 'Z')
    flat_foot_q = (flat @ rest['foot.'+side].to_3x3()).to_quaternion()
    flat_toe_q = (flat @ rest['toe.'+side].to_3x3()).to_quaternion()
    target_positions[side] = [];target_rotations[side] = [];toe_rotations[side] = [];influences[side] = []
    for i in range(cycle_frames + 1):
        local, weight = contact_at(i, settings)
        support = np.array(settings['anchor']) - virtual_velocity * (local-settings['midpoint']) / fps
        base = base_matrices[i, fi, :3, 3]
        target_positions[side].append(base * (1-weight) + support * weight)
        target_rotations[side].append(Matrix(base_matrices[i, fi, :3, :3]).to_quaternion().slerp(flat_foot_q, weight))
        toe_rotations[side].append(Matrix(base_matrices[i, ti, :3, :3]).to_quaternion().slerp(flat_toe_q, weight))
        influences[side].append(weight)
    target_positions[side] = np.array(target_positions[side])

# A small constant pelvis lowering leaves enough knee bend for the corrected
# stance. Unlike per-frame floor offsets, it cannot introduce vertical jitter.
pelvis_drop = 0.
for side in contacts:
    hi = names.index('thigh.'+side)
    length = arm.data.bones['thigh.'+side].length + arm.data.bones['shin.'+side].length
    for i in range(cycle_frames):
        hip = base_matrices[i, hi, :3, 3]
        target = target_positions[side][i]
        horizontal = float(np.sum((hip[:2]-target[:2])**2))
        reach = math.sqrt(max((length*.995)**2-horizontal, .001))
        pelvis_drop = max(pelvis_drop, float(hip[2]-target[2]-reach))
pelvis_drop = max(0., pelvis_drop + .003)
assert pelvis_drop < .12, f'Contact plan needs excessive pelvis lowering: {pelvis_drop}'

solver_errors=[]
def solve_leg(side, target, foot_rotation, toe_rotation):
    thigh=arm.pose.bones['thigh.'+side];shin=arm.pose.bones['shin.'+side]
    foot=arm.pose.bones['foot.'+side];toe=arm.pose.bones['toe.'+side]
    H=thigh.head.copy();K=shin.head.copy();A=foot.head.copy()
    upper=thigh.matrix.to_3x3();lower=shin.matrix.to_3x3()
    length1=(K-H).length;length2=(A-K).length
    target=Vector(target);axis=target-H;distance=axis.length;axis.normalize()
    clamped=max(abs(length1-length2)+1e-6,min(distance,length1+length2-1e-6))
    along=(length1*length1-length2*length2+clamped*clamped)/(2*clamped)
    height=math.sqrt(max(length1*length1-along*along,0))
    # A stable forward pole avoids an almost-straight source knee switching
    # sides when the corrected ankle crosses its old axis. Such switches can
    # look valid on keyed frames but collapse below the floor between frames.
    forward=arm.pose.bones['pelvis'].matrix.to_3x3()@rest_root.transposed()@Vector((0,-1,0))
    forward.z=0
    bend=forward-axis*forward.dot(axis)
    bend.normalize();new_knee=H+axis*along+bend*height
    reached=H+axis*clamped
    thigh.matrix=Matrix.LocRotScale(H,((K-H).rotation_difference(new_knee-H).to_matrix()@upper).to_quaternion(),Vector((1,1,1)))
    bpy.context.view_layer.update()
    shin.matrix=Matrix.LocRotScale(new_knee,((A-K).rotation_difference(reached-new_knee).to_matrix()@lower).to_quaternion(),Vector((1,1,1)))
    bpy.context.view_layer.update()
    # Use the reached ankle position so unreachable targets never stretch a bone.
    foot.matrix=Matrix.LocRotScale(foot.head.copy(),foot_rotation,Vector((1,1,1)))
    bpy.context.view_layer.update()
    toe.matrix=Matrix.LocRotScale(toe.head.copy(),toe_rotation,Vector((1,1,1)))
    bpy.context.view_layer.update()
    solver_errors.append((foot.head-target).length)

final_q=[];final_l=[];final_v=[];final_m=[]
for i in range(cycle_frames+1):
    set_base(i,pelvis_drop)
    targets={side:target_positions[side][i].copy() for side in contacts}
    for side in contacts:solve_leg(side,targets[side],target_rotations[side][i],toe_rotations[side][i])
    # Match the evaluated shoe sole to the floor during full stance, and remove
    # below-floor vertices during transitions without changing root motion.
    for _ in range(2):
        points=evaluated(body)
        for side in contacts:
            low=float(points[sole_ids[side],2].min());weight=influences[side][i]
            correction=max(.001-low,0.) if weight<.999 else .001-low
            if abs(correction)>1e-6:
                targets[side][2]+=correction
                solve_leg(side,targets[side],target_rotations[side][i],toe_rotations[side][i])
    final_q.append([tuple(b.rotation_quaternion) for b in arm.pose.bones])
    final_l.append([tuple(b.location) for b in arm.pose.bones])
    final_v.append(evaluated(body));final_m.append([np.array(b.matrix) for b in arm.pose.bones])
final_q=np.array(final_q);final_l=np.array(final_l);final_v=np.array(final_v);final_m=np.array(final_m)
# Remove tiny solver roundoff at the duplicate closing frame; sign-continuous quats.
for i in range(1,len(final_q)):
    final_q[i,np.sum(final_q[i]*final_q[i-1],axis=-1)<0]*=-1
final_q[-1]=final_q[0];final_l[-1]=final_l[0]

# Save before/after in-place variants using identical length and phase.
def linear_keys(action):
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    for key in curve.keyframe_points:key.interpolation='LINEAR'
                    curve.modifiers.new('CYCLES')

def save_variant(variant,locked):
    output=BASE/variant;output.mkdir(exist_ok=True)
    arm.animation_data_clear()
    for i in range(cycle_frames+1):
        if locked:
            for j,pb in enumerate(arm.pose.bones):
                pb.rotation_quaternion=Quaternion(final_q[i,j]);pb.location=Vector(final_l[i,j]);pb.scale=(1,1,1)
        else:set_base(i)
        for pb in arm.pose.bones:
            pb.keyframe_insert('rotation_quaternion',frame=i+1,group=pb.name)
            pb.keyframe_insert('location',frame=i+1,group=pb.name)
    action=arm.animation_data.action
    action.name='Walk - in place - foot locked' if locked else 'Walk - in place - before foot locking'
    linear_keys(action)
    arm['walk_speed_units_per_second']=speed
    arm['cycle_duration_seconds']=period_seconds
    arm['animation_note']='In-place cycle. Translate character forward at the recorded speed for planted-foot contact.'
    scene.frame_set(1)
    for frame,label in [(1,'Cycle start'),(19,'Right foot planted'),(49,'Left landing'),(cycle_frames+1,'Closing pose = start')]:scene.timeline_markers.new(label,frame=frame)
    bpy.ops.object.select_all(action='DESELECT')
    for ob in [arm,body,pouch]:
        if ob:ob.select_set(True)
    bpy.context.view_layer.objects.active=arm
    # Put the character back into the center of the authoring camera/view.
    center=Vector((0,0,1.0));cam=scene.camera
    cam.location=center+Vector((-2.5,-4,1.1));cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
    cam.data.type='ORTHO';cam.data.ortho_scale=2.5
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':area.spaces.active.region_3d.view_location=center;area.spaces.active.region_3d.view_distance=3.3
    bpy.ops.wm.save_as_mainfile(filepath=str(output/'peasant-walk.blend'))
    bpy.ops.export_scene.gltf(filepath=str(output/'peasant-walk.glb'),export_format='GLB',use_selection=True,
        export_yup=True,export_skins=True,export_animations=True,export_frame_range=True,
        export_force_sampling=True,export_def_bones=True,export_materials='EXPORT',
        export_animation_mode='ACTIVE_ACTIONS',export_anim_slide_to_zero=True,export_extras=True)
    scene.timeline_markers.clear()

save_variant('before-foot-lock',False)
save_variant('final',True)

# A translating companion makes foot contact inspectable against a fixed floor.
# It repeats the gait three times, adding the speed an engine would supply.
output=BASE/'travel-check';output.mkdir(exist_ok=True)
arm.animation_data_clear()
scene.frame_end=cycle_frames*3+1
scene.frame_preview_end=cycle_frames*3
for i in range(cycle_frames*3+1):
    index=i%cycle_frames
    for j,pb in enumerate(arm.pose.bones):
        pb.rotation_quaternion=Quaternion(final_q[index,j]);pb.location=Vector(final_l[index,j]);pb.scale=(1,1,1)
        if not pb.parent:pb.location+=rest_root.transposed()@Vector(virtual_velocity*i/fps)
        pb.keyframe_insert('rotation_quaternion',frame=i+1,group=pb.name)
        pb.keyframe_insert('location',frame=i+1,group=pb.name)
arm.animation_data.action.name='Walk - ground contact check - three strides'
linear_keys(arm.animation_data.action)
scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(output/'peasant-walk.blend'))
bpy.ops.export_scene.gltf(filepath=str(output/'peasant-walk.glb'),export_format='GLB',use_selection=True,
    export_yup=True,export_skins=True,export_animations=True,export_frame_range=True,
    export_force_sampling=True,export_def_bones=True,export_materials='EXPORT',
    export_animation_mode='ACTIVE_ACTIONS',export_anim_slide_to_zero=True,export_extras=True)

report={'source_blend':str(SOURCE),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    'source_period_frames':source_period,'source_samples':[21,120],'source_phase_origin_frame':phase_origin+1,
    'method':'Periodic quaternion/root Fourier fit across repeated strides, average heading removal, contact-weighted analytic two-bone IK with stable knee poles, flat stance shoes, baked FK keys.',
    'fps':fps,'unique_frames':cycle_frames,'closing_frame':cycle_frames+1,'duration_seconds':period_seconds,
    'speed_units_per_second':speed,'stride_length_units':speed*period_seconds,
    'heading_removed_degrees':math.degrees(heading),'pelvis_lowering_units':pelvis_drop,
    'travel_check':{'cycles':3,'duration_seconds':3*period_seconds,'net_displacement_blender':(virtual_velocity*3*period_seconds).tolist()},
    'contacts':contacts,'max_ankle_solver_error_units':max(solver_errors),
    'geometry_uvs_textures_rest_rig_weights_changed':False,
    'limitations':['Contact timing is authored for this peasant walk; not automatic for arbitrary actions.',
        'Full foot lock applies to the core flat-stance interval, with smooth transitions for landing and toe-off.',
        'In-place feet move backward; assess ground slip after virtual forward translation at the recorded speed.',
        ('Coarse elbow/knee and clothing deformation remain separate cleanup issues.' if args.no_pouch else
         'Tunic/sleeve deformation and attachment overlap are separate unresolved geometry issues.')]}
(BASE/'cycle.json').write_text(json.dumps(report,indent=2)+'\n')
np.savez_compressed(BASE/'cycle-analysis.npz',base_vertices=base_vertices,final_vertices=final_v,
    base_matrices=base_matrices,final_matrices=final_m,virtual_velocity=virtual_velocity,
    names=names,sole_L=sole_ids['L'],sole_R=sole_ids['R'],influence_L=influences['L'],influence_R=influences['R'])
print('CYCLE',json.dumps(report,indent=2))
