"""Prepare geometry guides and bake imagegen-painted views; no HY Paint model.

Image synthesis is performed separately with the built-in imagegen tool.
This script uses Hunyuan's deterministic renderer, xatlas and UV projection.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image
import torch
import torch.nn.functional as F
import trimesh
from hy3dgen.texgen.differentiable_renderer.mesh_render import MeshRender
from hy3dgen.texgen.utils.uv_warp_utils import mesh_uv_wrap

VIEWS = [(0, 0), (0, 180), (0, 90), (0, 270)]
TILTED_VIEWS = [(45,0),(45,180),(-35,0),(-35,180)]

def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def renderer(mesh, size=768):
    render = MeshRender(default_resolution=size, texture_size=2048, device='cuda')
    render.load_mesh(mesh)
    return render

def prepare(args):
    if args.output.exists() and any(args.output.iterdir()):
        raise ValueError('Output must be new or empty')
    args.output.mkdir(parents=True, exist_ok=True)
    mesh = trimesh.load(args.mesh, force='mesh', process=False)
    triangles = mesh.triangles.copy()
    mesh = mesh_uv_wrap(mesh)
    if not np.allclose(mesh.triangles, triangles, atol=1e-6, rtol=0):
        raise RuntimeError('UV unwrap changed geometry')
    mesh.visual = trimesh.visual.TextureVisuals(
        uv=mesh.visual.uv, image=Image.new('RGB',(2,2),'white'))
    mesh.export(args.output / 'unwrapped.glb')
    render = renderer(mesh)
    sheet = Image.new('RGB', (1536, 1536), 'white')
    guides = args.output / 'guides'
    guides.mkdir()
    selected_views = TILTED_VIEWS if args.view_set=='tilted' else VIEWS
    for i, (elev, azim) in enumerate(selected_views):
        camera, clip = render.get_pos_from_mvp(elev, azim, None, None)
        raster, _ = render.raster_rasterize(clip, render.pos_idx, [768,768])
        ids = raster[0, ..., -1].long()
        tri = camera[render.pos_idx, :3]
        normals = F.normalize(torch.cross(tri[:,1]-tri[:,0], tri[:,2]-tri[:,0], dim=-1), dim=-1)
        light = F.normalize(torch.tensor([-.3,.5,-1.], device='cuda'), dim=0)
        shades = (0.56 + .22 * (normals @ light).clamp(0,1))
        gray = torch.ones((768,768),device='cuda')
        gray[ids>0] = shades[ids[ids>0]-1]
        pixels = (gray.cpu().numpy()[...,None].repeat(3,axis=2)*255).astype(np.uint8)
        guide = Image.fromarray(pixels)
        guide.save(guides/f'{i}.png')
        Image.fromarray(((ids>0).cpu().numpy()*255).astype(np.uint8)).save(guides/f'{i}-mask.png')
        sheet.paste(guide, ((i%2)*768,(i//2)*768))
    sheet.save(args.output/'geometry-sheet.png')
    metadata = {'source':str(args.mesh.resolve()),'source_sha256':digest(args.mesh),
                'triangles':len(mesh.faces),'texture_size':2048,'tile_size':768,
                'views':[{'elevation':e,'azimuth':a} for e,a in selected_views],
                'sheet_layout':'2x2 row-major','unwrapped_sha256':digest(args.output/'unwrapped.glb')}
    (args.output/'projection.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(json.dumps(metadata,indent=2))

def bake(args):
    start = time.monotonic()
    folder = args.output
    meta = json.loads((folder/'projection.json').read_text())
    if digest(folder/'unwrapped.glb')!=meta['unwrapped_sha256']:
        raise ValueError('Prepared UV mesh changed; regenerate the guides')
    mesh = trimesh.load(folder/'unwrapped.glb',force='mesh',process=False)
    original_triangles = mesh.triangles.copy()
    render = renderer(mesh,1024)
    # Upstream's four-pixel erosion can discard nearly all pixels on narrow
    # low-poly details (pouch edges, fingers); retain more valid observations.
    render.bake_unreliable_kernel_size = 1
    destination = args.bake_output or folder
    destination.mkdir(parents=True,exist_ok=True)
    if (destination/'03-imagegen-textured.glb').exists():
        raise ValueError('Baked mesh already exists; choose a new --bake-output folder')
    views_dir = destination/'painted-views'
    views_dir.mkdir(exist_ok=True)
    textures, weights = [], []
    batches = [(args.sheet,meta['views'],1.0)]
    if args.extra_sheet:
        extra=json.loads((args.extra_sheet.parent/'projection.json').read_text())
        if extra['source_sha256']!=meta['source_sha256']:
            raise ValueError('Extra views reference a different mesh')
        batches.append((args.extra_sheet,extra['views'],0.75))
    for batch,(sheet_path,views,weight) in enumerate(batches):
        sheet = Image.open(sheet_path).convert('RGB')
        width,height = sheet.size
        if width != height:
            raise ValueError('Expected a square 2x2 painted sheet')
        for i,view in enumerate(views):
            x,y = i%2,i//2
            tile = sheet.crop((x*width//2,y*height//2,(x+1)*width//2,(y+1)*height//2))
            tile = tile.resize((1024,1024),Image.Resampling.LANCZOS)
            tile.save(views_dir/f'{batch*4+i}.png')
            texture,cosine,_ = render.back_project(tile,view['elevation'],view['azimuth'])
            textures.append(texture)
            weights.append(weight*cosine**6)
    texture,mask = render.fast_bake_texture(textures,weights)
    mask_np = (mask[...,0].cpu().numpy()*255).astype(np.uint8)
    Image.fromarray(mask_np).save(destination/'projection-mask.png')
    filled = render.uv_inpaint(texture,mask_np)
    render.set_texture(Image.fromarray(filled))
    result = render.save_mesh()
    result.visual.material.image.save(destination/'basecolor.png')
    path = destination/'03-imagegen-textured.glb'
    result.export(path)
    loaded = trimesh.load(path,force='mesh',process=False)
    if not np.allclose(loaded.triangles,original_triangles,atol=1e-6,rtol=0):
        raise RuntimeError('Export changed geometry')
    if loaded.visual.kind!='texture':
        raise RuntimeError('Missing embedded texture')
    embedded = getattr(loaded.visual.material,'baseColorTexture',None)
    if embedded is None or embedded.size!=(2048,2048):
        raise RuntimeError('Embedded texture has wrong dimensions')
    if not np.isfinite(loaded.visual.uv).all():
        raise RuntimeError('Invalid texture coordinates')
    meta.update({'painted_sheet':str(args.sheet.resolve()),'painted_sheet_sha256':digest(args.sheet),
                 'output':str(path.resolve()),'output_sha256':digest(path),
                 'output_triangles':len(loaded.faces),'bake_seconds':round(time.monotonic()-start,2),
                 'synthesis':'built-in imagegen; no Hunyuan Paint inference',
                 'extra_sheet':str(args.extra_sheet.resolve()) if args.extra_sheet else None,
                 'extra_sheet_sha256':digest(args.extra_sheet) if args.extra_sheet else None,
                 'view_count':sum(len(views) for _,views,_ in batches),
                 'projection':'angle-weighted multiview projection with geometry-aware UV filling'})
    (destination/'texture.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(meta,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['prepare','bake'])
    parser.add_argument('--mesh',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--sheet',type=Path)
    parser.add_argument('--extra-sheet',type=Path)
    parser.add_argument('--bake-output',type=Path)
    parser.add_argument('--view-set',choices=['cardinal','tilted'],default='cardinal')
    args=parser.parse_args()
    if args.mode=='prepare' and args.mesh is None:
        parser.error('prepare requires --mesh')
    if args.mode=='bake' and args.sheet is None:
        parser.error('bake requires --sheet')
    with torch.inference_mode():
        (prepare if args.mode=='prepare' else bake)(args)
