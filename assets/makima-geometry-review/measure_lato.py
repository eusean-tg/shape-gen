"""Measure raw output, save a normal-repaired copy in the source coordinate frame."""
from pathlib import Path
import sys
import json
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parent
label = sys.argv[1] if len(sys.argv) > 1 else 'lato-1200'
source = trimesh.load(ROOT / 'dense/result/01-dense.glb', force='mesh')
mesh = trimesh.load(ROOT / label / 'makima_pred.obj', force='mesh', process=False)

def metrics(m):
    counts = np.bincount(m.edges_unique_inverse)
    return dict(vertices=len(m.vertices), triangles=len(m.faces),
                boundary_edges=int((counts == 1).sum()),
                nonmanifold_edges=int((counts > 2).sum()),
                watertight=bool(m.is_watertight),
                winding_consistent=bool(m.is_winding_consistent),
                vertex_graph_components=len(trimesh.graph.connected_components(
                    m.edges_unique, nodes=np.arange(len(m.vertices)), min_len=1)),
                manifold_face_adjacency_components=len(m.split(only_watertight=False)),
                bounds=m.bounds.tolist())

fixed = mesh.copy()
trimesh.repair.fix_normals(fixed, multibody=True)
report = {'raw': metrics(mesh), 'normal_repaired': metrics(fixed)}
extent = np.ptp(source.vertices, axis=0).max()
center = source.bounds.mean(axis=0)
for suffix, m in [('raw', mesh), ('normals', fixed)]:
    m.vertices = m.vertices * extent + center
    m.export(ROOT / label / f'makima-{suffix}.glb')
(ROOT / label / 'geometry.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
