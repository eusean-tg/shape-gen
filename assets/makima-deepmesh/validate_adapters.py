"""Check inference adapters against direct math and serializer axis roundtrip."""
from pathlib import Path
import sys,fcntl,json
r=Path(__file__).resolve().parents[2];here=Path(__file__).resolve().parent
sys.path[:0]=[str(here/'compat'),str(r/'third_party/DeepMesh')]
with (Path.home()/'.cache/shape-gen/gpu.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 import torch,numpy as np,trimesh
 from lit_gpt.fused_rotary_embedding import apply_rotary_emb_func
 from lit_gpt.rmsnorm import FusedRMSNorm
 from sft.datasets.serializaiton import serialize,deserialize
 from scipy.spatial import cKDTree
 torch.manual_seed(23)
 with torch.inference_mode():
  x=torch.randn(1,11,4,128,device='cuda',dtype=torch.bfloat16)
  angle=torch.randn(11,64,device='cuda');c=angle.cos().bfloat16();s=angle.sin().bfloat16()
  y=apply_rotary_emb_func(x.clone(),c,s,False,True)
  left=x[...,:64].float();right=x[...,64:].float();co=c[None,:,None,:].float();si=s[None,:,None,:].float()
  expected=torch.cat([left*co-right*si,left*si+right*co],dim=-1).to(x.dtype)
  torch.testing.assert_close(y,expected,rtol=.01,atol=.02)
  norm=FusedRMSNorm(128,eps=1e-5).cuda()
  norm.weight.copy_(torch.randn_like(norm.weight))
  z=norm(x)
  ref=(x.float()*torch.rsqrt(x.float().square().mean(-1,keepdim=True)+1e-5)*norm.weight).to(x.dtype)
  torch.testing.assert_close(z,ref,rtol=.01,atol=.02)
  result={'rotary_max_abs':float((y.float()-expected.float()).abs().max()),'rmsnorm_max_abs':float((z.float()-ref.float()).abs().max())}
 v=np.array([[-.6,-.2,-.1],[.4,-.2,-.1],[-.6,.8,-.1],[-.6,-.2,.3]])
 mesh=trimesh.Trimesh(v[:,[2,0,1]],[[0,2,1],[0,1,3],[0,3,2],[1,2,3]],process=False)
 decoded=deserialize(serialize(mesh).copy())[:,[1,2,0]]
 distance=float(cKDTree(v).query(decoded)[0].max())
 assert distance<np.sqrt(3)*2/512
 result.update(serializer_axis_roundtrip_max_distance=distance,status='passed')
 (here/'adapter-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
