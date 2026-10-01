"""Verify original vertex positions and face retention in the saved GLB."""
from pathlib import Path
import json

import numpy as np
import pymeshlab
import trimesh

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'assets/peasant-bpt-staged/imagegen-paint'
OUT=PARENT/'repair-original-v4'
data=json.loads((PARENT/'repair-v3/source-mesh.json').read_text())
vertices=np.array(data['vertices'])[:,[0,2,1]]
vertices[:,2]*=-1 # Blender Z-up -> glTF Y-up
source_faces=np.array(data['faces'])
source_positions={tuple(v):i for i,v in enumerate(vertices)}
source_triangles={tuple(sorted(f)):i for i,f in enumerate(source_faces)}
scene=trimesh.load(OUT/'peasant-repaired.glb',process=False)
used=set();retained=set();report={}
for name,mesh in scene.geometry.items():
    indices=np.array([source_positions[tuple(v)] for v in mesh.vertices])
    used.update(indices)
    original_ids=[source_triangles.get(tuple(sorted(f))) for f in indices[mesh.faces]]
    # Matching triangles can occur twice at the touching body/pouch interface;
    # the union below measures retention of the source, not duplication count.
    retained.update(i for i in original_ids if i is not None)
    welded=trimesh.Trimesh(mesh.vertices,mesh.faces,process=True)
    ms=pymeshlab.MeshSet()
    ms.add_mesh(pymeshlab.Mesh(vertex_matrix=welded.vertices,face_matrix=welded.faces))
    ms.compute_selection_by_self_intersections_per_face()
    intersections=ms.current_mesh().selected_face_number()
    report[name]={'triangles':len(mesh.faces),
        'vertices_after_welding_export_seams':len(welded.vertices),
        'watertight':bool(welded.is_watertight),'consistent_winding':bool(welded.is_winding_consistent),
        'signed_volume':float(welded.volume),'self_intersecting_faces':intersections,
        'all_vertices_match_source_exactly':True}
    assert intersections==0
    if 'pouch' in name.lower():
        assert welded.is_watertight and welded.is_winding_consistent and welded.volume>0
assert used==set(range(len(vertices))), 'Some original vertex positions were discarded'
removed=sorted(set(range(len(source_faces)))-retained)
assert removed==[1281], removed
report['source_preservation']={'unique_original_positions':len(used),
    'new_positions':0,'moved_positions':0,'discarded_positions':0,
    'retained_source_triangles':len(retained),'retriangulated_source_face_ids':removed,
    'total_triangles':sum(len(m.faces) for m in scene.geometry.values())}
(OUT/'source-preservation-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
