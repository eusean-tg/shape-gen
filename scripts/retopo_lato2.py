"""LATO.2 mesh adapter. Preserve input scale/axes; retain native predictions privately."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import time

from experimental_common import gpu_lock, restore_lato_vertices

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT / 'third_party/LATO.2'
os.environ.setdefault('SPARSE_ATTN_BACKEND', 'xformers')
os.environ.setdefault('PYTORCH_CUDA_ALLOC_CONF', 'expandable_segments:True')
os.environ.setdefault('OMP_NUM_THREADS', '6')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '6')
os.environ.setdefault('EGL_PLATFORM', 'surfaceless')
os.environ.setdefault('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mesh', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=12345)
    parser.add_argument('--target-vertices', type=int, default=1200)
    parser.add_argument('--vertex-steps', type=int, default=24)
    parser.add_argument('--topology-steps', type=int, default=50)
    parser.add_argument('--guidance', type=float, default=3.0)
    parser.add_argument('--fill-quad-rings', action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()
    source, out = args.mesh.resolve(strict=True), args.output_dir.resolve()
    if out.exists() and any(out.iterdir()):
        parser.error('Output directory must be new or empty')
    out.mkdir(parents=True, exist_ok=True)
    record = {'status': 'waiting', 'input_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'args': {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
              'upstream_commit': subprocess.check_output(['git', '-C', str(REPO), 'rev-parse', 'HEAD'], text=True).strip(),
              'visual_acceptance': 'pending', 'normalization': 'upstream bbox center and max extent; restored to input coordinates',
              'target_note': 'Vertex density conditioning, not an exact count or triangle limit'}
    start = time.monotonic()
    try:
        with gpu_lock():
            import numpy as np
            import torch
            import trimesh
            torch.set_num_threads(6)
            torch.cuda.reset_peak_memory_stats()
            mesh = trimesh.load(source, force='mesh', process=False)
            center, extent = mesh.bounds.mean(axis=0), float(mesh.extents.max())
            if not np.isfinite(mesh.vertices).all() or extent <= 1e-7:
                raise ValueError('Invalid or degenerate source mesh')
            inputs = out / 'native-input'
            inputs.mkdir()
            # A material-free OBJ avoids reusing consumer texture paths upstream.
            trimesh.Trimesh(mesh.vertices, mesh.faces, process=False).export(inputs / 'input.obj')
            native = out / 'native-output'
            script = ROOT / 'scripts/lato2_inference.py'
            sys.path.insert(0, str(REPO))
            sys.argv = [str(script), '--mesh_dir', str(inputs), '--out_dir', str(native),
                        '--vert_num', str(args.target_vertices), '--vflow_steps', str(args.vertex_steps),
                        '--tflow_steps', str(args.topology_steps), '--cfg_strength', str(args.guidance),
                        '--batch_size', '1', '--num_workers', '0', '--seed', str(args.seed)]
            if not args.fill_quad_rings:
                sys.argv.append('--no-fill_quad_rings')
            record['status'] = 'running'
            runpy.run_path(str(script), run_name='__main__')
            # Upstream can exit zero after skipping a failed/empty mesh.
            prediction = native / 'input_pred.obj'
            if not prediction.is_file():
                raise RuntimeError('LATO.2 produced no mesh topology; inspect preprocessing/generation logs')
            result = trimesh.load(prediction, force='mesh', process=False)
            if len(result.faces) < 2 or not np.isfinite(result.vertices).all():
                raise ValueError('Empty or nonfinite LATO.2 prediction')
            result.vertices = restore_lato_vertices(result.vertices, center, extent)
            result.export(out / '02-lato2.glb')
            result.export(out / '02-lato2.obj')
            render = native / 'input_render.png'
            if render.exists():
                shutil.copyfile(render, out / 'conditioning.png')
            counts = np.bincount(result.edges_unique_inverse)
            record.update(status='complete', vertices=len(result.vertices), triangles=len(result.faces),
                          normalization_center=center.tolist(), normalization_extent=extent,
                          boundary_edges=int((counts == 1).sum()), nonmanifold_edges=int((counts > 2).sum()),
                          watertight=bool(result.is_watertight), winding_consistent=bool(result.is_winding_consistent),
                          peak_allocated_mib=round(torch.cuda.max_memory_allocated() / 2**20, 1))
    except Exception as error:
        record.update(status='failed', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        record['elapsed_seconds'] = round(time.monotonic() - start, 2)
        (out / 'lato2.json').write_text(json.dumps(record, indent=2) + '\n')
        print(json.dumps(record, indent=2), flush=True)


if __name__ == '__main__':
    main()
