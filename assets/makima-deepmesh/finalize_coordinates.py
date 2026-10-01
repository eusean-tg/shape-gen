"""Export completed token streams in source XYZ; preserve unmodified tokens."""
import sys,json,hashlib
from pathlib import Path
import numpy as np,trimesh
r=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(r/'third_party/DeepMesh'))
from sft.datasets.serializaiton import deserialize
folder=Path(sys.argv[1]);record=json.loads((folder/'trial.json').read_text())
assert record['status']=='complete' and record['ended_with_eos']
codes=np.load(folder/'codes.npy',allow_pickle=False);assert codes[-1]==4737
v=deserialize(codes[:-1].copy())
v=v*(record['normalization_extent']/1.9)+np.array(record['normalization_center'])
m=trimesh.Trimesh(v,np.arange(len(v)).reshape(-1,3),process=False)
m.merge_vertices();m.update_faces(m.unique_faces());m.update_faces(m.nondegenerate_faces());m.remove_unreferenced_vertices();m.fix_normals()
m.export(folder/'02-deepmesh.glb');m.export(folder/'02-deepmesh.obj')
record.update(bounds=m.bounds.tolist(),output_sha256=hashlib.sha256((folder/'02-deepmesh.glb').read_bytes()).hexdigest(),
 output_coordinate_transform='Decoder XYZ, undo normalization only; source alignment checked separately. Upstream reverse-axis diagnostic also saved.',
 component_triangles=sorted([len(c.faces) for c in m.split(only_watertight=False)],reverse=True))
(folder/'trial.json').write_text(json.dumps(record,indent=2)+'\n')
print(record['bounds'])
