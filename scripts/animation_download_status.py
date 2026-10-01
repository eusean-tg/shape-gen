"""Report local animation download progress without contacting Hugging Face."""
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
plan=json.loads((ROOT/'models/animation-download-plan.json').read_text())
total_received=0
for repo in plan['repositories']:
    folder=ROOT/repo['folder']
    received=0
    manifest=folder/'download-manifest.json'
    try:
        verified=json.loads(manifest.read_text()).get('files',[]) if manifest.exists() else []
    except json.JSONDecodeError:
        verified=[]  # The downloader may currently be updating this manifest.
    for f in repo['files']:
        target=folder/f['name']
        size=target.stat().st_size if target.exists() else 0
        if not size and f['sha256']:
            partials=(folder/'.cache/huggingface/download'/Path(f['name']).parent).glob('*.'+f['sha256']+'.incomplete')
            size=max([p.stat().st_size for p in partials]+[0])
        received+=min(size,f['size'])
    expected=sum(f['size'] for f in repo['files'])
    total_received+=received
    print(f"{repo['repo_id']}: {received/1e9:.2f}/{expected/1e9:.2f} GB; {len(verified)}/{len(repo['files'])} files verified")
print(f"Total: {total_received/1e9:.2f}/{plan['total_bytes']/1e9:.2f} GB ({total_received/plan['total_bytes']:.1%})",flush=True)
complete=ROOT/'models/animation-downloads.json'
if complete.exists():
    print('All downloads verified and model paths linked. Inference has not been tested.')
else:
    subprocess.run(['systemctl','--user','show',plan['service'],'--property=ActiveState,SubState'],check=False)
