# Shape-gen remote jobs — consumer handoff

The service is running at `http://100.66.127.115:8765` on the GPU machine.
The live, authenticated agent guide is **`GET /docs/agent.md`**; a copy is
included here as `agent.md`. The schema is **`GET /openapi.json`**.

The API credential is stored separately at `~/.config/shape-gen/api-token` on
the Mac. It is not included in this directory. The main-machine agent can also
retrieve that file from the same path on the GPU machine over its existing SSH
connection. No inbound SSH to the Mac is required for normal API consumption.

From this directory, using the operator-provided URL:

```sh
SHAPE_API_URL='http://100.66.127.115:8765' # Replace with your service address.
python3 shape_api_client.py --base-url "$SHAPE_API_URL" health
python3 shape_api_client.py --base-url "$SHAPE_API_URL" profiles
python3 shape_api_client.py --base-url "$SHAPE_API_URL" operations
python3 shape_api_client.py --base-url "$SHAPE_API_URL" helpers
python3 shape_api_client.py --base-url "$SHAPE_API_URL" helper-download --version 1.0.3 --output ../blender-helpers-1.0.3
python3 shape_api_client.py --base-url "$SHAPE_API_URL" diagnostics JOB_ID
python3 shape_api_client.py --base-url "$SHAPE_API_URL" docs
python3 shape_api_client.py --base-url "$SHAPE_API_URL" upload front.png
python3 shape_api_client.py --base-url "$SHAPE_API_URL" submit-json shape-request.json
python3 shape_api_client.py --base-url "$SHAPE_API_URL" submit --request-id openscape-motion-01 --prompt 'A person stands still and slowly looks around.' --clip-name Candidate_Look
python3 shape_api_client.py --base-url "$SHAPE_API_URL" watch JOB_ID
python3 shape_api_client.py --base-url "$SHAPE_API_URL" download JOB_ID --output ../motion-candidate-01
```

`watch` uses authenticated SSE, reconnects using event IDs, and prints stage/log
updates. `get JOB_ID` supports polling; `cancel JOB_ID` stops a job. Every download
is SHA-256 checked. Use a new output directory to preserve accepted assets.

**Core model operations:** Hunyuan shape, BPT, HY Paint, UniRig and raw HY-Motion. Blender
work stays on the Mac. `/operations` lists parameters and required asset inputs.
Use `upload FILE` and `submit-json request.json`; primary output artifact asset IDs
can feed later GPU jobs without a download/re-upload. The agent guide includes
payloads, and `/docs/blender-handoff.md` describes the local Blender handoffs.
The `submit --prompt` shortcut retains the old combined teal-v1 retarget job.
Review candidates before merging them into the accepted character/clip library.

The actual OpenScape application source has not been changed by this handoff.

**v0.3 additions:** the helper bundle includes scripts, supporting docs and a
versioned rig contract, with archive/per-file hashes; no SSH fetch is required.
New motion jobs publish diagnostics. Older jobs can use
`GET /jobs/{id}/motion-diagnostics` without changing their existing artifacts.
Read `/docs/motion-diagnostics.md` for threshold/units/crop interpretation.
An updated client can be fetched through authenticated `GET /clients/shape_api_client.py`.

**v0.4 additions:** original TRELLIS, TRELLIS.2, DeepMesh and LATO.2 are
available through the same `submit-json` workflow. Read authenticated
`/docs/geometry-experiments.md` for book/prop experiments and example requests.
The existing client and token work; no SSH or client upgrade is required.

**v0.4.2:** new deployments can disable the legacy teal profile with
`SHAPE_API_LEGACY_PROFILE=0`. Use `submit-json` for the nine model operations;
the legacy `submit` shortcut requires a nonempty `/profiles`. Supply your own
`--base-url` when using a different host. Current installation guides and the
documentation index live at `docs/setup.md` and `docs/INDEX.md` in a repository
checkout; they are not included in this portable handoff directory.
