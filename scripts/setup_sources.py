"""Clone selected upstream sources at recorded commits; never reset an existing checkout."""
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    specs = json.loads((ROOT / 'config/source-revisions.json').read_text())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sources', nargs='*')
    parser.add_argument('--list', action='store_true')
    args = parser.parse_args()
    if args.list:
        for name, spec in specs.items():
            print(name, spec['commit'], spec['url'])
        return
    if not args.sources or set(args.sources) - specs.keys():
        parser.error('Choose sources from: ' + ', '.join(specs))
    for name in dict.fromkeys(args.sources):
        target, spec = ROOT / 'third_party' / name, specs[name]
        if target.exists():
            actual = subprocess.check_output(['git', '-C', str(target), 'rev-parse', 'HEAD'], text=True).strip()
            if actual != spec['commit']:
                raise RuntimeError(f'{target} is at another commit; refusing to reset it')
            print(f'Existing {name} at expected revision; leaving local changes/submodules untouched')
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', 'clone', '--no-checkout', spec['url'], str(target)], check=True)
        subprocess.run(['git', '-C', str(target), 'checkout', '--detach', spec['commit']], check=True)
        subprocess.run(['git', '-C', str(target), 'submodule', 'update', '--init', '--recursive'], check=True)


if __name__ == '__main__':
    main()
