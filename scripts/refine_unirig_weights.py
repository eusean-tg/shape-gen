"""Mirror clean left-side weights to exact right-side vertex counterparts."""
import json
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree

BASE=Path(__file__).resolve().parents[1]/'assets/peasant-unirig'
data=np.load(BASE/'rig-data.npz')
vertices=data['vertices'];weights=data['weights'].copy();names=data['names'].tolist()
center=json.loads((BASE/'input.json').read_text())
# The original mesh symmetry plane, also the bounding-box normalization center.
mid=float((vertices[:,0].min()+vertices[:,0].max())/2)
mirrored=vertices.copy();mirrored[:,0]=2*mid-mirrored[:,0]
distance,index=cKDTree(vertices).query(mirrored)
swap=[names.index(n[:-2]+('.R' if n.endswith('.L') else '.L'))
      if n.endswith(('.L','.R')) else i for i,n in enumerate(names)]
mask=(vertices[:,0]<mid)&(distance<.002)
weights[mask]=data['weights'][index[mask]][:,swap]
assert np.isfinite(weights).all() and np.all(weights>=0)
assert np.max(abs(weights.sum(1)-1))<2e-6
assert np.max((weights>0).sum(1))<=4
np.savez(BASE/'refined-rig-data.npz',**{k:weights if k=='weights' else data[k] for k in data.files})
report={'method':'Copy left weights to matching right vertices, swapping L/R bone names.',
        'symmetry_plane_x':mid,'match_tolerance':.002,'matched_right_vertices':int(mask.sum()),
        'changed_vertices':int(np.any(weights!=data['weights'],axis=1).sum()),
        'max_matching_distance':float(distance[mask].max()),
        'geometry_uvs_and_joint_positions_changed':False,
        'limitation':'High hip lifts still fold the central tunic. No geometry repair or cloth simulation.'}
(BASE/'weight-refinement.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
