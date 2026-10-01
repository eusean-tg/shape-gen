"""Measure body self-intersections in saved, evaluated rig poses (PyMeshLab)."""
import json
from pathlib import Path
import numpy as np
import pymeshlab
BASE=Path(__file__).resolve().parents[1]/'assets/peasant-unirig/final'
result={}
for path in sorted(BASE.glob('*-mesh.npz')):
    data=np.load(path);mesh=pymeshlab.MeshSet()
    mesh.add_mesh(pymeshlab.Mesh(data['vertices'],data['faces']))
    mesh.apply_filter('compute_selection_by_self_intersections_per_face')
    selected=mesh.current_mesh().face_selection_array()
    result[path.stem.removesuffix('-mesh')]={'body_self_intersecting_faces':int(selected.sum()),
                                          'body_face_indices':np.flatnonzero(selected).tolist()}
    mesh=pymeshlab.MeshSet()
    mesh.add_mesh(pymeshlab.Mesh(np.concatenate([data['vertices'],data['pouch_vertices']]),
        np.concatenate([data['faces'],data['pouch_faces']+len(data['vertices'])])))
    mesh.apply_filter('compute_selection_by_self_intersections_per_face')
    selected=mesh.current_mesh().face_selection_array()
    result[path.stem.removesuffix('-mesh')]['intersecting_pouch_faces']=int(selected[len(data['faces']):].sum())
(BASE/'intersections.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
