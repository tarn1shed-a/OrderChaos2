"""Append verified original journal assets without replacing runtime or saves."""
import argparse,copy,gzip,hashlib,io,json,tarfile
from pathlib import Path
from runtime_delta import ROOT,inspect,package as delta_package,sha

encode=lambda v:(json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()

def package(base,assets,output,delta=None):
 base,assets,output=map(lambda p:Path(p).resolve(),(base,assets,output))
 if not any(output.is_relative_to(ROOT/p)for p in ['analysis/raw','backups/deployment'])or output.exists():raise ValueError('Choose a new ignored archive')
 manifest,_=inspect(base);profile=json.loads((assets/'profile.json').read_text());art=json.loads((assets/'journal-art.json').read_text())
 prefix='game-data/converted/source-quest-journal/'
 if profile['format']!='oc2-original-ordinary-journal-v1'or profile['questId']!=461 or profile['mapId']!=1 or art['gaps']:raise ValueError('Verified ordinary journal required')
 expected={'profile.json','journal-art.json','source-program.json','widget-program.json'}
 expected.update(v['file']for kind in ['assets','windows','stateDrawings']for v in art[kind].values())
 actual={p.name for p in assets.iterdir()if p.is_file()and not p.is_symlink()}
 if actual!=expected or any(p.is_symlink()or not p.is_file()for p in assets.iterdir()):raise ValueError('Original journal inventory differs')
 for kind in ['assets','windows','stateDrawings']:
  for row in art[kind].values():
   if sha(assets/row['file'])!=row['sha256']:raise ValueError('Original art bytes differ')
 for name,field in [('source-program.json','programSHA256'),('widget-program.json','widgetProgramSHA256')]:
  if sha(assets/name)!=profile[field]:raise ValueError('Original program differs')
 additions={prefix+name:(assets/name).read_bytes()for name in sorted(expected)}
 if set(additions)&set(manifest['files']):raise ValueError('Journal append cannot replace existing payload')
 next_manifest=copy.deepcopy(manifest)
 next_manifest['files'].update({name:{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}for name,raw in additions.items()})
 next_manifest['ordinaryJournal']={'questId':461,'compatibleAcceptedStateOnly':True,'originalTaskApprovalRecovered':False,'baseArchiveSHA256':sha(base)}
 output.parent.mkdir(parents=True,exist_ok=True)
 with tarfile.open(base,'r:gz')as old,output.open('xb')as stream,gzip.GzipFile(filename='',mode='wb',fileobj=stream,mtime=0)as zipped,tarfile.open(fileobj=zipped,mode='w')as new:
  for name in sorted(next_manifest['files']):
   raw=additions[name]if name in additions else old.extractfile(name).read()
   row=tarfile.TarInfo(name);row.mode=0o600;row.size=len(raw);new.addfile(row,io.BytesIO(raw))
  raw=encode(next_manifest);row=tarfile.TarInfo('bundle-manifest.json');row.mode=0o600;row.size=len(raw);new.addfile(row,io.BytesIO(raw))
 output.chmod(0o600);checked,_=inspect(output)
 if any(checked['files'][k]!=v for k,v in manifest['files'].items()):raise ValueError('Base payload changed')
 receipt={'archive':str(output),'sha256':sha(output),'bytes':output.stat().st_size,'baseArchiveSHA256':sha(base),
  'newFiles':len(additions),'payloadFiles':len(checked['files']),'baseFilesReplaced':0,'localSavesImported':False}
 if delta:receipt['delta']=delta_package(base,output,delta)
 proof=output.with_suffix(output.suffix+'.receipt.json')
 if proof.exists():raise ValueError('Existing proof must be preserved')
 proof.write_bytes(encode(receipt));proof.chmod(0o600);return receipt

if __name__=='__main__':
 c=argparse.ArgumentParser(description=__doc__)
 for name in ['base','assets','output']:c.add_argument('--'+name,type=Path,required=True)
 c.add_argument('--delta',type=Path);a=c.parse_args();print(json.dumps(package(a.base,a.assets,a.output,a.delta),indent=2))
