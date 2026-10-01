"""Compare body intersections before/after foot locking on all unique baked frames."""
from pathlib import Path
import json
import argparse
import numpy as np
import pymeshlab
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'assets/peasant-walk-cycle'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--asset-dir',type=Path,default=BASE)
parser.add_argument('--mesh',type=Path,default=ROOT/'assets/peasant-material-masks/regions.npz')
args=parser.parse_args();BASE=args.asset_dir.resolve()
data=np.load(BASE/'cycle-analysis.npz')
regions=np.load(args.mesh)
# The body is first in this existing, verified geometry/region export.
faces=regions['faces'];count=len(data['final_vertices'][0]);faces=faces[np.all(faces<count,axis=1)]
report={}
for name,key in [('before-foot-lock','base_vertices'),('final','final_vertices')]:
    counts=[]
    for v in data[key][:-1]:
        mesh=pymeshlab.MeshSet();mesh.add_mesh(pymeshlab.Mesh(v,faces))
        mesh.apply_filter('compute_selection_by_self_intersections_per_face')
        counts.append(int(mesh.current_mesh().face_selection_array().sum()))
    report[name]={'minimum':min(counts),'median':float(np.median(counts)),'maximum':max(counts),'per_frame_selected_face_counts':counts}
report['note']='Selected self-intersecting body faces, not collision pairs. Pouch attachment overlap is excluded. Near-touching surfaces can be precision-sensitive.'
(BASE/'intersections.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:({a:b for a,b in v.items() if not a.startswith('per_frame')} if isinstance(v,dict) else v) for k,v in report.items()},indent=2))
