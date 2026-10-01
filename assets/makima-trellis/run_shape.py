"""Original TRELLIS, geometry-only, with staged GPU inference and CPU FlexiCubes."""
import argparse,fcntl,gc,hashlib,json,os,subprocess,sys,time
from contextlib import nullcontext
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];REPO=ROOT/'third_party/TRELLIS'
MODEL=ROOT/'models/trellis/TRELLIS-image-large'
os.environ.setdefault('ATTN_BACKEND','xformers');os.environ.setdefault('SPARSE_ATTN_BACKEND','xformers')
os.environ.setdefault('SPARSE_BACKEND','spconv');os.environ.setdefault('SPCONV_ALGO','native')
os.environ.setdefault('PYTORCH_CUDA_ALLOC_CONF','expandable_segments:True')
sys.path.insert(0,str(REPO))
def digest(f):
 h=hashlib.sha256()
 with Path(f).open('rb') as stream:
  for block in iter(lambda:stream.read(4*1024*1024),b''):h.update(block)
 return h.hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--views',nargs='+',default=['front'],choices=['front','left','back','right'])
 p.add_argument('--steps',type=int,default=25);p.add_argument('--seed',type=int,default=12345)
 p.add_argument('--mode',choices=['stochastic','multidiffusion'],default='stochastic')
 p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--resume-shape',type=Path)
 a=p.parse_args();out=a.output_dir.resolve()
 if out.exists() and any(out.iterdir()):p.error('Use an empty/new output folder.')
 out.mkdir(parents=True,exist_ok=True)
 sources={v:ROOT/f'assets/makima-geometry-review/dense/result/views/{v}.png' for v in a.views}
 record={'status':'waiting','model':'Original TRELLIS-image-large (not TRELLIS.2)',
  'args':{k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()},
  'upstream_commit':subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD'],text=True).strip(),
  'input_hashes':{v:digest(f) for v,f in sources.items()},'stages':[],
  'memory_strategy':'GPU stage offload; original dense-grid FlexiCubes extraction on CPU',
  'postprocessing':'axis conversion only; no hole filling, smoothing, or wrapping',
  'checkpoint_manifest':json.loads((ROOT/'models/trellis/download-manifest.json').read_text())}
 def save():(out/'experiment.json').write_text(json.dumps(record,indent=2)+'\n')
 save()
 with (Path.home()/'.cache/shape-gen/gpu.lock').open('a') as lock:
  print('Waiting for shared GPU lock',flush=True);fcntl.flock(lock,fcntl.LOCK_EX)
  import torch,numpy as np,trimesh
  from PIL import Image
  from torchvision import transforms
  from safetensors.torch import load_file
  from trellis import models
  from trellis.pipelines import TrellisImageTo3DPipeline,samplers
  from trellis.modules import sparse as sp
  from trellis.models.structured_latent_vae import decoder_mesh
  original_extractor=decoder_mesh.SparseFeatures2Mesh
  class CPUExtractor(original_extractor):
   def __init__(self,*args,**kwargs):
    kwargs['device']='cpu';super().__init__(*args,**kwargs)
   def __call__(self,x,training=False):return super().__call__(x.cpu(),training=training)
  decoder_mesh.SparseFeatures2Mesh=CPUExtractor
  class StagedPipeline(TrellisImageTo3DPipeline):
   @property
   def device(self):return torch.device('cuda')
  torch.set_num_threads(8);started=time.monotonic();record.update(status='running',gpu=torch.cuda.get_device_name(),torch=torch.__version__)
  config=json.loads((MODEL/'pipeline.json').read_text())['args']
  pipeline=StagedPipeline();pipeline.models={};pipeline.rembg_session=None
  pipeline.image_cond_model_transform=transforms.Normalize(mean=[.485,.456,.406],std=[.229,.224,.225])
  for key in ['sparse_structure_sampler','slat_sampler']:
   c=config[key];setattr(pipeline,key,getattr(samplers,c['name'])(**c['args']));setattr(pipeline,key+'_params',c['params'])
  pipeline.slat_normalization=config['slat_normalization']
  def load(name):
   print('Loading',name,flush=True);path=MODEL/config['models'][name];c=json.loads(path.with_suffix('.json').read_text())
   model=getattr(models,c['name'])(**c['args']);model.load_state_dict(load_file(str(path.with_suffix('.safetensors'))),strict=True)
   pipeline.models[name]=model.eval().requires_grad_(False);return model
  def drop(*names):
   for name in names:
    if name in pipeline.models:pipeline.models.pop(name).cpu()
   gc.collect();torch.cuda.empty_cache()
  def stage(name,fn):
   print('STAGE',name,flush=True);torch.cuda.reset_peak_memory_stats();t=time.monotonic()
   value=fn();torch.cuda.synchronize()
   record['stages'].append({'name':name,'seconds':round(time.monotonic()-t,2),
    'peak_allocated_mib':round(torch.cuda.max_memory_allocated()/2**20,1),
    'peak_reserved_mib':round(torch.cuda.max_memory_reserved()/2**20,1)})
   save();return value
  def ctx(name):
   return pipeline.inject_sampler_multi_image(name,len(a.views),a.steps,mode=a.mode) if len(a.views)>1 else nullcontext()
  try:
   with torch.inference_mode():
    if a.resume_shape:
     data=torch.load(a.resume_shape,weights_only=True,map_location='cuda');slat=sp.SparseTensor(feats=data['feats'],coords=data['coords'])
    else:
     pipeline.models['image_cond_model']=torch.hub.load('facebookresearch/dinov2','dinov2_vitl14_reg',pretrained=True,trust_repo=True).eval().cuda()
     images=[]
     for v,f in sources.items():
      image=pipeline.preprocess_image(Image.open(f).convert('RGBA'));image.save(out/f'conditioning-{v}.png');images.append(image)
     cond=stage('image_features',lambda:{'cond':torch.cat([pipeline.get_cond([image])['cond'] for image in images])})
     cond['neg_cond']=torch.zeros_like(cond['cond'][:1]);drop('image_cond_model')
     torch.save({k:v.cpu() for k,v in cond.items()},out/'conditioning.pt')
     load('sparse_structure_flow_model').cuda();load('sparse_structure_decoder').cuda()
     torch.manual_seed(a.seed);torch.cuda.manual_seed_all(a.seed)
     with ctx('sparse_structure_sampler'):
      coords=stage('sparse_structure',lambda:pipeline.sample_sparse_structure(cond,sampler_params={'steps':a.steps}))
     torch.save(coords.cpu(),out/'coords.pt');record['sparse_tokens']=len(coords);drop('sparse_structure_flow_model','sparse_structure_decoder')
     load('slat_flow_model').cuda()
     with ctx('slat_sampler'):
      slat=stage('shape_latent',lambda:pipeline.sample_slat(cond,coords,sampler_params={'steps':a.steps}))
     torch.save({'feats':slat.feats.cpu(),'coords':slat.coords.cpu()},out/'shape-latent.pt')
     drop('slat_flow_model');del cond,coords
    def decode():
     load('slat_decoder_mesh').cuda();return pipeline.decode_slat(slat,formats=['mesh'])['mesh'][0]
    mesh=stage('mesh_decode_cpu_extraction',decode)
    v=mesh.vertices.detach().cpu().numpy();faces=mesh.faces.detach().cpu().numpy()
    if not np.isfinite(v).all():raise ValueError('Nonfinite generated vertices')
    # Same Z-up -> glTF Y-up rotation as upstream to_glb, without its postprocessing.
    v=v@np.array([[1,0,0],[0,0,-1],[0,1,0]])
    m=trimesh.Trimesh(v,faces,process=False);m.export(out/'01-dense-raw.glb');m.export(out/'01-dense-raw.ply')
    counts=np.bincount(m.edges_unique_inverse)
    record['mesh']={'vertices':len(v),'triangles':len(faces),'bounds':m.bounds.tolist(),
     'watertight':bool(m.is_watertight),'winding_consistent':bool(m.is_winding_consistent),
     'boundary_edges':int((counts==1).sum()),'nonmanifold_edges':int((counts>2).sum()),'sha256':digest(out/'01-dense-raw.glb')}
    if mesh.vertex_attrs is not None:
     colors=mesh.vertex_attrs.detach().cpu().numpy()[:,:3];m.visual.vertex_colors=(np.clip(colors,0,1)*255).astype(np.uint8);m.export(out/'01-dense-vertex-colors.glb')
    record['status']='complete'
  except Exception as e:record.update(status='failed',error=f'{type(e).__name__}: {e}');raise
  finally:
   record['elapsed_seconds']=round(time.monotonic()-started,2);save();drop(*list(pipeline.models))
if __name__=='__main__':main()
