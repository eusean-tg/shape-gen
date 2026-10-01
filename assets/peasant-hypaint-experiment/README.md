# HY Paint followed by imagegen: peasant experiment

Completed 2026-09-17. Start with the [visual comparison](comparison.png).

## Results

- **HY Paint baseline:** [Blender](hypaint/peasant-hypaint.blend), [GLB](hypaint/peasant-hypaint.glb), [face](hypaint/after-head-angle.png).
- **HY Paint + imagegen:** [Blender](hypaint-imagegen/peasant-hypaint-imagegen.blend), [GLB](hypaint-imagegen/peasant-hypaint-imagegen.glb), [face](hypaint-imagegen/after-head-angle.png), [whole character](hypaint-imagegen/three-quarter.png).
- [Original native HY Paint output](hypaint-native/03-textured.glb) is retained separately from the direct-texel rebake used for the comparison.

The face is the strongest improvement: imagegen clarifies eyes, brows, hair and
beard boundaries over the blurry HY Paint result. Clothing changes are subtler.
HY Paint does not guarantee correct material placement everywhere: color bleed
around the pouch, tunic hem, collar and occluded surfaces remains. Restyling can
preserve those mistakes. This is a viable refinement experiment, not a proven
fully automatic production workflow or a perfectly seamless final asset.

## Recommended sequence

1. Hunyuan3D-2 dense shape generation from the reference.
2. BPT low-poly topology generation.
3. Repair geometry and check normals; finalize parts and silhouette.
4. Mark seams, unwrap, pack and validate UVs. Freeze geometry and UVs.
5. HY Paint with the character reference, **preserving those UVs**.
6. Inspect HY Paint by itself. Where useful, render fixed-camera textured views
   and ask imagegen for constrained style/detail refinement.
7. Project the edited views back onto the same UVs. Use HY Paint for unseen or
   rejected areas; inspect facial placement, seams and material boundaries.
8. Save a packed authoring `.blend` and validate the GLB export.

Imagegen edits rendered views here, not the flattened UV atlas. The projection
step after imagegen is necessary. Finalizing geometry before painting avoids
invalidating texture correspondence during BPT or later face repairs.

## What ran

Input: `../peasant-bpt-staged/imagegen-paint/repair-original-v4/peasant-repaired.glb`.
Reference: `../peasant-turnaround/front.png`.

- Local Hunyuan3D Paint v2.0 and Delight; existing installed checkpoints.
- 30 Paint steps, seed 0, six generated 512×512 views, 2048×2048 atlas.
- Staged CPU offload and feed-forward chunking. HY Paint/Delight plus its native
  bake completed in **69.99 seconds**, peak allocated GPU memory **4215.5 MiB**.
  This timing excludes imagegen calls and later rendering/reprojection.
- Added `--preserve-uvs` to `scripts/paint.py`; it verifies that exported UVs,
  triangle coordinates and winding remain unchanged.
- HY Paint's six generated views were rebaked with direct sampling of UV texels
  to avoid the earlier sparse projection artifact. This baseline covers 94.8%
  of occupied texels directly and retains the native HY texture elsewhere.
- Rendered four full-body and four head close-up views from that textured mesh.
- **Two built-in imagegen edit calls**, no CLI/API fallback. Prompts:
  [body](prompts/body.txt), [head](prompts/head.txt).
- Saved returned images: [body](body-restyled.png), [head](head-restyled.png).
  Both are 1254×1254. Body returned alpha; sampling composites it over white
  and rejects eroded background pixels.
- Reprojected with front-view priority on the central face, smooth transition
  to side coverage, and an **85% restyle / 15% HY baseline blend** at accepted
  texels. The 12.3% without accepted restyle coverage stays HY Paint.
- Geometry and UVs are identical throughout this experiment: **2,289 triangles**.
  The original-vertex pouch repair is preserved.

## Checks and limitations

- [Geometry, UV and embedded-texture comparison](validation.json).
- [HY Paint inference metadata](hypaint-native/paint.json).
- [HY baseline projection](hypaint/projection.json) and [restyle projection](hypaint-imagegen/projection.json).
- [UV overlap check](hypaint-imagegen/uv-validation.json): no zero-area triangles
  or overlapping triangle-interior samples on a 2048×2048 grid.
- Saved Blender files reopened; packed textures and zero normal-recalculation
  flips checked in each folder's `saved-file-validation.json`.
- Full-body silhouette IoU: 97.6–98.3%; head: 98.9–99.0%. See
  [body alignment](body-restyled-views/alignment.json) and
  [head alignment](head-restyled-views/alignment.json). These measurements do
  not establish exact eye, mouth or clothing-boundary correspondence.
- Visible review: head and pouch close-ups, full character and rear view.
- The source body still has 27 boundary edges and two edges shared by more
  than two faces. This experiment changes textures only and does not resolve
  the remaining geometry defects or establish rigging readiness.
- Some shading exists in the generated base color. This is not a full PBR set.

## Reproduce

From `/home/sean/workspace/shape-gen`, choose fresh output directories:

```sh
.venv/bin/python scripts/paint.py assets/peasant-bpt-staged/imagegen-paint/repair-original-v4/peasant-repaired.glb --image assets/peasant-turnaround/front.png --output-dir assets/peasant-hypaint-experiment/hypaint-native --preserve-uvs --texture-size 2048 --render-size 1024 --steps 30 --seed 0

.venv/bin/python scripts/texture_projection.py bake --mesh assets/peasant-bpt-staged/imagegen-paint/repair-original-v4/peasant-repaired.glb --views assets/peasant-hypaint-experiment/hypaint-native/views.json --output assets/peasant-hypaint-experiment/hypaint --fallback assets/peasant-hypaint-experiment/hypaint-native/basecolor.png --front-head
```

`texture_projection.py guides` renders the fixed-camera sheets; `--head` creates
close-ups and saves their camera crop transforms. Generate edits using the saved
prompts and built-in imagegen, then split each with `prepare_style_views.py`.

```sh
.venv/bin/python scripts/texture_projection.py bake --mesh assets/peasant-bpt-staged/imagegen-paint/repair-original-v4/peasant-repaired.glb --views assets/peasant-hypaint-experiment/body-restyled-views/views.json --extra-views assets/peasant-hypaint-experiment/head-restyled-views/views.json --output assets/peasant-hypaint-experiment/hypaint-imagegen --fallback assets/peasant-hypaint-experiment/hypaint/basecolor.png --front-head --strength 0.85 --erosion 2

blender --background --factory-startup --threads 8 --python scripts/review_peasant.py -- --output assets/peasant-hypaint-experiment/hypaint-imagegen --source-blend assets/peasant-bpt-staged/imagegen-paint/repair-original-v4/untextured.blend --name peasant-hypaint-imagegen --material-label 'Hunyuan Paint plus imagegen style refinement'
```

The head-region threshold in projection is specific to this peasant's scale and
orientation. It needs adaptation for a different asset. Imagegen results are
not guaranteed to reproduce exactly; the original returned sheets are retained.
