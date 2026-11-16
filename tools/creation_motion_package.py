"""Append checked source motion resources; preserve the published preview archive."""
import argparse
import copy
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = 'd7f1a548a7f59ccc6282b1e40b5038fecd33588d0793ddcfb75522383d0ebb29'
MOTION_SHA = 'c0d52ea32832aca8fcbeb139da14f4444abcd7e69ab5d44ba6a44ac11528b24c'
RUNTIME_SHA = 'f91b6b0363ddd896ca954ce4231e44a2be4b1945ede40af6e37a7a28ec59eb40'
V4 = 'game-data/converted/source-creation-stage/manifest-stages-v4.json'
V5 = 'game-data/converted/source-creation-stage/manifest-stages-v5.json'
encoded = lambda value: (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()
digest = lambda raw: hashlib.sha256(raw).hexdigest()


def file_digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def checked_names(tar):
    names = set()
    for member in tar.getmembers():
        p = Path(member.name)
        if not member.isfile() or p.is_absolute() or '..' in p.parts or '\\' in member.name or member.name in names or p.as_posix() != member.name:
            raise ValueError('Only unique safe regular members are admitted')
        names.add(member.name)
    return names


def package(base, motion, runtime, output):
    base, motion, runtime, output = (Path(p).resolve() for p in (base, motion, runtime, output))
    if output.exists() or not output.is_relative_to(ROOT/'analysis/raw'):
        raise ValueError('Fresh ignored private output required')
    if file_digest(base) != BASE_SHA or file_digest(motion) != MOTION_SHA or file_digest(runtime) != RUNTIME_SHA:
        raise ValueError('Published preview or frozen motion archive differs')
    with tarfile.open(base) as old, tarfile.open(motion) as new, tarfile.open(runtime) as lean:
        old_names, new_names = checked_names(old), checked_names(new)
        manifest = json.load(old.extractfile('bundle-manifest.json'))
        if set(manifest['files']) != old_names-{'bundle-manifest.json'} or len(manifest['files']) != 6457 or len(new_names) != 75 or old_names & new_names:
            raise ValueError('Published payload membership differs')
        if any(not name.startswith(('game-data/converted/source-creation-control-v1/', 'game-data/converted/source-creation-initial-idle-v1/')) or Path(name).suffix not in ('.json', '.mjs') for name in new_names):
            raise ValueError('Unexpected non-runtime resource in source append')
        lean_names = checked_names(lean)
        if len(lean_names) != 4 or lean_names & (old_names | new_names) or any(not name.startswith('game-data/converted/source-creation-control-runtime-v1/modules/') or Path(name).suffix != '.mjs' for name in lean_names):
            raise ValueError('Non-auditing queue closure differs')
        profile = json.load(old.extractfile(V4))
        if len(profile['candidates']) != 90 or 'sourceMotion' in profile:
            raise ValueError('Published finite preview routes differ')
        profile['sourceMotion'] = {'version': 1,
            'classManifestURL': '/assets/source-creation-control-v1/manifest-class-v1.json',
            'initialManifestURL': '/assets/source-creation-initial-idle-v1/manifest.json'}
        profile_raw = encoded(profile)
        result = copy.deepcopy(manifest)
        for source in [new, lean]:
            for member in source.getmembers():
                raw = source.extractfile(member).read()
                result['files'][member.name] = {'bytes': len(raw), 'sha256': digest(raw)}
        result['files'][V5] = {'bytes': len(profile_raw), 'sha256': digest(profile_raw)}
        result['creationMotionIntegration'] = {'baseArchiveSHA256': BASE_SHA, 'sourceMotionArchiveSHA256': MOTION_SHA,
            'oldPayloadsPreserved': 6457, 'newSourcePayloads': 80, 'nonAuditingQueueArchiveSHA256': RUNTIME_SHA, 'unboundedResearchTraceEnabled': False, 'ownClassShowQueues': 43, 'missingOwnClassQueues': 2,
            'ownInitialGenericQueues': 8, 'PartFiniteOnly': 45, 'playableAdmissionChanged': False,
            'missingEffectsInvented': False, 'originalGPUReadyProduced': False, 'localSavesImported': False}
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('xb') as stream, gzip.GzipFile(fileobj=stream, mode='wb', filename='', mtime=0) as compressed, tarfile.open(fileobj=compressed, mode='w') as tar:
            def add(name, raw):
                member = tarfile.TarInfo(name); member.size, member.mode = len(raw), 0o600
                tar.addfile(member, io.BytesIO(raw))
            for member in old.getmembers():
                if member.name == 'bundle-manifest.json':
                    continue
                raw = old.extractfile(member).read()
                if {'bytes': len(raw), 'sha256': digest(raw)} != manifest['files'][member.name]:
                    raise ValueError('Published member digest differs')
                add(member.name, raw)
            for source in [new, lean]:
                for member in source.getmembers():
                    add(member.name, source.extractfile(member).read())
            add(V5, profile_raw)
            add('bundle-manifest.json', encoded(result))
    output.chmod(0o600)
    receipt = {'output': str(output), 'sha256': file_digest(output), 'bytes': output.stat().st_size,
        'payloads': len(result['files']), 'expandedBytes': sum(v['bytes'] for v in result['files'].values()), **result['creationMotionIntegration']}
    output.with_suffix(output.suffix+'.receipt.json').write_bytes(encoded(receipt))
    return receipt


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    for name in ['base', 'motion', 'runtime', 'output']:
        cli.add_argument('--'+name, required=True, type=Path)
    args = cli.parse_args()
    print(json.dumps(package(args.base, args.motion, args.runtime, args.output)))
