# Seamless in-place walk and foot-contact cleanup

[Open the reusable preview](http://localhost:5173/preview/). The default is now
**Peasant · seamless in-place walk**, with the accepted masked clothing texture.

| Saved model | What to inspect |
| --- | --- |
| Seamless in-place walk | Repeating gait with matching end poses and no accumulated travel. |
| Foot-contact check (forward travel) | Three strides translated at the intended speed, against a fixed floor. This review clip resets its travel at the end. |
| In-place before foot locking | Same periodic gait before stance correction, at the same playback phase. |
| Masked cloth + leather | The unchanged original four-second generated walk. |

Pause and switch between the two in-place versions to compare the same moment.
**Open Blender file** in the preview opens the selected variant's editable asset.

## Files and use

- [Final editable Blender animation](final/peasant-walk.blend)
- [Final animated GLB](final/peasant-walk.glb)
- [Forward-travel contact check](travel-check/peasant-walk.glb)
- [Before foot locking](before-foot-lock/peasant-walk.glb)
- [Settings and authored contact intervals](cycle.json)
- [Saved-file and export validation](validation.json)
- [Body intersection review](intersections.json)

The cycle lasts **1.30 seconds**: 78 unique samples at **60 fps**, plus an identical
closing pose at Blender frame 79. The Blender preview range is frames 1–78, so
its playback does not dwell on the duplicate closing sample. The exported GLB
includes the closing sample at 1.30 seconds for interpolation across the seam.

For game movement at 1× animation speed, translate the character at
**1.384715 model units/s** in its forward direction. At ½× playback, use half that
speed. Blender forward is −Y; exported glTF forward is +Z. The stride length is
1.800129 units. Apply any character scale to the movement speed as well.

An in-place planted foot necessarily travels backward relative to the character.
The forward-travel review adds the matching movement, so the planted shoe stays
on the same place on the floor. Its 3.9-second clip contains three strides and
5.400387 units of travel; it is a contact diagnostic, not a position-continuous loop.

## What changed

1. Measured a source gait period of about 39.1 frames at 30 fps. Averaged the
   repeating poses from source frames 21–120 using a periodic Fourier fit of
   sign-aligned local quaternions and pelvis motion. This produces a repeating
   stride instead of simply blending unrelated first and last poses.
2. Removed accumulated translation and aligned mean travel to straight ahead.
   Small periodic pelvis sway remains: about 0.055/0.057 units peak-to-peak in X/Y.
3. Authored flat-stance intervals from the shoe heights and foot speeds. During
   the core interval, a two-bone IK solve places the ankle on a fixed support
   anchor in the virtually moving character's world. Contact influence fades
   during landing and toe-off, retaining the generated swing and foot roll.
4. Centered the planted steps within leg reach, lowered the pelvis by **0.05514
   units**, and used stable forward knee poles. The result has somewhat more
   knee bend; no leg bones are stretched.
5. Flattened the shoe deformation during core stance and corrected evaluated
   sole height. Baked the result to ordinary FK keys at 60 fps, with repeat
   modifiers for Blender. No live IK constraint or model inference is needed
   to play the saved result.

The **source file is unchanged**. Rest vertices, faces, UVs, material regions,
material assignments, packed texture bytes, skin weights and rest bones all
match the accepted masked-texture source.

## Measured result (2026-09-18)

Contact measurements follow individual sole vertices during the **full-lock
core only**, adding forward travel at the speed above. Landing/toe-off ramps
are excluded, so these numbers are not a claim of zero slip over the whole step.

| Measurement | Before foot locking | After |
| --- | ---: | ---: |
| Left sole: maximum horizontal vertex drift | 0.12869 units | 0.00296 units |
| Right sole: maximum horizontal vertex drift | 0.09302 units | 0.00317 units |
| Median sole-vertex drift, left/right | 0.09380 / 0.06799 units | Below 0.000001 units |
| Body self-intersecting faces: min / median / max | 0 / 4 / 45 | 0 / 7 / 45 |

The small remaining worst-case sole drift comes from vertices blended with shin
weights. Source weights were preserved. Ground contact and seam checks:

- First/last evaluated mesh positions match exactly; net root travel is zero.
- Boundary acceleration is below the cycle's 95th percentile; no exceptional
  velocity change at the seam was detected.
- **313 integer and quarter-frame samples** checked: lowest sole height remains
  above the floor (minimum 0.000137 units). Full-stance soles sit about 0.001
  units above it.
- The GLB reimport matches all 313 samples within **0.00000177 units**.
- Forward-travel GLB checked at all **235 frames** against the translated cycle;
  maximum difference **0.00000527 units**.
- Leg-length error stays below 0.000001 units.
- Chromium checks passed for repeated playback, identical endpoint bone
  transforms, paused comparison, source links, and a stationary planted foot
  in the translating review. The general preview regression checks also pass.

## Remaining work

Tunic/sleeve clipping and the existing pouch attachment overlap remain. The
median selected body-intersection count rose from 4 to 7 after the stance
correction, while the worst count stayed at 45. These counts are affected by
near-touching geometry and are not collision-pair counts. Geometry/weight cleanup
is still needed for production-quality deformation.

The contact windows and grounding choices are specific to this character's walk.
They should not be applied to running, jumping or another skeleton unchanged.
The floor and walking speed are fixed; game terrain handling needs runtime IK
or a separate adaptation step. Next useful work is clothing deformation cleanup,
then an idle and an idle↔walk transition at the intended game viewing distance.

## Reproduce

From `/home/sean/workspace/shape-gen`:

```sh
blender --background --factory-startup --threads 6 --python scripts/inspect_walk_cycle.py
blender --background --factory-startup --threads 6 --python scripts/build_walk_cycle.py
blender --background --factory-startup --threads 6 --python scripts/validate_walk_cycle.py
.venv/bin/python scripts/check_walk_cycle_intersections.py
node scripts/test_walk_cycle_preview.mjs
node scripts/test_model_preview.mjs
```

Build commands replace only this experiment's outputs. The source is
`assets/peasant-material-masks/masked/peasant-walk.blend`. The browser checks
require the localhost preview server; see `assets/preview/README.md`.
