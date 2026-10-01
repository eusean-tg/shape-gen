"""Official TRELLIS.2 geometry-only experiment, staged offload and saved intermediates.

Use .venv-trellis2/bin/python. DINOv3 access must be granted by its publisher.
The existing Makima cutout supplies alpha; no new segmentation model is needed.
"""
import argparse,fcntl,gc,hashlib,json,os,subprocess,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
REPO=ROOT/'third_party/TRELLIS.2'
MODEL_ROOT=ROOT/'models/trellis2'
DINO_REPO='facebook/dinov3-vitl16-pretrain-lvd1689m'
DINO_REV='ea8dc2863c51be0a264bab82070e3e8836b02d51'
os.environ.setdefault('ATTN_BACKEND','xformers')
os.environ.setdefault('SPARSE_ATTN_BACKEND','xformers')
os.environ.setdefault('SPARSE_CONV_BACKEND','flex_gemm')
os.environ.setdefault('PYTORCH_CUDA_ALLOC_CONF','expandable_segments:True')
os.environ.setdefault('HF_HUB_DISABLE_XET','1')
sys.path.insert(0,str(REPO))

def digest(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for chunk in iter(lambda:f.read(4*1024*1024),b''):h.update(chunk)
 return h.hexdigest()

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--image',type=Path,default=ROOT/'assets/makima-geometry-review/dense/result/views/front.png')
 p.add_argument('--output-dir',type=Path,required=True)
 p.add_argument('--seed',type=int,default=12345)
 p.add_argument('--steps',type=int,default=12)
 p.add_argument('--resolution',type=int,choices=[512,1024],default=512)
 p.add_argument('--encoder-path',type=Path,default=MODEL_ROOT/'dinov3-vitl16')
 p.add_argument('--resume-shape',type=Path,help='Resume decoding a saved shape-latent.pt without loading image/flow models.')
 a=p.parse_args();out=a.output_dir.resolve()
 if out.exists() and any(out.iterdir()):p.error('Output folder must be new or empty.')
 if not 1<=a.steps<=100:p.error('steps must be 1–100')
 if not a.resume_shape:
  from huggingface_hub import snapshot_download
  if not (a.encoder_path/'model.safetensors').exists():
   print('Checking authorized DINOv3 access; downloading official encoder if available.',flush=True)
   snapshot_download(DINO_REPO,revision=DINO_REV,allow_patterns=['config.json','model.safetensors'],local_dir=a.encoder_path)
  # Require the official checkpoint, whether downloaded here or supplied locally.
  from huggingface_hub import HfApi
  info=HfApi().model_info(DINO_REPO,revision=DINO_REV,files_metadata=True)
  expected=next(f.lfs.sha256 for f in info.siblings if f.rfilename=='model.safetensors')
  if digest(a.encoder_path/'model.safetensors')!=expected:raise ValueError('DINOv3 checkpoint hash mismatch')
 out.mkdir(parents=True,exist_ok=True)
 record={'status':'waiting','args':{k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()},
  'upstream_commit':subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD'],text=True).strip(),
  'resolution':a.resolution,'stages':[],'input_sha256':digest(a.image),
  'image_conditioning':'single-view; native crop/black composite using existing Hunyuan RGBA cutout',
  'texture_generation':False,'postprocessing':'none on raw mesh',
  'checkpoint_manifest':json.loads((MODEL_ROOT/'download-manifest.json').read_text())}
 def save():(out/'experiment.json').write_text(json.dumps(record,indent=2)+'\n')
 save()
 with (Path.home()/'.cache/shape-gen/gpu.lock').open('a') as lock:
  print('Waiting for shared GPU lock',flush=True);fcntl.flock(lock,fcntl.LOCK_EX)
  import numpy as np,torch,trimesh
  from PIL import Image
  from safetensors.torch import load_file
  from trellis2 import models
  from trellis2.pipelines import Trellis2ImageTo3DPipeline
  from trellis2.pipelines import samplers
  from trellis2.modules.image_feature_extractor import DinoV3FeatureExtractor
  from trellis2.modules.sparse import SparseTensor
  torch.set_num_threads(6);torch.cuda.reset_peak_memory_stats();started=time.monotonic()
  record.update(status='running',gpu=torch.cuda.get_device_name(),torch=torch.__version__);save()
  config=json.loads((MODEL_ROOT/'TRELLIS.2-4B/pipeline.json').read_text())['args']
  def load(name):
   source=config['models'][name]
   path=MODEL_ROOT/'TRELLIS-image-large'/source.split('microsoft/TRELLIS-image-large/')[1] if source.startswith('microsoft/') else MODEL_ROOT/'TRELLIS.2-4B'/source
   spec=json.loads(path.with_suffix('.json').read_text())
   print('Loading',name,flush=True)
   model=getattr(models,spec['name'])(**spec['args'])
   check=model.load_state_dict(load_file(str(path.with_suffix('.safetensors'))),strict=False)
   # Upstream loading is non-strict. Only allow its deterministically constructed
   # positional buffer, never silently accept absent learned parameters.
   if set(check.missing_keys)-{'rope_phases'} or check.unexpected_keys:
    raise ValueError(f'Checkpoint mismatch: {check}')
   record.setdefault('load_checks',{})[name]={'missing_derived_buffers':check.missing_keys,'unexpected_keys':check.unexpected_keys}
   return model.eval().requires_grad_(False)
  def stage(name,fn):
   print('STAGE',name,flush=True);t=time.monotonic();torch.cuda.reset_peak_memory_stats()
   result=fn();torch.cuda.synchronize()
   record['stages'].append({'name':name,'seconds':round(time.monotonic()-t,2),
    'peak_allocated_mib':round(torch.cuda.max_memory_allocated()/2**20,1),
    'peak_reserved_mib':round(torch.cuda.max_memory_reserved()/2**20,1)})
   save();gc.collect();torch.cuda.empty_cache();return result
  pipeline=None
  try:
   with torch.inference_mode():
    needed=['shape_slat_decoder'] if a.resume_shape else ['sparse_structure_flow_model','sparse_structure_decoder','shape_slat_flow_model_512','shape_slat_decoder']
    if a.resolution==1024 and not a.resume_shape:needed.append('shape_slat_flow_model_1024')
    loaded={name:load(name) for name in needed}
    ss=config['sparse_structure_sampler'];ss_sampler=getattr(samplers,ss['name'])(**ss['args'])
    sh=config['shape_slat_sampler'];sh_sampler=getattr(samplers,sh['name'])(**sh['args'])
    pipeline=Trellis2ImageTo3DPipeline(models=loaded,sparse_structure_sampler=ss_sampler,
     shape_slat_sampler=sh_sampler,sparse_structure_sampler_params=ss['params'],
     shape_slat_sampler_params=sh['params'],shape_slat_normalization=config['shape_slat_normalization'],
     low_vram=True,default_pipeline_type='512')
    pipeline.cuda()
    if a.resume_shape:
     data=torch.load(a.resume_shape,map_location='cuda',weights_only=True)
     slat=SparseTensor(feats=data['feats'],coords=data['coords'])
    else:
     pipeline.image_cond_model=DinoV3FeatureExtractor(str(a.encoder_path))
     image=Image.open(a.image).convert('RGBA')
     if image.getextrema()[3][0]==255:raise ValueError('Supply a foreground RGBA cutout; automatic segmentation is deliberately not loaded.')
     image=pipeline.preprocess_image(image);image.save(out/'conditioning.png')
     cond=stage('image_features',lambda:pipeline.get_cond([image],512))
     high_cond=stage('image_features_1024',lambda:pipeline.get_cond([image],1024)) if a.resolution==1024 else None
     pipeline.image_cond_model=None;gc.collect();torch.cuda.empty_cache()
     torch.save({k:v.cpu() for k,v in cond.items()},out/'conditioning.pt')
     torch.manual_seed(a.seed);torch.cuda.manual_seed_all(a.seed)
     coords=stage('sparse_structure',lambda:pipeline.sample_sparse_structure(cond,32,sampler_params={'steps':a.steps}))
     torch.save(coords.cpu(),out/'coords.pt');record['sparse_tokens']=len(coords)
     if a.resolution==512:
      slat=stage('shape_latent',lambda:pipeline.sample_shape_slat(cond,loaded['shape_slat_flow_model_512'],coords,sampler_params={'steps':a.steps}))
     else:
      slat,_=stage('shape_latent_cascade',lambda:pipeline.sample_shape_slat_cascade(cond,high_cond,
       loaded['shape_slat_flow_model_512'],loaded['shape_slat_flow_model_1024'],512,1024,coords,sampler_params={'steps':a.steps}))
     torch.save({'feats':slat.feats.cpu(),'coords':slat.coords.cpu()},out/'shape-latent.pt')
     del cond,high_cond,coords
    meshes,subs=stage('shape_decode',lambda:pipeline.decode_shape_slat(slat,a.resolution))
    mesh=meshes[0];v=mesh.vertices.detach().cpu().numpy();f=mesh.faces.detach().cpu().numpy()
    if not np.isfinite(v).all():raise ValueError('Decoder produced nonfinite vertices')
    trimesh.Trimesh(v,f,process=False).export(out/'01-dense-native-z-up.ply')
    # Match upstream o_voxel.postprocess.to_glb axis conversion, with no remeshing.
    v=v@np.array([[1,0,0],[0,0,-1],[0,1,0]])
    m=trimesh.Trimesh(v,f,process=False);m.export(out/'01-dense-raw.ply');m.export(out/'01-dense-raw.glb')
    record['postprocessing']='Z-up to glTF Y-up axis rotation only; no smoothing, hole filling or wrapping'
    counts=np.bincount(m.edges_unique_inverse)
    record['mesh']={'vertices':len(v),'triangles':len(f),'bounds':m.bounds.tolist(),
     'watertight':bool(m.is_watertight),'winding_consistent':bool(m.is_winding_consistent),
     'boundary_edges':int((counts==1).sum()),'nonmanifold_edges':int((counts>2).sum()),
     'sha256':digest(out/'01-dense-raw.glb')}
    record['status']='complete'
  except Exception as e:
   record.update(status='failed',error=f'{type(e).__name__}: {e}');raise
  finally:
   record['elapsed_seconds']=round(time.monotonic()-started,2);save()
   if pipeline:
    for model in pipeline.models.values():model.cpu()
   torch.cuda.empty_cache()

if __name__=='__main__':main()
