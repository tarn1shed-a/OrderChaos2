"""Build a private four-inside deployment delta and optional complete archive.

The source bundle, reviewed runtime, saves and production are read-only. Only
the four already inspected primary models and their original PHY are added.
Deployment entry hooks live separately in map-runtime-inside-overlay.mjs.
"""
import argparse
import copy
import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path, PurePosixPath

from package_deployment import ROOT, DEST, python_closure

BASE_SHA='203eebc9ac16f44f9408d20bb36eadf2dec7489ac12978cdccacf44d87fc7b8b'
BASE=ROOT/'backups/deployment/oc2-runtime-attribute-final-20261113.tar.gz'
CANDIDATE=ROOT/'analysis/raw/map-specialist-20261114/inside-visible-candidate-v6'
CONFIG=ROOT/'analysis/raw/tutorial-elevator-20261114/four-inside-candidate/native-physics.json'
MANIFEST_SHA='c1a872f00cdde785c7105c4ec763d44cb48d5075f0fc9cd5faa51ad91dc730f6'
FORMAT='oc2-four-inside-delivery-delta-v1'
def digest(raw):return hashlib.sha256(raw).hexdigest()
def encode(value):return json.dumps(value,sort_keys=True,indent=2).encode()

def read_base(archive=BASE):
 archive=Path(archive)
 if digest(archive.read_bytes())!=BASE_SHA:raise ValueError('Pinned deployment base differs')
 with tarfile.open(archive,'r:gz')as packed:
  members=packed.getmembers();files={}
  for m in members:
   p=PurePosixPath(m.name)
   if not m.isfile()or p.is_absolute()or '..'in p.parts or m.name in files:raise ValueError('Unsafe base member')
   files[m.name]=packed.extractfile(m).read()
 manifest=json.loads(files.pop('bundle-manifest.json'))
 if set(files)!=set(manifest['files']):raise ValueError('Base bundle inventory differs')
 for name,raw in files.items():
  if manifest['files'][name]!={'bytes':len(raw),'sha256':digest(raw)}:raise ValueError('Base bundle file differs: '+name)
 identity=json.loads((ROOT/'tools/local_mvp_runtime.json').read_text())
 if identity!=manifest['runtimeIdentity']:raise ValueError('Reviewed runtime identity differs')
 for name,sha in identity['files'].items():
  if digest(files[name])!=sha:raise ValueError('Reviewed runtime file differs')
 return files,manifest

def delta_payload(base_files):
 checks=json.loads((ROOT/'analysis/raw/map-specialist-20261114/inside-visible-checksums.json').read_text())
 if digest((CANDIDATE/'manifest.json').read_bytes())!=MANIFEST_SHA:raise ValueError('Inspected candidate manifest differs')
 files={}
 for file in sorted(CANDIDATE.iterdir()):
  if not file.is_file()or file.is_symlink():raise ValueError('Unsafe candidate file')
  raw=file.read_bytes();expected=checks[str(file.relative_to(ROOT))]
  if expected!={'bytes':len(raw),'sha256':digest(raw)}:raise ValueError('Inspected candidate changed')
  files['game-data/converted/source-tutorial-inside/'+file.name]=raw
 helper=ROOT/'tools/preview/source-inside-models.js'
 raw=helper.read_bytes()
 if digest(raw)!=checks['tools/preview/source-inside-models.js']['sha256']:raise ValueError('Inspected material adapter differs')
 files['prototype/public/source-inside-models.js']=raw
 config=json.loads(CONFIG.read_text());old=json.loads(base_files['prototype/native-physics.json'])
 if config['nativeSHA256']!=old['nativeSHA256']or not config.get('nativeArchiveStream'):raise ValueError('Original PHY stream identity missing')
 col=Path(config['collision']).read_bytes();new_collision=json.loads(col);previous=json.loads(base_files['native-inputs/collision.json'])
 if len(new_collision['instances'])!=1044 or new_collision['instances'][:1040]!=previous['instances']:raise ValueError('Existing collision placements changed')
 if len(config['sourceFiles'])!=139 or not set(old['sourceFiles']).issubset(config['sourceFiles']):raise ValueError('Original PHY source inventory differs')
 result=copy.deepcopy(old);result['nativeArchiveStream']=True
 for name,row in config['sourceFiles'].items():
  if name in old['sourceFiles']:
   if row['sha256']!=old['sourceFiles'][name]['sha256']:raise ValueError('Existing original PHY changed')
   continue
  raw=Path(row['path']).read_bytes()
  if digest(raw)!=row['sha256']:raise ValueError('New original PHY differs')
  target='native-inputs/phy/'+row['sha256']+'.phy';files[target]=raw
  result['sourceFiles'][name]={'path':str(DEST/target),'sha256':row['sha256']}
 files['native-inputs/collision.json']=col
 files['prototype/native-physics.json']=encode(result)
 # All other native inputs and every reviewed text stay from the base bundle.
 return files

def write_archive(output,files,manifest):
 output=Path(output).resolve()
 if not any(output.is_relative_to(ROOT/p)for p in ('analysis/raw','backups'))or output.exists():raise ValueError('Choose a new ignored archive path')
 output.parent.mkdir(parents=True,exist_ok=True)
 with output.open('xb')as out,gzip.GzipFile(filename='',mode='wb',fileobj=out,mtime=0)as compressed,tarfile.open(fileobj=compressed,mode='w')as archive:
  for name,raw in sorted({**files,'bundle-manifest.json':encode(manifest)}.items()):
   info=tarfile.TarInfo(name);info.size=len(raw);info.mode=0o600;archive.addfile(info,io.BytesIO(raw))
 output.chmod(0o600)
 receipt={'archive':str(output),'sha256':digest(output.read_bytes()),'bytes':output.stat().st_size,'files':len(files),'localSavesImported':False,'wholeMapAccepted':False}
 output.with_suffix(output.suffix+'.receipt.json').write_bytes(encode(receipt));return receipt

def package(output,complete=False):
 base,manifest=read_base();delta=delta_payload(base)
 if complete:
  files={**base,**delta};manifest=copy.deepcopy(manifest)
  manifest['pythonFiles']={p:digest((ROOT/p).read_bytes())for p in python_closure()}
  manifest['mapIntegration']={'format':FORMAT,'baseArchiveSHA256':BASE_SHA,'originalRuntimePreserved':127,'insidePrimaryModels':4,'collisionInstances':1044,'liftActivityRestored':False,'wholeMapAccepted':False}
 else:
  files=delta;manifest={'format':FORMAT,'baseArchiveSHA256':BASE_SHA,'localSavesImported':False,'wholeMapAccepted':False,'requiresDeploymentOverlay':True}
 manifest['files']={name:{'bytes':len(raw),'sha256':digest(raw)}for name,raw in sorted(files.items())}
 return write_archive(output,files,manifest)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--complete',action='store_true');a=p.parse_args();print(json.dumps(package(a.output,a.complete),indent=2))
