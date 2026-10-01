"""Sync mutable API handoff copies and their checksums; never touch helper releases."""
import argparse
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    'agent.md': 'docs/api-agent.md',
    'blender-handoff.md': 'docs/blender-handoff.md',
    'geometry-experiments.md': 'docs/api-geometry-experiments.md',
    'motion-diagnostics.md': 'docs/motion-diagnostics.md',
    'shape_api_client.py': 'scripts/shape_api_client.py',
}


def sync(root, check=False):
    directory = root / 'exports/shape-gen-api'
    # README is maintained in the export itself. Fail before any writes if missing.
    files = {'README.md': (directory / 'README.md').read_bytes()}
    files.update({name: (root / source).read_bytes() for name, source in SOURCES.items()})
    files['SHA256SUMS'] = ''.join(
        f'{hashlib.sha256(data).hexdigest()}  {name}\n'
        for name, data in sorted(files.items())).encode()
    stale = [name for name, data in files.items()
             if not (directory / name).is_file() or (directory / name).read_bytes() != data]
    if check and stale:
        raise ValueError('Stale API handoff: ' + ', '.join(stale) + '; run scripts/sync_api_handoff.py')
    if not check:
        for name in stale:
            (directory / name).write_bytes(files[name])
    return stale


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Verify source copies and complete checksums without writes')
    args = parser.parse_args()
    try:
        changed = sync(ROOT, args.check)
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + '\n')
    print('API handoff copies and checksums are current.' if args.check else f'Updated {len(changed)} handoff files.')


if __name__ == '__main__':
    main()
