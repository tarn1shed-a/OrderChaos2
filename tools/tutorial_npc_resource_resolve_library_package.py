"""Hash, validate and archive the ignored independent NPC resource library."""
import argparse
import gzip
import io
import json
import tarfile
from pathlib import Path

from tutorial_npc_resource_resolve_library_candidate import FORMAT, digest, json_write, private_path


def validate(candidate):
    candidate = private_path(candidate)
    receipt = json.loads((candidate / 'package-files.json').read_text())
    if receipt.get('format') != FORMAT or receipt.get('privateOnly') is not True:
        raise ValueError('Expected independent private resource library')
    names = set(receipt['files']) | {'package-files.json'}
    if names != {str(p.relative_to(candidate)) for p in candidate.rglob('*') if p.is_file()}:
        raise ValueError('Missing or unreceipted library files')
    records = {}
    for name in sorted(names):
        path = candidate / name
        if Path(name).is_absolute() or '..' in Path(name).parts or path.is_symlink() or not path.resolve().is_relative_to(candidate):
            raise ValueError('Unsafe resource member')
        records[name] = digest(path)
        if name != 'package-files.json' and records[name] != receipt['files'][name]:
            raise ValueError('Resource hash or length changed: ' + name)
    return records


def package(candidate, output):
    candidate, output = map(private_path, (candidate, output))
    proof = Path(str(output) + '.json')
    if output.exists() or proof.exists():
        raise ValueError('Existing private package is preserved')
    records = validate(candidate)
    encoded = io.BytesIO()
    with gzip.GzipFile(fileobj=encoded, mode='wb', filename='', mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode='w') as archive:
            for name, record in records.items():
                raw = (candidate / name).read_bytes()
                item = tarfile.TarInfo('npc-source-resource-library/' + name)
                item.size = record['bytes']; item.mode = 0o644; item.mtime = 0
                archive.addfile(item, io.BytesIO(raw))
    raw = encoded.getvalue()
    import hashlib
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        for item in archive.getmembers():
            name = item.name.removeprefix('npc-source-resource-library/')
            content = archive.extractfile(item).read()
            if {'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()} != records[name]:
                raise ValueError('Private archive roundtrip failed')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(raw)
    report = {'format': FORMAT, 'package': str(output), **digest(output), 'files': len(records),
              'privateOnly': True, 'allMembersVerified': True, 'productionChanged': False,
              'activityCreated': False, 'modelReadyProduced': False}
    json_write(proof, {**report, 'members': records})
    return report


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--candidate', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    print(json.dumps(package(args.candidate, args.output), ensure_ascii=False))
