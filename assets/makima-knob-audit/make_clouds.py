"""Controlled surface-sampling variants in the BPT normalization frame."""
from pathlib import Path
import argparse,json
import numpy as np
import trimesh
from scipy.spatial import cKDTree
import open3d as o3d
p=argparse.ArgumentParser();p.add_argument('mesh',type=Path);p.add_argument('output',type=Path)
a=p.parse_args();a.output.mkdir(exist_ok=True,parents=True)
m=trimesh.load(a.mesh,force='mesh',process=False)
m.vertices=(m.vertices-m.bounds.mean(axis=0))*(1.9/m.extents.max())
np.random.seed(12345)
points,faces=m.sample(50000,return_index=True)
cloud=np.concatenate([points,m.face_normals[faces]],axis=1).astype(np.float16)
idx=np.random.choice(len(cloud),4096,replace=False)
np.save(a.output/'area4096.npy',cloud[idx])
np.random.seed(12345)
np.save(a.output/'area8192.npy',cloud[np.random.choice(len(cloud),8192,replace=False)])
pc=o3d.geometry.PointCloud(o3d.utility.Vector3dVector(points))
sampled=np.asarray(pc.farthest_point_down_sample(4096).points)
ids=cKDTree(points).query(sampled)[1]
np.save(a.output/'coverage4096.npy',cloud[ids])
report={}
for f in a.output.glob('*.npy'):
 c=np.load(f);report[f.name]={'points':len(c),
 'upper_back_region_points':int(((np.abs(c[:,0])<.12)&(c[:,1]>.2)&(c[:,1]<.7)&(c[:,2]<-.09)).sum())}
(a.output/'sampling.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report),flush=True)
