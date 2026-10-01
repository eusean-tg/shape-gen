"""Check the replacement's topology repair, UVs, textures and final rig export."""
from pathlib import Path
import json,hashlib
import bpy,bmesh
import numpy as np
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'assets/teal-peasant'
meta=json.loads((BASE/'model/geometry.json').read_text())
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(BASE/'bpt/02-bpt.glb'))
obj=next(o for o in bpy.context.scene.objects if o.type=='MESH')
original=np.array([tuple(obj.matrix_world@v.co) for v in obj.data.vertices])+np.array(meta['translation_from_bpt'])
bpy.ops.wm.open_mainfile(filepath=str(BASE/'model/geometry.blend'));obj=bpy.data.objects['Peasant body']
vertices=np.array([tuple(v.co) for v in obj.data.vertices]);assert vertices.shape==original.shape
error=float(np.max(abs(vertices-original)));assert error<2e-7,error
bm=bmesh.new();bm.from_mesh(obj.data)
assert all(e.is_manifold for e in bm.edges)
assert all(len(f.verts)==3 for f in bm.faces)
old=np.array([tuple(f.normal) for f in bm.faces]);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));new=np.array([tuple(f.normal) for f in bm.faces]);flips=int((np.sum(old*new,axis=1)<0).sum());assert flips==0
volume=bm.calc_volume(signed=True);assert volume>0;bm.free()
uv=np.array([tuple(x.uv) for x in obj.data.uv_layers.active.data]);assert np.isfinite(uv).all() and uv.min()>=0 and uv.max()<=1
bpy.ops.wm.open_mainfile(filepath=str(BASE/'walk-cycle/final/peasant-walk.blend'))
body=bpy.data.objects['Peasant body'];arm=bpy.data.objects['Peasant rig']
assert len(arm.data.bones)==34 and len(body.data.polygons)==1460
assert np.array_equal(np.array([tuple(v.co) for v in body.data.vertices]),vertices)
assert np.array_equal(np.array([tuple(x.uv) for x in body.data.uv_layers.active.data]),uv)
for v in body.data.vertices:assert abs(sum(g.weight for g in v.groups)-1)<1e-5 and len(v.groups)<=4
textures={hashlib.sha256(n.image.packed_file.data).hexdigest() for slot in body.material_slots for n in slot.material.node_tree.nodes if n.type=='TEX_IMAGE'}
assert textures=={hashlib.sha256((BASE/'model/basecolor.png').read_bytes()).hexdigest()}
cycle=json.loads((BASE/'walk-cycle/validation.json').read_text());assert cycle['source_preserved']
report={'vertices':len(vertices),'triangles':len(body.data.polygons),'bones':len(arm.data.bones),
 'original_bpt_vertex_positions_preserved_after_centering':True,'max_vertex_error':error,
 'boundary_edges':0,'overconnected_edges':0,'normal_recalculation_flips':flips,'positive_signed_volume':volume,
 'hair_t_junction_splits':meta['hair_t_junctions_split'],'ankle_edge_flips':meta['ankle_nonmanifold_edges_repaired'],
 'finite_in_range_uvs':True,'final_uvs_rest_vertices_and_packed_texture_verified':True,'normalized_weights_max_four_influences':True,
 'animation_validation':'walk-cycle/validation.json',
 'limitation':'Manifold connectivity does not guarantee absence of geometric self-intersections; see walk-cycle/intersections.json.'}
(BASE/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
