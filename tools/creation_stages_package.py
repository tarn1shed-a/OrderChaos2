"""Append verified Class/Part preview data; never import player saves or replace assets."""
import argparse
import copy
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import tarfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'analysis/raw/ordinary-quest-journal-live-20261116/complete-v2.tar.gz'
BASE_SHA = '438dd2d0c97ba11dd7585c2ed342fb087fef8614c802a597a0345c0a65bd0d59'
BASE_V2 = ROOT / 'analysis/raw/creation-class-ui-fix-20261116/complete-three-class-v2.tar.gz'
BASE_V2_SHA = '01ed9ab1da0b171bc13b2554c63dea0e8bad1d2e8ee26ec8dac10842d01e7451'
CONTRACT = ROOT / 'analysis/raw/creation-class-entry-20261116/source-v1/contract-runtime.json'
CONTRACT_SHA = '26ad805cd6b9abb68026e30996b8344e100673b37fb41a230cc9f30e1017a8ba'
FORMAT = 'oc2-source-creation-stages-delivery-v1'
sha = lambda b: hashlib.sha256(b).hexdigest()
encoded = lambda v: (json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def relative_resource(value):
    if not isinstance(value, str) or not re.fullmatch(r'/?[-A-Za-z0-9_./]+', value):
        raise ValueError('Invalid original actor resource path')
    name = value.lstrip('/')
    p = PurePosixPath(name)
    if not name or str(p) != name or '..' in p.parts or p.is_absolute():
        raise ValueError('Original actor resource escaped its namespace')
    return name


def payload(actors, actor_version=2):
    if actor_version not in (2, 3):
        raise ValueError('Reviewed source actor version required')
    if sha(CONTRACT.read_bytes()) != CONTRACT_SHA:
        raise ValueError('Frozen original stage contract changed')
    contract = json.loads(CONTRACT.read_bytes())
    cases = {(r['uiRace'], r['gender'], r['uiProfessionIndex']): r for r in contract['identityCases']}
    added = {'game-data/converted/source-creation-stages/contract.json': CONTRACT.read_bytes()}
    profile = {'format': FORMAT, 'mapId': 7, 'sourceSelectionRegion': 211, 'freshStartOnly': True,
        'createsPlayableRole': False, 'wholeCreationRestored': False,
        'raceProfileURL': '/assets/source-creation-stage/manifest-conditional-v1.json',
        'contractURL': '/assets/source-creation-stages/contract.json', 'contractSHA256': CONTRACT_SHA,
        'candidates': {}}
    if actor_version == 3:
        profile['actorVersion'] = 3
    receipts = []
    for folder in actors:
        folder = Path(folder).resolve()
        if not folder.is_relative_to(ROOT/'analysis/raw') or not re.fullmatch(r'[-A-Za-z0-9_]+', folder.name):
            raise ValueError('Explicit private actor candidate directory required')
        raw = (folder/'manifest.json').read_bytes()
        m = json.loads(raw)
        if (m.get('format') != 'oc2-creation-class-part-candidate-v1' or m.get('panel') not in (1, 2)
            or m.get('createdRole') is not False or m.get('grantsEquipment') is not False
            or m.get('writesCharacter') is not False or m.get('appearanceComplete') is not True):
            raise ValueError('Completed original preview appearance required, not a playable role')
        panel = m['panel']; case = cases[(m['race'], m['gender'], m['professionIndex'])]
        expected = case['classRequest' if panel == 1 else 'partRequest']
        model = case['classSourceModel' if panel == 1 else 'partSourceModel']
        if m['sourceRequest'] != expected or m['sourceModel'] != model or m['profession'] != case['profession']:
            raise ValueError('Candidate does not match its original stage/display/model')
        if m['screen'] != ('CharacterChooseClass' if panel == 1 else 'CharacterChoosePart') or m['cameraGroup'] != (3 if panel == 1 else 2):
            raise ValueError('Original screen/camera combination differs')
        key = f"{panel}:{m['race']}:{m['gender']}:{m['professionIndex']}"
        if key in profile['candidates']:
            raise ValueError('Duplicate stage choice')
        prefix = 'game-data/converted/source-creation-stages/actors/'+folder.name+'/'
        profile['candidates'][key] = {'baseURL': '/assets/'+prefix.removeprefix('game-data/converted/'), 'sourceKey': folder.name}
        names = {'manifest.json', relative_resource(m['model'])}
        for attachment in m['attachments']:
            names.add(relative_resource(attachment['model']))
        for row in m['materials'] + [v for a in m['attachments'] for v in a['materials']]:
            names.update(relative_resource(v) for v in row['samplers'].values())
        members = {}
        for name in sorted(names):
            content = (folder/name).read_bytes()
            if prefix+name in added:
                raise ValueError('Duplicate actor member')
            added[prefix+name] = content
            members[name] = {'bytes': len(content), 'sha256': sha(content)}
        receipts.append({'sourceKey': folder.name, 'choice': key, 'manifestSHA256': sha(raw), 'members': members})
    if not profile['candidates']:
        raise ValueError('At least one verified original preview candidate required')
    profile_name = 'manifest-stages-v2.json' if actor_version == 3 else 'manifest-stages-v1.json'
    added['game-data/converted/source-creation-stage/'+profile_name] = encoded(profile)
    return added, profile, receipts


def package(output, actors, actor_version=2):
    from runtime_delta import inspect
    from creation_preview_delivery import safe_members
    output = Path(output).resolve()
    if not output.is_relative_to(ROOT/'analysis/raw') or output.exists():
        raise ValueError('New private output required')
    base, base_sha = (BASE_V2, BASE_V2_SHA) if actor_version == 3 else (BASE, BASE_SHA)
    if sha(base.read_bytes()) != base_sha:
        raise ValueError('Original published base runtime changed')
    original, _ = inspect(base)
    files = safe_members(base); files.pop('bundle-manifest.json')
    added, profile, actors_receipt = payload(actors, actor_version)
    for name in set(files) & set(added):
        if files[name] != added[name]:
            raise ValueError('Original asset replacement refused: '+name)
    added = {name: raw for name, raw in added.items() if name not in files}
    manifest = copy.deepcopy(original)
    files.update(added)
    manifest['files'] = {k: {'bytes': len(v), 'sha256': sha(v)} for k, v in sorted(files.items())}
    manifest['creationStagesIntegration'] = {'format': FORMAT, 'baseArchiveSHA256': base_sha,
        'originalPayloadsPreserved': len(original['files']), 'addedPayloads': len(added),
        'choices': sorted(profile['candidates']), 'localSavesImported': False, 'playableRacesChanged': False,
        'fullCreationOrAll45Restored': False, 'actorVersion': actor_version}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream, gzip.GzipFile(filename='', mode='wb', fileobj=stream, mtime=0) as gz, tarfile.open(fileobj=gz, mode='w') as archive:
        for name, raw in sorted({**files, 'bundle-manifest.json': encoded(manifest)}.items()):
            member = tarfile.TarInfo(name); member.size = len(raw); member.mode = 0o600
            archive.addfile(member, io.BytesIO(raw))
    output.chmod(0o600); inspect(output)
    result = {'output': str(output), 'bytes': output.stat().st_size, 'sha256': sha(output.read_bytes()),
        'integration': manifest['creationStagesIntegration'], 'actors': actors_receipt}
    output.with_suffix(output.suffix+'.receipt.json').write_bytes(encoded(result))
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--actor', type=Path, action='append', required=True)
    p.add_argument('--actor-version', type=int, choices=(2, 3), default=2)
    a = p.parse_args(); r = package(a.output, a.actor, a.actor_version)
    print(json.dumps({k: v for k, v in r.items() if k != 'actors'}))
