# Low-poly peasant multi-view references

Generated with the built-in image_gen tool from the supplied medieval peasant
style reference. The front view establishes the design; the side and back were
generated using that front image as their reference. Exact prompts are saved in
`prompts.json`, and dimensions, alpha checks and hashes are in `views.json`.

## Hunyuan view inputs

- `front.png`: straight-on front view.
- `left.png`: profile facing image-left, matching the orientation in Tencent's
  `assets/example_mv_images/1/left.png` example. This is the Hunyuan view label,
  not an instruction to reinterpret it as the character's anatomical left.
- `back.png`: straight-on back view.
- `style-reference.png`: original inspiration; do not include as a model view.

Each model input is a separate square RGBA PNG with transparent background.
Do not concatenate them into a sheet for Hunyuan input. No background removal
or image processing has been applied to the generated files.

Use the dedicated `tencent/Hunyuan3D-2mv` shape checkpoint with these view keys.
Install with `uv run scripts/setup_multiview.py`, then generate with:

```sh
uv run scripts/generate.py assets/peasant-turnaround --model mv --output-dir assets/peasant-mv
```

`front.png` can also be used for a single-image baseline and as the Paint reference.

The broad pose, proportions, colors and outfit were visually checked. These
are independently synthesized angles, not exact projections of one shared
mesh: hands, facial profile and small surface facets may differ. Reconstruction
quality has not yet been tested. The reference's faceted appearance does not
guarantee a low-poly Hunyuan mesh; topology and triangle budget remain a later step.
