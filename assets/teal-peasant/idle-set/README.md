# Idle variants and idle ↔ walk playback

Current character: [five-clip GLB](final/teal-character.glb) and
[editable Blender actions](final/teal-character.blend).
[Preview](http://localhost:5173/preview/) defaults to **Teal peasant · idle + walk**.

| Clip | Duration | Runtime role |
|---|---:|---|
| `Idle_Breathe` | 4 s | Quiet repeating idle |
| `Idle_LookAround` | 4 s | Occasional head/upper-body glance |
| `Idle_WeightShift` | 4 s | Small standing weight shift |
| `Idle_HandCheck` | 4 s | Brief hand/wrist fidget |
| `Walk` | 1.30 s | Existing in-place walk |

The three accents are one-shot gestures, selected after **6–12 seconds** of
quiet idle. Immediate repeats are excluded. They blend back into breathing;
walking interrupts any accent. State changes use a **0.4-second smooth blend**.
Rapid reversals preserve the phase of a still-visible walk instead of rewinding
it. Pause also pauses the scheduler; no wall-clock timeout keeps running.

Use **Character state** to test idle/walk. **Try an idle accent** skips the wait.
**Inspect individual clips** enables the animation selector and timeline.
Clothing recoloring remains available. Switching assets resets runtime state.

## Generation and cleanup

Four local HY-Motion Lite runs used four-second prompts/seeds from
`generation-plan.json`. All outputs, prompt features, logs and measurements
remain under `generated/<id>/`. Text encoding used full BF16 Qwen with sequential
CPU offload; motion used full FP32 Lite. This run measured roughly 4.7–5.4 s text
encoding and 11.0–11.3 s motion generation per clip, excluding initial imports.
Peak allocated GPU memory was 1,197 MiB / 3,388 MiB respectively.

The original `adjust-sleeve` prompt did not achieve precise cuff contact on this
rig. Its retained gesture reads as checking/fidgeting with a hand, so the final
action is named **Idle_HandCheck**. Do not describe it as validated cloth contact.

`build_teal_idle_set.py` fits periodic low-frequency breathing motion, authors a
common standing stance with mild knee bend, fixes the foot targets with analytic
leg IK, and gives accents gentle .75/.85-second entry/exit envelopes. Look-around
and weight-shift clips use selected upper-body motion; weight-shift pelvis sway
is authored at ±.025 model units. The hand check retains the generated arm motion.
Every idle has an identical entry/exit pose; all baked actions are ordinary FK.

**2026-09-18 correction:** the common idle stance now places the hands beside
the thighs with a gentle forward elbow bend, correcting the initial backward
arm posture. The final export also embeds the repaired inner-sleeve atlas.
See [before files, review images and regression checks](../idle-sleeve-fix/README.md).

## Validation and limits

- `validation.json`: geometry, UVs, skin weights, rest bones, material assignments
  and packed texture bytes match the updated collar-fix source. Existing walk differs by at most
  0.000001073 units from the preceding saved scene due to evaluated pose roundoff.
- All five clips reimported from GLB; **2,081 integer/half-frame samples** pass.
  Worst vertex error is .000007823 units, in the hand-check clip.
- Idles have exact closing poses. Minimum tested idle surface height is above
  0.000999 units. Largest idle sole-vertex drift is 0.000314 units in weight shift.
- `runtime-validation.json`: randomized scheduling, no immediate repeats, walk
  priority, rapid reversals, return to idle, finite posed vertices, pause and UI
  inspection pass in Chromium/Three r180. Blend weight sum error ≤1.2e-16.
- Blending standing and walking originally dipped soles by .0321 units. The
  runtime now applies a small model-height correction **during transitions**,
  sampling sole vertices. This is a floor safeguard, not full contact-preserving
  transition IK: transient horizontal foot slip and height bob can remain.
- Coarse joint/clothing geometry still overlaps. `intersections.json` samples
  every fourth idle frame after the arm correction: min/median/max 49/49/49
  breathing, 49/49/49 looking, 46/49/79 shifting, 36/54/104 hand check. These are selected faces, not collision
  pairs.
- Still a stylized animation draft; no finger articulation, cloth simulation,
  authored walk-start/stop steps, terrain adaptation or navigation controller.

## React Three Fiber

Copy `final/teal-character.glb` into `public/teal/`. Copy the following from
`../collar-fix/textures/` into the same directory:

- `clothing-mask.png`
- `clothing-palette.json`

Copy the shared source files from `assets/preview/` into your React source:

- `TealPeasant.jsx`
- `character-motion.js`
- `clothing-palette.js`

Fetch the palette JSON once and pass the resulting stable config object inside
your existing Canvas/Suspense setup:

```jsx
<TealPeasant
  config={paletteConfig}
  moving={isMoving}
  colors={{ tunic: '#8e3430', trousers: '#b6a579' }}
  position={[0, 0, 0]}
/>
```

The component uses one mixer per cloned skinned character, advances it through
`useFrame`, clones materials per character, and keeps geometry/textures shared.
Outer group transforms remain available to gameplay code. The inner model's
vertical offset belongs to the transition-floor safeguard. Runtime state is
separate from the five embedded clips. **The GLB by itself does not randomly
schedule gestures or choose movement states.**

Use a continuously rendered Canvas for animation. Existing dependencies:
React, Three, `@react-three/fiber`, `@react-three/drei`. This wrapper is provided
as an integration example; the shared helpers were browser-tested here, but
the wrapper has not been run inside Sean's future R3F project. The clothing
helper uses WebGL shader hooks, not WebGPU nodes.

Walk motion is in-place. At full walking weight and 1× playback, gameplay should
translate the outer group forward at **1.471686 model units/s**, multiplied by
character scale. During fades, movement speed should track walk blend weight;
that still does not guarantee exact contact. The controller exposes weights
through `state` for a custom game integration. Start/stop clips or runtime foot
IK are the next step if close-up locomotion requires planted transitions.

## Reproduction

The source plan stores exact prompts/seeds; use a new directory for new model
runs. For each plan entry, run `scripts/run_hymotion.py encode`, then `motion`
with matching `--prompt`, `--seed`, `--duration 4`, and `--output`. Retarget using
`scripts/retarget_hymotion_peasant.py` with the corrected rest scene, `--no-pouch`,
`--skip-renders`, `--level-foot-rest` and `--arm-clearance 5`. Extract each result
with `scripts/inspect_walk_cycle.py` into `generated/<id>/samples`.

The saved inputs are sufficient for rebuilding without running models again:

```sh
blender -b -t 2 --python scripts/build_teal_idle_set.py
blender -b -t 2 --python scripts/validate_teal_idle_set.py
node scripts/test_teal_idle_set.mjs
```

The build script targets this character and overwrites only the idle-set final
exports/analysis. Preserve any manual edits separately before rebuilding.
