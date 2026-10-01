"""Find nonintersecting caps using only original BPT boundary vertices."""
from pathlib import Path
import itertools
import json
import numpy as np
import pymeshlab
import trimesh

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'assets/peasant-bpt-staged/imagegen-paint'
OUT=PARENT/'repair-original-v4'
data=json.loads((PARENT/'repair-v3/source-mesh.json').read_text())
vertices=np.array(data['vertices']);faces=np.array(data['faces'])
bag_ids=set(range(856,890))|set(range(1264,1275))|{1281}|set(range(1311,1321))|set(range(1361,1372))
# One original triangle crosses the top flap. Retessellate that patch using the
# other diagonal and the same four original vertices.
retained=sorted(bag_ids-{1281})
top=[[669,672,969],[672,677,969]]

def triangulations(loop):
    if len(loop)<3:return [[]]
    if len(loop)==3:return [[list(loop)]]
    result=[]
    for k in range(1,len(loop)-1):
        for left,right in itertools.product(triangulations(loop[:k+1]),triangulations(loop[k:])):
            result.append(left+right+[[loop[0],loop[k],loop[-1]]])
    return result

side_options=triangulations([693,695,760,759,917,1010])
back_options=triangulations([693,691,576,677,672,671])
best=None;tested=0
for side,back in itertools.product(side_options,back_options):
    added=np.array(side+back+top)
    candidate=np.concatenate([faces[retained],added])
    mesh=trimesh.Trimesh(vertices,candidate,process=False)
    if (mesh.area_faces<1e-12).any():continue
    ms=pymeshlab.MeshSet();ms.add_mesh(pymeshlab.Mesh(vertex_matrix=vertices,face_matrix=candidate))
    ms.compute_selection_by_self_intersections_per_face();tested+=1
    if ms.current_mesh().selected_face_number():continue
    score=float(trimesh.triangles.area(vertices[added]).sum())
    if best is None or score<best[0]:best=(score,added.tolist())
assert best is not None,'No nonintersecting cap found using boundary vertices'
report={'retained_pouch_face_ids':retained,'retriangulated_original_face_ids':[1281],
        'added_pouch_triangles':best[1],'cap_candidates_tested':tested,
        'self_intersecting_pouch_faces':0,'cap_area':best[0]}
(OUT/'diagnostics/cap-plan.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
