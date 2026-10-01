"""Small shared utilities for experimental model runners; no model imports."""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path


@contextmanager
def gpu_lock():
    # API parent holds the flock across all stages. Reacquiring here deadlocks.
    if os.environ.get('SHAPE_GEN_GPU_LOCK_HELD') == '1':
        yield
        return
    path = Path.home() / '.cache/shape-gen/gpu.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as lock:
        print('Waiting for shared GPU lock', flush=True)
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def require_cutout(path):
    from PIL import Image
    with Image.open(path) as image:
        lo, hi = image.convert('RGBA').getextrema()[3]
        if lo == 255 or hi <= 127:
            raise ValueError('TRELLIS requires a foreground RGBA cutout with transparent background and visible foreground; remove the background on the consumer first.')


def restore_lato_vertices(vertices, center, extent):
    """Undo upstream bbox normalization without fitting/deforming the result."""
    return vertices * extent + center
