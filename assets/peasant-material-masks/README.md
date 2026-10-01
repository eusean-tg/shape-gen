# Material masks: clothing boundary experiment

Completed 2026-09-17. [Open the interactive comparison](http://localhost:5173/materials/review.html).

The labeled trouser surfaces no longer inherit the tunic's ochre paint. The
existing face/skin paint is retained, along with the small metal buckle. The
clothing uses a simple palette and optional subtle generated cloth/leather grain.

## Review files

- [Masked materials: animated Blender](masked/peasant-walk.blend) / [GLB](masked/peasant-walk.glb)
- [Flat-color baseline](flat/peasant-walk.blend)
- [Editable region labels](regions/peasant-walk.blend)
- [UV material IDs](material-ids.png) / [colored UV regions](region-colors.png)
- [Generated material swatches](material-swatches.png)
- [Preservation and export validation](validation.json)

The viewer switches between **Masked cloth + leather**, **Flat colors**,
**Previous texture**, and **Region labels** at the same paused time.
The original ankle-corrected walk remains unchanged in
`assets/peasant-hymotion/walk/final/`. This is a separate experiment.

## What ran

1. Extracted the rest mesh and per-corner UVs from the animated Blender file.
2. Authored region rules in Blender coordinates and reviewed front/back/side,
   waist and cuff renders. Corrected the neck boundary and front hanging tabs
   after the first review. These are character-specific authored labels,
   not HY Paint predictions or automatic semantic segmentation.
3. Assigned skin/head, tunic, trousers, boots and pouch to faces, including
   a `material_region` face attribute and named Blender material slots.
4. Rasterized those assignments into the existing 2048×2048 UV atlas. The thin
   belt crosses existing triangles, so it uses a sub-face surface mask instead
   of adding geometry. The belt band spans rest Z .085–.13; its original metal
   buckle is retained with a small color/position mask.
5. Made a flat-color clothing baseline while retaining the old face/skin paint.
6. Used one built-in imagegen call to generate four material swatches: ochre
   tunic cloth, taupe trouser cloth, dark boot/belt leather, and pouch leather.
   Applied only restrained variation around the chosen material palette,
   independently within each region. The strongest variation is ±5.25% per
   channel around the palette; no generated swatch can recolor another region.
7. Saved three editable animated variants and rendered the results at rest
   and on the existing walk. No shape model, UniRig or HY-Motion rerun was needed.

**HY Paint was not rerun.** The retained face/skin/buckle artwork comes from
the previous HY Paint + imagegen experiment. This tests controlled region
assignment plus generated material detail, rather than another full-character
view repaint. It intentionally replaces much of the old clothing's baked-in
lighting and painted detail with a simpler material treatment.

The source imagegen file is retained at
`/home/sean/.codex/generated_images/01a0a441-8aeb-7a02-9170-9ef36876d9f7/exec-3b821ad1-6443-42f6-a77c-e64079aaa64a.png`
and copied here as `material-swatches.png`. The returned sheet is 1254×1254.

## Results and limits

- On the reviewed trouser mask above Z −.32, an ochre-color check found
  **66,572 pixels before and 0 after**, across 206,420 occupied upper-trouser
  texels. See `color-boundary-check.json` for the exact RGB rule. This is a
  color diagnostic, not independent proof that every material label is correct.
- The two narrow projecting front tabs are labeled as tunic; the wider thigh
  surfaces behind them are trousers. Changing their material does not fix
  their existing topology or deformation issues.
- Geometry, UVs, weights, rest bones and all 120 evaluated animation frames are
  preserved in each variant. The textured GLB was reimported and checked over
  all 120 frames; maximum world-vertex error is below 0.000004 units.
- Preserved head/skin/buckle texels are byte-identical to the old base color;
  the label-debug variant deliberately displays flat region colors instead.
- The surfaces now read more consistently, but the clothing is simpler. The
  weave is subtle at normal viewing distance and more visible close up; compare
  against the flat-color option before deciding whether to keep it.
- Swatch variation is tiled in atlas coordinates. Fabric scale/direction can
  change across UV islands, so this is not a seamless directional fabric weave.
  Subtle contrast limits its visibility. Region assignments can also be refined
  further around ambiguous garment geometry.
- Clothing intersections, the pouch/body attachment overlap, foot sliding,
  existing face-paint quality, and loop construction are outside this experiment.

## Editing and reuse

Open the region-label blend, select **Peasant body**, enter Edit Mode, and use
the named material slots to inspect the assigned faces. `material_region` stores
the corresponding per-face integer. The belt and buckle are sub-face texture
masks and cannot be selected as complete faces without including some tunic.

The label script is currently the authoritative reproducible assignment.
Manual Blender edits are not automatically read back by the baker; update the
script or export revised face IDs into `regions.npz` before rebaking. Region
rules are specific to this mesh and should not be blindly reused on a new BPT
output. Palette changes and new swatches can reuse this mesh's masks.

`material-ids.png` uses integer values: 0 = unused space, 1 = skin/head,
2 = tunic, 3 = trousers, 4 = belt/buckle, 5 = boots, 6 = pouch. Use nearest
sampling when reading categorical IDs. `regions.npz` stores zero-based face
labels, original vertices/faces and per-corner UVs; `uv-regions.npz` stores
the per-texel face ID, region ID and rest position.

## Reproduce

These commands regenerate this experiment's own outputs; archive edits first.
They do not overwrite the source rig or original walk.

```sh
blender --background --factory-startup --threads 6 --python scripts/prepare_material_regions.py
.venv/bin/python scripts/bake_material_regions.py \
  --swatches assets/peasant-material-masks/material-swatches.png
blender --background --factory-startup --threads 6 --python scripts/build_material_experiment.py -- --variant regions
blender --background --factory-startup --threads 6 --python scripts/build_material_experiment.py -- --variant flat
blender --background --factory-startup --threads 6 --python scripts/build_material_experiment.py -- --variant masked
blender --background --factory-startup --threads 6 --python scripts/validate_material_experiment.py
```

The scripts reuse the existing Blender and `.venv` environment. A fresh imagegen
call is not needed to reproduce these baked results from the saved swatches.

## Next useful experiment

Choose the flat or subtly textured treatment, then add selected details
(stitching, wear or cloth folds) within the same masks. If imagegen view
refinement is revisited, use these region IDs to reject material-boundary drift
during projection. The current experiment does not implement that additional
view-segmentation/projection stage.
