"""Check exported docs, immutable source bundles and Git storage policy together."""
import hashlib
import json
from pathlib import Path
import subprocess
import types
import zipfile

import pytest

from scripts.shape_api_client import unpack_helper
from scripts.sync_api_handoff import SOURCES, sync
from scripts.motion_diagnostics import diagnose
from test_motion_diagnostics import motion

ROOT = Path(__file__).resolve().parents[1]


def ignored(path):
    return subprocess.run(['git', 'check-ignore', '--no-index', '-q', str(path)], cwd=ROOT).returncode == 0


def test_api_handoff_matches_sources_and_complete_checksums():
    assert sync(ROOT, check=True) == []
    directory = ROOT / 'exports/shape-gen-api'
    entries = dict(line.split('  ', 1)[::-1] for line in (directory / 'SHA256SUMS').read_text().splitlines())
    assert set(entries) == set(SOURCES) | {'README.md'}
    for name, digest in entries.items():
        assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == digest


def test_handoff_check_rejects_drift_without_rewriting(tmp_path):
    directory = tmp_path / 'exports/shape-gen-api'
    directory.mkdir(parents=True)
    (directory / 'README.md').write_text('Consumer guide')
    for source in SOURCES.values():
        path = tmp_path / source
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('canonical ' + source)
    sync(tmp_path)
    path = tmp_path / SOURCES['geometry-experiments.md']
    path.write_text('new geometry guide')
    old = (directory / 'SHA256SUMS').read_bytes()
    with pytest.raises(ValueError, match='geometry-experiments.md'):
        sync(tmp_path, check=True)
    assert (directory / 'SHA256SUMS').read_bytes() == old
    sync(tmp_path)
    assert sync(tmp_path, check=True) == []


def test_every_advertised_helper_is_git_eligible_and_verifiable(tmp_path):
    releases = sorted((ROOT / 'exports/blender-helpers').glob('*/release.json'))
    assert releases
    for release in releases:
        entry = json.loads(release.read_text())
        directory = release.parent
        for name in ('release.json', 'manifest.json', 'bundle.zip'):
            path = directory / name
            assert path.is_file(), path
            assert not ignored(path), path  # A clone must include the advertised download.
        assert (directory / 'bundle.zip').stat().st_size < 1024 * 1024  # Small source bundles only.
        report = unpack_helper(entry, (directory / 'manifest.json').read_bytes(),
                               (directory / 'bundle.zip').read_bytes(), tmp_path / entry['version'])
        assert report['verified_files'] >= 8


def has_geometry(value):
    if isinstance(value, dict):
        if isinstance(value.get('vertices'), list) and isinstance(value.get('faces'), list):
            return True
        return any(has_geometry(v) for v in value.values())
    if isinstance(value, list):
        return any(has_geometry(v) for v in value)
    return False


def test_generated_geometry_is_ignored_but_reports_remain_eligible():
    assert ignored('assets/example/source-mesh.json')
    assert ignored('assets/example/mesh.json')
    assert ignored('assets/example/01-dense.glb')
    assert ignored('assets/example/archive.zip')
    assert not ignored('assets/example/generation.json')
    eligible = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
                                       cwd=ROOT, text=True).split('\0')
    for name in eligible:
        if name.startswith('assets/') and name.endswith('.json'):
            assert not has_geometry(json.loads((ROOT / name).read_text())), name


def test_diagnostic_description_update_preserves_calculations():
    # The old published analyzer is immutable; compare numerical output directly.
    with zipfile.ZipFile(ROOT / 'exports/blender-helpers/1.0.0/bundle.zip') as archive:
        source = archive.read('scripts/motion_diagnostics.py').decode()
    old = types.ModuleType('published_diagnostics_v100')
    exec(compile(source, 'published_diagnostics_v100', 'exec'), old.__dict__)
    data = motion(speed=1, cyclic=True)
    data['transl'][0, 75:, 2] = data['transl'][0, 75, 2]  # Travel, then stop.
    before, after = old.diagnose(data), diagnose(data)
    assert before['schema_version'] == after['schema_version'] == '1.0.0'
    assert before.pop('diagnostic_version') == '1.0.0'
    assert after.pop('diagnostic_version') == '1.0.1'
    before['speed_over_time'].pop('smoothing')
    after['speed_over_time'].pop('smoothing')
    assert before == after
