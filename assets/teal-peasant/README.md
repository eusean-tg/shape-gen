# Teal peasant replacement character

[Open the updated preview](http://localhost:5173/preview/). It now defaults to
**Teal peasant · idle + walk**. Choose **rest pose** to inspect the hands and
skeleton, or **foot-contact check** to see forward travel against a fixed floor.
The previous bearded character remains in the saved-model list.

## Selected result

**Latest animation update:** breathing idle, three occasional accents and the
accepted walk in one five-clip GLB, with runtime transitions and movement priority.
[Idle set, validation and R3F integration](idle-set/README.md).

**Latest texture update:** corrected skin spill at the shoulders/back neckline.
The preview now includes independent clothing colors.
[Correction notes and React Three Fiber integration](collar-fix/README.md).

- [Editable character and loop](idle-set/final/teal-character.blend)
- [Animated GLB](idle-set/final/teal-character.glb)
- [Rigged rest-pose Blender file](collar-fix/rest/rigged.blend)
- [Rigged rest-pose GLB](collar-fix/rest/rigged.glb)
- [Forward-travel contact check](collar-fix/travel-check/peasant-walk.glb)
- [Reference images and exact prompts](reference/README.md)
- [Geometry/material/rig validation](validation.json)
- [Loop and export validation](collar-fix/validation.json)
- [Sleeve/hand weight repair and before/after evidence](arm-repair/README.md)

**Latest correction:** replaced contaminated lower-arm weights on 166 vertices.
The preview uses the corrected exports; the original walk remains available
for comparison. Geometry, textures, bone motion and foot corrections are unchanged.
The build measurements below describe the initial generation; the repair notes
record the subsequent deformation improvements and remaining intersections.

The new asset follows the supplied slender, faceless character reference:
small grouped fingers, dark hair, teal tunic and knee breeches, pale sleeves and
stockings, and simple ankle shoes. No pouch or belt was added.

**730 welded vertices, 1,460 triangles, 34 bones, 2048² base-color atlas.**
The in-place walk lasts **1.30 seconds**, baked at 60 fps with 78 unique samples
and a matching closing pose. Blender's preview range excludes the duplicate
closing sample. For forward travel at 1× animation speed, use **1.471686 model
units/s** (scaled with the character and animation playback speed). Blender
forward is −Y; glTF forward is +Z. The contact-check export adds three strides
of travel; that diagnostic resets its position when repeated.

## Build

1. **References:** built-in imagegen created separate transparent front, back
   and profile images from the user-supplied design. Exact prompts and inputs
   are saved under `reference/`. No paid CLI/API fallback was used.
2. **Shape:** local Hunyuan3D-2mv, seed 12345, 50 steps, resolution 128, staged
   FP16 inference. 29,822 triangles; 161.46 seconds, 2,764 MiB peak PyTorch GPU
   allocation. Settings/hashes: `dense/generation.json`.
3. **Low-poly reconstruction:** local BPT, seed 12345, temperature 0.5. Completed
   with an end token after 3,212 tokens: 1,458 triangles, 63.61 seconds total,
   1,684.7 MiB peak allocated GPU memory. See `bpt/bpt.json`.
4. **Topology preparation:** split two collinear hair T-junctions and changed
   the triangulation at two four-face ankle edges, producing 1,460 triangles.
   Preserved every BPT vertex position, apart from centering and grounding the
   whole character. Final connectivity is manifold, with no open or
   overconnected edges; normal recalculation flips zero faces. This is not a
   guarantee of a collision-free surface. See `model/geometry.json`.
5. **Materials:** authored garment regions and sub-face collar/cuff masks,
   baked to per-corner UVs. Recolored the earlier imagegen cloth swatch for
   restrained grain. Hunyuan Paint was not run for this variant. The accepted
   mask-first texturing method fits this design's plain face and simple outfit.
   See `model/materials.json`, `material-ids.png` and `basecolor.png`.
6. **Rig:** UniRig predicted a new 34-bone skeleton, including thumb and grouped
   finger chains. Reviewed its hierarchy, mapped names in `rig/bone-names.json`,
   and transferred learned weights onto the exact welded vertices with at most
   four influences. Skeleton inference: 11.25 s / 2,443 MiB peak allocated;
   skin inference: 14.96 s / 4,170 MiB. Existing character data was not overwritten.
7. **Motion:** retargeted the existing HY-Motion sample to the new rest skeleton
   with level foot references, 5° arm clearance and initial grounding. Rebuilt
   the periodic in-place gait, contact anchors and two-bone leg solve for these
   proportions. Pelvis lowering is 0.05610 units. All animation is baked FK;
   no inference or live IK dependency is needed for playback.

GPU figures exclude other applications and driver overhead. These timings are
for this run and do not include image generation, setup or all preparation work.

## Checks and limits

- Source BPT vertex positions retained within 0.000000060 units after centering.
- Finite UVs within the atlas, normalized skin weights, exact packed texture,
  and rest vertices/UVs preserved through the final animation export process.
- Matching loop endpoints, zero accumulated root travel, no exceptional seam
  acceleration and no leg stretching detected.
- 313 integer/subframe checks passed for the in-place GLB reimport: maximum
  vertex error **0.00000533 units**. The 235-frame translating export passed
  within **0.00000534 units**.
- Lowest tested sole point remains above the floor at **0.000120 units**.
  Worst individual sole-vertex drift during core stance is 0.003924 / 0.003817
  units (left/right), after adding the intended forward movement. Landing and
  toe-off ramps are excluded from this metric.
- Chromium checks passed for the new default, 34-bone loading, exact loop
  endpoints, automatic repeat, rest-pose controls, planted-foot contact, Blender
  links and switching back to the old character. Existing preview tests pass.

**This is a reviewable replacement draft, not finished production topology.**
Some elbow, wrist and clothing deformation still needs polish. The BPT surface
also has self-intersections despite closed, consistent connectivity: the body
intersection checker selects 44/74/127 faces (minimum/median/maximum) across the
corrected cycle, versus 42/74/122 before foot locking. Many existing intersections
are near the ankles and sleeve joins; animation adds others. Counts represent
selected faces, not collision pairs, and can be sensitive to near-touching
surfaces. See `walk-cycle/intersections.json`.

The hands are visibly narrower and have grouped fingers rather than the old
open claw silhouette. `hand-comparison.json` is an exploratory measurement of
vertices selected by learned hand weights; it can include wrist/cuff vertices
and should not be treated as an exact anatomical hand-size measurement.

## Reproduction and editable scripts

Workspace: `/home/sean/workspace/shape-gen`. Original generation commands:

```sh
.venv/bin/python scripts/generate.py assets/teal-peasant/reference --model mv --output-dir assets/teal-peasant/dense
.venv-bpt/bin/python scripts/retopo_bpt.py assets/teal-peasant/dense/01-dense.glb --output-dir assets/teal-peasant/bpt
blender --background --factory-startup --threads 6 --python scripts/prepare_teal_peasant.py
.venv/bin/python scripts/texture_teal_peasant.py
.venv-unirig/bin/python scripts/configure_unirig.py --asset-dir assets/teal-peasant/rig --config-dir assets/teal-peasant/rig/config
.venv-unirig/bin/python scripts/run_unirig.py skeleton --asset-dir assets/teal-peasant/rig --config-dir assets/teal-peasant/rig/config
.venv-unirig/bin/python scripts/run_unirig.py skin --asset-dir assets/teal-peasant/rig --config-dir assets/teal-peasant/rig/config
.venv-unirig/bin/python scripts/transfer_unirig_weights.py --asset-dir assets/teal-peasant/rig --bone-names assets/teal-peasant/rig/bone-names.json
blender --background --factory-startup --threads 6 --python scripts/build_teal_peasant.py -- --rig
blender --background --factory-startup --threads 6 --python scripts/retarget_hymotion_peasant.py -- --source assets/teal-peasant/model/rigged.blend --no-pouch --skip-renders --output assets/teal-peasant/walk-source --arm-clearance 5 --ground-feet --level-foot-rest
blender --background --factory-startup --threads 6 --python scripts/inspect_walk_cycle.py -- --source assets/teal-peasant/walk-source/peasant-walk.blend --output assets/teal-peasant/walk-cycle
blender --background --factory-startup --threads 6 --python scripts/build_walk_cycle.py -- --asset-dir assets/teal-peasant/walk-cycle --source assets/teal-peasant/walk-source/peasant-walk.blend --no-pouch
```

The generation/BPT/retarget runners protect existing outputs; use fresh paths
when retrying those stages. Character-specific preparation/material scripts
replace their own experiment outputs. Check existing results with:

```sh
blender --background --factory-startup --threads 6 --python scripts/validate_teal_peasant.py
blender --background --factory-startup --threads 6 --python scripts/validate_walk_cycle.py -- --asset-dir assets/teal-peasant/walk-cycle --no-pouch
.venv/bin/python scripts/check_walk_cycle_intersections.py --asset-dir assets/teal-peasant/walk-cycle --mesh assets/teal-peasant/model/mesh.npz
node scripts/test_teal_peasant_preview.mjs
```
