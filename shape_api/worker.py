"""Serial subprocess worker with a shared GPU lock and durable stage events."""
import asyncio
import codecs
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import time

from .store import TERMINAL, now


def sha256(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def process_identity(pid):
    try:
        # Account for spaces in the process name; field 22 is the start tick.
        return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]
    except (FileNotFoundError, ProcessLookupError):
        return None


def kill_group(pid, sig):
    try:
        os.killpg(pid, sig)
    except ProcessLookupError:
        pass


class Canceled(Exception):
    pass


class Worker:
    def __init__(self, store, settings, profile):
        self.store, self.settings, self.profile = store, settings, profile
        self.process = None
        self.active_job = None
        self.stopping = False

    def recover(self):
        for job in self.store.jobs():
            if job['state'] != 'running':
                continue
            process = job.get('process')
            if process and process_identity(process['pid']) == process['start_ticks']:
                kill_group(process['pid'], signal.SIGKILL)
            self.store.update(job['id'], state='interrupted', process=None,
                              error='Service stopped during execution; submit a new request_id to retry.')

    async def stop_process(self):
        process = self.process
        if process is None:
            return
        kill_group(process.pid, signal.SIGTERM)
        try:
            await asyncio.wait_for(process.wait(), 3)
        except asyncio.TimeoutError:
            pass
        # Also reap descendants if the leader exited before its children.
        kill_group(process.pid, signal.SIGKILL)
        await process.wait()

    def check_cancel(self, job_id):
        if self.store.get(job_id)['cancel_requested']:
            raise Canceled()

    async def run_stage(self, job_id, name, command):
        self.check_cancel(job_id)
        self.store.update(job_id, stage=name)
        start = time.monotonic()
        self.store.event(job_id, 'stage', {'name': name, 'state': 'started'})
        env = dict(os.environ, PYTHONUNBUFFERED='1', SHAPE_GEN_GPU_LOCK_HELD='1')
        env.pop('SHAPE_API_TOKEN', None)
        # The tiny exec wrapper arranges SIGKILL if the server dies before it
        # records the child's PID. systemd also owns the entire process cgroup.
        wrapper = [str(self.settings.root / '.venv-api/bin/python'),
                   str(self.settings.root / 'scripts/api_stage_exec.py')]
        self.process = await asyncio.create_subprocess_exec(
            *wrapper, *map(str, command), cwd=self.settings.root, env=env,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            start_new_session=True)
        process = self.process
        self.store.update(job_id, process={'pid': process.pid,
                                          'start_ticks': process_identity(process.pid)})

        async def read_logs():
            decoder = codecs.getincrementaldecoder('utf-8')('replace')
            while block := await process.stdout.read(4096):
                text = decoder.decode(block)
                if text:
                    self.store.event(job_id, 'log', {'stage': name, 'text': text})
            tail = decoder.decode(b'', final=True)
            if tail:
                self.store.event(job_id, 'log', {'stage': name, 'text': tail})

        reader = asyncio.create_task(read_logs())
        try:
            while process.returncode is None:
                self.check_cancel(job_id)
                if time.monotonic() - start > self.settings.stage_timeout:
                    raise RuntimeError(f'Stage {name} exceeded its time limit')
                await asyncio.sleep(.2)
            await reader
            self.check_cancel(job_id)
            self.store.event(job_id, 'stage', {'name': name, 'state': 'finished',
                                             'exit_code': process.returncode,
                                             'seconds': time.monotonic() - start})
            if process.returncode:
                raise RuntimeError(f'Stage {name} exited {process.returncode}; inspect job logs')
        finally:
            if process.returncode is None or not reader.done():
                await self.stop_process()
            await reader
            self.process = None
            self.store.update(job_id, process=None)

    def stages(self, job, directory, source):
        root = self.settings.root
        params = job['request']['parameters']
        common = ['--output', directory / 'motion', '--prompt', params['prompt'],
                  '--duration', params['duration'], '--seed', params['seed']]
        stages = [(name, [root / '.venv-hymotion/bin/python', root / 'scripts/run_hymotion.py',
                          name, *common]) for name in ['encode', 'motion']]
        stages += [('motion-diagnostics', [root / '.venv-api/bin/python', root / 'scripts/motion_diagnostics.py',
                                           directory / 'motion/motion.npz', '--output', directory / 'motion/motion-diagnostics.json'])]
        blender = [self.settings.blender, '-b', '-t', '4', '--disable-autoexec', '--python-exit-code', '1']
        stages += [
            ('retarget', [*blender, '--python', root / 'scripts/retarget_hymotion_peasant.py', '--',
                          '--source', source, '--motion', directory / 'motion/motion.npz',
                          '--output', directory / 'candidate', '--no-pouch', '--level-foot-rest',
                          '--arm-clearance', '5', '--skip-renders', '--clip-name', params['clip_name']]),
            ('validate-and-render', [*blender, '--python', root / 'scripts/review_api_motion.py', '--',
                                     '--source', source, '--directory', directory / 'candidate',
                                     '--clip-name', params['clip_name'], '--frames', round(params['duration'] * 30)]),
        ]
        return stages

    async def execute(self, job):
        if job['request']['operation'] != 'hymotion-retarget':
            from .model_jobs import execute_model
            return await execute_model(self, job)
        job_id = job['id']
        directory = self.settings.data / 'jobs' / job_id
        directory.mkdir(parents=True, exist_ok=False)
        source = self.settings.data / 'assets' / (job['request']['rig_asset_id'] + '.blend')
        if sha256(source) != job['request']['rig_asset_id']:
            raise RuntimeError('Rig input hash changed')
        scripts = ['scripts/run_hymotion.py', 'scripts/motion_diagnostics.py', 'scripts/retarget_hymotion_peasant.py',
                   'scripts/review_api_motion.py', 'scripts/api_stage_exec.py',
                   'shape_api/worker.py', 'shape_api/server.py', 'shape_api/store.py']
        script_hashes = {p: sha256(self.settings.root / p) for p in scripts}
        provenance = {'operation_version': 2, 'created_at': now(), 'request': job['request'],
                      'profile': self.profile, 'script_sha256': script_hashes,
                      'model_provenance': 'Recorded pinned download manifest; no per-job rehash of all model weights.',
                      'visual_acceptance': 'pending', 'looped': False, 'foot_ik': False}
        for name in ['hymotion-environment.txt', 'api-environment.txt']:
            file = self.settings.root / 'config' / name
            if file.exists():
                shutil.copy2(file, directory / name)
        shutil.copy2(self.settings.root / 'models/animation-downloads.json', directory / 'model-downloads.json')
        (directory / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
        for name, command in self.stages(job, directory, source):
            await self.run_stage(job_id, name, command)
        report = json.loads((directory / 'candidate/validation.json').read_text())
        if report.get('status') != 'passed':
            raise RuntimeError('Candidate validation did not pass')
        if any(sha256(self.settings.root / p) != h for p, h in script_hashes.items()):
            raise RuntimeError('Implementation changed during this job; results remain unpublished')
        if sha256(source) != job['request']['rig_asset_id']:
            raise RuntimeError('Rig source changed during this job')
        for file in self.profile['sidecars']:
            shutil.copy2(self.settings.data / 'profile' / file, directory / 'candidate' / file)
        # Publish only reviewed outputs and provenance, not large intermediate tensors.
        paths = [directory / 'provenance.json', directory / 'model-downloads.json',
                 *directory.glob('*environment.txt'),
                 *sorted((directory / 'candidate').glob('*.png')),
                 directory / 'candidate/peasant-walk.blend', directory / 'candidate/peasant-walk.glb',
                 directory / 'candidate/retarget.json', directory / 'candidate/validation.json',
                 *[directory / 'candidate' / f for f in self.profile['sidecars']],
                 directory / 'motion/encode-run.json', directory / 'motion/motion-run.json',
                 directory / 'motion/motion-diagnostics.json']
        artifacts = []
        for i, path in enumerate(paths):
            artifacts.append({'id': f'{job_id}-{i}', 'name': str(path.relative_to(directory)),
                              'bytes': path.stat().st_size, 'sha256': sha256(path),
                              'download_url': f'/artifacts/{job_id}-{i}'})
        self.check_cancel(job_id)
        self.store.update(job_id, state='succeeded', stage='complete', artifacts=artifacts,
                          validation=report, completed_at=now())

    async def run(self):
        self.recover()
        self.settings.gpu_lock.parent.mkdir(parents=True, exist_ok=True)
        with self.settings.gpu_lock.open('a') as gpu_lock:
            while True:
                queued = next((j for j in self.store.jobs() if j['state'] == 'queued'), None)
                if not queued:
                    await asyncio.sleep(.25)
                    continue
                try:
                    fcntl.flock(gpu_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    await asyncio.sleep(.5)
                    continue
                job_id = queued['id']
                self.active_job = job_id
                self.store.update(job_id, state='running', started_at=now())
                try:
                    await self.execute(queued)
                except Canceled:
                    self.store.update(job_id, state='canceled', completed_at=now())
                except asyncio.CancelledError:
                    await self.stop_process()
                    self.store.update(job_id, state='interrupted', process=None,
                                      error='Service stopped; submit a new request_id to retry.')
                    raise
                except Exception as error:
                    self.store.update(job_id, state='failed', error=str(error), completed_at=now())
                finally:
                    self.active_job = None
                    fcntl.flock(gpu_lock, fcntl.LOCK_UN)
