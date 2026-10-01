"""Bake authored garment masks and restrained cloth grain onto the new UVs."""
from pathlib import Path
import argparse,json
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt,map_coordinates
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'assets/teal-peasant'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,default=BASE/'model')
args=parser.parse_args();OUT=args.output.resolve();OUT.mkdir(parents=True,exist_ok=True)
d=np.load(BASE/'model/mesh.npz');v=d['vertices'];faces=d['faces'];uv=d['uv'][d['loops']]
height=float(v[:,2].max());size=2048
ids=np.full((size,size),-1,np.int32);xyz=np.zeros((size,size,3),np.float32)
for i,(triangle,face) in enumerate(zip(uv,faces)):
 p=triangle*np.array([size,-size])+np.array([0,size]);lo=np.maximum(np.floor(p.min(0)).astype(int),0);hi=np.minimum(np.ceil(p.max(0)).astype(int),size-1)
 if np.any(hi<lo):continue
 yy,xx=np.mgrid[lo[1]:hi[1]+1,lo[0]:hi[0]+1];q=np.stack([xx+.5,yy+.5],-1)
 basis=np.stack([p[1]-p[0],p[2]-p[0]],axis=1)
 if abs(np.linalg.det(basis))<1e-10:continue
 ab=(q-p[0])@np.linalg.inv(basis).T;w=np.concatenate([1-ab.sum(-1,keepdims=True),ab],-1);valid=(w>=-1e-7).all(-1)
 ids[lo[1]:hi[1]+1,lo[0]:hi[0]+1][valid]=i
 xyz[lo[1]:hi[1]+1,lo[0]:hi[0]+1][valid]=(w@v[face])[valid]
# Region IDs: teal cloth, pale linen, skin, hair, shoes, collar/trim.
def classify(points):
 x,y,z=np.moveaxis(points,-1,0);f=z/height;a=abs(x)
 out=np.zeros(x.shape,np.int16)
 out[(f<.245)&(f>=.083)]=1
 out[f<.083]=4
 arm=(a>.215)&(f>.36)&(f<.711)
 out[arm]=1
 out[arm&(f<.501)]=2
 out[arm&(f>.697)]=5
 # Head/neck: front faceless skin panel, angular dark hair around sides/back.
 # Below the collar top, skin belongs only inside the authored front opening.
 # The old .808 box exposed skin below the back collar and beside the front V.
 out[(f>.850)&(a<.125)]=2
 hair=(f>.846)
 out[hair]=3
 face=hair&(f<.951)&(y<-.045)&(a<.092)
 out[face]=2
 # V neck and narrow pale facing on the front. Back facing wraps the neckline.
 vline=.778+.65*a/height
 front=(y<.01)&(a<.18)&(f>.76)&(f<.856)
 out[front&(f>=vline)&(f<vline+.025)]=5
 out[front&(f>=vline+.025)&(f<.851)]=2
 back=(y>=.01)&(a<.165)&(f>.824)&(f<.850)
 out[back]=5
 return out
region=classify(xyz);occupied=ids>=0
palette=np.array([[.19,.27,.285],[.65,.61,.61],[.76,.51,.42],[.105,.155,.18],[.40,.36,.34],[.70,.72,.73]],np.float32)
flat=palette[region];result=flat.copy()
# Reuse the previously generated cloth swatch's neutral variation, recolored to
# the reference palette. This preserves its grain without projecting old colors.
swatch=np.asarray(Image.open(ROOT/'assets/peasant-material-masks/material-swatches.png').convert('RGB'),dtype=np.float32)/255
swatch=swatch[:swatch.shape[0]//2,:swatch.shape[1]//2];grain=swatch.mean(-1);grain=np.clip(grain/np.median(grain),.8,1.2)
texel=xyz[occupied];coords=np.array([(texel[:,2]/.35%1)*(grain.shape[0]-1),(texel[:,0]/.35%1)*(grain.shape[1]-1)])
variation=map_coordinates(grain,coords,order=1,mode='wrap')
for rid,strength in [(0,.3),(1,.18),(4,.12),(5,.16)]:
 mask=region[occupied]==rid;colors=result[occupied];colors[mask]*=(1+strength*(variation[mask]-1))[:,None];result[occupied]=colors
_,nearest=distance_transform_edt(~occupied,return_indices=True)
for arr,name in [(flat,'flat-basecolor.png'),(result,'basecolor.png')]:
 arr[~occupied]=arr[nearest[0][~occupied],nearest[1][~occupied]]
 Image.fromarray(np.uint8(np.clip(arr*255,0,255))).save(OUT/name)
Image.fromarray(np.uint8(np.where(occupied,region+1,0))).save(OUT/'material-ids.png')
labels=classify(v[faces].mean(1));np.save(OUT/'face-regions.npy',labels)
np.savez_compressed(OUT/'surface-regions.npz',face_ids=ids,region=region,xyz=xyz)
report={'size':size,'method':'Authored surface-space garment masks, baked to per-corner UVs; recolored imagegen cloth grain.',
 'region_names':['Teal tunic and breeches','Pale linen sleeves and stockings','Faceless skin and hands','Dark hair','Ankle shoes','Collar and cuff trim'],
 'palette_srgb':palette.tolist(),'occupied_texels':int(occupied.sum()),'grain_source':'assets/peasant-material-masks/material-swatches.png',
 'region_texels':{int(i):int(((region==i)&occupied).sum()) for i in range(6)}}
(OUT/'materials.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
