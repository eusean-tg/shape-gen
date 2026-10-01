import bpy,math,json
from pathlib import Path
from mathutils import Vector
out=Path(__file__).resolve().parent
stats={}
for label,source in [('lato-1200-noquad',out/'lato-1200-noquad/makima-normals.glb')]:
 bpy.ops.wm.read_factory_settings(use_empty=True)
 bpy.ops.import_scene.gltf(filepath=str(source))
 objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
 points=[o.matrix_world@v.co for o in objects for v in o.data.vertices]
 low=Vector([min(p[i] for p in points) for i in range(3)]);high=Vector([max(p[i] for p in points) for i in range(3)])
 stats[label]={'bounds':[list(low),list(high)],'vertices':len(points),'triangles':sum(len(o.data.polygons) for o in objects)}
 mat=bpy.data.materials.new('Neutral geometry');mat.diffuse_color=(.43,.48,.55,1);mat.use_nodes=True
 bsdf=mat.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Base Color'].default_value=(.43,.48,.55,1);bsdf.inputs['Roughness'].default_value=.8
 for o in objects:
  o.data.materials.clear();o.data.materials.append(mat)
  for f in o.data.polygons:f.use_smooth=False
 scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=16;scene.cycles.use_denoising=True
 scene.render.threads_mode='FIXED';scene.render.threads=6;scene.render.resolution_x=800;scene.render.resolution_y=900;scene.render.resolution_percentage=100
 scene.world=bpy.data.worlds.new('World');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.05,.06,.08,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.5
 scene.view_settings.view_transform='Standard'
 center=Vector((0,0,high.z-(high.z-low.z)*.20));extent=high.z-low.z
 for name,offset,power in [('Key',(2,-3,3),350),('Back',(-2,3,2),280),('Fill',(2,2,0),100)]:
  ld=bpy.data.lights.new(name,'AREA');ld.energy=power;ld.size=2
  ob=bpy.data.objects.new(name,ld);scene.collection.objects.link(ob);ob.location=center+Vector(offset);ob.rotation_euler=(center-ob.location).to_track_quat('-Z','Y').to_euler()
 camera=bpy.data.objects.new('Camera',bpy.data.cameras.new('Camera'));scene.collection.objects.link(camera);scene.camera=camera
 camera.data.type='ORTHO';camera.data.ortho_scale=extent*.48
 for name,angle in [('front',0),('side',90),('back-quarter',135),('back',180)]:
  a=math.radians(angle);camera.location=center+Vector((math.sin(a)*4,-math.cos(a)*4,.08));camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
  scene.render.filepath=str(out/f'{label}-{name}.png');bpy.ops.render.render(write_still=True)
(out/'lato-noquad-render-stats.json').write_text(json.dumps(stats,indent=2)+'\n')
