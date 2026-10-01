"""Fetch pinned inference assets for UniRig and HY-Motion Lite; verify hashes."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
import time

os.environ.setdefault('HF_HUB_DISABLE_XET', '1')
os.environ.setdefault('HF_HUB_DOWNLOAD_TIMEOUT', '120')
from huggingface_hub import HfApi, hf_hub_download

ROOT = Path(__file__).resolve().parents[1]
SPECS = [
    ('VAST-AI/UniRig', '36842e2b5947e9e60f89275b83208c8e74071c63', 'models/unirig',
     ['README.md', 'skeleton/articulation-xl_quantization_256/model.ckpt', 'skin/articulation-xl/model.ckpt']),
    ('tencent/HY-Motion-1.0', '620dd559f8d964aac2f82f1204fe6a35ad8ad14d', 'models/hy-motion/tencent',
     ['README.md', 'LICENSE.txt', 'HY-Motion-1.0-Lite/config.yml', 'HY-Motion-1.0-Lite/latest.ckpt']),
    ('Qwen/Qwen3-8B', 'b968826d9c46dd6066d109eabc6255188de91218', 'models/hy-motion/Qwen3-8B', None),
    ('openai/clip-vit-large-patch14', '32bd64288804d66eefd0ccbe215aa642df71cc41', 'models/hy-motion/clip-vit-large-patch14', None),
    # UniRig initializes OPT from its config, then loads its own trained checkpoint.
    ('facebook/opt-350m', '08ab08cc4b72ff5593870b5d527cf4230323703c', 'models/unirig/opt-350m',
     ['config.json', 'LICENSE.md', 'README.md']),
]


def download(spec):
    repo, revision, folder, selected = spec
    folder = ROOT / folder
    folder.mkdir(parents=True, exist_ok=True)
    info = HfApi().model_info(repo, revision=revision, files_metadata=True)
    files = [s for s in info.siblings if (s.rfilename in selected if selected is not None else
             s.rfilename.endswith(('.json', '.txt', '.safetensors', '.md')) or s.rfilename == 'LICENSE')]
    report = {'repo_id': repo, 'revision': revision, 'status': 'downloading', 'files': []}
    manifest = folder / 'download-manifest.json'
    manifest.write_text(json.dumps(report, indent=2) + '\n')
    print(f'Start {repo}: {sum(s.size for s in files)/1e9:.2f} GB', flush=True)
    lock = threading.Lock()
    def fetch(s):
        for attempt in range(4):
            try:
                path = Path(hf_hub_download(repo, s.rfilename, revision=revision, local_dir=folder))
                break
            except Exception:
                if attempt == 3: raise
                time.sleep(5*(attempt+1))
        with path.open('rb') as f:
            digest = hashlib.file_digest(f, 'sha256').hexdigest()
        if path.stat().st_size != s.size or (s.lfs and digest != s.lfs.sha256):
            raise RuntimeError(f'Integrity check failed: {path}')
        with lock:
            report['files'].append({'name': s.rfilename, 'size': s.size, 'sha256': digest,
                                'upstream_sha256_verified': bool(s.lfs)})
            manifest.write_text(json.dumps(report, indent=2) + '\n')
        print(f'Verified {repo}/{s.rfilename} ({s.size/1e6:.1f} MB)', flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(fetch, files))
    report['status'] = 'complete'
    manifest.write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    # Large shards run concurrently; HF locks and resumes each individual file.
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        reports = list(pool.map(download, SPECS))
    links = {
        'third_party/UniRig/experiments/skeleton/articulation-xl_quantization_256': 'models/unirig/skeleton/articulation-xl_quantization_256',
        'third_party/UniRig/experiments/skin/articulation-xl': 'models/unirig/skin/articulation-xl',
        'third_party/HY-Motion-1.0/ckpts/tencent': 'models/hy-motion/tencent',
        'third_party/HY-Motion-1.0/ckpts/Qwen3-8B': 'models/hy-motion/Qwen3-8B',
        'third_party/HY-Motion-1.0/ckpts/clip-vit-large-patch14': 'models/hy-motion/clip-vit-large-patch14',
    }
    for link, target in links.items():
        path, dest = ROOT/link, ROOT/target
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink() and path.resolve() == dest.resolve():
            continue
        if path.exists() or path.is_symlink():
            raise FileExistsError(path)
        path.symlink_to(os.path.relpath(dest, path.parent), target_is_directory=True)
    commits = {name: subprocess.check_output(['git', '-C', str(ROOT/'third_party'/name),
                'rev-parse', 'HEAD'], text=True).strip() for name in ['UniRig', 'HY-Motion-1.0']}
    (ROOT/'models/animation-downloads.json').write_text(json.dumps({
        'status': 'complete', 'source_commits': commits, 'repositories': reports,
        'total_bytes': sum(f['size'] for r in reports for f in r['files']),
        'scope': 'Inference assets downloaded; Python environments and inference not tested.',
    }, indent=2)+'\n')
    print('All animation model downloads verified.', flush=True)


if __name__ == '__main__':
    main()
