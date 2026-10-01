"""Isolated HY knob audit; preserve latent samples and share the API GPU lock."""
import argparse,fcntl,json,os,sys,time,hashlib,gc
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'scripts'))
from generate import load_pipeline,MODEL_DIRS,sha256
p=argparse.ArgumentParser()
p.add_argument('label');p.add_argument('--model',default='mv',choices=MODEL_DIRS)
p.add_argument('--source',choices=['processed','original'],default='processed')
p.add_argument('--steps',type=int,default=50);p.add_argument('--guidance',type=float,default=5)
p.add_argument('--seed',type=int,default=12345)
p.add_argument('--resolutions',type=int,nargs='+',default=[384])
p.add_argument('--decoder',choices=['hierarchical','vanilla'],default='hierarchical')
p.add_argument('--chunks',type=int,default=4096)
p.add_argument('--views',nargs='+',default=['front','left','back','right'])
p.add_argument('--latent-from',type=Path)
p.add_argument('--levels',type=float,nargs='+',default=[0])
a=p.parse_args();out=OUT/a.label;out.mkdir(exist_ok=False)
source=ROOT/('assets/makima-geometry-review/dense/result/views' if a.source=='processed' else 'var/api/jobs/a1faf1d3c76a48e093344a8875d7445c/inputs')
record={'args':vars(a).copy(),'status':'running','outputs':[]}
record['args']['latent_from']=str(a.latent_from) if a.latent_from else None
record['model_info']=json.loads((MODEL_DIRS[a.model]/'model-info.json').read_text())
def save(): (out/'trial.json').write_text(json.dumps(record,indent=2)+'\n')
save()
with (Path.home()/'.cache/shape-gen/gpu.lock').open('a') as lock:
 print('Waiting for shared GPU lock',flush=True);fcntl.flock(lock,fcntl.LOCK_EX)
 import torch,numpy as np
 from PIL import Image
 from hy3dgen.shapegen.models.autoencoders.volume_decoders import VanillaVolumeDecoder
 from hierarchical_decoder import HierarchicalVolumeDecoding
 from hy3dgen.shapegen.pipelines import export_to_trimesh
 from hy3dgen.shapegen.models.autoencoders.surface_extractors import MCSurfaceExtractor
 torch.set_num_threads(6);torch.cuda.reset_peak_memory_stats();start=time.monotonic();hooks=[]
 try:
  views=a.views if a.model=='mv' else ['front']
  images={v:Image.open(source/f'{v}.png').convert('RGBA') for v in views}
  record['input_hashes']={v:sha256(source/f'{v}.png') for v in views}
  pipeline,hooks=load_pipeline(MODEL_DIRS[a.model])
  with torch.inference_mode():
   if a.latent_from:
    latent=torch.load(a.latent_from,map_location='cuda',weights_only=True)
   else:
    latent=pipeline(image=images if a.model=='mv' else images['front'],num_inference_steps=a.steps,
      guidance_scale=a.guidance,generator=torch.Generator(device='cpu').manual_seed(a.seed),
      output_type='latent',mc_algo='mc',enable_pbar=True)
   torch.save(latent.cpu(),out/'latent.pt')
   decoded=pipeline.vae(latent/pipeline.vae.scale_factor)
   decoder=HierarchicalVolumeDecoding() if a.decoder=='hierarchical' else VanillaVolumeDecoder()
   for res in a.resolutions:
    print(f'EXTRACT {a.label} {res} {a.decoder}',flush=True)
    grid=decoder(decoded,pipeline.vae.geo_decoder,bounds=1.01,num_chunks=a.chunks,
        mc_level=0,octree_resolution=res,enable_pbar=True)
    for level in a.levels:
     mesh=export_to_trimesh(MCSurfaceExtractor()(grid,bounds=1.01,mc_level=level,octree_resolution=res))[0]
     if mesh is None:raise RuntimeError('Extraction failed')
     name=f'r{res}-iso{level:g}.glb';mesh.export(out/name)
     counts=np.bincount(mesh.edges_unique_inverse)
     item={'file':name,'vertices':len(mesh.vertices),'triangles':len(mesh.faces),'watertight':bool(mesh.is_watertight),
       'winding_consistent':bool(mesh.is_winding_consistent),'boundary_edges':int((counts==1).sum()),
       'nonmanifold_edges':int((counts>2).sum()),'sha256':sha256(out/name)}
     record['outputs'].append(item);save();print(json.dumps(item),flush=True)
    del grid;gc.collect();torch.cuda.empty_cache()
  record['status']='complete'
 except Exception as e:
  record.update(status='failed',error=repr(e));raise
 finally:
  record.update(elapsed_seconds=time.monotonic()-start,peak_allocated_mib=torch.cuda.max_memory_allocated()/2**20,
    peak_reserved_mib=torch.cuda.max_memory_reserved()/2**20)
  save()
  for hook in hooks:hook.offload()
  torch.cuda.empty_cache()
  print(json.dumps(record),flush=True)
