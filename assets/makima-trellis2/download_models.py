"""Download only official geometry checkpoints, pin revisions and verify hashes."""
import os,json,hashlib
os.environ['HF_HUB_DISABLE_XET']='1'
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from huggingface_hub import HfApi,hf_hub_download
root=Path(__file__).resolve().parents[2];out=root/'models/trellis2';out.mkdir(exist_ok=True)
specs={'microsoft/TRELLIS.2-4B':['pipeline.json']+[f'ckpts/{stem}.{ext}' for stem in ['ss_flow_img_dit_1_3B_64_bf16','slat_flow_img2shape_dit_1_3B_512_bf16','slat_flow_img2shape_dit_1_3B_1024_bf16','shape_dec_next_dc_f16c32_fp16'] for ext in ['json','safetensors']], 'microsoft/TRELLIS-image-large':[f'ckpts/ss_dec_conv3d_16l8_fp16.{e}' for e in ['json','safetensors']]}
revisions={'microsoft/TRELLIS.2-4B':'af44b45f2e35a493886929c6d786e563ec68364d','microsoft/TRELLIS-image-large':'25e0d31ffbebe4b5a97464dd851910efc3002d96'}
manifest={};tasks=[]
for repo,files in specs.items():
 info=HfApi().model_info(repo,revision=revisions[repo],files_metadata=True);manifest[repo]={'revision':info.sha,'files':{}}
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
