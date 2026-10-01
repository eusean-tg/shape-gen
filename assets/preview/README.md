# Reusable model and animation preview

Open **http://localhost:5173/preview/**. The default example is now the new teal character’s seamless
in-place walk; a forward-travel contact check and the earlier walk
variants remain selectable. See [walk results](../peasant-walk-cycle/README.md). The existing texture and walk review
pages use the same viewer module, including looping and close-up camera fixes.

The teal walk now includes corrected sleeve/hand weights. Select **Teal peasant ·
before arm weight repair** for comparison. See [repair notes](../teal-peasant/arm-repair/README.md).

The current teal exports also correct skin-color spill below the collar. Use
the **Clothing colors** controls to recolor garments independently; Reset restores
the original appearance. Colors reset when switching assets. Other models hide
these controls unless their library entry supplies matching `clothing.config`
and `clothing.mask` URLs. [Assets and React Three Fiber integration](../teal-peasant/collar-fix/README.md).

## Open future assets

- Click **Open GLB**, or drag a `.glb` onto the viewport. Files are read in the
  browser; there is no upload endpoint.
- Export the mesh, materials, textures, rig and desired actions together in a
  Blender glTF Binary (`.glb`) file. Choose **Animation** to switch embedded clips.
- Static models work too. Playback controls are disabled when there is no clip.
- **Loop** defaults on and remembers your choice in this browser. Uncheck it to
  stop at the final pose. Restart always begins playback from zero.
- Pause, then switch saved variants to compare the same time. Different-length
  clips clamp that time to their own endpoint.
- Drag to orbit, scroll toward the pointer to zoom, right-drag to pan, and use
  **Frame model** to recover the full model. Follow tracks a top-level animated
  node or bone, with no required skeleton names.

The camera fits each model's bounds. Its near clipping plane and zoom limits
scale with the model; logarithmic depth maintains useful depth precision during
close inspection. Animated meshes also bypass stale rest-pose visibility bounds,
which previously made the whole character disappear when zooming close. The camera can still enter a mesh if you zoom through its
surface; pan toward the part you want to inspect before zooming further.

This viewer plays embedded clips. It does not retarget a separate motion file
onto a different skeleton, convert FBX, or construct seamless cycles. Bake and
export compatible actions from Blender first. Use self-contained, uncompressed
GLBs: Draco, Meshopt and KTX2 decoders are not bundled.

## Save a model in the library

Edit `assets/preview/examples.json`, adding an entry such as:

```json
{
  "id": "next-character-walk",
  "label": "Next character · walk",
  "src": "./models/next-character-walk.glb",
  "floorY": 0
}
```

Put the GLB in `assets/preview/models/`, or symlink an existing export there:

```sh
ln -s ../../next-character/walk.glb assets/preview/models/next-character-walk.glb
```

The included examples use symlinks so large exports are not duplicated. Optional `note` and `blend` fields show per-asset guidance and a Blender source
link in the viewer. IDs must be unique. Paths resolve relative to the viewer page. `floorY` is optional:
omit it to place the floor below the initial displayed model bounds, or specify
its actual ground height. Refresh the page to reload the library.

## Run after a reboot

The current localhost server runs as a transient user service and may not
survive a reboot. Start the preview with:

```sh
cd /home/sean/workspace/shape-gen
python3 -m http.server 5173 --bind 127.0.0.1 --directory assets/peasant-deformation-check
```

If port 5173 is already in use, keep the existing server, or choose another
port and open `/preview/` on that port. No Vite build or npm installation is
required. Three.js 0.180.0 is already vendored locally.

## Files

- `index.html`, `style.css`: reusable viewer interface.
- `viewer.js`: shared rendering, loading, camera and animation controller.
- `examples.json`: saved model library.
- `../peasant-material-masks/viewer.js` and `../peasant-hymotion/viewer.js`:
  small adapters preserving the old review pages and comparison choices.

The viewer only reads exported assets. It never modifies the Blender files,
GLBs, mesh, rig, textures or animation data.

## Verification (2026-09-18)

`node scripts/test_model_preview.mjs` uses the installed Playwright Chromium
against the running localhost server. It covers repeat/stop/restart, paused
variant comparisons, the actual character's close-up pixels, file selection
and drop, static exports, multiple animation clips without a skeleton, models
at 0.001 / 1 / 1000 unit scales, failed-file recovery, both legacy review pages,
and mobile-width layout. Screenshots are written to `/tmp/model-preview*.png`.

## Idle and walking character playback

The default **Teal peasant · idle + walk** contains five clips. Character state
selects randomized idle, walking, or manual clip inspection. Accents wait 6–12
seconds between quiet idle periods and do not immediately repeat. Movement
interrupts a gesture with a .4-second blend. Try an idle accent skips the wait.
The runtime pauses with the viewer; manual clip inspection restores full action
weight before scrubbing. Generic models still use the ordinary clip player.

[Full behavior, validation, limitations and R3F example](../teal-peasant/idle-set/README.md).
