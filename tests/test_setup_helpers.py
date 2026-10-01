"""Fresh-install support without network, model downloads or a GPU."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import types

import pytest

from scripts import setup_models, setup_sources

ROOT = Path(__file__).resolve().parents[1]


def tiny_group():
    payload = b'tiny verified checkpoint'
    return payload, {'files': [{'repo': 'test/model', 'revision': 'a' * 40,
                               'filename': 'nested/model.bin', 'target': 'models/test/nested/model.bin',
                               'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}],
                     'metadata': [{'path': 'models/test/model-info.json', 'content': {'revision': 'a' * 40}}]}


def test_download_verify_and_resume_without_network(tmp_path, monkeypatch):
    payload, group = tiny_group()
    calls = []

    def fetch(repo, filename, *, revision, local_dir):
        calls.append((repo, filename, revision))
        path = Path(local_dir) / filename
        path.parent.mkdir(parents=True)
        path.write_bytes(payload)
        return str(path)

    monkeypatch.setitem(sys.modules, 'huggingface_hub', types.SimpleNamespace(hf_hub_download=fetch))
    setup_models.install(group, tmp_path)
    setup_models.install(group, tmp_path)  # Reuses verified bytes.
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in tmp_path.rglob('*') if p.is_file()}
    setup_models.install(group, tmp_path, verify_only=True)
    assert len(calls) == 1
    assert all((p.read_bytes(), p.stat().st_mtime_ns) == state for p, state in before.items())
    (tmp_path / group['metadata'][0]['path']).unlink()
    with pytest.raises(RuntimeError, match='Missing runner metadata'):
        setup_models.install(group, tmp_path, verify_only=True)


def test_bad_existing_checkpoint_is_preserved(tmp_path):
    _, group = tiny_group()
    target = tmp_path / group['files'][0]['target']
    target.parent.mkdir(parents=True)
    target.write_bytes(b'other checkpoint')
    with pytest.raises(RuntimeError, match='Move it aside'):
        setup_models.install(group, tmp_path)
    assert target.read_bytes() == b'other checkpoint'
    assert not (tmp_path / group['metadata'][0]['path']).exists()


def test_model_destination_cannot_escape_root(tmp_path):
    with pytest.raises(ValueError, match='escapes'):
        setup_models.local_path(tmp_path, '../outside.bin')
    (tmp_path / 'linked').symlink_to(tmp_path.parent, target_is_directory=True)
    with pytest.raises(ValueError, match='escapes'):
        setup_models.local_path(tmp_path, 'linked/outside.bin')


def test_catalog_and_portable_requirements():
    catalog = json.loads(setup_models.CATALOG.read_text())
    for group in catalog.values():
        for spec in group['files']:
            assert re.fullmatch('[a-f0-9]{40}', spec['revision'])
            assert re.fullmatch('[a-f0-9]{64}', spec['sha256'])
            assert spec['bytes'] > 0
            setup_models.local_path(ROOT, spec['target'])
            assert Path(spec['target']).as_posix().endswith('/' + spec['filename'])
        for spec in group['metadata']:
            setup_models.local_path(ROOT, spec['path'])
    for path in (ROOT / 'config/install').glob('*.txt'):
        assert 'file:' not in path.read_text()
        assert '/home/' not in path.read_text()
        assert '/tmp/' not in path.read_text()


def test_source_helper_clones_pin_and_preserves_existing_changes(tmp_path, monkeypatch):
    upstream = tmp_path / 'upstream'
    upstream.mkdir()
    def git(*args):
        return subprocess.check_output(['git', '-C', str(upstream), *args], text=True).strip()
    git('init', '-q')
    (upstream / 'file.txt').write_text('first')
    git('add', 'file.txt')
    git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'first')
    commit = git('rev-parse', 'HEAD')
    root = tmp_path / 'checkout'
    (root / 'config').mkdir(parents=True)
    (root / 'config/source-revisions.json').write_text(json.dumps({'example': {'url': str(upstream), 'commit': commit}}))
    monkeypatch.setattr(setup_sources, 'ROOT', root)
    monkeypatch.setattr(sys, 'argv', ['setup_sources.py', 'example'])
    setup_sources.main()
    target = root / 'third_party/example/file.txt'
    target.write_text('local change')
    setup_sources.main()
    assert target.read_text() == 'local change'
    (root / 'config/source-revisions.json').write_text(json.dumps({'example': {'url': str(upstream), 'commit': 'a' * 40}}))
    with pytest.raises(RuntimeError, match='refusing to reset'):
        setup_sources.main()
    assert target.read_text() == 'local change'
