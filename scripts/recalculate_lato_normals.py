"""CPU-only winding correction for a fresh LATO.2 result; preserve raw artifacts."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import trimesh


def measurements(mesh):
    counts = np.bincount(mesh.edges_unique_inverse)
    return {'vertices': len(mesh.vertices), 'triangles': len(mesh.faces),
            'winding_consistent': bool(mesh.is_winding_consistent),
            'watertight': bool(mesh.is_watertight),
            'boundary_edges': int((counts == 1).sum()),
            'nonmanifold_edges': int((counts > 2).sum())}


def recalculate(directory):
    source = directory / '02-lato2.glb'
    raw = directory / '02-lato2-raw.glb'
    raw_obj = directory / '02-lato2-raw.obj'
    report_path = directory / 'normal-recalculation.json'
    if any(path.exists() for path in [raw, raw_obj, report_path]):
        raise FileExistsError('Normal recalculation requires a fresh result; raw artifacts already exist')
    original_bytes = source.read_bytes()
    mesh = trimesh.load(source, force='mesh', process=False)
    vertices, faces = mesh.vertices.copy(), mesh.faces.copy()
    before = measurements(mesh)
    mesh.fix_normals(multibody=True)
    after = measurements(mesh)
    # Winding may change. Geometry, face membership and vertex indexing may not.
    if not np.array_equal(vertices, mesh.vertices) or not np.array_equal(
            np.sort(faces, axis=1), np.sort(mesh.faces, axis=1)):
        raise RuntimeError('Normal recalculation unexpectedly changed geometry/connectivity')
    corrected_bytes = mesh.export(file_type='glb')
    corrected_obj = mesh.export(file_type='obj')
    obj = directory / '02-lato2.obj'
    if not obj.is_file():
        raise FileNotFoundError('Missing source LATO.2 OBJ')
    raw.write_bytes(original_bytes)
    raw_obj.write_bytes(obj.read_bytes())
    source.write_bytes(corrected_bytes)
    obj.write_text(corrected_obj)
    report = {'status': 'complete', 'method': 'trimesh.fix_normals(multibody=True)',
              'trimesh_version': trimesh.__version__, 'before': before, 'after': after,
              'faces_flipped': int(np.any(faces != mesh.faces, axis=1).sum()),
              'geometry_and_connectivity_preserved': True,
              'raw_sha256': hashlib.sha256(original_bytes).hexdigest(),
              'corrected_sha256': hashlib.sha256(corrected_bytes).hexdigest(),
              'visual_acceptance': 'pending',
              'limitations': 'Consistent winding is not proof of correct outside orientation on open/nonmanifold surfaces. No hole filling, overlap removal or nonmanifold repair is performed.'}
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    recalculate(parser.parse_args().directory)
