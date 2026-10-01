---
title: "Operating the shape-gen API"
summary: "Original deployment, safe restarts, recovery, retention and measured API acceptance."
kind: "operations"
status: "current"
topics: ["api", "deployment", "recovery"]
read_when: "Operate or update the running service; use setup.md for a new host."
---
# Operating the shape-gen API

For a new host, follow [core installation](setup.md#start-the-api). The addresses
and systemd unit below describe the original deployment. Version 0.4.2 supports
`SHAPE_API_LEGACY_PROFILE=0` for model-only startup without the legacy character
files. The portable service example is `config/shape-gen-api.service.example`.

## Service

The first implementation is a single FastAPI/Uvicorn process with an asynchronous
serial worker. SQLite stores requests, jobs and replayable events; model/Blender
stages run as separate processes in their existing environments. No model is
loaded in the HTTP process. SSE clients read persisted events and cannot cancel
a job by disconnecting.

- Address: `http://100.66.127.115:8765`, bound to the Tailscale IP only.
- Local unit: `config/shape-gen-api.service` (ignored by Git), installed as a user
  systemd service. The tracked portable template is `config/shape-gen-api.service.example`.
- Agent contract: [api-agent.md](api-agent.md), also authenticated `/docs/agent.md`.
- Credential: `~/.config/shape-gen/api-token`, mode 0600; never checked in.
- State: `var/api/jobs.sqlite3`, `var/api/assets/`, `var/api/objects/`, `var/api/profile/`, `var/api/jobs/`.
- GPU lock: `~/.cache/shape-gen/gpu.lock`.

```sh
systemctl --user status shape-gen-api.service
systemctl --user restart shape-gen-api.service
journalctl --user -u shape-gen-api.service -n 50
.venv-api/bin/python scripts/shape_api_client.py health
```

To reinstall this machine's service using its existing local unit, use the commands
below. A fresh checkout has no `config/shape-gen-api.service`: first create and
customize a local unit from the tracked `.service.example` as described in
[API setup](setup.md#persistent-user-service), then install it.

```sh
uv venv .venv-api --python 3.11
uv pip install --python .venv-api/bin/python -r config/api-environment.txt
# Provision a random token in ~/.config/shape-gen/api-token with mode 0600.
mkdir -p ~/.config/systemd/user
cp config/shape-gen-api.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now shape-gen-api.service
```

The unit deliberately contains this machine's paths/address. Adapt those and
the registered profile explicitly when moving the service. Verify availability
after a reboot; user-service lifetime depends on the machine's login/linger setup.
Use **one** Uvicorn worker. A per-data-directory flock refuses a second owner.

## Applying code changes

**There is no automatic code reload.** Uvicorn runs without `--reload`.
`Restart=on-failure` restarts a crashed service; it does not watch source files.
The agent making API/worker changes must explicitly restart and check the service
as part of deploying them. Editing a file alone does not deploy imported Python code.

1. Coordinate with the consumer to pause submissions. Check `/health` and `/jobs`
   and let active/queued work finish before editing runner or service code. There
   is currently no maintenance/drain endpoint. Changing tracked scripts during a
   job can fail its provenance check; restarting interrupts an active job.
2. Once idle, stop the service before edits to keep queued jobs from starting
   against a mixture of old and new code:

   ```sh
   systemctl --user stop shape-gen-api.service
   ```

3. Make changes and run appropriate checks from `/home/sean/workspace/shape-gen`.
   For API/worker changes, run `.venv-api/bin/python -m pytest -q tests`.
   If dependencies changed, install the updated pins into the affected environment.
4. If `config/shape-gen-api.service` changed, install the unit and reload systemd:

   ```sh
   cp config/shape-gen-api.service ~/.config/systemd/user/shape-gen-api.service
   systemctl --user daemon-reload
   ```

   Ordinary Python edits do not require `daemon-reload`.
5. Start the updated service and verify readiness:

   ```sh
   systemctl --user start shape-gen-api.service
   .venv-api/bin/python scripts/shape_api_client.py health
   journalctl --user -u shape-gen-api.service -n 30 --no-pager
   ```

   If the service was left running for an idle code update, use
   `systemctl --user restart shape-gen-api.service` instead. For runner/contract
   changes, verify the affected operation before telling the consumer it is ready.

Queued jobs survive a restart. An active job becomes `interrupted` and needs a new
request ID to retry; inference does not resume automatically. SSE consumers can
reconnect using their last event ID.

Exceptions: served Markdown guides are read on each request, so documentation-only
edits appear immediately. Runner scripts are loaded when each subprocess starts;
that is not a safe hot-deployment mechanism, so still use the idle update procedure
for runner changes. Client/handoff copies on the Mac must be refreshed explicitly
when their contents change; they do not synchronize automatically.

## Model inputs and legacy rig profile

### v0.4 experimental geometry operations

Adds `trellis-shape`, `trellis2-shape`, `deepmesh-retopology`, and `lato2-retopology`.
See [consumer recipes](api-geometry-experiments.md), also served at
`/docs/geometry-experiments.md`. Fixed adapters under `scripts/` replace
asset-specific experiment paths. TRELLIS variants use `.venv-trellis2`, DeepMesh
uses `.venv-deepmesh`, and LATO.2 uses `.venv-lato2`. Environment snapshots and
`config/experimental-models.json` identify retained installations. Upstream Python
and DeepMesh compatibility files are hashed in job provenance. Checkpoints remain
local and ignored by Git; provisioning a fresh machine is still separate work.

Runners respect `SHAPE_GEN_GPU_LOCK_HELD=1` from the worker, avoiding a nested
flock deadlock. Direct experimental CLI runs acquire the hardcoded default lock
`~/.cache/shape-gen/gpu.lock`; this matches the API worker only when its lock path
has not been overridden. See the lock-path details below.
LATO.2 uses `scripts/lato2_inference.py`, a staged-memory adaptation of the
pinned upstream inference script; its license is `scripts/lato2-LICENSE.txt`.
The health response reports interpreter presence for the nine model operations,
not the legacy retarget operation or successful model inference. No Blender or music-generation operations were added.

### v0.3 helper releases and diagnostics

`GET /helpers` discovers immutable bundles under `exports/blender-helpers/<version>/`.
The release directory contains `bundle.zip`, `manifest.json` and `release.json`;
all three are included in Git. Preserve their exact bytes and back up the complete
directory. Never regenerate an existing version from newer source.
Build with `python3 scripts/build_blender_helpers.py --version N.N.N`. Rebuilding
identical bytes is allowed; changing an existing version is refused. Review/test a
new bundle on the consumer before publishing it as a recommended version. Keep old
release directories available for pinned clients. Archive/member hashes and the rig
contract version are separate from the API version. Catalog/download requests read
release files directly; adding a completed release needs no service restart.

New motion jobs run `scripts/motion_diagnostics.py` in `.venv-api` after inference,
then publish its report with the usual hashes. It has only a NumPy dependency and
does not consume GPU memory. `GET /jobs/{id}/motion-diagnostics` reads that report;
for pre-0.3 jobs, it runs the analyzer on the existing stored NPZ in a thread.
Historical jobs/artifact manifests stay unchanged. There is no automatic cache of
on-demand reports; consumers should save version/hash metadata when pinning them.

The reference bundle's analyzer is a frozen copy. Changes to live analysis code
need tests and a service restart; a matching portable helper update needs a **new
bundle version**, not edits to the published ZIP. See `/docs/motion-diagnostics.md`
for measurement definitions, source units and the estimated-contact limitation.
The standard-library client is downloadable at `/clients/shape_api_client.py`.

v0.2 adds `hunyuan-shape`, `bpt-retopology`, `hy3d-paint`, `unirig`, and `hymotion`
using the existing queue. These operations run no Blender. `GET /operations`
is the model/input/parameter catalog. General PNG/JPEG, static GLB and numeric mesh
NPZ uploads live under `var/api/objects/<sha256>` with metadata in SQLite's `assets`
table. Original bytes are preserved; generated primary outputs are registered for
chaining by asset ID. Back up `objects/` along with SQLite and the job directories.

`shape_api/model_jobs.py` constructs fixed runner commands; `scripts/api_model_io.py`
prepares numeric UniRig inputs and validates portable outputs. Each stage uses
its installed `.venv`, `.venv-bpt`, `.venv-unirig` or `.venv-hymotion` interpreter.
NumPy/Pillow in `.venv-api` validate bounded uploads without importing GPU models.

`config/api-profile-teal-v1.json` pins the accepted Blender source hash, semantic
object names and clothing sidecar hashes. With the legacy profile enabled
(`SHAPE_API_LEGACY_PROFILE=1`, the default), first startup snapshots those files
under the service's asset/profile directory; restarts verify the snapshots.
Replacing the authoring source does not silently replace the service's rig.
With `SHAPE_API_LEGACY_PROFILE=0`, startup skips that snapshot and verification
entirely and does not require the legacy files.

The legacy `hymotion-retarget` profile supports the exact accepted 34-bone source, not arbitrary
uploaded Blender scenes. The upload endpoint hash-validates/deduplicates that
source. Additional rigs need their own reviewed profile and validation before
being made available; do not weaken this check to claim general rig support.

Run manual GPU operations through the same advisory lock:

```sh
flock ~/.cache/shape-gen/gpu.lock .venv-hymotion/bin/python scripts/run_hymotion.py encode --output assets/manual-test --prompt 'A person stands still.' --duration 4 --seed 100
```

The worker holds this lock across an entire job. Core direct runners (Hunyuan,
BPT, Paint, UniRig and HY-Motion) need the external `flock` wrapper. The four
experimental model runners (TRELLIS, TRELLIS.2, DeepMesh and LATO.2), plus
`scripts/remesh_trellis2.py`, acquire the lock internally; do not wrap those five
scripts in another `flock`, which can deadlock.

The API worker honors `SHAPE_API_GPU_LOCK`; its subprocesses receive
`SHAPE_GEN_GPU_LOCK_HELD=1` and skip reacquiring the parent's lock. Direct
experimental runs use the hardcoded `~/.cache/shape-gen/gpu.lock`, ignoring
`SHAPE_API_GPU_LOCK`. Keep the API's default path when sharing the GPU with those
direct runs. A custom API lock path will not coordinate with them. Core manual
`flock` commands must likewise use the same path as the API. Other GPU
applications remain outside this advisory lock's control.

## Recovery and retention

Graceful stop interrupts the active job and terminates its subprocess group;
systemd `KillMode=control-group` also owns all descendants. The exec wrapper
requests a Linux parent-death signal. On recovery, the worker marks any stale
running record interrupted and kills its recorded process group only when its
PID/start-time identity matches. Queued jobs remain queued and resume scheduling.

Retries require new request IDs and create separate directories. There is no
automatic inference checkpoint resume. Cancellation/failed runs keep partial
files for diagnosis; their artifacts are not published. Every completed job
retains its request, provenance, events and output manifest.

Retention is manual: monitor disk usage; there is no background purge.
Do not delete job/event rows while clients rely on their replay cursors. Stop the
service before backing up SQLite plus referenced asset/job directories. Restart
after restoring them as a coherent set. Do not reuse a data directory for an
unrelated profile revision.

The model identity report copies the pinned download manifest; it is not a fresh
checksum of 25 GB of weights on each job. Runner/script hashes are recorded and
checked again before publishing. Avoid editing running-stage implementation
files during a job; such a change fails publication rather than mislabeling provenance.

## Validation

The counts in the dated acceptance sections below record those historical runs;
they are not current suite totals. Collect and run the tests in your checkout:

```sh
.venv-api/bin/python -m pytest --collect-only -q tests
.venv-api/bin/python -m pytest -q tests
```

A fresh checkout without the separately stored legacy character fixtures should
start with the [fresh-install checks](setup.md#checks-and-common-failures).

Tests use real short subprocesses, isolated temporary state and the actual HTTP
routes. They cover auth, schemas, input rejection, idempotency, serial queuing,
cancellation, subprocess failure, GPU lock waiting, persisted SSE replay and
shutdown/recovery. Model contract tests cover durable asset uploads, numeric/pickle
rejection, GLB resource constraints, input roles, parameter bounds and commands
that never invoke Blender. They do not claim to validate GPU model quality.

Live acceptance additionally requires an actual HY-Motion/Blender job, published
artifacts with verified hashes, visual inspection of renders and GLB loading.
The first live-run evidence is saved under `var/api/verification/`. Mac-side
testing must be recorded separately from local network/API checks.

### v0.2 measured acceptance (2026-09-18)

All five model stages completed on real inputs. A new mini shape output fed BPT
by asset ID; the Mac downloaded it, ran Blender 5.2.1 Smart UV Project, uploaded
the UV GLB for paint and original-vertex NPZ for UniRig, and requested raw motion.
It downloaded and hash-checked all 60 published files from that chain. Thirteen
automated tests pass. Evidence: `var/api/verification/mac-model-v02.json` and
`mac-model-v02-blender.json`.

The Mac also executed the documented rig-construction recipe: 34 bones, 778
vertices, rest-pose maximum displacement 8.94e-8 units, finite positions after
a small pose perturbation (`mac-rig-import-v02.json`). The first test selected
the imported GLB root instead of the body; the handoff guide now makes the body
selection explicit. This test does not establish deformation quality.

After adding per-operation environment artifacts and restarting the service, a
second Mac raw-motion job passed and downloaded eight verified files. All earlier
results persisted and the authenticated Blender handoff guide was reachable
(`mac-model-v02-final.json`). The BPT test mesh has open boundaries and the candidate
remains pending visual review. No production character or app source was replaced.

### v0.4 measured acceptance (2026-09-22)

All four added operations completed through authenticated HTTP jobs, SSE, numeric
validation, primary-asset registration and checksum-verified artifact downloads.
Evidence: `var/api/verification/geometry-v04/acceptance.json` and sibling job/event
records. The suite passes 34 tests. A generated primary asset was also accepted
as a subsequent reconstruction input and its queued test job canceled successfully.

- DeepMesh: synthetic book-shaped GLB, default sampler settings, 60 output triangles.
- LATO.2: same translated/scaled book fixture, target 400 vertices, 1,039 triangles.
  Initial all-networks-resident inference ran out of VRAM; the staged adaptation
  completed in 63.76 seconds with 1,961.3 MiB peak PyTorch allocation. This excludes
  native/driver allocations and is not a general memory ceiling.
- Original TRELLIS: retained front/back character cutouts, stochastic multiview,
  12 steps, 162,296 triangles.
- TRELLIS.2: retained front cutout, 512, 12 steps, remesh enabled, 471,612 triangles.

These are execution checks, not book visual acceptance. The 1024 route, alternate
sampler mode and extreme parameter limits were not GPU-tested in this deployment.
Topology metrics remain descriptive; successful jobs can contain defects.


### v0.4.1 normal recalculation (2026-09-22)

New LATO.2 submissions explicitly store `recalculate_normals:true` by default.
The worker runs `scripts/recalculate_lato_normals.py` in `.venv` as a separate
`recalculate-normals` stage before output validation. This is CPU-only Trimesh;
no Blender instance. The queue retains its existing shared lock across all stages.
The script is included in job provenance and LATO.2 operation version is now 2.
Old persisted requests without the flag retain their original behavior.

Primary filenames/asset registration remain unchanged. The step keeps raw GLB/OBJ
bytes, verifies positions and face membership are unchanged, and publishes a
before/after report. Topology defects are reported, not silently removed.
Historic job artifacts are immutable and are not retroactively recalculated.

Verification: 36 tests pass, including intentionally flipped disconnected closed
meshes, nonmanifold preservation, unchanged vertex positions/face membership, raw
byte retention, and default/opt-out/legacy command paths. Live job
`df7b5620da344f4c953bfdd0c8f912c9` repeated the consumer book settings, flipped 379
of 920 triangles, retained 246 nonmanifold edges, and published both raw/corrected
artifacts and its report. All downloads were checksum-verified; the registered
primary asset hash matches the corrected report. Evidence:
`var/api/verification/normals-v041/`. This verifies the stage, not visual acceptance.
