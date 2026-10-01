"""Download and verify the standard Hunyuan3D-2mv FP16 checkpoint and config."""

import hashlib
import json
from pathlib import Path

from huggingface_hub import hf_hub_download


ROOT = Path(__file__).resolve().parents[1]
REPO = "tencent/Hunyuan3D-2mv"
REVISION = "3a761b539b29fe4ff64714813aa9560fd66f5de0"
SUBFOLDER = "hunyuan3d-dit-v2-mv"
WEIGHTS_SHA256 = "d36f5881bcdc56726b73e517cd444c13c60732431622da7268145355c8d38e9c"
CONFIG_SHA256 = "315fd5bf601d1d103130b9fda202f1bd28eda495e68ed1621bc823d5519c5e5b"
WEIGHTS_SIZE = 4928151562


def main():
    root = ROOT / "models/hunyuan3d-2mv"
    for filename, expected in [("config.yaml", CONFIG_SHA256), ("model.fp16.safetensors", WEIGHTS_SHA256)]:
        path = Path(hf_hub_download(
            repo_id=REPO, revision=REVISION, filename=f"{SUBFOLDER}/{filename}", local_dir=root,
        ))
        print(f"Verifying {filename}...", flush=True)
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != expected:
            raise RuntimeError(f"Checksum mismatch: {path}")
    info = {
        "repo_id": REPO, "revision": REVISION, "subfolder": SUBFOLDER,
        "sha256": WEIGHTS_SHA256,
        "file": {"rfilename": f"{SUBFOLDER}/model.fp16.safetensors", "size": WEIGHTS_SIZE,
                 "lfs": {"sha256": WEIGHTS_SHA256, "size": WEIGHTS_SIZE}},
        "config_url": f"https://huggingface.co/{REPO}/resolve/{REVISION}/{SUBFOLDER}/config.yaml",
        "config_sha256": CONFIG_SHA256,
    }
    (root / SUBFOLDER / "model-info.json").write_text(json.dumps(info, indent=2) + "\n")
    print(f"Verified 2mv model installed at {root / SUBFOLDER}", flush=True)


if __name__ == "__main__":
    main()
