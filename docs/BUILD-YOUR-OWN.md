# Build your own artifact-promotion project

Create an equivalent learning project from an empty folder; no repository clone is required. Use Python 3.10 or newer and a terminal; Python's standard library is sufficient for the local model.

## 1. Create the folders

Create `my-artifact-promotion`, then the `lab`, `tests` and `examples/workflows` subfolders. Keep the terminal at that project root for the commands below.

```bash
mkdir my-artifact-promotion
cd my-artifact-promotion
mkdir -p lab tests examples/workflows
```

Bash commands work in Linux, macOS, WSL or Git Bash. In PowerShell, use `New-Item -ItemType Directory -Force lab, tests, examples/workflows` instead of `mkdir -p`; use `python` or your installed Python 3 launcher consistently.

## 2. Write the implementation

Create an empty `lab/__init__.py` file and then create `lab/promotion.py` with the full contents below. This model writes fictional local state only and never contacts Azure.

```python
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
```

## 3. Write tests for the intended behavior

Create `tests/test_promotion.py` with the following contents. The tests initialize their own temporary folders so they do not overwrite your manually prepared candidate or runtime.

```python
import json, tempfile, unittest
from pathlib import Path
from lab.promotion import setup,prepare,execute,read,atomic,canonical,digest

class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        setup(self.root)
    def candidate(self, operation='release', source='2'*40):
        path = self.root / (operation + '.json')
        sha = prepare(self.root, source, operation, path)
        return path, sha
    def test_release_and_exact_rollback_preserve_settings(self):
        initial = read(self.root/'runtime.json')
        path, sha = self.candidate()
        execute(self.root,path,sha)
        path, sha = self.candidate('rollback','1'*40)
        result = execute(self.root,path,sha)
        self.assertEqual(read(self.root/'runtime.json')['active'],initial['active'])
        self.assertTrue(result['settings_preserved'])
    def test_wrong_approval_and_duplicate_execution_rejected(self):
        path, sha = self.candidate()
        with self.assertRaisesRegex(ValueError,'exact candidate'):execute(self.root,path,'0'*64)
        execute(self.root,path,sha)
        with self.assertRaisesRegex(ValueError,'Runtime changed'):execute(self.root,path,sha)
    def test_drift_rejected(self):
        path, sha = self.candidate()
        state=read(self.root/'runtime.json');state['settings']['email']=True
        atomic(self.root/'runtime.json',state)
        with self.assertRaisesRegex(ValueError,'Runtime changed'):execute(self.root,path,sha)
    def test_package_tamper_rejected(self):
        path, sha = self.candidate()
        (self.root/'archive'/('2'*40)/'api.zip').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):execute(self.root,path,sha)
    def test_schema_conflict_rejected(self):
        state=read(self.root/'runtime.json');state['schema']=2
        atomic(self.root/'runtime.json',state)
        with self.assertRaisesRegex(ValueError,'Schema compatibility'):self.candidate()
    def test_expired_candidate_rejected(self):
        path, sha = self.candidate()
        data=read(path);data['created']=0;data['expires']=1
        path.write_bytes(canonical(data))
        with self.assertRaisesRegex(ValueError,'expired'):execute(self.root,path,digest(path.read_bytes()))
    def test_concurrent_publication_lock_rejected(self):
        path, sha = self.candidate()
        lock=self.root/'.publication.lock';lock.touch()
        with self.assertRaises(FileExistsError):execute(self.root,path,sha)
        self.assertTrue(lock.exists())
    def test_same_target_rejected(self):
        with self.assertRaisesRegex(ValueError,'already selected'):self.candidate(source='1'*40)

if __name__=='__main__':unittest.main()
```

## 4. Create your fictional archive

Run setup once in your project root; it creates two retained API/web ZIP pairs and a current runtime record. If setup was interrupted, inspect that folder and start a new uniquely named lab root rather than repeatedly overwriting it.

```bash
python -m lab.promotion setup
python -m unittest discover -s tests -v
```

Eight tests should pass. The packages contain harmless `version.txt` files, not functioning API/web applications, and the schema field is a teaching contract rather than a SQL migration tool.

## 5. Prepare, inspect and execute a release

Prepare the second source and inspect the resulting candidate with `python -m json.tool`. Copy its printed SHA-256 into the separate execute command; this local argument illustrates exact-content approval but is not a real identity or permission check.

```bash
python -m lab.promotion prepare --operation release --source 2222222222222222222222222222222222222222 --output release.candidate.json
python -m json.tool release.candidate.json
python -m lab.promotion execute --candidate release.candidate.json --approved-sha256 YOUR_PRINTED_CANDIDATE_SHA256
python -m json.tool work/runtime.json
```

The second source should now be active and all three settings remain false. A candidate is valid for 15 minutes and becomes stale after a successful execution or any runtime change.

## 6. Restore the exact retained first release

Prepare a new rollback candidate for the first source, review it and use its new hash. Check runtime.json afterward; a new revision records selection, while the original package hashes and settings are retained.

```bash
python -m lab.promotion prepare --operation rollback --source 1111111111111111111111111111111111111111 --output rollback.candidate.json
python -m json.tool rollback.candidate.json
python -m lab.promotion execute --candidate rollback.candidate.json --approved-sha256 YOUR_NEW_ROLLBACK_CANDIDATE_SHA256
python -m json.tool work/runtime.json
```

A package rollback does not undo database changes. This model rejects a schema mismatch instead of guessing a migration downgrade.

## 7. Create the cloud orchestration templates

Create the following two files outside `.github/workflows` while you implement your cloud adapter. They show the actual platform's stage ordering and controls, condensed into teaching templates; they intentionally cannot publish anything until their missing adapter and environment configuration have been implemented.

### Create `examples/workflows/release.yml`

```yaml
# Teaching template. Stored outside .github/workflows; it does not run here.
# Implement the adapter contract in examples/workflows/README.md before activation.
name: Promote an exact archived release
on:
  workflow_dispatch:
    inputs:
      source_sha:
        description: Exact 40-character archived source commit
        type: string
        required: true
      api_sha256:
        description: Exact API ZIP SHA-256
        type: string
        required: true
      web_sha256:
        description: Exact web ZIP SHA-256
        type: string
        required: true
      migration_set_sha256:
        description: Packaged migration-set hash; publishing does not apply migrations
        type: string
        required: true
permissions:
  contents: read
  actions: read
# Release and rollback share ONE publication lock in the same repository.
concurrency:
  group: project-production-publication
  cancel-in-progress: false
jobs:
  promote:
    runs-on: ubuntu-24.04
    timeout-minutes: 30
    environment: project-production
    permissions:
      contents: read
      actions: read
      id-token: write
    env:
      SOURCE_SHA: ${{ inputs.source_sha }}
      API_SHA256: ${{ inputs.api_sha256 }}
      WEB_SHA256: ${{ inputs.web_sha256 }}
      MIGRATION_SHA256: ${{ inputs.migration_set_sha256 }}
      ADAPTER_COMMISSIONED: ${{ vars.RELEASE_ADAPTER_COMMISSIONED }}
      GH_TOKEN: ${{ github.token }}
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
        with:
          persist-credentials: false
      - name: Validate exact request and trusted execution context
        shell: bash
        run: |
          set -euo pipefail
          test "$GITHUB_REF" = refs/heads/main
          test "$GITHUB_RUN_ATTEMPT" = 1
          test "$ADAPTER_COMMISSIONED" = true
          [[ "$SOURCE_SHA" =~ ^[0-9a-f]{40}$ ]]
          for value in "$API_SHA256" "$WEB_SHA256" "$MIGRATION_SHA256"; do
            [[ "$value" =~ ^[0-9a-f]{64}$ ]]
          done
          test -f scripts/cloud_release_adapter.py
      - uses: azure/login@v2
        id: azure
        with:
          client-id: ${{ vars.AZURE_CLIENT_ID }}
          tenant-id: ${{ vars.AZURE_TENANT_ID }}
          subscription-id: ${{ vars.AZURE_SUBSCRIPTION_ID }}
      - name: Retrieve retained ZIPs and verify trusted acceptance evidence
        run: python -B scripts/cloud_release_adapter.py retrieve-and-verify
      - name: Check target, schema compatibility and preserved settings
        run: python -B scripts/cloud_release_adapter.py preflight
      # The same adapter publication entry point is used for rollback.
      # No source checkout at SOURCE_SHA, npm build or docker build happens here.
      - name: Publish the selected packages without rebuilding
        run: python -B scripts/cloud_release_adapter.py publish
      - name: Verify health, anonymous denial, assets and settings preservation
        run: python -B scripts/cloud_release_adapter.py verify
      - name: Record active release only after successful verification
        run: python -B scripts/cloud_release_adapter.py record
      - name: Restore only temporary state recorded by this run
        if: always() && steps.azure.outcome == 'success'
        run: python -B scripts/cloud_release_adapter.py cleanup
      - name: Retain safe evidence even if publication or verification failed
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: release-receipt-${{ github.run_id }}
          path: receipts/
          if-no-files-found: warn
          retention-days: 30
```

### Create `examples/workflows/rollback.yml`

```yaml
# Teaching template. This is not the platform's commissioned rollback workflow.
# Account-bound authorization and the cloud adapter must be implemented first.
name: Prepare or execute an exact retained-package rollback
on:
  workflow_dispatch:
    inputs:
      operation:
        type: choice
        options: [prepare, execute]
        default: prepare
        required: true
      request_json:
        description: Prepare only; exact current/target hashes and incident reason
        type: string
        required: false
      candidate_run_id:
        description: Execute only; successful preparation run in this repository
        type: string
        required: false
      candidate_sha256:
        description: Execute only; hash of the exact reviewed candidate bytes
        type: string
        required: false
permissions:
  contents: read
  actions: read
# This sample publishes in-process; it never waits for a child publisher holding
# the same lock. A dispatcher design must leave the parent outside this lock.
concurrency:
  group: project-production-publication
  cancel-in-progress: false
jobs:
  rollback:
    runs-on: ${{ vars.ROLLBACK_PRIVATE_RUNNER }}
    timeout-minutes: 30
    environment: project-production
    permissions:
      contents: read
      actions: read
      id-token: write
    env:
      OPERATION: ${{ inputs.operation }}
      REQUEST_JSON: ${{ inputs.request_json }}
      CANDIDATE_RUN_ID: ${{ inputs.candidate_run_id }}
      CANDIDATE_SHA256: ${{ inputs.candidate_sha256 }}
      ADAPTER_COMMISSIONED: ${{ vars.RELEASE_ADAPTER_COMMISSIONED }}
      APPROVED_OPERATOR_ID: ${{ vars.ROLLBACK_OPERATOR_ID }}
      GH_TOKEN: ${{ github.token }}
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
        with:
          persist-credentials: false
      - name: Validate the separate preparation or execution request
        shell: bash
        run: |
          set -euo pipefail
          test "$GITHUB_REF" = refs/heads/main
          test "$GITHUB_RUN_ATTEMPT" = 1
          test "$ADAPTER_COMMISSIONED" = true
          test -f scripts/cloud_release_adapter.py
          if [ "$OPERATION" = prepare ]; then
            test -n "$REQUEST_JSON"
            test -z "$CANDIDATE_RUN_ID$CANDIDATE_SHA256"
          else
            test "$OPERATION" = execute
            test -z "$REQUEST_JSON"
            [[ "$CANDIDATE_RUN_ID" =~ ^[1-9][0-9]*$ ]]
            [[ "$CANDIDATE_SHA256" =~ ^[0-9a-f]{64}$ ]]
            [[ "$APPROVED_OPERATOR_ID" =~ ^[1-9][0-9]*$ ]]
            test "$GITHUB_ACTOR_ID" = "$APPROVED_OPERATOR_ID"
            test "$GITHUB_TRIGGERING_ACTOR" = "$GITHUB_ACTOR"
          fi
      - uses: azure/login@v2
        id: azure
        with:
          client-id: ${{ vars.AZURE_CLIENT_ID }}
          tenant-id: ${{ vars.AZURE_TENANT_ID }}
          subscription-id: ${{ vars.AZURE_SUBSCRIPTION_ID }}
      - name: Prepare a fresh, read-only compatibility candidate
        if: inputs.operation == 'prepare'
        run: python -B scripts/cloud_release_adapter.py prepare-rollback
      - name: Retain the exact candidate for a separate operator decision
        if: inputs.operation == 'prepare'
        uses: actions/upload-artifact@v4
        with:
          name: rollback-candidate-${{ github.run_id }}
          path: |
            candidate.json
            candidate.sha256
          if-no-files-found: error
          retention-days: 7
      - name: Resolve and revalidate the approved candidate under the lock
        if: inputs.operation == 'execute'
        run: python -B scripts/cloud_release_adapter.py resolve-and-revalidate
      - name: Publish earlier retained packages through the same publisher
        if: inputs.operation == 'execute'
        run: python -B scripts/cloud_release_adapter.py publish
      - name: Verify restored binding, health, access boundary and settings
        if: inputs.operation == 'execute'
        run: python -B scripts/cloud_release_adapter.py verify
      - name: Record restored release only after successful verification
        if: inputs.operation == 'execute'
        run: python -B scripts/cloud_release_adapter.py record
      - name: Restore only temporary state recorded by this run
        if: always() && steps.azure.outcome == 'success'
        run: python -B scripts/cloud_release_adapter.py cleanup
      - name: Retain safe preparation/execution evidence
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: rollback-receipt-${{ github.run_id }}
          path: receipts/
          if-no-files-found: warn
          retention-days: 30
```

## 8. Implement your own cloud boundary

Follow the [adapter contract and commissioning steps](../examples/workflows/README.md), creating each adapter command in your own project and testing it in isolation. Treat cloud deployment, live SQL compatibility, authorization and private connectivity as additional implementation work; the local model does not establish any of them.

## 9. Capture evidence and clean up

Record the active source/hash pair after release and rollback, plus one rejected case such as a stale candidate. Keep your own outputs, then remove only your fictional workspace when finished; never apply local cleanup commands to a real archive or state account.

| Evidence | Expected observation | Your result |
| --- | --- | --- |
| Release | Second source active with retained hashes | Not recorded |
| Rollback | First source restored with retained hashes | Not recorded |
| Failure boundary | Wrong/stale/tampered request rejected | Not recorded |
| Settings | API pause/email/SMS choices preserved | Not recorded |

See [operations and troubleshooting](OPERATIONS.md) and [architecture](ARCHITECTURE.md) for the limitations and production equivalents.
