import io
import json
import struct

import numpy as np
from PIL import Image
import pytest

from test_shape_api import client, settings
from shape_api.assets import inspect_upload
from shape_api.model_jobs import commands
from shape_api.operations import MODELS
from shape_api.server import ROOT
from scripts.experimental_common import gpu_lock, require_cutout, restore_lato_vertices


def upload(c, data):
    return c.post('/assets', content=data, headers={'Content-Type': 'application/octet-stream'})


def png():
    stream = io.BytesIO()
    Image.new('RGB', (32, 32), 'white').save(stream, format='PNG')
    return stream.getvalue()


def test_model_contracts_and_durable_assets(settings):
    with settings.gpu_lock.open('a') as lock:
        import fcntl
        fcntl.flock(lock, fcntl.LOCK_EX)
        with client(settings) as c:
            assert c.get('/operations', headers={'Authorization': 'Bearer wrong'}).status_code == 401
            assert c.get('/docs/blender-handoff.md', headers={'Authorization': 'Bearer wrong'}).status_code == 401
            assert 'local Blender handoffs' in c.get('/docs/blender-handoff.md').text
            catalog = c.get('/operations').json()['operations']
            assert {o['name'] for o in catalog} == set(MODELS)
            assert all(not o['runs_blender'] for o in catalog)
            asset = upload(c, png()).json()
            assert asset['kind'] == 'image' and 'path' not in asset
            assert upload(c, png()).json()['deduplicated']
            assert c.get('/assets/' + asset['id'] + '/content').content == png()
            request = {'request_id': 'shape', 'operation': 'hunyuan-shape',
                       'inputs': {'front': asset['id']}, 'parameters': {}}
            job = c.post('/jobs', json=request)
            assert job.status_code == 202
            assert job.json()['request']['parameters']['model'] == 'mini'
            assert c.post('/jobs', json=request).status_code == 200
            assert c.post('/jobs', json={**request, 'parameters': {'seed': 2}}).status_code == 409
            for changes in [
                {'inputs': {}}, {'inputs': {'front': 'unknown'}},
                {'parameters': {'model': 'mv'}}, {'parameters': {'steps': True}},
                {'parameters': {'output_dir': '/tmp/injected'}},
                {'operation': 'bpt-retopology', 'inputs': {'mesh': asset['id']}},
                {'profile': 'teal-v1'},
            ]:
                assert c.post('/jobs', json={**request, **changes}).status_code == 422
            assert c.post('/jobs', json={'request_id': 'motion', 'operation': 'hymotion',
                                        'parameters': {'prompt': '   '}}).status_code == 422
            c.post('/jobs/' + job.json()['id'] + '/cancel')
        with client(settings) as c:
            assert c.get('/assets/' + asset['id']).json()['sha256'] == asset['id']
            assert c.get('/assets/' + asset['id'] + '/content').content == png()


def test_numeric_uploads_reject_pickle_and_bad_indices(settings):
    vertices = np.array([[0., 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]])
    faces = np.array([[0, 1, 2], [0, 2, 3]])
    with client(settings) as c:
        for value, expected in [(vertices, 200), (vertices.astype(object), 422)]:
            buffer = io.BytesIO()
            np.savez(buffer, vertices=value, faces=faces)
            response = upload(c, buffer.getvalue())
            assert response.status_code == expected
        buffer = io.BytesIO()
        np.savez(buffer, vertices=vertices, faces=faces + 100)
        assert upload(c, buffer.getvalue()).status_code == 422
        assert upload(c, b'PKbad zip').status_code == 422


def test_glb_rejects_external_resources_and_rigs(tmp_path):
    for extra in [{'buffers': [{'uri': '/etc/passwd'}]}, {'skins': [{}]}, {'animations': [{}]}]:
        payload = json.dumps({'asset': {'version': '2.0'}, 'meshes': [{'primitives': []}], **extra}).encode()
        payload += b' ' * (-len(payload) % 4)
        path = tmp_path / 'input.glb'
        path.write_bytes(struct.pack('<IIIII', 0x46546c67, 2, 20 + len(payload), len(payload), 0x4E4F534A) + payload)
        with pytest.raises(ValueError):
            inspect_upload(path)


@pytest.mark.parametrize('operation', list(MODELS))
def test_model_commands_never_invoke_blender(operation, tmp_path):
    params = MODELS[operation].model_validate({'prompt': 'Walk forward'} if operation == 'hymotion' else {}).model_dump()
    stages, primary, reports, kind = commands(ROOT, {'operation': operation, 'parameters': params},
        tmp_path, {role: tmp_path / role for role in ['front', 'mesh', 'reference']})
    assert primary.is_relative_to(tmp_path) and reports
    for name, command in stages:
        assert 'blender' not in str(command[0]).lower()
        assert str(command[0]).endswith('/bin/python')
        assert command[1].is_file()
        assert all('\x00' not in str(arg) for arg in command)


def test_experimental_contracts(settings):
    import fcntl
    with settings.gpu_lock.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with client(settings) as c:
            assert c.get('/docs/geometry-experiments.md', headers={'Authorization': 'Bearer wrong'}).status_code == 401
            assert 'book' in c.get('/docs/geometry-experiments.md').text
            opaque = upload(c, png()).json()['id']
            image = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
            image.paste((100, 60, 10, 255), (8, 8, 24, 24))
            stream = io.BytesIO()
            image.save(stream, format='PNG')
            cutout = upload(c, stream.getvalue()).json()['id']
            base = {'request_id': 'experiment', 'operation': 'trellis2-shape',
                    'inputs': {'front': cutout}, 'parameters': {}}
            for changes in [
                {'inputs': {'front': opaque}},
                {'inputs': {'front': cutout, 'back': cutout}},
                {'parameters': {'resolution': 2048}},
                {'parameters': {'steps': True}},
                {'parameters': {'encoder_path': '/tmp/injection'}},
                {'operation': 'deepmesh-retopology', 'inputs': {'mesh': cutout}},
                {'operation': 'trellis-shape', 'inputs': {'front': cutout, 'back': cutout}, 'parameters': {'steps': 1}},
            ]:
                assert c.post('/jobs', json={**base, **changes}).status_code == 422
            response = c.post('/jobs', json=base)
            assert response.status_code == 202
            assert response.json()['request']['parameters']['remesh'] is True
            c.post('/jobs/' + response.json()['id'] + '/cancel')
            response = c.post('/jobs', json={**base, 'request_id': 'multi', 'operation': 'trellis-shape',
                                           'inputs': {'front': cutout, 'back': cutout}})
            assert response.status_code == 202
            c.post('/jobs/' + response.json()['id'] + '/cancel')


@pytest.mark.parametrize('operation,bad', [
    ('deepmesh-retopology', {'max_tokens': 30001}),
    ('deepmesh-retopology', {'max_seconds': 1200}),
    ('deepmesh-retopology', {'temperature': float('nan')}),
    ('lato2-retopology', {'target_vertices': 100000}),
    ('lato2-retopology', {'target_vertices': True}),
    ('lato2-retopology', {'mesh_dir': '/tmp/arbitrary'}),
])
def test_experimental_parameter_bounds(operation, bad):
    with pytest.raises(ValueError):
        MODELS[operation].model_validate(bad)


def test_experimental_staging_and_coordinate_contract(tmp_path):
    p = MODELS['trellis2-shape']().model_dump()
    request = {'operation': 'trellis2-shape', 'parameters': p}
    stages, primary, reports, _ = commands(ROOT, request, tmp_path, {'front': tmp_path / 'front.png'})
    assert len(stages) == 2 and primary.name == '01-dense-remesh.glb'
    assert '01-dense-remesh.json' in reports
    p['remesh'] = False
    stages, primary, reports, _ = commands(ROOT, request, tmp_path, {'front': tmp_path / 'front.png'})
    assert len(stages) == 1 and primary.name == '01-dense-raw.glb'
    p = MODELS['lato2-retopology'](fill_quad_rings=False).model_dump()
    stages, _, _, _ = commands(ROOT, {'operation': 'lato2-retopology', 'parameters': p}, tmp_path, {'mesh': tmp_path / 'mesh.glb'})
    assert '--no-fill-quad-rings' in stages[0][1]
    center, extent = np.array([12., -6., 8.]), 4.
    result = restore_lato_vertices(np.array([[-.5, 0, .25], [.5, 0, -.25]]), center, extent)
    np.testing.assert_allclose(result, [[10, -6, 9], [14, -6, 7]])


def test_cutout_preflight_and_inherited_gpu_lock(tmp_path, monkeypatch):
    path = tmp_path / 'image.png'
    for color in [(1, 2, 3, 255), (1, 2, 3, 0)]:
        Image.new('RGBA', (32, 32), color).save(path)
        with pytest.raises(ValueError, match='foreground RGBA cutout'):
            require_cutout(path)
    image = Image.new('RGBA', (32, 32))
    image.paste((1, 2, 3, 255), (8, 8, 24, 24))
    image.save(path)
    require_cutout(path)
    # Fail immediately if a worker child attempts to reacquire the parent's flock.
    monkeypatch.setenv('SHAPE_GEN_GPU_LOCK_HELD', '1')
    monkeypatch.setattr('fcntl.flock', lambda *a: pytest.fail('nested GPU lock'))
    with gpu_lock():
        pass
