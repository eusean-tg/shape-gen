from dataclasses import replace
from pathlib import Path

from test_shape_api import client, settings
from test_model_api import png, upload
from shape_api.server import Settings


def test_model_only_start_without_any_legacy_assets(settings, tmp_path):
    clean = replace(settings, root=tmp_path / 'empty-checkout', legacy_profile=False,
                    blender=tmp_path / 'no-blender')
    with client(clean) as c:
        health = c.get('/health')
        assert health.status_code == 200
        assert not health.json()['legacy_profile_enabled']
        assert not any(health.json()['runner_environments_present'].values())
        assert c.get('/profiles').json() == {'profiles': []}
        assert c.get('/operations').json()['legacy_operation'] is None
        assert upload(c, png()).status_code == 200
        assert c.post('/jobs', json={'request_id': 'legacy', 'parameters': {'prompt': 'wave'}}).status_code == 422
        assert not (clean.data / 'profile').exists()


def test_model_only_environment_flag(monkeypatch):
    monkeypatch.setenv('SHAPE_API_LEGACY_PROFILE', '0')
    assert Settings().legacy_profile is False
    monkeypatch.delenv('SHAPE_API_LEGACY_PROFILE')
    assert Settings().legacy_profile is True
