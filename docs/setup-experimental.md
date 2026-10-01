---
title: "Experimental geometry model installation"
summary: "Portable package installs, native builds, caches and gated weights for optional geometry models."
kind: "setup"
status: "current"
topics: ["installation", "deepmesh", "lato2", "trellis"]
read_when: "Install an alternative generator or reconstruction model."
---
# Experimental geometry model installation

These models are optional alternatives to the Hunyuan → BPT path. They are exposed
as independent API operations, but their quality is input-dependent. DeepMesh can
create holes; LATO.2 can produce winding/connectivity defects; a detailed dense mesh
can still lose detail during low-poly reconstruction. See
[API recipes](api-geometry-experiments.md) and the dated [research notes](research/).

Complete [core setup](setup.md) first, including `.venv` for shared mesh utilities
and downloads. Commands below run from the checkout root. Install only the models
you intend to compare; existing environments should not be recreated unnecessarily.

## Package and compiler conventions

These runners use **Python 3.10, Torch 2.6.0/CUDA 12.4**. They must not share the
main Hunyuan or BPT environments. Portable package snapshots live under
`config/install/`. Only the older `config/deepmesh-environment.txt`,
`config/lato2-environment.txt` and `config/trellis2-environment.txt` snapshots contain
machine-local wheel/source paths and are retained as provenance. The API, UniRig
and HY-Motion `*-environment.txt` files remain current install inputs.

DeepMesh uses a pinned prebuilt FlashAttention wheel. LATO.2 and TRELLIS need native
extensions. The commands below reuse the private GCC 13/CUDA 12.6 compiler installed
by [Paint setup](setup.md#paint-and-delight). Run that build step first if those
native extensions are needed; downloading Paint weights is unnecessary. The
compiler/runtime minor-version difference (12.6 compiler, 12.4 Torch) matches the
working installation. Do not treat this as a general cross-version compatibility
claim. GPU target `8.6` is the tested RTX 3050; adjust for other compatible hardware.

## DeepMesh

```sh
.venv/bin/python scripts/setup_sources.py DeepMesh
uv venv .venv-deepmesh --python 3.10
uv pip install --python .venv-deepmesh/bin/python \
  --extra-index-url https://download.pytorch.org/whl/cu124 --index-strategy unsafe-best-match \
  -r config/install/deepmesh.txt
.venv/bin/python scripts/setup_models.py deepmesh
.venv-deepmesh/bin/python -c 'import torch, flash_attn; print("DeepMesh dependencies import")'
```

The checkpoint is roughly 3.63 GB. `scripts/deepmesh_compat/` contains the local
inference compatibility layer; its source and license are included. The runner
also reads upstream model configuration from `third_party/DeepMesh`. Use
`deepmesh-retopology` with a static GLB. It is a learned reconstruction, not an
exact face-budget simplifier. Review the raw geometry before downstream work.

## LATO.2

```sh
.venv/bin/python scripts/setup_sources.py LATO.2 lato2-trellis
uv venv .venv-lato2 --python 3.10
uv pip install --python .venv-lato2/bin/python \
  --extra-index-url https://download.pytorch.org/whl/cu124 --index-strategy unsafe-best-match \
  --find-links https://data.pyg.org/whl/torch-2.6.0+cu124.html \
  -r config/install/lato2.txt
.venv/bin/python scripts/setup_models.py lato2
```

LATO.2 uses the `o-voxel` package from a separate pinned TRELLIS.2 checkout. Apply
the included import patch to a **fresh** checkout, then compile the extension:

```sh
git -C third_party/lato2-trellis apply --check "$PWD/config/patches/o-voxel-lazy-postprocess.patch"
git -C third_party/lato2-trellis apply "$PWD/config/patches/o-voxel-lazy-postprocess.patch"
env CUDA_HOME="$PWD/.toolchain/cuda-12.6" TORCH_CUDA_ARCH_LIST=8.6 MAX_JOBS=4 \
  .toolchain/bin/micromamba run -p "$PWD/.toolchain/host" \
  uv pip install --python "$PWD/.venv-lato2/bin/python" --no-build-isolation --no-deps \
  "$PWD/third_party/lato2-trellis/o-voxel"
```

On an existing patched checkout, do not apply it twice. Confirm with
`git -C third_party/lato2-trellis apply --reverse --check "$PWD/config/patches/o-voxel-lazy-postprocess.patch"`
and skip the apply commands when that succeeds. The patch delays loading texture
postprocessing dependencies that LATO's geometry path does not use.

Warm up its DINOv2 cache on CPU (this may download additional files):

```sh
.venv-lato2/bin/python - <<'PY'
from pathlib import Path
import torch
cache = Path('third_party/LATO.2/ckpt/dinov2').resolve()
torch.hub.set_dir(str(cache))
torch.hub.load('facebookresearch/dinov2', 'dinov2_vitl14_reg', pretrained=True, trust_repo=True)
PY
.venv-lato2/bin/python -c 'import torch, o_voxel; print("LATO dependencies import")'
```

Use `lato2-retopology` with a static GLB. The API uses staged offload rather than
the upstream all-resident GPU path. New requests default to CPU normal recalculation
and preserve the raw result for comparison. Consistent winding does not repair
holes, self-intersections or nonmanifold topology.

## Shared TRELLIS environment

Both generations use `.venv-trellis2`. The working installation builds `o-voxel`
from the patched `third_party/lato2-trellis` checkout; `third_party/TRELLIS.2` stays
unpatched. Both checkouts are pinned to the same upstream commit. Set up the shared
environment once. If LATO setup already applied the patch, use its reverse check
and skip the two `git apply` commands below:

```sh
.venv/bin/python scripts/setup_sources.py TRELLIS TRELLIS.2 lato2-trellis CuMesh FlexGEMM
uv venv .venv-trellis2 --python 3.10
uv pip install --python .venv-trellis2/bin/python \
  --extra-index-url https://download.pytorch.org/whl/cu124 --index-strategy unsafe-best-match \
  --find-links https://data.pyg.org/whl/torch-2.6.0+cu124.html \
  --find-links https://nvidia-kaolin.s3.us-east-2.amazonaws.com/torch-2.6.0_cu124.html \
  -r config/install/trellis2.txt
git -C third_party/lato2-trellis apply --check "$PWD/config/patches/o-voxel-lazy-postprocess.patch"
git -C third_party/lato2-trellis apply "$PWD/config/patches/o-voxel-lazy-postprocess.patch"
env CUDA_HOME="$PWD/.toolchain/cuda-12.6" TORCH_CUDA_ARCH_LIST=8.6 MAX_JOBS=4 \
  .toolchain/bin/micromamba run -p "$PWD/.toolchain/host" \
  uv pip install --python "$PWD/.venv-trellis2/bin/python" --no-build-isolation --no-deps \
  "$PWD/third_party/lato2-trellis/o-voxel" "$PWD/third_party/CuMesh" "$PWD/third_party/FlexGEMM"
.venv-trellis2/bin/python -c 'import torch, o_voxel, cumesh, flex_gemm; print("TRELLIS dependencies import")'
```

Kaolin 0.18.0 comes from NVIDIA's Torch 2.6.0/CUDA 12.4 wheel index above;
PyPI alone does not supply that pinned build. Keep this `--find-links` source
when recreating the environment. It is also recorded in `config/install/trellis2.txt`
so the requirements file carries the package source.

On 2026-10-01, the package-install command above resolved all 147 packages in an
empty Python 3.10 environment with `--dry-run --no-cache`. This checks dependency
resolution without the existing uv cache; it does not install the packages,
compile the native extensions or verify GPU inference on a new host.

The same lazy-import patch used for LATO is required here: the geometry environment
does not install the optional nvdiffrast texture baker. Skip reapplying it when the
reverse check succeeds, as described above. Source cloning includes recursive
submodules. If compilation reports missing vendored headers, inspect the submodules
before changing package versions.

### Original TRELLIS

```sh
.venv/bin/python scripts/setup_models.py trellis
.venv-trellis2/bin/python - <<'PY'
from pathlib import Path
import torch
torch.hub.set_dir(str(Path.home() / '.cache/torch/hub'))
torch.hub.load('facebookresearch/dinov2', 'dinov2_vitl14_reg', pretrained=True, trust_repo=True)
PY
```

The runner explicitly reads `~/.cache/torch/hub/facebookresearch_dinov2_main` and
`~/.cache/torch/hub/checkpoints/dinov2_vitl14_reg4_pretrain.pth`. Keep these default
locations for this adapter. The group downloads approximately 2.66 GB of TRELLIS
files; DINOv2 is additional. DINOv2 has no DINOv3 access gate. These Torch Hub warm-up
commands fetch upstream's default source branch; unlike the checkpoint catalog,
that auxiliary cache source is not pinned by the setup helper.

Use `trellis-shape` with a prepared RGBA cutout. Optional multiple images use the
adapter's TRELLIS conditioning strategy, not Hunyuan's specifically trained 2mv
model. Review views/silhouettes independently.

### TRELLIS.2

Request and accept access to
[facebook/dinov3-vitl16-pretrain-lvd1689m](https://huggingface.co/facebook/dinov3-vitl16-pretrain-lvd1689m)
with the same Hugging Face account used on the GPU host, then authenticate locally:

```sh
.venv/bin/hf auth login
.venv/bin/python scripts/setup_models.py trellis2
```

The group downloads about 10.06 GB, including pinned geometry checkpoints, shared
TRELLIS components and the gated DINOv3 config/weights. Token credentials stay outside
Git. A 401/403 on DINOv3 means the account/token lacks access; installing the other
checkpoints does not bypass it.

Use `trellis2-shape` with a single RGBA cutout. Geometry is staged between system RAM
and GPU; the tested machine has 64 GB RAM and 8 GB VRAM. Start with the endpoint's
512-resolution default. This service does not expose TRELLIS.2 texture generation.

## Verification and operation

```sh
.venv/bin/python scripts/setup_models.py --verify-only deepmesh lato2 trellis trellis2
```

Select only the groups you installed. Hash verification does not run inference.
After dependency imports succeed, submit one small actual job through the API and
inspect its result. All four adapters acquire the shared GPU lock when run directly;
do not wrap them in another `flock`. API calls coordinate this internally.

For parameter names, accepted input types, output artifacts and a reproducible
comparison sequence, use [geometry API recipes](api-geometry-experiments.md).
Individual runner `--help` describes direct CLI options. Historical measurements
are evidence for particular assets, not quality or memory guarantees.
