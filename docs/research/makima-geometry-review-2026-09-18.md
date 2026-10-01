---
title: "Makima: Hunyuan, BPT and LATO.2 comparison"
summary: "API-sourced Makima HY/BPT comparison and initial LATO.2 connectivity findings."
kind: "research"
status: "historical"
topics: ["hunyuan", "bpt", "lato2"]
read_when: "Separate defects inherited from dense geometry from reconstruction defects."
---
# Makima: Hunyuan, BPT and LATO.2 comparison

Date: 2026-09-18. Experimental assets: `assets/makima-geometry-review/`.

## Inputs verified through the API

Downloaded both jobs through the authenticated API and verified artifact checksums.

| Stage | Job | Settings | Output |
|---|---|---|---|
| Hunyuan | `a1faf1d3c76a48e093344a8875d7445c` | **2mv**, four views, seed 12345, 50 steps, resolution 192, guidance 5 | 31,322 vertices, 62,648 triangles |
| BPT | `3fd71d263c3c401286076f56ee6337ed` | Same dense mesh, seed 12345, temperature 0.5, 10,000-token cap | 1,209 vertices, 2,409 triangles |

Dense asset SHA-256: `edd2455717fb9638c3f1c880cda9e7ba43612e92e164223b527ab46430e3821e`.
BPT asset SHA-256: `9b150563c8a33748560b648a7295d37ee310c946f0e3ecfbc3019964303d34bd`.

The API supports `parameters.model = "mini" | "full" | "mv"`; **mini is the
default**. Mini/full accept only `inputs.front`; mv requires front and at least
one additional view. This particular character used mv, not mini or full.

## Direct visual observations

Neutral clay renders remove texture ambiguity. The lower braid **does have an
air gap behind the torso** in the dense side view, and this survives BPT. Calling
the entire ponytail fused would be inaccurate. The upper braid has a broad
merged-looking join against the neck/upper back; the side hair also joins the
collar/shoulder area. These shapes already appear in Hunyuan's dense result.
BPT simplifies them further and loses much of the braid's surface detail.

- [Dense side](../../assets/makima-geometry-review/dense-side.png)
- [BPT side](../../assets/makima-geometry-review/bpt-side.png)
- [Dense back quarter](../../assets/makima-geometry-review/dense-back-quarter.png)
- [BPT back quarter](../../assets/makima-geometry-review/bpt-back-quarter.png)

Both are one connected component. This fact alone cannot diagnose fused hair:
hair attached at the scalp can legitimately share a connected component.
Dense is watertight. BPT has 15 boundary edges, no non-manifold edges, consistent
winding, and is not watertight. These are descriptive checks, not rigging or
visual-quality guarantees.

## LATO.2 experiment

Completed: same dense input, seed 12345, batch size one, target 1,200 vertices
to roughly match the existing BPT budget. Vertex conditioning is not an exact
triangle limit. Actual vertex count: 1,252. Upstream defaults: V-Flow 24 steps,
T-Flow 50 steps, guidance 3, conditioning render azimuth 45 / elevation 30.

The official [LATO.2 runner](https://github.com/LoHhhha/LATO.2) conditions on a
render of the input mesh and a voxel scaffold derived from that mesh. This test
does not feed the original Makima image to the final mesh model. It can assess
preservation/reconstruction of existing geometry; it cannot establish reliable
recovery of hair structure missing from Hunyuan.

Environment: isolated `.venv-lato2`, upstream Python 3.10 / torch 2.6 CUDA 12.4;
checkpoints in `third_party/LATO.2/ckpt`. Production environments and API runners
are unchanged. Uses the shared advisory GPU lock when running inference.

Local dependency adaptation: `third_party/lato2-trellis/o-voxel` imports its unused
texture postprocessor lazily, avoiding CuMesh/FlexGEMM/nvdiffrast dependencies for
the mesh-to-voxel path. Voxel extraction code is unchanged. Xformers is selected
through the upstream-supported sparse-attention backend setting.

### Measured results

| Output | Vertices | Triangles | Boundary edges | Edges with >2 faces |
|---|---:|---:|---:|---:|
| Existing BPT | 1,209 | 2,409 | 15 | 0 |
| LATO, default quad-ring filling | 1,252 | 2,933 | 8 | 661 |
| LATO, quad-ring filling disabled | 1,252 | 2,618 | 50 | 239 |

Default LATO completed in 36.38 seconds including imports/model loading; its
inference loop reported 23.83 seconds. The no-quad run took 32.69 seconds overall,
21.72 seconds in the loop. Both peaked at **5,470.6 MiB allocated / 5,544 MiB
reserved in PyTorch**. This excludes desktop/OpenGL/driver memory; the desktop
used about 1,611 MiB before inference. No CPU model offloading was required.
These timings are not directly comparable to the original BPT report's timer.

Both LATO raw meshes have inconsistent face winding. For viewing only, separate
copies use `trimesh.repair.fix_normals(multibody=True)`, which changes winding
without removing faces or changing vertices. They pass trimesh's winding check
afterward but retain the non-manifold edges. This does not guarantee a valid
outward surface where faces intersect or overlap. Original OBJ outputs remain.

All outputs have one **vertex-graph** connected component. Trimesh's face-adjacency
split reports 527/205 pieces for the two LATO meshes because that adjacency ignores
non-manifold edges; those numbers must not be described as 527/205 physically
disconnected body parts.

### Visual conclusion

LATO produces a more visible upper-braid/back gap in the side view and changes the
braid silhouette, but its head, shoulder and torso surfaces look rougher than BPT
at this budget. The original braid detail is still substantially simplified.
Together with the edge defects, this is **not a clear replacement for BPT on this
sample**. One seed on one character is not a general benchmark of either model.
The no-quad experiment isolates a postprocessing contribution to the defects;
disabling it does not solve the underlying topology problem.

- [LATO side, default](../../assets/makima-geometry-review/lato-1200-side.png)
- [LATO back quarter, default](../../assets/makima-geometry-review/lato-1200-back-quarter.png)
- [LATO side, no quad filling](../../assets/makima-geometry-review/lato-1200-noquad-side.png)
- [LATO GLB, normal-repaired](../../assets/makima-geometry-review/lato-1200/makima-normals.glb)
- [LATO GLB, no quad filling, normal-repaired](../../assets/makima-geometry-review/lato-1200-noquad/makima-normals.glb)

Mini/full comparisons remain available through the API. Neither was generated
in this experiment. To select mini, submit operation `hunyuan-shape`, supply only
`inputs.front` and set `parameters.model` to `mini`. For a useful comparison with
this mv run, explicitly match seed 12345, steps 50, resolution 192 and guidance 5;
the conditioning evidence necessarily differs (one image versus four).

## Reproduction on this machine

From `/home/sean/workspace/shape-gen`:

```sh
.venv-lato2/bin/python assets/makima-geometry-review/run_lato.py
LATO_LABEL=lato-1200-noquad LATO_FILL_QUAD_RINGS=0 \
  .venv-lato2/bin/python assets/makima-geometry-review/run_lato.py
.venv/bin/python assets/makima-geometry-review/measure_lato.py lato-1200
.venv/bin/python assets/makima-geometry-review/measure_lato.py lato-1200-noquad
```

Use a new `LATO_LABEL` for fresh runs to preserve existing outputs. This is a
local experimental runner, not an API operation. It honors the same GPU lock as
the API. No service restart or production changes were needed.

Reproducibility files in the experiment directory:

- `lato-provenance.json`: upstream commits and checkpoint hashes/revisions.
- `lato-environment.txt`: isolated Python package versions.
- `lato-voxel-import.patch`: the lazy-import adaptation.
- `lato-1200-run.json`, `lato-1200-noquad-run.json`: commands, times, memory.
- Each output's `geometry.json`: before/after normal-repair measurements.
- `render_compare.py`, `render_lato.py`, `render_lato_noquad.py`: CPU Blender renders.

The extension was compiled using the existing local CUDA 12.6 toolkit and GCC 13
host toolchain, targeting the 3050's sm_86 architecture. The runtime is torch
2.6.0+cu124. `o_voxel` was installed with `--no-build-isolation --no-deps`; its
needed runtime dependencies were installed explicitly. The lazy postprocessor
import avoids installing unused CuMesh/FlexGEMM/nvdiffrast. Sparse attention uses
xformers 0.0.29.post2; topology attention uses upstream PyTorch SDPA fallback
because FlashAttention is not installed. Geometry generation code is unchanged.
