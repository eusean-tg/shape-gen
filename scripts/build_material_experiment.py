"""Apply material-ID textures to a copy of the animated peasant and render review views."""
import argparse,json
from pathlib import Path
import sys
import bpy
import numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'assets/peasant-material-masks'
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--variant',choices=['regions','flat','masked'],default='masked');args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
OUT=BASE/args.variant;OUT.mkdir(exist_ok=True)
source=ROOT/'assets/peasant-hymotion/walk/final/peasant-walk.blend';bpy.ops.wm.open_mainfile(filepath=str(source))
scene=bpy.context.scene;arm=bpy.data.objects['Peasant rig'];body=bpy.data.objects['Peasant body'];pouch=bpy.data.objects['Original BPT pouch']
data=np.load(BASE/'regions.npz');meta=json.loads((BASE/'regions.json').read_text())
texture=BASE/({'regions':'region-colors.png','flat':'flat-basecolor.png','masked':'masked-basecolor.png'}[args.variant])
image=bpy.data.images.load(str(texture),check_existing=False);image.name='Material-masked base color';image.pack()
names=['Skin and preserved head','Tunic','Trousers','Belt UV mask','Boots','Pouch']
materials=[]
for i,name in enumerate(names):
    mat=bpy.data.materials.new(name);mat.use_nodes=True;n=mat.node_tree.nodes;bsdf=n.get('Principled BSDF');bsdf.inputs['Roughness'].default_value=.93 if i<3 else .82
    tex=n.new('ShaderNodeTexImage');tex.image=image;tex.interpolation='Linear';mat.node_tree.links.new(tex.outputs['Color'],bsdf.inputs['Base Color']);materials.append(mat)
for obj,entry in zip([body,pouch],meta['objects']):
    obj.data.materials.clear()
    for mat in materials:obj.data.materials.append(mat)
    attr=obj.data.attributes.get('material_region') or obj.data.attributes.new('material_region','INT','FACE')
    for p in obj.data.polygons:
        label=int(data['labels'][entry['face_start']+p.index]);p.material_index=label;attr.data[p.index].value=label
    obj['region_legend']=json.dumps(dict(enumerate(names)))
    obj['belt_note']='Belt occupies a sub-face UV mask between Z .085 and .13; inspect material-ids.png.'
scene.render.engine='CYCLES';scene.cycles.samples=16;scene.cycles.use_denoising=True
scene.render.threads_mode='FIXED';scene.render.threads=6;scene.render.resolution_x=scene.render.resolution_y=800;scene.render.resolution_percentage=100
cam=scene.camera;ground=bpy.data.objects.get('Motion review ground')
def render(name,center,direction,scale):
    cam.data.type='ORTHO';cam.data.ortho_scale=scale;cam.location=Vector(center)+Vector(direction).normalized()*4;cam.rotation_euler=(Vector(center)-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
arm.data.pose_position='REST'
if ground:ground.hide_render=True
for name,direction in [('front',(0,-1,.015)),('back',(0,1,.015)),('side',(-1,0,.015))]:render(name,(-.022,.06,-.008),direction,2.2)
render('waist',(-.022,.05,-.08),(0,-1,.08),.9)
render('cuff',(-.36,.04,.29),(-.5,-1,.08),.65)
arm.data.pose_position='POSE';scene.frame_set(16)
if ground:ground.hide_render=False
deps=bpy.context.evaluated_depsgraph_get();ob=body.evaluated_get(deps);mesh=ob.to_mesh();v=np.array([ob.matrix_world@x.co for x in mesh.vertices]);ob.to_mesh_clear();center=(v.min(0)+v.max(0))/2
render('walking',center,(-2.5,-4,1.1),2.6)
scene.frame_set(1);bpy.ops.object.select_all(action='DESELECT')
for ob in [arm,body,pouch]:ob.select_set(True)
bpy.context.view_layer.objects.active=arm;bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'peasant-walk.blend'))
bpy.ops.export_scene.gltf(filepath=str(OUT/'peasant-walk.glb'),export_format='GLB',use_selection=True,
    export_yup=True,export_skins=True,export_animations=True,export_frame_range=True,
    export_force_sampling=True,export_def_bones=True,export_materials='EXPORT',
    export_animation_mode='ACTIVE_ACTIONS',export_anim_slide_to_zero=True)
print('Saved',OUT)
