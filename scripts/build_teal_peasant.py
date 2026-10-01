"""Assemble the material-masked replacement character, optionally adding UniRig."""
import argparse,json,sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'assets/teal-peasant';OUT=BASE/'model'
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--rig',action='store_true')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
bpy.ops.wm.open_mainfile(filepath=str(OUT/'geometry.blend'))
body=bpy.data.objects['Peasant body'];scene=bpy.context.scene
meta=json.loads((OUT/'materials.json').read_text());labels=np.load(OUT/'face-regions.npy')
image=bpy.data.images.load(str(OUT/'basecolor.png'),check_existing=False);image.name='Teal peasant masked base color';image.pack()
body.data.materials.clear()
for name in meta['region_names']:
 material=bpy.data.materials.new(name);material.use_nodes=True
 nodes=material.node_tree.nodes;bsdf=nodes.get('Principled BSDF');bsdf.inputs['Roughness'].default_value=.92
 texture=nodes.new('ShaderNodeTexImage');texture.image=image;texture.interpolation='Linear'
 material.node_tree.links.new(texture.outputs['Color'],bsdf.inputs['Base Color'])
 body.data.materials.append(material)
attr=body.data.attributes.get('material_region') or body.data.attributes.new('material_region','INT','FACE')
for poly,rid in zip(body.data.polygons,labels):poly.material_index=int(rid);attr.data[poly.index].value=int(rid)
objects=[body]
if args.rig:
 data=np.load(BASE/'rig/rig-data.npz');names=data['names'].tolist()
 assert np.max(abs(np.array([tuple(v.co) for v in body.data.vertices])-data['vertices']))<1e-7
 arm_data=bpy.data.armatures.new('Teal peasant UniRig skeleton');arm=bpy.data.objects.new('Peasant rig',arm_data);scene.collection.objects.link(arm)
 bpy.ops.object.select_all(action='DESELECT');arm.select_set(True);bpy.context.view_layer.objects.active=arm
 bpy.ops.object.mode_set(mode='EDIT')
 for i,name in enumerate(names):
  bone=arm_data.edit_bones.new(name);bone.head=data['joints'][i];bone.tail=data['tails'][i]
  if bone.length<.001:bone.tail=bone.head+Vector((0,0,.02))
  if data['parents'][i]>=0:bone.parent=arm_data.edit_bones[names[data['parents'][i]]]
  bone.use_connect=False
 bpy.ops.object.mode_set(mode='OBJECT');arm.show_in_front=True;arm.data.display_type='OCTAHEDRAL'
 body.parent=arm;modifier=body.modifiers.new('UniRig skinning','ARMATURE');modifier.object=arm;modifier.use_deform_preserve_volume=False
 for name in names:body.vertex_groups.new(name=name)
 for i,row in enumerate(data['weights']):
  for j in np.flatnonzero(row>0):body.vertex_groups[names[j]].add([i],float(row[j]),'REPLACE')
 objects.append(arm)
scene.world=bpy.data.worlds.new('Review world');scene.world.use_nodes=True
scene.world.node_tree.nodes.get('Background').inputs['Color'].default_value=(.15,.18,.22,1)
scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.7
for name,offset,energy in [('Key',(-3,-4,5),700),('Fill',(3,-2,3),350),('Rim',(0,3,4),600)]:
 lamp=bpy.data.lights.new(name,'AREA');lamp.energy=energy;lamp.size=4
 obj=bpy.data.objects.new(name,lamp);scene.collection.objects.link(obj);obj.location=offset;obj.rotation_euler=(Vector((0,0,1))-obj.location).to_track_quat('-Z','Y').to_euler()
cam=bpy.data.objects.new('Review camera',bpy.data.cameras.new('Review camera'));scene.collection.objects.link(cam);scene.camera=cam
cam.location=(-2.5,-4,2);cam.rotation_euler=(Vector((0,0,1))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=2.5
scene.render.engine='CYCLES';scene.cycles.samples=12;scene.render.resolution_x=scene.render.resolution_y=800;scene.render.resolution_percentage=100
scene.render.fps=60
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':area.spaces.active.region_3d.view_location=(0,0,1);area.spaces.active.region_3d.view_distance=3.2;area.spaces.active.shading.type='MATERIAL'
bpy.ops.object.select_all(action='DESELECT')
for obj in objects:obj.select_set(True)
bpy.context.view_layer.objects.active=objects[-1]
bpy.ops.file.pack_all();name='rigged' if args.rig else 'textured'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/(name+'.blend')))
bpy.ops.export_scene.gltf(filepath=str(OUT/(name+'.glb')),export_format='GLB',use_selection=True,export_animations=False,export_skins=args.rig)
print('Saved',name)
