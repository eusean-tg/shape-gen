"""CPU-only model input preparation and numeric output validation; no Blender."""
import argparse
import json
from pathlib import Path

import numpy as np
import trimesh


def prepare_rig(source, directory):
    with np.load(source, allow_pickle=False) as data:
        vertices = data['vertices'].astype(np.float32)
        faces = data['faces'].astype(np.int64)
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    target = directory / 'data/peasant'
    target.mkdir(parents=True)
    np.savez(target / 'raw_data.npz', vertices=vertices, faces=faces,
             vertex_normals=mesh.vertex_normals.astype(np.float32),
             face_normals=mesh.face_normals.astype(np.float32), joints=None, skin=None,
             parents=None, names=None, matrix_local=None, tails=None, no_skin=None, path=None, cls=None)
    (directory / 'data/inference.txt').write_text('peasant\n')
    lo, hi = vertices.min(0), vertices.max(0)
    report = {'vertices': len(vertices), 'triangles': len(faces),
              'normalization_center': ((lo + hi) / 2).tolist(),
              'normalization_half_extent': float(max(hi - lo) / 2),
              'coordinates': 'Blender world Z-up, forward -Y; supplied by consumer'}
    (directory / 'input.json').write_text(json.dumps(report, indent=2) + '\n')


def validate(kind, source):
    report = {'status': 'passed', 'visual_acceptance': 'pending', 'kind': kind}
    if kind == 'mesh':
        mesh = trimesh.load(source, force='mesh', process=False)
        assert len(mesh.vertices) >= 4 and len(mesh.faces) >= 2, 'Empty mesh'
        assert np.isfinite(mesh.vertices).all(), 'Nonfinite mesh coordinates'
        assert mesh.faces.min() >= 0 and mesh.faces.max() < len(mesh.vertices)
        report.update(vertices=len(mesh.vertices), triangles=len(mesh.faces),
                      watertight=bool(mesh.is_watertight), winding_consistent=bool(mesh.is_winding_consistent),
                      has_uv=getattr(mesh.visual, 'uv', None) is not None)
        counts = np.bincount(mesh.edges_unique_inverse)
        report.update(boundary_edges=int((counts == 1).sum()), nonmanifold_edges=int((counts > 2).sum()),
                      bounds=mesh.bounds.tolist(),
                      validation_scope='Finite geometry and valid indices; topology measurements are descriptive, not acceptance thresholds')
    else:
        with np.load(source, allow_pickle=False) as archive:
            data = {key: archive[key] for key in archive.files}
        assert all(a.dtype.kind != 'O' for a in data.values()), 'Object arrays forbidden'
        assert all(np.isfinite(a).all() for a in data.values() if a.dtype.kind in 'fc'), 'Nonfinite arrays'
        report['arrays'] = {key: list(value.shape) for key, value in data.items()}
        if kind == 'rig-data':
            joints, parents, weights = data['joints'], data['parents'], data['weights']
            n = len(joints)
            assert joints.shape == data['tails'].shape == (n, 3)
            assert parents.shape == (n,) and data['names'].shape == (n,)
            assert len(set(data['names'].tolist())) == n
            assert np.all((parents >= -1) & (parents < n)) and np.any(parents == -1)
            for start in range(n):
                seen = set()
                while start != -1:
                    assert start not in seen, 'Cyclic skeleton'
                    seen.add(start)
                    start = int(parents[start])
            assert weights.shape == (len(data['vertices']), n)
            assert weights.min() >= 0 and np.max(np.abs(weights.sum(1) - 1)) < 1e-5
            assert np.max((weights > 0).sum(1)) <= 4
            report.update(bones=n, vertices=len(weights), max_influences=4,
                          bone_names='generic; consumer must review and map semantic names',
                          coordinate_system='input Blender world Z-up, forward -Y')
        elif kind == 'motion':
            rotations = data['rotations']
            assert rotations.shape == (1, 120, 22, 3, 3)
            assert np.max(np.abs(rotations @ rotations.swapaxes(-1, -2) - np.eye(3))) < 1e-4
            assert np.max(np.abs(np.linalg.det(rotations) - 1)) < 1e-4
            report.update(fps=30, frames=120, rotation_joints=22, retargeted=False, looped=False)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare-rig', 'mesh', 'rig-data', 'motion'])
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.command == 'prepare-rig':
        prepare_rig(args.source, args.output)
    else:
        result = validate(args.command, args.source)
        args.output.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result), flush=True)
