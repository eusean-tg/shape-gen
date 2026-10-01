---
title: "Character workflow and animation experiments"
summary: "Original API, teal character, previews, material masks and rig/motion preparation."
kind: "history"
status: "historical"
topics: ["character", "animation", "materials"]
read_when: "Recover context or asset paths from early character workflow iterations."
---
# Character workflow and animation experiments

Archived from the former README on 2026-09-30. “Latest,” paths, measurements and
commands below describe historical runs, not current install instructions.
Generated assets are excluded from Git. See [history overview](../project-history.md)
and [current setup](../setup.md).

---

## Original project overview

Git tracks code, configuration, docs and small experiment reports. Model weights,
environments and generated binary assets stay local; a clone needs those restored
or downloaded separately. See [repository storage policy](../repository-storage.md).

## Remote generation API

The HTTP/SSE service runs at `http://100.66.127.115:8765` on the GPU machine.
It exposes Hunyuan/TRELLIS/TRELLIS.2 shape, BPT/DeepMesh/LATO.2 retopology,
HY Paint, UniRig and raw HY-Motion through durable,
serial jobs. The Mac runs Blender repair, UVs, rig construction and retargeting.
`GET /operations` lists typed model contracts; the original combined teal motion
operation remains compatible. Every endpoint requires bearer authentication.

- [Agent guide](../api-agent.md), also served at `/docs/agent.md`.
- [Geometry alternatives and book experiments](../api-geometry-experiments.md), also `/docs/geometry-experiments.md`.
- [Service operations and recovery](../api-operations.md).
- [Standard-library client](../../scripts/shape_api_client.py).
- [Consumer handoff](../../exports/shape-gen-api/README.md).

Status/logs stream live through SSE and can be replayed after reconnecting.
Candidate outputs remain separate from the accepted character. Service:
`systemctl --user status shape-gen-api.service`; tests:
`.venv-api/bin/python -m pytest -q tests`.

API v0.3 adds authenticated `/helpers` downloads for the versioned local Blender
retarget/review bundle and `/jobs/{id}/motion-diagnostics` for root travel, speed,
stationary tails, repeating-segment candidates and estimated contacts. New motion
jobs include the report as an artifact; old jobs can be analyzed without regeneration.
[Diagnostic definitions](../motion-diagnostics.md). Exact prompt speed and seamless
loops remain local cleanup/runtime concerns.

See the repository [workflow history index](../project-history.md). The original
Obsidian reference is local to this machine at
`/home/sean/obsidian/vault/Workflows/shape-gen/00 Shape-gen workflow.md`; it is
not part of a repository clone.

Local image-to-mesh setup using undistilled Hunyuan3D-2.0, 2mini, or 2mv in FP16.
Blender handles the later mesh reduction and materials stages.

## Latest character: teal peasant

The preview now starts with breathing idle and three randomized accents. Switch
**Character state** between idle and walking to test transitions.
[Five-clip asset and React Three Fiber integration](../../assets/teal-peasant/idle-set/README.md).

[Open the replacement character](http://localhost:5173/preview/), based on the
new slender, faceless reference with smaller, narrower hands. Includes the
masked teal outfit, a fresh 34-bone UniRig skeleton and a seamless 1.30-second
walk. Rest pose and forward-travel checks are selectable; the old character is
retained. Includes the corrected sleeve/hand weights.
[Blender asset](../../assets/teal-peasant/idle-set/final/teal-character.blend)
· [Build notes, references and limitations](../../assets/teal-peasant/README.md).

## Latest: seamless in-place walk

[Preview the finished cycle](http://localhost:5173/preview/): 1.30 seconds,
foot locking through the planted phases, and the latest masked clothing.
Choose **Foot-contact check (forward travel)** to inspect it against a fixed
floor, or **In-place before foot locking** to compare. Match game movement to
1.385 model units/s at 1× animation speed. Clothing deformation still needs work.
See [results and reproduction](../../assets/peasant-walk-cycle/README.md) and the
[editable Blender animation](../../assets/peasant-walk-cycle/final/peasant-walk.blend).

## Reusable model and animation preview

[Open the model preview](http://localhost:5173/preview/). Drop in a self-contained
GLB, choose an embedded animation, and toggle looping (on by default). Static
models, saved peasant variants, skeleton/wireframe inspection, automatic framing
and close-up zoom are supported. Existing experiment pages share the same viewer.
See [the viewer guide](../../assets/preview/README.md) to add future models or restart
the local server. Playback repetition does not make the source walk seamless.

## Material-mask texture experiment

[Compare the clothing textures](http://localhost:5173/materials/review.html):
previous paint, flat palette, generated cloth/leather within authored masks,
and the region labels. Shirt color no longer spills onto the labeled trousers.
The existing face/skin paint and the ankle-corrected walk are retained.
See [experiment notes](../../assets/peasant-material-masks/README.md) and the
[editable textured character](../../assets/peasant-material-masks/masked/peasant-walk.blend).
The original animation result remains available for comparison.

## Generated animation: HY-Motion Lite

**The textured peasant now has a locally generated four-second walk.**
[Play the interactive review](http://localhost:5173/hymotion/review.html),
open the [animated Blender file](../../assets/peasant-hymotion/walk/final/peasant-walk.blend),
or read the [setup and quality report](../../assets/peasant-hymotion/README.md).

Staged full-weight inference fits the RTX 3050: text encoding peaked at 1,197 MiB
GPU allocation; motion generation at 3,388 MiB. Both stages completed in about
22 seconds combined, excluding setup and retargeting. The peasant's rest mesh,
UVs, texture, weights and bones are preserved; animated GLB passed all-frame
reimport checks. Foot sliding, clothing intersections and seamless looping
remain cleanup work.

## Rigging preparation: deformation review and model downloads

**UniRig is now working on the RTX 3050.** The [rigging report](../../assets/peasant-unirig/README.md)
includes setup, measured memory use, and remaining tunic limitations.
Open the [rigged Blender file](../../assets/peasant-unirig/final/peasant-rigged.blend)
or [visual review](http://localhost:5173/unirig/review.html). The 28-bone rig
preserves the original mesh and texture and includes a bend-test action.
The animated GLB passed reimport checks. HY-Motion now also works; see above.

The textured peasant's joint-area review is in
[assets/peasant-deformation-check/README.md](../../assets/peasant-deformation-check/README.md),
with an [interactive visual review](../../assets/peasant-deformation-check/review.html)
and editable Blender bend probes. It is suitable for a first rigging experiment;
deep joint bends and the tunic/hip region still need work. The source mesh and
UVs are preserved. The probes use temporary manually chosen weights, not UniRig.

Official UniRig and HY-Motion sources are in `third_party/UniRig` and
`third_party/HY-Motion-1.0`. Pinned UniRig skeleton+skin and HY-Motion Lite+text
encoder downloads completed and passed hash verification (25.77 GB total).
The original progress helper, `scripts/animation_download_status.py`, depends on
the separately prepared `models/animation-download-plan.json`; no setup script
creates that historical plan, so the helper is not a fresh-install instruction.
For current installs, watch the downloader's verification output and per-repository
`download-manifest.json` files. `models/animation-downloads.json` is written after
all selected assets are verified and paths linked. To resume downloads after a reboot:

```sh
.venv/bin/python scripts/download_animation_models.py
```

UniRig uses `.venv-unirig` and explicit local configs in `config/unirig/`.
Skeleton and skin inference peaked at 2,443 and 4,155 MiB of allocated PyTorch
GPU memory respectively. HY-Motion uses `.venv-hymotion`; staged text encoding
and motion generation succeeded within 8 GB, followed by a reviewed retargeted walk.

