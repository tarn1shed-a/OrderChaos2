"""Append the checked shared HumanF Class and Part batches; preserve old bytes.

Original PNG/models/policies stay in the ignored private bundle. This neither
imports saves nor expands the played-world race/class admission policy.
"""
import argparse
import copy
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

from creation_stages_package import relative_resource
from creation_preview_delivery import safe_members
from runtime_delta import inspect

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = 'fa96e6ad07555ce3ed8516f62b821ada09bafcee2431ba21e3e6103e84bd6ca7'
HANDOFF_SHA = '8b8646e77d4603b7761f0d67b2bdd347e33f8c299c826c5173967535ad2a745c'
PART_HANDOFF_SHA = '2167acb6706b6791ae7b3006ca79d764a50eaac8df461c7db39faf343cca046b'
POLICY_SHA = 'bca0b324a56c3e7c577b6b0b63761f4b4ec6efb66e50c1dd4ca1a626aeefdac4'
REGISTRY_SHA = '337c79ea6501456014771e94222648257f676464e261e33cb367853a5fdabc60'
digest = lambda raw: hashlib.sha256(raw).hexdigest()
encoded = lambda x: (json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def file_digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def package(source_root, base, output):
    source_root, base, output = map(lambda p: Path(p).resolve(), (source_root, base, output))
    if not output.is_relative_to(ROOT/'analysis/raw') or output.exists():
        raise ValueError('A new ignored private output is required')
    if file_digest(base) != BASE_SHA:
        raise ValueError('Current six-preview original base differs')
    source = source_root/'analysis/raw/creation-human-female-batch-20261116'
    part_source = source_root/'analysis/raw/creation-human-female-part-20261116'
    frozen_members = {}
    for folder, expected in [(source, HANDOFF_SHA), (part_source, PART_HANDOFF_SHA)]:
        raw_handoff = (folder/'handoff-v1.json').read_bytes()
        if digest(raw_handoff) != expected:
            raise ValueError('Frozen source handoff differs: '+str(folder))
        for name, meta in json.loads(raw_handoff)['files'].items():
            if name in frozen_members and frozen_members[name] != meta:
                raise ValueError('Conflicting frozen source member: '+name)
            frozen_members[name] = meta
    def frozen(path):
        name = str(path.relative_to(source_root))
        expected = frozen_members.get(name)
        raw = path.read_bytes()
        if expected != {'bytes': len(raw), 'sha256': digest(raw)}:
            raise ValueError('Frozen own source member differs: '+name)
        return raw
    original, _ = inspect(base)
    files = safe_members(base)
    files.pop('bundle-manifest.json')
    profile = json.loads(files['game-data/converted/source-creation-stage/manifest-stages-v2.json'])
    profile['sharedGeometry'] = {'version': 1,
        'policyURL': '/assets/source-creation-shared-v1/policy.json', 'policySHA256': POLICY_SHA,
        'registryURL': '/assets/source-creation-shared-v1/capabilities.json', 'registrySHA256': REGISTRY_SHA,
        'initialSourceIdleOnly': True, 'fullClassQueueRestored': False}
    additions = {}
    for panel, stage, folder in [(1, 'class', source/'candidates-v2'), (2, 'part', part_source/'candidates-v1')]:
        for index in range(5):
            candidate = folder/('class-'+str(index))
            m = json.loads(frozen(candidate/'manifest.json'))
            if (m['race'], m['gender'], m['panel'], m['professionIndex']) != (0, 1, panel, index):
                raise ValueError('Own original stage identity differs')
            name = 'shared-human-female-'+stage+'-'+str(index)
            prefix = 'game-data/converted/source-creation-stages/actors/'+name+'/'
            profile['candidates'][str(panel)+':0:1:'+str(index)] = {
                'sourceKey': name, 'baseURL': '/assets/'+prefix.removeprefix('game-data/converted/'),
                'provider': 'shared-source-geometry-v1'}
            names = {'manifest.json', relative_resource(m['model'])}
            for attachment in m['attachments']:
                names.add(relative_resource(attachment['model']))
            for material in [*m['materials'], *[v for a in m['attachments'] for v in a['materials']]]:
                names.update(relative_resource(v) for v in material['samplers'].values())
            for member in sorted(names):
                additions[prefix+member] = frozen(candidate/member)
    policy = frozen(source/'stage-policy-v2.json')
    registry = (source_root/'analysis/raw/creation-capability-batch-20261116/projection-v1/registry.json').read_bytes()
    if digest(policy) != POLICY_SHA or digest(registry) != REGISTRY_SHA:
        raise ValueError('Original typed policy or capability registry differs')
    additions['game-data/converted/source-creation-shared-v1/policy.json'] = policy
    additions['game-data/converted/source-creation-shared-v1/capabilities.json'] = registry
    additions['game-data/converted/source-creation-stage/manifest-stages-v3.json'] = encoded(profile)
    if set(additions)&set(files):
        raise ValueError('Shared source append would replace an original payload')
    files.update(additions)
    manifest = copy.deepcopy(original)
    manifest['files'] = {name: {'bytes': len(raw), 'sha256': digest(raw)} for name, raw in sorted(files.items())}
    manifest['creationSharedIntegration'] = {'sourceHandoffSHA256': HANDOFF_SHA, 'partSourceHandoffSHA256': PART_HANDOFF_SHA, 'baseArchiveSHA256': BASE_SHA,
        'originalPayloadsPreserved': len(original['files']), 'addedPayloads': len(additions),
        'oneSharedGeometryCore': True, 'newClassChoices': 5, 'allClassChoices': 9,
        'newPartChoices': 5, 'allPartChoices': 7,
        'localSavesImported': False, 'playableRacesChanged': False, 'missingBEFFRestored': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', filename='', mtime=0) as gz, tarfile.open(fileobj=gz, mode='w') as tar:
        for name, content in sorted({**files, 'bundle-manifest.json': encoded(manifest)}.items()):
            item = tarfile.TarInfo(name)
            item.size, item.mode = len(content), 0o600
            tar.addfile(item, io.BytesIO(content))
    output.chmod(0o600)
    verified, _ = inspect(output)
    if any(verified['files'].get(name) != meta for name, meta in original['files'].items()):
        raise ValueError('Old payload identity changed')
    result = {'output': str(output), 'sha256': file_digest(output),
              'bytes': output.stat().st_size, 'payloads': len(files), **manifest['creationSharedIntegration']}
    output.with_suffix(output.suffix+'.receipt.json').write_bytes(encoded(result))
    return result


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    for name in ['source-root', 'base', 'output']:
        cli.add_argument('--'+name, type=Path, required=True)
    a = cli.parse_args()
    print(json.dumps(package(a.source_root, a.base, a.output), ensure_ascii=False))
