"""Repair original BPT pouch faces without moving or introducing positions.

Run in background Blender. Face IDs refer to the preserved final-v2 source.
Shared attachment vertices are duplicated at exactly the same coordinates when
separating the pouch. One intersecting source triangle is retessellated.
"""
from pathlib import Path
import json

import bmesh
import bpy

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'assets/peasant-bpt-staged/imagegen-paint'
OUT=PARENT/'repair-original-v4'
OUT.mkdir(exist_ok=True)
target=OUT/'untextured.blend'
if target.exists(): raise FileExistsError(target)
bpy.ops.wm.open_mainfile(filepath=str(PARENT/'final-v2/peasant-editable.blend'))
source=next(o for o in bpy.context.scene.objects if o.type=='MESH')
assert len(source.data.vertices)==1152 and len(source.data.polygons)==2279
positions=[tuple(v.co) for v in source.data.vertices]
source_faces=[tuple(p.vertices) for p in source.data.polygons]
bag_ids=set(range(856,890))|set(range(1264,1275))|{1281}|set(range(1311,1321))|set(range(1361,1372))
assert len(bag_ids)==67
old_uv=source.data.uv_layers.active.data
report={}
objects=[]
plan=json.loads((OUT/'diagnostics/cap-plan.json').read_text())
for name,selected,new_triangles in [
    ('Peasant body',[i for i in range(2279) if i not in bag_ids],[[658,671,693]]),
    ('Original BPT pouch',plan['retained_pouch_face_ids'],plan['added_pouch_triangles'])]:
    used=sorted({v for i in selected for v in source_faces[i]})
    local={v:i for i,v in enumerate(used)}
    mesh=bpy.data.meshes.new(name)
    mesh.from_pydata([positions[i] for i in used],[],[
        [local[v] for v in source_faces[i]] for i in selected])
    mesh.update()
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj)
    obj.data.materials.append(source.data.materials[0])
    uv=mesh.uv_layers.new(name='UVMap')
    for poly,source_id in zip(mesh.polygons,selected):
        for new_i,old_i in zip(poly.loop_indices,source.data.polygons[source_id].loop_indices):
            uv.data[new_i].uv=old_uv[old_i].uv
    bm=bmesh.new();bm.from_mesh(mesh);bm.verts.ensure_lookup_table()
    original_layer=bm.verts.layers.int.new('BPT vertex ID')
    for i,v in enumerate(bm.verts): v[original_layer]=used[i]
    original_face=bm.faces.layers.int.new('BPT face ID')
    for f,i in zip(bm.faces,selected): f[original_face]=i+1
    added=[]
    for triangle in new_triangles:
        verts=[bm.verts[local[i]] for i in triangle]
        face=bm.faces.new(verts);face[original_face]=0
        added.append(face)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    if name=='Original BPT pouch' and bm.calc_volume(signed=True)<0:
        bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
    # Existing charts identify tunic seams; the original pouch will be unwrapped
    # separately to include the filled panels.
    luv=bm.loops.layers.uv.active
    for e in bm.edges:
        if len(e.link_faces)!=2:
            e.seam=True
        elif any(f[original_face]==0 for f in e.link_faces):
            e.seam=not all(f[original_face]==0 for f in e.link_faces)
        else:
            a,b=[{l.vert:l[luv].uv.copy() for l in f.loops if l.vert in e.verts} for f in e.link_faces]
            e.seam=any((a[v]-b[v]).length>1e-6 for v in e.verts)
    for v in bm.verts:
        assert tuple(v.co)==positions[v[original_layer]],'A vertex moved'
    report[name]={'vertices':len(bm.verts),'triangles':len(bm.faces),
        'retained_original_triangles':sum(f[original_face]>0 for f in bm.faces),
        'added_triangles':sum(f[original_face]==0 for f in bm.faces),
        'boundary_edges':sum(e.is_boundary for e in bm.edges),
        'overconnected_edges':sum(len(e.link_faces)>2 for e in bm.edges),
        'signed_volume':bm.calc_volume(signed=True),'max_vertex_displacement':0.0}
    bm.to_mesh(mesh);bm.free();mesh.update();objects.append(obj)
assert report['Original BPT pouch']['boundary_edges']==0
assert report['Original BPT pouch']['overconnected_edges']==0
assert report['Original BPT pouch']['signed_volume']>0
bpy.data.objects.remove(source,do_unlink=True)

# Borrow the improved head/body UVs from v3 wherever the same original face
# exists. UV transfer is by exact corner position, not nearest-surface sampling.
with bpy.data.libraries.load(str(PARENT/'repair-v3/untextured.blend'),link=False) as (src,dst):
    dst.objects=['Peasant body']
donor=dst.objects[0]
lookup={}
for poly in donor.data.polygons:
    coordinates=[tuple(donor.data.vertices[i].co) for i in poly.vertices]
    lookup[tuple(sorted(coordinates))]={co:tuple(donor.data.uv_layers.active.data[j].uv)
        for co,j in zip(coordinates,poly.loop_indices)}
body,pouch=objects
bm=bmesh.new();bm.from_mesh(body.data)
luv=bm.loops.layers.uv.active
new_faces=[]
for f in bm.faces:
    key=tuple(sorted(tuple(v.co) for v in f.verts))
    if key in lookup:
        for l in f.loops:l[luv].uv=lookup[key][tuple(l.vert.co)]
    else:new_faces.append(f)
bm.select_mode={'FACE'}
for f in bm.faces:f.select_set(f in new_faces)
for e in bm.edges:
    if len(e.link_faces)==2:
        a,b=[{l.vert:l[luv].uv.copy() for l in f.loops if l.vert in e.verts} for f in e.link_faces]
        e.seam=any((a[v]-b[v]).length>1e-6 for v in e.verts) or any(f in new_faces for f in e.link_faces)
bm.select_flush_mode();bm.to_mesh(body.data);bm.free()
bpy.data.objects.remove(donor,do_unlink=True)
bpy.ops.object.select_all(action='DESELECT');body.select_set(True)
bpy.context.view_layer.objects.active=body
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.uv.unwrap(method='ANGLE_BASED')
bpy.ops.object.mode_set(mode='OBJECT')

# Use connected panels separated at sharp geometric bends on the original bag.
bm=bmesh.new();bm.from_mesh(pouch.data)
tag=bm.faces.layers.int.get('BPT face ID')
for e in bm.edges:
    e.seam=e.calc_face_angle(0)>.8 or any(f[tag]-1 in {1367,1368,1370} for f in e.link_faces)
bm.to_mesh(pouch.data);bm.free()
bpy.ops.object.select_all(action='DESELECT');pouch.select_set(True)
bpy.context.view_layer.objects.active=pouch
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.unwrap(method='ANGLE_BASED');bpy.ops.object.mode_set(mode='OBJECT')
body.select_set(True)
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.average_islands_scale();bpy.ops.object.mode_set(mode='OBJECT')
for poly in body.data.polygons:
    if poly.center.z>.54:
        for i in poly.loop_indices:body.data.uv_layers.active.data[i].uv*=1.7
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.uv.pack_islands(rotate=True,margin_method='FRACTION',margin=.006)
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.wm.save_as_mainfile(filepath=str(target))
bpy.ops.export_scene.gltf(filepath=str(OUT/'unwrapped.glb'),export_format='GLB',
    use_selection=True,export_yup=True,export_normals=True,export_materials='EXPORT')
(OUT/'geometry-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
