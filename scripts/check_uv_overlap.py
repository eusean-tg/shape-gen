"""Check exported UV triangle interiors on a pixel grid (not an exact proof)."""
import argparse
import json
from pathlib import Path

import numpy as np
import trimesh

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('mesh',type=Path)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--resolution',type=int,default=2048)
args=parser.parse_args()
scene=trimesh.load(args.mesh,force='scene',process=False)
size=args.resolution
count=np.zeros((size,size),np.uint16)
zero=0;out_of_bounds=0
for mesh in scene.geometry.values():
    uv=mesh.visual.uv
    out_of_bounds+=int(((uv<0)|(uv>1)|~np.isfinite(uv)).any(axis=1).sum())
    for t in uv[mesh.faces]*(size-1):
        low=np.maximum(np.floor(t.min(0)).astype(int),0)
        high=np.minimum(np.ceil(t.max(0)).astype(int),size-1)
        x,y=np.meshgrid(np.arange(low[0],high[0]+1),np.arange(low[1],high[1]+1))
        p=np.stack([x,y],axis=-1)-t[0]
        a,b=t[1]-t[0],t[2]-t[0]
        det=a[0]*b[1]-a[1]*b[0]
        if abs(det)<1e-10:
            zero+=1
            continue
        u=(p[...,0]*b[1]-p[...,1]*b[0])/det
        v=(a[0]*p[...,1]-a[1]*p[...,0])/det
        count[low[1]:high[1]+1,low[0]:high[0]+1]+=(u>1e-5)&(v>1e-5)&(u+v<1-1e-5)
report={'zero_area_uv_triangles':zero,'out_of_bounds_uv_vertices':out_of_bounds,
    'overlapping_triangle_interior_samples':int((count>1).sum()),'raster_resolution':size}
args.output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
if zero or out_of_bounds or report['overlapping_triangle_interior_samples']:
    raise SystemExit(1)
