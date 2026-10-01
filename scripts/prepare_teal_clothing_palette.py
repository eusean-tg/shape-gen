"""Bake independent runtime dye regions without changing mesh topology or UVs."""
from pathlib import Path
import json
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets/teal-peasant/collar-fix/textures'
d=np.load(OUT/'surface-regions.npz');r=d['region'];xyz=d['xyz'];occupied=d['face_ids']>=0
mesh=np.load(ROOT/'assets/teal-peasant/model/mesh.npz')
centers=mesh['vertices'][mesh['faces']].mean(1)
# Follow the coarse hem's face boundary instead of drawing a stripe across it.
trouser_faces=centers[:,2]<.94
mask=np.zeros(r.shape,np.uint8)
mask[r==0]=1
mask[(r==0)&trouser_faces[d['face_ids'].clip(0)]]=2
mask[(r==1)&(xyz[:,:,2]>.7)]=3
mask[(r==1)&(xyz[:,:,2]<=.7)]=4
mask[r==5]=5;mask[r==4]=6
mask[~occupied]=0
assert not mask[(r==2)|(r==3)].any()
_,near=distance_transform_edt(~occupied,return_indices=True)
mask[~occupied]=mask[near[0][~occupied],near[1][~occupied]]
Image.fromarray(mask).save(OUT/'clothing-mask.png')
meta=json.loads((OUT/'materials.json').read_text())
slots=[]
for i,(key,label,rid) in enumerate([('tunic','Tunic',0),('trousers','Trousers',0),('sleeves','Sleeves',1),('stockings','Stockings',1),('trim','Collar / cuffs',5),('shoes','Shoes',4)]):
 color=meta['palette_srgb'][rid]
 slots.append({'id':i+1,'key':key,'label':label,'baseSRGB':color,
               'defaultColor':'#'+''.join(f'{round(c*255):02x}' for c in color),
               'texels':int(((mask==i+1)&occupied).sum())})
(OUT/'clothing-palette.json').write_text(json.dumps({'version':1,'slots':slots},indent=2)+'\n')
print({s['key']:s['texels'] for s in slots})
