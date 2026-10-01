import json
from pathlib import Path
import subprocess
import sys

import pytest
from scripts.build_docs_index import metadata, render

ROOT = Path(__file__).resolve().parents[1]


def write_doc(path, **changes):
    values = dict(title='Example', summary='Concrete contents | and boundaries', kind='reference',
                  status='current', topics=['test'], read_when='Choosing a test document.')
    values.update(changes)
    path.write_text('---\n' + '\n'.join(f'{k}: {json.dumps(v)}' for k, v in values.items()) + '\n---\n# Example\n')


def test_nested_docs_deterministic_and_check_detects_staleness(tmp_path):
    (tmp_path / 'nested').mkdir()
    path = tmp_path / 'nested/example.md'
    write_doc(path)
    result = render(tmp_path)
    assert '(nested/example.md)' in result
    assert '&#124;' in result
    index = tmp_path / 'INDEX.md'
    index.write_text(result)
    assert render(tmp_path) == result
    command = [sys.executable, str(ROOT / 'scripts/build_docs_index.py'), '--docs-dir', str(tmp_path), '--check']
    assert subprocess.run(command, capture_output=True).returncode == 0
    write_doc(path, summary='Changed scope')
    assert subprocess.run(command, capture_output=True).returncode == 1
    assert index.read_text() == result  # Check does not rewrite.


def test_missing_or_invalid_metadata_fails(tmp_path):
    path = tmp_path / 'new.md'
    path.write_text('# Unindexed doc\n')
    with pytest.raises(ValueError, match='missing frontmatter'):
        render(tmp_path)
    write_doc(path, topics='not an array')
    with pytest.raises(ValueError, match='topics'):
        metadata(path)
    write_doc(path, kind='unknown')
    with pytest.raises(ValueError, match='invalid kind'):
        metadata(path)


def test_repository_index_is_current():
    assert (ROOT / 'docs/INDEX.md').read_text() == render(ROOT / 'docs')
