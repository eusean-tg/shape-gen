# Makima geometry knob audit

[Findings, limits and settings](../../docs/research/makima-knob-audit-2026-09-19.md)
· [Interactive preview](http://localhost:5173/makima-knob-audit/)
· [Clay-render gallery](http://localhost:5173/makima-knob-audit/gallery.html)

## Gap experiment — not an accepted replacement

Visual review found worse face and knee shapes despite the larger braid gap. The original BPT is the viewer default again. See the gallery for face/knee close-ups.

- `mv-original-fixed/r384-clean.glb`: cleaned dense shape with clearer upper braid separation.
- `bpt-mv-original/02-bpt-closed.glb`: BPT reconstruction, 2,178 triangles, two tiny triangular holes closed.
- Raw files remain alongside these, with `cleanup.json` describing the changes.

## Reproduction on this machine

Run from `/home/sean/workspace/shape-gen`. These scripts deliberately reference
the archived Makima inputs and existing verified checkpoints. They are experiment
tools, not general API runners. Use new output labels; existing trials are protected
against accidental overwrite. Shape and BPT scripts acquire the shared GPU lock.

```sh
.venv/bin/python assets/makima-knob-audit/shape_trial.py repeat-original --source original --model mv --resolutions 384
.venv-bpt/bin/python assets/makima-knob-audit/bpt_trial.py assets/makima-knob-audit/repeat-original/r384-iso0.glb --output-dir assets/makima-knob-audit/repeat-original-bpt
```

Shape defaults: seed 12345, 50 steps, guidance 5, four views for mv, corrected
experimental hierarchical decoder. Use `--latent-from PATH` to compare extraction
settings on the same sampled shape. `--decoder vanilla` selects the unmodified
exhaustive decoder, which is slower at large grids. Shape latents and metadata
are saved in each trial directory.

For a BPT comparison that holds the conditioning points fixed:

```sh
.venv-bpt/bin/python assets/makima-knob-audit/bpt_trial.py assets/makima-geometry-review/dense/result/01-dense.glb --cloud assets/makima-knob-audit/baseline-points.npy --temperature .3 --output-dir assets/makima-knob-audit/repeat-temperature
```

`clouds-original/*.npy` are the authoritative saved inputs for the alternate
sampling trials. Their initial candidate pool was generated with a newer
trimesh RNG implementation; re-running `make_clouds.py` does not reproduce it
just by setting NumPy's global seed. Do not overwrite those saved inputs.

## Review generation

```sh
python3 assets/makima-knob-audit/build_review.py
/home/sean/.local/bin/blender -b -t 4 --python assets/makima-knob-audit/render_trials.py
python3 assets/makima-knob-audit/build_review.py
python3 assets/makima-knob-audit/summarize_trials.py
```

Rendering uses CPU Cycles, not the GPU inference lock. Existing images are
skipped. The existing preview server serves this folder via a symlink from
`assets/peasant-deformation-check/makima-knob-audit` and reuses the shared viewer.
The accepted character preview is unchanged.

`mv-baseline` and `mv-original` contain failed extraction attempts and valid saved
latent samples. Their replacement extraction runs are `mv-resolutions` and
`mv-original-fixed`. The report explains the installed upstream fast-path issue
and validation of the experiment-only correction. Production uses the vanilla
path and was not modified.
