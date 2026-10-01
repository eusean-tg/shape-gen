---
title: "Core installation and API startup"
summary: "First-host installation for Hunyuan, BPT, Paint, API credentials, systemd and preview."
kind: "setup"
status: "current"
topics: ["installation", "hunyuan", "bpt", "paint", "api"]
read_when: "Install the core GPU host or diagnose missing setup files."
---
# Core installation and API startup

Start with Hunyuan mini, then add only the operations you need. This guide describes
the Linux NVIDIA GPU host; the [API client](api-agent.md) runs on the consumer.
Commands run from the checkout root. Python environments must remain separate.

## Host prerequisites

Install Git, curl, build tools and graphics runtime libraries. For Debian/Ubuntu:

```sh
sudo apt-get update
sudo apt-get install git git-lfs curl build-essential pkg-config libgl1 libegl1 libglib2.0-0 libgomp1
git lfs install
nvidia-smi
```

`nvidia-smi` must find the GPU before proceeding. PyTorch wheels provide a CUDA
runtime; they do not install the host NVIDIA driver. Use a driver compatible with
CUDA 12.6 for the main environments. The recipes were tested on an Ampere RTX 3050;
other GPU generations may need different Torch/compiler builds.

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and open a
shell where `uv` is on PATH. Install managed Python:

```sh
uv python install 3.11 3.10
```

Download sources before creating environments that reference them:

```sh
uv run --no-project --python 3.11 python scripts/setup_sources.py --list
uv run --no-project --python 3.11 python scripts/setup_sources.py Hunyuan3D-2
```

The helper uses `config/source-revisions.json`, checks out pinned commits and
initializes submodules. It refuses to reset a checkout at another commit. At an
already matching commit it leaves local changes and submodules untouched; it is
not a repair tool for a damaged or locally modified checkout.

## Hunyuan environment and checkpoints

```sh
uv sync --locked --no-install-package custom-rasterizer --no-install-package mesh-processor
.venv/bin/python scripts/setup_models.py mini
```

This creates `.venv` (Python 3.11, Torch 2.7.1/CUDA 12.6), using `pyproject.toml`
and `uv.lock`. The two skipped packages are native Paint extensions. Use the
explicit interpreter until Paint is installed; unqualified `uv run` resynchronizes
all project dependencies.

`.venv` is also the API's shared mesh-validation/utility environment. Install it
even if another model is your only mesh generator. Model downloads are optional:

| Group | Approximate files size | Purpose |
|---|---:|---|
| `mini` | 3.82 GB | Main API default, single reference |
| `full` | 4.93 GB | Undistilled Hunyuan3D-2; CLI default |
| `mv` | 4.93 GB | Hunyuan3D-2 multiview |
| `paint` | 13.50 GB | Complete Paint and Delight components |

```sh
.venv/bin/python scripts/setup_models.py --list
# Optional; choose just the groups you need.
.venv/bin/python scripts/setup_models.py full mv
.venv/bin/python scripts/setup_models.py --verify-only mini
```

`config/model-download-catalog.json` records upstream repositories, exact revisions,
file sizes and SHA-256 hashes. The downloader verifies bytes and writes the runner
metadata sidecars. It refuses to overwrite an existing mismatching checkpoint;
move that file aside deliberately before retrying. Downloads use Hugging Face's
`local_dir` support: resumable partial files and download metadata live under the
per-repository destination folder's `.cache/huggingface/download/`. For example,
full shape and Paint share `models/hunyuan3d-2/.cache/huggingface/download/`, even
though their model files occupy separate subdirectories. An interrupted group can
be rerun. `--verify-only` makes no writes and also checks that sidecars exist.

Do not download only a loose safetensors file: config and `model-info.json` are
required. The listed shape checkpoint includes the components needed by this
runner; a separate manually selected VAE checkpoint is unnecessary.

### Generate and verify

```sh
mkdir -p ~/.cache/shape-gen
flock ~/.cache/shape-gen/gpu.lock .venv/bin/python scripts/check_environment.py
flock ~/.cache/shape-gen/gpu.lock .venv/bin/python scripts/generate.py /path/to/reference.png \
  --model mini --output-dir assets/example-mini
```

The environment check imports dependencies and exercises a small CUDA calculation
and mesh round trip; it does not load a shape model. A successful actual generation
is the model smoke test. Inspect `01-dense.glb` and the run's metadata visually.
Opaque input normally triggers CPU background removal and a first-use U2Net download.
A prepared RGBA cutout avoids that download; `--keep-background` disables removal
for opaque input when intentional.

For multiview, prepare a directory containing `front.png` and at least one of
`left.png`, `back.png`, `right.png`, then pass that directory with `--model mv`.
Views should describe the same object with consistent proportions and pose.

Defaults are 50 steps, resolution 128, chunks 1024, guidance 5 and seed 12345.
Changing masking, extraction resolution or seeds can improve one feature and harm
another. The [Makima audit](research/makima-knob-audit-2026-09-19.md) is an experiment,
not a universal replacement preset. `--target-triangles N` optionally adds a
simplified mesh; it does not invoke BPT or produce deformation-aware topology.

## BPT reconstruction

```sh
.venv/bin/python scripts/setup_sources.py bpt
uv venv .venv-bpt --python 3.11
uv pip install --python .venv-bpt/bin/python -r config/bpt-lock.txt
.venv-bpt/bin/python scripts/setup_bpt.py
flock ~/.cache/shape-gen/gpu.lock .venv-bpt/bin/python scripts/retopo_bpt.py \
  assets/example-mini/01-dense.glb --output-dir assets/example-bpt
```

The downloader creates `models/bpt/` and its required metadata, with a pinned
roughly 1.64 GB checkpoint. Outputs include `02-bpt.glb` and OBJ. Useful controls
are `--seed`, `--temperature`, `--max-tokens` and `--encoder-device cpu`.
A token ceiling is not a triangle budget and can truncate generation. BPT reconstructs
geometry and can change silhouettes, close gaps or lose detail. Review before UVs,
texturing or rigging; numerical validity does not certify a useful game asset.

## Paint and Delight

Paint runs on an existing mesh; regenerating its shape is unnecessary. Install the
native dependencies and both complete model directories:

```sh
.venv/bin/python scripts/setup_paint.py
.venv/bin/python scripts/setup_models.py paint
flock ~/.cache/shape-gen/gpu.lock .venv/bin/python scripts/paint.py \
  assets/example-bpt/02-bpt.glb --image /path/to/reference.png \
  --output-dir assets/example-painted
```

The build script downloads a pinned private CUDA 12.6 toolchain and GCC 13 host
environment under `.toolchain/`, then compiles `custom-rasterizer` and
`mesh-processor`. It does not replace the system driver. Its default CUDA target
is `8.6` (RTX 3050); set `TORCH_CUDA_ARCH_LIST` to your GPU's supported architecture
when compiling for different compatible hardware. `MAX_JOBS` controls parallel
compilation (default 4).

Paint needs all its scheduler, tokenizer, encoder, UNet and VAE files, plus Delight;
the download group handles them together. Output is `03-textured.glb`, a base-color
atlas and diagnostic projected views. This is not a complete PBR-material pipeline.
With reviewed UVs, use `--preserve-uvs`; otherwise the runner can unwrap. Hair/cloth
boundaries and color masks may still need local correction.

## Start the API

The API itself is CPU-only. Set up its independent environment:

```sh
uv venv .venv-api --python 3.11
uv pip install --python .venv-api/bin/python -r config/api-environment.txt
```

Create a token once, without printing it. This command intentionally refuses to
overwrite an existing credential; skip it if the token is already provisioned.

```sh
.venv-api/bin/python - <<'PY'
import os
from pathlib import Path
import secrets
path = Path.home() / '.config/shape-gen/api-token'
path.parent.mkdir(parents=True, exist_ok=True)
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as stream:
    stream.write(secrets.token_urlsafe(48) + '\n')
print(f'Created credential at {path}')
PY
SHAPE_API_LEGACY_PROFILE=0 .venv-api/bin/python -m uvicorn shape_api.server:app \
  --host 127.0.0.1 --port 8765 --workers 1 --no-access-log
```

`SHAPE_API_LEGACY_PROFILE=0` is essential for a normal fresh checkout. It disables
the old server-side teal retarget job and removes its dependency on ignored Blender
files. All nine model operations remain available. The default is still `1` for
compatibility with the original deployment. Do not enable it without restoring
and verifying the exact legacy assets referenced in `config/api-profile-teal-v1.json`.

In another terminal:

```sh
python3 scripts/shape_api_client.py --base-url http://127.0.0.1:8765 health
python3 scripts/shape_api_client.py --base-url http://127.0.0.1:8765 operations
python3 scripts/shape_api_client.py --base-url http://127.0.0.1:8765 upload /path/to/reference.png
```

`health` reports interpreter presence; it does not test all weights, imports or GPU
inference. The operation catalog describes supported contracts even for uninstalled
optional models. For submission, use `submit-json` with an operation and the uploaded
asset ID, then `watch JOB_ID` and `download JOB_ID --output PATH`. See the
[agent guide](api-agent.md#upload-and-chain-inputs) for complete request examples.
The client's plain `submit` subcommand is for the legacy profile only.

All endpoints require a bearer token, including docs. The supplied client reads
`~/.config/shape-gen/api-token`; override with `--token-file`. Its historical default
URL is the original machine's Tailscale address, so specify `--base-url` explicitly.
For remote use, bind to your own private network interface. One shared token grants
the same service access to each holder; there are no per-user scopes or isolated queues.

### Persistent user service

`config/shape-gen-api.service` is an ignored local unit for the original machine;
it is not included in a clone. For a new installation,
copy `config/shape-gen-api.service.example` to
`~/.config/systemd/user/shape-gen-api.service` and replace **every** `/ABSOLUTE/SHAPE_GEN`
with this checkout's absolute path. Change the bind address only if remote access
is wanted. Then:

```sh
systemctl --user daemon-reload
systemctl --user enable --now shape-gen-api.service
systemctl --user status shape-gen-api.service
journalctl --user -u shape-gen-api.service -n 50
```

Stop a foreground instance before starting the service. Use one Uvicorn worker;
a second process using the same state directory is rejected. User services need
an active user manager; configure login/linger for unattended boot if required.
Code changes require an explicit idle-stop-update-test-restart sequence; see
[operations](api-operations.md#applying-code-changes).

| Environment variable | Default / purpose |
|---|---|
| `SHAPE_API_LEGACY_PROFILE` | `1`; use `0` for independent model operations |
| `SHAPE_API_DATA` | `<checkout>/var/api`; durable private job state |
| `SHAPE_API_TOKEN_FILE` | `~/.config/shape-gen/api-token` |
| `SHAPE_API_GPU_LOCK` | API worker lock path; default `~/.cache/shape-gen/gpu.lock`. Direct experimental runners ignore this variable and always use that default path. |
| `SHAPE_API_BLENDER` | `~/.local/bin/blender`; legacy operation only |

### Blender helper downloads

The small versioned helper ZIPs are included in Git with their manifests and release
metadata, so a fresh clone can serve the advertised bundles immediately. Discover
available versions with:

```sh
python3 scripts/shape_api_client.py --base-url http://127.0.0.1:8765 helpers
```

The current guide update is bundle **1.0.3**; versions **1.0.0** through **1.0.2**
remain byte-identical for pinned consumers. Bundles contain scripts, contract metadata and documentation,
not a character `.blend`. Do not rebuild an existing version from newer source:
that changes its published hashes. To publish a later source change, choose an
unused version (for example 1.0.4):

```sh
.venv-api/bin/python scripts/build_blender_helpers.py --version 1.0.4
```

Review the new archive and commit `bundle.zip`, `manifest.json` and `release.json`
together. If an old ZIP is missing, restore its exact bytes from Git or a backup;
regenerating it from current guides is not a repair. See
[helper requirements](blender-helpers-readme.md) and [storage policy](repository-storage.md).

## Browser preview

The reusable preview is local static Three.js source under `assets/`, whose contents
are excluded from Git. These instructions require restoring `assets/preview/` and
`assets/peasant-hymotion/vendor/` from an existing workspace or backup first; a
fresh clone does not include the viewer. Recreate the vendor symlink only if missing:

```sh
ln -s ../peasant-hymotion/vendor assets/preview/vendor
python3 -m http.server 5173 --bind 127.0.0.1 --directory assets
```

Open `http://127.0.0.1:5173/preview/` and use **Open GLB** or drop a self-contained
GLB into the page. Run `ln` only if `assets/preview/vendor` is absent. Vendored Three.js
source must be restored alongside the viewer; no Bun, Vite or npm build is needed. The saved example menu
references historical binary assets excluded from Git; opening one can fail until
those assets are restored. Your own GLB can still be loaded and played/looped.

## Checks and common failures

```sh
.venv-api/bin/python -m pytest -q tests/test_fresh_install.py tests/test_setup_helpers.py tests/test_docs_index.py
```

These checks do not download or run GPU models. The full `tests/` suite also covers
the original legacy profile and needs its separately stored character fixtures.
A fresh checkout should use the checks above and an actual smoke generation for
each installed operation. Setup commands were derived from the working installation;
a full reinstall on a second clean GPU host has not been performed.

- **Missing `third_party` path:** clone the pinned sources before syncing dependencies.
- **Missing model metadata:** run its downloader; a lone weight file is insufficient.
- **CUDA unavailable:** check driver visibility and the specific environment's Torch
  install. The CUDA version printed by `nvidia-smi` is not an installed compiler.
- **Paint build fails:** check `.toolchain/`, compiler output and GPU architecture.
- **Out of memory:** ensure another GPU task is not running; reduce resolution or
  use documented offload options. Small-memory success depends on the stage/input.
- **Token missing / 401:** provision the credential, check the path and private file
  permissions; restarting is required after rotating the server's token file.
- **API starts but a model fails:** install that model's source, environment and
  checkpoint; `/health` is not a complete dependency verification.
- **Mesh holes / poor motion:** examine output and diagnostics; successful numeric
  validation does not establish visual quality. Raw motion is not an exact-speed loop.

Core direct GPU commands above use `flock`. Experimental runners already acquire
the same lock internally: do not wrap those in another `flock`, which can deadlock.
The same applies to `scripts/remesh_trellis2.py`, which also locks internally.
The API coordinates the lock across its subprocess stages. Its worker honors
`SHAPE_API_GPU_LOCK`, but direct experimental runners use the hardcoded default
`~/.cache/shape-gen/gpu.lock`. Keep the default API path when mixing API jobs and
direct experimental runs; overriding it does not move their lock.
