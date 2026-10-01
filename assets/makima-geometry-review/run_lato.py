"""Run the upstream LATO experiment under the API's advisory GPU lock."""
import fcntl
import json
import os
from pathlib import Path
import runpy
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
os.environ.setdefault('SPARSE_ATTN_BACKEND', 'xformers')
os.environ.setdefault('PYTORCH_CUDA_ALLOC_CONF', 'expandable_segments:True')
os.environ.setdefault('OMP_NUM_THREADS', '6')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '6')
os.environ.setdefault('EGL_PLATFORM', 'surfaceless')
os.environ.setdefault('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}')
upstream = ROOT / 'third_party/LATO.2'
script = Path(os.environ.get('LATO_SCRIPT', str(upstream / 'scripts/e2e_inference.py')))
target = os.environ.get('LATO_TARGET', '1200')
label = os.environ.get('LATO_LABEL', 'lato-1200')
sys.path.insert(0, str(upstream))
sys.argv = [str(script), '--mesh_dir', str(OUT / 'lato-input'),
            '--out_dir', str(OUT / label), '--vert_num', target,
            '--batch_size', '1', '--num_workers', '0', '--seed', '12345']
if os.environ.get('LATO_FILL_QUAD_RINGS', '1') == '0':
    sys.argv.append('--no-fill_quad_rings')
lockpath = Path.home() / '.cache/shape-gen/gpu.lock'
lockpath.parent.mkdir(parents=True, exist_ok=True)
with lockpath.open('a') as lock:
    print('Waiting for shared GPU lock', flush=True)
    fcntl.flock(lock, fcntl.LOCK_EX)
    print('Acquired shared GPU lock', flush=True)
    import torch
    torch.set_num_threads(6)
    torch.cuda.reset_peak_memory_stats()
    start = time.monotonic()
    result = {'argv': sys.argv, 'script': str(script), 'success': False}
    try:
        runpy.run_path(str(script), run_name='__main__')
        result['success'] = (OUT / label / 'makima_pred.obj').exists()
    except Exception:
        result['error'] = traceback.format_exc()
        raise
    finally:
        result.update(elapsed_seconds=time.monotonic()-start,
                      peak_allocated_mib=torch.cuda.max_memory_allocated()/2**20,
                      peak_reserved_mib=torch.cuda.max_memory_reserved()/2**20)
        (OUT / f'{label}-run.json').write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(result), flush=True)
