---
title: "Shape-gen: local Blender handoffs"
summary: "Mesh, rig and motion array/axis contracts plus local Blender assembly and adaptation."
kind: "reference"
status: "current"
topics: ["blender", "rigging", "animation"]
read_when: "Consume UniRig/HY-Motion outputs or adapt a rig locally."
---
# Shape-gen: local Blender handoffs

API version 0.4.2. Served at authenticated **`GET /docs/blender-handoff.md`**.
Start with `/docs/agent.md` and `/operations` for submission/authentication.
The consumer owns Blender; no new model operation launches it on the GPU server.

## Workflow and review points

1. Supply consistent reference images. Submit Hunyuan shape, then BPT using the
   dense GLB artifact's `asset_id`. Download the BPT output with checksum checking.
2. In local Blender, inspect components, normals, boundaries and intersections.
   Repair before rigging; BPT inference success does not guarantee manifold geometry.
   Keep the dense mesh if normal baking is useful. Freeze topology before final UVs/weights.
3. Unwrap locally. Export the unrigged rest mesh as GLB, with embedded resources,
   Y-up glTF axes, no skins/actions or Draco compression. Upload it for HY Paint
   with `preserve_uvs: true` and the reference image. Do not upload `.blend`.
4. Download paint/atlas results. Preserve the local authoring mesh: use the atlas
   on its matching UVs. GLB import/export may split/reorder vertices at seams and
   normals; do not substitute a reimported mesh beneath weights indexed to another mesh.
5. Apply texture/style refinement and clothing masks locally. HY Paint alone does
   not create the reviewed recoloring masks used by the current R3F character.
6. Export the exact body vertices/triangles as numeric NPZ and submit UniRig.
   Keep rigid accessories separate. Import predicted joints/weights onto that same
   authoring mesh, inspect bone layout/deformation and assign semantic names.
7. Submit HY-Motion, download raw arrays, retarget onto the reviewed local rig,
   clean up loops/contacts, export/validate and preview on the Mac. Motion can run
   before the other work finishes; retargeting needs the reviewed rig.

This is an agent-orchestrated pipeline with review points. It is not a single
unattended operation that promises production topology, masks, rigs or animations.

## Export the body for UniRig

Run inside Blender Python on the final **unposed authoring body**. Finalize any
modifiers that change topology first. Do not export an evaluated, deformed mesh
and later apply the returned weights to the original vertex order.

```python
import bpy
import numpy as np

body = bpy.context.active_object
assert body and body.type == 'MESH'
body.data.calc_loop_triangles()
vertices = np.array([body.matrix_world @ v.co for v in body.data.vertices], dtype=np.float32)
faces = np.array([list(t.vertices) for t in body.data.loop_triangles], dtype=np.int64)
np.savez('/absolute/candidate/body.npz', vertices=vertices, faces=faces)
```

Axes: **Blender world Z-up, character forward -Y**. The service does no automatic
orientation inference. Numeric input is deliberate: glTF can split/reorder vertices,
while skin weights must index the original authoring vertices. Do not add normals,
UVs or metadata to the upload archive; it accepts exactly `vertices` and `faces`.

After submission, preserve the saved body mesh and its transform. Inputs are immutable
on the service; each output records the exact input asset ID/hash in `provenance.json`.

## Read and build the UniRig draft

`result/rig-data.npz` loads with `numpy.load(..., allow_pickle=False)`.
In the table below, **N** is the number of vertices in the uploaded authoring mesh,
and **B** is the number of predicted bones.

| Array | Meaning |
|---|---|
| `vertices`, `faces` | Original uploaded mesh (vertices converted to float32, faces to int64) |
| `joints` | Bone heads, B×3, in supplied Blender world coordinates |
| `tails` | Bone tails, B×3, same coordinates |
| `parents` | B integers; `-1` is a root |
| `names` | Unicode `bone_0` … `bone_{B-1}` (B bones); prediction order, not semantic labels |
| `weights` | N×B float weights; normalized, at most four nonzero values per vertex |
| `unlimited_weights` | Weights before keeping only the largest four |

Use the `joints` and `tails` to construct a new armature with **identity world
transform**. Create all edit bones before assigning parent relationships. Do not
force connected bones: predicted children may not start at their parent's tail.
Weights are indexed by body vertex and bone column, not glTF-export vertex indices.

Before assigning weights, compare current world vertices and triangle order against
the returned arrays; reject a mismatch. A minimal draft, inside Blender:

```python
import bpy
import numpy as np

body = bpy.context.active_object
data = np.load('/absolute/candidate/result/rig-data.npz', allow_pickle=False)
assert body and body.type == 'MESH', 'Select the original body mesh, not the imported GLB root'
body.data.calc_loop_triangles()
current = np.array([body.matrix_world @ v.co for v in body.data.vertices])
triangles = np.array([list(t.vertices) for t in body.data.loop_triangles])
assert current.shape == data['vertices'].shape
assert np.allclose(current, data['vertices'], atol=2e-6, rtol=0)
assert np.array_equal(triangles, data['faces'])
assert not any(m.type == 'ARMATURE' for m in body.modifiers), 'Use a fresh unrigged candidate'
names = data['names'].tolist()
assert not any(name in body.vertex_groups for name in names), 'Avoid overwriting existing groups'

armature = bpy.data.armatures.new('Predicted skeleton')
rig = bpy.data.objects.new('Predicted rig', armature)
bpy.context.collection.objects.link(rig)
bpy.ops.object.select_all(action='DESELECT')
rig.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode='EDIT')
for i, name in enumerate(names):
    bone = armature.edit_bones.new(name)
    bone.head = data['joints'][i]
    bone.tail = data['tails'][i]
    assert bone.length > 1e-6, 'Review a degenerate predicted bone before continuing'
for i, name in enumerate(names):
    parent = int(data['parents'][i])
    if parent >= 0:
        armature.edit_bones[name].parent = armature.edit_bones[names[parent]]
bpy.ops.object.mode_set(mode='OBJECT')
for i, name in enumerate(names):
    group = body.vertex_groups.new(name=name)
    column = data['weights'][:, i]
    for vertex in np.flatnonzero(column > 0):
        group.add([int(vertex)], float(column[vertex]), 'REPLACE')
modifier = body.modifiers.new('Predicted skin', 'ARMATURE')
modifier.object = rig
```

This builds a **draft**, not a reviewed deformation rig. Check bone roll, shoulder,
elbow, hip and knee motion; adjust weights as needed. Establish a semantic mapping
by inspecting heads/tails/parents in the character's coordinate frame. Never reuse
the accepted teal character's bone-index mapping on a fresh prediction blindly.
Renaming bones requires matching vertex-group names as well.

## Raw HY-Motion contract

`result/motion.npz` is numeric/Unicode, no pickle. See `motion-run.json` and
`validation.json` for the exact array shapes. Core arrays:

- `rotations`: `(1, 120, 22, 3, 3)`, parent-relative rotation matrices for the 22
  body joints. They are not ready-made target-rig quaternions.
- `transl`: `(1, 120, 3)`, generated root travel. The existing retargeter subtracts
  its first sample and scales displacement using the target/source leg-length ratio.
- `parents`, `joint_names`, `rest_joints`: source skeleton metadata. Rest-skeleton
  metadata may contain more joints than the 22 animated body joints; read the arrays
  rather than assuming every rest joint has a generated rotation track.
- Other model outputs (`rot6d`, etc.) are retained as numeric data.
- Source axes: **Y-up, +Z forward**. To Blender: `(x, y, z) -> (x, -z, y)`.
  Conjugate rotation matrices by that coordinate conversion; do not just swap Euler channels.
- 30 fps, 120 samples. The interval between first and last samples is 119/30 seconds.
  Motion is neither looped nor in-place by default; fingers are not animated here.

The tested retarget approach accumulates source local rotations through the parent
chain, converts axes, aligns rest-bone directions and converts into target local
bases. Foot/toe rest alignment must be checked to avoid upward-pointing feet.

## Downloadable reference helpers

Use authenticated `GET /helpers` to discover **blender-helpers 1.0.3**.
Versions 1.0.0 through 1.0.2 are retained unchanged for pinned consumers. Version
1.0.3 clarifies vertex/bone counts in this guide and bone naming in the bundle
README. Scripts and contracts are unchanged from 1.0.2. Diagnostic calculations
remain unchanged from 1.0.0. The catalog entry supplies archive size/hash, manifest
hash and versioned download URLs:

- `/helpers/blender-helpers/1.0.3/manifest`
- `/helpers/blender-helpers/1.0.3/download`

The manifest lists every script/support file with SHA-256 and includes the
`peasant-humanoid` rig contract version 1.0.0. The archive is immutable; changed
contents require a new bundle version. It includes the retargeter, review helper,
rig preflight checker, local diagnostics script, contract JSON, README and guides.
No credentials, model weights or source character are included; provide your own
compatible `.blend` and downloaded raw motion. All script dependencies for these
helpers are supplied by Blender 5.2.1 (tested), or NumPy for standalone diagnostics.

Download the updated standard-library client through authenticated
`GET /clients/shape_api_client.py`, then:

```sh
SHAPE_API_URL='http://100.66.127.115:8765' # Replace with your operator-provided URL.
python3 shape_api_client.py --base-url "$SHAPE_API_URL" helpers
python3 shape_api_client.py --base-url "$SHAPE_API_URL" helper-download --version 1.0.3 --output ./blender-helpers-1.0.3
```

The client verifies the archive, manifest and individual file hashes before
extracting to a new directory. Read the included README, run the rig-contract
preflight, then invoke Blender locally with explicit paths. No SSH fetch is needed.
For candidate crop/speed/contact diagnostics, read `/docs/motion-diagnostics.md`.

## Scripts: reuse with explicit adaptation

The retargeter and review helper are in the bundle above. They are **reference implementations**
for the accepted peasant, not general-purpose scripts that work unchanged on all rigs:

- `retarget_hymotion_peasant.py`: accepts `--source`, `--motion`, `--output`,
  `--clip-name`, `--level-foot-rest`, `--arm-clearance DEGREES`, `--ground-feet`,
  `--no-pouch`, `--skip-renders`. Requires
  `Peasant body`, `Peasant rig`, the reviewed semantic bone names, a camera and
  triangulated body. Use explicit paths on the Mac. Arm clearance and floor
  correction are per-character/per-motion decisions, not universal defaults.
- `review_api_motion.py`: source-preservation/export check and renders for that
  character contract; inspect/adapt its assumptions before using a new rig.
- `build_teal_idle_set.py`, `validate_teal_idle_set.py`,
  `validate_teal_idle_sleeves.py`: character-specific idle/contact/deformation work;
  historical workspace references, not part of this portable bundle. Do not apply
  their thresholds to arbitrary meshes; local loop/contact cleanup needs adaptation.

See the Obsidian workflow chapters 04 Texturing, 05 Rigging, 06 Animation and
07 Preview/R3F for the measured pipeline history and character-specific corrections.
