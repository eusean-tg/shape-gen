"""API contracts, durable replay, real process cancellation and queue behavior."""
import asyncio
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from fastapi.testclient import TestClient
import pytest

from shape_api.server import ROOT, Settings, create_app
from shape_api.store import Store
from shape_api.worker import Worker, process_identity


class FixtureWorker(Worker):
    async def execute(self, job):
        directory = self.settings.data / 'jobs' / job['id']
        directory.mkdir(parents=True)
        mode = job['request']['parameters']['prompt']
        if mode == 'fail':
            code = 'import sys; print("fixture failure",flush=True); sys.exit(7)'
        elif mode == 'sleep':
            code = 'import time; print("fixture running",flush=True); time.sleep(60)'
        else:
            code = 'import time; print("fixture ready",flush=True); time.sleep(.3)'
        await self.run_stage(job['id'], 'fixture', [sys.executable, '-c', code])
        self.store.update(job['id'], state='succeeded')


@pytest.fixture
def settings(tmp_path):
    token = tmp_path / 'token'
    token.write_text('t' * 64)
    return Settings(data=tmp_path / 'data', token_file=token, gpu_lock=tmp_path / 'gpu.lock')


def client(settings):
    return TestClient(create_app(settings, FixtureWorker), headers={'Authorization': 'Bearer ' + 't' * 64})


def submit(c, request_id='test', prompt='normal'):
    rig = c.get('/profiles').json()['profiles'][0]['rig_asset_id']
    return c.post('/jobs', json={'request_id': request_id, 'rig_asset_id': rig,
                                'parameters': {'prompt': prompt}})


def wait(c, job_id, states, timeout=10):
    stop = time.monotonic() + timeout
    while time.monotonic() < stop:
        job = c.get('/jobs/' + job_id).json()
        if job['state'] in states:
            return job
        time.sleep(.05)
    raise AssertionError(f'Timed out: {job}')


def test_auth_schema_upload_and_idempotency(settings):
    with client(settings) as c:
        for path in ['/health', '/profiles', '/docs/agent.md', '/openapi.json']:
            assert c.get(path, headers={'Authorization': 'Bearer wrong'}).status_code == 401
        assert c.get('/health').status_code == 200
        assert c.get('/docs/agent.md').headers['content-type'].startswith('text/markdown')
        assert '/jobs/{job_id}/events' in c.get('/openapi.json').json()['paths']
        first = submit(c)
        assert first.status_code == 202
        assert submit(c).json()['id'] == first.json()['id']
        assert submit(c, prompt='changed').status_code == 409
        assert c.post('/jobs', json={'request_id': '../bad'}).status_code == 422
        rig = c.get('/profiles').json()['profiles'][0]['rig_asset_id']
        assert c.post('/jobs', json={'request_id': 'too-long', 'rig_asset_id': rig,
            'parameters': {'prompt': 'normal', 'duration': 60}}).status_code == 422
        assert c.post('/assets', content=b'not a rig', headers={'Content-Type': 'application/octet-stream'}).status_code == 422
        source = settings.data / 'assets' / (rig + '.blend')
        assert c.post('/assets', content=source.read_bytes(), headers={'Content-Type': 'application/octet-stream'}).json()['id'] == rig
        assert c.get('/artifacts/invalid').status_code == 404


def test_replay_terminal_and_persistence(settings):
    with client(settings) as c:
        job = submit(c).json()
        wait(c, job['id'], {'succeeded'})
        events = c.get(f'/jobs/{job["id"]}/logs').json()['events']
        assert any(e['event'] == 'log' and 'fixture ready' in e['data']['text'] for e in events)
        cursor = events[len(events) // 2]['id']
        text = c.get(f'/jobs/{job["id"]}/events', headers={'Last-Event-ID': str(cursor)}).text
        ids = [int(line[4:]) for line in text.splitlines() if line.startswith('id: ')]
        assert ids == [e['id'] for e in events if e['id'] > cursor]
        assert 'event: end' in text
        assert c.get(f'/jobs/{job["id"]}/events', headers={'Last-Event-ID': '-1'}).status_code == 400
    with client(settings) as c:
        assert c.get('/jobs/' + job['id']).json()['state'] == 'succeeded'
        assert c.get(f'/jobs/{job["id"]}/logs').json()['events'] == events


def test_serial_queue_cancel_running_queued_and_failure(settings):
    with client(settings) as c:
        a = submit(c, 'first', 'sleep').json()['id']
        first = wait(c, a, {'running'})
        while not first['process']:
            time.sleep(.05)
            first = c.get('/jobs/' + a).json()
        pid = first['process']['pid']
        b = submit(c, 'second', 'normal').json()['id']
        assert c.get('/jobs/' + b).json()['state'] == 'queued'
        assert c.post('/jobs/' + b + '/cancel').json()['state'] == 'canceled'
        c.post('/jobs/' + a + '/cancel')
        assert wait(c, a, {'canceled'})['process'] is None
        assert process_identity(pid) is None
        assert c.post('/jobs/' + a + '/cancel').json()['state'] == 'canceled'
        failed = submit(c, 'failed', 'fail').json()['id']
        assert 'exited 7' in wait(c, failed, {'failed'})['error']
        done = submit(c, 'after-failure').json()['id']
        wait(c, done, {'succeeded'})
        assert c.get('/jobs/' + a + '/artifacts').json()['artifacts'] == []


def test_gpu_lock_shutdown_and_restart(settings):
    with settings.gpu_lock.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with client(settings) as c:
            job = submit(c, prompt='sleep').json()['id']
            time.sleep(.4)
            assert c.get('/jobs/' + job).json()['state'] == 'queued'
            fcntl.flock(lock, fcntl.LOCK_UN)
            active = wait(c, job, {'running'})
            while not active['process']:
                time.sleep(.05)
                active = c.get('/jobs/' + job).json()
            pid = active['process']['pid']
        assert process_identity(pid) is None
    with client(settings) as c:
        assert c.get('/jobs/' + job).json()['state'] == 'interrupted'
        again = submit(c, 'retry').json()['id']
        wait(c, again, {'succeeded'})


def test_recovery_kills_recorded_orphan(settings):
    store = Store(settings.data)
    job, _ = store.submit({'request_id': 'orphan'})
    process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)
    try:
        store.update(job['id'], state='running', process={'pid': process.pid, 'start_ticks': process_identity(process.pid)})
        Worker(store, settings, {}).recover()
        process.wait(timeout=5)
        assert store.get(job['id'])['state'] == 'interrupted'
    finally:
        process.kill()
        process.wait()
        store.db.close()
