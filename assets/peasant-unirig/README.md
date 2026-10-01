# UniRig peasant — tested local rig

Completed 2026-09-17 on the RTX 3050 8 GB. UniRig skeleton and skin inference
both fit, without CPU model offload or weight quantization. This is an editable
rigging draft; the tunic still needs deformation cleanup before unrestricted motion.

- [Visual review](review.html), served at http://localhost:5173/unirig/review.html
- [Rigged Blender file](final/peasant-rigged.blend)
- [Animated GLB](final/peasant-rigged.glb)
- [Skeleton placement](skeleton-review.png)

## Result

28 named deform bones; 1,121 body vertices; 40 pouch vertices; 2,289 triangles.
All vertices have normalized weights with at most four influences. The pouch
is rigidly attached to the pelvis. FK posing is available in Blender Pose Mode;
there are no IK handles or foot controls yet. The source rest coordinates,
faces, UVs, object transforms, and used packed texture bytes are unchanged.

The **Deformation checks** action contains 14 independent pose tests at 24 fps,
frames 1–337. Open the blend and play the timeline, or jump to named markers.
Frame 1 is rest. This is a diagnostic action, not HY-Motion-generated animation.

UniRig initially produced asymmetric weights on the symmetric character.
Copying left-side weights to exact right-side vertex counterparts changed 480
vertices, preserved the skeleton and geometry, and improved the right arm/leg.
Unmatched vertices retain their learned weights. The raw rig remains in `raw-rig/`.

## Deformation findings

Measured from evaluated Blender meshes after weight refinement:

| Independent test | Body faces detected as self-intersecting |
| --- | ---: |
| Rest | 0 |
| Shoulder raise 60°, both sides | 0 / 0 |
| Elbow 60° right, 90° both sides | 0; 0 / 0 |
| Knee 60° right, 90° both sides | 0; 0 / 0 |
| Head turn 30°, chest turn 20° | 0 / 0 |
| Hip lift 20°, both sides | 3 / 3 |
| Hip lift 45°, both sides | 12 / 11 |

The right-side raw rig had 24 intersecting body faces at elbow 90°, four at
shoulder 60°, and four at knee 90°. These cleared after weight transfer.
Counts are selected faces, not collision pairs, and can be sensitive to
floating-point differences near touching surfaces. Zero is not proof of good
deformation in arbitrary combined poses. Low-poly joint creases remain angular.

The tunic/crotch needs local weight/topology work, including two detached small
pieces already present in the authoring mesh. Weight smoothing and making those
pieces uniformly weighted did not improve the trial hip results, so those
changes were not retained. No vertices were deleted or replaced.

The pouch also intersects the body at its attachment in rest: the combined-mesh
check selects 26 pouch faces. This contact predates the rig; it persists in most
tests (23 faces at right hip 20°). The pouch is closed and does not self-intersect
in the earlier static review. Clothing/body collision is not solved by this rig.

## Measured inference cost

| Stage | Runtime | Peak PyTorch allocated / reserved | Peak process RAM |
| --- | ---: | ---: | ---: |
| Skeleton | 11.08 s | 2,443 / 2,658 MiB | 4,143 MiB |
| Skin | 14.29 s | 4,155 / 4,570 MiB | 6,982 MiB |

Runtime includes model construction/loading and inference after the runner's
initial imports. It excludes environment installation, downloads, weight
transfer, and Blender rendering. GPU figures exclude other apps and CUDA
overhead. This establishes feasibility for this example, not every mesh.

Settings: seed 12345, batch 1, BF16 mixed precision, FP32 stored parameters;
skeleton beams reduced from 15 to 3; original sample counts retained; skin
voxelization on CPU with Open3D. No optional prompt model is involved in UniRig.

## Validation

`saved-file-validation.json` records a fresh reopen of the final blend and exact
comparisons against the textured source. Animated GLB was reimported into a
fresh Blender scene and compared at rest and all 14 test peaks. World-space
vertex positions match within 0.000002 units, despite export UV seam splits.
The original source file is unchanged. `final/intersections.json` contains
the collision measurements and face indices.

## Reproduce on this machine

Source: `third_party/UniRig` commit
`6793c6640ff01c8fb389f3993434124bb43d2933`, unchanged by this setup.
Checkpoint revisions and SHA-256 hashes are in `models/animation-download-plan.json`
and the completed `models/animation-downloads.json` manifest.

The isolated `.venv-unirig` uses Python 3.11.16, Torch 2.7.1+cu126,
Transformers 4.51.3, FlashAttention 2.8.3, spconv-cu126 2.3.8, and bpy 4.2.0.
`config/unirig-environment.txt` pins the full installed environment. To recreate:

```sh
uv venv .venv-unirig --python 3.11
uv pip install --python .venv-unirig/bin/python \
  --extra-index-url https://download.pytorch.org/whl/cu126 \
  --index-strategy unsafe-best-match -r config/unirig-environment.txt
```

The lock references official prebuilt FlashAttention and PyG wheels, avoiding a
local CUDA compilation. The bpy wheel has an inconsistent internal `cp39` tag:
`uv pip check` warns, but its Python 3.11 import and both upstream inference
stages succeeded. Blender authoring/rendering uses the separately installed
Blender 5.2.1 executable, not the pip bpy module.

Run from the workspace root, after the source and checkpoints are downloaded:

```sh
blender --background --factory-startup --threads 6 --python scripts/prepare_unirig_peasant.py
.venv-unirig/bin/python scripts/configure_unirig.py
.venv-unirig/bin/python scripts/run_unirig.py skeleton
.venv-unirig/bin/python scripts/inspect_unirig_skeleton.py
.venv-unirig/bin/python scripts/run_unirig.py skin
.venv-unirig/bin/python scripts/transfer_unirig_weights.py
.venv-unirig/bin/python scripts/refine_unirig_weights.py
# Choose a new output directory; the builder refuses to overwrite a saved rig.
blender --background --factory-startup --threads 6 \
  --python scripts/build_unirig_peasant.py -- \
  --weights assets/peasant-unirig/refined-rig-data.npz \
  --output assets/peasant-unirig/rebuild
```

These scripts target this peasant asset. Preparation and inference regenerate
intermediate files in `assets/peasant-unirig/`; archive them first if retaining
an exact previous run. Validation scripts currently target `final/`:

```sh
blender --background --factory-startup --threads 6 --python scripts/validate_unirig_peasant.py
.venv/bin/python scripts/check_unirig_intersections.py
```

## Subsequent motion experiment

HY-Motion Lite subsequently generated a four-second walk on this 8 GB GPU,
which was retargeted onto this rig. See the [motion report](../peasant-hymotion/README.md)
and [interactive viewer](http://localhost:5173/hymotion/review.html). This rig
remains the unchanged baseline; foot sliding and garment cleanup remain pending.
