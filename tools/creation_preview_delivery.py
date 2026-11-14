"""Append source-backed race previews to a private runtime, preserving all saves.

Only admitted geometry/decoded images and small runtime profiles are included.
Full source tables, disassemblies, probe reports and review pages stay outside
the web bundle. The original 127 runtime files are never replaced.
"""
import argparse
import copy
import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path, PurePosixPath
from runtime_delta import inspect

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'analysis/raw/tutorial-sky-candidate-20261114/qa-complete-v4.tar.gz'
BASE_SHA = 'e946b9f1a17967de274487dbbe801ae22f047f2996acf9923a7fe7ffa42ed50a'
FORMAT = 'oc2-source-creation-preview-delivery-v1'
PACKS = [
    ('selection-scene-candidate-20261115/selection-static-candidate-v1.tar.gz',
     'addd4f911eb4ec09328fa99f93cd49d886db49f4581e2b2810492fc5f1bd180e', 146),
    ('selection-scene-inside-20261115/selection-inside-append-v1.tar.gz',
     '356eadeca5d28aef4a0dfc1d492f1587053f7fb2555b3f155199e6ab3fe62fc1', 13),
    ('selection-scene-stones-20261115/selection-stones-append-v1.tar.gz',
     'ee022fe1534241ec20c66a7ba352bd64bc14b2c1b70436248068a9d6f652f5d8', 7),
]
PREVIEWS = {
    'male': 'ed884412def2622e515b552abff1215d2455199b63fdb1a50b06eb8dfd9949c4',
    'female': '68c7b075b2c5a770ea6c4d44b819898aed7b28a07feec988044387c71974a8db',
}
MODULES = ['source-selection-scene.js', 'selection_scene_inside_material.js',
           'selection_scene_stones_material.js', 'source-creation-stage.mjs',
           'character_creation_preview_proposal.mjs']
def sha(raw): return hashlib.sha256(raw).hexdigest()
def encoded(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()+b'\n'


def safe_members(path):
    with tarfile.open(path) as archive:
        result = {}
        for m in archive.getmembers():
            p = PurePosixPath(m.name)
            if not m.isfile() or p.is_absolute() or '..' in p.parts or '\\' in m.name or str(p) != m.name or m.name in result:
                raise ValueError('Unsafe original candidate package')
            result[m.name] = archive.extractfile(m).read()
    return result


def payload(stage_path, environment_path):
    result = {}
    for path, digest, count in PACKS:
        archive = ROOT/'analysis/raw'/path
        if sha(archive.read_bytes()) != digest: raise ValueError('Frozen selection append differs')
        rows = safe_members(archive)
        assets = {k: v for k, v in rows.items() if k.startswith('assets/')}
        if len(assets) != count: raise ValueError('Frozen selection append population differs')
        for key, raw in assets.items(): result['game-data/converted/'+key.removeprefix('assets/')] = raw
    for gender, digest in PREVIEWS.items():
        folder = ROOT/'analysis/raw/character-addressing-correction-20261114'/(gender+'-corrected')
        raw = (folder/'manifest.json').read_bytes()
        if sha(raw) != digest: raise ValueError('Frozen race preview manifest differs')
        manifest = json.loads(raw); checks = json.loads((folder/'package-files.json').read_text())['files']
        paths = {manifest['model'].lstrip('/'), 'manifest.json'}
        paths.update(p.lstrip('/') for row in manifest['materials'] for p in row['samplers'].values())
        for name in sorted(paths):
            p = PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or str(p) != name: raise ValueError('Unsafe character candidate member')
            content = (folder/name).read_bytes()
            if checks.get(name) != {'bytes': len(content), 'sha256': sha(content)}: raise ValueError('Frozen character bytes differ')
            result['game-data/converted/source-creation-human-'+gender+'/'+name] = content
    for name in MODULES: result['prototype/public/'+name] = (ROOT/'tools/preview'/name).read_bytes()
    stage = json.loads(Path(stage_path).read_text()); environment = json.loads(Path(environment_path).read_text())
    if (stage.get('format') != 'oc2-source-creation-stage-v1' or
        stage.get('racePanel', {}).get('panel') != 0 or stage['panelGroups'][0] != 3 or
        stage['transform'].get('originalModelCompleted') is not False or
        stage['transform'].get('scale') != [5, 5, 5] or len(stage['cameraGroups']) != 25):
        raise ValueError('Original camera/transform source proof missing')
    # Pose sample reports are audit artifacts, not required game data.
    for row in stage['cameraGroups']: row.pop('frames', None)
    if (environment.get('format') != 'oc2-selection-environment-fresh-inputs-v1' or
        not environment.get('freshStartOnly') or not environment.get('fieldInputsReady') or
        environment.get('sourceSelectionRegion') != 211 or environment.get('reentrySupported')):
        raise ValueError('Original fresh-start environment missing')
    result['game-data/converted/source-creation-stage/stage.json'] = encoded(stage)
    result['game-data/converted/source-creation-stage/environment.json'] = encoded(environment)
    profile = {'format': FORMAT, 'mapId': 7, 'sourceSelectionRegion': 211,
        'freshStartOnly': True, 'stages': ['CharacterChooseRace'],
        'stage': '/assets/source-creation-stage/stage.json',
        'environment': '/assets/source-creation-stage/environment.json',
        'scene': '/assets/source-selection-scene/manifest.json',
        'inside': '/assets/source-selection-inside/overlay.json',
        'stones': '/assets/source-selection-stones/overlay.json',
        'previews': {f'0:{i}': {'baseURL': '/assets/source-creation-human-'+gender+'/'} for i, gender in enumerate(PREVIEWS)},
        'createsPlayableRole': False, 'wholeCreationRestored': False,
        'sourceModelCompletionProved': False, 'sourceGPUObserved': False,
        'remaining': ['other race previews', 'profession/saved-role previews', 'sky/effects and unresolved records', 'original live streaming center'],
    }
    result['game-data/converted/source-creation-stage/manifest.json'] = encoded(profile)
    return result


def package(output, stage_path, environment_path):
    output = Path(output).resolve()
    if not output.is_relative_to(ROOT/'analysis/raw') or output.exists(): raise ValueError('Choose a fresh ignored output path')
    if sha(BASE.read_bytes()) != BASE_SHA: raise ValueError('Pinned current runtime differs')
    original, _ = inspect(BASE)
    files = safe_members(BASE); files.pop('bundle-manifest.json')
    if len(original['runtimeIdentity']['files']) != 127: raise ValueError('Reviewed runtime population differs')
    added = payload(stage_path, environment_path)
    if set(files) & set(added): raise ValueError('Append cannot replace an original runtime member')
    files.update(added); manifest = copy.deepcopy(original)
    manifest['files'] = {k: {'bytes': len(v), 'sha256': sha(v)} for k, v in sorted(files.items())}
    manifest['creationPreviewIntegration'] = {'format': FORMAT, 'baseArchiveSHA256': BASE_SHA,
        'existingMembersPreserved': len(original['files']), 'addedFiles': len(added),
        'reviewedRuntimePreserved': 127, 'pythonHostFilesPreserved': len(original['pythonFiles']),
        'stages': ['CharacterChooseRace'], 'playableRacesChanged': False,
        'localSavesImported': False, 'wholeCreationRestored': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream, gzip.GzipFile(filename='', mode='wb', fileobj=stream, mtime=0) as compressed, tarfile.open(fileobj=compressed, mode='w') as archive:
        for name, raw in sorted({**files, 'bundle-manifest.json': encoded(manifest)}.items()):
            member = tarfile.TarInfo(name); member.size = len(raw); member.mode = 0o600; archive.addfile(member, io.BytesIO(raw))
    output.chmod(0o600)
    inspect(output)
    receipt = {'format': FORMAT, 'output': str(output), 'sha256': sha(output.read_bytes()),
        'bytes': output.stat().st_size, 'files': len(files), **manifest['creationPreviewIntegration']}
    output.with_suffix(output.suffix+'.receipt.json').write_bytes(encoded(receipt))
    return receipt


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output', type=Path, required=True)
    cli.add_argument('--stage', type=Path, default=ROOT/'analysis/raw/creation-stage-transform-20261115/source-stage-v2.json')
    cli.add_argument('--environment', type=Path, default=ROOT/'analysis/raw/selection-scene-environment-upstream-20261115/result-v2-fresh-inputs.json')
    args = cli.parse_args(); print(json.dumps(package(args.output, args.stage, args.environment)))
