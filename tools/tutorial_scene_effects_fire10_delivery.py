"""Append ten admitted original fires to the frozen 43-effect private candidate."""
import argparse
import copy
import gzip
import io
import json
import tarfile
from pathlib import Path, PurePosixPath

from tutorial_scene_effects_assets import ROOT, output_path
from tutorial_scene_effects_delivery import sha, encode
from tutorial_scene_effects_fire10_assets import FORMAT, SOURCE

BASE = ROOT/'analysis/raw/tutorial-scene-effects-20261114/scene-effects-complete-v2.tar.gz'
BASE_SHA = '5301671ce7be5016e3b6e8205c3279599d98826d377a552b8e1609ffac15983e'
CANDIDATE = ROOT/'analysis/raw/tutorial-scene-effects-20261114/fire10-candidate-v1'


def additions():
    manifest = json.loads((CANDIDATE/'manifest.json').read_text()); audit = json.loads((CANDIDATE/'audit.json').read_text())
    if (manifest['format'] != FORMAT or manifest['source'] != SOURCE or manifest['placementCount'] != 10 or
            manifest['profile'] != 'APK_Default' or manifest['originalLookupLevel'] != 2):
        raise ValueError('Only original admitted fire10 candidate')
    for name, expected in audit['files'].items():
        if Path(name).name != name or sha((CANDIDATE/name).read_bytes()) != expected:
            raise ValueError('Candidate changed: '+name)
    names = ['manifest.json',manifest['effect'],manifest['placements'],manifest['playback'],
        *(r['file'] for r in manifest['textures'].values())]
    if len(names) != 6 or len(set(names)) != 6: raise ValueError('Unexpected runtime payload')
    files = {'game-data/converted/source-scene-fire10/'+name:(CANDIDATE/name).read_bytes() for name in names}
    for name in ['source-scene-effect-fire10-preview.js','source-scene-effect-fire10-runtime.js']:
        files['prototype/public/'+name] = (ROOT/'tools/preview'/name).read_bytes()
    files['tools/preview/source-scene-effect-fire10-overlay.mjs'] = (ROOT/'tools/preview/source-scene-effect-fire10-overlay.mjs').read_bytes()
    return files


def read_base():
    if sha(BASE.read_bytes()) != BASE_SHA: raise ValueError('Frozen first43 private base differs')
    files = {}
    with tarfile.open(BASE,'r:gz') as tar:
        for member in tar.getmembers():
            p = PurePosixPath(member.name)
            if not member.isfile() or p.is_absolute() or '..' in p.parts or member.name in files:
                raise ValueError('Unsafe base member')
            files[member.name] = tar.extractfile(member).read()
    manifest = json.loads(files.pop('bundle-manifest.json'))
    if set(files) != set(manifest['files']): raise ValueError('Base inventory differs')
    for name, raw in files.items():
        if manifest['files'][name] != {'bytes':len(raw),'sha256':sha(raw)}: raise ValueError('Base changed: '+name)
    if manifest['sceneEffectsIntegration']['conditionalOriginalPlacements'] != 43:
        raise ValueError('Expected original first43 candidate')
    return files, manifest


def package(output, complete=False):
    output = output_path(output)
    if output.exists(): raise ValueError('Choose a new ignored archive path')
    delta = additions()
    if complete:
        base, manifest = read_base()
        if set(delta)&set(base): raise ValueError('Fire10 candidate must be append-only')
        files = {**base,**delta}; manifest = copy.deepcopy(manifest)
    else:
        files = delta; manifest = {'format':'oc2-source-scene-fire10-append-v1'}
    manifest['sceneFire10Integration'] = {'format':'oc2-source-scene-fire10-append-v1',
        'baseArchiveSHA256':BASE_SHA,'appendOnly':True,'placements':10,'profile':'APK_Default','originalLookupLevel':2,
        'defaultEmitterClockExecuted':True,'sourceShapesAndQualityExecuted':True,'automaticRestart':False,
        'nativeFullResourceIOLoaded':False,'nativeRandomStreamRestored':False,'originalSoundPlaybackRestored':False,
        'lightsAdded':False,'wholeMapAccepted':False,'requiresDeploymentOverlay':True}
    manifest['files'] = {name:{'bytes':len(raw),'sha256':sha(raw)} for name,raw in sorted(files.items())}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as stream,gzip.GzipFile(filename='',mode='wb',fileobj=stream,mtime=0) as compressed,tarfile.open(fileobj=compressed,mode='w') as tar:
        for name,raw in sorted({**files,'bundle-manifest.json':encode(manifest)}.items()):
            member=tarfile.TarInfo(name);member.size=len(raw);member.mode=0o600;member.mtime=0;tar.addfile(member,io.BytesIO(raw))
    receipt={'archive':str(output.relative_to(ROOT)),'sha256':sha(output.read_bytes()),'bytes':output.stat().st_size,
        'files':len(files),'newFiles':len(delta),'existingFilesReplaced':0,'sourceFire10Placements':10,
        'wholeMapAccepted':False,'savesModified':False,'productionModified':False}
    output.with_suffix(output.suffix+'.receipt.json').write_bytes(encode(receipt))
    return receipt


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--complete',action='store_true')
    args=p.parse_args();print(json.dumps(package(args.output,args.complete)))
