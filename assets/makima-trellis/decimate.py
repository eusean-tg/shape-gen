"""Blender collapse-decimation control at the generated BPT triangle count."""
import bpy, json, sys, hashlib
from pathlib import Path
source, output, count = sys.argv[sys.argv.index('--')+1:]
source, output, count = Path(source).resolve(), Path(output).resolve(), int(count)
if output.exists():
    raise FileExistsError(output)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(source))
objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']
assert len(objects) == 1, 'This comparison expects one mesh'
o = objects[0]
bpy.context.view_layer.objects.active = o
o.select_set(True)
before = len(o.data.polygons)
mod = o.modifiers.new('Collapse control', 'DECIMATE')
mod.decimate_type = 'COLLAPSE'
mod.ratio = min(1, count / before)
mod.use_collapse_triangulate = True
bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.ops.export_scene.gltf(filepath=str(output), export_format='GLB', use_selection=True)
record = dict(input=str(source), input_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    output=str(output), method='Blender collapse decimation, triangulate enabled; no extra cleanup',
    input_triangles=before, requested_triangles=count, output_triangles=len(o.data.polygons),
    blender=bpy.app.version_string, sha256=hashlib.sha256(output.read_bytes()).hexdigest())
output.with_suffix('.json').write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps(record, indent=2))
