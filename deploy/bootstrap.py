"""Verify a private runtime archive and hold the single-writer save lock on Linux.

This is deployment plumbing, not an implementation of original game rules.
The archive never contains existing saves, credentials or the analysis tree.
"""
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'analysis/raw/portable/running-preview'
FORMAT = 'oc2-private-runtime-v1'
MAX_EXPANDED = 2 * 1024**3
BUNDLE_CACHE = Path('/data/bundles')
DELTA_V2 = 'oc2-private-runtime-delta-v2'
WORLD_PATH_INDEX_SHA = '5adc87f4f9d95cce1a563cf5809cc48b3fff24c996826a390afe96c3cd23d3e8'
WORLD_GATHER_PLAN_SHA = 'b5e0be53fcd9680e9c8b5eb672a0b66de6eb8440815c6390809050e0faf7eebe'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def relative(name):
    path = PurePosixPath(name)
    if not name or path.is_absolute() or '..' in path.parts or '\\' in name or str(path) != name:
        raise ValueError('Unsafe bundle member')
    return path


def verify_source_world_code(root=ROOT):
    """Check the image's complete reviewed code closure before native startup."""
    root = Path(root)
    source_code = json.loads((root / 'tools/source_world_python.json').read_text())
    if (source_code.get('format') != 'oc2-source-world-python-closure-v1' or
            not isinstance(source_code.get('files'), dict) or not source_code['files']):
        raise ValueError('Source world Python closure differs')
    for name, expected in source_code['files'].items():
        relative(name)
        if not name.startswith('tools/') or not name.endswith('.py'):
            raise ValueError('Invalid source world code path')
        if not (root / name).is_file() or sha(root / name) != expected:
            raise ValueError('Source world Python bytes differ: ' + name)
    return source_code


def install_world_path_index(runtime, root=ROOT, expected=WORLD_PATH_INDEX_SHA):
    """Project one original private lookup table; never overwrite other data."""
    source = Path(runtime) / 'native-inputs/world-own-air-v1/root-support/matrix.json'
    target = Path(root) / 'analysis/raw/character-world-matrix-20261116/candidate-final/matrix.json'
    if not source.is_file() or sha(source) != expected:
        raise ValueError('Original world model-path index differs')
    if target.exists():
        if not target.is_file() or sha(target) != expected:
            raise ValueError('Existing world model-path index differs')
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as output, source.open('rb') as incoming:
        shutil.copyfileobj(incoming, output)
    target.chmod(0o600)
    return target


def install_world_gather_support(runtime, root=ROOT, expected=WORLD_GATHER_PLAN_SHA):
    """Project the three frozen dynamic helpers into disposable image paths."""
    runtime, root = Path(runtime), Path(root)
    plan = runtime / 'native-inputs/world-gather-v1/append-plan.json'
    if sha(plan) != expected:
        raise ValueError('Original Gather support plan differs')
    rows = {name: row for name, row in json.loads(plan.read_text())['newRootFiles'].items()
            if name.startswith('analysis/raw/')}
    if len(rows) != 3:
        raise ValueError('Original Gather helper set differs')
    return project_world_support(runtime, root, rows, 'world-gather-v1')


def project_world_support(runtime, root, rows, namespace):
    """Use one checked projection for frozen helpers and original lookup data."""
    runtime, root = Path(runtime), Path(root)
    for name, row in rows.items():
        relative(name)
        if not name.startswith('analysis/raw/'):
            raise ValueError('Private world support path differs')
        source = runtime / 'native-inputs' / namespace / 'root-support' / name
        target = root / name
        if not source.is_file() or source.stat().st_size != row['bytes'] or sha(source) != row['sha256']:
            raise ValueError('Original world helper differs: ' + name)
        if target.exists():
            if not target.is_file() or sha(target) != row['sha256']:
                raise ValueError('Existing world helper differs: ' + name)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as output, source.open('rb') as incoming:
            shutil.copyfileobj(incoming, output)
        target.chmod(0o600)
    return rows


def latest_world_plan(root=ROOT):
    """The image and Node host read one versioned runtime-plan declaration."""
    try:
        source = json.loads((Path(root) / 'tools/source_world_python.json').read_text())
        row = source['plans']['latestWorld']
        if (source.get('format') != 'oc2-source-world-python-closure-v1' or
                set(row) != {'path', 'sha256', 'bytes'} or
                row['path'] != 'native-inputs/world-latest-v1/append-plan.json' or
                len(row['sha256']) != 64 or any(c not in '0123456789abcdef' for c in row['sha256']) or
                type(row['bytes']) is not int or row['bytes'] <= 0):
            raise ValueError('Invalid common world plan declaration')
        return row
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise ValueError('Common world source plan differs: missing or invalid image declaration') from error


def install_world_latest_support(runtime, root=ROOT, expected=None):
    """Install the one index-driven normal/facts closure for either host flag."""
    declaration = latest_world_plan(root) if expected is None else None
    expected = declaration['sha256'] if declaration is not None else expected
    plan_file = Path(runtime) / 'native-inputs/world-latest-v1/append-plan.json'
    if declaration is not None and plan_file.stat().st_size != declaration['bytes']:
        raise ValueError('Common world source plan differs')
    if sha(plan_file) != expected:
        raise ValueError('Common world source plan differs')
    plan = json.loads(plan_file.read_text())
    if plan.get('actualFactsHostCompiled') is not True or plan.get('normalRepairIndependentOfGatherFlag') is not True:
        raise ValueError('Complete same-core world source required')
    rows = plan['explicitRootSupport']
    if not rows:
        raise ValueError('Original world support index required')
    project_world_support(runtime, root, rows, 'world-latest-v1')
    return plan


def members_checked(bundle):
    members = bundle.getmembers()
    if len(members) > 20000 or sum(m.size for m in members) > MAX_EXPANDED:
        raise ValueError('Private runtime archive exceeds limits')
    names = set()
    for member in members:
        relative(member.name)
        if not member.isfile() or member.name in names:
            raise ValueError('Only unique regular files are accepted')
        names.add(member.name)
    if 'bundle-manifest.json' not in names:
        raise ValueError('Missing private runtime manifest')
    manifest = json.load(bundle.extractfile('bundle-manifest.json'))
    if manifest.get('format') != FORMAT or manifest.get('localSavesImported') is not False:
        raise ValueError('Private runtime member set or manifest differs')
    return members, names, manifest


def write_source_checked(source, name, manifest, stage):
    relative(name)
    target = stage / name
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as output:
        shutil.copyfileobj(source, output)
    target.chmod(0o600)
    if name != 'bundle-manifest.json':
        expected = manifest['files'][name]
        if target.stat().st_size != expected['bytes'] or sha(target) != expected['sha256']:
            raise ValueError('Private runtime file identity differs: ' + name)


def write_checked(bundle, member, manifest, stage):
    with bundle.extractfile(member) as source:
        write_source_checked(source, member.name, manifest, stage)


def unique_json(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate private delta JSON key')
        value[key] = item
    return value


def strict_manifest(bundle):
    raw = bundle.extractfile('bundle-manifest.json').read()
    return json.loads(raw, object_pairs_hook=unique_json), hashlib.sha256(raw).hexdigest()


def checked_file_rows(manifest):
    if (type(manifest) is not dict or manifest.get('format') != FORMAT or
            manifest.get('localSavesImported') is not False or
            type(manifest.get('files')) is not dict or not manifest['files'] or
            type(manifest.get('pythonFiles')) is not dict):
        raise ValueError('Invalid private delta manifest')
    lengths = {}
    for name, row in manifest['files'].items():
        relative(name)
        if (name in {'bundle-manifest.json', 'bundle-base.json'} or type(row) is not dict or
                set(row) != {'bytes', 'sha256'} or type(row['bytes']) is not int or
                not 0 <= row['bytes'] <= MAX_EXPANDED or type(row['sha256']) is not str or
                not re.fullmatch('[0-9a-f]{64}', row['sha256'])):
            raise ValueError('Invalid private delta payload identity')
        if row['sha256'] in lengths and lengths[row['sha256']] != row['bytes']:
            raise ValueError('Ambiguous private delta content identity')
        lengths[row['sha256']] = row['bytes']
    for name, digest in manifest['pythonFiles'].items():
        relative(name)
        if (not name.startswith('tools/') or not name.endswith('.py') or
                type(digest) is not str or not re.fullmatch('[0-9a-f]{64}', digest)):
            raise ValueError('Invalid private delta image Python identity')
    if len(manifest['files']) + 1 > 20000 or sum(row['bytes'] for row in manifest['files'].values()) > MAX_EXPANDED:
        raise ValueError('Logical private runtime exceeds limits')
    return manifest['files']


def derive_delta_v2(old_manifest, manifest):
    old, new = checked_file_rows(old_manifest), checked_file_rows(manifest)
    if old_manifest['runtimeIdentity'] != manifest['runtimeIdentity']:
        raise ValueError('Private delta targets a different reviewed runtime')
    if any(new.get(name) != row for name, row in old.items()):
        raise ValueError('Private delta v2 cannot replace or remove existing files')
    lengths = {row['sha256']: row['bytes'] for row in old.values()}
    for row in new.values():
        if row['sha256'] in lengths and lengths[row['sha256']] != row['bytes']:
            raise ValueError('Ambiguous private delta content identity')
        lengths[row['sha256']] = row['bytes']
    added = sorted(set(new) - set(old))
    if not added:
        raise ValueError('No append-only runtime files to deliver')
    def identity(row):
        return row['sha256'], row['bytes']
    base_content, payload_content, aliases, payload = {}, {}, {}, []
    for name in sorted(old):
        base_content.setdefault(identity(old[name]), name)
    for name in added:
        key = identity(new[name])
        if key in base_content:
            aliases[name] = {'source': 'base', 'path': base_content[key]}
        elif key in payload_content:
            aliases[name] = {'source': 'delta', 'path': payload_content[key]}
        else:
            payload.append(name)
            payload_content[key] = name
    return {'added': added, 'payload': payload, 'aliases': aliases}


def delta_v2_reference_checked(reference):
    keys = {'format', 'baseArchiveSHA256', 'baseManifestSHA256', 'targetManifestSHA256', 'aliases'}
    if type(reference) is not dict or set(reference) != keys or reference['format'] != DELTA_V2:
        raise ValueError('Invalid private delta v2 reference')
    for key in ('baseArchiveSHA256', 'baseManifestSHA256', 'targetManifestSHA256'):
        if type(reference[key]) is not str or not re.fullmatch('[0-9a-f]{64}', reference[key]):
            raise ValueError('Invalid private delta v2 digest')
    if type(reference['aliases']) is not dict:
        raise ValueError('Invalid private delta v2 aliases')
    for name, row in reference['aliases'].items():
        relative(name)
        if type(row) is not dict or set(row) != {'source', 'path'} or row['source'] not in ('base', 'delta'):
            raise ValueError('Invalid private delta v2 alias')
        relative(row['path'])
    return reference


def make_delta_v2_reference(old_manifest, manifest, base_digest, base_manifest_digest, target_manifest_digest):
    layout = derive_delta_v2(old_manifest, manifest)
    reference = {'format': DELTA_V2, 'baseArchiveSHA256': base_digest,
                 'baseManifestSHA256': base_manifest_digest, 'targetManifestSHA256': target_manifest_digest,
                 'aliases': layout['aliases']}
    return delta_v2_reference_checked(reference)


def extract_delta_v2(bundle, members, names, manifest, reference, stage):
    reference = delta_v2_reference_checked(reference)
    manifest, manifest_digest = strict_manifest(bundle)
    if manifest_digest != reference['targetManifestSHA256']:
        raise ValueError('Private delta v2 target manifest differs')
    target_files = checked_file_rows(manifest)
    if sum(row['bytes'] for row in target_files.values()) + bundle.getmember('bundle-manifest.json').size > MAX_EXPANDED:
        raise ValueError('Logical private runtime exceeds limits')
    base_archive = BUNDLE_CACHE / (reference['baseArchiveSHA256'] + '.tar.gz')
    if not base_archive.is_file() or sha(base_archive) != reference['baseArchiveSHA256']:
        raise ValueError('Verified private runtime base is unavailable')
    with tarfile.open(base_archive, 'r:gz') as base:
        old_members, old_names, old_manifest = members_checked(base)
        if 'bundle-base.json' in old_names or set(old_manifest['files']) != old_names - {'bundle-manifest.json'}:
            raise ValueError('Only one complete private base is accepted')
        old_manifest, old_digest = strict_manifest(base)
        if old_digest != reference['baseManifestSHA256']:
            raise ValueError('Private delta v2 base manifest differs')
        layout = derive_delta_v2(old_manifest, manifest)
        if reference['aliases'] != layout['aliases']:
            raise ValueError('Private delta v2 aliases differ from exact content identities')
        if names != set(layout['payload']) | {'bundle-manifest.json', 'bundle-base.json'}:
            raise ValueError('Private delta v2 member set differs')
        if (len(old_members) + len(members) > 20000 or
                sum(m.size for m in old_members) + sum(m.size for m in members) > MAX_EXPANDED):
            raise ValueError('Combined private runtime exceeds limits')
        for member in old_members:
            if member.name != 'bundle-manifest.json':
                write_checked(base, member, old_manifest, stage)
    for member in members:
        if member.name != 'bundle-base.json':
            write_checked(bundle, member, manifest, stage)
    for name, alias in layout['aliases'].items():
        # Only non-alias base/payload source paths are accepted by derive_delta_v2.
        with (stage / alias['path']).open('rb') as source:
            write_source_checked(source, name, manifest, stage)
    return manifest


def extract_verified(archive, digest, destination):
    if not re.fullmatch('[0-9a-f]{64}', digest or '') or sha(archive) != digest:
        raise ValueError('Private runtime archive SHA256 does not match')
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='unpack-', dir=destination.parent) as temporary:
        stage = Path(temporary)
        with tarfile.open(archive, 'r:gz') as bundle:
            members, names, manifest = members_checked(bundle)
            v2_complete = False
            if 'bundle-base.json' in names:
                reference = json.load(bundle.extractfile('bundle-base.json'))
                if reference.get('format') == DELTA_V2:
                    reference = json.loads(bundle.extractfile('bundle-base.json').read(), object_pairs_hook=unique_json)
                    manifest = extract_delta_v2(bundle, members, names, manifest, reference, stage)
                    v2_complete = True
                else:
                    base_digest = reference.get('baseArchiveSHA256', '')
                    if (reference.get('format') != 'oc2-private-runtime-delta-v1' or
                            not re.fullmatch('[0-9a-f]{64}', base_digest)):
                        raise ValueError('Private runtime base reference differs')
                    base_archive = Path(archive).parent / (base_digest + '.tar.gz')
                    if not base_archive.is_file() or sha(base_archive) != base_digest:
                        raise ValueError('Verified private runtime base is unavailable')
                    with tarfile.open(base_archive, 'r:gz') as base:
                        old_members, old_names, old_manifest = members_checked(base)
                        if 'bundle-base.json' in old_names or set(old_manifest['files']) != old_names - {'bundle-manifest.json'}:
                            raise ValueError('Only one complete private base is accepted')
                        old_files, new_files = old_manifest['files'], manifest['files']
                        if (old_manifest['runtimeIdentity'] != manifest['runtimeIdentity'] or
                                old_manifest['pythonFiles'] != manifest['pythonFiles'] or
                                any(new_files.get(name) != meta for name, meta in old_files.items())):
                            raise ValueError('Private delta cannot replace existing runtime files')
                        if set(new_files) - set(old_files) != names - {'bundle-manifest.json', 'bundle-base.json'}:
                            raise ValueError('Private delta member set differs')
                        if (len(old_members) + len(members) > 20000 or
                                sum(m.size for m in old_members) + sum(m.size for m in members) > MAX_EXPANDED):
                            raise ValueError('Combined private runtime exceeds limits')
                        for member in old_members:
                            if member.name != 'bundle-manifest.json':
                                write_checked(base, member, old_manifest, stage)
            elif set(manifest['files']) != names - {'bundle-manifest.json'}:
                raise ValueError('Private runtime member set differs')
            if not v2_complete:
                for member in members:
                    if member.name != 'bundle-base.json':
                        write_checked(bundle, member, manifest, stage)
        pinned = json.loads((ROOT / 'tools/local_mvp_runtime.json').read_text())
        if manifest['runtimeIdentity'] != pinned:
            raise ValueError('Bundle targets a different reviewed runtime')
        # Runtime text must be exactly the reviewed text, not merely self-signed.
        for name, digest in pinned['files'].items():
            if sha(stage / name) != digest:
                raise ValueError('Reviewed runtime text differs: ' + name)
        if sha(stage / 'native-inputs/library.so') != pinned['nativeSHA256']:
            raise ValueError('Original ARM64 library differs')
        expected_tools = {name: sha(ROOT / name) for name in manifest['pythonFiles']}
        if expected_tools != manifest['pythonFiles']:
            raise ValueError('Physics host modules differ from the migration package')
        # Extraction only replaces disposable /opt runtime, never /data saves.
        if destination.exists():
            shutil.rmtree(destination)
        shutil.move(str(stage), str(destination))
    modules = destination / 'prototype/node_modules'
    modules.symlink_to(ROOT / 'deploy/node_modules', target_is_directory=True)
    return manifest


def archive_from_env():
    digest = os.environ.get('OC2_BUNDLE_SHA256', '')
    if not re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('Set OC2_BUNDLE_SHA256 to the migration receipt; no fallback runtime')
    if os.environ.get('OC2_BUNDLE_CACHE') == '0':
        # A private CLI image already owns this complete immutable archive.
        # Read it in place; preserve every existing /data cache and save for
        # rollback instead of requiring two full archives on the save volume.
        source = Path(os.environ.get('OC2_BUNDLE_PATH', str(ROOT / 'deploy/private-runtime.tar.gz')))
        if os.environ.get('OC2_BUNDLE_URL') or not source.is_file() or sha(source) != digest:
            raise ValueError('Uncached deployment requires the exact bundled private archive')
        with tarfile.open(source, 'r:gz') as packed:
            _, names, _ = members_checked(packed)
            if 'bundle-base.json' in names:
                reference = json.loads(packed.extractfile('bundle-base.json').read(), object_pairs_hook=unique_json)
                if type(reference) is not dict or reference.get('format') != DELTA_V2:
                    raise ValueError('Uncached deployment requires a complete private archive')
                delta_v2_reference_checked(reference)
                # Selection is not preparation. extract_verified must verify the
                # one exact /data cached complete base before any runtime starts.

        return source, digest
    cache = BUNDLE_CACHE
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    archive = cache / (digest + '.tar.gz')
    if archive.exists() and sha(archive) == digest:
        return archive, digest
    url = os.environ.get('OC2_BUNDLE_URL')
    if not url:
        source = Path(os.environ.get('OC2_BUNDLE_PATH', str(ROOT / 'deploy/private-runtime.tar.gz')))
        if not source.is_file():
            raise ValueError('Missing private runtime archive: use the private CLI build context, mount OC2_BUNDLE_PATH or configure OC2_BUNDLE_URL')
        if sha(source) != digest:
            raise ValueError('Private runtime archive SHA256 does not match')
        fd, temporary = tempfile.mkstemp(prefix='copy-', dir=cache)
        try:
            with os.fdopen(fd, 'wb') as output, source.open('rb') as input_file:
                shutil.copyfileobj(input_file, output)
            if sha(temporary) != digest:
                raise ValueError('Copied private runtime archive SHA256 differs')
            os.replace(temporary, archive)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return archive, digest
    if urllib.parse.urlsplit(url).scheme != 'https':
        raise ValueError('Private runtime download requires HTTPS')
    fd, temporary = tempfile.mkstemp(prefix='download-', dir=cache)
    try:
        with os.fdopen(fd, 'wb') as output, urllib.request.urlopen(url, timeout=60) as response:
            if urllib.parse.urlsplit(response.url).scheme != 'https':
                raise ValueError('Private runtime download redirected outside HTTPS')
            total = 0
            while block := response.read(1024**2):
                total += len(block)
                if total > MAX_EXPANDED:
                    raise ValueError('Private runtime download exceeds limits')
                output.write(block)
        if sha(temporary) != digest:
            raise ValueError('Downloaded private runtime SHA256 differs')
        os.replace(temporary, archive)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return archive, digest


def main():
    if ROOT != Path('/opt/oc2'):
        raise ValueError('This launcher only runs in the deployment container')
    if not any(len(fields := line.split()) > 4 and fields[4] == '/data'
               for line in Path('/proc/self/mountinfo').read_text().splitlines()):
        raise ValueError('Mount a persistent Docker/Railway volume at /data; ephemeral saves are refused')
    # flock is released by the OS on exit/crash. Do not guess whether a PID is stale.
    lock = os.open('/data/server.lock', os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise ValueError('This deployment volume already has an active server') from None
    archive, digest = archive_from_env()
    manifest = extract_verified(archive, digest, DEST)
    if os.environ.get('OC2_HUMAN_FEMALE_WORLD') == '1':
        # Only the appended, verified own-body recipe is projected. The base
        # physics inputs, original library and existing save files are untouched.
        verify_source_world_code()
        subprocess.run([sys.executable, str(ROOT / 'tools/female_world_delivery/materialize.py'), sys.executable], check=True)
        install_world_path_index(DEST)
        # This projects verified file paths only. No body engine, actor, seed,
        # tick or ready receipt is created; native preparation stays lazy on
        # the selected authenticated body in the one existing game server.
        plan = install_world_latest_support(DEST)
        materializer = plan['materializer']
        relative(materializer['target'])
        if not materializer['target'].startswith('tools/') or materializer['sameForBothGatherFlags'] is not True:
            raise ValueError('Shared world materializer differs')
        subprocess.run([sys.executable, str(ROOT / materializer['target']),
                        sys.executable, materializer['entryKey'], *plan['bodies']], check=True)
    subprocess.run(['node', str(ROOT / 'deploy/prepare_delivery.mjs')], check=True)
    Path('/data/saves').mkdir(exist_ok=True, mode=0o700)
    os.ftruncate(lock, 0)
    os.write(lock, json.dumps({'pid': os.getpid(), 'bundleSHA256': digest}).encode())
    os.set_inheritable(lock, True)
    print(json.dumps({'privateRuntimeVerified': True, 'bundleSHA256': digest,
                      'files': len(manifest['files']), 'localSavesImported': False}), flush=True)
    os.execvp('node', ['node', str(ROOT / 'deploy/server.mjs')])


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Do not log signed URLs or download error bodies containing credentials.
        print('Deployment refused: ' + (str(error) if isinstance(error, ValueError) else type(error).__name__), file=sys.stderr)
        sys.exit(1)
