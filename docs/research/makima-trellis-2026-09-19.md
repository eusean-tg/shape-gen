---
title: "Makima: TRELLIS and TRELLIS.2 on RTX 3050"
summary: "Staged TRELLIS/TRELLIS.2 geometry runs on 8 GB VRAM and later BPT comparison."
kind: "research"
status: "historical"
topics: ["trellis", "bpt", "vram"]
read_when: "Review measured geometry improvements, memory use and remaining detail loss."
---
# Makima: TRELLIS and TRELLIS.2 on RTX 3050

Date: 2026-09-19 MYT. Local geometry experiment; production API unchanged.

## Dense geometry result

**TRELLIS.2 runs on this 8 GiB RTX 3050, including the 1024 path.** Staging the
models between CPU RAM and GPU avoided an out-of-memory failure. This machine
has 64 GiB system RAM. We did not test the full texture pipeline or arbitrary
inputs, so this is not a general 8 GiB guarantee.

On the Makima front reference, the 1024 result after the demo's geometry export
has more defined collar flaps, tie, shirt hem and individual hair tips than the
prior single-front HY full result. The face remains coarse, especially the eye
region, nose and mouth. The rear knees still have fold ridges. It is a useful
dense-source candidate, not a demonstrated Meshy T2 replacement.

**The low-poly stage remains the limiting step in this trial.** Ordinary BPT
on the demo export fragmented badly; another cleanup alone did not fix it.
Visibility-filtered surface sampling produced a more coherent BPT result and
retained more of the tie/shirt outline, but it still oversimplifies the face and
hair and has topology defects. Conventional decimation reaches a similar
practical budget after cleanup, with visibly harsh face/scalp triangulation.
None is being promoted as the accepted character or a rig-ready upgrade.

The original TRELLIS fallback also ran, both with one image and with four views.
Those results look softer and do not provide a clear overall improvement here.
Its multiview output still joins the upper rear hair to the neck/back.

## Compare the artifacts

- [Interactive viewer](http://localhost:5173/makima-trellis/)
- [Matched clay renders, face and knee closeups](http://localhost:5173/makima-trellis/gallery.html)
- [TRELLIS.2 setup and reproduction instructions](../../assets/makima-trellis2/README.md)
- [Previous Hunyuan/BPT audit](makima-knob-audit-2026-09-19.md)

All renders use neutral clay, matching cameras and lights, and flat face
shading. They are a geometry comparison; there is no generated texture hiding
or emphasizing differences between runs.

## Inputs and fairness

TRELLIS.2 receives the existing processed front RGBA image from job
`a1faf1d3c76a48e093344a8875d7445c`. The native image preprocessing crops it and
composites it over black. No new background-removal model was loaded.
The front image does **not** reveal Makima's long rear braid. The resulting
rear hair is an inference, not a reconstruction of that unseen braid.

The original HY 2mv baseline and the older TRELLIS multi-image trial receive
four images. They have information unavailable to this TRELLIS.2 run. The
gallery includes the earlier **single-front HY full** run for a more useful
same-view comparison, but preprocessing, trained models and samplers differ.
This is a practical pipeline comparison, not a controlled architecture study.

The older TRELLIS four-image run uses the official stochastic multi-image
inference mode; it is not a separately trained multiview model. We did not
invent or test a corresponding TRELLIS.2 multi-image adaptation.

## Measured generation cost

| Run | Raw triangles | Elapsed generation/export | Highest stage PyTorch allocation |
|---|---:|---:|---:|
| TRELLIS original, front | 167,380 | 45.00 s | 1,352.2 MiB |
| TRELLIS original, four views | 162,784 | 44.84 s | 1,368.3 MiB |
| TRELLIS.2, 512 | 792,914 | 93.04 s | 2,685.1 MiB |
| TRELLIS.2, 1024 cascade | 3,132,280 | 131.71 s | 2,730.3 MiB |

Times include local model loading, inference and raw geometry export inside
the runner, but exclude environment setup and model downloads. First-use kernel
compilation affects these measurements. This is one run per setting, not a
throughput benchmark. PyTorch allocation does not include all CUDA contexts,
native libraries or the desktop; it must not be presented as total VRAM use.

The original TRELLIS runner explicitly performs FlexiCubes extraction on CPU.
TRELLIS.2 uses the official low-VRAM staging and its GPU geometry decoder.
There is no weight quantization. Source checkpoint precision is retained.
The 1024 path is the official 512-to-1024 shape cascade, not merely a finer
extraction of the 512 output. Both TRELLIS.2 runs in the table (512 and 1024
cascade) use seed 12345 and 12 steps per sampling stage. The original TRELLIS
front and four-view runs use seed 12345 and 25 steps per sampling stage.
The 1024 cascade includes both 512 and 1024 shape-latent sampling stages;
12 is not the total number of updates across the whole pipeline.

## Why the raw mesh is not the final export

The raw TRELLIS.2 outputs have visible tiny holes and many non-manifold edges.
At 1024, measured raw edge counts were 55,905 boundary and 67,600 edges shared
by more than two faces; winding was inconsistent. Judging only that raw mesh
would omit the cleanup used by the official demo.

The non-remeshing export branch was tested first at 512. It removed the edges
with more than two incident faces but left 35,989 boundary edges and inconsistent
winding. Trimesh normal correction did not resolve this. Those files are kept
as diagnostics rather than described as repaired final geometry.

The upstream example and app both enable narrow-band dual-contouring remeshing
with `band=1` and `project_back=0`. We reproduced its geometry stages, including
initial small-hole filling, then simplified to a 500k target (the example uses
1M). No UV parameterization or texture baking was needed for this experiment.
The 1024 result has 491,882 triangles, consistent winding, zero boundary edges
and 9,823 edges with more than two incident faces. It looks much cleaner, but
**is not manifold**. Remeshing changes the surface and can close sufficiently
narrow gaps. Neither a closed appearance nor zero boundary edges certifies
rigging readiness, self-intersection freedom or deformation quality.

## Reduction trials

The first BPT trial consumed the demo-remeshed 1024 mesh directly. It reached
EOS at 9,600 tokens (not the 10,000-token limit), took 285.73 seconds overall,
and produced only 1,676 retained triangles after the standard duplicate and
degenerate-face cleanup. There are 48 connected components, 304 boundary edges
and 87 edges with more than two incident faces. Visually the collar and hair
detail are largely lost. **Successful token completion did not produce a usable
low-poly replacement.**

The first Blender collapse-decimation control requested the same 1,676
triangles but stopped at 72,237. Blender's decimation ratio is not an exact
triangle constraint, especially with difficult topology. This failed attempt
is explicitly labelled in the gallery; it is not a matched-budget comparison.
Blender import reported 490,989 input polygons rather than the GLB's 491,882;
the source and imported counts are retained in their respective metadata.

An additional cleanup trial ran the non-remeshing CuMesh cleanup recipe *after*
the demo remesh, with a 200k target. This produced 189,699 triangles, 977 boundary
edges, no edges shared by more than two faces, and consistent winding on its
indexed mesh. It is still not watertight. This is an extra experimental stage,
not a claim that the official export performs this sequence.

The second BPT trial used this additionally cleaned mesh with unchanged BPT
settings. It reached the 10,000-token cap without EOS and **failed**. Its token
array is retained for diagnosis; no partial mesh is presented as a result.

Blender could reduce that cleaned input to 2,353 triangles when targeting the
original HY/BPT budget of 2,409. It preserves recognisable collar/tie and longer
hair tips, but the face and scalp are harshly triangulated. This is still not a
clean finished character. The exported GLB splits vertices along flat normals;
topology diagnostics use a separate position-welded copy, not those render-only
splits. That copy still has boundaries and non-manifold junctions, so visual
detail retention should not be confused with clean deformation topology.

### Visibility-filtered conditioning diagnostic

Narrow-band remeshing can introduce inner and outer surfaces close together.
Here the remesh roughly doubles total surface area relative to raw extraction
(1.844 versus 1.077 in the normalized coordinate system), while its signed volume
is small. These measurements are suggestive, not a valid solid-volume test on
the defective raw mesh. Uniform area sampling can condition BPT on both sides.

`exterior_cloud.py` tests a different point distribution on the *same* additionally
cleaned dense mesh. It draws 100,000 area samples, casts rays from outside the
bounding box along each sample's normal, and retains points when the first hit
is within 0.0002 normalized units of that surface. A random 4,096-point subset
then supplies the usual BPT conditioner. 31,335 candidates passed the visibility
test. This is not proof that the others were interior: recessed or occluded
outward surfaces may also be rejected. Normals are not guessed or flipped.
The same seed, temperature, top-k, top-p and token cap remain in effect.

This third BPT trial completed in 81.29 seconds, reaching EOS at 3,892 tokens.
It produced 1,789 triangles, 11 components, 145 boundary edges and 25 edges with
more than two incident faces; winding is inconsistent. Its highest measured
PyTorch allocation was 1,817.6 MiB. The face and bangs are still heavily reduced,
but the tie and shirt structure are more coherent than the first BPT trial.
Rear-knee folds remain angular. It is promising evidence that point selection
matters for this export, not a production-quality result or a clean causal
isolation of interior samples: the filter also changes visible surface coverage.

The decimation control has 2,353 triangles versus this BPT result's 1,789 and the
old HY/BPT baseline's 2,409. These are explicitly different budgets; the renders
do not establish an equal-count win for one reducer.

## Recommendation

Keep TRELLIS.2 as an experimental dense source. The 1024 run's collar, tie and
hair edges justify further use, and VRAM is demonstrably manageable on this
machine with staged inference. Do not replace the existing API default or
character with these low-poly candidates. The next useful work would preserve
those surfaces while repairing topology and allocating more geometry to the
face/hair, rather than assuming the usual BPT area-sampling pass will carry
every new detail through. Texture quality and animation were not tested here.

## Evidence and reproducibility

`assets/makima-trellis2/` contains raw and remeshed meshes, conditioning images,
saved latents, stage timings, topology measurements, source revisions and
environment freeze. The checkpoint manifest pins model revisions and records
hashes. The official DINOv3 checkpoint was obtained using approved HF access;
the runner validates its LFS checksum.

`assets/makima-trellis/` contains the older fallback runs, BPT comparison,
decimation control, renders and the static review UI. BPT stores its actual
sampled point cloud and generated token stream. All GPU runners use the same
file lock as the API to avoid overlapping inference jobs.

Browser verification loaded all 14 listed GLBs successfully and fetched all 84
gallery images, with no page errors or missing resources. The failed BPT trial
is labelled in the gallery and has no mesh entry. Validation is recorded in
`assets/makima-trellis/preview-validation.json`.

## Primary implementation sources

- [Official TRELLIS.2 repository](https://github.com/microsoft/TRELLIS.2)
- [Official TRELLIS.2 export example at the tested revision](https://github.com/microsoft/TRELLIS.2/blob/75fbf0183001ed9876c8dbb35de6b68552ee08bd/example.py)
- [Official TRELLIS repository](https://github.com/microsoft/TRELLIS)
- [Official TRELLIS.2 weights](https://huggingface.co/microsoft/TRELLIS.2-4B)

Conclusions above concern the saved local outputs; they are not claims about
all characters, other seeds, texture quality or Meshy's unpublished system.
