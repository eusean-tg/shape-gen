# Peasant: pouch, UV, and projection repair

## Open the result

- [Editable Blender file](peasant-repaired.blend), with its texture packed.
- [GLB export](peasant-repaired.glb).
- [Whole character](three-quarter.png), [face close-up](after-head-angle.png), and [pouch close-up](after-pouch.png).
- Before: [face](before-head-angle.png), [pouch texture](before-pouch-texture.png), and [pouch geometry](before-pouch-clay.png).

Created 2026-09-17 from the saved `final-v2/peasant-editable.blend`. The user's
interactive Blender session and unsaved edits were not modified. This is a new
asset version; existing files remain available.

## Geometry changes

The original pouch was a folded shell fused into the tunic, with holes and
edges shared by more than two faces. Reversing normals alone could not repair
it. Removed 79 faces within the recorded local repair region, closed the tunic
patch underneath, and built a separate chamfered pouch in the same location.
Also closed the small triangular hole beside the ear.

The replacement pouch is a simplified shape, not a topology-preserving edit.
It is closed, consistently wound, and has positive signed volume. Both objects
retain flat shading and backface culling; the repair does not hide faults by
making the material double-sided.

| Object | Vertices | Triangles | Boundary edges | Edges with >2 faces |
| --- | ---: | ---: | ---: | ---: |
| Body | 1,120 | 2,212 | 24 | 2 |
| Pouch | 24 | 44 | 0 | 0 |
| Total | 1,144 | 2,256 | 24 | 2 |

The remaining defects are in the original tunic geometry. This is not yet a
fully manifold, animation-ready character. Recalculating normals flips zero
faces in either saved object, but that test alone is not an outside-orientation
proof; the closed pouch's winding and positive volume are also checked.

## UV and texture changes

- Head: one UV island, a neck boundary and connected seam down the back,
  Blender Minimum Stretch unwrap, and extra texture density for facial detail.
- Pouch: deliberate panel/band seams; its leather color comes from a local
  mapping to the pouch panel in the existing generated frontal painting.
- Body: preserves the earlier chart structure except the repaired patch.
  Charts are repacked with a 0.006 fractional margin.
- Texture: 2048×2048. Each UV texel directly samples visible generated views,
  replacing the sparse screen-to-atlas splatting used in the previous bake.
- Facial features use the frontal painting, with a smooth transition to other
  views at the sides. View weights use smooth normals; surface shading remains
  flat. An eroded foreground mask excludes white image backgrounds.
- Unobserved texels are filled from nearby observed surface points. Colors are
  extended around UV islands to support filtering.

No new image-generation call or model installation was needed. This rebakes
the original two imagegen sheets. The source tiles are only 627×627 full-body
images, so facial detail remains soft in extreme close-up. Small color/feature
mismatches remain near the temples, collar, tunic, and occluded areas. Texture
paint includes stylized shading; it is not a full PBR material set.

## Validation

- [Geometry checks](geometry-validation.json).
- [UV checks](uv-validation.json): no zero-area UV triangles; zero overlapping
  triangle-interior samples on a 2048×2048 grid. This is a raster test, not a
  mathematical guarantee against subpixel overlap. Head has one island.
- [Bake checks](bake-validation.json): approximately 93.6% of occupied texels
  receive direct projected/pouch-panel samples; the remaining 6.4% are filled.
- [Saved Blender checks](saved-file-validation.json): reopened file, packed
  texture, topology counts, and normal recalculation.
- [GLB export checks](export-validation.json): texture, geometry, UVs, and
  closed pouch after welding export seam duplicates for analysis.
- Visually reviewed the head and pouch close-ups and full-character views.

## Reproduce

From `/home/sean/workspace/shape-gen`:

```sh
blender --background --factory-startup --threads 8 --python scripts/repair_peasant.py
.venv/bin/python scripts/rebake_peasant.py
blender --background --factory-startup --threads 8 --python scripts/review_peasant.py
```

These are asset-specific scripts, including the pouch region and head seam
choices. They are not a general automatic character-repair algorithm. The
Blender scripts refuse to overwrite their target `.blend` files; archive the
generated working output before intentionally repeating those steps.

Use the `.blend` as the editing source. GLB may split vertices along UV seams
again. Reimporting a GLB for editing needs the same careful seam-vertex welding
as before; runtime export vertex counts are not authoring vertex counts.
