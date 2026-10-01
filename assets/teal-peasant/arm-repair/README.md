# Sleeve and hand weight repair — 2026-09-18

The sleeve zigzag came from unrelated UniRig skin influences: lower-arm vertices
followed the pelvis, thighs and thumb chains. Removing only tiny weights would
not fix it; some unrelated influences were dominant.

The preview now uses [the corrected walk](final/peasant-walk.blend), with
[rest pose](rest/rigged.blend) and [forward travel](travel-check/peasant-walk.blend)
also corrected. **Teal peasant · before arm weight repair** preserves the previous
walk in the preview list. Pause before switching to compare the same time.

## Correction

Cut mesh connectivity below z=1.34 and select the two isolated arm components,
84 vertices each. Replace their weights with smooth upper-arm/forearm/hand bands
around the existing elbow and wrist pivots. 166 vertices change; two already
matched. Keep the remaining weights, every rest vertex, UV, material, texture,
rest bone and baked bone transform unchanged. Raw learned rig data and the
original Blender files remain under `../rig/` and `../walk-cycle/`.

This asset-specific correction treats the grouped hands as following the hand
bone. Independent finger articulation has not been established. It does not
solve general automatic weight painting or repair the remaining coarse topology.

## Validation

- `preservation.json`: exact unchanged geometry/UVs/textures/rest bones and bone
  motion across the rest pose, 120-frame source, both 79-frame cycle variants and
  235-frame translating check. Vertices outside the edited set have zero motion
  difference.
- `validation.json`: 313 integer/quarter-frame GLB comparisons; maximum world
  vertex error 0.00000533 units. 235 travel frames pass within 0.00000527 units.
  Matching loop endpoints and previously measured foot-contact results retained.
- `intersection-comparison.json`: arm-region selected intersecting faces over
  78 unique frames change from min/median/max **2/28/65** to **2/2/9**. Whole-body
  counts change from **44/74/127** to **37/51/67**. These are selected faces, not
  collision pairs; intersections remain, including the existing ankle geometry.
- Browser review: front and both three-quarter views, seven sampled poses,
  automatic looping, static rest pose, planted-foot check and Blender links pass.
  Example views: `review-left.png`, `review-right.png`.

## Reproduce

From the workspace root:

```sh
.venv/bin/python scripts/refine_teal_arm_weights.py
blender -b -t 2 --python scripts/apply_teal_arm_weights.py -- --source assets/teal-peasant/walk-cycle/final/peasant-walk.blend --output assets/teal-peasant/arm-repair/final/peasant-walk.blend
```

Apply the same script to the original rest, source, before-foot-lock and travel
scenes, writing to the corresponding directories here. Then run:

```sh
blender -b -t 2 --python scripts/validate_teal_arm_repair.py
blender -b -t 2 --python scripts/validate_walk_cycle.py -- --asset-dir assets/teal-peasant/arm-repair --no-pouch
node scripts/test_teal_peasant_preview.mjs
```

The original pipeline outputs remain historical inputs; `arm-repair/` contains
the current selected deliverables. `cycle.json` refers to the corrected source
scene so the cycle validator compares matching reviewed weights.
