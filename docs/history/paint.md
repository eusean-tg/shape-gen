---
title: "Hunyuan Paint experiments"
summary: "Original Hunyuan Paint proof of concept and historical native-build commands."
kind: "history"
status: "historical"
topics: ["paint", "texturing"]
read_when: "Inspect the early Paint results or build provenance."
---
# Hunyuan Paint experiments

Archived from the former README on 2026-09-30. “Latest,” paths, measurements and
commands below describe historical runs, not current install instructions.
Generated assets are excluded from Git. See [history overview](../project-history.md)
and [current setup](../setup.md).

---

## Paint an existing mesh with Hunyuan Paint

Shape generation does **not** need to run again. Paint takes an existing mesh
and a reference image. Delight first removes lighting from the reference;
Paint then generates six views, projects them onto UVs, and fills uncovered
texture areas.

```sh
uv run scripts/paint.py assets/peasant2/01-dense.glb --output-dir assets/peasant2/my-paint
```

The reference defaults to `input.png` beside the mesh. To use another image:

```sh
uv run scripts/paint.py /path/to/mesh.glb --image /path/to/reference.png --output-dir assets/my-paint
```

Defaults: standard Paint v2.0, 30 Paint steps, 50 Delight steps, seed 0, six
512-pixel generated views, 1024-pixel geometry renders and a 1024-pixel texture.
Options: `--steps`, `--seed`, `--texture-size {512,1024,2048}`, and
`--render-size {512,1024,2048}`. Higher texture resolution alone does not add
detail to the model's 512-pixel views.

The runner loads each network on CPU, enables model CPU offloading and VAE
slicing, and releases Delight before loading Paint. A local adapter fixes an
upstream device mismatch in learned prompt embeddings during offloading. The
upstream checkout is unchanged. All weights load locally, with network access
disabled for the runner.

Results go in a new or empty directory:

```text
03-textured.glb      # mesh with embedded color texture; import into Blender
basecolor.png       # separate copy of the texture atlas
reference.png       # centered input reference
delighted.png       # reference with lighting reduced
views/              # six normal, position, and generated color views
projection-mask.png # areas covered by projection, before filling gaps
paint.json          # settings, hashes, timings, GPU memory, success/failure
```

This produces a color texture, not a high-to-low normal bake or a full PBR
material set. Paint creates new UVs and may duplicate vertices at UV seams;
it does not reduce the triangle count. Source files are preserved. For later
retopology, either paint the finished low-poly mesh or transfer the dense
mesh's texture by baking onto the low-poly UVs.

### Verified paint proof of concept

`assets/peasant2/paint-poc-v2/03-textured.glb` was painted from the existing
`assets/peasant2/01-dense.glb` and its saved reference, without regenerating shape.
The default settings completed in **74.2 seconds**, including model loading,
with **4216.7 MiB peak allocated GPU memory** and **4376.0 MiB peak reserved**
(PyTorch measurements, excluding other applications). The export retains
**36,536 triangles** and embeds its **1024×1024** color texture.

The GLB was reopened and rendered in Blender. Clothing colors and the overall
character appearance transfer, including generated back-side coverage. This is
a working PoC, not a finished asset: the face and small details differ from the
reference, and patchy artifacts remain around the boots and underarms.

Open `assets/peasant2/paint-poc-v2/preview.blend` for a review scene, or inspect
the four renders in its `previews/` directory. To make these for another result:

```sh
blender --background --factory-startup --threads 8 \
  --python scripts/preview_mesh.py -- assets/my-paint/03-textured.glb
```

The preview command uses a separate Blender process and CPU rendering. It writes
`preview.blend` and `previews/` beside the mesh; rerunning it replaces those previews.

### Build the Paint dependencies

The native extensions are installed in this environment. To rebuild them:

```sh
python3 scripts/setup_paint.py
```

This sets up CUDA 12.6 compiler components and a GCC 13 host compiler under
`.toolchain/`, then builds `custom-rasterizer` and `mesh-processor` into `.venv`.
It does not install a system CUDA toolkit or change the NVIDIA driver. The
host compiler uses its own Linux headers because Ubuntu 26.04's GCC 15 and
system headers are newer than this CUDA compiler supports. Downloads are
checksum-verified; host packages are pinned in `config/paint-host-toolchain.txt`.
The extension targets this RTX 3050's CUDA architecture 8.6.

The complete model folders must be under `models/hunyuan3d-2/`:

```sh
uv run hf download tencent/Hunyuan3D-2 \
  --include 'hunyuan3d-paint-v2-0/*' 'hunyuan3d-delight-v2-0/*' \
  --local-dir models/hunyuan3d-2
```

Keep the complete folder trees. The pinned upstream Paint UNet loader reads
`diffusion_pytorch_model.bin`, even when its safetensors alternative is present.
The installed download was checked against the Hugging Face file listing and
weight checksums; `models/hunyuan3d-2/paint-model-info.json` records the results.

