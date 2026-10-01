"""Diagnostic BPT conditioning: reject surface samples occluded along their normal.

This favors externally visible surfaces, can omit deep recesses, and changes the
conditioning distribution. It is not a watertight repair or an interior proof.
"""
import argparse, json, hashlib
from pathlib import Path
import numpy as np
import trimesh
import open3d as o3d
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('mesh',type=Path)
p.add_argument('output',type=Path)
a=p.parse_args()
if a.output.exists():raise FileExistsError(a.output)
m=trimesh.load(a.mesh,force='mesh',process=False)
m.vertices=(m.vertices-m.bounds.mean(axis=0))*(1.9/m.extents.max())
np.random.seed(12345)
points,faces=m.sample(100000,return_index=True)
normals=m.face_normals[faces]
mesh=o3d.t.geometry.TriangleMesh(
    o3d.core.Tensor(m.vertices.astype(np.float32)),
    o3d.core.Tensor(m.faces.astype(np.int32)))
scene=o3d.t.geometry.RaycastingScene(nthreads=6)
scene.add_triangles(mesh)
rays=np.concatenate([points+normals*4,-normals],axis=1).astype(np.float32)
hit=scene.cast_rays(o3d.core.Tensor(rays),nthreads=6)['t_hit'].numpy()
# At normalized max extent 1.9, this is smaller than the remesh band thickness.
visible=np.isfinite(hit)&(np.abs(hit-4)<.0002)
cloud=np.concatenate([points[visible],normals[visible]],axis=1).astype(np.float16)
if len(cloud)<4096:raise RuntimeError(f'Only {len(cloud)} exterior samples')
cloud=cloud[np.random.choice(len(cloud),4096,replace=False)]
np.save(a.output,cloud)
record=dict(source=str(a.mesh),source_sha256=hashlib.sha256(a.mesh.read_bytes()).hexdigest(),
    method='100k area samples, first-hit visibility along normal from distance 4 in normalized coordinates, tolerance 0.0002, random subset 4096',
    seed=12345,candidate_points=len(points),visible_points=int(visible.sum()),
    visible_fraction=float(visible.mean()),point_count=len(cloud),
    cloud_sha256=hashlib.sha256(cloud.tobytes()).hexdigest(),
    caveat='May reject concave or occluded outward faces; not a semantic interior classifier')
a.output.with_suffix('.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
