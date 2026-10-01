"""Content-addressed inputs with bounded, non-executable format validation."""
import json
from pathlib import Path
import shutil
import struct
import warnings
import zipfile

import numpy as np
from PIL import Image

from .store import now
from .worker import sha256

MAX_UPLOAD = 64 * 1024 * 1024


def inspect_upload(path):
    with Path(path).open('rb') as stream:
        magic = stream.read(12)
    if magic.startswith(b'\x89PNG\r\n\x1a\n') or magic.startswith(b'\xff\xd8\xff'):
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(path) as im:
                if not 16 <= min(im.size) or max(im.size) > 4096 or im.width * im.height > 16_777_216:
                    raise ValueError('Images must be 16–4096 pixels per side')
                size, fmt = im.size, im.format
                im.verify()
            with Image.open(path) as im:
                lo, hi = im.convert('RGBA').getextrema()[3]
        return {'kind': 'image', 'extension': '.png' if fmt == 'PNG' else '.jpg', 'dimensions': size,
                'has_foreground_alpha': lo < 255 and hi > 127}
    if magic.startswith(b'glTF'):
        data = Path(path).read_bytes()
        if len(data) < 20:
            raise ValueError('Truncated GLB')
        _, version, size, chunk_size, chunk_type = struct.unpack_from('<IIIII', data)
        if version != 2 or size != len(data) or chunk_type != 0x4E4F534A or 20 + chunk_size > len(data):
            raise ValueError('Invalid GLB 2.0 header')
        gltf = json.loads(data[20:20 + chunk_size])
        if not gltf.get('meshes'):
            raise ValueError('GLB must contain a mesh')
        if gltf.get('skins') or gltf.get('animations'):
            raise ValueError('Model operations take a static mesh; export the rest mesh without rig/actions')
        for item in gltf.get('buffers', []) + gltf.get('images', []):
            if 'uri' in item:
                raise ValueError('GLB resources must be embedded in bufferViews, not URI references')
        if gltf.get('extensionsRequired'):
            raise ValueError('Export an uncompressed GLB without required extensions')
        counts = [a.get('count', 0) for a in gltf.get('accessors', [])]
        if any(not isinstance(n, int) or n < 0 or n > 3_000_000 for n in counts):
            raise ValueError('GLB accessor exceeds mesh limits')
        return {'kind': 'mesh', 'extension': '.glb', 'coordinate_system': 'glTF Y-up',
                'has_uv': any('TEXCOORD_0' in p.get('attributes', {}) for m in gltf['meshes'] for p in m.get('primitives', []))}
    if magic.startswith(b'PK'):
        with zipfile.ZipFile(path) as z:
            if len(z.infolist()) > 8 or sum(i.file_size for i in z.infolist()) > 128 * 1024 * 1024:
                raise ValueError('Numeric mesh archive exceeds expanded-size limits')
        with np.load(path, allow_pickle=False) as arrays:
            if set(arrays.files) != {'vertices', 'faces'}:
                raise ValueError('Mesh NPZ must contain exactly vertices and faces; no pickle/object data')
            v, f = arrays['vertices'], arrays['faces']
            if v.ndim != 2 or v.shape[1] != 3 or not 4 <= len(v) <= 200_000 or v.dtype.kind not in 'fi':
                raise ValueError('Expected 4–200000 finite XYZ vertices')
            if f.ndim != 2 or f.shape[1] != 3 or not 2 <= len(f) <= 400_000 or f.dtype.kind not in 'iu':
                raise ValueError('Expected 2–400000 integer triangle indices')
            if not np.isfinite(v).all() or f.min() < 0 or f.max() >= len(v) or np.ptp(v, axis=0).max() <= 1e-6:
                raise ValueError('Invalid coordinates or triangle indices')
        return {'kind': 'mesh-data', 'extension': '.npz', 'vertices': len(v), 'triangles': len(f),
                'coordinate_system': 'Blender world Z-up, forward -Y; caller must supply these axes'}
    raise ValueError('Supported uploads are PNG/JPEG, static self-contained GLB, or numeric vertices/faces NPZ')


def register_file(store, data_dir, path, metadata, source_job=None):
    digest = sha256(path)
    existing = store.asset(digest)
    if existing:
        return existing
    target = Path(data_dir) / 'objects' / digest
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, target)
    target.chmod(0o444)
    return store.add_asset({'id': digest, 'sha256': digest, 'bytes': target.stat().st_size,
                            'path': str(target.relative_to(data_dir)), 'created_at': now(),
                            'source_job': source_job, **metadata})


def public_asset(record):
    return {k: v for k, v in record.items() if k != 'path'}
