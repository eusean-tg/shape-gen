"""Adapters for model-only jobs. Every command is fixed and uses an isolated venv."""
import asyncio
import json
import shutil

from .assets import inspect_upload, register_file
from .store import now
from .worker import sha256
from .operations import EXPERIMENTAL


def commands(root, request, directory, inputs):
    op, p = request['operation'], request['parameters']
    output = directory / 'result'
    py = lambda env: root / env / 'bin/python'
    script = lambda name: root / 'scripts' / name
    if op in {'deepmesh-retopology', 'lato2-retopology'}:
        deep = op == 'deepmesh-retopology'
        command = [py('.venv-deepmesh' if deep else '.venv-lato2'),
                   script('retopo_deepmesh.py' if deep else 'retopo_lato2.py'),
                   inputs['mesh'], '--output-dir', output]
        keys = ['seed', 'temperature', 'max_tokens', 'max_seconds'] if deep else [
            'seed', 'target_vertices', 'vertex_steps', 'topology_steps', 'guidance']
        for key in keys:
            command += ['--' + key.replace('_', '-'), p[key]]
        if not deep and not p['fill_quad_rings']:
            command += ['--no-fill-quad-rings']
        stages, reports = [(op, command)], ['trial.json' if deep else 'lato2.json']
        # Old persisted requests lack this flag and keep their original behavior.
        # Newly submitted requests get the explicit True default from the schema.
        if not deep and p.get('recalculate_normals', False):
            stages.append(('recalculate-normals', [py('.venv'), script('recalculate_lato_normals.py'), output]))
            reports.append('normal-recalculation.json')
        return stages, output / ('02-deepmesh.glb' if deep else '02-lato2.glb'), reports, 'mesh'
    if op == 'trellis-shape':
        views = [view for view in ['front', 'left', 'back', 'right'] if view in inputs]
        command = [py('.venv-trellis2'), script('generate_trellis.py'), '--input-dir', directory / 'inputs',
                   '--views', *views, '--output-dir', output,
                   '--steps', p['steps'], '--seed', p['seed'], '--mode', p['mode']]
        return [('trellis-shape', command)], output / '01-dense-raw.glb', ['experiment.json'], 'mesh'
    if op == 'trellis2-shape':
        stages = [('trellis2-shape', [py('.venv-trellis2'), script('generate_trellis2.py'),
                   '--image', inputs['front'], '--output-dir', output,
                   '--steps', p['steps'], '--seed', p['seed'], '--resolution', p['resolution']])]
        primary, reports = output / '01-dense-raw.glb', ['experiment.json']
        if p['remesh']:
            primary = output / '01-dense-remesh.glb'
            reports.append('01-dense-remesh.json')
            stages.append(('trellis2-remesh', [py('.venv-trellis2'), script('remesh_trellis2.py'),
                           output / '01-dense-raw.glb', primary,
                           '--resolution', p['resolution'], '--target', p['remesh_target']]))
        return stages, primary, reports, 'mesh'
    if op == 'hunyuan-shape':
        source = directory / 'inputs' if p['model'] == 'mv' else inputs['front']
        command = [py('.venv'), script('generate.py'), source, '--output-dir', output]
        for key in ['model', 'steps', 'resolution', 'chunks', 'seed', 'guidance']:
            command += ['--' + key, p[key]]
        if p['keep_background']:
            command += ['--keep-background']
        return [('shape', command)], output / '01-dense.glb', ['generation.json'], 'mesh'
    if op == 'bpt-retopology':
        command = [py('.venv-bpt'), script('retopo_bpt.py'), inputs['mesh'], '--output-dir', output]
        for key in ['seed', 'temperature', 'max_tokens', 'encoder_device']:
            command += ['--' + key.replace('_', '-'), p[key]]
        return [('bpt', command)], output / '02-bpt.glb', ['bpt.json'], 'mesh'
    if op == 'hy3d-paint':
        command = [py('.venv'), script('paint.py'), inputs['mesh'], '--image', inputs['reference'], '--output-dir', output]
        for key in ['steps', 'seed', 'texture_size', 'render_size']:
            command += ['--' + key.replace('_', '-'), p[key]]
        if p['preserve_uvs']:
            command += ['--preserve-uvs']
        return [('paint', command)], output / '03-textured.glb', ['paint.json'], 'mesh'
    if op == 'unirig':
        common = ['--asset-dir', output, '--config-dir', output / 'config']
        stages = [('prepare-rig', [py('.venv'), script('api_model_io.py'), 'prepare-rig', inputs['mesh'], output]),
                  ('configure-rig', [py('.venv-unirig'), script('configure_unirig.py'), *common])]
        stages += [(name, [py('.venv-unirig'), script('run_unirig.py'), name, *common, '--seed', p['seed']])
                   for name in ['skeleton', 'skin']]
        stages += [('transfer-weights', [py('.venv-unirig'), script('transfer_unirig_weights.py'),
                                         '--asset-dir', output, '--generic-names'])]
        return stages, output / 'rig-data.npz', ['skeleton-run.json', 'skin-run.json'], 'rig-data'
    if op == 'hymotion':
        common = ['--output', output, '--prompt', p['prompt'], '--duration', p['duration'], '--seed', p['seed']]
        stages = [(name, [py('.venv-hymotion'), script('run_hymotion.py'), name, *common]) for name in ['encode', 'motion']]
        stages += [('motion-diagnostics', [py('.venv-api'), script('motion_diagnostics.py'), output / 'motion.npz',
                                           '--output', output / 'motion-diagnostics.json'])]
        return stages, \
            output / 'motion.npz', ['encode-run.json', 'motion-run.json'], 'motion'
    raise ValueError('Unknown operation')


async def execute_model(worker, job):
    root, data, store = worker.settings.root, worker.settings.data, worker.store
    job_id, request = job['id'], job['request']
    directory = data / 'jobs' / job_id
    (directory / 'inputs').mkdir(parents=True, exist_ok=False)
    inputs, input_records = {}, {}
    for role, asset_id in request['inputs'].items():
        record = store.asset(asset_id)
        source = data / record['path']
        if await asyncio.to_thread(sha256, source) != asset_id:
            raise RuntimeError(f'Input hash changed: {role}')
        # PIL detects content, so JPEG views also work under the multiview runner's .png names.
        suffix = '.png' if request['operation'] in {'hunyuan-shape', 'trellis-shape'} else record['extension']
        target = directory / 'inputs' / (role + suffix)
        await asyncio.to_thread(shutil.copyfile, source, target)
        inputs[role], input_records[role] = target, {k: v for k, v in record.items() if k != 'path'}
    stages, primary, reports, kind = commands(root, request, directory, inputs)
    scripts = {str(path.relative_to(root)) for _, command in stages for path in command
               if hasattr(path, 'suffix') and path.suffix == '.py'}
    scripts.update(['scripts/api_model_io.py', 'scripts/api_stage_exec.py', 'shape_api/model_jobs.py',
                    'shape_api/worker.py', 'shape_api/server.py', 'shape_api/assets.py', 'shape_api/operations.py'])
    if request['operation'] in EXPERIMENTAL:
        scripts.update(['scripts/experimental_common.py', 'config/experimental-models.json'])
        upstream = {'deepmesh-retopology': 'DeepMesh', 'lato2-retopology': 'LATO.2',
                    'trellis-shape': 'TRELLIS', 'trellis2-shape': 'TRELLIS.2'}[request['operation']]
        scripts.update(str(path.relative_to(root)) for path in (root / 'third_party' / upstream).rglob('*.py'))
        if request['operation'] == 'deepmesh-retopology':
            scripts.update(str(path.relative_to(root)) for path in (root / 'scripts/deepmesh_compat').rglob('*.py'))
        if request['operation'] == 'lato2-retopology':
            scripts.add('scripts/lato2_inference.py')
    hashes = {name: sha256(root / name) for name in sorted(scripts)}
    provenance = {'operation_version': 2 if request['operation'] in {'hymotion', 'lato2-retopology'} else 1,
                  'created_at': now(), 'request': request,
                  'inputs': input_records, 'script_sha256': hashes, 'runs_blender': False,
                  'experimental': request['operation'] in EXPERIMENTAL,
                  'visual_acceptance': 'pending', 'model_provenance': 'Pinned local models; see runner reports/download manifests. Not rehashed in full per job.'}
    (directory / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    for source in [root / 'config/api-environment.txt', root / 'models/animation-downloads.json']:
        if source.exists():
            shutil.copyfile(source, directory / source.name)
    pins = {'hunyuan-shape': ['uv.lock'], 'bpt-retopology': ['config/bpt-lock.txt'],
            'deepmesh-retopology': ['config/experimental-models.json', 'config/deepmesh-environment.txt', 'models/deepmesh/manifest.json'],
            'lato2-retopology': ['config/experimental-models.json', 'config/lato2-environment.txt'],
            'trellis-shape': ['config/experimental-models.json', 'config/trellis2-environment.txt', 'models/trellis/download-manifest.json'],
            'trellis2-shape': ['config/experimental-models.json', 'config/trellis2-environment.txt', 'models/trellis2/download-manifest.json'],
            'hy3d-paint': ['uv.lock', 'config/paint-host-toolchain.txt'],
            'unirig': ['config/unirig-environment.txt'], 'hymotion': ['config/hymotion-environment.txt']}
    environment_paths = []
    for relative in pins[request['operation']]:
        source = root / relative
        if source.exists():
            target = directory / source.name
            shutil.copyfile(source, target)
            environment_paths.append(target)
    for name, command in stages:
        await worker.run_stage(job_id, name, command)
    for name in reports:
        report = json.loads((directory / 'result' / name).read_text())
        if report.get('status') != 'complete':
            raise RuntimeError(f'Model report is not complete: {name}')
    await worker.run_stage(job_id, 'validate-output', [root / '.venv/bin/python', root / 'scripts/api_model_io.py',
                                                     kind, primary, directory / 'validation.json'])
    if any(sha256(root / name) != digest for name, digest in hashes.items()):
        raise RuntimeError('Implementation changed during this job; results remain unpublished')
    for role, path in inputs.items():
        if await asyncio.to_thread(sha256, path) != request['inputs'][role]:
            raise RuntimeError(f'Input snapshot changed: {role}')
    validation = json.loads((directory / 'validation.json').read_text())
    metadata = await asyncio.to_thread(inspect_upload, primary) if kind == 'mesh' else {
        'kind': kind, 'extension': '.npz', 'validation': validation}
    worker.check_cancel(job_id)
    # Numeric raw predictions and model tensors are private intermediates. Publish portable results and reports.
    paths = [directory / 'provenance.json', directory / 'validation.json', directory / 'api-environment.txt']
    paths += environment_paths
    if (directory / 'animation-downloads.json').exists():
        paths.append(directory / 'animation-downloads.json')
    output = directory / 'result'
    paths += sorted(path for path in output.iterdir() if path.is_file() and
                    (path == primary or path.suffix in {'.glb', '.obj', '.png', '.json', '.md'}))
    paths += sorted((output / 'views').glob('*.png'))
    artifacts = []
    for i, path in enumerate(paths):
        artifacts.append({'id': f'{job_id}-{i}', 'name': str(path.relative_to(directory)),
                          'bytes': path.stat().st_size, 'sha256': await asyncio.to_thread(sha256, path),
                          'download_url': f'/artifacts/{job_id}-{i}'})
    worker.check_cancel(job_id)
    asset = register_file(store, data, primary, metadata, source_job=job_id)
    next(a for a in artifacts if a['name'] == str(primary.relative_to(directory)))['asset_id'] = asset['id']
    store.update(job_id, state='succeeded', stage='complete', artifacts=artifacts,
                 validation=validation, completed_at=now())
