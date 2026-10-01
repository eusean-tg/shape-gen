# TRELLIS.2 geometry experiment

Run on RTX 3050 8 GiB, 2026-09-19. This is an isolated local experiment, not an API operation.
The review UI is in `../makima-trellis/` and served at
<http://localhost:5173/makima-trellis/> by the existing preview server.

## Environment and sources

- Python: `/home/sean/workspace/shape-gen/.venv-trellis2/bin/python` (3.10).
- Exact installed packages: `environment-freeze.txt`.
- Source revisions: `code-revisions.json`.
- Official Microsoft checkpoints and hashes: `../../models/trellis2/download-manifest.json`.
- DINOv3: `facebook/dinov3-vitl16-pretrain-lvd1689m`, revision
  `ea8dc2863c51be0a264bab82070e3e8836b02d51`, under `models/trellis2/dinov3-vitl16`.
  Access was approved and the user's existing HF CLI login was used. No token is stored here.
  The runner verifies the checkpoint against the official repository's LFS hash.
- Geometry only: no TRELLIS.2 texture weights or texture baking were used.

The environment uses Torch 2.6.0/cu124 and xformers. FlexGEMM, CuMesh and o_voxel
were compiled with the existing CUDA 12.6 / Conda host compiler toolchain for
SM 8.6. Build logs are in `.toolchain/trellis2-*.log` from the project root.
The o_voxel build uses `third_party/lato2-trellis/o-voxel`, the same official
TRELLIS.2 source revision; its earlier lazy import of the texture postprocessor
is retained. Geometry conversion math was not changed.

## Reproduce

From `/home/sean/workspace/shape-gen`; use new output directories to preserve results:

```sh
.venv-trellis2/bin/python assets/makima-trellis2/run_shape.py \
  --resolution 1024 --seed 12345 --steps 12 \
  --output-dir assets/makima-trellis2/new-1024

.venv-trellis2/bin/python assets/makima-trellis2/remesh_export.py \
  assets/makima-trellis2/new-1024/01-dense-raw.glb \
  assets/makima-trellis2/new-1024/01-dense-remesh.glb \
  --resolution 1024 --target 500000

.venv-bpt/bin/python assets/makima-knob-audit/bpt_trial.py \
  assets/makima-trellis2/new-1024/01-dense-remesh.glb \
  --output-dir assets/makima-trellis/new-bpt
```

`--resolution 512` runs the smaller path. Both use the same existing front RGBA
cutout by default; `--image` accepts another foreground RGBA image. An opaque
image is rejected because this runner deliberately does not load another
segmentation model. The native crop and black compositing remain enabled.

The runner uses the upstream low-VRAM mode and stages the image encoder,
structure flow/decoder, shape flow and shape decoder. The 1024 path uses the
official 512-to-1024 cascade. Flow/decoder precision follows the checkpoints;
there is no weight quantization. The full models live in CPU RAM between GPU
stages. This machine has 64 GiB RAM; this is not a low-system-RAM test.

Every GPU runner acquires `~/.cache/shape-gen/gpu.lock`, shared with the API.
`experiment.json` records stages, elapsed time, PyTorch allocation peaks,
model loading checks and raw mesh measurements. PyTorch measurements exclude
some driver/native-library allocations and are **not total GPU utilization**.

`shape-latent.pt` allows a decode-only retry with `--resume-shape`; use the same
resolution and a new output directory. Raw output is preserved both in native
Z-up PLY and in glTF Y-up coordinates. Use the Y-up GLB for BPT and Blender.

## Export variants

- `01-dense-raw.glb`: decoder output, axis rotation only. Many topology defects.
- `01-dense-clean*.glb` in `front/`: exploratory non-remeshing cleanup. This
  leaves many boundaries; normal recalculation did not make it consistently
  oriented. These are diagnostics, not recommended final exports.
- `01-dense-remesh.glb`: geometry part of the official demo's export:
  initial small-hole fill, narrow-band dual contouring (`band=1`,
  `project_back=0`) at the source resolution, then CuMesh simplification.
  We use a 500k target rather than the example's 1M target. No UV or texture
  stages. This visibly closes most tiny defects but is not a manifoldness
  guarantee. Remeshing changes the surface and can affect narrow gaps.
- `front1024/01-dense-remesh-clean.glb`: extra non-remesh cleanup *after*
  remeshing, with a 200k target. This experimental combination leaves boundary
  edges. The unchanged BPT pass on it failed to reach EOS within 10k tokens.

`../makima-trellis/exterior_cloud.py` is a separate surface-sampling diagnostic.
It filters area samples by visibility along the surface normal before choosing
4,096 BPT points. It can exclude valid recessed faces, so it is not a generally
validated replacement for standard sampling. Reproduce with:

```sh
.venv-trellis2/bin/python assets/makima-trellis/exterior_cloud.py \
  INPUT.glb NEW-cloud.npy
.venv-bpt/bin/python assets/makima-knob-audit/bpt_trial.py \
  INPUT.glb --cloud NEW-cloud.npy --output-dir NEW-output-folder
```

The older TRELLIS fallback runner/results live in `../makima-trellis/`.
It uses DINOv2, staged models, and CPU FlexiCubes extraction. Its four-view
trial uses upstream stochastic multi-image inference. It is not TRELLIS.2.

## Review regeneration

`../makima-trellis/render-list.json` maps models to CPU Blender clay renders.
`render_trials.py` and `render_details.py` skip existing images; remove only
the affected generated images when intentionally changing a source.
`build_review.py` asserts that all listed GLBs and renders exist before writing
the gallery and interactive model list. Never replace the accepted character
or API defaults based only on this experiment.
