"""Rasterize reviewed mesh-region masks into UV space, then bake masked materials."""
import argparse,json
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt,map_coordinates
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'assets/peasant-material-masks'
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--swatches',type=Path);args=parser.parse_args()
d=np.load(OUT/'regions.npz');size=2048
ids=np.full((size,size),-1,np.int32);xyz=np.zeros((size,size,3),np.float32)
for i,(uv,face) in enumerate(zip(d['uv'],d['faces'])):
    p=uv*np.array([size,-size])+np.array([0,size])
    low=np.maximum(np.floor(p.min(0)).astype(int),0);high=np.minimum(np.ceil(p.max(0)).astype(int),size-1)
    if np.any(high<low):continue
    yy,xx=np.mgrid[low[1]:high[1]+1,low[0]:high[0]+1];q=np.stack([xx+.5,yy+.5],-1)
    basis=np.stack([p[1]-p[0],p[2]-p[0]],axis=1)
    if abs(np.linalg.det(basis))<1e-10:continue
    ab=(q-p[0])@np.linalg.inv(basis).T;w=np.concatenate([1-ab.sum(-1,keepdims=True),ab],axis=-1);valid=(w>=-1e-7).all(-1)
    target=ids[low[1]:high[1]+1,low[0]:high[0]+1];target[valid]=i
    pos=xyz[low[1]:high[1]+1,low[0]:high[0]+1];pos[valid]=(w@d['vertices'][face])[valid]
occupied=ids>=0;region=np.full_like(ids,-1);region[occupied]=d['labels'][ids[occupied]]
old=np.asarray(Image.open(ROOT/'assets/peasant-hypaint-experiment/hypaint-imagegen/basecolor.png').convert('RGB'),dtype=np.float32)/255
# This band follows the original belt's location; split within triangles in UV
# space instead of changing the mesh merely to add a thin material boundary.
belt=(region==1)&(xyz[:,:,2]>.085)&(xyz[:,:,2]<.13)&(abs(xyz[:,:,0]+.02224)<.235)
region[belt]=3
palette=np.array([[.78,.61,.40],[.61,.47,.22],[.40,.31,.29],[.215,.169,.137],[.215,.169,.137],[.44,.31,.21]],np.float32)
flat=palette[region.clip(0)];preserved=(region==0)
# Keep the existing small metal buckle within the belt mask, without retaining
# the old surrounding shirt/trouser color contamination.
buckle=((region==3)|(region==1))&(abs(xyz[:,:,0]+.005)<.075)&(xyz[:,:,2]>.045)&(xyz[:,:,2]<.16)&(xyz[:,:,1]<-.035)&((old.max(-1)-old.min(-1))<.12)&(old.max(-1)>.38)
region[buckle]=3
preserved|=buckle
flat[preserved]=old[preserved]
result=flat.copy()
if args.swatches:
    swatch=np.asarray(Image.open(args.swatches).convert('RGB'),dtype=np.float32)/255
    hh,ww=swatch.shape[:2];tiles=[swatch[:hh//2,:ww//2],swatch[:hh//2,ww//2:],swatch[hh//2:,:ww//2],swatch[hh//2:,ww//2:]]
    for rid,tile_id in [(1,0),(2,1),(3,2),(4,2),(5,3)]:
        mask=(region==rid)&~preserved;tile=tiles[tile_id]
        # Keep only the swatch's subtle variation around the chosen palette.
        detail=tile/np.maximum(np.median(tile.reshape(-1,3),axis=0),.03)
        detail=np.clip(detail,.85,1.15)
        y,x=np.nonzero(mask);sy=(y%256)*(tile.shape[0]-1)/255;sx=(x%256)*(tile.shape[1]-1)/255
        variation=np.stack([map_coordinates(detail[:,:,c],[sy,sx],order=1,mode='wrap') for c in range(3)],-1)
        result[mask]=np.clip(palette[rid]*(.65+.35*variation),0,1)
_,nearest=distance_transform_edt(~occupied,return_indices=True)
for arr,name in [(flat,'flat-basecolor.png'),(result,'masked-basecolor.png')]:
    arr[~occupied]=arr[nearest[0][~occupied],nearest[1][~occupied]]
    Image.fromarray(np.rint(arr*255).astype(np.uint8)).save(OUT/name)
Image.fromarray(np.uint8(region+1),'L').save(OUT/'material-ids.png')
debug_palette=np.array([[239,180,130],[236,190,40],[60,110,210],[100,60,150],[40,45,50],[210,70,40]],np.uint8)
debug=np.zeros((size,size,3),np.uint8);debug[occupied]=debug_palette[region[occupied]];debug[~occupied]=debug[nearest[0][~occupied],nearest[1][~occupied]]
Image.fromarray(debug).save(OUT/'region-colors.png')
np.savez_compressed(OUT/'uv-regions.npz',face_ids=ids,region=region,xyz=xyz)
report={'size':size,'occupied_texels':int(occupied.sum()),'region_texels':{int(i):int((region==i).sum()) for i in range(6)},'head_skin_and_buckle_texels_exact':bool(np.array_equal(np.rint(result[preserved]*255).astype(np.uint8),np.rint(old[preserved]*255).astype(np.uint8))),'preserved_buckle_texels':int(buckle.sum()),'swatches':str(args.swatches) if args.swatches else None,'belt_height_range':[.085,.13]}
(OUT/'bake.json').write_text(json.dumps(report,indent=2)+'\n')
for lo in np.arange(-.05,.26,.025):
    mask=occupied&(abs(xyz[:,:,0]+.02224)<.15)&(xyz[:,:,1]<0)&(xyz[:,:,2]>lo)&(xyz[:,:,2]<lo+.025)
    if mask.any():print('old front band',round(float(lo),3),np.median(old[mask],axis=0).round(3).tolist())
print(json.dumps(report,indent=2))
