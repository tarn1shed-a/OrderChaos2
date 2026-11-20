"""Package an append-only private runtime delta; never modify the base or saves."""
import argparse
import gzip
import hashlib
import io
import importlib.util
import json
import tarfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
FORMAT = 'oc2-private-runtime-delta-v1'


def protocol():
    spec = importlib.util.spec_from_file_location('oc2_delta_protocol', ROOT / 'deploy/bootstrap.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def manifest_raw(path):
    with tarfile.open(path, 'r:gz') as archive:
        return archive.extractfile('bundle-manifest.json').read()


def write_delta_tar(complete, payload_names, target_manifest_raw, reference_raw, output):
    """The v2 TAR writer, shared with measurement/encoding; no codec here.

    Metadata is first, then selected members in the complete archive's actual
    order. All output members are regular mode0600/mtime0, using Python's PAX
    default for the same long-path support as the original delta writer.
    """
    remaining = set(payload_names)
    if len(remaining) != len(payload_names):
        raise ValueError('Duplicate private delta payload selection')
    with tarfile.open(complete, 'r:gz') as source, tarfile.open(fileobj=output, mode='w|') as target:
        members, names, manifest = protocol().members_checked(source)
        if ('bundle-base.json' in names or set(manifest['files']) != names - {'bundle-manifest.json'} or
                not remaining <= set(manifest['files'])):
            raise ValueError('Complete private delta source required')
        actual_manifest = source.extractfile('bundle-manifest.json').read()
        if actual_manifest != target_manifest_raw:
            raise ValueError('Target manifest bytes changed before delta writing')
        for name, raw in [('bundle-base.json', reference_raw), ('bundle-manifest.json', target_manifest_raw)]:
            member = tarfile.TarInfo(name); member.size = len(raw); member.mode = 0o600; member.mtime = 0
            target.addfile(member, io.BytesIO(raw))
        for old in members:
            if old.name in remaining:
                member = tarfile.TarInfo(old.name); member.size = old.size; member.mode = 0o600; member.mtime = 0
                with source.extractfile(old) as stream:
                    target.addfile(member, stream)
                remaining.remove(old.name)
        if remaining:
            raise ValueError('Missing actual private delta payload')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inspect(path, keep=()):
    payload = {}
    with tarfile.open(path, 'r:gz') as archive:
        members = archive.getmembers()
        names = [m.name for m in members]
        if (len(names) != len(set(names)) or len(names) > 20000 or
                sum(m.size for m in members) > 2*1024**3):
            raise ValueError('Private runtime inventory exceeds limits')
        for member in members:
            p = PurePosixPath(member.name)
            if (not member.isfile() or p.is_absolute() or '..' in p.parts or
                    str(p) != member.name or '\\' in member.name):
                raise ValueError('Unsafe private runtime member')
        if 'bundle-base.json' in names:
            raise ValueError('The delta base must be a complete archive')
        manifest = json.load(archive.extractfile('bundle-manifest.json'))
        if (manifest.get('format') != 'oc2-private-runtime-v1' or
                manifest.get('localSavesImported') is not False or
                set(manifest['files']) != set(names)-{'bundle-manifest.json'}):
            raise ValueError('Private runtime manifest differs')
        for member in members:
            if member.name == 'bundle-manifest.json':
                continue
            raw = archive.extractfile(member).read()
            if manifest['files'][member.name] != {'bytes':len(raw), 'sha256':hashlib.sha256(raw).hexdigest()}:
                raise ValueError('Private runtime bytes differ: '+member.name)
            if member.name in keep:
                payload[member.name] = raw
    return manifest, payload


def package(base, complete, output, version=1):
    base, complete, output = map(lambda p:Path(p).resolve(), (base,complete,output))
    if not any(output.is_relative_to(ROOT/p) for p in ['analysis/raw','backups/deployment']):
        raise ValueError('Private runtime deltas must remain in ignored directories')
    proof = output.with_suffix(output.suffix+'.receipt.json')
    if output.exists() or proof.exists():
        raise ValueError('Existing private packages are preserved')
    if type(version) is not int or version not in (1, 2):
        raise ValueError('Unsupported private delta version')
    old, _ = inspect(base)
    new, _ = inspect(complete)
    if version == 2:
        loader = protocol()
        old_raw, new_raw = manifest_raw(base), manifest_raw(complete)
        reference = loader.make_delta_v2_reference(old, new, sha(base),
            hashlib.sha256(old_raw).hexdigest(), hashlib.sha256(new_raw).hexdigest())
        layout = loader.derive_delta_v2(old, new)
        raw_reference = (json.dumps(reference, sort_keys=True, indent=2) + '\n').encode()
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('xb') as stream, gzip.GzipFile(filename='', mode='wb', fileobj=stream, mtime=0) as compressed:
            write_delta_tar(complete, layout['payload'], new_raw, raw_reference, compressed)
        output.chmod(0o600)
        result = {'format': loader.DELTA_V2, 'archive': str(output), 'sha256': sha(output),
                  'bytes': output.stat().st_size, 'baseArchiveSHA256': reference['baseArchiveSHA256'],
                  'baseManifestSHA256': reference['baseManifestSHA256'],
                  'targetManifestSHA256': reference['targetManifestSHA256'],
                  'completeArchiveSHA256': sha(complete), 'newFiles': len(layout['added']),
                  'payloadFiles': len(layout['payload']), 'aliases': len(layout['aliases']),
                  'files': len(new['files']), 'baseFilesReplaced': 0, 'localSavesImported': False}
        proof.write_text(json.dumps(result, indent=2) + '\n'); proof.chmod(0o600)
        return result
    if (old['runtimeIdentity'] != new['runtimeIdentity'] or old['pythonFiles'] != new['pythonFiles'] or
            any(new['files'].get(name) != meta for name,meta in old['files'].items())):
        raise ValueError('Delta cannot replace existing runtime files')
    added = set(new['files'])-set(old['files'])
    if not added:
        raise ValueError('No append-only runtime files to deliver')
    _, payload = inspect(complete, added)
    payload['bundle-manifest.json'] = (json.dumps(new,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
    reference = {'format':FORMAT,'baseArchiveSHA256':sha(base),'completeArchiveSHA256':sha(complete)}
    payload['bundle-base.json'] = (json.dumps(reference,sort_keys=True)+'\n').encode()
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as stream, gzip.GzipFile(filename='',mode='wb',fileobj=stream,mtime=0) as compressed, tarfile.open(fileobj=compressed,mode='w') as archive:
        for name,raw in sorted(payload.items()):
            member = tarfile.TarInfo(name); member.size=len(raw);member.mode=0o600;member.mtime=0
            archive.addfile(member,io.BytesIO(raw))
    output.chmod(0o600)
    result = {'format':FORMAT,'archive':str(output),'sha256':sha(output),'bytes':output.stat().st_size,
              'baseArchiveSHA256':reference['baseArchiveSHA256'],'completeArchiveSHA256':reference['completeArchiveSHA256'],
              'newFiles':len(added),'files':len(new['files']),'baseFilesReplaced':0,'localSavesImported':False}
    proof.write_text(json.dumps(result,indent=2)+'\n');proof.chmod(0o600)
    return result


if __name__ == '__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    for name in ('base','complete','output'):cli.add_argument('--'+name,type=Path,required=True)
    cli.add_argument('--version', type=int, choices=(1, 2), default=1)
    args=cli.parse_args();print(json.dumps(package(args.base,args.complete,args.output,args.version)))
