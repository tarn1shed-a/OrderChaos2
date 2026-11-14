"""Append the frozen read-only character panels to the private four-inside bundle.

No base member, reviewed runtime, game rule, native input or save is changed.
The stageCharacterPanelsEntry / stageCharacterPanelsPlan deployment hooks are
integrated separately by root. Their SHA in the archive is a build-time audit;
the overlay itself is outside the append-only runtime bundle.
"""
import argparse
import copy
import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path,PurePosixPath

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'backups/deployment/oc2-runtime-four-inside-20261114.tar.gz'
BASE_SHA='a2b224a85878934e0003b46afaf79f78b8d70ff03f977b568b9ab37fb5ff1cf7'
CANDIDATE=ROOT/'analysis/raw/character-progression-20261114/panel-candidate-final'
CANDIDATE_MANIFEST_SHA='8fe259f894a4003d11090b3190555e75f45a513d408e4bfb51c952c99d1f9c2b'
FROZEN=ROOT/'analysis/raw/character-progression-20261114/panel-batch4/SHA256.json'
OVERLAY=ROOT/'tools/preview/character-panel-runtime-overlay.mjs'
FORMAT='oc2-character-panel-delivery-v1'
MODULES=('character-source-panels.mjs','character-source-state.mjs','character-source-panels.css')
def digest(raw):return hashlib.sha256(raw).hexdigest()
def encode(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2).encode()+b'\n'


def read_base(archive=BASE):
    archive=Path(archive)
    if digest(archive.read_bytes())!=BASE_SHA:raise ValueError('Pinned four-inside bundle differs')
    with tarfile.open(archive,'r:gz')as packed:
        files={}
        for member in packed.getmembers():
            name=member.name;p=PurePosixPath(name)
            if not member.isfile()or p.is_absolute()or '..'in p.parts or str(p)!=name or name in files:raise ValueError('Unsafe base member')
            files[name]=packed.extractfile(member).read()
    manifest=json.loads(files.pop('bundle-manifest.json'))
    if set(files)!=set(manifest['files']):raise ValueError('Base inventory differs')
    for name,raw in files.items():
        if manifest['files'][name]!={'bytes':len(raw),'sha256':digest(raw)}:raise ValueError('Base member changed: '+name)
    identity=json.loads((ROOT/'tools/local_mvp_runtime.json').read_text())
    if identity!=manifest['runtimeIdentity']or len(identity['files'])!=127:raise ValueError('Reviewed runtime identity differs')
    for name,expected in identity['files'].items():
        if digest(files[name])!=expected:raise ValueError('Reviewed original runtime changed: '+name)
    if manifest.get('localSavesImported')is not False or manifest.get('mapIntegration',{}).get('insidePrimaryModels')!=4:raise ValueError('Four-inside no-save base identity missing')
    return files,manifest


def panel_payload(base_files,candidate=CANDIDATE):
    candidate=Path(candidate);public=candidate/'public';checks_raw=(candidate/'SHA256.json').read_bytes()
    if digest(checks_raw)!=CANDIDATE_MANIFEST_SHA:raise ValueError('Frozen character candidate differs')
    checks=json.loads(checks_raw);freeze=json.loads(FROZEN.read_text())
    for path,meta in freeze.items():
        if isinstance(meta,dict)and path.startswith(('tools/','docs/'))and digest((ROOT/path).read_bytes())!=meta['sha256']:raise ValueError('Frozen character implementation changed: '+path)
    def read(name):
        p=public/name
        if p.is_symlink()or not p.is_file()or digest(p.read_bytes())!=checks.get(name):raise ValueError('Frozen character asset changed: '+name)
        return p.read_bytes()
    files={}
    asset_paths=sorted((public/'assets/character-source').iterdir())
    if any(not p.is_file()or p.is_symlink()or p.suffix not in('.png','.svg','.json')for p in asset_paths):raise ValueError('Unexpected character asset')
    for p in asset_paths:files['game-data/converted/character-source/'+p.name]=read('assets/character-source/'+p.name)
    for name in MODULES:files['prototype/public/'+name]=read(name)
    if set(base_files)&set(files):raise ValueError('Character append would overwrite an existing base member')
    # Existing frame art, fonts and source SVG helper remain byte-for-byte base
    # dependencies. Login/entry art is deliberately not copied or overwritten.
    dependencies=['prototype/public/source-ui-svg.js']
    dependencies.extend('game-data/converted/ui/'+n for n in('chineseText.woff','chineseDisplay.woff','leagueGothic.woff','igm-atlas-1.png','igm-atlas-8.png'))
    for name in dependencies:
        relative=name.removeprefix('prototype/public/')if name.startswith('prototype/public/')else'assets/'+name.removeprefix('game-data/converted/')
        if base_files.get(name)!=read(relative):raise ValueError('Existing panel dependency differs: '+name)
    if len(files)!=104:raise ValueError('Frozen panel append inventory differs')
    return files,dependencies


def write_archive(output,files,manifest,receipt_fields):
    output=Path(output).resolve()
    if not any(output.is_relative_to(ROOT/p)for p in('analysis/raw','backups'))or output.exists():raise ValueError('Choose a new ignored archive path')
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb')as raw,gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0)as compressed,tarfile.open(fileobj=compressed,mode='w')as archive:
        for name,content in sorted({**files,'bundle-manifest.json':encode(manifest)}.items()):
            member=tarfile.TarInfo(name);member.size=len(content);member.mode=0o600;archive.addfile(member,io.BytesIO(content))
    output.chmod(0o600)
    receipt={'format':FORMAT,'archive':str(output),'sha256':digest(output.read_bytes()),'bytes':output.stat().st_size,'files':len(files),**receipt_fields}
    output.with_suffix(output.suffix+'.receipt.json').write_bytes(encode(receipt));return receipt


def package(output,archive=BASE,candidate=CANDIDATE):
    base,manifest=read_base(archive);delta,dependencies=panel_payload(base,candidate)
    combined={**base,**delta};result=copy.deepcopy(manifest)
    integration={'format':FORMAT,'baseArchiveSHA256':BASE_SHA,'candidateManifestSHA256':CANDIDATE_MANIFEST_SHA,
        'overlaySHA256':digest(OVERLAY.read_bytes()),'baseMembersUnchanged':len(base),'originalRuntimePreserved':127,'addedFiles':len(delta),
        'realSourceState':None,'trialProgress':'Read-only existing field-xp.value/max; no conversion or award',
        'standaloneQAIncluded':False,'requiresDeploymentOverlay':True,'localSavesImported':False,
        'learningServiceRestored':False,'wholeCharacterSystemAccepted':False}
    result['characterIntegration']=integration
    result['files']={name:{'bytes':len(raw),'sha256':digest(raw)}for name,raw in sorted(combined.items())}
    return write_archive(output,combined,result,{'baseArchiveSHA256':BASE_SHA,'candidateManifestSHA256':CANDIDATE_MANIFEST_SHA,
        'overlaySHA256':integration['overlaySHA256'],'baseMembersUnchanged':len(base),'appendedFiles':len(delta),
        'existingDependencies':{n:digest(base[n])for n in dependencies},'localSavesImported':False,'standaloneQAIncluded':False,
        'realSourceState':None,'requiresDeploymentOverlay':True,'wholeCharacterSystemAccepted':False})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(package(args.output),ensure_ascii=False,indent=2))
