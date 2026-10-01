---
title: "Geometry alternatives: API 0.4.2"
summary: "Experimental operation parameters and an API sequence for comparing a book across models."
kind: "reference"
status: "current"
topics: ["api", "geometry", "deepmesh", "lato2", "trellis"]
read_when: "Choose alternative shape/retopology operations and interpret their artifacts."
---
# Geometry alternatives: API 0.4.2

Served at authenticated `GET /docs/geometry-experiments.md`. Start with
`/docs/agent.md` for uploads, authentication, SSE, cancellation and downloads.
Discover current parameter bounds using `GET /operations`.

All choices use **POST /jobs** with distinct `operation` names. No new client,
SSH connection or Blender installation on the server is required. GPU jobs run
serially through the existing shared lock. Each result is a candidate for visual
review, including when `validation.status` is `passed`.

## Choose stages independently

| Stage | Operation | Inputs | Parameters and limits |
|---|---|---|---|
| Dense shape | `hunyuan-shape` | front; optional left/back/right for mv | Existing mini/full/mv options unchanged |
| Dense shape | `trellis-shape` | front; optional left/back/right | Original TRELLIS. `steps:25`, `mode:"stochastic"` or `"multidiffusion"`; steps 1–50. Multiview stochastic steps must cover all views |
| Dense shape | `trellis2-shape` | front only | TRELLIS.2. `steps:12` (1–50), `resolution:512` or `1024`, `remesh:true`, `remesh_target:500000` (10k–500k) |
| Low-poly reconstruction | `bpt-retopology` | mesh: static GLB | Existing temperature/token/encoder options unchanged |
| Low-poly reconstruction | `deepmesh-retopology` | mesh: static GLB | `temperature:0.5` (0–2, excluding 0), `max_tokens:30000` (250–30000), `max_seconds:900` (30–1000) |
| Low-poly reconstruction | `lato2-retopology` | mesh: static GLB | `target_vertices:1200` (200–5000), `vertex_steps:24` (1–50), `topology_steps:50` (1–100), `guidance:3` (0–10), `fill_quad_rings:true`, `recalculate_normals:true` |

All accept `seed` (default 12345). The four new operations are marked
`experimental:true` in the catalog. Character-specific experiments do not
establish which model is best for a book or other prop.

**Use a foreground PNG cutout for TRELLIS.** The implemented alpha check only
requires at least one pixel with alpha below 255 and at least one pixel above
127 (on the 0–255 scale). It does not measure whether the foreground is mostly
opaque or whether background removal is good. Remove the background locally
and inspect the cutout. These adapters do not download/run a segmentation model.
Fully opaque images and images whose alpha never exceeds 127 are rejected; older
uploaded assets without alpha metadata are checked by the runner.
Use consistent views of the same object, in the same upright orientation. Original
TRELLIS multiview is upstream image-conditioning aggregation; it is different from
Hunyuan's dedicated multiview model. TRELLIS.2 is single-view here.

## Book experiment for a consumer agent

1. Upload a background-removed book reference. If a dense book GLB already exists,
   upload that too (or reuse its generated primary artifact `asset_id`).
2. Compare BPT, DeepMesh and LATO.2 against **the same dense mesh**, one candidate
   per operation initially. This isolates the reconstruction stage.
3. Separately generate original TRELLIS and TRELLIS.2 dense candidates from the
   same front reference. Start TRELLIS.2 at 512; try 1024 if 512 loses thin parts.
4. Inspect the dense meshes before spending time on reconstruction. Feed promising
   dense candidates into the preferred retopology options using their asset IDs.
5. Compare cover thickness/overhang, spine, page block, cavities/gaps, silhouette,
   triangle count, missing faces and normal direction in local Blender/preview.
   Texture work cannot reliably restore absent geometry.

Submit JSON files using the existing standard-library client. Replace the example
URL with the operator-provided address; without `--base-url`, the client defaults
to the original Tailscale deployment:

```sh
SHAPE_API_URL='http://100.66.127.115:8765' # Replace with your service address.
python3 shape_api_client.py --base-url "$SHAPE_API_URL" operations
python3 shape_api_client.py --base-url "$SHAPE_API_URL" upload book-cutout.png
python3 shape_api_client.py --base-url "$SHAPE_API_URL" submit-json book-trellis2.json
python3 shape_api_client.py --base-url "$SHAPE_API_URL" watch JOB_ID
python3 shape_api_client.py --base-url "$SHAPE_API_URL" download JOB_ID --output ./incoming/book-trellis2-01
```

`book-trellis2.json`:

```json
{
  "request_id": "book-trellis2-01",
  "operation": "trellis2-shape",
  "inputs": {"front": "IMAGE_ASSET_ID"},
  "parameters": {"resolution": 512, "steps": 12, "seed": 12345, "remesh": true}
}
```

Original TRELLIS example (omit absent views):

```json
{
  "request_id": "book-trellis-01",
  "operation": "trellis-shape",
  "inputs": {"front": "FRONT_ASSET_ID", "back": "BACK_ASSET_ID"},
  "parameters": {"steps": 25, "mode": "stochastic", "seed": 12345}
}
```

Use a generated primary mesh artifact's **`asset_id`**, not its artifact `id`,
as `MESH_ASSET_ID` below. One request per candidate:

```json
{
  "request_id": "book-deepmesh-01",
  "operation": "deepmesh-retopology",
  "inputs": {"mesh": "MESH_ASSET_ID"},
  "parameters": {"temperature": 0.5, "max_tokens": 30000, "max_seconds": 900, "seed": 12345}
}
```

```json
{
  "request_id": "book-lato2-01",
  "operation": "lato2-retopology",
  "inputs": {"mesh": "MESH_ASSET_ID"},
  "parameters": {"target_vertices": 1200, "fill_quad_rings": true, "seed": 12345}
}
```

## Outputs and interpretation

- TRELLIS: primary `result/01-dense-raw.glb` in glTF Y-up, plus conditioning
  images and `experiment.json`. Its optional vertex-color GLB is a secondary
  artifact, not a full texture-generation pass.
- TRELLIS.2: primary `result/01-dense-remesh.glb` by default; also publishes
  `01-dense-raw.glb`. With `remesh:false`, raw becomes primary. Demo remeshing
  closes many small defects but can change thin covers or narrow gaps.
  `remesh_target` is a simplification target, not low-poly reconstruction or an
  exact triangle guarantee. Geometry only; no TRELLIS.2 textures are generated.
- DeepMesh: primary `result/02-deepmesh.glb`, OBJ and `trial.json`. Generation
  must reach its end token (EOS); hitting the time/token bound fails the job
  instead of publishing a truncated mesh as successful. More tokens may take
  longer; they are not a triangle-count control.
- LATO.2: primary `result/02-lato2.glb`, OBJ, conditioning render and `lato2.json`.
  Source axes, center and scale are restored after upstream normalization.
  `target_vertices` conditions density and is **not an exact vertex or triangle
  count**. Quad-ring filling can bridge regions incorrectly; compare a second
  `fill_quad_rings:false` candidate if that occurs.
  Since 0.4.1, **`recalculate_normals:true`** adds a CPU-only Trimesh step after
  inference, before validation and publication. No Blender process or GPU is used
  by this step. `02-lato2.glb` and its OBJ contain the corrected winding and the
  primary artifact's asset ID chains the corrected mesh. The original bytes are
  retained as `02-lato2-raw.glb` / `02-lato2-raw.obj`. `normal-recalculation.json`
  records flipped-face counts, before/after topology metrics, hashes and limits.
  `lato2.json` describes the raw inference result; `validation.json` describes the
  final primary mesh. Set `recalculate_normals:false` for the original behavior
  (no extra stage, raw copies or normal report). Vertex positions and triangle
  membership/connectivity are preserved. Winding correction does not remove
  overlapping/internal faces, close holes or repair nonmanifold edges; outside
  orientation may remain ambiguous on those surfaces. Existing completed jobs
  stay unchanged; submit a new request ID to use the added stage.

Only the primary GLB is automatically registered for chaining. To use a secondary
raw/remeshed/colored GLB, download it and upload it as a new asset. Retopology
outputs need local UVs and material/texture work; input textures are not transferred.

`validation.json` reports finite geometry, valid indices, bounds, boundary edges,
nonmanifold edges and winding. These measurements **do not certify visual quality,
watertightness or suitability for animation**. Source/library hashes and model
identities accompany outputs. Unknown parameters and arbitrary paths are rejected.
Existing stage timeout, queue limits, cancellation and immutable downloads apply.
Small batches are best; failed jobs retain private intermediates for diagnosis.
