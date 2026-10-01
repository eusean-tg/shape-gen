"""Reopen the cycle, verify source preservation, contact, seams and GLB playback."""
from pathlib import Path
import argparse,sys
import hashlib
import json
import bpy
import numpy as np
from mathutils.kdtree import KDTree
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'assets/peasant-walk-cycle'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--asset-dir',type=Path,default=BASE)
parser.add_argument('--no-pouch',action='store_true')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
BASE=args.asset_dir.resolve()
config=json.loads((BASE/'cycle.json').read_text())
SOURCE=Path(config['source_blend'])
N=config['unique_frames'];FPS=config['fps'];names=['Peasant body','Original BPT pouch']
if args.no_pouch:names=['Peasant body']
analysis=np.load(BASE/'cycle-analysis.npz')

def snapshot():
    out={}
    for name in names:
        obj=bpy.data.objects[name]
        out[name]={
            'vertices':np.array([tuple(v.co) for v in obj.data.vertices]),
            'faces':np.array([list(f.vertices) for f in obj.data.polygons]),
            'uv':np.array([tuple(t.uv) for t in obj.data.uv_layers.active.data]),
            'weights':[(v.index,g.group,g.weight) for v in obj.data.vertices for g in v.groups],
            'groups':[g.name for g in obj.vertex_groups],
            'material_indices':np.array([f.material_index for f in obj.data.polygons]),
            'material_regions':np.array([f.value for f in obj.data.attributes['material_region'].data]),
            'transform':np.array(obj.matrix_world),
            'images':sorted(hashlib.sha256(node.image.packed_file.data).hexdigest()
                for slot in obj.material_slots for node in slot.material.node_tree.nodes
                if node.type=='TEX_IMAGE' and node.image),
        }
    arm=bpy.data.objects['Peasant rig']
    out['bones']={b.name:np.array(b.matrix_local) for b in arm.data.bones}
    return out

def evaluated(name):
    bpy.context.view_layer.update()
    ob=bpy.data.objects[name].evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh=ob.to_mesh();v=np.array([tuple(ob.matrix_world@p.co) for p in mesh.vertices]);ob.to_mesh_clear();return v

def set_time(frame):
    integer=int(np.floor(frame));bpy.context.scene.frame_set(integer,subframe=float(frame-integer))

def nearest(a,b):
    tree=KDTree(len(b))
    for i,v in enumerate(b):tree.insert(v,i)
    tree.balance();return max(tree.find(v)[2] for v in a)

bpy.ops.wm.open_mainfile(filepath=str(SOURCE));original=snapshot()
expected={};contact={};scene_reports={}
for variant in ['before-foot-lock','final']:
    bpy.ops.wm.open_mainfile(filepath=str(BASE/variant/'peasant-walk.blend'))
    now=snapshot()
    for name in names:
        for key in original[name]:assert np.array_equal(original[name][key],now[name][key]),(variant,name,key)
    for name in original['bones']:assert np.array_equal(original['bones'][name],now['bones'][name]),name
    scene=bpy.context.scene;arm=bpy.data.objects['Peasant rig']
    assert scene.frame_start==1 and scene.frame_end==N+1 and scene.render.fps==FPS
    values=[];root=[];lengths=[]
    for i in range(N+1):
        scene.frame_set(i+1)
        vertices={name:evaluated(name) for name in names};values.append(vertices[names[0]])
        root.append(tuple(arm.pose.bones['pelvis'].head))
        for side in ['L','R']:
            h=arm.pose.bones['thigh.'+side].head;k=arm.pose.bones['shin.'+side].head;a=arm.pose.bones['foot.'+side].head
            lengths.append(max(abs((k-h).length-arm.data.bones['thigh.'+side].length),abs((a-k).length-arm.data.bones['shin.'+side].length)))
        if variant=='final':expected[float(i)]=vertices
    values=np.array(values);root=np.array(root)
    endpoint=float(np.max(np.abs(values[-1]-values[0])))
    assert endpoint<2e-6,(variant,endpoint)
    assert np.max(abs(root[-1]-root[0]))<2e-6
    assert max(lengths)<1e-5,max(lengths)
    # Loop-boundary velocity change should be unexceptional compared with normal
    # per-frame curvature; identical endpoints alone would not catch a hitch.
    accelerations=np.roll(values[:-1],-1,axis=0)-2*values[:-1]+np.roll(values[:-1],1,axis=0)
    accel=np.sqrt(np.mean(accelerations**2,axis=(1,2)))*FPS**2
    scene_reports[variant]={'endpoint_max_vertex_error':endpoint,
        'root_horizontal_peak_to_peak':np.ptp(root[:,:2],axis=0).tolist(),
        'max_leg_length_error':max(lengths),'seam_rms_acceleration':float(accel[0]),
        'cycle_rms_acceleration_p95':float(np.quantile(accel,.95))}
    assert accel[0]<np.quantile(accel,.95)*1.25,(variant,'boundary spike',accel[0])
    contact[variant]={}
    for side,cfg in config['contacts'].items():
        core=np.array(cfg['core_frames'])-1
        local=(core-cfg['midpoint']+N/2)%N-N/2+cfg['midpoint']
        sole=values[:,analysis['sole_'+side]]
        translated=sole[core]+analysis['virtual_velocity']*(local[:,None,None]/FPS)
        drift=np.linalg.norm(np.ptp(translated[:,:,:2],axis=0),axis=1)
        contact[variant][side]={'core_frames':cfg['core_frames'],
            'median_sole_vertex_horizontal_drift':float(np.median(drift)),
            'max_sole_vertex_horizontal_drift':float(drift.max()),
            'core_lowest_sole_height_range':[float(sole[core,:,2].min(1).min()),float(sole[core,:,2].min(1).max())]}
        if variant=='final':assert drift.max()<.01,(side,drift.max())
    if variant=='final':
        fractional_min=1.;fractional_max_stance_drift=0.
        sample_points=[]
        for t in np.arange(0,N+.001,.25):
            set_time(float(t)+1)
            vertices={name:evaluated(name) for name in names}
            expected[float(t)]=vertices
            for side in ['L','R']:
                points=vertices[names[0]][analysis['sole_'+side]]
                fractional_min=min(fractional_min,float(points[:,2].min()))
            sample_points.append(vertices[names[0]])
        assert fractional_min>-.003,('subframe floor penetration',fractional_min)
        scene_reports[variant]['quarter_frame_minimum_sole_height']=fractional_min
        scene_reports[variant]['quarter_frames_checked']=len(sample_points)

# Validate animation after an actual GLB reimport, including intermediate times.
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.render.fps=FPS
bpy.ops.import_scene.gltf(filepath=str(BASE/'final/peasant-walk.glb'))
errors={}
for t,reference in sorted(expected.items()):
    set_time(t)
    errors[str(t)]={}
    for name in names:
        a=evaluated(name);b=reference[name]
        error=max(nearest(a,b),nearest(b,a));assert error<3e-5,(t,name,error)
        errors[str(t)][name]=error
inplace_error=max(e for row in errors.values() for e in row.values())
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.render.fps=FPS
bpy.ops.import_scene.gltf(filepath=str(BASE/'travel-check/peasant-walk.glb'))
travel_error=0.
for i in range(3*N+1):
    set_time(i)
    for name in names:
        a=evaluated(name)
        b=expected[float(i%N)][name]+analysis['virtual_velocity']*i/FPS
        error=max(nearest(a,b),nearest(b,a));assert error<3e-5,('travel',i,name,error)
        travel_error=max(travel_error,error)
report={'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    'rest_mesh_uvs_weights_material_assignments_region_labels_texture_bytes_and_bones_unchanged':True,
    'source_preserved':hashlib.sha256(SOURCE.read_bytes()).hexdigest()==config['source_sha256'],
    'fps':FPS,'duration_seconds':config['duration_seconds'],'variants':scene_reports,
    'contact_metrics':contact,'max_glb_world_vertex_error':inplace_error,
    'travel_check_glb_frames_checked':3*N+1,'travel_check_max_vertex_error':travel_error,
    'glb_frames_and_subframes_checked':len(expected),'per_sample_glb_errors':errors,
    'contact_metric_note':'Drift of each sole vertex during the full-lock core, with forward travel added at the documented speed. Ramp intervals are excluded.'}
(BASE/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='per_sample_glb_errors'},indent=2))
