"""Append the verified ordinary-task area to the current private runtime.

No source table dump, credentials, saved characters or QA state is packaged.
The previous runtime payload remains byte-for-byte present, including map5.
"""
import argparse
import copy
import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path, PurePosixPath

from ordinary_quest_profile import export_profile
from package_deployment import ROOT, DEST
from runtime_delta import inspect, package as make_delta

BASE = ROOT/'backups/deployment/oc2-runtime-character-panels-20261114.tar.gz'
CURRENT = ROOT/'backups/deployment/tutorial-terrain-groups-context-20261115/deploy/private-runtime.tar.gz'
BASE_SHA = 'f1dc28154f890f3e3eccd39e927130e51daa693f215d8cd0936bbc4c063d4569'
CURRENT_SHA = '6f764b775b98ff70aae8f7ff26b3b1b3adbfb2211ae5375fd1af6e4777bc3b00'
MAP = ROOT/'analysis/raw/plain-quest-map1-20261115/candidate-v3'
ACTORS = ROOT/'analysis/raw/plain-quest-feasibility-20261115/actors-v4'
UI = ROOT/'analysis/raw/quest-ui-compatible-20261115/qa-v1'
TRACKING = ROOT/'analysis/raw/ordinary-quest-tracking-20261115/candidate-v1'
sha=lambda b:hashlib.sha256(b).hexdigest()
encode=lambda v:(json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()


def load_current():
    if sha(BASE.read_bytes())!=BASE_SHA or sha(CURRENT.read_bytes())!=CURRENT_SHA:
        raise ValueError('Pinned current runtime identity differs')
    old,_=inspect(BASE)
    files={}
    with tarfile.open(BASE)as archive:
        for name in old['files']:files[name]=archive.extractfile(name).read()
    with tarfile.open(CURRENT)as archive:
        manifest=json.load(archive.extractfile('bundle-manifest.json'))
        reference=json.load(archive.extractfile('bundle-base.json'))
        if reference['baseArchiveSHA256']!=BASE_SHA:
            raise ValueError('Current base reference differs')
        for m in archive.getmembers():
            if m.name in ('bundle-base.json','bundle-manifest.json'):continue
            if not m.isfile()or m.name in files or '..'in PurePosixPath(m.name).parts:
                raise ValueError('Unsafe current delta')
            files[m.name]=archive.extractfile(m).read()
    if set(files)!=set(manifest['files']):raise ValueError('Current inventory differs')
    for name,raw in files.items():
        if manifest['files'][name]!={'bytes':len(raw),'sha256':sha(raw)}:raise ValueError('Current bytes differ '+name)
    return files,manifest


def package(output,delta=None):
    output=Path(output).resolve()
    if not output.is_relative_to(ROOT/'backups/deployment')or output.exists():raise ValueError('Choose a new ignored deployment archive')
    files,previous=load_current();base=dict(files)
    def add(name,raw):
        if name in files and files[name]!=raw:raise ValueError('Cannot replace current runtime '+name)
        files[name]=raw
    for folder in [MAP,ACTORS,UI,TRACKING]:
        for file in sorted((folder/'assets').rglob('*')):
            if not file.is_file():continue
            if file.is_symlink()or file.suffix not in ('.json','.png','.svg','.woff'):
                raise ValueError('Unlisted resource kind '+str(file))
            add('game-data/converted/'+str(file.relative_to(folder/'assets')),file.read_bytes())
    for name in ['mission_program.mjs','program-v1.json','item-assets.json','quality-frames.json']:
        target='prototype/public/'+name if name=='mission_program.mjs'else 'game-data/converted/ordinary-quests/'+name
        add(target,(UI/name).read_bytes())
    profile=export_profile()
    add('game-data/converted/ordinary-quests/profile.json',encode(profile))
    for name in ['ordinary-quest-scene.mjs','source-ordinary-quest-actors.mjs',
                 'source-npc-final-pair-material.js','source-npc-material.js']:
        add('prototype/public/'+name,(ROOT/'tools/preview'/name).read_bytes())
    # Assert every existing module referenced by the scene wrapper is exactly
    # the CPU/GPU-reviewed version; never overwrite an older one to make it fit.
    closure=json.loads((MAP/'verification-v1.json').read_text())['moduleClosure']
    for name,row in closure.items():
        path=row if isinstance(row,str)else row['path']
        add('prototype/public/'+name,(ROOT/path).read_bytes())
    terrain=json.loads((MAP/'assets/source-ordinary-quest-map1/terrain.json').read_text())
    collision=json.loads((MAP/'assets/source-ordinary-quest-map1/collision.json').read_text())
    collision['coordinateFrame']={'min':terrain['bounds']['min'],'max':terrain['bounds']['max'],'width':1280,'height':1280}
    prefix='native-inputs/ordinary-quest/'
    add(prefix+'collision.json',encode(collision))
    source_files={}
    for name,row in collision['sourceFiles'].items():
        raw=(MAP/row['file']).read_bytes()
        if sha(raw)!=row['sha256']:raise ValueError('Original ordinary PHY changed')
        target=prefix+'phy/'+row['sha256']+'.phy';add(target,raw)
        source_files[name]={'path':str(DEST/target),'sha256':row['sha256']}
    original_config=json.loads(files['prototype/native-physics.json'])
    config={'python':'/opt/venv/bin/python','worker':'/opt/oc2/tools/source_physics_worker.py',
            'config':str(DEST/(prefix+'native-physics.json')),'library':original_config['library'],
            'nativeSHA256':original_config['nativeSHA256'],'sourceFiles':source_files,
            'terrain':str(DEST/'game-data/converted/source-ordinary-quest-map1/terrain.json'),
            'terrainLighting':str(DEST/'game-data/converted/source-ordinary-quest-map1/terrain-lighting.json'),
            'collision':str(DEST/(prefix+'collision.json'))}
    add(prefix+'native-physics.json',encode(config))
    manifest=copy.deepcopy(previous)
    manifest['files']={name:{'bytes':len(raw),'sha256':sha(raw)}for name,raw in sorted(files.items())}
    manifest['ordinaryQuest']={'questIds':[q['id']for q in profile['quests']],'compatibleExecution':True,'originalServerRecovered':False,
                             'wholeMapRestored':False,'existingCharactersImported':False,'baseCurrentSHA256':CURRENT_SHA}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb')as stream,gzip.GzipFile(filename='',mode='wb',fileobj=stream,mtime=0)as compressed,tarfile.open(fileobj=compressed,mode='w')as archive:
        for name,raw in sorted({**files,'bundle-manifest.json':encode(manifest)}.items()):
            m=tarfile.TarInfo(name);m.size=len(raw);m.mode=0o600;archive.addfile(m,io.BytesIO(raw))
    output.chmod(0o600)
    receipt={'archive':str(output),'sha256':sha(output.read_bytes()),'bytes':output.stat().st_size,
             'newFiles':len(files)-len(base),'existingFilesReplaced':0,'existingSavesImported':False}
    output.with_suffix(output.suffix+'.receipt.json').write_bytes(encode(receipt))
    if delta:receipt['delta']=make_delta(BASE,output,delta)
    return receipt


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output',type=Path,required=True);cli.add_argument('--delta',type=Path)
    args=cli.parse_args();print(json.dumps(package(args.output,args.delta),indent=2))
