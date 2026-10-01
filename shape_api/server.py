"""Authenticated HTTP/SSE interface; no GPU model imports in the API process."""
import asyncio
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field
import fcntl
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .store import Store, TERMINAL
from .worker import Worker, sha256
from .assets import MAX_UPLOAD, inspect_upload, register_file, public_asset
from .operations import MODELS, catalog, validate_inputs
from scripts.motion_diagnostics import diagnose_file

ROOT = Path(__file__).resolve().parents[1]
VERSION = '0.4.2'


@dataclass
class Settings:
    root: Path = ROOT
    data: Path = field(default_factory=lambda: Path(os.environ.get('SHAPE_API_DATA', ROOT / 'var/api')))
    token_file: Path = field(default_factory=lambda: Path(os.environ.get(
        'SHAPE_API_TOKEN_FILE', Path.home() / '.config/shape-gen/api-token')))
    gpu_lock: Path = field(default_factory=lambda: Path(os.environ.get(
        'SHAPE_API_GPU_LOCK', Path.home() / '.cache/shape-gen/gpu.lock')))
    blender: Path = field(default_factory=lambda: Path(os.environ.get(
        'SHAPE_API_BLENDER', Path.home() / '.local/bin/blender')))
    stage_timeout: float = 1200
    legacy_profile: bool = field(default_factory=lambda: os.environ.get('SHAPE_API_LEGACY_PROFILE', '1') != '0')


class MotionParameters(BaseModel):
    model_config = ConfigDict(extra='forbid')
    prompt: str = Field(min_length=3, max_length=500)
    seed: int = Field(default=12345, ge=0, le=4294967295, strict=True)
    duration: Literal[4.0] = 4.0
    clip_name: str = Field(default='Candidate_Motion', pattern=r'^[A-Za-z][A-Za-z0-9_-]{0,63}$')


class JobRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    operation: Literal['hymotion-retarget', 'hunyuan-shape', 'bpt-retopology', 'hy3d-paint', 'unirig', 'hymotion',
                       'trellis-shape', 'trellis2-shape', 'deepmesh-retopology', 'lato2-retopology'] = 'hymotion-retarget'
    profile: Literal['teal-v1'] | None = None
    rig_asset_id: str | None = Field(default=None, pattern=r'^[0-9a-f]{64}$')
    inputs: dict[str, str] = Field(default_factory=dict, max_length=4)
    parameters: dict = Field(default_factory=dict)


def prepare_profile(settings):
    profile = json.loads((settings.root / 'config/api-profile-teal-v1.json').read_text())
    asset_dir = settings.data / 'assets'
    asset_dir.mkdir(parents=True, exist_ok=True)
    destination = asset_dir / (profile['rig_asset_id'] + '.blend')
    if not destination.exists():
        source = settings.root / profile['source_blend']
        if sha256(source) != profile['rig_asset_id']:
            raise RuntimeError('Profile source changed; create a new profile revision explicitly')
        temporary = destination.with_suffix('.tmp')
        shutil.copyfile(source, temporary)
        temporary.replace(destination)
        destination.chmod(0o444)
    if sha256(destination) != profile['rig_asset_id']:
        raise RuntimeError('Stored rig input failed hash verification')
    sidecars = settings.data / 'profile'
    sidecars.mkdir(exist_ok=True)
    for name, digest in profile['sidecars'].items():
        target = sidecars / name
        if not target.exists():
            source = settings.root / profile['texture_directory'] / name
            if sha256(source) != digest:
                raise RuntimeError(f'Profile sidecar changed: {name}')
            shutil.copyfile(source, target)
            target.chmod(0o444)
        if sha256(target) != digest:
            raise RuntimeError(f'Stored profile sidecar failed hash verification: {name}')
    return profile


def create_app(settings=None, worker_class=Worker):
    settings = settings or Settings()
    security = HTTPBearer(auto_error=False)

    async def authenticate(credentials: HTTPAuthorizationCredentials | None = Depends(security)):
        if credentials is None or not hmac.compare_digest(credentials.credentials, app.state.token):
            raise HTTPException(401, 'Bearer authentication required', headers={'WWW-Authenticate': 'Bearer'})

    @asynccontextmanager
    async def lifespan(app):
        settings.data.mkdir(parents=True, exist_ok=True)
        lock = (settings.data / 'worker.lock').open('a')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            token = settings.token_file.read_text().strip()
            if len(token) < 32:
                raise RuntimeError('API credential must have at least 32 characters')
            app.state.token = token
            app.state.profile = prepare_profile(settings) if settings.legacy_profile else None
            store = app.state.store = Store(settings.data)
            worker = app.state.worker = worker_class(store, settings, app.state.profile)
            worker.recover()
            task = app.state.worker_task = asyncio.create_task(worker.run())
            try:
                yield
            finally:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
                store.db.close()
        finally:
            lock.close()

    app = FastAPI(title='Shape-gen jobs', version=VERSION, lifespan=lifespan,
                  dependencies=[Depends(authenticate)], docs_url=None, redoc_url=None, openapi_url=None)

    def get_job(job_id):
        job = app.state.store.get(job_id)
        if job is None:
            raise HTTPException(404, 'Unknown job')
        return job

    @app.get('/health')
    async def health(response: Response):
        requirements = ([settings.root / '.venv-hymotion/bin/python', settings.blender,
                         settings.root / 'models/hy-motion/tencent/HY-Motion-1.0-Lite/latest.ckpt']
                        if settings.legacy_profile else [])
        ready = all(p.exists() for p in requirements) and not app.state.worker_task.done()
        environments = {'hunyuan-shape': '.venv', 'bpt-retopology': '.venv-bpt',
                        'trellis-shape': '.venv-trellis2', 'trellis2-shape': '.venv-trellis2',
                        'deepmesh-retopology': '.venv-deepmesh', 'lato2-retopology': '.venv-lato2',
                        'hy3d-paint': '.venv', 'unirig': '.venv-unirig', 'hymotion': '.venv-hymotion'}
        response.status_code = 200 if ready else 503
        return {'status': 'ready' if ready else 'unavailable', 'version': VERSION,
                'gpu_concurrency': 1, 'active_job': app.state.worker.active_job,
                'runner_environments_present': {name: (settings.root / env / 'bin/python').exists()
                                                for name, env in environments.items()},
                'legacy_profile_enabled': settings.legacy_profile,
                'readiness_scope': 'Worker ready; legacy requirements checked only when enabled. Environment presence is not model availability; no model load or VRAM test.'}

    @app.get('/profiles')
    async def profiles():
        p = app.state.profile
        if p is None:
            return {'profiles': []}
        return {'profiles': [{'id': p['id'], 'rig_asset_id': p['rig_asset_id'],
                              'description': p['description'], 'bones': p['bones'],
                              'supported_operations': ['hymotion-retarget'], 'duration_seconds': [4],
                              'sidecars': p['sidecars'], 'upload_policy': 'Exact registered rig revision only'}]}

    @app.get('/operations')
    async def operations():
        return {'operations': catalog(), 'legacy_operation': 'hymotion-retarget' if settings.legacy_profile else None,
                'blender_work': 'Run repair, UVs, rig construction and retargeting on the consumer.'}

    def helper_release(version):
        if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version):
            raise HTTPException(404, 'Unknown helper version')
        directory = settings.root / 'exports/blender-helpers' / version
        if not (directory / 'release.json').is_file():
            raise HTTPException(404, 'Unknown helper version')
        return directory, json.loads((directory / 'release.json').read_text())

    @app.get('/helpers')
    async def helpers():
        entries = []
        for path in (settings.root / 'exports/blender-helpers').glob('*/release.json'):
            if re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', path.parent.name):
                entries.append(json.loads(path.read_text()))
        return {'helpers': sorted(entries, key=lambda item: tuple(map(int, item['version'].split('.')))),
                'execution': 'Download and run locally; no Blender execution through these endpoints'}

    @app.get('/helpers/blender-helpers/{version}/manifest')
    async def helper_manifest(version: str):
        directory, entry = helper_release(version)
        path = directory / 'manifest.json'
        if await asyncio.to_thread(sha256, path) != entry['manifest_sha256']:
            raise HTTPException(409, 'Helper manifest integrity check failed')
        return FileResponse(path, media_type='application/json', headers={'X-Checksum-SHA256': entry['manifest_sha256']})

    @app.get('/helpers/blender-helpers/{version}/download')
    async def helper_download(version: str):
        directory, entry = helper_release(version)
        path = directory / 'bundle.zip'
        if path.stat().st_size != entry['bytes'] or await asyncio.to_thread(sha256, path) != entry['sha256']:
            raise HTTPException(409, 'Helper archive integrity check failed')
        return FileResponse(path, filename=f'blender-helpers-{version}.zip',
                            headers={'X-Checksum-SHA256': entry['sha256']})

    @app.post('/assets')
    async def upload(request: Request):
        if request.headers.get('content-type', '').split(';')[0] != 'application/octet-stream':
            raise HTTPException(415, 'Send the file as application/octet-stream (raw body)')
        digest = hashlib.sha256()
        size = 0
        with tempfile.NamedTemporaryFile(dir=settings.data, prefix='upload-') as temporary:
            async for block in request.stream():
                size += len(block)
                if size > MAX_UPLOAD:
                    raise HTTPException(413, 'Input exceeds the 64 MiB upload limit')
                digest.update(block)
                temporary.write(block)
            temporary.flush()
            asset_id = digest.hexdigest()
            if app.state.profile and asset_id == app.state.profile['rig_asset_id']:
                return {'id': asset_id, 'bytes': size, 'profile': 'teal-v1', 'deduplicated': True}
            existing = app.state.store.asset(asset_id)
            if existing:
                return {**public_asset(existing), 'deduplicated': True}
            try:
                metadata = await asyncio.to_thread(inspect_upload, temporary.name)
            except Exception as error:
                raise HTTPException(422, f'Invalid asset: {error}') from error
            record = register_file(app.state.store, settings.data, temporary.name, metadata)
            return {**public_asset(record), 'deduplicated': False}

    def get_asset(asset_id):
        record = app.state.store.asset(asset_id)
        if record is None:
            raise HTTPException(404, 'Unknown asset')
        return record

    @app.get('/assets/{asset_id}')
    async def asset(asset_id: str):
        return public_asset(get_asset(asset_id))

    @app.get('/assets/{asset_id}/content')
    async def asset_content(asset_id: str):
        record = get_asset(asset_id)
        return FileResponse(settings.data / record['path'], filename=asset_id + record['extension'],
                            headers={'X-Checksum-SHA256': record['sha256']})

    @app.post('/jobs', status_code=202)
    async def submit(request: JobRequest, response: Response):
        store = app.state.store
        try:
            if request.operation == 'hymotion-retarget':
                if app.state.profile is None:
                    raise ValueError('Legacy profile is disabled; use named model operations with inputs')
                if request.rig_asset_id != app.state.profile['rig_asset_id'] or request.inputs:
                    raise ValueError('Legacy operation requires the registered teal-v1 rig and no inputs')
                params = MotionParameters.model_validate(request.parameters).model_dump()
                if not params['prompt'].strip():
                    raise ValueError('Prompt must not be blank')
                payload = {'request_id': request.request_id, 'operation': request.operation,
                           'profile': 'teal-v1', 'rig_asset_id': request.rig_asset_id, 'parameters': params}
            else:
                if request.rig_asset_id is not None or request.profile is not None:
                    raise ValueError('Use inputs for model operations, not profile or rig_asset_id')
                params = MODELS[request.operation].model_validate(request.parameters).model_dump()
                validate_inputs(request.operation, request.inputs, params, store)
                payload = {'request_id': request.request_id, 'operation': request.operation,
                           'inputs': request.inputs, 'parameters': params}
        except (ValueError, ValidationError) as error:
            raise HTTPException(422, str(error)) from error
        existing_ids = {j['request']['request_id'] for j in store.jobs()}
        if request.request_id not in existing_ids and sum(j['state'] == 'queued' for j in store.jobs()) >= 16:
            raise HTTPException(429, 'Queue is full; retry later')
        try:
            job, created = store.submit(payload)
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        response.status_code = 202 if created else 200
        response.headers['Location'] = f'/jobs/{job["id"]}'
        return job

    @app.get('/jobs')
    async def jobs(limit: int = Query(default=50, ge=1, le=200)):
        return {'jobs': app.state.store.jobs()[-limit:][::-1]}

    @app.get('/jobs/{job_id}')
    async def job(job_id: str):
        return get_job(job_id)

    @app.post('/jobs/{job_id}/cancel')
    async def cancel(job_id: str):
        record = get_job(job_id)
        if record['state'] in TERMINAL:
            return record
        changes = {'cancel_requested': True}
        if record['state'] == 'queued':
            changes['state'] = 'canceled'
        return app.state.store.update(job_id, **changes)

    @app.get('/jobs/{job_id}/logs')
    async def logs(job_id: str, after: int = Query(0, ge=0, le=9223372036854775807), limit: int = Query(200, ge=1, le=1000)):
        get_job(job_id)
        events = app.state.store.events(job_id, after, limit)
        return {'events': events, 'next_cursor': events[-1]['id'] if events else after}

    @app.get('/jobs/{job_id}/events')
    async def events(job_id: str, request: Request, after: int = Query(0, ge=0, le=9223372036854775807),
                     last_event_id: str | None = Header(default=None)):
        get_job(job_id)
        if last_event_id is not None:
            if not last_event_id.isdecimal() or len(last_event_id) > 18:
                raise HTTPException(400, 'Last-Event-ID must be a nonnegative integer')
            after = int(last_event_id)
        if after > 9223372036854775807:
            raise HTTPException(400, 'Event cursor is out of range')

        async def stream():
            cursor, heartbeat = after, 0
            yield 'retry: 1000\n\n'
            while True:
                rows = app.state.store.events(job_id, cursor)
                for row in rows:
                    cursor = row['id']
                    yield f'id: {cursor}\nevent: {row["event"]}\ndata: {json.dumps(row)}\n\n'
                # Drain ALL saved rows before closing a completed stream.
                if not rows and get_job(job_id)['state'] in TERMINAL:
                    yield 'event: end\ndata: {}\n\n'
                    return
                if await request.is_disconnected():
                    return
                if rows:
                    continue
                heartbeat += 1
                if heartbeat >= 40:
                    yield ': heartbeat\n\n'
                    heartbeat = 0
                await asyncio.sleep(.25)

        return StreamingResponse(stream(), media_type='text/event-stream', headers={
            'Cache-Control': 'no-cache, no-transform', 'X-Accel-Buffering': 'no'})

    @app.get('/jobs/{job_id}/artifacts')
    async def artifacts(job_id: str):
        record = get_job(job_id)
        return {'state': record['state'], 'visual_acceptance': 'pending', 'artifacts': record['artifacts']}

    @app.get('/jobs/{job_id}/motion-diagnostics')
    async def motion_diagnostics(job_id: str):
        record = get_job(job_id)
        if record['request']['operation'] not in {'hymotion', 'hymotion-retarget'}:
            raise HTTPException(422, 'Motion diagnostics require a motion operation')
        if record['state'] != 'succeeded':
            raise HTTPException(409, 'Wait for a successfully completed motion job')
        directory = settings.data / 'jobs' / job_id
        artifact = next((a for a in record['artifacts'] if a['name'].endswith('/motion-diagnostics.json')), None)
        if artifact:
            source = directory / artifact['name']
            if await asyncio.to_thread(sha256, source) != artifact['sha256']:
                raise HTTPException(409, 'Diagnostic artifact failed integrity verification')
            report = json.loads(source.read_text())
            delivery = 'published-artifact'
        else:
            subdir = 'result' if record['request']['operation'] == 'hymotion' else 'motion'
            source = directory / subdir / 'motion.npz'
            if not source.is_file():
                raise HTTPException(404, 'Raw motion is unavailable for analysis')
            report = await asyncio.to_thread(diagnose_file, source)
            motion_artifact = next((a for a in record['artifacts'] if a['name'] == subdir + '/motion.npz'), None)
            if motion_artifact and report['source_sha256'] != motion_artifact['sha256']:
                raise HTTPException(409, 'Motion artifact failed integrity verification')
            delivery = 'on-demand; original job and artifacts unchanged'
        return {'job_id': job_id, 'delivery': delivery, 'scope': 'Raw generated motion before retargeting/cleanup',
                'diagnostics': report}

    @app.get('/artifacts/{artifact_id}')
    async def download(artifact_id: str):
        if not re.fullmatch(r'[0-9a-f]{32}-[0-9]+', artifact_id):
            raise HTTPException(404, 'Unknown artifact')
        record = get_job(artifact_id.split('-')[0])
        artifact = next((a for a in record['artifacts'] if a['id'] == artifact_id), None)
        if not artifact or record['state'] != 'succeeded':
            raise HTTPException(404, 'Artifact is not published')
        directory = (settings.data / 'jobs' / record['id']).resolve()
        path = (directory / artifact['name']).resolve()
        if not path.is_relative_to(directory) or not path.is_file():
            raise HTTPException(404, 'Artifact is unavailable')
        return FileResponse(path, filename=path.name, headers={'X-Checksum-SHA256': artifact['sha256']})

    @app.get('/docs/agent.md', response_class=PlainTextResponse)
    async def agent_docs():
        return PlainTextResponse((settings.root / 'docs/api-agent.md').read_text(), media_type='text/markdown')

    @app.get('/docs/geometry-experiments.md', response_class=PlainTextResponse)
    async def geometry_experiments():
        return PlainTextResponse((settings.root / 'docs/api-geometry-experiments.md').read_text(), media_type='text/markdown')

    @app.get('/docs/blender-handoff.md', response_class=PlainTextResponse)
    async def blender_docs():
        return PlainTextResponse((settings.root / 'docs/blender-handoff.md').read_text(), media_type='text/markdown')

    @app.get('/docs/motion-diagnostics.md', response_class=PlainTextResponse)
    async def diagnostic_docs():
        return PlainTextResponse((settings.root / 'docs/motion-diagnostics.md').read_text(), media_type='text/markdown')

    @app.get('/clients/shape_api_client.py')
    async def python_client():
        path = settings.root / 'scripts/shape_api_client.py'
        return FileResponse(path, filename=path.name, media_type='text/x-python',
                            headers={'X-Checksum-SHA256': sha256(path)})

    @app.get('/openapi.json')
    async def openapi():
        return app.openapi()

    return app


app = create_app()
