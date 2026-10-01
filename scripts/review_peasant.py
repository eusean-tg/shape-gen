"""Save the repaired authoring asset and render close-up acceptance views."""
from pathlib import Path
import argparse
import json
import math

import bmesh
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets/peasant-bpt-staged/imagegen-paint/repair-v3'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,default=OUT)
parser.add_argument('--source-blend',type=Path)
parser.add_argument('--name',default='peasant-repaired')
parser.add_argument('--material-label',default='Imagegen paint — repaired UV bake')
import sys
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
OUT=args.output.resolve()
target=OUT/(args.name+'.blend')
if target.exists(): raise FileExistsError(target)
bpy.ops.wm.open_mainfile(filepath=str(args.source_blend or OUT/'untextured.blend'))
objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
image=bpy.data.images.load(str(OUT/'basecolor.png'),check_existing=False)
material=bpy.data.materials.new(args.material_label)
material.use_nodes=True
material.use_backface_culling=True
nodes=material.node_tree.nodes
shader=nodes.get('Principled BSDF')
shader.inputs['Roughness'].default_value=.85
tex=nodes.new('ShaderNodeTexImage');tex.image=image
tex.interpolation='Linear'
material.node_tree.links.new(tex.outputs['Color'],shader.inputs['Base Color'])
for obj in objects:
    obj.data.materials.clear();obj.data.materials.append(material)
    for poly in obj.data.polygons: poly.material_index=0

scene=bpy.context.scene
scene.render.threads_mode='FIXED';scene.render.threads=8
scene.cycles.samples=32
scene.render.resolution_x=scene.render.resolution_y=768
scene.render.resolution_percentage=100
camera=scene.camera
def pose(center,direction,scale):
    camera.data.ortho_scale=scale
    camera.location=Vector(center)+Vector(direction).normalized()*4
    camera.rotation_euler=(Vector(center)-camera.location).to_track_quat('-Z','Y').to_euler()
def render(name,center,direction,scale,clay=False):
    pose(center,direction,scale)
    scene.render.engine='BLENDER_WORKBENCH' if clay else 'CYCLES'
    scene.display.shading.light='STUDIO'
    scene.display.shading.color_type='SINGLE'
    scene.display.shading.single_color=(.55,.55,.55)
    scene.display.shading.show_cavity=True
    scene.render.filepath=str(OUT/(name+'.png'))
    bpy.ops.render.render(write_still=True)

render('after-head',(0,-.03,.74),(0,-1,.05),.55)
render('after-head-angle',(0,-.03,.74),(-.7,-1,.1),.55)
render('after-pouch',(-.225,.005,.015),(-.9,-1,.15),.45)
render('after-pouch-clay',(-.225,.005,.015),(-.9,-1,.15),.45,True)
for name,angle in [('front',0),('three-quarter',-35),('side',-90),('back',180)]:
    a=math.radians(angle)
    render(name,(0,.04,-.008),(math.sin(a),-math.cos(a),.04),2.32)
pose((0,.04,-.008),(-.65,-1,.06),2.32)
scene.render.engine='CYCLES'
bpy.ops.object.select_all(action='DESELECT')
for obj in objects: obj.select_set(True)
bpy.context.view_layer.objects.active=objects[0]
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.overlay.show_extras=False
            area.spaces.active.shading.type='MATERIAL'
            area.spaces.active.region_3d.view_location=(0,0,0)
            area.spaces.active.region_3d.view_distance=3.4
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(target))
bpy.ops.export_scene.gltf(filepath=str(OUT/(args.name+'.glb')),export_format='GLB',
    use_selection=True,export_yup=True,export_normals=True,export_materials='EXPORT')
bpy.ops.wm.open_mainfile(filepath=str(target))
report={}
for obj in [o for o in bpy.context.scene.objects if o.type=='MESH']:
    bm=bmesh.new();bm.from_mesh(obj.data);bm.normal_update()
    normals=[f.normal.copy() for f in bm.faces]
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.normal_update()
    flips=sum(f.normal.dot(n)<-.99 for f,n in zip(bm.faces,normals))
    report[obj.name]={'triangles':len(bm.faces),'vertices':len(bm.verts),
        'boundary_edges':sum(e.is_boundary for e in bm.edges),
        'overconnected_edges':sum(len(e.link_faces)>2 for e in bm.edges),
        'normal_recalculation_flips':flips,'signed_volume':bm.calc_volume(signed=True)}
    assert flips==0
    bm.free()
assert all(i.packed_file for i in bpy.data.images if i.name.startswith('basecolor'))
(OUT/'saved-file-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
