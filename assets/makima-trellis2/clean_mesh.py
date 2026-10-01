"""Geometry portion of official o_voxel non-remesh export; preserve raw input."""
import argparse,fcntl,json,time,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('output',type=Path);p.add_argument('--target',type=int,default=500000);a=p.parse_args()
if a.output.exists():raise FileExistsError(a.output)
with (Path.home()/'.cache/shape-gen/gpu.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 import torch,cumesh,trimesh,numpy as np
 torch.set_num_threads(6);torch.cuda.reset_peak_memory_stats();start=time.monotonic()
 m=trimesh.load(a.input,force='mesh',process=False);mesh=cumesh.CuMesh();mesh.init(torch.tensor(m.vertices,dtype=torch.float32,device='cuda'),torch.tensor(m.faces,dtype=torch.int32,device='cuda'))
 mesh.fill_holes(max_hole_perimeter=.03)
 mesh.simplify(a.target*3,verbose=True)
 for i in range(2):
  mesh.remove_duplicate_faces();mesh.repair_non_manifold_edges();mesh.remove_small_connected_components(1e-5);mesh.fill_holes(max_hole_perimeter=.03)
  if i==0:mesh.simplify(a.target,verbose=True)
 mesh.unify_face_orientations()
 v,f=mesh.read();n=trimesh.Trimesh(v.cpu().numpy(),f.cpu().numpy(),process=False);n.export(a.output)
 c=np.bincount(n.edges_unique_inverse)
 record={'input':str(a.input),'output':str(a.output),'recipe':'official o_voxel non-remesh geometry cleanup, no UV or texturing stages','target':a.target,'triangles':len(n.faces),'vertices':len(n.vertices),'watertight':bool(n.is_watertight),'winding_consistent':bool(n.is_winding_consistent),'boundary_edges':int((c==1).sum()),'nonmanifold_edges':int((c>2).sum()),'seconds':time.monotonic()-start,'peak_allocated_mib':torch.cuda.max_memory_allocated()/2**20,'sha256':hashlib.sha256(a.output.read_bytes()).hexdigest()}
 a.output.with_suffix('.json').write_text(json.dumps(record,indent=2)+'\n');print(record)
