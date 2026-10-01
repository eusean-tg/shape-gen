"""CPU clay renders, matching angles and framing across experimental meshes."""
import bpy,math,json,sys
from pathlib import Path
from mathutils import Vector
out=Path(__file__).resolve().parent
manifest={k:v for k,v in json.loads((out/'render-list.json').read_text()).items() if k in ['original-dense','mv384','mv-original','original-bpt','recommended']}
for label,path in manifest.items():
 source=(out/path).resolve()
 if not source.exists():continue
 destination=out/'detail-renders';destination.mkdir(exist_ok=True)
 if all((destination/f'{label}-{angle}.png').exists() for angle in ['front','side','back-quarter','full']):continue
 bpy.ops.wm.read_factory_settings(use_empty=True)
 bpy.ops.import_scene.gltf(filepath=str(source))
 objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
 points=[o.matrix_world@v.co for o in objects for v in o.data.vertices]
 low=Vector([min(p[i] for p in points) for i in range(3)]);high=Vector([max(p[i] for p in points) for i in range(3)])
 mat=bpy.data.materials.new('Neutral clay');mat.use_nodes=True
 bsdf=mat.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Base Color'].default_value=(.25,.31,.38,1);bsdf.inputs['Roughness'].default_value=.8
 for o in objects:
  o.data.materials.clear();o.data.materials.append(mat)
  for f in o.data.polygons:f.use_smooth=False
 scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=12;scene.cycles.use_denoising=True
 scene.render.threads_mode='FIXED';scene.render.threads=4;scene.render.resolution_x=600;scene.render.resolution_y=700;scene.render.resolution_percentage=100
 scene.world=bpy.data.worlds.new('World');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.07,.08,.10,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.5
 scene.view_settings.view_transform='AgX'
 center=Vector((0,0,high.z-(high.z-low.z)*.20));extent=high.z-low.z
 for name,offset,power in [('Key',(2,-3,3),260),('Back',(-2,3,2),200),('Fill',(2,2,0),80)]:
  ld=bpy.data.lights.new(name,'AREA');ld.energy=power;ld.size=2
  ob=bpy.data.objects.new(name,ld);scene.collection.objects.link(ob);ob.location=center+Vector(offset);ob.rotation_euler=(center-ob.location).to_track_quat('-Z','Y').to_euler()
 camera=bpy.data.objects.new('Camera',bpy.data.cameras.new('Camera'));scene.collection.objects.link(camera);scene.camera=camera
 camera.data.type='ORTHO';camera.data.ortho_scale=extent*.48
 for name,angle,fraction,scale in [('face',0,.10,.24),('knees-back',180,.28,.33)]:
  target=Vector((0,0,high.z-extent*fraction if name=='face' else low.z+extent*fraction))
  camera.data.ortho_scale=extent*scale
  a=math.radians(angle);camera.location=target+Vector((math.sin(a)*4,-math.cos(a)*4,0));camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
  scene.render.filepath=str(destination/f'{label}-{name}.png');bpy.ops.render.render(write_still=True)
