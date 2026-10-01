---
title: "Hunyuan shape and environment experiments"
summary: "Original shape/multiview experiments, simplification and environment verification."
kind: "history"
status: "historical"
topics: ["hunyuan", "multiview", "geometry"]
read_when: "Trace initial shape settings and measured results."
---
# Hunyuan shape and environment experiments

Archived from the former README on 2026-09-30. “Latest,” paths, measurements and
commands below describe historical runs, not current install instructions.
Generated assets are excluded from Git. See [history overview](../project-history.md)
and [current setup](../setup.md).

---

## Generate a mesh

```sh
uv run scripts/generate.py /path/to/object.png --model full
uv run scripts/generate.py /path/to/object.png --model mini
```

### Generate from multiple views (2mv)

Install the separate standard 2mv checkpoint into the existing environment:

```sh
uv run scripts/setup_multiview.py
```

This downloads only `config.yaml` and `model.fp16.safetensors` (about 4.9 GB)
from `tencent/Hunyuan3D-2mv/hunyuan3d-dit-v2-mv`, verifies their SHA-256 hashes,
and records provenance. It pins revision `3a761b539b29fe4ff64714813aa9560fd66f5de0`.
The checkpoint includes the shape model, image conditioner and VAE; another
Python environment, separate VAE download, and different Paint weights are not needed.

Put separate transparent PNGs in one folder, named `front.png`, `left.png`,
`back.png`, and optionally `right.png`. Our runner requires `front.png` plus at
least one other named view. It ignores other filenames, including style-reference
images. Use consistent pose, clothing, proportions and framing across views.
Follow Tencent's view labels: the example `left.png` is a profile facing image-left.

The recorded run used the following paths. These output folders already exist
on the original machine; choose fresh folders when reproducing it:

```sh
uv run scripts/generate.py assets/peasant-turnaround --model mv \
  --output-dir assets/peasant-mv-setup
```

This uses the same 50-step, resolution-128, chunk-1024 defaults and CPU offload
as the single-image runner. It records each view's hash and background-removal
status, saves processed copies in `views/`, and saves the front as `input.png`
for the existing Paint command:

```sh
uv run scripts/paint.py assets/peasant-mv-setup/01-dense.glb \
  --output-dir assets/peasant-mv-setup/01-dense-paint
```

The default output folder without `--output-dir` is `assets/<folder name>-mv`.
Use a fresh output directory for each generation. The existing `--resolution`,
`--target-triangles`, and other generation options also apply to 2mv. Multiview
guides shape; our Paint runner still uses the front reference image.

The generated reference images are approximations, not exact renders of a
shared mesh. Multiple views do not guarantee matching anatomy or low-poly topology.
See [Tencent's 2mv model](https://huggingface.co/tencent/Hunyuan3D-2mv) and
[official example](https://github.com/Tencent-Hunyuan/Hunyuan3D-2/blob/main/examples/shape_gen_multiview.py).

Check view mapping and preprocessing without loading model weights:

```sh
uv run scripts/test_multiview_inputs.py
```

#### Verified on this machine

The generated front/left/back peasant references completed a full 50-step 2mv
run at resolution 128 in **160.32 seconds**, including model loading, on the
RTX 3050. Peak allocated PyTorch VRAM was **2764.0 MiB**. The saved mesh has
**38,162 triangles**. The result is `assets/peasant-mv-setup/01-dense.glb`, with
input provenance and measurements in its `generation.json`. This confirms the
three-view execution path; it does not establish reconstruction accuracy or
animation-ready topology. A subsequent Paint run on this dense mesh completed;
its input hashes, settings and results are recorded in
[`paint.json`](../../assets/peasant-mv-setup/01-dense-paint/paint.json).
The textured GLB and atlas are generated assets excluded from Git.

### Optional triangle budget

To also produce a mesh within a triangle budget:

```sh
uv run scripts/generate.py /path/to/object.png --model mini --target-triangles 2000
```

This preserves `01-dense.glb` and writes `02-lowpoly.glb` using CPU quadric
edge-collapse simplification. It produces triangles, not Quadriflow quads.
The target is an upper budget, not a promise of exactly that count. If topology
preservation prevents reaching it, the command reports an error and keeps the
dense mesh. It never exports a low-poly result above the requested budget.

For a mesh already generated, change the budget without running the model again:

```sh
uv run scripts/reduce_mesh.py assets/my-object/01-dense.glb --target-triangles 2000
```

The standalone command defaults to `02-lowpoly.glb` beside the input and records
the result in `02-lowpoly.json`. Use `--output path/to/another.glb` for another
budget; existing files are not overwritten. Already-small meshes retain their
geometry. This stage handles untextured geometry; UVs and materials are not
transferred, so finish reduction/remeshing before texturing. Aggressive reduction
can lose surface detail even when topology is preserved.

`--model full` selects the original Hunyuan3D-2.0; `--model mini` selects the
standard Hunyuan3D-2mini. Full is the default when `--model` is omitted. Both
downloaded models are undistilled, so both use 50 steps by default.

The default output directories are `assets/object-full/` and
`assets/object-mini/`, respectively. You can choose a different destination with
`--output-dir assets/my-object`. Only the selected model is loaded into memory.

The defaults are 50 sampling steps, guidance 5, a 128-resolution mesh grid,
1024 decoder queries per batch, and seed 12345. CPU offloading keeps only one
model component on the GPU at a time. This preserves the selected model and its
standard decoder; no Turbo weights or FlashVDM replacement decoder are used.

Transparent PNGs work directly. For opaque images, background removal runs on
the CPU and downloads the U2Net background-removal weights on first use. Pass
`--keep-background` to skip that step. The Hunyuan weights load locally.

Each run writes:

```text
assets/my-object/
  input.png          # processed input with alpha
  01-dense.glb       # dense geometry, without textures
  02-lowpoly.glb     # optional: when --target-triangles is specified
  generation.json   # settings, source hashes, timing and peak GPU memory
  notes.md          # short summary
```

Use a fresh output directory for each run; existing results are preserved.
Open `01-dense.glb` in Blender with File > Import > glTF 2.0.

For more surface detail, try `--resolution 256` in a new output directory.
Higher resolution increases extraction cost and may require smaller `--chunks`.
More sampling steps mostly increase runtime. Sampling memory also depends on
guidance and model size, so lowering extraction resolution will not resolve
every out-of-memory error.

### Verified on this machine

The bundled `assets/demo.png` from the upstream checkout completed 50 steps at
resolution 128 on the RTX 3050 in 94.81 seconds, including model loading. PyTorch
reported 2516.9 MiB peak allocated GPU memory and 2828.0 MiB peak reserved memory;
these figures exclude the desktop and other applications. The resulting mesh
has 79,392 triangles, is watertight, and has one connected component.

The result is `assets/setup-demo/01-dense.glb`, with measurements recorded in
`assets/setup-demo/generation.json`. This verifies the transparent-image path
and the default generation settings. Higher resolutions and automatic background
removal have not been tested by this sample run.

The same image, seed, step count and resolution also completed with `--model
mini` in 31.54 seconds, including loading, with 2252.5 MiB peak allocated GPU
memory. Its output is `assets/setup-demo-mini/01-dense.glb` (74,448 triangles).
These are individual setup measurements rather than a controlled benchmark.

Both sample meshes were reduced to 2,000 triangles and remained watertight.

## Run Python

From this directory:

```sh
uv run python
```

Or activate the environment for a terminal session:

```sh
source .venv/bin/activate
python
```

## Verify the environment

```sh
uv run scripts/check_environment.py
```

This checks Hunyuan imports, NVIDIA GPU access, FP16 matrix multiplication and
attention, marching-cubes mesh extraction, PyMeshLab, and a GLB export/import.
It does not download weights or run the trained model.

## Dependencies

- Python 3.11 in `.venv/` (managed by `uv`).
- PyTorch 2.7.1 and torchvision 0.22.1 from the official CUDA 12.6 wheel index.
- Diffusers 0.33.1 and Transformers 4.51.3 pinned for the Hunyuan3D-2 API.
- Hunyuan installed in editable mode from `third_party/Hunyuan3D-2/`.
- Complete dependency versions recorded in `uv.lock`.

This environment targets Linux x86-64 with an NVIDIA GPU. PyTorch wheels supply
the CUDA runtime; the machine's NVIDIA driver supplies GPU access. Paint's two
native extensions are built with the [local toolchain in the Paint chapter](paint.md#build-the-paint-dependencies). The
geometry pipeline can use the standard `mc` mesh extractor.

## Recreate the environment

The upstream checkout is ignored by Git. To recreate it in a fresh copy:

```sh
git clone https://github.com/Tencent-Hunyuan/Hunyuan3D-2.git third_party/Hunyuan3D-2
git -C third_party/Hunyuan3D-2 checkout f8db63096c8282cb27354314d896feba5ba6ff8a
python3 scripts/setup_paint.py
uv run scripts/check_environment.py
```

For an existing checkout, `uv sync --locked` restores the environment using the
recorded dependency versions.

## Model files

Each downloaded checkpoint has its own matching config and provenance record:

```text
models/hunyuan3d-2/hunyuan3d-dit-v2-0/
  model.fp16.safetensors
  config.yaml
  model-info.json
models/hunyuan3d-2mini/hunyuan3d-dit-v2-mini/
  model.fp16.safetensors
  config.yaml
  model-info.json
models/hunyuan3d-2mv/hunyuan3d-dit-v2-mv/
  model.fp16.safetensors
  config.yaml
  model-info.json
```

The full checkpoint was verified against Tencent's published SHA-256:
`360bc281fc956d4acac0c3d36d5ec0ebf8cdddbf4b8892e894d12419388d479b`.
The mini checkpoint was also verified:
`3cc66f3bea33e4062b7dbc875ffe1d70c4888914aec3e91b60f94e9bd01b522b`.
The 2mv checkpoint was verified:
`d36f5881bcdc56726b73e517cd444c13c60732431622da7268145355c8d38e9c`.
All three contain their shape model, image conditioner and standard VAE decoder.
No separate VAE files are required. Original copies in Downloads are preserved.

The full config is pinned to Hugging Face revision
`9cd649ba6913f7a852e3286bad86bfa9a2d83dcf`; the mini config uses revision
`f90a0f7df7d5e6f71109cf333f6a95a0ae3194a6`.
`model-info.json` records the upstream identity and checksums. Preserve all
three files for each model when moving the setup; `models/` is ignored by Git.

The runner uses explicit Accelerate offload hooks because the upstream
convenience method references a missing `components` attribute in the pinned
code revision. It sets the sampling device to CUDA and offloads the conditioner,
denoiser and decoder in sequence. The upstream checkout is unmodified.

Official sources:

- [Hunyuan3D code](https://github.com/Tencent-Hunyuan/Hunyuan3D-2)
- [Original Hunyuan3D-2.0 weights](https://huggingface.co/tencent/Hunyuan3D-2/tree/main/hunyuan3d-dit-v2-0)
- [Original Hunyuan3D-2mini weights](https://huggingface.co/tencent/Hunyuan3D-2mini/tree/main/hunyuan3d-dit-v2-mini)
- [Hunyuan3D-2mv weights](https://huggingface.co/tencent/Hunyuan3D-2mv/tree/main/hunyuan3d-dit-v2-mv)
- [PyTorch wheel installation](https://pytorch.org/get-started/previous-versions/)
