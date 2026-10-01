# Character v1 — OpenScape handoff

Accepted teal peasant with corrected idle arms, inner-sleeve color masks,
neckline, arm weights and walking ankles. This is a portable handoff from the
shape-gen workspace, not an installed change to the OpenScape application.

## Contents

- `public/teal/teal-character.glb`: textured skinned model with all five clips.
- `public/teal/clothing-mask.png`, `clothing-palette.json`: runtime recoloring data.
- `src/characters/teal/`: R3F component and two shared Three.js helpers.
- `authoring/teal-character.blend`: editable source with packed base-color atlas.
- `review/`: accepted side/back/contrast screenshots.
- `validation/`: source export, runtime and sleeve/posture regression reports.
- `manifest.json`, `SHA256SUMS`: package metadata and file integrity checks.

## Integrate

1. Merge `public/teal/` into the app's public assets. Keep the GLB and color
   sidecars from the same package revision.
2. Copy `src/characters/teal/` into the app's source tree; keep all three files
   together. Existing dependencies are React, Three.js, React Three Fiber and
   Drei. Follow the app's existing package manager/version choices.
3. Load `/teal/clothing-palette.json` once through the app's loader/query layer.
   Pass the parsed object as a stable `config` prop. Render only after it loads.
4. Render the component inside the app's Canvas and Suspense boundary:

```jsx
import { TealPeasant } from './characters/teal/TealPeasant.jsx';

// paletteConfig is the loaded JSON object; isMoving comes from gameplay.
<TealPeasant
  config={paletteConfig}
  moving={isMoving}
  colors={{ tunic: '#254b5a', trousers: '#383c42' }}
  position={[0, 0, 0]}
/>
```

Use a continuously rendered Canvas for animation. `url` and `maskUrl` can be
overridden if the app serves assets under different paths. Position, rotation
and scale belong to the outer group; the internal model's Y offset belongs to
the transition floor correction. This component does not move the character
through the world or implement input, navigation, physics or turning.

## Asset contract

- glTF is Y-up, facing +Z; height is approximately 1.975 model units at scale 1.
- Rest mesh: 730 welded vertices, 1,460 triangles, 34 bones, 2048-square atlas.
  Export duplicates vertices at UV/material seams.
- Named clips: `Idle_Breathe`, `Idle_LookAround`, `Idle_WeightShift`,
  `Idle_HandCheck` (4 seconds each), and `Walk` (1.30 seconds).
- `moving={false}` breathes and chooses an idle accent after 6–12 seconds,
  avoiding immediate repeats. `moving={true}` interrupts accents and walks.
  Transitions take 0.4 seconds. Timing follows animation updates, not wall time.
- The walk is in-place. At full walk weight and normal playback speed, translate
  +Z at **1.471686 model units/second**, multiplied by uniform character scale.
  During fades, movement speed should follow walk blend weight. The lower-level
  controller exposes `state.weights.Walk`; the supplied JSX wrapper does not
  expose a controller ref, so adapt it when wiring accurate movement blending.
- Color keys: `tunic`, `trousers`, `sleeves`, `stockings`, `trim`, `shoes`.
  Unspecified keys use defaults. Skin/hair are protected. Colors use normal
  Three.js color inputs (e.g. hex strings). Separate instances clone their
  skeletons and materials while sharing loader geometry/textures.
- The GLB embeds its default appearance and clips. Random idle scheduling,
  transitions and arbitrary recoloring require the supplied helpers.

## Validation and next review

The asset and shared helpers passed Blender export checks and Chromium/Three
r180 browser checks. All 2,081 sampled GLB poses matched Blender within
0.000007823 units; the supplied regression report also checks inner sleeves and
forward idle wrists. The R3F wrapper still needs testing in the target app.

In OpenScape, check idle/walk movement at the real game camera, contrast-colored
clothing, multiple independently colored instances, unmount/remount behavior
and actual performance. Check animated bounds if frustum culling hides a posed
mesh. The palette helper targets WebGLRenderer; WebGPU needs an adaptation.

This remains a reviewed low-poly draft. Coarse clothing/joint overlaps and
transient foot slip during crossfades remain possible. There is no finger
articulation, cloth simulation, start/stop footstep clip or terrain foot IK.

## Verify package

From this directory on macOS:

```sh
shasum -a 256 -c SHA256SUMS
```

The source project and detailed workflow remain on the generation machine at
`/home/sean/workspace/shape-gen` and the Obsidian `Workflows/shape-gen/` chapters.
