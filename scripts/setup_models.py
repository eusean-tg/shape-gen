"""Download pinned optional models and required sidecars; never load GPU models."""
import argparse
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'config/model-download-catalog.json'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def local_path(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Catalog destination escapes the project')
    return path


def verified(path, spec):
    return path.is_file() and path.stat().st_size == spec['bytes'] and digest(path) == spec['sha256']


def install(group, root, verify_only=False):
    for spec in group['files']:
        target = local_path(root, spec['target'])
        if not verified(target, spec):
            if verify_only:
                raise RuntimeError(f'Missing or checksum mismatch: {target}')
            if target.exists():
                raise RuntimeError(f'Existing file differs from pinned model: {target}. Move it aside explicitly before retrying.')
            from huggingface_hub import hf_hub_download
            # Use local_dir so large files need not be copied out of the HF cache.
            relative = Path(spec['filename'])
            if list(target.parts[-len(relative.parts):]) != list(relative.parts):
                raise ValueError('Catalog target must end with its upstream filename')
            base = target.parents[len(relative.parts) - 1]
            print(f"Downloading {spec['repo']}/{spec['filename']}", flush=True)
            hf_hub_download(spec['repo'], spec['filename'], revision=spec['revision'], local_dir=base)
            if not verified(target, spec):
                raise RuntimeError(f'Download checksum mismatch: {target}')
        print(f"Verified {spec['target']}", flush=True)
    for sidecar in group['metadata']:
        target = local_path(root, sidecar['path'])
        if verify_only:
            if not target.is_file():
                raise RuntimeError(f'Missing runner metadata: {target}; run setup without --verify-only')
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(sidecar['content'], indent=2) + '\n')


def main():
    catalog = json.loads(CATALOG.read_text())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('models', nargs='*', help='Groups listed by --list; choose only what you need')
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--verify-only', action='store_true', help='Check installed bytes/metadata without network or writes')
    args = parser.parse_args()
    if args.list:
        for name, group in catalog.items():
            size = sum(s['bytes'] for s in group['files']) / 1e9
            print(f'{name:12} {size:6.2f} GB  {len(group["files"]):3} files')
        print('BPT: scripts/setup_bpt.py; UniRig + HY-Motion: scripts/download_animation_models.py')
        return
    if not args.models or set(args.models) - catalog.keys():
        parser.error('Choose one or more groups: ' + ', '.join(catalog))
    os.environ.setdefault('HF_HUB_DISABLE_XET', '1')
    for name in dict.fromkeys(args.models):
        install(catalog[name], ROOT, args.verify_only)


if __name__ == '__main__':
    main()
