"""Download only official geometry checkpoints, pin revisions and verify hashes."""
import os,json,hashlib
os.environ['HF_HUB_DISABLE_XET']='1'
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from huggingface_hub import HfApi,hf_hub_download
root=Path(__file__).resolve().parents[2];out=root/'models/trellis';out.mkdir(exist_ok=True)
specs={'microsoft/TRELLIS-image-large':['pipeline.json']+[f'ckpts/{stem}.{ext}' for stem in ['ss_dec_conv3d_16l8_fp16','ss_flow_img_dit_L_16l8_fp16','slat_dec_mesh_swin8_B_64l8m256c_fp16','slat_flow_img_dit_L_64l8p2_fp16'] for ext in ['json','safetensors']]}
manifest={};tasks=[]
for repo,files in specs.items():
 info=HfApi().model_info(repo,files_metadata=True);manifest[repo]={'revision':info.sha,'files':{}}
 for f in info.siblings:
  if f.rfilename in files:tasks.append((repo,info.sha,f))
def get(task):
 repo,rev,info=task
 print('Downloading',repo,info.rfilename,info.size,flush=True)
 path=Path(hf_hub_download(repo,info.rfilename,revision=rev,local_dir=out/repo.split('/')[-1]))
 with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest() if hasattr(hashlib,'file_digest') else None
 if digest is None:
  h=hashlib.sha256()
  with path.open('rb') as stream:
   for block in iter(lambda:stream.read(4*1024*1024),b''):h.update(block)
  digest=h.hexdigest()
 if info.lfs:assert digest==info.lfs.sha256,(path,digest)
 print('Verified',info.rfilename,flush=True)
 return repo,info.rfilename,{'sha256':digest,'bytes':path.stat().st_size,'path':str(path)}
with ThreadPoolExecutor(max_workers=2) as pool:
 for repo,name,record in pool.map(get,tasks):
  manifest[repo]['files'][name]=record
  (out/'download-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
