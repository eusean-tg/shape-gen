# DeepMesh experiment

Local isolated experiment, 2026-09-19. Primary target: simple low-poly character
art, using the teal peasant. Makima is a secondary difficult example. One seed
per source; no broad parameter sweep. Production API and accepted assets unchanged.

## Reproduce

From `/home/sean/workspace/shape-gen`:

```sh
.venv-deepmesh/bin/python assets/makima-deepmesh/run_trial.py \
  assets/teal-peasant/dense/01-dense.glb \
  --output-dir assets/makima-deepmesh/NEW-teal
```

Use a new/empty output directory. Defaults: seed 12345, temperature .5, one
candidate, 16,384 surface points, sliding window 9,000. A 30,000-token or
900-second generation bound stops a runaway attempt. EOS is required; an
incomplete sequence is not exported as a successful mesh. These bounds are
not triangle-count controls.

## Environment and implementation

- Independent `.venv-deepmesh`, Python 3.10, Torch 2.6/cu124, xformers and
  FlashAttention 2.7.4.post1. See `environment-freeze.txt`.
- Official source: `third_party/DeepMesh`, revision in `code-manifest.json`.
- Official weights: `models/deepmesh/pytorch_model.bin`, verified against the
  publisher's LFS SHA256; pinned revision in `models/deepmesh/manifest.json`.
- The full checkpoint is strictly loaded with `weights_only=True`; no missing
  learned parameters are silently accepted.
- Source checkout is unchanged. `compat/lit_gpt` copies its Python package;
  only rotary and RMSNorm wrappers change, using FlashAttention's corresponding
  Triton kernels instead of separately compiled legacy extensions. Source and
  adapted hashes are recorded. This preserves the operations but is not a
  bit-identical-kernel claim.
- Weights remain FP32 and inference uses BF16 autocast, as in upstream sampling.
  The point encoder runs first, then moves off GPU before the autoregressive
  generator. No weight quantization, DDP, or batch repetition.
- All GPU trials acquire the API's existing `~/.cache/shape-gen/gpu.lock`.

## Geometry and sampling

The source is centered and scaled to a 1.9-wide longest bounding-box dimension,
following the repository's normalization helper. A seeded area sample of 50k
points supplies the 16,384-point cloud with face normals. The OBJ input path's
ZXY axis convention is retained. Sampling uses explicit RNG seeds and saves the
actual cloud; it is not bit-identical to the upstream unseeded dataset path.

Sampler equations, temperature convention, recursive hourglass cache and sliding
window refresh follow `sample.py`. Tokens and input points are retained. Raw
upstream-coordinate output is saved separately from the comparison GLB. The
learned decoder already returns source XYZ although conditioning uses ZXY. A
discrete-axis comparison against the source confirmed the final convention;
`finalize_coordinates.py` re-exports saved tokens without regeneration. The
comparison output restores scale and center only; it then merges
vertices, removes duplicate/degenerate faces, drops unused vertices and fixes
normals. There is no wrapping, smoothing, hole filling, or manual repair.

`trial.json` records settings, hashes, timing, memory and topology. PyTorch memory
figures exclude CUDA contexts, desktop use and some native allocations. A
successful numerical check or EOS does not certify visual quality or deformation.

## Review

`render-list.json` supplies matched CPU Blender renders. `render_trials.py` and
`render_details.py` skip existing images. `build_review.py` assembles the gallery
and model list; `check_preview.mjs` exercises model loading and gallery resources.

Preview: <http://localhost:5173/makima-deepmesh/>.
