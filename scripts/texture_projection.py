"""Render texture guides and project fixed-camera views onto existing UVs.

Reuses Hunyuan camera/raster conventions. Geometry and UVs are never regenerated.
"""
import argparse
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt
from scipy.spatial import cKDTree
import torch
import torch.nn.functional as F
import trimesh
from hy3dgen.texgen.differentiable_renderer.mesh_render import MeshRender


def sample(image, grid, mode='bilinear'):
    if image.ndim==2:image=image[...,None]
    return F.grid_sample(image.permute(2,0,1)[None].contiguous(),grid[None],
        mode=mode,padding_mode='border',align_corners=True)[0].permute(1,2,0)


def rgb_pixels(path):
    image=Image.open(path).convert('RGBA')
    # Generated sheets may return alpha despite a white-background request.
    # Composite for sampling; foreground erosion then excludes this background.
    white=Image.new('RGBA',image.size,(255,255,255,255))
    return np.array(Image.alpha_composite(white,image).convert('RGB'),dtype=np.float32)/255


def load(path,size):
    mesh=trimesh.load(path,force='mesh',process=False)
    assert mesh.visual.uv is not None and np.isfinite(mesh.visual.uv).all()
    render=MeshRender(default_resolution=2048,texture_size=size,device='cuda')
    render.load_mesh(mesh)
    return mesh,render


def camera_for(render,view):
    camera,clip=render.get_pos_from_mvp(view['elevation'],view['azimuth'],None,None)
    if 'crop' in view:
        xmin,ymin,xmax,ymax=view['crop']
        clip=clip.clone()
        clip[...,0]=(clip[...,0]-(xmin+xmax)/2*clip[...,3])*2/(xmax-xmin)
        clip[...,1]=(clip[...,1]-(ymin+ymax)/2*clip[...,3])*2/(ymax-ymin)
    return camera,clip


@torch.inference_mode()
def guides(args):
    mesh,render=load(args.mesh,args.size)
    texture=torch.tensor(np.array(Image.open(args.texture).convert('RGB'))/255,
                         device='cuda',dtype=torch.float32)
    specs=[];sheet=Image.new('RGB',(1536,1536),'white')
    for i,(elev,azim) in enumerate([(0,0),(0,180),(0,90),(0,270)]):
        spec={'elevation':elev,'azimuth':azim,'weight':1.0,'image':f'{i}.png'}
        if args.head:
            _,fullclip=camera_for(render,spec)
            points=fullclip[0][torch.tensor(mesh.vertices[:,1]>.47,device='cuda')]
            ndc=points[:,:2]/points[:,3:]
            low=ndc.min(0).values;high=ndc.max(0).values
            center=(low+high)/2;extent=(high-low).max()*1.12
            spec['crop']=[float(center[0]-extent/2),float(center[1]-extent/2),
                          float(center[0]+extent/2),float(center[1]+extent/2)]
            spec['region']='head'
        _,clip=camera_for(render,spec)
        rast,_=render.raster_rasterize(clip,render.pos_idx,[768,768])
        uv=render.raster_interpolate(render.vtx_uv[None],rast,render.uv_idx)[0][0]
        color=sample(texture,uv*2-1)
        mask=rast[0,...,-1]>0
        color[~mask]=1
        image=Image.fromarray(np.uint8(np.clip(color.cpu().numpy()*255,0,255)))
        image.save(args.output/f'{i}.png')
        Image.fromarray(np.uint8(mask.cpu().numpy())*255).save(args.output/f'{i}-mask.png')
        sheet.paste(image,((i%2)*768,(i//2)*768));specs.append(spec)
    sheet.save(args.output/'guide-sheet.png')
    (args.output/'views.json').write_text(json.dumps(specs,indent=2)+'\n')


@torch.inference_mode()
def bake(args):
    start=time.monotonic()
    mesh,render=load(args.mesh,args.size)
    uvclip=torch.cat([render.vtx_uv*2-1,torch.ones_like(render.vtx_uv)],dim=-1)
    uvrast,_=render.raster_rasterize(uvclip,render.uv_idx,[args.size,args.size])
    ids=uvrast[0,...,-1].long()-1;occupied=ids>=0;indices=ids.clamp(min=0)
    original=torch.tensor(mesh.vertices,device='cuda',dtype=torch.float32)
    xyz=render.raster_interpolate(original[None],uvrast,render.pos_idx)[0][0]
    head=(xyz[...,1]>.54)&occupied
    total=torch.zeros((args.size,args.size,3),device='cuda')
    denom=torch.zeros((args.size,args.size),device='cuda')
    front_color=torch.zeros_like(total);front_strength=torch.zeros_like(denom)
    front_priority=torch.zeros_like(denom)
    _,welded=np.unique(np.round(mesh.vertices,7),axis=0,return_inverse=True)
    welded=torch.tensor(welded,device='cuda',dtype=torch.long)
    specs=json.loads(args.views.read_text())
    if args.extra_views:
        specs += [dict(v,image=str((args.extra_views.parent/v['image']).resolve()))
                  for v in json.loads(args.extra_views.read_text())]
    counts=[]
    has_head=any(v.get('region')=='head' for v in specs)
    for spec in specs:
        path=args.views.parent/spec['image']
        tile=rgb_pixels(path)
        camera,clip=camera_for(render,spec)
        rast,_=render.raster_rasterize(clip,render.pos_idx,[2048,2048])
        depth=render.raster_interpolate(camera[None,:,:3],rast,render.pos_idx)[0][0,...,2]
        uv_camera=render.raster_interpolate(camera[None,:,:3],uvrast,render.pos_idx)[0][0]
        uv_clip=render.raster_interpolate(clip,uvrast,render.pos_idx)[0][0]
        grid=uv_clip[...,:2]/uv_clip[...,3:].clamp(min=1e-8)
        visible=(sample(depth,grid,'nearest')[...,0]-uv_camera[...,2]).abs()<.003
        visible &= sample((rast[0,...,-1]>0).float(),grid,'nearest')[...,0]>.5
        visible &= (grid.abs()<=1).all(dim=-1)&occupied
        tri=camera[render.pos_idx,:3]
        normals=F.normalize(torch.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0],dim=-1),dim=-1)
        cosine=(-normals[:,2])[indices].clamp(0,1)
        smooth=torch.zeros((int(welded.max())+1,3),device='cuda')
        for j in range(3):smooth.index_add_(0,welded[render.pos_idx[:,j].long()],normals)
        smooth=F.normalize(smooth,dim=-1)[welded]
        normalmap=render.raster_interpolate(smooth[None],uvrast,render.pos_idx)[0][0]
        smooth_cos=(-F.normalize(normalmap,dim=-1)[...,2]).clamp(0,1)
        foreground=distance_transform_edt(tile.min(axis=-1)<.94)>args.erosion
        visible &= sample(torch.tensor(foreground,device='cuda',dtype=torch.float32),grid)[...,0]>.999
        visible &= cosine>.12
        if spec.get('region')=='head':visible &= head
        elif has_head:visible &= ~head
        color=sample(torch.tensor(tile,device='cuda'),grid)
        weight=smooth_cos**6*visible*spec.get('weight',1.0)
        total+=color*weight[...,None];denom+=weight
        if args.front_head and spec['elevation']==0 and spec['azimuth']==0:
            priority=2 if spec.get('region')=='head' else 1
            take=visible&(priority>front_priority)
            strength=((smooth_cos-.35)/.35).clamp(0,1)
            strength=strength**2*(3-2*strength)
            front_color[take]=color[take];front_strength[take]=strength[take]
            front_priority[take]=priority
        counts.append({'image':str(path),'covered_texels':int(visible.sum())})
    texture=total/denom[...,None].clamp(min=1e-8)
    blend=front_strength[...,None]
    texture[head]=(front_color*blend+texture*(1-blend))[head]
    arr=texture.cpu().numpy();mask=occupied.cpu().numpy();known=(occupied&(denom>1e-8)).cpu().numpy()
    missing=mask&~known
    if args.fallback:
        fallback=np.array(Image.open(args.fallback).convert('RGB'),dtype=np.float32)/255
        assert fallback.shape==arr.shape
        arr[missing]=fallback[missing]
        arr[known]=arr[known]*args.strength+fallback[known]*(1-args.strength)
    elif missing.any():
        positions=xyz.cpu().numpy()
        _,nearest=cKDTree(positions[known]).query(positions[missing],workers=8)
        arr[missing]=arr[known][nearest]
    _,nearest=distance_transform_edt(~mask,return_indices=True)
    arr[~mask]=arr[nearest[0][~mask],nearest[1][~mask]]
    output=Image.fromarray(np.uint8(np.clip(arr*255,0,255)))
    output.save(args.output/'basecolor.png')
    Image.fromarray(np.uint8(known)*255).save(args.output/'projection-mask.png')
    before=mesh.triangles.copy();uv=mesh.visual.uv.copy()
    mesh.visual=trimesh.visual.TextureVisuals(uv=uv,image=output)
    mesh.export(args.output/'textured.glb')
    loaded=trimesh.load(args.output/'textured.glb',force='mesh',process=False)
    assert np.array_equal(loaded.triangles,before)
    assert np.allclose(loaded.visual.uv[loaded.faces],uv[mesh.faces],atol=1e-7,rtol=0)
    report={'mesh':str(args.mesh.resolve()),'views':counts,'triangles':len(mesh.faces),
        'geometry_unchanged':True,'uvs_unchanged':True,'coverage':float(known.sum()/mask.sum()),
        'unobserved_texels':int(missing.sum()),'fallback':str(args.fallback) if args.fallback else None,
        'restyle_strength':args.strength,'seconds':round(time.monotonic()-start,2)}
    (args.output/'projection.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['guides','bake'])
    parser.add_argument('--mesh',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--size',type=int,default=2048)
    parser.add_argument('--texture',type=Path)
    parser.add_argument('--views',type=Path)
    parser.add_argument('--extra-views',type=Path)
    parser.add_argument('--head',action='store_true')
    parser.add_argument('--front-head',action='store_true')
    parser.add_argument('--fallback',type=Path)
    parser.add_argument('--strength',type=float,default=1.0)
    parser.add_argument('--erosion',type=float,default=1.0)
    args=parser.parse_args()
    if args.mode=='guides' and args.texture is None:parser.error('guides needs --texture')
    if args.mode=='bake' and args.views is None:parser.error('bake needs --views')
    args.output.mkdir(parents=True,exist_ok=True)
    target=args.output/('guide-sheet.png' if args.mode=='guides' else 'basecolor.png')
    if target.exists():raise FileExistsError(target)
    (guides if args.mode=='guides' else bake)(args)
