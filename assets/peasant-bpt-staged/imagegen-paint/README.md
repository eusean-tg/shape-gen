# Imagegen texture proof of concept

## Selected result

For editing, open [repair-original-v4/peasant-repaired.blend](repair-original-v4/peasant-repaired.blend).
This [original-vertex repair](repair-original-v4/README.md) preserves all original
positions and repairs the pouch's face connectivity. It has 2,289 triangles.

The earlier replacement-pouch version is [repair-v3/peasant-repaired.blend](repair-v3/peasant-repaired.blend).
See [repair details and validation](repair-v3/README.md): this revision rebuilds
the pouch, unwraps the head with controlled seams, and replaces the speckled
projection bake. It changes the geometry and has 2,256 triangles.

The previous welded copy is [final-v2/peasant-editable.blend](final-v2/peasant-editable.blend).
The original review scene is [final-v2/preview.blend](final-v2/preview.blend), or import
[final-v2/03-imagegen-textured.glb](final-v2/03-imagegen-textured.glb).
The GLB embeds [the 2048×2048 base color](final-v2/basecolor.png).
[Front preview](final-v2/previews/front.png) and
[three-quarter preview](final-v2/previews/three-quarter.png).

## Generation and projection

- Image synthesis: **built-in imagegen**, two calls, no fallback API runner.
- [First prompt](prompt.txt): paint the four exact cardinal geometry views
  using `assets/peasant-turnaround/front.png` as the character reference.
- [Second prompt](tilted/prompt.txt): paint four elevated/lowered geometry
  views using the first painted sheet as the color reference.
- Original returned images are preserved as `painted-sheet.png` and
  `tilted/painted-sheet.png`; each is 1254×1254.
- Preparation/projection script: `scripts/imagegen_texture.py`.
- Projection uses the exact cameras that rendered the guides, xatlas UVs,
  viewing-angle weights, and geometry-aware filling of uncovered texels.
- Final projection uses one-pixel silhouette/depth-edge erosion at a
  1024-pixel per-view bake resolution to preserve narrow details.
- No Hunyuan Paint or Delight neural model was used.

The root-level bake uses only four views. `final/` adds four tilted views.
`final-v2/` retains those eight views and reduces erosion around narrow edges.
Earlier variants remain available for comparison.

## Validation and limits

The earlier `final-v2` GLB was reopened and rendered in Blender from four angles.
All 2,279 triangles have exactly the same coordinates as the BPT source.
UV seams duplicate vertices: 1,152 geometric vertices become 2,092 exported
vertices. The embedded texture is 2048×2048 and UV coordinates are finite.
See [validation.json](final-v2/validation.json) and
[texture.json](final-v2/texture.json) for measurements and hashes.

The four initial painted silhouettes overlap the guide masks by roughly
97–98% intersection-over-union (threshold-based diagnostic, not a guarantee
of feature alignment). The face, beard, clothing and boots transfer well.
Color mismatches remain on narrow/occluded details around the pouch, belt and
tunic hem. The source mesh's topology defects remain. The color texture also
contains some stylized shading; it is not a normal bake or full PBR set.

## Blender editing and normal recalculation

The exported GLB splits vertices at UV seams. In the original Blender import,
that leaves 129 disconnected components; recalculating normals flips 638 faces.
Backface culling then makes those faces disappear from the outside. The texture
material is opaque, and the export itself preserved the source triangle winding.

`final-v2/peasant-editable.blend` welds coincident vertices at a distance of
0.000001 Blender units, preserving the separate UV coordinates on each face
corner. It has 1,152 vertices and the same 2,279 faces. Recalculating its normals
flips zero faces. Exact face coordinates, winding, UVs, material assignments,
and shading flags were checked before and after; the saved file was reopened
and its packed texture checked. This copy was made from the original saved
preview, not from any unsaved edits in the user's Blender session.

Use that `.blend` as the authoring copy. A GLB export can split seam vertices
again; when reimporting this asset for editing, merge coincident vertices before
recalculating. Avoid applying a broad merge distance to unrelated meshes.
If faces have already been flipped in an edited copy, welding alone does not
guarantee recovery of their intended orientation.

This fixes the reproduced recalculation problem, not all geometry defects:
37 boundary edges and 9 edges shared by more than two faces remain from BPT.
These need review before rigging or workflows requiring a manifold mesh.

Evidence: [normal audit](diagnostics/normals-audit.json),
[editable-copy validation](diagnostics/editable-validation.json), and
[preparation script](diagnostics/prepare_editable.py).
