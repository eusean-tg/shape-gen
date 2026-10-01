"""Download the official BPT checkpoint at a pinned revision and verify it."""
import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
from huggingface_hub import hf_hub_download

ROOT = Path(__file__).resolve().parents[1]
REVISION = "4a7c93a2691b38682fc33ba8a414f2bf849700e3"
SHA256 = "94b587484efdcc75f5579f15c064b6f9a6697018aa619557341374f8dc705824"
FILENAME = "bpt-8-16-500m.pt"

def main():
    folder = ROOT / "models/bpt"
    path = folder / FILENAME
    if not path.exists():
        path = Path(hf_hub_download("whaohan/bpt", FILENAME, revision=REVISION, local_dir=folder))
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != SHA256:
        raise RuntimeError(f"Checkpoint SHA256 mismatch: {path}")
    (folder / "model-info.json").write_text(json.dumps({
        "repo_id": "whaohan/bpt", "revision": REVISION,
        "filename": FILENAME, "sha256": actual, "size": path.stat().st_size,
    }, indent=2) + "\n")
    print(f"Verified checkpoint: {path}")

if __name__ == "__main__":
    main()
