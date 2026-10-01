# Original-vertex pouch repair

Open [peasant-repaired.blend](peasant-repaired.blend), or use the
[GLB export](peasant-repaired.glb).

Review [pouch geometry](after-pouch-clay.png), [textured pouch](after-pouch.png),
and [whole character](three-quarter.png).

## What was preserved

This version repairs the original BPT pouch instead of replacing it with the
simplified shell from `repair-v3`.

- All **1,152 unique original vertex positions** remain, exactly unchanged.
  No new positions were introduced and none were discarded.
- Pouch: all **40 original positions**, **66 of 67 original triangles** retained.
  One original triangle crossed the top fold and needed different connectivity.
- Body: all **2,212 original non-pouch triangles** retained.
- Original vertices shared by the body and pouch are duplicated at the same
  coordinates to separate the objects. Authoring count is 1,161 vertices across
  both objects, including those nine duplicates.
- Added ten pouch triangles and one body triangle while removing the one
  intersecting original triangle: **2,289 triangles total**, a net increase of ten.

Normal winding is corrected where needed. Triangle retention means retaining
the same three original corner positions, not retaining erroneous winding.

## Repair

Separated the original pouch shell from its fused attachment to the tunic.
Closed the body's triangular opening and the pouch's missing panels using only
existing boundary vertices. Evaluated 196 nondegenerate combinations of cap
triangulations, rejecting candidates with self-intersections and choosing the
lowest total cap area among those passing the check.

The pouch is now closed, consistently wound, and has positive signed volume.
MeshLab's self-intersection test reports zero intersecting faces within it.
This preserves the original faceted, uneven shape; it is not smoothed or rebuilt
as a different object shape. It remains a separate touching object at the tunic
attachment, rather than a single watertight union with the body.

## Texture and limitations

The improved head UVs from v3 are transferred by exact matching face corners.
The repaired pouch is unwrapped and the existing imagegen paintings are rebaked
using the direct-texel projection workflow. This pass primarily repairs geometry;
softness and some mismatched painted features from those images remain.

The body still has 27 boundary edges and two edges shared by more than two
faces elsewhere in the original mesh. It is not yet fully manifold or ready
for rigging. The ear hole from the source is retained in this version, unlike v3.

## Evidence

- [Source preservation and self-intersection validation](source-preservation-validation.json).
- [Geometry counts](geometry-validation.json).
- [Selected cap triangulation](diagnostics/cap-plan.json).
- [Saved Blender validation](saved-file-validation.json): packed texture,
  reopened file, and zero face flips under normal recalculation.
- [UV validation](uv-validation.json): no zero-area triangles or overlapping
  triangle-interior samples on a 2048×2048 grid; subpixel overlap is not ruled out.

Created from the preserved `final-v2/peasant-editable.blend` on 2026-09-17.
The interactive Blender scene, unsaved edits, source, and v3 remain untouched.

## Reproduce

Run from `/home/sean/workspace/shape-gen`:

```sh
.venv/bin/python scripts/plan_pouch_caps.py
blender --background --factory-startup --threads 8 --python scripts/salvage_peasant_pouch.py
.venv/bin/python scripts/rebake_peasant.py --output assets/peasant-bpt-staged/imagegen-paint/repair-original-v4
blender --background --factory-startup --threads 8 --python scripts/review_peasant.py -- --output assets/peasant-bpt-staged/imagegen-paint/repair-original-v4
.venv/bin/python scripts/validate_pouch_salvage.py
.venv/bin/python scripts/check_uv_overlap.py assets/peasant-bpt-staged/imagegen-paint/repair-original-v4/peasant-repaired.glb --output assets/peasant-bpt-staged/imagegen-paint/repair-original-v4/uv-validation.json
```

These scripts are specific to the saved peasant mesh. Blender preparation and
review refuse to overwrite their `.blend` targets. Archive working outputs
before intentionally rerunning them. Use the `.blend` as the editing source;
GLB duplicates seam vertices during export.

## Proposed next texture experiment

Sean suggested HY3D Paint for the initial geometry-conditioned texture, followed
by imagegen to restyle rendered views. This has not been run on this repaired
asset. Preserve the final UV layout, judge the HY Paint baseline, then apply
constrained imagegen restyling to fixed-camera renders and project accepted
changes back. Retain HY Paint colors where restyled views drift or lack coverage.
The current `scripts/paint.py` always re-unwraps, so preserving existing UVs is
an implementation step before that experiment.
