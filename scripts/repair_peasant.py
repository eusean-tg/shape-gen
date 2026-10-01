"""Asset-specific pouch repair and controlled UVs. Run with background Blender.

Writes a new authoring file; never modifies the open interactive Blender scene.
"""
from pathlib import Path
import heapq
import json
import math

import bmesh
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets/peasant-bpt-staged/imagegen-paint/repair-v3'
OUT.mkdir(exist_ok=True)
target = OUT / 'untextured.blend'
if target.exists():
    raise FileExistsError(target)
bpy.ops.wm.open_mainfile(filepath=str(OUT.parent/'final-v2/peasant-editable.blend'))
body = next(o for o in bpy.context.scene.objects if o.type == 'MESH')
body.name = 'Peasant body'
bm = bmesh.new()
bm.from_mesh(body.data)
bm.faces.ensure_lookup_table()
bm.verts.ensure_lookup_table()
uv = bm.loops.layers.uv.active

# Retain original seams on the body, replacing the head's seam pattern below.
for e in bm.edges:
    if len(e.link_faces) != 2:
        e.seam = True
        continue
    def edge_uv(face):
        return {l.vert: l[uv].uv.copy() for l in face.loops if l.vert in e.verts}
    a, b = [edge_uv(f) for f in e.link_faces]
    e.seam = any((a[v]-b[v]).length > 1e-6 for v in e.verts)

def in_pouch(v):
    x,y,z = v.co
    return -.29 < x < -.15 and -.076 < y < .041 and -.081 < z < .141

removed = [f for f in bm.faces if all(in_pouch(v) for v in f.verts)]
assert len(removed) == 79, 'Source mesh changed; re-evaluate the local repair'
bmesh.ops.delete(bm, geom=removed, context='FACES')
# Close the exposed body patch underneath the removed, fused pouch.
patch_edges = [e for e in bm.edges if e.is_boundary and all(
    -.30 < v.co.x < -.14 and -.081 < v.co.y < .061 and -.091 < v.co.z < .151
    for v in e.verts)]
assert len(patch_edges) == 13
patch = bmesh.ops.holes_fill(bm, edges=patch_edges, sides=0)['faces']
for f in patch:
    for e in f.edges:
        e.seam = True
# The small open triangle beside an ear is also visible in close-up.
ear_edges = [e for e in bm.edges if e.is_boundary and all(v.co.z > .55 for v in e.verts)]
ear_patch = bmesh.ops.holes_fill(bm, edges=ear_edges, sides=0)['faces'] if ear_edges else []
bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))

head = {f for f in bm.faces if f.calc_center_median().z > .54}
head_verts = {v for f in head for v in f.verts}
neck_edges = []
for e in bm.edges:
    if any(f in head for f in e.link_faces):
        e.seam = any(f not in head for f in e.link_faces) or e.is_boundary
        if e.seam:
            neck_edges.append(e)
# One seam down the rear of the head, chosen as a connected shortest path.
neck_verts = {v for e in neck_edges for v in e.verts}
start = max(neck_verts, key=lambda v: v.co.y - abs(v.co.x)*2)
end = max(head_verts, key=lambda v: v.co.z - abs(v.co.x)*.1)
queue = [(0.0, start.index, start)]
cost, previous = {start:0.0}, {}
while queue:
    value, _, v = heapq.heappop(queue)
    if value != cost[v]:
        continue
    if v == end:
        break
    for e in v.link_edges:
        other = e.other_vert(v)
        if other not in head_verts:
            continue
        midpoint = (v.co + other.co)/2
        weight = e.calc_length()*(1+abs(midpoint.x)*30+max(0,-midpoint.y)*80)
        trial = value + weight
        if trial < cost.get(other, math.inf):
            cost[other] = trial
            previous[other] = (v,e)
            heapq.heappush(queue, (trial, other.index, other))
v = end
while v != start:
    v,e = previous[v]
    e.seam = True

# Store selection on faces for a dedicated head unwrap.
for v in bm.verts: v.select = False
for e in bm.edges: e.select = False
bm.select_mode = {'FACE'}
for f in bm.faces: f.select_set(f in head)
bm.select_flush_mode()
bm.to_mesh(body.data)
bm.free()
bpy.context.view_layer.objects.active = body
bpy.ops.object.select_all(action='DESELECT')
body.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_mode(type='FACE')
bpy.ops.uv.unwrap(method='MINIMUM_STRETCH', iterations=30, no_flip=True)
bpy.ops.mesh.select_all(action='DESELECT')
bpy.ops.object.mode_set(mode='OBJECT')

# Unwrap the newly filled body patch independently; the original charts stay.
bm = bmesh.new(); bm.from_mesh(body.data)
bm.select_mode = {'FACE'}
for f in bm.faces:
    c = f.calc_center_median()
    f.select_set(len(f.verts)>3 and -.30<c.x<-.14 and -.10<c.z<.16)
bm.select_flush_mode(); bm.to_mesh(body.data); bm.free()
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.uv.unwrap(method='ANGLE_BASED')
bpy.ops.mesh.select_all(action='DESELECT')
bpy.ops.object.mode_set(mode='OBJECT')

# A closed, chamfered pouch replaces the self-intersecting fused shell.
# Front and rear outlines follow the original silhouette in the same location.
outline = [(-.047,.105),(.038,.105),(.060,.079),(.054,-.078),
           (.030,-.105),(-.033,-.105),(-.058,-.079),(-.064,.073)]
verts = []
for y, scale, dx in [(-.074,.88,0),(-.060,1,0),(.029,.9,.009)]:
    verts += [(-.220+x*scale+dx,y,.025+z*scale) for x,z in outline]
faces = [tuple(range(8)),tuple(range(23,15,-1))]
for ring in range(2):
    for i in range(8):
        j = (i+1)%8
        faces.append((ring*8+i,ring*8+j,(ring+1)*8+j,(ring+1)*8+i))
mesh = bpy.data.meshes.new('Pouch closed shell')
mesh.from_pydata(verts,[],faces);mesh.update()
pouch = bpy.data.objects.new('Pouch',mesh)
bpy.context.collection.objects.link(pouch)
bm=bmesh.new();bm.from_mesh(mesh)
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
for e in bm.edges:
    # Front panel, rear panel, and one opened band around the sides.
    e.seam = abs(e.verts[0].co.y-e.verts[1].co.y)<1e-6 or all(v.co.z>.11 for v in e.verts)
bm.to_mesh(mesh);bm.free()
pouch.data.materials.append(body.data.materials[0])
bpy.ops.object.select_all(action='DESELECT');pouch.select_set(True)
bpy.context.view_layer.objects.active=pouch
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.unwrap(method='ANGLE_BASED')
bpy.ops.object.mode_set(mode='OBJECT')

# Pack together with padding. Normalize density, then allocate extra pixels to
# the head for its small, high-contrast facial features.
body.select_set(True)
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.average_islands_scale()
bpy.ops.object.mode_set(mode='OBJECT')
uvdata=body.data.uv_layers.active.data
for poly in body.data.polygons:
    if poly.center.z>.54:
        for i in poly.loop_indices:
            uvdata[i].uv *= 1.7
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.uv.pack_islands(rotate=True,margin_method='FRACTION',margin=.006)
bpy.ops.object.mode_set(mode='OBJECT')

report={}
for obj in (body,pouch):
    bm=bmesh.new();bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm,faces=list(bm.faces))
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    report[obj.name]={'vertices':len(bm.verts),'triangles':len(bm.faces),
        'boundary_edges':sum(e.is_boundary for e in bm.edges),
        'overconnected_edges':sum(len(e.link_faces)>2 for e in bm.edges),
        'signed_volume':bm.calc_volume(signed=True)}
    bm.to_mesh(obj.data);bm.free()
    obj.data.update()
assert report['Pouch']['boundary_edges']==0
assert report['Pouch']['overconnected_edges']==0
assert report['Pouch']['signed_volume']>0
bpy.ops.wm.save_as_mainfile(filepath=str(target))
bpy.ops.export_scene.gltf(filepath=str(OUT/'unwrapped.glb'),export_format='GLB',
    use_selection=True,export_yup=True,export_normals=True,export_materials='EXPORT')
(OUT/'geometry-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
