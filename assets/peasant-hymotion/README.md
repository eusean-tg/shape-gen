# HY-Motion Lite → UniRig peasant: first generated walk

**New:** the accepted textured walk now has a separate
[seamless in-place cycle with foot locking](../peasant-walk-cycle/README.md),
available in the [reusable preview](http://localhost:5173/preview/).
The original generated-motion results below are retained for comparison.

**Successful local inference on the RTX 3050 8 GB**, followed by retargeting to
the existing textured peasant. Tested 2026-09-17. The result is a motion proof
of concept with remaining clothing intersections and foot sliding.

- [Interactive review](http://localhost:5173/hymotion/review.html): play/pause,
  scrub, orbit, change speed, show bones/wireframe, and compare both transfers.
- [Corrected Blender animation](walk/final/peasant-walk.blend)
- [Corrected animated GLB](walk/final/peasant-walk.glb)
- [Raw transfer](walk/retarget/peasant-walk.blend)
- [Saved-file validation](validation.json) and [motion review](motion-review.json)

Prompt: **“A person walks forward at a relaxed pace, with natural arm swings.”**
Seed 12345. 120 frames at 30 fps (four seconds of samples, keyframe times
0–3.9667 seconds). Blender frames 1–120. The character travels forward; this is
neither an in-place animation nor a seamless loop. The viewer can repeat it, but this original clip resets its pose and travel at the boundary.

## How it fits

The default upstream pipeline keeps the large Qwen encoder and motion model on
the GPU together. Our runner separates them:

1. Encode the prompt with CLIP and unload it.
2. Load the **full BF16 Qwen3-8B backbone** in system RAM. Accelerate streams its
   modules through CUDA as needed. Preserve the upstream prompt template,
   crop offset, 128-token context window, and final hidden-state features.
   No token generation, output logits, or KV cache is needed for this step.
3. Save the features and exit that process, releasing the encoder entirely.
4. Load HY-Motion Lite in **FP32** on CUDA and run the original 50-step Euler
   schedule with guidance 5.0, one seed, the full 360-frame internal sequence,
   and a four-second output. Retain upstream rotation/translation smoothing.

No weight quantization, optional prompt rewriting model, or reduced denoising
step count was used. The pinned upstream source files are unchanged.

| Stage | Wall time | Peak PyTorch GPU allocated / reserved | Peak process RAM |
| --- | ---: | ---: | ---: |
| CLIP + offloaded Qwen text encoding | 10.59 s | 1,197 / 1,222 MiB | 15,882 MiB |
| Lite model loading + motion generation | 11.16 s | 3,388 / 3,422 MiB | 4,112 MiB |

Times exclude initial Python/Torch imports, downloads, installation, Blender
retargeting, and rendering. GPU measurements exclude other applications and
CUDA overhead. This establishes feasibility for this input and configuration;
the official stock pipeline's published 24 GB estimate is a different setup.

## Retargeting and corrections

Map 22 HY body joints to the peasant's 28-bone rig. Finger chains inherit their
hand motion; no finger articulation was generated. Convert Y-up/+Z-forward
to Blender Z-up/−Y-forward, correct each bone's reference direction to account
for the source T-pose and peasant's lower arm rest pose, and scale root travel
by the ratio of combined thigh/shin lengths. The mapping, scale, and settings
are in `walk/final/retarget.json`.

The raw transfer is retained in `walk/retarget/`. The corrected version adds:

- **Level foot reference alignment:** match foot/toe headings in the horizontal
  plane, removing the approximately 13° upward bias caused by different ankle
  heights in the two skeletons. Generated heel strike, ankle movement, and toe-off
  remain. The previous corrected clip is retained in `walk/before-ankle-fix/`.
- **8° shoulder abduction** on both arms, moving the arms slightly outward to
  clear this character's torso. Elbow and wrist articulation are retained.
- **Walking-only root-height correction** at each frame so the lowest point of
  the foot mesh touches the floor. Horizontal root travel remains unchanged.
  This is not foot-lock IK and should not be applied unchanged to jumps.

The original rest vertices, faces, UVs, packed texture bytes, skin weights,
and bone rest matrices are unchanged. Both variants are ordinary editable FK
actions; no live HY-Motion dependency is required to play the saved files.

## Quality review

All 120 evaluated frames were checked, and selected textured frames plus the
interactive GLB were visually inspected.

The ankle correction reduced approximate foot-mesh pitch from 16.84° to 4.76°
on the right at frame 16, and 15.29° to 3.01° on the left at frame 46. These are
two reviewed stance samples, not a flat-foot constraint across the whole walk.
See [ankle comparison measurements](walk/final/ankle-review.json). The preview
defaults to **Ankles corrected** and preserves paused time when switching to
**Before ankle fix**. Collision counts stayed unchanged after this correction.

| Measurement | Raw transfer | Corrected transfer |
| --- | ---: | ---: |
| Self-intersecting body faces: minimum / median / maximum | 14 / 78 / 196 | 0 / 4 / 51 |
| Lowest foot height above ground | 0–0.0594 units | Within 0.000001 of ground |

Counts describe selected faces, not collision pairs; near-touching surfaces
can be precision-sensitive. The correction improves torso/arm clearance, but
some sleeve and tunic overlaps remain. The pouch already overlaps the body at
its belt attachment in rest, as recorded in the earlier rig review.

Feet are not locked during stance. The height-based contact estimate records
roughly 0.20–0.22 units/s median horizontal foot-center movement during candidate
contact after correction. This includes foot roll, so it is not a pure slip
measurement, but sliding still needs review and cleanup. Do not treat this
clip as a finished game walk cycle. The endpoint does not match the start.

## Validation

Reopened the corrected `.blend` and compared the rest mesh, topology, UVs,
weights, bones, and texture against the source rig. Reimported the GLB into a
fresh Blender scene and compared **all 120 animation frames**: maximum
bidirectional nearest-vertex difference was 0.00000351 world units. Export
includes only the active walk action; Blender frame 1 becomes glTF time zero
and imports at Blender frame 0. UV seam duplicates in GLB are expected.

Browser testing used Chromium: animation loaded without JavaScript errors;
scrubbing, skeleton/wireframe controls, raw/corrected switching, and restarting
after the endpoint worked. Three.js 0.180.0 and its MIT license are bundled
locally, so the viewer does not require an external CDN.

## Reproduce

Source: `third_party/HY-Motion-1.0`, commit
`4e426f5a1021cbcf7f375458c37b840ee7225229`. Model revisions and hashes are in
`models/animation-download-plan.json` and `models/animation-downloads.json`.
The upstream model license is retained at `models/hy-motion/tencent/LICENSE.txt`.

Environment: `.venv-hymotion`, Python 3.11.16, Torch 2.7.1+cu126,
Transformers 4.53.3, Accelerate 1.10.1, torchdiffeq 0.2.5. Full pins are in
`config/hymotion-environment.txt`; `uv pip check` passes. The inference path
does not require Gradio, the Autodesk FBX SDK, bitsandbytes, or FlashAttention.
Blender 5.2.1 provides the animated GLB export.

```sh
uv venv .venv-hymotion --python 3.11
uv pip install --python .venv-hymotion/bin/python \
  --extra-index-url https://download.pytorch.org/whl/cu126 \
  --index-strategy unsafe-best-match -r config/hymotion-environment.txt

# Choose a new output directory; completed features/motion are not overwritten.
.venv-hymotion/bin/python scripts/run_hymotion.py encode --output assets/walk-retry
.venv-hymotion/bin/python scripts/run_hymotion.py motion --output assets/walk-retry

blender --background --factory-startup --threads 6 \
  --python scripts/retarget_hymotion_peasant.py -- \
  --motion assets/walk-retry/motion.npz --output assets/walk-retry/retarget \
  --arm-clearance 8 --ground-feet --level-foot-rest
```

The runner supports `--prompt`, `--seed`, and `--duration`; provide the same
prompt to both stages. Retargeting/rendering currently targets this peasant and
the four-second walk review; camera snapshots and cleanup choices are specific
to this experiment. Use different clearance/grounding choices for other actions.

Existing result checks:

```sh
blender --background --factory-startup --threads 6 --python scripts/validate_hymotion_peasant.py
```

## Next useful work

Choose a target motion set, then add stance-aware foot locking, clean the
tunic/sleeve deformation, and construct an in-place seamless cycle if needed.
The local motion-generation and rig-to-animation feasibility questions are
answered positively for this example.
