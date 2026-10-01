#!/usr/bin/env python3
"""Standard-library client for the shape-gen API, including resumable SSE."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request
import zipfile


def unpack_helper(entry, manifest_bytes, archive_bytes, output):
    """Verify the archive AND each declared member before writing a new directory."""
    if hashlib.sha256(manifest_bytes).hexdigest() != entry['manifest_sha256']:
        raise RuntimeError('Helper manifest checksum mismatch')
    if len(archive_bytes) != entry['bytes'] or hashlib.sha256(archive_bytes).hexdigest() != entry['sha256']:
        raise RuntimeError('Helper archive checksum mismatch')
    manifest = json.loads(manifest_bytes)
    if manifest['name'] != entry['name'] or manifest['version'] != entry['version']:
        raise RuntimeError('Helper release identity mismatch')
    files = manifest['files']
    expected = {f['name'] for f in files} | {'manifest.json'}
    if len(expected) != len(files) + 1:
        raise RuntimeError('Duplicate or reserved manifest filename')
    contents = {}
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        members = archive.infolist()
        if len(members) != len(expected) or {m.filename for m in members} != expected:
            raise RuntimeError('Archive member list differs from manifest')
        if sum(m.file_size for m in members) > 64 * 1024 * 1024:
            raise RuntimeError('Helper archive exceeds expanded-size limit')
        for member in members:
            name = member.filename
            if Path(name).is_absolute() or '..' in Path(name).parts or '\\' in name or member.is_dir() or \
                    (member.external_attr >> 16) & 0o170000 == 0o120000:
                raise RuntimeError('Unsafe helper archive member')
            contents[name] = archive.read(member)
    if contents['manifest.json'] != manifest_bytes:
        raise RuntimeError('Embedded manifest differs from release manifest')
    for file in files:
        data = contents[file['name']]
        if len(data) != file['bytes'] or hashlib.sha256(data).hexdigest() != file['sha256']:
            raise RuntimeError('Helper file checksum mismatch: ' + file['name'])
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    for name, data in contents.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return {'directory': str(output), 'version': entry['version'], 'verified_files': len(files),
            'archive_sha256': entry['sha256']}


class Client:
    def __init__(self, base_url, token_file):
        self.base = base_url.rstrip('/')
        self.token = Path(token_file).expanduser().read_text().strip()

    def open(self, path, data=None, method=None, headers=None, timeout=60):
        request = urllib.request.Request(self.base + path, data=data, method=method,
                  headers={'Authorization': 'Bearer ' + self.token, **(headers or {})})
        return urllib.request.urlopen(request, timeout=timeout)

    def json(self, path, value=None, method=None):
        data = None if value is None else json.dumps(value).encode()
        with self.open(path, data, method, {'Content-Type': 'application/json'}) as response:
            return json.load(response)

    def upload(self, file):
        file = Path(file)
        if file.stat().st_size > 64 * 1024 * 1024:
            raise ValueError('Upload exceeds 64 MiB')
        with self.open('/assets', file.read_bytes(), 'POST', {'Content-Type': 'application/octet-stream'}) as response:
            return json.load(response)

    def helper_download(self, version, output):
        entry = next((item for item in self.json('/helpers')['helpers']
                      if item['name'] == 'blender-helpers' and item['version'] == version), None)
        if entry is None:
            raise ValueError('Unknown helper bundle version')
        with self.open(entry['manifest_url']) as response:
            manifest = response.read()
        with self.open(entry['download_url']) as response:
            archive = response.read()
        return unpack_helper(entry, manifest, archive, output)

    def watch(self, job_id, after=0):
        while True:
            try:
                with self.open(f'/jobs/{job_id}/events', headers={'Last-Event-ID': str(after)}, timeout=30) as stream:
                    event, payload, event_id = '', [], None
                    for raw in stream:
                        line = raw.decode('utf-8').rstrip('\r\n')
                        if line.startswith('id:'):
                            event_id = int(line[3:].strip())
                        elif line.startswith('event:'):
                            event = line[6:].strip()
                        elif line.startswith('data:'):
                            payload.append(line[5:].lstrip())
                        elif not line:
                            if event == 'end':
                                return self.json(f'/jobs/{job_id}')
                            if payload and (event_id is None or event_id > after):
                                record = json.loads('\n'.join(payload))
                                print(json.dumps(record), flush=True)
                                if event_id is not None:
                                    after = event_id
                            event, payload, event_id = '', [], None
            except urllib.error.HTTPError:
                raise
            except (OSError, TimeoutError) as error:
                print(f'Stream disconnected ({type(error).__name__}); resuming after {after}', file=sys.stderr)
            time.sleep(1)

    def download(self, job_id, output):
        manifest = self.json(f'/jobs/{job_id}/artifacts')
        if manifest['state'] != 'succeeded':
            raise RuntimeError('Job has no completed artifact set')
        output = Path(output).resolve()
        output.mkdir(parents=True, exist_ok=False)
        for artifact in manifest['artifacts']:
            target = (output / artifact['name']).resolve()
            if not target.is_relative_to(output):
                raise RuntimeError('Unsafe artifact name')
            target.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            partial = target.with_name(target.name + '.partial')
            count = 0
            with self.open(artifact['download_url']) as response, partial.open('xb') as file:
                while block := response.read(1024 * 1024):
                    digest.update(block)
                    count += len(block)
                    file.write(block)
            if digest.hexdigest() != artifact['sha256'] or count != artifact['bytes']:
                raise RuntimeError(f'Artifact integrity failure: {artifact["name"]}')
            partial.replace(target)
        (output / 'artifacts.json').write_text(json.dumps(manifest, indent=2) + '\n')
        return {'directory': str(output), 'verified_files': len(manifest['artifacts'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://100.66.127.115:8765')
    parser.add_argument('--token-file', type=Path, default=Path.home() / '.config/shape-gen/api-token')
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ['health', 'profiles', 'operations', 'helpers', 'docs']:
        commands.add_parser(command)
    helper = commands.add_parser('helper-download')
    helper.add_argument('--version', required=True)
    helper.add_argument('--output', type=Path, required=True)
    diagnostics = commands.add_parser('diagnostics')
    diagnostics.add_argument('job_id')
    submit_json = commands.add_parser('submit-json', help='Submit any operation using a JSON request file')
    submit_json.add_argument('file', type=Path)
    upload = commands.add_parser('upload')
    upload.add_argument('file', type=Path)
    submit = commands.add_parser('submit')
    submit.add_argument('--request-id', required=True)
    submit.add_argument('--prompt', required=True)
    submit.add_argument('--seed', type=int, default=12345)
    submit.add_argument('--clip-name', default='Candidate_Motion')
    for command in ['get', 'cancel', 'watch', 'download']:
        sub = commands.add_parser(command)
        sub.add_argument('job_id')
        if command == 'watch':
            sub.add_argument('--after', type=int, default=0)
        if command == 'download':
            sub.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    client = Client(args.base_url, args.token_file)
    if args.command in ['health', 'profiles', 'operations', 'helpers']:
        result = client.json('/' + args.command)
    elif args.command == 'helper-download':
        result = client.helper_download(args.version, args.output)
    elif args.command == 'diagnostics':
        result = client.json('/jobs/' + args.job_id + '/motion-diagnostics')
    elif args.command == 'docs':
        with client.open('/docs/agent.md') as response:
            print(response.read().decode())
        return
    elif args.command == 'upload':
        result = client.upload(args.file)
    elif args.command == 'submit-json':
        result = client.json('/jobs', json.loads(args.file.read_text()))
    elif args.command == 'submit':
        profile = client.json('/profiles')['profiles'][0]
        result = client.json('/jobs', {'request_id': args.request_id, 'profile': profile['id'],
            'operation': 'hymotion-retarget', 'rig_asset_id': profile['rig_asset_id'],
            'parameters': {'prompt': args.prompt, 'seed': args.seed, 'duration': 4, 'clip_name': args.clip_name}})
    elif args.command == 'get':
        result = client.json('/jobs/' + args.job_id)
    elif args.command == 'cancel':
        result = client.json('/jobs/' + args.job_id + '/cancel', method='POST')
    elif args.command == 'watch':
        result = client.watch(args.job_id, args.after)
    else:
        result = client.download(args.job_id, args.output)
    print(json.dumps(result, indent=2))
    if args.command == 'watch' and result['state'] != 'succeeded':
        raise SystemExit(1)


if __name__ == '__main__':
    try:
        main()
    except urllib.error.HTTPError as error:
        print(f'HTTP {error.code}: {error.read().decode()}', file=sys.stderr)
        raise SystemExit(1)
