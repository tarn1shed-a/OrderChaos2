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


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def relative(name):
    path = PurePosixPath(name)
    if not name or path.is_absolute() or '..' in path.parts or '\\' in name or str(path) != name:
        raise ValueError('Unsafe bundle member')
    return path


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


def write_checked(bundle, member, manifest, stage):
    target = stage / member.name
    target.parent.mkdir(parents=True, exist_ok=True)
    with bundle.extractfile(member) as source, target.open('xb') as output:
        shutil.copyfileobj(source, output)
    target.chmod(0o600)
    if member.name != 'bundle-manifest.json':
        expected = manifest['files'][member.name]
        if target.stat().st_size != expected['bytes'] or sha(target) != expected['sha256']:
            raise ValueError('Private runtime file identity differs: ' + member.name)


def extract_verified(archive, digest, destination):
    if not re.fullmatch('[0-9a-f]{64}', digest or '') or sha(archive) != digest:
        raise ValueError('Private runtime archive SHA256 does not match')
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='unpack-', dir=destination.parent) as temporary:
        stage = Path(temporary)
        with tarfile.open(archive, 'r:gz') as bundle:
            members, names, manifest = members_checked(bundle)
            if 'bundle-base.json' in names:
                reference = json.load(bundle.extractfile('bundle-base.json'))
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
    cache = Path('/data/bundles')
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
