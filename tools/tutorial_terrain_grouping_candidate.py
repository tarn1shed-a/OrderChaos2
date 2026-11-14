"""Independent final-layer replacement policy; original payloads stay frozen."""
import argparse,hashlib,json,gzip,io,tarfile
from pathlib import Path
from selection_scene_candidate import ROOT,local_output
from tutorial_terrain_grouping_probe import PINNED
sha=lambda b:hashlib.sha256(b).hexdigest()
FORMAT='oc2-tutorial-terrain-native-material-groups-v2'


def package(output):
 output=local_output(output);files=[]
 archive=output/'tutorial-terrain-groups-append-v1.tar.gz';manifest=output/'package-manifest.json'
 if archive.exists()or manifest.exists():raise ValueError('Preserve previous candidate package')
 with archive.open('wb')as f,gzip.GzipFile(fileobj=f,mode='wb',filename='',mtime=0)as gz,tarfile.open(fileobj=gz,mode='w')as tar:
  for p in sorted((output/'assets').rglob('*')):
   if not p.is_file():continue
   data=p.read_bytes();name=str(p.relative_to(output));info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o644;tar.addfile(info,io.BytesIO(data))
   files.append({'path':name,'bytes':len(data),'sha256':sha(data)})
 r={'format':FORMAT,'payloads':len(files),'payloadBytes':sum(f['bytes']for f in files),'files':files,
  'archive':{'path':str(archive.relative_to(ROOT)),'bytes':archive.stat().st_size,'sha256':sha(archive.read_bytes())}}
 manifest.write_text(json.dumps(r,indent=2)+'\n');return r


def build(evidence,runtime,output):
 evidence,runtime,output=map(local_output,(evidence,runtime,output))
 if output.exists():raise ValueError('Choose a new independent grouping candidate')
 r=json.loads(evidence.read_text());base=runtime/'game-data/converted/geometry-water/terrain-materials.json'
 if r['format']!='oc2-tutorial-terrain-final-group-audit-v2'or r['counts']['chunks']!=16064 or sha(base.read_bytes())!=PINNED['game-data/converted/geometry-water/terrain-materials.json']:raise ValueError('Grouping source differs')
 if not r['sourceRepresentativeMaterialTransfer']or not r['nativeMaterialCopy']['fullOriginal35127cExecuted']or not r['nativeMaterialCopy']['memberIndexFieldsUnchanged']or r['nativeLayerUniformTable']['names']!=['texture1','texture2','texture3','texture4','texture5']:raise ValueError('Final representative material transfer is unproved')
 rows=[]
 for tile in r['tiles']:
  if not tile['different']:continue
  if tile['freshGlobal2527a10']!=0 or not tile['nativeFull355f28']or not tile['native35650cRepresentativeExecuted']:raise ValueError('Original grouping branch differs')
  chunks=[]
  for c in tile['chunks']:
   if not c['indicesDiffer']and not c['macroDiffers']:continue
   mask=sum(1<<i for i,v in enumerate(c['finalIndices'])if v>=0)
   if c['finalIndices'][0]<0 or mask!=c['textureLayerMask']:raise ValueError('Native macro is not represented by the final source index vector')
   binding=c['actualMaterialBinding'];rep=tile['chunks'][c['representativeChunk'][1]*8+c['representativeChunk'][0]]
   if binding!=rep['actualMaterialBinding']or [s['sourceIndex']for s in binding['samplers']]!=c['finalIndices']or binding['macro']!=mask:raise ValueError('Representative material differs from copied member')
   chunks.append({'chunk':c['chunk'],'current':c['currentEffectiveIndices'],'material':binding,'group':c['sourceGroup'],'flags':c['nativeFlags']})
  rows.append({'tile':tile['tile'],'source':tile['source'],'sourceSHA256':tile['sourceSHA256'],'textures':[t['sourcePath']for t in tile['textures']],'chunks':chunks})
 p={'format':FORMAT,'world':'tutorial','mapId':5,'profile':'APK_Default','baseMaterialsSHA256':sha(base.read_bytes()),'evidenceSHA256':sha(evidence.read_bytes()),
  'tiles':rows,'changedChunks':r['counts']['differentChunks'],'changedDry':r['counts']['differentDry'],'changedWet':r['counts']['differentWet'],
  'sourceFull355f28':True,'source3563dcRepresentative':True,'source35127cMaterialTransfer':True,'sourceGeometryChanged':False,'sourceLightingChanged':False,'savesChanged':False,
  'copyEvidence':r['nativeMaterialCopy'],'uniformEvidence':r['nativeLayerUniformTable'],
  'scope':'Explicit final representative effect/samplers/macro/water descriptor. Clone-only compatibility input to unchanged existing dry/wet constructors; native member index fields are NOT claimed copied. No new geometry, texture, lighting or collision.',
  'limits':['Native fresh mask-optimization branch, not Android active residency/device assertion.','Most group differences are masked; do not equate changedChunks with visible defects.']}
 dest=output/'assets/source-tutorial-terrain-groups';dest.mkdir(parents=True);raw=(json.dumps(p,ensure_ascii=False,separators=(',',':'))+'\n').encode();(dest/'overlay.json').write_bytes(raw)
 audit={'format':FORMAT,'overlaySHA256':sha(raw),'payloads':1,'bytes':len(raw),'oldSourcesUnchanged':all(sha((runtime/k).read_bytes())==v for k,v in PINNED.items()),'originalEvidence':str(evidence)}
 (output/'audit.json').write_text(json.dumps(audit,indent=2)+'\n');return audit


if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for k in('evidence','runtime','output'):p.add_argument('--'+k,type=Path,required=True)
 a=p.parse_args();print(json.dumps({'audit':build(a.evidence,a.runtime,a.output),'package':package(a.output)}))
