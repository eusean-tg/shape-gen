# Idle posture and sleeve dye correction — 2026-09-18

The current [five-clip GLB](../idle-set/final/teal-character.glb) and
[Blender file](../idle-set/final/teal-character.blend) include both corrections.
The [preview](http://localhost:5173/preview/) selects that character by default.

## What changed

- The generated breathing mean put wrists behind the shoulders. The idle builder
  now aims upper arms slightly forward, adds a gentle elbow bend and keeps
  clearance beside the thighs. Small generated breathing motion is retained.
  Look-around/weight-shift and accent entry/exit share the new stance; the middle
  of the hand-check gesture retains its original generated arm motion.
- The old width cutoff missed inner sleeves. Arm components below the armpits
  seed a distance-along-mesh-edges classification. Central torso seeds prevent
  that mask invading the upper back; known outer sleeve/cuff coverage is retained.
  This changes 16,029 occupied atlas texels from tunic to sleeve/trim. The baked
  color, face labels, runtime dye mask and palette metadata were rebuilt together.
- UVs, rest geometry, weights, bone rest poses and accepted walk are preserved.
  All five collar-fix variants receive the atlas. No model inference was rerun.

These corrections are character-specific. The graph seed height, center-body
width, cuff heights and arm targets need review on any replacement character.

## Review and evidence

- [Side stance](side.png), [opposite side](other-side.png).
- [Blue tunic from back](back-blue.png), [front](front-blue.png),
  [blue tunic / yellow sleeves](back-blue-yellow.png).
- [Weight-shift arm clearance](weightshift-clearance.png).
- `regression-validation.json`: 65,817 sleeve texels (8,365 on the inner surface)
  use the sleeve region and dye ID; 58,796 torso texels retain tunic. No skin,
  hair, neckline or trouser changes. Across 481 breathing samples, wrists sit
  .0909–.0981 units ahead of their shoulders in Blender's -Y forward direction.
- `../idle-set/validation.json`: all 2,081 GLB integer/half-frame comparisons pass;
  maximum error .000007823 units. Common idle entry/exit and walk preservation pass.
- `../idle-set/runtime-validation.json`: idle scheduling, walk priority, rapid
  reversals, blend weights, floor clearance and finite deformed vertices pass.
- `colors-test.log`: rendered recoloring, protected skin/hair and exact reset pass.
- `../collar-fix/validation.json`: single-walk/contact exports also pass.

Sampled mesh overlaps remain: current min/median/max selected intersecting faces
are 49/49/49 breathing, 49/49/49 looking, 46/49/79 shifting, 36/54/104 hand check.
These are not collision-pair counts. This fix does not supply collision-aware
animation or repair all coarse clothing/ankle geometry.

`before/` preserves the previous final Blender/GLB, textures, all five source
Blender variants, animation analysis and changed generation scripts. Current
outputs retain their established paths so the preview and R3F integration use
the same filenames. Refresh copied GLB and clothing sidecars together.

## Reproduce checks

```sh
blender -b -t 2 --python-exit-code 1 --python scripts/validate_teal_idle_sleeves.py
blender -b -t 2 --python-exit-code 1 --python scripts/validate_teal_idle_set.py
node scripts/test_teal_idle_set.mjs
node scripts/test_teal_clothing_colors.mjs
node scripts/review_teal_idle_sleeves.mjs
```

Browser checks require the local preview server. For rebuilding, use the texture
and palette scripts, apply the texture to the collar-fix variants, refresh the
source hash in cycle.json, then run `build_teal_idle_set.py`. Preserve manual
edits before rebuilding. `apply_teal_texture.py` exports only the active action;
apply it to the single-action source, then rebuild the five-clip character.
