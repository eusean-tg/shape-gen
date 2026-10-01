"""Pull imagegen colors into each UV texel, avoiding sparse screen-space splats.

Asset-specific projection of the existing eight generated views. No new image
synthesis: all coordinates and visibility tests are computed from the mesh.
"""
from pathlib import Path
import argparse
import json
import time

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt
from scipy.spatial import cKDTree
import torch
import torch.nn.functional as F
import trimesh
from hy3dgen.texgen.differentiable_renderer.mesh_render import MeshRender

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'assets/peasant-bpt-staged/imagegen-paint'
OUT=PARENT/'repair-v3'
SIZE=2048

def sample(image, grid, mode='bilinear'):
    if image.ndim==2: image=image[...,None]
    return F.grid_sample(image.permute(2,0,1)[None].contiguous(),grid[None],
                         mode=mode,padding_mode='border',align_corners=True)[0].permute(1,2,0)

@torch.inference_mode()
def main():
    start=time.monotonic()
    scene=trimesh.load(OUT/'unwrapped.glb',process=False)
    meshes=[m for name,m in sorted(scene.geometry.items(),key=lambda item: 'pouch' in item[0].lower())]
    assert len(meshes)==2, 'Expected one body and one pouch'
    vertices=np.concatenate([m.vertices for m in meshes])
    uv=np.concatenate([m.visual.uv for m in meshes])
    faces=np.concatenate([m.faces+sum(len(n.vertices) for n in meshes[:i]) for i,m in enumerate(meshes)])
    mesh=trimesh.Trimesh(vertices,faces,process=False,
        visual=trimesh.visual.TextureVisuals(uv=uv))
    render=MeshRender(default_resolution=2048,texture_size=SIZE,device='cuda')
    render.load_mesh(mesh)
    uvclip=torch.cat([render.vtx_uv*2-1,torch.ones_like(render.vtx_uv)],dim=-1)
    uvrast,_=render.raster_rasterize(uvclip,render.uv_idx,[SIZE,SIZE])
    ids=uvrast[0,...,-1].long()-1
    occupied=ids>=0
    indices=ids.clamp(min=0)
    original=torch.tensor(vertices,dtype=torch.float32,device='cuda')
    positions=render.raster_interpolate(original[None],uvrast,render.pos_idx)[0][0]
    head=(positions[...,1]>.54)&occupied
    pouch=(indices>=len(meshes[0].faces))&occupied
    totals=torch.zeros((SIZE,SIZE,3),device='cuda')
    denominator=torch.zeros((SIZE,SIZE,1),device='cuda')
    frontal_color=torch.zeros_like(totals)
    frontal_weight=torch.zeros((SIZE,SIZE),device='cuda')
    _, welded_index=np.unique(np.round(vertices,7),axis=0,return_inverse=True)
    welded_index=torch.tensor(welded_index,device='cuda',dtype=torch.long)
    counts=[]
    views=[(0,0),(0,180),(0,90),(0,270),(45,0),(45,180),(-35,0),(-35,180)]
    tiles=[]
    for file in [PARENT/'painted-sheet.png',PARENT/'tilted/painted-sheet.png']:
        sheet=Image.open(file).convert('RGB');w,h=sheet.size
        for i in range(4):
            tiles.append(np.array(sheet.crop(((i%2)*w//2,(i//2)*h//2,
                (i%2+1)*w//2,(i//2+1)*h//2)),dtype=np.float32)/255)
    for i,((elev,azim),tile) in enumerate(zip(views,tiles)):
        camera,clip=render.get_pos_from_mvp(elev,azim,None,None)
        rast,_=render.raster_rasterize(clip,render.pos_idx,[2048,2048])
        depth=render.raster_interpolate(camera[None,:,:3],rast,render.pos_idx)[0][0,...,2]
        uv_camera=render.raster_interpolate(camera[None,:,:3],uvrast,render.pos_idx)[0][0]
        uv_clip=render.raster_interpolate(clip,uvrast,render.pos_idx)[0][0]
        grid=uv_clip[...,:2]/uv_clip[...,3:].clamp(min=1e-8)
        seen_depth=sample(depth,grid,'nearest')[...,0]
        visible=(seen_depth-uv_camera[...,2]).abs()<.003
        visible &= sample((rast[0,...,-1]>0).float(),grid,'nearest')[...,0]>.5
        tri=camera[render.pos_idx,:3]
        normals=F.normalize(torch.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0],dim=-1),dim=-1)
        cosine=(-normals[:,2])[indices].clamp(0,1)
        # Smooth only view-selection weights; keep actual mesh shading flat.
        smooth=torch.zeros((int(welded_index.max())+1,3),device='cuda')
        for corner in range(3):
            smooth.index_add_(0,welded_index[render.pos_idx[:,corner].long()],normals)
        smooth=F.normalize(smooth,dim=-1)[welded_index]
        smooth=render.raster_interpolate(smooth[None],uvrast,render.pos_idx)[0][0]
        smooth_cos=(-F.normalize(smooth,dim=-1)[...,2]).clamp(0,1)
        color=sample(torch.tensor(tile,device='cuda'),grid)
        foreground=distance_transform_edt(tile.min(axis=-1)<.91)>2.0
        visible &= sample(torch.tensor(foreground,dtype=torch.float32,device='cuda'),grid)[...,0]>.999
        visible &= occupied & (cosine>.12)
        weight=(smooth_cos**6)*visible*(1.0 if i<4 else .6)
        totals+=color*weight[...,None]
        denominator+=weight[...,None]
        if i==0:
            frontal_color=color.clone()
            # Full frontal authority over eyes/nose/mouth; blend gently into
            # side views across the temples and sides of the beard.
            frontal_weight=((smooth_cos-.35)/.35).clamp(0,1)*visible
            frontal_weight=frontal_weight**2*(3-2*frontal_weight)
        counts.append({'view':[elev,azim],'covered_texels':int(visible.sum())})
        print('Projected',i,counts[-1],flush=True)
    texture=totals/denominator.clamp(min=1e-8)
    blend=frontal_weight[...,None]
    face_color=frontal_color*blend+texture*(1-blend)
    texture[head]=face_color[head]
    known=occupied & (denominator[...,0]>1e-8)

    # Map the rebuilt pouch to the leather panel in the existing frontal
    # painting. Avoid sampling the shirt/hand that surrounded the old shell.
    x=positions[...,0];y=positions[...,1]
    px=249+(x+.284)/.127*15
    py=282+(.13-y)/.21*38
    pouch_grid=torch.stack([px/(tiles[0].shape[1]-1)*2-1,
                            py/(tiles[0].shape[0]-1)*2-1],dim=-1)
    pouch_color=sample(torch.tensor(tiles[0],device='cuda'),pouch_grid)
    texture[pouch]=pouch_color[pouch];known|=pouch
    arr=texture.cpu().numpy()
    mask=occupied.cpu().numpy();valid=known.cpu().numpy()
    xyz=positions.cpu().numpy()
    # Fill genuinely unobserved surface points spatially, keeping disconnected
    # UV islands from borrowing arbitrary neighboring atlas colors.
    missing=mask & ~valid
    if missing.any():
        tree=cKDTree(xyz[valid]);_,nearest=tree.query(xyz[missing],workers=8)
        arr[missing]=arr[valid][nearest]
    # Dilate around every chart for texture filtering and lower mip levels.
    _,nearest=distance_transform_edt(~mask,return_indices=True)
    arr[~mask]=arr[nearest[0][~mask],nearest[1][~mask]]
    Image.fromarray(np.uint8(np.clip(arr*255,0,255))).save(OUT/'basecolor.png')
    Image.fromarray(np.uint8(mask)*255).save(OUT/'uv-coverage.png')
    Image.fromarray(np.uint8(valid)*255).save(OUT/'projection-coverage.png')
    report={'texture_size':SIZE,'triangles':len(faces),'occupied_texels':int(mask.sum()),
        'directly_projected_texels':int(valid.sum()),'filled_texels':int(missing.sum()),
        'coverage':float(valid.sum()/mask.sum()),'views':counts,
        'head_policy':'front view supplies central facial features, smooth transition to side coverage',
        'pouch_policy':'local mapping to leather panel from original generated frontal view',
        'seconds':round(time.monotonic()-start,2)}
    (OUT/'bake-validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=OUT)
    OUT=parser.parse_args().output.resolve()
    main()
