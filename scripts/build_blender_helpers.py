"""Build an immutable, deterministic Blender reference bundle; never overwrite a release."""
import argparse
import ast
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def build(root, destination, version):
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version):
        raise ValueError('Expected semantic version N.N.N')
    root, destination = Path(root), Path(destination)
    script = root / 'scripts/retarget_hymotion_peasant.py'
    mapping = next(ast.literal_eval(node.value) for node in ast.parse(script.read_text()).body
                   if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'mapping' for t in node.targets))
    contract = {'id': 'peasant-humanoid', 'version': '1.0.0',
                'objects': {'body': 'Peasant body', 'armature': 'Peasant rig', 'optional_legacy_pouch': 'Original BPT pouch'},
                'target_to_source_joint': mapping,
                'target_coordinates': 'Blender Z-up, forward -Y; identity armature world transform',
                'motion_coordinates': 'HY-Motion Y-up, forward +Z',
                'motion_arrays': {'rotations': [1, 120, 22, 3, 3], 'transl': [1, 120, 3],
                                  'rest_joints': 'J x 3', 'parents': 'J, root -1', 'joint_names': 'J strings'},
                'fps': 30, 'tested_blender_versions': ['5.2.1'],
                'python_dependencies': {'blender': ['bpy', 'mathutils', 'numpy'], 'standalone_diagnostics': ['numpy']},
                'required_support_files': ['Caller-provided source .blend with camera, triangulated body, active UVs and packed node textures',
                                           'Downloaded HY-Motion motion.npz'],
                'bone_contract': 'Reviewed semantic names; parent-before-child order; one pelvis root. Additional finger bones inherit parent motion.',
                'scope': 'Reference retargeter and preservation review for this rig contract, not automatic arbitrary-rig mapping or cleanup',
                'speed_and_loop_constraints': False, 'visual_acceptance': 'pending'}
    files = {name: (root / name).read_bytes() for name in [
        'scripts/retarget_hymotion_peasant.py', 'scripts/review_api_motion.py',
        'scripts/check_blender_rig_contract.py', 'scripts/motion_diagnostics.py',
        'docs/blender-handoff.md', 'docs/motion-diagnostics.md']}
    files['README.md'] = (root / 'docs/blender-helpers-readme.md').read_bytes()
    files['contracts/peasant-humanoid-v1.json'] = encoded(contract)
    manifest = {'schema_version': 1, 'name': 'blender-helpers', 'version': version,
                'rig_contract': contract, 'runs_on': 'consumer',
                'files': [{'name': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                          for name, data in sorted(files.items())]}
    files['manifest.json'] = encoded(manifest)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    zip_bytes = buffer.getvalue()
    entry = {'name': 'blender-helpers', 'version': version, 'rig_contract': {'id': contract['id'], 'version': contract['version']},
             'manifest_url': f'/helpers/blender-helpers/{version}/manifest',
             'manifest_sha256': hashlib.sha256(files['manifest.json']).hexdigest(),
             'download_url': f'/helpers/blender-helpers/{version}/download',
             'bytes': len(zip_bytes), 'sha256': hashlib.sha256(zip_bytes).hexdigest()}
    outputs = {'bundle.zip': zip_bytes, 'manifest.json': files['manifest.json'], 'release.json': encoded(entry)}
    release = destination / version
    if release.exists():
        if any(not (release / name).exists() or (release / name).read_bytes() != data for name, data in outputs.items()):
            raise RuntimeError('Release already exists with different content; use a new version')
        return entry
    release.mkdir(parents=True)
    for name, data in outputs.items():
        (release / name).write_bytes(data)
        (release / name).chmod(0o444)
    return entry


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'exports/blender-helpers')
    args = parser.parse_args()
    print(json.dumps(build(ROOT, args.output, args.version), indent=2))
