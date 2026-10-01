"""Run pinned upstream inference with local configs and memory/runtime accounting."""
import argparse
import json
import os
from pathlib import Path
import resource
import runpy
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('stage',choices=['skeleton','skin'])
parser.add_argument('--seed',type=int,default=12345)
parser.add_argument('--asset-dir',type=Path,default=ROOT/'assets/peasant-unirig')
parser.add_argument('--config-dir',type=Path,default=ROOT/'config/unirig')
args=parser.parse_args()
ASSET=args.asset_dir.resolve()
CONFIG=args.config_dir.resolve()
os.environ.setdefault('HF_HUB_OFFLINE','1')
os.environ.setdefault('WANDB_MODE','disabled')
os.environ.setdefault('OMP_NUM_THREADS','6')
os.environ.setdefault('OPENBLAS_NUM_THREADS','6')
os.environ.setdefault('PYTORCH_CUDA_ALLOC_CONF','expandable_segments:True')
# Checkpoints are the official downloaded, hash-verified Lightning checkpoints.
os.environ.setdefault('TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD','1')
repo=ROOT/'third_party/UniRig'
os.chdir(repo);sys.path.insert(0,str(repo))
import torch
torch.set_num_threads(6)
torch.cuda.reset_peak_memory_stats()
# Upstream catches generation exceptions and returns an empty list; preserve a
# useful traceback so OOM/compatibility failures cannot look like success.
from src.system.ar import ARSystem
ARSystem.predict_step=ARSystem._predict_step
started=time.monotonic()
report={'stage':args.stage,'seed':args.seed,'status':'running'}
sys.argv=[str(repo/'run.py'),'--task',str(CONFIG/f'{args.stage}.yaml'),'--seed',str(args.seed)]
try:
    runpy.run_path(str(repo/'run.py'),run_name='__main__')
    output=ASSET/'data/peasant'/('predict_skeleton.npz' if args.stage=='skeleton' else 'predict_skin.npz')
    if not output.exists():raise RuntimeError(f'Missing expected inference output: {output}')
    report['status']='complete';report['output']=str(output)
except BaseException as e:
    report['status']='failed';report['error']=repr(e)
    raise
finally:
    report.update(seconds=time.monotonic()-started,
        peak_cuda_allocated_mib=torch.cuda.max_memory_allocated()/2**20,
        peak_cuda_reserved_mib=torch.cuda.max_memory_reserved()/2**20,
        peak_process_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    path=ASSET/f'{args.stage}-run.json'
    path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)
