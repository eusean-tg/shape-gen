"""Geometry stages of the official TRELLIS.2 demo export, with no texture bake."""
import argparse, fcntl, hashlib, json, time
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('input', type=Path)
p.add_argument('output', type=Path)
p.add_argument('--resolution', type=int, required=True)
p.add_argument('--target', type=int, default=500000)
a = p.parse_args()
if a.output.exists():
    raise FileExistsError(a.output)
with (Path.home()/'.cache/shape-gen/gpu.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    import torch, cumesh, trimesh, numpy as np
    torch.set_num_threads(6)
    start = time.monotonic()
    m = trimesh.load(a.input, force='mesh', process=False)
    mesh = cumesh.CuMesh()
    mesh.init(torch.tensor(m.vertices, dtype=torch.float32, device='cuda'),
              torch.tensor(m.faces, dtype=torch.int32, device='cuda'))
    mesh.fill_holes(max_hole_perimeter=.03)
    v, f = mesh.read()
    bvh = cumesh.cuBVH(v, f)
    mesh.init(*cumesh.remeshing.remesh_narrow_band_dc(
        v, f, center=torch.zeros(3, device='cuda'),
        scale=(a.resolution+3)/a.resolution, resolution=a.resolution,
        band=1, project_back=0, verbose=True, bvh=bvh))
    remeshed_faces = mesh.num_faces
    mesh.simplify(a.target, verbose=True)
    v, f = mesh.read()
    n = trimesh.Trimesh(v.cpu().numpy(), f.cpu().numpy(), process=False)
    n.export(a.output)
    c = np.bincount(n.edges_unique_inverse)
    record = dict(input=str(a.input), output=str(a.output),
        recipe='Official demo geometry export: initial fill .03, narrow-band DC band=1 project_back=0, simplify; no texture or UV stages',
        resolution=a.resolution, target=a.target, remeshed_faces=remeshed_faces,
        triangles=len(n.faces), vertices=len(n.vertices), watertight=bool(n.is_watertight),
        winding_consistent=bool(n.is_winding_consistent), boundary_edges=int((c==1).sum()),
        nonmanifold_edges=int((c>2).sum()), seconds=round(time.monotonic()-start,2),
        sha256=hashlib.sha256(a.output.read_bytes()).hexdigest())
    a.output.with_suffix('.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps(record, indent=2), flush=True)
