"""Append frozen Race, generic Class and partial Class control resources."""
import argparse
import copy
import gzip
import io
import json
from pathlib import Path
import tarfile

from creation_motion_package import checked_names, digest, encoded, file_digest

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = 'aeeb873afb05abc1f55019e4986ead3066cbb47f370c203bdcf2ff2e002c2c6a'
APPENDS = {
    'race': ('68f454104fc048d8e8e5d61c484b9af41fbe9f4789bf41ce305f5111621b1add', 24),
    'initial': ('da94eb389bd9061ce17b4f2b3e80c6d5f6f24d187472cc4d0825ce99a9d85d87', 59),
    'partial': ('8e58fa209a6bb9662e7b339652e2ea1f16d0ef33564a728d112a12cb59ab2a25', 12),
}
V5 = 'game-data/converted/source-creation-stage/manifest-stages-v5.json'
V6 = 'game-data/converted/source-creation-stage/manifest-stages-v6.json'
SOURCE_MOTION = {
    'version': 2,
    'classManifestURL': '/assets/source-creation-control-v1/manifest-class-v1.json',
    'initialManifestURL': '/assets/source-creation-initial-all-v1/manifest.json',
    'raceManifestURL': '/assets/source-creation-race-control-v1/manifest.json',
    'partialManifestURL': '/assets/source-creation-partial-class-v1/manifest.json',
}
PREFIXES = tuple('game-data/converted/source-creation-'+s+'/' for s in (
    'race-control-v1', 'initial-all-v1', 'partial-class-v1', 'initial-idle-v1'))


def package(base, race, initial, partial, output):
    base, output = Path(base).resolve(), Path(output).resolve()
    inputs = {k: Path(v).resolve() for k, v in [('race', race), ('initial', initial), ('partial', partial)]}
    proof = output.with_suffix(output.suffix+'.receipt.json')
    if output.exists() or proof.exists() or not output.is_relative_to(ROOT/'analysis/raw'):
        raise ValueError('Fresh ignored private output required')
    if file_digest(base) != BASE_SHA:
        raise ValueError('Published complete base archive differs')
    for kind, p in inputs.items():
        if file_digest(p) != APPENDS[kind][0]:
            raise ValueError('Frozen source append differs: '+kind)
    payloads = {}
    with tarfile.open(base, 'r:gz') as old:
        old_names = checked_names(old)
        manifest = json.load(old.extractfile('bundle-manifest.json'))
        if (manifest.get('format') != 'oc2-private-runtime-v1' or manifest.get('localSavesImported') is not False
                or len(manifest['files']) != 6537 or set(manifest['files']) != old_names-{'bundle-manifest.json'}):
            raise ValueError('Published base inventory differs')
        result = copy.deepcopy(manifest)
        for kind, p in inputs.items():
            with tarfile.open(p, 'r:gz') as packed:
                names = checked_names(packed)
                if len(names) != APPENDS[kind][1]:
                    raise ValueError('Frozen append inventory differs: '+kind)
                for member in packed.getmembers():
                    if not member.name.startswith(PREFIXES) or Path(member.name).suffix not in ('.json', '.mjs'):
                        raise ValueError('Non-runtime source in append')
                    raw = packed.extractfile(member).read()
                    meta = {'bytes': len(raw), 'sha256': digest(raw)}
                    if member.name in result['files']:
                        # The partial registry deliberately reuses seven exact
                        # generic/math files; it may not replace their bytes.
                        if kind != 'partial' or result['files'][member.name] != meta:
                            raise ValueError('Frozen dependency replacement refused')
                        continue
                    payloads[member.name] = raw
                    result['files'][member.name] = meta
        profile = json.load(old.extractfile(V5))
        if len(profile['candidates']) != 90 or profile['sourceMotion'].get('version') != 1:
            raise ValueError('Published source preview profile differs')
        profile['sourceMotion'] = dict(SOURCE_MOTION)
        payloads[V6] = encoded(profile)
        result['files'][V6] = {'bytes': len(payloads[V6]), 'sha256': digest(payloads[V6])}
        if len(result['files']) != 6626 or len(payloads) != 89:
            raise ValueError('Combined source append coverage differs')
        result['creationRaceMotionIntegration'] = {
            'baseArchiveSHA256': BASE_SHA,
            'sourceAppendsSHA256': {kind: row[0] for kind, row in APPENDS.items()},
            'oldPayloadsPreserved': 6537, 'newSourcePayloads': 89,
            'ownRaceQueues': 9, 'ownInitialClassQueues': 45,
            'unchangedCompleteClassQueues': 43, 'ownPartialClassQueues': 2,
            'missingClipsInvented': False, 'PartFiniteOnly': 45,
            'playableAdmissionChanged': False, 'originalGPUReadyProduced': False,
            'localSavesImported': False,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('xb') as stream, gzip.GzipFile(fileobj=stream, mode='wb', filename='', mtime=0) as gz, tarfile.open(fileobj=gz, mode='w') as packed:
            def add(name, raw):
                member = tarfile.TarInfo(name)
                member.size, member.mode = len(raw), 0o600
                packed.addfile(member, io.BytesIO(raw))
            for member in old.getmembers():
                if member.name == 'bundle-manifest.json':
                    continue
                raw = old.extractfile(member).read()
                if {'bytes': len(raw), 'sha256': digest(raw)} != manifest['files'][member.name]:
                    raise ValueError('Published base member differs: '+member.name)
                add(member.name, raw)
            for name, raw in sorted(payloads.items()):
                add(name, raw)
            add('bundle-manifest.json', encoded(result))
    output.chmod(0o600)
    receipt = {
        'output': str(output), 'sha256': file_digest(output), 'bytes': output.stat().st_size,
        'payloads': len(result['files']), 'expandedBytes': sum(row['bytes'] for row in result['files'].values()),
        **result['creationRaceMotionIntegration'],
    }
    proof.write_bytes(encoded(receipt))
    proof.chmod(0o600)
    return receipt


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'race', 'initial', 'partial', 'output'):
        cli.add_argument('--'+name, required=True, type=Path)
    args = cli.parse_args()
    print(json.dumps(package(args.base, args.race, args.initial, args.partial, args.output)))
