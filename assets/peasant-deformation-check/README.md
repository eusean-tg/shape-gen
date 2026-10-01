# Peasant deformation-area check

Completed 2026-09-17 on the HY Paint + imagegen peasant, **2,289 triangles**.

**Verdict:** suitable for a first rigging experiment. Moderate bend probes are
promising; deep bends and the tunic/hip region need attention. This is not an
animation-ready certification and is not UniRig output.

## Review files

- [Visual review](review.html): switch between textured and wireframe probes.
- [Topology review in Blender](topology-review.blend): original geometry with
  inspection overlays. Red marks open edges; orange marks edges with more than
  two adjacent faces. Hide the overlay collection to inspect the original mesh.
- [Editable bend probes](poses/bend-probes.blend): select **Peasant body**, open
  Object Data Properties → Shape Keys, and set one named probe to 1. Reset it to
  0 before trying another. All probes are saved at 0; the original rest mesh,
  UV coordinates and packed texture are preserved. These are diagnostic shape
  keys, not an armature or production animation.
- [Measured topology](topology.json), [probe parameters](poses/bend-probes.json),
  [self-intersection checks](pose-intersections.json), [saved-file validation](saved-file-validation.json).

## Findings

| Area | Observed result | Next action |
| --- | --- | --- |
| Shoulders / underarms | Both 60° raises have no detected self-intersections. Broad triangles and an angular underarm fold remain. Correcting the diagnostic weights greatly reduced stretching. | Test UniRig's shoulder placement and weights before deciding to add topology. Include overhead reach and upper-arm twist later. |
| Elbows | The tested screen-left 60° bend has no detected self-intersections. Both 90° bends select 11 intersecting faces each, around the joint/cuff. | Refine pivots and weights, then reassess the sleeve/cuff and joint topology. |
| Knees | The tested screen-left 60° bend has no detected self-intersections; the inner bend compresses. Both 90° bends select 17 intersecting faces each. | Tune knee weights, then consider a small local topology correction if deep flexion still fails. |
| Hips / tunic | The 45° leg lifts compress and fold the central tunic/crotch region: 8 selected intersecting faces on one side, 5 on the other. | Highest-priority deformation area. Give the garment hem deliberate weights; separate garment control or local topology changes may be necessary. |
| Pouch | Existing repair remains closed and separate. It stays rigid in pelvis space during the probes. | Attach to pelvis/belt on the real rig; test thigh clearance. Inter-object pouch/body collision was not measured here. |

The counts are **faces selected by MeshLab's self-intersection detector**, not
collision-pair counts. The rest body selects zero faces. No probe produced a
zero-area triangle. A zero count does not establish that a pose looks good.

## Remaining geometry defects

The body object consists of three connected components:

- Main character: **1,099 vertices / 2,191 triangles**, **7 open boundary edges**,
  no edges shared by more than two faces. Openings are at the neck/shoulder
  junction (3 edges) and central front tunic hem (4 edges).
- Two small detached pieces under the front tunic: **11 vertices / 11 triangles
  each**, **10 open boundary edges and 1 overconnected edge each**. These were
  retained from the original BPT geometry. Their intended shape is unclear;
  do not blindly remove them or close every opening.
- The separate pouch has **40 vertices / 76 triangles** and is closed.

The body-wide total is therefore **27 open edges and 2 overconnected edges**.
Those two overconnected edges belong to the detached pieces, not the main
character surface. The elbow and knee regions have neither kind of defect.

## How the probes work and what they do not establish

`scripts/probe_peasant_bends.py` uses hand-estimated pivots and one-joint linear
blend deformation. The distal arm mask follows mesh connectivity so nearby
belt/pouch attachment vertices do not accidentally move with the arm. The
opposite-side masks use nearest correspondences in the nearly symmetric rest
mesh. The actual vertex positions are retained on both sides.

These masks are **not learned weights** and the probes omit the combined motion
of clavicle, shoulder, pelvis and spine. A collision can be caused by the test
weights or pivot rather than topology alone. Evaluate the trained rig before
committing to larger mesh changes. Pouch dynamics, finger articulation, foot
contact, compound poses, continuous motion and engine export are not tested.

Earlier mask-debugging artifacts are retained under `diagnostics/`; the final
review uses only `poses/`. The source character file and user's open Blender
scene were not changed.

## Reproduction

From the workspace, using fresh output folders (the scripts refuse to overwrite
their saved review `.blend` files):

```sh
blender --background --factory-startup --threads 4 --python scripts/check_peasant_deformation.py -- --output assets/peasant-deformation-check-rerun
blender --background --factory-startup --threads 6 --python scripts/probe_peasant_bends.py -- --output assets/peasant-deformation-check-rerun/poses
```

The joint centers and region masks are specific to this peasant's scale and pose.

## Downloads and next milestone

Official UniRig source and HY-Motion source are cloned under `third_party/`.
Pinned model downloads run as the user service
`shape-gen-animation-downloads.service`, with resumable downloads and automatic
SHA256 verification against the upstream LFS hashes. **Downloads running does
not mean inference is installed or tested.**

Selected inference assets total **25.77 GB**:

- UniRig Articulation-XL skeleton and skin checkpoints: **5.82 GB**.
- HY-Motion **Lite** checkpoint and configuration: **1.84 GB**.
- Required Qwen3-8B and CLIP text encoders: **18.11 GB**.
- Small OPT architecture configuration for UniRig; OPT weights are not needed.

The optional HY-Motion prompt-rewriting LLM and training datasets are omitted.
The upstream HY-Motion README lists a 24 GB minimum for Lite; an 8 GB runtime
still requires an offload/quantization experiment. Downloading Lite does not
establish that it fits this GPU.

Check progress from the workspace:

```sh
.venv/bin/python scripts/animation_download_status.py
journalctl --user -u shape-gen-animation-downloads -n 20 --no-pager
```

Completion produces `models/animation-downloads.json` and links the checkpoints
into the upstream directories. Each model folder has its own download manifest.
`models/animation-download-plan.json` records pinned revisions and expected sizes.
`models/animation-lfs-manifest.json` records the fetched source support files.

The download service survives this chat ending. It is a transient user service;
after a reboot, resume with `.venv/bin/python scripts/download_animation_models.py`.

**Next:** prepare an isolated UniRig environment, generate and inspect the
skeleton, predict weights, and repeat the bend checks with the actual armature.
Preserve the source mesh and UVs; target repairs only where the real rig shows
they are needed. HY-Motion inference and retargeting follow that rigging test.

Primary sources checked during this task:
[UniRig](https://github.com/VAST-AI-Research/UniRig),
[HY-Motion](https://github.com/Tencent-Hunyuan/HY-Motion-1.0),
[HY-Motion checkpoint guide](https://github.com/Tencent-Hunyuan/HY-Motion-1.0/blob/master/ckpts/README.md).
