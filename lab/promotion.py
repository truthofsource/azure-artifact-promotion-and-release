"""A local model of retained-package promotion. Does not deploy to Azure."""
from pathlib import Path
import argparse, contextlib, hashlib, json, os, re, time

def digest(data):
    return hashlib.sha256(data).hexdigest()

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()

def atomic(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.new')
    try:
        with temporary.open('xb') as stream:
            stream.write(canonical(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)

@contextlib.contextmanager
def locked(root):
    lock = root / '.publication.lock'
    with lock.open('x'):
        pass
    try:
        yield
    finally:
        lock.unlink()

def archive(root, source):
    if not re.fullmatch(r'[0-9a-f]{40}', source):
        raise ValueError('Select an exact 40-character source commit')
    folder = root / 'archive' / source
    manifest = read(folder / 'release.json')
    if manifest['source'] != source or manifest['nonproduction'] != 'passed':
        raise ValueError('Source or nonproduction evidence mismatch')
    for component in ('api', 'web'):
        actual = digest((folder / (component + '.zip')).read_bytes())
        if actual != manifest['sha256'][component]:
            raise ValueError('Archived package hash mismatch: ' + component)
    # Local fixture field, not a substitute for a real SQL compatibility query.
    if not isinstance(manifest['schema'], int) or isinstance(manifest['schema'], bool):
        raise ValueError('Invalid schema contract')
    return manifest

def setup(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    # One-time fixture setup: refuse to overwrite previous runs.
    with (root / '.initialized').open('x'):
        pass
    import zipfile, io
    for index in (1, 2):
        source = str(index) * 40
        folder = root / 'archive' / source
        folder.mkdir(parents=True)
        hashes = {}
        for component in ('api', 'web'):
            data = io.BytesIO()
            with zipfile.ZipFile(data, 'w') as output:
                output.writestr('version.txt', f'fictional {component} release {index}')
            (folder / (component + '.zip')).write_bytes(data.getvalue())
            hashes[component] = digest(data.getvalue())
        atomic(folder / 'release.json', {'source': source, 'sha256': hashes,
               'nonproduction': 'passed', 'schema': 1})
    initial = archive(root, '1' * 40)
    atomic(root / 'runtime.json', {'active': initial, 'schema': 1,
        'settings': {'api_enabled': False, 'email': False, 'sms': False},
        'revision': 1})

def prepare(root, source, operation, output):
    root, output = Path(root), Path(output)
    if operation not in ('release', 'rollback'):
        raise ValueError('Unknown operation')
    if output.exists():
        raise FileExistsError('Use a new candidate filename')
    manifest = archive(root, source)
    state = read(root / 'runtime.json')
    if state['active']['source'] == source:
        raise ValueError('This source is already selected')
    if state['schema'] != manifest['schema']:
        raise ValueError('Schema compatibility failed; package rollback cannot undo SQL')
    candidate = {'operation': operation, 'before': digest(canonical(state)),
                 'target': manifest, 'created': int(time.time()), 'expires': int(time.time()) + 900}
    with output.open('xb') as stream:
        stream.write(canonical(candidate))
    return digest(canonical(candidate))

def execute(root, candidate_path, approved_sha256):
    root = Path(root)
    data = Path(candidate_path).read_bytes()
    if not re.fullmatch(r'[0-9a-f]{64}', approved_sha256) or digest(data) != approved_sha256:
        raise ValueError('Approval must match the exact candidate bytes')
    candidate = json.loads(data)
    if candidate['operation'] not in ('release', 'rollback'):
        raise ValueError('Unknown operation')
    now = int(time.time())
    if not candidate['created'] <= now < candidate['expires'] or candidate['expires'] - candidate['created'] > 900:
        raise ValueError('Candidate expired or invalid; prepare again')
    with locked(root):
        state = read(root / 'runtime.json')
        if digest(canonical(state)) != candidate['before']:
            raise ValueError('Runtime changed after preparation; prepare again')
        target = archive(root, candidate['target']['source'])
        if target != candidate['target'] or target['schema'] != state['schema']:
            raise ValueError('Archive or compatibility changed after preparation')
        new_state = dict(state, active=target, revision=state['revision'] + 1)
        atomic(root / 'runtime.json', new_state)
        if read(root / 'runtime.json') != new_state:
            raise RuntimeError('Publication readback failed; inspect before retrying')
    return {'operation': candidate['operation'], 'source': target['source'],
            'sha256': target['sha256'], 'settings_preserved': state['settings'] == new_state['settings']}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='work')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('setup')
    p = commands.add_parser('prepare')
    p.add_argument('--source', required=True)
    p.add_argument('--operation', choices=['release', 'rollback'], required=True)
    p.add_argument('--output', required=True)
    p = commands.add_parser('execute')
    p.add_argument('--candidate', required=True)
    p.add_argument('--approved-sha256', required=True)
    args = parser.parse_args()
    if args.command == 'setup':
        setup(args.root)
        print('Fictional archive initialized. No cloud resources were contacted.')
    elif args.command == 'prepare':
        print(prepare(args.root, args.source, args.operation, args.output))
    else:
        print(json.dumps(execute(args.root, args.candidate, args.approved_sha256), indent=2))

if __name__ == '__main__':
    main()
