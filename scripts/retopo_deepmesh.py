"""Bounded, staged DeepMesh inference using official weights and sampler semantics."""
import argparse, fcntl, gc, hashlib, json, os, subprocess, sys, time
from pathlib import Path
from experimental_common import gpu_lock, require_cutout
ROOT=Path(__file__).resolve().parents[1]
HERE=Path(__file__).resolve().parent
REPO=ROOT/'third_party/DeepMesh'
os.environ.setdefault('PYTORCH_CUDA_ALLOC_CONF','expandable_segments:True')
sys.path[:0]=[str(HERE/'deepmesh_compat'),str(REPO)]

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for chunk in iter(lambda:f.read(4*1024*1024),b''):h.update(chunk)
 return h.hexdigest()

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('mesh',type=Path)
 p.add_argument('--output-dir',type=Path,required=True)
 p.add_argument('--seed',type=int,default=12345)
 p.add_argument('--temperature',type=float,default=.5)
 p.add_argument('--max-tokens',type=int,default=30000)
 p.add_argument('--max-seconds',type=float,default=900)
 a=p.parse_args();source=a.mesh.resolve(strict=True);out=a.output_dir.resolve()
 if out.exists() and any(out.iterdir()):p.error('Output directory must be new or empty')
 manifest=json.loads((ROOT/'models/deepmesh/manifest.json').read_text())
 checkpoint=ROOT/manifest['path']
 if sha(checkpoint)!=manifest['sha256']:raise ValueError('Checkpoint checksum mismatch')
 out.mkdir(parents=True,exist_ok=True)
 record=dict(status='waiting',input=str(source),input_sha256=sha(source),checkpoint=manifest,
  args={k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()},
  upstream_commit=subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD'],text=True).strip(),
  adaptations=['Point encoder staged before generator; FP32 weights, BF16 autocast as upstream',
   'Rotary and RMSNorm use FlashAttention Triton kernels instead of standalone CUDA extensions',
   'Batch one; no DDP; saved point cloud; bounded runtime; require EOS for completed mesh'])
 def save():(out/'trial.json').write_text(json.dumps(record,indent=2)+'\n')
 save()
 with gpu_lock():
  import numpy as np, torch, trimesh
  from lit_gpt.model_cache import GPTCache,Config
  from sft.datasets.serializaiton import deserialize
  torch.set_num_threads(4);start=time.monotonic();torch.cuda.reset_peak_memory_stats()
  record.update(status='running',gpu=torch.cuda.get_device_name(),torch=torch.__version__);save()
  try:
   m=trimesh.load(source,force='mesh',process=False)
   center=m.bounds.mean(axis=0);extent=float(m.extents.max())
   norm=m.copy();norm.vertices=(m.vertices-center)*1.9/extent
   # Official OBJ sampling: 50k area samples -> 16,384, XYZ permuted to ZXY.
   points,faces=trimesh.sample.sample_surface(norm,50000,seed=a.seed)
   cloud=np.concatenate([points[:,[2,0,1]],norm.face_normals[faces][:,[2,0,1]]],axis=1)
   rng=np.random.default_rng(a.seed);cloud=cloud[rng.choice(50000,16384,replace=False)].astype(np.float16)
   np.save(out/'input-points.npy',cloud)
   record.update(input_triangles=len(m.faces),normalization_center=center.tolist(),normalization_extent=extent,
     cloud_sha256=hashlib.sha256(cloud.tobytes()).hexdigest(),point_count=len(cloud))
   torch.manual_seed(a.seed);torch.cuda.manual_seed_all(a.seed)
   config=Config.from_name('Diff_LLaMA_551M');config.padded_vocab_size=4738;config.block_size=270000
   os.chdir(REPO)
   print('Constructing CPU model and strictly loading checkpoint',flush=True)
   model=GPTCache(config).eval().requires_grad_(False)
   state=torch.load(checkpoint,map_location='cpu',weights_only=True,mmap=True)
   model.load_state_dict(state,strict=True);del state
   record['strict_checkpoint_load']=True;record['parameters']=sum(x.numel() for x in model.parameters())
   conditioner=model.conditioner;model.conditioner=None
   with torch.inference_mode():
    print('Encoding surface points',flush=True)
    conditioner.cuda()
    with torch.autocast('cuda',dtype=torch.bfloat16):
     encoded=conditioner(pc=torch.from_numpy(cloud).unsqueeze(0).cuda()).cpu()
    torch.cuda.synchronize();record['encoder_peak_mib']=round(torch.cuda.max_memory_allocated()/2**20,1)
    conditioner.cpu();del conditioner;gc.collect();torch.cuda.empty_cache()
    model.cuda()
    with torch.autocast('cuda',dtype=torch.bfloat16):model.cond_embeds=model.norm(model.linear(encoded.cuda()))
    del encoded;gc.collect();torch.cuda.empty_cache()
    prompt=torch.tensor([[4736]],device='cuda',dtype=torch.long)
    ended=False;generation=time.monotonic();record['generator_resident_mib']=round(torch.cuda.memory_allocated()/2**20,1);save()
    print('Generating',record['generator_resident_mib'],'MiB resident',flush=True)
    for cur_pos in range(1,a.max_tokens+1):
     if time.monotonic()-generation>a.max_seconds:break
     s=4500+((cur_pos-9001)//4500)*4500 if cur_pos>=9001 and (cur_pos-9001)%4500==0 else cur_pos-1
     input_pos=torch.arange(cur_pos,device='cuda')
     with torch.autocast('cuda',dtype=torch.bfloat16):
      logits=model(prompt[:,s:cur_pos],pc=None,start=s,window_size=9000,input_pos=input_pos)[:,-1]
     # Official Gumbel sampling, including its temperature convention.
     logits=logits.to(torch.float64)
     noise=(-torch.log(torch.rand_like(logits,dtype=torch.float64)))**a.temperature
     token=torch.argmax(logits.exp()/noise,dim=-1,keepdim=True)
     prompt=torch.cat([prompt,token],dim=-1)
     if token.item()==4737:ended=True;break
     if cur_pos%500==0:print(f'{cur_pos} tokens, {time.monotonic()-generation:.1f}s, peak {torch.cuda.max_memory_allocated()/2**20:.0f} MiB',flush=True)
    torch.cuda.synchronize()
    codes=prompt[0,1:].cpu().numpy();np.save(out/'codes.npy',codes)
    record.update(tokens=len(codes),ended_with_eos=ended,generation_seconds=round(time.monotonic()-generation,2))
    if not ended:raise RuntimeError('Bound reached without EOS; tokens saved, no completed mesh')
    v=deserialize(codes[:-1].copy())
    if not np.isfinite(v).all() or len(v)%3:raise ValueError('Invalid decoded geometry')
    # Preserve upstream output coordinates for inspection; restore Y-up below.
    native=trimesh.Trimesh(v[:,[2,1,0]],np.arange(len(v)).reshape(-1,3),process=False)
    native.export(out/'02-deepmesh-upstream-coordinates.ply')
    # Learned decoder returns source XYZ despite ZXY point conditioning.
    # Validated against source via discrete axis diagnostics; no fitted deformation.
    v=v*(extent/1.9)+center
    result=trimesh.Trimesh(v,np.arange(len(v)).reshape(-1,3),process=False)
    result.merge_vertices();result.update_faces(result.unique_faces());result.update_faces(result.nondegenerate_faces());result.remove_unreferenced_vertices();result.fix_normals()
    result.export(out/'02-deepmesh.glb');result.export(out/'02-deepmesh.obj')
    count=np.bincount(result.edges_unique_inverse)
    record.update(status='complete',output_triangles=len(result.faces),output_vertices=len(result.vertices),
      bounds=result.bounds.tolist(),watertight=bool(result.is_watertight),winding_consistent=bool(result.is_winding_consistent),
      boundary_edges=int((count==1).sum()),nonmanifold_edges=int((count>2).sum()),
      connected_components=len(result.split(only_watertight=False)),output_sha256=sha(out/'02-deepmesh.glb'),
      output_coordinate_transform='decoder XYZ, undo normalization; upstream reverse-axis copy also saved')
  except Exception as e:
   record.update(status='failed',error=f'{type(e).__name__}: {e}');raise
  finally:
   record.update(elapsed_seconds=round(time.monotonic()-start,2),peak_allocated_mib=round(torch.cuda.max_memory_allocated()/2**20,1),peak_reserved_mib=round(torch.cuda.max_memory_reserved()/2**20,1));save()
   print(json.dumps(record,indent=2),flush=True)

if __name__=='__main__':main()
