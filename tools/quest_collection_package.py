"""Append pinned collection art/source inputs without replacing live assets."""
import argparse
import copy
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
from creation_preview_delivery import safe_members
from runtime_delta import inspect, sha

ROOT=Path(__file__).resolve().parents[1]
BASE='e683041c3e7d7c6c9a1df4949feb75b3fc156697ce50710da52ec23b0952fb8b'
PROGRAM='4aed22d400be720600dfa91a4030b6dd7ef3cd43b04728f07f5898d46b134be2'
VISUAL='8b47d8cf5395ae2f60beacc81564b559f1f5f2fe287d262b4f59c07609a1fc0c'
ART='6f3f2ae104dc1eb5d659b30136a5137ef2d718a8e7833514490d3218e69e10b3'
SOURCE='0fe5482598667a28f459cce0bd4a533fb440102df6b983c317a7742a1a82dea8'
BINDING='c939575b7a4d7be63419a7d679df0ce5a08b174c1e2ebd1b2823b0a77fd582a3'
digest=lambda b:hashlib.sha256(b).hexdigest()
encode=lambda v:(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()

def package(source_root,base,output):
 source_root,base,output=map(lambda p:Path(p).resolve(),(source_root,base,output))
 if not output.is_relative_to(ROOT/'analysis/raw')or output.exists():raise ValueError('New ignored output required')
 if sha(base)!=BASE:raise ValueError('Preserve the current live complete preview bundle')
 old,_=inspect(base);files=safe_members(base);files.pop('bundle-manifest.json');added={}
 def add(folder,name,pin):
  raw=(folder/name).read_bytes()
  if digest(raw)!=pin:raise ValueError('Original collection source differs: '+name)
  return raw
 art=ROOT/'analysis/raw/quest461-channel-art-20261116/art-v2'
 manifest=add(art,'manifest.json',ART);drawing=json.loads(manifest)
 added['game-data/converted/source-quest461-channel-v1/manifest.json']=manifest
 for item in [drawing['svg'],*drawing['assets'].values()]:
  raw=add(art,item['file'],item['sha256'])
  if len(raw)!=item['bytes']:raise ValueError('Artwork size differs')
  added['game-data/converted/source-quest461-channel-v1/'+item['file']]=raw
 original=source_root/'analysis/raw/quest461-channel-parent-20261116/public'
 for name,pin in [('program.json',PROGRAM),('profile.json',VISUAL)]:
  added['game-data/converted/source-quest461-channel-v1/'+name]=add(original,name,pin)
 source=source_root/'analysis/raw/ordinary-quest461-browser-gather-20261116/candidate-v2/quest461-browser-gather-v1/assets'
 for name,pin in [('source.json',SOURCE),('binding.json',BINDING)]:
  added['game-data/converted/source-quest461-gather-v1/'+name]=add(source,name,pin)
 added['game-data/converted/source-quest461-channel-v1/execution.json']=encode({
  'format':'oc2-compatible-461-channel-v1','originalServerRecovered':False,'questId':461,'mapId':1,
  'objectEntry':467,'skillProtoId':15,'skillChannelTime':1500,'isChannel':False,
  'programSHA256':PROGRAM,'visualSHA256':VISUAL,'artSHA256':ART})
 if set(added)&set(files):raise ValueError('Collection append cannot overwrite existing assets')
 files.update(added);m=copy.deepcopy(old)
 m['files']={n:{'bytes':len(b),'sha256':digest(b)}for n,b in sorted(files.items())}
 m['questCollectionIntegration']={'compatibleQuestId':461,'originalServerRecovered':False,
  'preservedBaseArchiveSHA256':BASE,'preservedPayloads':len(old['files']),'addedPayloads':len(added),
  'sourcePoseBody':'legacy-elf-female','sourceActorInitialStateRecovered':False,
  'windowMeasurement':'browser-original-SVG-content','nativeFlashBoundsObserved':False,
  'localSavesImported':False,'mainline208OrQuest227Enabled':False}
 output.parent.mkdir(parents=True,exist_ok=True)
 with output.open('xb')as stream,gzip.GzipFile(fileobj=stream,mode='wb',filename='',mtime=0)as gz,tarfile.open(fileobj=gz,mode='w')as tar:
  for name,raw in sorted({**files,'bundle-manifest.json':encode(m)}.items()):
   item=tarfile.TarInfo(name);item.size=len(raw);item.mode=0o600;tar.addfile(item,io.BytesIO(raw))
 output.chmod(0o600);verified,_=inspect(output)
 if any(verified['files'].get(n)!=meta for n,meta in old['files'].items()):raise ValueError('Existing payload identity changed')
 result={'archive':str(output),'sha256':sha(output),'bytes':output.stat().st_size,'payloads':len(files),**m['questCollectionIntegration']}
 output.with_suffix(output.suffix+'.receipt.json').write_bytes(encode(result));return result

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['source-root','base','output']:p.add_argument('--'+name,type=Path,required=True)
 a=p.parse_args();print(json.dumps(package(a.source_root,a.base,a.output),ensure_ascii=False))
