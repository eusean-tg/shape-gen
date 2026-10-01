---
title: "BPT reconstruction experiments"
summary: "Original BPT reconstruction settings, environment recipe and RTX 3050 measurements."
kind: "history"
status: "historical"
topics: ["bpt", "geometry"]
read_when: "Trace the original BPT experiment; use current setup for installation."
---
# BPT reconstruction experiments

Archived from the former README on 2026-09-30. “Latest,” paths, measurements and
commands below describe historical runs, not current install instructions.
Generated assets are excluded from Git. See [history overview](../project-history.md)
and [current setup](../setup.md).

---

## BPT: learned low-poly reconstruction

BPT has a separate `.venv-bpt` environment. It takes an existing mesh and
predicts a new triangle mesh from sampled surface points. Run it with:

```sh
.venv-bpt/bin/python scripts/retopo_bpt.py assets/peasant-mv-setup/01-dense.glb \
  --output-dir assets/my-peasant-bpt
```

The output directory must be new or empty. Outputs include `02-bpt.glb`,
`02-bpt.obj`, sampled input points, generated tokens, and `bpt.json` with
provenance, timings, peak PyTorch memory, and topology checks. The output is
untextured, with the source coordinate system and scale restored. It has new
connectivity; existing UVs, materials, skinning, and shape keys do not transfer.

Controls:

- `--seed 12345`: sampling seed.
- `--temperature 0.5`: token sampling temperature; lower is less random.
- `--max-tokens 10000`: generation safety limit, **not a triangle budget**.
  Hitting this limit before the model's end token is reported as a failed,
  incomplete generation; tokens remain saved for diagnosis.
- `--encoder-device cpu`: run point encoding in FP32 on CPU, if extra GPU
  headroom is needed. Mesh generation still uses CUDA FP16.

The runner loads the checkpoint on CPU, runs the point encoder once, then
releases the encoder from CUDA before loading the mesh-generation network.
It uses FP16 weights, cached attention, batch size one, and inference mode.
No weight quantization or retraining is applied. The original BPT checkout is
unchanged. The verified checkpoint contains unused DeepSpeed optimizer
metadata; the loader maps its three metadata types to inert local containers
under PyTorch's `weights_only` loader, avoiding a DeepSpeed dependency.

### Recreate the BPT environment

```sh
git clone https://github.com/Tencent-Hunyuan/bpt.git third_party/bpt
git -C third_party/bpt checkout 4e6510e7ebaac6d21f558252ad7eb573aed0234a
uv venv .venv-bpt --python 3.11
uv pip install --python .venv-bpt/bin/python -r config/bpt-lock.txt
.venv-bpt/bin/python scripts/setup_bpt.py
```

`config/bpt-requirements.txt` lists direct inference dependencies;
`config/bpt-lock.txt` pins the tested environment, including the CUDA 12.6
PyTorch wheel. Setup downloads the 1.64 GB official checkpoint from
`whaohan/bpt` at revision `4a7c93a2691b38682fc33ba8a414f2bf849700e3`,
verifies SHA-256, and records `models/bpt/model-info.json`.

### Verified BPT result on the RTX 3050 8 GB

`assets/peasant-bpt-staged/02-bpt.glb` completed normally (model end token,
4,789 generated tokens) with the default settings:

| Measurement | Result |
| --- | --- |
| Input / output triangles | 38,162 / 2,279 |
| Output vertices | 1,152 |
| Loading + encoding + generation + export | 105.48 seconds |
| Autoregressive generation | 100.62 seconds |
| Peak allocated / reserved PyTorch VRAM | 1,992.8 / 2,238.0 MiB |

Memory figures exclude other applications and CUDA overhead. This confirms
that this checkpoint and example fit the 3050 using staged FP16 inference;
longer generations may use more memory. The upstream 12 GB estimate is not
a measured requirement for this runner. No INT8/INT4 quantization was needed.

Blender reopened and rendered the GLB successfully. The silhouette, limbs,
collar, and pouch remain recognizable with broad polygonal facets. Fine facial
detail, the belt buckle, and the tunic hem are simplified. This is a useful
draft, not finished animation topology: it has 37 boundary edges, 9 edges
shared by more than two faces, and 5 connected components (2,261 triangles in
the main component, with 18 triangles in small components).

Review `assets/peasant-bpt-staged/preview.blend` or its `previews/` images.
`geometry-review.json` records an approximate sampled-surface comparison:
mean bidirectional distance is 0.30% of character height. This average does
not measure detail preservation or topology quality.

The optional CPU encoder and incomplete-generation handling were also checked
with a one-token limit: inference ran, reported failure without an end token,
and saved diagnostics without exporting an incomplete mesh.

