---
title: "Blender reference helpers"
summary: "Contents, prerequisites and limits of the versioned Blender reference helper bundle."
kind: "reference"
status: "current"
topics: ["blender", "helpers", "retargeting"]
read_when: "Download or use the helper bundle without assuming arbitrary-rig support."
---
# Blender reference helpers

This versioned bundle runs **locally on the consumer's Blender installation**.
No GPU weights, model runner environments, source character, or credentials are
included. Every bundled dependency is listed in `manifest.json` with size and SHA-256.
The downloadable archive has a separate size/hash in the authenticated `/helpers`
catalog. Pin the version/hash used for each local candidate.

## Contents and prerequisites

- `scripts/retarget_hymotion_peasant.py`: the tested peasant retarget/export reference.
- `scripts/review_api_motion.py`: source preservation, GLB pose comparison, renders.
- `scripts/check_blender_rig_contract.py`: non-mutating local source preflight.
- `scripts/motion_diagnostics.py`: NumPy-only raw-motion measurements; also usable
  in ordinary Python with NumPy installed. Does not require Blender.
- `contracts/peasant-humanoid-v1.json`: object names, semantic joint mapping,
  coordinate conventions, dependencies, tested Blender version and scope.
- `docs/blender-handoff.md` and `docs/motion-diagnostics.md`: formats and interpretation.

Blender **5.2.1** is the tested version. The Blender scripts use its bundled
`bpy`, `mathutils` and NumPy; no pip install or remote script fetch is required.
Supply your own `.blend` rig with packed textures and the downloaded `motion.npz`.
The `.blend` must satisfy the contract. UniRig predicts B bones named `bone_0`
through `bone_{B-1}`. These names need reviewed semantic mapping before the retarget
helpers can operate on them.

The original helper names and output names are preserved. Run with explicit paths;
their repository-relative default paths do not describe your local project.

## Example: Mac

From the extracted bundle directory, first preflight the rig:

```sh
/Applications/Blender.app/Contents/MacOS/Blender -b --disable-autoexec --python-exit-code 1 --python scripts/check_blender_rig_contract.py -- --source /absolute/rig.blend --contract contracts/peasant-humanoid-v1.json --report /absolute/new-preflight.json
```

Read the report and review semantic bone correspondence. Passing name/structure
checks does not establish correct anatomy, weights or deformation.

```sh
/Applications/Blender.app/Contents/MacOS/Blender -b --disable-autoexec --python-exit-code 1 --python scripts/retarget_hymotion_peasant.py -- --source /absolute/rig.blend --motion /absolute/motion.npz --output /absolute/new-candidate --clip-name Candidate_Jog --no-pouch --level-foot-rest --skip-renders
/Applications/Blender.app/Contents/MacOS/Blender -b --disable-autoexec --python-exit-code 1 --python scripts/review_api_motion.py -- --source /absolute/rig.blend --directory /absolute/new-candidate --clip-name Candidate_Jog --frames 120
```

Use a fresh output directory. `--no-pouch` is appropriate for the accepted teal
character; omitting it requires the contract's named legacy pouch. A scene camera
is required even with `--skip-renders`. The helper saves `.blend`/GLB and reports
locally. Review the source-unit/target-leg scaling and feet alignment before using
the clip. No seamless-loop or exact-speed promise is attached to this helper.

The motion diagnostics script can be run separately:

```sh
python3 scripts/motion_diagnostics.py /absolute/motion.npz --output /absolute/new-diagnostics.json
```

Read `docs/motion-diagnostics.md` before choosing crop endpoints. Contact estimates
are not contact locks. Local stride, loop, contact and runtime cleanup remain your
responsibility. Character-specific idle-set builders are not part of this portable
bundle; this bundle does not claim to reproduce all historical character edits.
