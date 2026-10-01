"""Exercise actual mesh repair/export in the installed CPU mesh environment."""
import subprocess

from shape_api.server import ROOT


def test_normal_recalculation_preserves_geometry_and_raw_files(tmp_path):
    code = r'''
import hashlib
from pathlib import Path
import sys
import numpy as np
import trimesh
from scripts.recalculate_lato_normals import recalculate

root = Path(sys.argv[1])
box = trimesh.creation.box()
box.faces[[0, 3, 7]] = box.faces[[0, 3, 7], ::-1]
second = trimesh.creation.box()
second.apply_translation([3, 0, 0])
second.invert()
closed = trimesh.util.concatenate([box, second])
nonmanifold = trimesh.creation.box()
nonmanifold.faces = np.vstack([nonmanifold.faces, nonmanifold.faces[:1, ::-1]])

for label, mesh in [('closed', closed), ('nonmanifold', nonmanifold)]:
    directory = root / label
    directory.mkdir()
    source = directory / '02-lato2.glb'
    obj = directory / '02-lato2.obj'
    mesh.export(source)
    mesh.export(obj)
    raw_bytes, raw_obj = source.read_bytes(), obj.read_bytes()
    original = trimesh.load(source, force='mesh', process=False)
    report = recalculate(directory)
    assert (directory / '02-lato2-raw.glb').read_bytes() == raw_bytes
    assert (directory / '02-lato2-raw.obj').read_bytes() == raw_obj
    assert report['raw_sha256'] == hashlib.sha256(raw_bytes).hexdigest()
    corrected = trimesh.load(source, force='mesh', process=False)
    np.testing.assert_array_equal(original.vertices, corrected.vertices)
    np.testing.assert_array_equal(np.sort(original.faces,axis=1), np.sort(corrected.faces,axis=1))
    for key in ['vertices', 'triangles', 'boundary_edges', 'nonmanifold_edges']:
        assert report['before'][key] == report['after'][key]
    if label == 'closed':
        assert report['faces_flipped'] > 0
        assert corrected.is_winding_consistent and corrected.is_watertight
        assert all(component.volume > 0 for component in corrected.split())
    else:
        assert report['after']['nonmanifold_edges'] > 0
    try:
        recalculate(directory)
        raise AssertionError('Overwrote retained raw output')
    except FileExistsError:
        pass
'''
    result = subprocess.run([str(ROOT / '.venv/bin/python'), '-c', code, str(tmp_path)],
                            cwd=ROOT, text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
