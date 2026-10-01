"""Prepare the new BPT character as a welded editable mesh and UniRig input."""
from pathlib import Path
import json,hashlib
import bpy,bmesh
import numpy as np
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'assets/teal-peasant'
SOURCE=BASE/'bpt/02-bpt.glb';OUT=BASE/'model';OUT.mkdir(exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(SOURCE))
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
bpy.ops.object.select_all(action='DESELECT')
for obj in meshes:obj.select_set(True)
bpy.context.view_layer.objects.active=meshes[0]
bpy.ops.object.join();body=bpy.context.object;body.name='Peasant body'
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
bm=bmesh.new();bm.from_mesh(body.data)
before={'vertices':len(bm.verts),'faces':len(bm.faces)}
bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6)
bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-7)
# Remove exact duplicate faces, preserving geometric vertices.
seen=set();duplicate=[]
for face in bm.faces:
 key=frozenset(face.verts)
 if key in seen:duplicate.append(face)
 else:seen.add(key)
if duplicate:bmesh.ops.delete(bm,geom=duplicate,context='FACES_ONLY')
# Repair the two collinear hair T-junctions without moving their vertices.
t_junctions=0
for edge in list(bm.edges):
 if not edge.is_valid or not edge.is_boundary:continue
 a,b=edge.verts;direction=b.co-a.co
 if direction.length_squared<1e-12:continue
 candidates=[]
 for v in bm.verts:
  if v in edge.verts:continue
  t=(v.co-a.co).dot(direction)/direction.length_squared
  if 1e-5<t<1-1e-5 and (v.co-(a.co+t*direction)).length<1e-6:candidates.append((t,v))
 if not candidates:continue
 middle=min(candidates,key=lambda item:abs(item[0]-.5))[1]
 face=edge.link_faces[0];ordered=list(face.verts)
 if len(ordered)!=3:continue
 for j in range(3):
  if ordered[j] in edge.verts and ordered[(j+1)%3] in edge.verts:
   a,b,c=ordered[j],ordered[(j+1)%3],ordered[(j+2)%3];break
 bmesh.ops.delete(bm,geom=[face],context='FACES_ONLY')
 bm.faces.new((a,middle,c));bm.faces.new((middle,b,c));t_junctions+=1
# Flip one smooth face pair off each four-face ankle edge. This repairs the
# connectivity while retaining every original vertex and its position.
bm.normal_update();ankle_flips=0
for edge in list(bm.edges):
 if not edge.is_valid or len(edge.link_faces)!=4:continue
 pairs=[]
 import itertools
 for f1,f2 in itertools.combinations(edge.link_faces,2):
  c=next(v for v in f1.verts if v not in edge.verts);d=next(v for v in f2.verts if v not in edge.verts)
  if bm.edges.get((c,d)):continue
  pairs.append((f1.normal.dot(f2.normal),f1,f2,c,d))
 if not pairs:continue
 _,f1,f2,c,d=max(pairs,key=lambda row:row[0]);ordered=list(f1.verts)
 for j in range(3):
  if ordered[j] in edge.verts and ordered[(j+1)%3] in edge.verts:a,b=ordered[j],ordered[(j+1)%3];break
 bmesh.ops.delete(bm,geom=[f1,f2],context='FACES_ONLY')
 bm.faces.new((c,a,d));bm.faces.new((c,d,b));ankle_flips+=1
loose=[e for e in bm.edges if not e.link_faces]
if loose:bmesh.ops.delete(bm,geom=loose,context='EDGES')
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
bm.to_mesh(body.data);bm.free();body.data.update()
for p in body.data.polygons:p.use_smooth=False
vertices=np.array([tuple(v.co) for v in body.data.vertices]);lo=vertices.min(0);hi=vertices.max(0)
# Keep Hunyuan scale; center the character in X/Y and put the soles at Z=0.
shift=np.array([-(lo[0]+hi[0])/2,-(lo[1]+hi[1])/2,-lo[2]])
for v in body.data.vertices:v.co+=__import__('mathutils').Vector(shift)
body.data.update()
vertices=np.array([tuple(v.co) for v in body.data.vertices],dtype=np.float32)
faces=np.array([list(f.vertices) for f in body.data.polygons],dtype=np.int64)
assert faces.shape[1]==3
normals=np.array([tuple(v.normal) for v in body.data.vertices],dtype=np.float32)
face_normals=np.array([tuple(f.normal) for f in body.data.polygons],dtype=np.float32)
lo=vertices.min(0);hi=vertices.max(0)
# Angle-based islands keep per-corner UVs on the welded authoring mesh.
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=1.151917,island_margin=.025,area_weight=.2)
bpy.ops.object.mode_set(mode='OBJECT')
mat=bpy.data.materials.new('Geometry review');mat.diffuse_color=(.48,.58,.61,1);mat.use_nodes=True
mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.48,.58,.61,1)
body.data.materials.clear();body.data.materials.append(mat)
# Save raw inference data using the upstream extraction convention: Blender Z-up.
rig=BASE/'rig';(rig/'data/peasant').mkdir(parents=True,exist_ok=True)
np.savez(rig/'data/peasant/raw_data.npz',vertices=vertices,faces=faces,vertex_normals=normals,
 face_normals=face_normals,joints=None,skin=None,parents=None,names=None,matrix_local=None,tails=None,no_skin=None,path=None,cls=None)
(rig/'data/inference.txt').write_text('peasant\n')
meta={'source':str(SOURCE),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
 'object':body.name,'vertices':len(vertices),'triangles':len(faces),'normalization_center':((lo+hi)/2).tolist(),
 'normalization_half_extent':float(max(hi-lo)/2),'coordinate_system':'Blender Z-up, forward -Y, soles at Z=0'}
(rig/'input.json').write_text(json.dumps(meta,indent=2)+'\n')
bm=bmesh.new();bm.from_mesh(body.data)
report={**meta,'input_counts':before,'duplicate_faces_removed':len(duplicate),
 'hair_t_junctions_split':t_junctions,'ankle_nonmanifold_edges_repaired':ankle_flips,
 'boundary_edges':sum(e.is_boundary for e in bm.edges),'overconnected_edges':sum(len(e.link_faces)>2 for e in bm.edges),
 'bounds':[lo.tolist(),hi.tolist()],'translation_from_bpt':shift.tolist()}
bm.free();(OUT/'geometry.json').write_text(json.dumps(report,indent=2)+'\n')
np.savez_compressed(OUT/'mesh.npz',vertices=vertices,faces=faces,
 uv=np.array([tuple(t.uv) for t in body.data.uv_layers.active.data]),loops=np.array([p.loop_indices[:] for p in body.data.polygons]))
scene=bpy.context.scene;scene.render.fps=60
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'geometry.blend'))
bpy.ops.export_scene.gltf(filepath=str(OUT/'geometry.glb'),export_format='GLB',use_selection=True,export_animations=False)
print(json.dumps(report,indent=2))
