# Corrected neckline and runtime clothing colors

Current selected character: [Blender walk](final/peasant-walk.blend),
[animated GLB](final/peasant-walk.glb), [rest pose](rest/rigged.glb), and
[forward travel](travel-check/peasant-walk.glb).

## Neckline correction

The previous broad neck mask started at 80.8% of body height, below the back
collar and outside the front V. Restrict that broad mask to above the collar;
keep the separately authored front opening. This changes **3,368 occupied
atlas texels**, all from skin to tunic, at z=1.59613–1.62769. Skin on the face,
actual front neck opening and hands is unchanged. Front/back close-up checks
are saved as `front.png` and `back.png`.

The current files retain the arm weight repair, original geometry/UVs and walk.
`validation.json` records 313 integer/quarter-frame GLB checks and 235 traveling
frames; maximum error remains 0.00000533 units. Foot contact and loop closure
pass. Previous versions remain in `../arm-repair/` and `../walk-cycle/`.

## Runtime colors

**2026-09-18 sleeve correction:** the current atlas/mask also fixes tunic color
on the inner sleeves. Mesh-connected arm regions supplement the old width
cutoff; 16,029 occupied texels change from tunic to sleeve/trim. The neckline
correction above is preserved. See [review and regression evidence](../idle-sleeve-fix/README.md).

The preview exposes six independent colors: **tunic, trousers, sleeves,
stockings, collar/cuffs, shoes**. Skin/hair are protected. Garment masks retain
sub-triangle neckline/cuff boundaries; the tunic/trouser division follows the
coarse hem faces. Contrast review: `clothing-colors.png`.

Implementation differs from simply splitting face materials: some triangles
contain both skin and clothing. A UV mask and small shader helper restrict
color changes to the correct pixels. The helper removes each region's baseline
color in linear space before applying the selected color, preserving grain.
Default/reset ratios are exactly one, keeping the corrected original look.
Very close inspection can reveal discrete mask edges or texture-filtering fringes.

**The GLB alone retains the default outfit. Runtime recoloring requires the
mask, palette metadata and helper below.** No neutral-texture-only stock-material
export was created. Materials are cloned per character so independently colored
instances do not share color uniforms. Texture and geometry resources can remain
shared. The helper targets Three.js WebGLRenderer, tested here on Three r180;
WebGPU needs a separate implementation. The customization hook's scope is
documented in [Three.js Material](https://threejs.org/docs/pages/Material.html#onBeforeCompile).

## React Three Fiber integration

The shared component now supports the five-clip idle/walk set. Follow
[the current integration guide](../idle-set/README.md), which lists the correct
GLB, all three helper/component files, the `moving` prop and clothing sidecars.
This folder still supplies the corrected atlas, mask and palette configuration.
The standalone `clothing-palette.js` helper also works with this folder's
older single-walk or static exports; the new character-motion controller requires
the five named clips.

## Reproduction / validation

```sh
.venv/bin/python scripts/texture_teal_peasant.py --output assets/teal-peasant/collar-fix/textures
.venv/bin/python scripts/prepare_teal_clothing_palette.py
blender -b -t 2 --python scripts/apply_teal_texture.py -- --source assets/teal-peasant/arm-repair/final/peasant-walk.blend --output assets/teal-peasant/collar-fix/final/peasant-walk.blend --textures assets/teal-peasant/collar-fix/textures
blender -b -t 2 --python scripts/validate_walk_cycle.py -- --asset-dir assets/teal-peasant/collar-fix --no-pouch
node scripts/test_teal_clothing_colors.mjs
node scripts/test_teal_peasant_preview.mjs
```

Apply the same texture replacement to rest, source, before-foot-lock and travel
scenes to recreate every variant. If rebuilding the source scene, refresh its
SHA-256 in `cycle.json` before running the source-preservation check.
