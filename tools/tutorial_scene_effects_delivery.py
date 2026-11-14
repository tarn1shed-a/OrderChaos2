"""Append the verified fire/smoke group to a pinned private delivery bundle.

No existing member is replaced. Deployment hooks remain a separate new module;
the caller must opt into them in its own deployment preparation copy.
"""
import argparse
import copy
import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path, PurePosixPath

from tutorial_scene_effects_assets import ROOT, output_path
from tutorial_scene_effects_package import checked_candidate

BASE = ROOT/'backups/deployment/oc2-runtime-character-panels-20261114.tar.gz'
BASE_SHA = 'f1dc28154f890f3e3eccd39e927130e51daa693f215d8cd0936bbc4c063d4569'
CANDIDATE = ROOT/'analysis/raw/tutorial-scene-effects-20261114/candidate-v3'
PLAYBACK = ROOT/'analysis/raw/tutorial-scene-effects-20261114/lifecycle-v3/playback.json'
def sha(raw): return hashlib.sha256(raw).hexdigest()
def encode(value): return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode()


def additions():
    candidate, _, names = checked_candidate(CANDIDATE)
    frozen = json.loads((ROOT/'analysis/raw/tutorial-scene-effects-20261114/isolated-handoff.json').read_text())
    for name, expected in frozen['frozenFiles'].items():
        if sha((ROOT/name).read_bytes()) != expected: raise ValueError('Frozen first group changed: '+name)
    from tutorial_scene_effects_lifecycle_probe import playback_profile
    report = json.loads((PLAYBACK.parent/'lifecycle.json').read_text())
    if json.loads(PLAYBACK.read_text()) != playback_profile(report): raise ValueError('Playback proof differs')
    files = {'game-data/converted/source-scene-effects/'+name: (candidate/name).read_bytes() for name in names}
    files['game-data/converted/source-scene-effects/playback.json'] = PLAYBACK.read_bytes()
    for name in ('source-scene-effect-preview.js', 'source-scene-effect-runtime.js', 'source-scene-effect-clock.mjs'):
        files['prototype/public/'+name] = (ROOT/'tools/preview'/name).read_bytes()
    files['tools/preview/source-scene-effect-overlay.mjs'] = (ROOT/'tools/preview/source-scene-effect-overlay.mjs').read_bytes()
    return files


def read_base():
    if sha(BASE.read_bytes()) != BASE_SHA: raise ValueError('Pinned deployment base differs')
    files = {}
    with tarfile.open(BASE, 'r:gz') as tar:
        for member in tar.getmembers():
            path = PurePosixPath(member.name)
            if not member.isfile() or path.is_absolute() or '..' in path.parts or member.name in files:
                raise ValueError('Unsafe base member')
            files[member.name] = tar.extractfile(member).read()
    manifest = json.loads(files.pop('bundle-manifest.json'))
    if set(files) != set(manifest['files']): raise ValueError('Base bundle inventory differs')
    for name, raw in files.items():
        if manifest['files'][name] != {'bytes': len(raw), 'sha256': sha(raw)}:
            raise ValueError('Base bundle member differs: '+name)
    return files, manifest


def package(output, complete=False):
    output = output_path(output)
    if output.exists(): raise ValueError('Choose a new ignored archive path')
    delta = additions()
    if complete:
        base, manifest = read_base()
        if set(base) & set(delta): raise ValueError('Scene effect layer must be append-only')
        files = {**base, **delta}; manifest = copy.deepcopy(manifest)
    else:
        files = delta; manifest = {'format': 'oc2-source-scene-effects-append-v1'}
    integration = {'format': 'oc2-source-scene-effects-append-v1', 'baseArchiveSHA256': BASE_SHA,
        'baseSourceCommit': 'ccdb6c57719cfbfaab9c043c327e55adaaba57bc',
        'appendOnly': True, 'conditionalOriginalPlacements': 43, 'resourceGroupsRemaining': 13,
        'defaultEmitterClockExecuted': True, 'wholeMapAccepted': False,
        'nativeFullResourceIOLoaded': False, 'nativeRandomStreamRestored': False,
        'lightsAdded': False, 'automaticRestart': False, 'localSavesImported': False,
        'requiresDeploymentOverlay': True}
    manifest['sceneEffectsIntegration'] = integration
    manifest['files'] = {name: {'bytes': len(raw), 'sha256': sha(raw)} for name, raw in sorted(files.items())}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream, gzip.GzipFile(filename='', mode='wb', fileobj=stream, mtime=0) as compressed, tarfile.open(fileobj=compressed, mode='w') as archive:
        for name, raw in sorted({**files, 'bundle-manifest.json': encode(manifest)}.items()):
            member = tarfile.TarInfo(name); member.size = len(raw); member.mode = 0o600; member.mtime = 0
            archive.addfile(member, io.BytesIO(raw))
    proof = {'archive': str(output.relative_to(ROOT)), 'sha256': sha(output.read_bytes()), 'bytes': output.stat().st_size,
        'files': len(files), 'newFiles': len(delta), 'existingFilesReplaced': 0,
        'wholeMapAccepted': False, 'savesModified': False, 'productionModified': False}
    output.with_suffix(output.suffix+'.receipt.json').write_bytes(encode(proof))
    return proof


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output', type=Path, required=True)
    p.add_argument('--complete', action='store_true'); args = p.parse_args()
    print(json.dumps(package(args.output, args.complete), ensure_ascii=False))
