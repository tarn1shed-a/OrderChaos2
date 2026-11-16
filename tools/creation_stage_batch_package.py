"""Append the frozen ninety-choice source preview closure, preserving old files."""
import argparse
import copy
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
from creation_preview_delivery import safe_members
from runtime_delta import inspect

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = '485a10e06414de0e2a8a953c0b462055d73f203d673f540a05e64a863ed56f16'
APPEND_SHA = 'c51b71ccd258fbab854e56a67f882c2fddbcbcdb09d3374187c953c853889508'
PROFILE = 'game-data/converted/source-creation-stage/manifest-stages-v4.json'
digest = lambda raw: hashlib.sha256(raw).hexdigest()
encoded = lambda value: (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def package(base, append, output):
    base, append, output = (Path(p).resolve() for p in (base, append, output))
    if output.exists() or not output.is_relative_to(ROOT/'analysis/raw'):
        raise ValueError('New ignored private output required')
    for path, expected in [(base, BASE_SHA), (append, APPEND_SHA)]:
        with path.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
                raise ValueError('Frozen source archive differs')
    original, _ = inspect(base)
    files, added = safe_members(base), safe_members(append)
    files.pop('bundle-manifest.json')
    if set(files) & set(added) or len(added) != 2262:
        raise ValueError('New preview append replaces old bytes or differs in membership')
    for name in added:
        if (name != PROFILE and not name.startswith('game-data/converted/source-creation-shared-v2/')) or Path(name).suffix not in ('.json', '.png'):
            raise ValueError('Non-runtime source artifact in preview append')
    profile = json.loads(added[PROFILE])
    old_profile = json.loads(files['game-data/converted/source-creation-stage/manifest-stages-v3.json'])
    if len(profile['candidates']) != 90 or any(profile['candidates'].get(k) != v for k, v in old_profile['candidates'].items()):
        raise ValueError('Original sixteen routes were changed')
    files.update(added)
    manifest = copy.deepcopy(original)
    manifest['files'] = {name: {'bytes': len(raw), 'sha256': digest(raw)} for name, raw in sorted(files.items())}
    manifest['creationStageBatchIntegration'] = {'baseArchiveSHA256': BASE_SHA, 'appendArchiveSHA256': APPEND_SHA,
        'originalPayloadsPreserved': len(original['files']), 'addedPayloads': len(added),
        'classChoices': 45, 'partChoices': 45, 'previousRoutesPreserved': 16,
        'localSavesImported': False, 'playableRacesChanged': False,
        'oneSharedGeometryCore': True, 'initialSourceIdleOnly': True,
        'fullClassQueueRestored': False, 'missingBEFFRestored': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream, gzip.GzipFile(fileobj=stream, mode='wb', filename='', mtime=0) as compressed, tarfile.open(fileobj=compressed, mode='w') as tar:
        for name, raw in sorted({**files, 'bundle-manifest.json': encoded(manifest)}.items()):
            member = tarfile.TarInfo(name); member.size, member.mode = len(raw), 0o600
            tar.addfile(member, io.BytesIO(raw))
    output.chmod(0o600)
    inspect(output)
    with output.open('rb') as stream:
        result = {'output': str(output), 'sha256': hashlib.file_digest(stream, 'sha256').hexdigest(),
                  'bytes': output.stat().st_size, 'payloads': len(files), **manifest['creationStageBatchIntegration']}
    output.with_suffix(output.suffix+'.receipt.json').write_bytes(encoded(result))
    return result


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    for name in ['base', 'append', 'output']:
        cli.add_argument('--'+name, required=True, type=Path)
    args = cli.parse_args()
    print(json.dumps(package(args.base, args.append, args.output)))
