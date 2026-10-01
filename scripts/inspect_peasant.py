"""Background Blender diagnostics for the peasant texture/geometry repair."""
from pathlib import Path
import json
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets/peasant-bpt-staged/imagegen-paint/repair-v3'
OUT.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(OUT.parent / 'final-v2/peasant-editable.blend'))
obj = next(o for o in bpy.context.scene.objects if o.type == 'MESH')
scene = bpy.context.scene
scene.render.resolution_x = scene.render.resolution_y = 768
scene.render.resolution_percentage = 100
scene.cycles.samples = 16
scene.render.threads_mode = 'FIXED'
scene.render.threads = 8
camera = scene.camera
def render(name, center, direction, scale, clay=False):
    camera.data.ortho_scale = scale
    camera.location = Vector(center) + Vector(direction).normalized() * 4
    camera.rotation_euler = (Vector(center) - camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.engine = 'BLENDER_WORKBENCH' if clay else 'CYCLES'
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.color_type = 'SINGLE'
    scene.display.shading.single_color = (0.55,0.55,0.55)
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = 'BOTH'
    scene.render.filepath = str(OUT / (name + '.png'))
    bpy.ops.render.render(write_still=True)

render('before-head', (0,-.03,.74), (0,-1,.05), .55)
render('before-head-angle', (0,-.03,.74), (-.7,-1,.1), .55)
render('before-pouch-clay', (-.225,.005,.015), (-.9,-1,.15), .45, True)
render('before-pouch-clay-side', (-.225,.005,.015), (-1,.2,.15), .45, True)
render('before-pouch-texture', (-.225,.005,.015), (-.9,-1,.15), .45)
data = {'vertices':[list(v.co) for v in obj.data.vertices],
        'faces':[list(p.vertices) for p in obj.data.polygons],
        'centers':[list(p.center) for p in obj.data.polygons]}
(OUT/'source-mesh.json').write_text(json.dumps(data))
