---
title: "Hunyuan → BPT: Makima parameter audit"
summary: "Input masking and HY/BPT parameter trials; improved braid gap but worse face/knees."
kind: "research"
status: "historical"
topics: ["hunyuan", "bpt", "tuning"]
read_when: "Assess tuning tradeoffs without treating one candidate as a universal preset."
---
# Hunyuan → BPT: Makima parameter audit

Experiments started 2026-09-18 and continued after midnight on 2026-09-19 MYT.
Machine: RTX 3050 8 GB, staged model offload, existing installed checkpoints.
Scope: improve the existing geometry pipeline before trying TRELLIS. These are
isolated experiments, not changes to API defaults or the accepted character.

## Main result — revised after visual review

**The original-background candidate is not an accepted overall upgrade.** The
user identified worse face and rear-knee quality. Follow-up close-up renders
confirm a more pronounced horizontal facial recess in the BPT candidate and
angular ledges where the dense meshes have rounded fabric folds. The larger
braid gap is a useful capability demonstration, but does not outweigh these
regressions. The original BPT is again the comparison preview's default; this
experiment remains available with an explicit quality-tradeoff label.

See the face/knee comparisons in the [gallery](http://localhost:5173/makima-knob-audit/gallery.html)
and `assets/makima-knob-audit/detail-renders/`. Dense face differences are subtler
than the BPT differences, so blaming only Hunyuan or only masking would be too
strong. No texture test was performed; color/normal maps could improve appearance
but would not remove the geometric recesses, ledges or silhouette errors.


We had not exhausted the useful levers. In this case, changing input preparation
made a larger difference to the braid gap than increasing extraction resolution.
Using the original white-background views produced a clearer upper braid/back
gap, and **that gap survived BPT**. This is the best inspected candidate for the
specific separation problem, not a claim that every aspect of it is superior.
The braid remains much more angular and simpler than the reference.

- [Clean dense candidate](../../assets/makima-knob-audit/mv-original-fixed/r384-clean.glb):
  256,902 triangles, watertight, consistent winding.
- [BPT candidate with two tiny holes closed](../../assets/makima-knob-audit/bpt-mv-original/02-bpt-closed.glb):
  2,178 triangles, watertight, consistent winding, no non-manifold edges.
- [Raw BPT candidate](../../assets/makima-knob-audit/bpt-mv-original/02-bpt.glb):
  2,176 triangles, two triangular boundary loops (six boundary edges), no
  non-manifold edges. The closed copy adds exactly two triangles, without smoothing
  or remeshing. It is not a rig/deformation or self-intersection certification.

BPT was run on the raw dense candidate; its separately saved clean dense copy
only removes degenerate/duplicate geometry. The closed BPT copy is a subsequent
small-hole repair. These distinctions are recorded in each `cleanup.json`.

## Review and evidence

- [Interactive comparison](http://localhost:5173/makima-knob-audit/)
- [Matched clay renders](http://localhost:5173/makima-knob-audit/gallery.html)
- [Experiment files and scripts](../../assets/makima-knob-audit/)
- [Original Makima and LATO.2 review](makima-geometry-review-2026-09-18.md)

Each shape run stores arguments, input hashes, checkpoint information, timing,
memory and output geometry checks in `trial.json`. Each BPT run has `bpt.json`,
the actual conditioning points and generated codes. Logs and saved latent
samples are retained. All GPU experiments acquire the same lock as the API.

## Baseline

| Stage | Actual settings | Result |
|---|---|---|
| Shape | HY3D-2mv, four views, seed 12345, 50 steps, guidance 5, resolution 192, automatic background removal | 62,648 triangles; watertight |
| BPT | 4,096 area-sampled points + normals, seed 12345, temperature .5, top-k 50 / top-p .95, 10,000-token cap | 2,409 triangles, EOS at 5,080 tokens; 15 boundary edges, no edges with >2 incident faces |

Jobs: `a1faf1d3c76a48e093344a8875d7445c` and
`3fd71d263c3c401286076f56ee6337ed`.

The original lower braid already has an air gap. The problematic regions are
the upper braid/neck/back junction and the side locks near the shoulders.
Calling the entire ponytail fused is inaccurate.

## Levers and interpretation

### Input preparation and views

Automatic background removal partly removes the face in the side reference.
The pipeline composites alpha over white, then crops to the nonzero-alpha
bounding box and adds padding independently per view. Thus segmentation also
affects apparent scale and framing.

Feeding the original opaque white-background images, using the same 2mv model,
seed, steps and guidance, creates a visibly larger upper braid/back gap. This
experiment changes both the mask and crop/framing; it does not isolate which
change caused the improvement. It is a useful candidate, not evidence that
background removal should always be disabled. Cluttered backgrounds still need
appropriate isolation.

Single-view mini and full were also tested using the processed front view.
Both miss the long rear braid. This compares practical input/model choices;
it is not a controlled architecture ranking because those models cannot consume
the same four views. Mini may outperform full on other inputs.

### Extraction resolution and isosurface threshold

The original saved latent was extracted at 192, 384 and 512, holding the sampled
shape fixed. Resolution 512 gives a smoother surface, but retains the same
unwanted joins. More marching-cubes cells cannot invent a gap absent from the
learned field. The 384 and 512 meshes contain 250,938 and 446,130 triangles.

Isosurface levels −.02, 0 and +.02 were tested at each resolution. These small
global threshold changes do not visibly solve the main joins. They are field
thresholds, not calibrated physical distances or semantic hair-separation
controls. Large shifts can damage thin features elsewhere.

`chunks` changes the query batch size and memory/performance tradeoff. It is
not a detail control. The checkpoint's trained latent length is also not a
free quality setting: mini uses 512 latent tokens, full/mv use 3,072 here.

### Shape guidance and step count

Lowering Hunyuan guidance from 5 to 3 and increasing its steps from 50 to 75
were separately tested at resolution 384. Neither visibly opened the unwanted
joins in the processed-view shape. The 75-step run took approximately 278 seconds
including loading and extraction. More steps are not a reliable separation dial.

### BPT sampling and generation

The experiment freezes the *original saved conditioning points* for the
temperature .3 and generation-seed 24680 runs. This separates BPT generation
randomness from its ordinarily seed-dependent surface sampling.

Other candidates use farthest-point coverage sampling (4,096 points), or 8,192
area-sampled points. These use a separately saved candidate cloud, so comparisons
against the historical original include a changed random sample. The newer
trimesh version in the CPU sampling environment uses a different RNG path;
`np.random.seed` alone does not reproduce that cloud. The saved NPY files and
their hashes are the reproducible inputs for these completed trials. Do not
infer a universal sampling-method advantage from one mesh/one cloud.

8,192 points is an experiment outside the advertised 4,096-point recipe, even
though the encoder accepts it. Extra points do not expand its fixed compressed
conditioning representation. Farthest-point sampling improves spatial coverage
but may underrepresent useful broad surfaces or change the training distribution.

The source mesh is normalized to a 1.9-wide longest dimension. This checkpoint
uses 128 coordinate bins per axis: one bin corresponds to approximately 0.82%
of the source's longest bounding-box dimension. Small gaps and thin features
therefore face a second bottleneck after Hunyuan. Raising `quant_bit` changes
the learned vocabulary and requires compatible weights; it is not a valid
inference-time precision switch.

The original BPT sample ends voluntarily at 5,080 tokens. Raising a 10,000-token
cap cannot make that sample more detailed. The cap is neither a triangle target
nor a minimum output length. Temperature and seed produce alternative meshes,
not a monotonic quality dial. Top-k/top-p remain 50/.95 in these trials.

The 512-resolution source produced a 2,230-triangle BPT result with 24 boundary
edges and five non-manifold edges: more dense input triangles did not improve
this reconstruction. The original-background source produced 2,176 triangles
and retained its larger upper braid gap. The coverage-sampled candidate had
2,511 triangles and nine boundary edges, but remained visibly coarse and did
not establish an overall fidelity advantage. Temperature .3 retained 15 boundary
edges; changing only the generation seed yielded seven boundary edges and two
non-manifold edges. These are individual candidate outcomes, not statistical
benchmarks of the settings.

The 8,192-point trial completed successfully but produced 2,302 triangles,
16 boundary edges and five non-manifold edges, without a visible braid-detail
improvement. There is no reason from this result to promote it over the standard
4,096-point recipe. All completed experiments fit the 8 GB card; the largest
reported PyTorch allocation was about 2,894 MiB, excluding desktop, CUDA context
and other processes. Reserved memory is recorded separately in `results.json`.

## Recipe tested for gap preservation — not an accepted overall preset

1. For these already clean white-background references, keep all four views and
   use `keep_background: true`. Inspect masks and framing for each new subject;
   this is not a universal background-removal default.
2. Keep mv / 50 steps / guidance 5 / seed 12345 for this candidate. Use 384
   extraction locally when surface smoothness matters; 512 was not a useful
   BPT quality upgrade here. The API currently caps resolution at 256.
3. Inspect the dense mesh's actual gaps before BPT. Reject unsuitable shapes
   here; a high triangle count alone says little about semantic fidelity.
4. Use standard BPT conditioning and temperature .5, then check topology and
   compare the reconstruction visually. Keep the saved candidate above as the
   best inspected braid-separation result from this pass.
5. If remaining feature fidelity is inadequate, another shape representation or
   part-based workflow is more promising than spending indefinitely on the
   resolution/steps/point-count settings tested here. TRELLIS remains a separate
   future experiment, with memory measured on this machine.

## Extraction implementation and validation

The installed upstream `HierarchicalVolumeDecoding` constructs a scale tensor
with integer grid-index dtype, truncating the sub-unit cell width to zero. Its
unqueried NaN sentinel can also create invalid marching-cubes vertices.
The first two attempted fast extractions failed, after successfully saving
their latent samples. They are retained as failed trials, not counted as results.

`assets/makima-knob-audit/hierarchical_decoder.py` copies that class at runtime
and fixes these issues **only in the experiment**: floating-point query indices,
and interpolated coarse field values outside the queried surface band. The
production runner uses the vanilla decoder, so its original result was not
affected by this fast-path defect.

Validation:

- Analytic sphere: vanilla vs corrected hierarchical extraction both produced
  2,888 triangles; maximum nearest-vertex difference 3.58e-7.
- Original Makima latent at 192: both produced 31,322 vertices / 62,648 triangles;
  maximum nearest-vertex difference 7.33e-6, mean 1.13e-8 in normalized coordinates.
- This is evidence for this implementation on these inputs, not a general
  equivalence proof: adaptive extraction may miss a component absent at its
  initial coarse grid. Production adoption requires broader validation.
- Some new dense meshes contain a few zero-area marching-cubes faces. Removing
  degenerates/duplicates makes the original-background, mini and full candidates
  watertight without reconstructing their surfaces; see `degeneracy-check.json`.

## Architecture limits and remaining options

Hunyuan's paper describes a signed-distance field decoded by marching cubes.
That representation can express overhangs, enclosed cavities and separated
volumetric parts. A thin, open sheet with free boundaries is a different problem
from a watertight object with an overhang. These experiments do not support
the blanket claim that Hunyuan cannot make an overhang.

However, an image-conditioned model may predict a filled join where a person
expects a narrow gap. Increasing extraction resolution cannot reverse that
prediction. Better silhouettes, consistent side/back views, preserving visible
gaps during input preparation, and trying shape candidates are meaningful levers.

Not exhausted in this bounded pass: additional Hunyuan seeds, higher guidance,
view subsets, new reference angles, controlled mask-vs-framing isolation,
region-weighted sampling, and BPT top-k/top-p sweeps. None is a guaranteed fix.
Separately generating/reconstructing hair or accessories could allocate more
spatial precision to them, but requires segmentation, assembly and seam work;
it is a workflow change rather than another scalar knob.

BPT is the current convenient reconstruction stage, not an unavoidable stage of
all pipelines. It has its own information and coordinate limits even with a
good source mesh. A good input is necessary but is not a fidelity guarantee.

VRAM results here depend on staged offload and workload. They justify measuring
another model with an appropriate low-memory implementation; they do not prove
TRELLIS will fit, since activation and sparse-grid memory can behave differently.
No TRELLIS installation was started in this pass.

## API implications

Already available: `model`, `steps`, `guidance`, `seed`, `keep_background`,
and BPT `temperature` / `max_tokens`. Production shape resolution currently
accepts only 64/128/192/256. The 384/512 extractions, alternative point clouds,
isosurface thresholds and corrected hierarchical decoder are **local experiments**,
not newly deployed API capabilities. No service restart is needed for this report.

## Sources

- [Hunyuan3D 2.0 paper, §3.1](https://arxiv.org/html/2501.12202v1): SDF and marching-cubes architecture.
- [Official BPT repository](https://github.com/Tencent-Hunyuan/bpt): model and inference recipe.
- Local installed code: `scripts/generate.py`, `scripts/retopo_bpt.py`,
  `shape_api/operations.py`, and `third_party/bpt/config/BPT-open-8k-8-16.yaml`.

## Completed trial measurements

| Trial | Triangles | Boundary edges | Non-manifold edges | Peak allocated MiB |
|---|---:|---:|---:|---:|
| full/r384-iso0.glb | 245,520 | 0 | 6 | 2,517 |
| mini/r384-iso0.glb | 266,708 | 0 | 4 | 2,253 |
| mv-guidance3/r384-iso0.glb | 247,568 | 0 | 0 | 2,894 |
| mv-original-fixed/r384-iso0.glb | 256,908 | 0 | 6 | 1,347 |
| mv-resolutions/r192-iso0.glb | 62,648 | 0 | 0 | 2,294 |
| mv-resolutions/r192-iso-0.02.glb | 62,824 | 0 | 0 | 2,294 |
| mv-resolutions/r192-iso0.02.glb | 62,536 | 0 | 0 | 2,294 |
| mv-resolutions/r384-iso0.glb | 250,938 | 0 | 0 | 2,294 |
| mv-resolutions/r384-iso-0.02.glb | 251,476 | 0 | 0 | 2,294 |
| mv-resolutions/r384-iso0.02.glb | 250,448 | 0 | 0 | 2,294 |
| mv-resolutions/r512-iso0.glb | 446,130 | 0 | 0 | 2,294 |
| mv-resolutions/r512-iso-0.02.glb | 447,200 | 0 | 0 | 2,294 |
| mv-resolutions/r512-iso0.02.glb | 445,136 | 0 | 0 | 2,294 |
| mv-steps75/r384-iso0.glb | 250,580 | 0 | 0 | 2,894 |
| bpt-8192 | 2,302 | 16 | 5 | 2,059 |
| bpt-coverage | 2,511 | 9 | 0 | 2,085 |
| bpt-mv-original | 2,176 | 6 | 0 | 1,963 |
| bpt-mv512 | 2,230 | 24 | 5 | 1,984 |
| bpt-seed24680 | 2,551 | 7 | 2 | 2,096 |
| bpt-temp03 | 2,469 | 15 | 0 | 2,061 |

Memory is PyTorch allocation, not total GPU usage. Shape extraction trials that reuse a saved latent exclude diffusion sampling. All resolutions/levels in one trial share its run-level peak. Raw marching-cubes degenerate faces are included in the table; cleaned candidate metrics are recorded separately.
