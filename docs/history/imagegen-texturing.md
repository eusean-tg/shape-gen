---
title: "Image-generated texture experiments"
summary: "Image-generated atlas experiments, original-vertex repair and animation follow-up notes."
kind: "history"
status: "historical"
topics: ["texturing", "imagegen", "repair"]
read_when: "Review earlier texture/mesh repair choices and their limitations."
---
# Image-generated texture experiments

Archived from the former README on 2026-09-30. “Latest,” paths, measurements and
commands below describe historical runs, not current install instructions.
Generated assets are excluded from Git. See [history overview](../project-history.md)
and [current setup](../setup.md).

---

## Texture with imagegen

Latest texture experiment: [HY Paint followed by imagegen](../../assets/peasant-hypaint-experiment/README.md).
It keeps the repaired BPT mesh and UVs fixed, uses HY Paint to establish the
texture, then refines rendered views with imagegen and projects them back.
[Compare results](../../assets/peasant-hypaint-experiment/comparison.png) or open
[the combined Blender result](../../assets/peasant-hypaint-experiment/hypaint-imagegen/peasant-hypaint-imagegen.blend).
The face is clearer; material-boundary errors around occluded areas remain.

Latest reviewed asset: [original-vertex pouch repair](../../assets/peasant-bpt-staged/imagegen-paint/repair-original-v4/peasant-repaired.blend).
It preserves all 1,152 original vertex positions, repairs the pouch's connectivity,
and has 2,289 triangles. See [validation and limitations](../../assets/peasant-bpt-staged/imagegen-paint/repair-original-v4/README.md).

Earlier replacement-pouch asset: [peasant-repaired.blend](../../assets/peasant-bpt-staged/imagegen-paint/repair-v3/peasant-repaired.blend).
The [repair notes](../../assets/peasant-bpt-staged/imagegen-paint/repair-v3/README.md)
cover the rebuilt closed pouch, controlled head UVs, and direct texel projection
that removes the earlier speckled bake. This version has 2,256 triangles and
reuses the existing generated paintings. Geometry cleanup is still needed
before rigging. The repair scripts are specific to this peasant asset.

Earlier example: `assets/peasant-bpt-staged/imagegen-paint/final-v2/` contains
the textured GLB, a packed Blender review scene, a 2048×2048 `basecolor.png`,
and four rendered previews. All **2,279 triangles and their coordinates are
unchanged**; UV seams increase the exported vertex count from 1,152 to 2,092.

The workflow uses the **built-in imagegen tool** for two paint-over sheets:
front/back/left/right first, then four views from above/below. Each sheet uses
exact geometry renders as the edit target, with the character reference or
the previous painted sheet as the color reference. The images are projected
onto xatlas UVs using visibility and viewing-angle weights; uncovered texels
are filled using the mesh and nearby texture values. Hunyuan's renderer and
baking utilities are reused, but no Hunyuan Paint or Delight model is run.

Prepare the first geometry sheet:

```sh
.venv/bin/python scripts/imagegen_texture.py prepare \
  --mesh assets/peasant-bpt-staged/02-bpt.glb --output assets/my-texture
```

Use imagegen to paint `geometry-sheet.png` while preserving every silhouette
and camera position. Save the result as `painted-sheet.png` in that directory.
The exact prompts for the completed example are saved in
`assets/peasant-bpt-staged/imagegen-paint/prompt.txt` and `tilted/prompt.txt`.

Optional coverage pass: prepare another sheet with `--view-set tilted` and
`--output assets/my-texture/tilted`, then paint it using the first painted
sheet as the color reference. Keep its result beside its `projection.json`.

Bake all eight views (omit `--extra-sheet` to bake four):

```sh
.venv/bin/python scripts/imagegen_texture.py bake \
  --output assets/my-texture --sheet assets/my-texture/painted-sheet.png \
  --extra-sheet assets/my-texture/tilted/painted-sheet.png \
  --bake-output assets/my-texture/baked
blender --background --factory-startup --threads 8 \
  --python scripts/preview_mesh.py -- assets/my-texture/baked/03-imagegen-textured.glb
```

The test preserves the character's overall appearance well. Small color
mismatches remain around the pouch, belt, and tunic edges; imagegen does not
guarantee exact correspondence between views. Some stylized shading remains
in the base color. This is a reviewed proof of concept, not a guarantee of
seamless texturing on arbitrary meshes or a complete PBR material workflow.

### Later: generated character animation

Candidates identified for a separate experiment:
[Tencent HY-Motion 1.0](https://github.com/Tencent-Hunyuan/HY-Motion-1.0)
generates skeletal motion from text;
[UniRig](https://github.com/VAST-AI-Research/UniRig) generates skeletons and
skin weights. The integration would require rigging, motion retargeting,
and deformation review in Blender. UniRig is now installed and tested; see the
[rigging report](character-workflow.md#rigging-preparation-deformation-review-and-model-downloads).
HY-Motion inference and walk retargeting are also tested; see the
[generated-animation section](character-workflow.md#generated-animation-hy-motion-lite).
HY-Motion documents 24–26 GB minimum VRAM for its provided pipeline;
our staged Lite runner works on this 8 GB GPU. Seamless loops and in-place
motion are also listed as unsupported in its current prompting guide.

