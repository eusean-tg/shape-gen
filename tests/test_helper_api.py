import hashlib
import io
import json
from pathlib import Path
import zipfile

import numpy as np
import pytest

from test_shape_api import client, settings
from test_motion_diagnostics import motion
from scripts.build_blender_helpers import build
from scripts.shape_api_client import unpack_helper
from shape_api.server import ROOT
from shape_api.store import Store


def test_helper_auth_and_complete_verified_bundle(settings, tmp_path):
    with client(settings) as c:
        for path in ['/helpers', '/helpers/blender-helpers/1.0.0/manifest',
                     '/helpers/blender-helpers/1.0.0/download', '/clients/shape_api_client.py',
                     '/docs/motion-diagnostics.md']:
            assert c.get(path, headers={'Authorization': 'Bearer wrong'}).status_code == 401
        entry = c.get('/helpers').json()['helpers'][0]
        manifest = c.get(entry['manifest_url']).content
        archive = c.get(entry['download_url']).content
        output = tmp_path / 'downloaded'
        report = unpack_helper(entry, manifest, archive, output)
        assert report['verified_files'] >= 8
        assert (output / 'scripts/retarget_hymotion_peasant.py').read_bytes() == (ROOT / 'scripts/retarget_hymotion_peasant.py').read_bytes()
        contract = json.loads((output / 'contracts/peasant-humanoid-v1.json').read_text())
        assert contract['target_to_source_joint']['foot.L'] == 7
        assert c.get('/helpers/blender-helpers/999.0.0/download').status_code == 404
        with pytest.raises(RuntimeError, match='checksum'):
            unpack_helper(entry, manifest, archive + b'corrupt', tmp_path / 'bad')
        assert not (tmp_path / 'bad').exists()


def test_bundle_release_is_immutable(tmp_path):
    entry = build(ROOT, tmp_path, '1.0.0')
    assert build(ROOT, tmp_path, '1.0.0') == entry
    (tmp_path / '1.0.0/manifest.json').chmod(0o644)
    (tmp_path / '1.0.0/manifest.json').write_text('{}')
    with pytest.raises(RuntimeError, match='new version'):
        build(ROOT, tmp_path, '1.0.0')


def test_helper_path_traversal_even_with_matching_hashes(tmp_path):
    file = b'bad'
    manifest = {'name': 'blender-helpers', 'version': '1.0.0',
                'files': [{'name': '../outside', 'bytes': len(file), 'sha256': hashlib.sha256(file).hexdigest()}]}
    encoded = json.dumps(manifest).encode()
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('manifest.json', encoded)
        archive.writestr('../outside', file)
    data = stream.getvalue()
    entry = {'name': 'blender-helpers', 'version': '1.0.0', 'bytes': len(data),
             'sha256': hashlib.sha256(data).hexdigest(), 'manifest_sha256': hashlib.sha256(encoded).hexdigest()}
    with pytest.raises(RuntimeError, match='Unsafe'):
        unpack_helper(entry, encoded, data, tmp_path / 'bad')
    assert not (tmp_path / 'bad').exists()


def test_older_job_diagnostics_preserve_manifest(settings):
    store = Store(settings.data)
    job, _ = store.submit({'request_id': 'old-motion', 'operation': 'hymotion'})
    directory = settings.data / 'jobs' / job['id'] / 'result'
    directory.mkdir(parents=True)
    np.savez(directory / 'motion.npz', **motion(speed=1))
    original = store.update(job['id'], state='succeeded')
    store.db.close()
    with client(settings) as c:
        url = '/jobs/' + job['id'] + '/motion-diagnostics'
        assert c.get(url, headers={'Authorization': 'Bearer wrong'}).status_code == 401
        report = c.get(url).json()
        assert 'on-demand' in report['delivery']
        assert report['diagnostics']['root']['horizontal_speed']['mean'] == pytest.approx(1)
        assert c.get('/jobs/' + job['id']).json() == original
        assert not (directory / 'motion-diagnostics.json').exists()
