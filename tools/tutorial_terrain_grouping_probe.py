"""Audit shipped tutorial material groups against original TRN/MSK consumers."""
import argparse,hashlib,json,collections
from pathlib import Path
from tutorial_terrain_grouping_native import TutorialTerrainGroups
from selection_scene_candidate import ROOT,local_output
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from selection_scene_water_floor_group_copy import controlled_copy,uniform_names
sha=lambda b:hashlib.sha256(b).hexdigest()
NATIVE_SHA='77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4'
PINNED={'game-data/converted/geometry-water/terrain-materials.json':'755af4bb2b9c5e7f63f8b4eb0c024052798552e73f14939fb09a5857b6625227',
 'prototype/public/terrain-materials.js':'f8dd01f16fa74f5c8941690e11ed4473f77c888530d8f9f54f81b59c62464623',
 'prototype/public/source-water-floor.js':'2061935f0602e43f85870c9e12bc42543d8736b7be3034cfebf356057e28a8b3'}


def analyze(image,runtime):
 if sha(image.data)!=NATIVE_SHA:raise ValueError('Original native build differs')
 runtime=local_output(runtime);loaded={}
 for name,digest in PINNED.items():
  b=(runtime/name).read_bytes()
  if sha(b)!=digest:raise ValueError('Current tutorial base differs: '+name)
  loaded[name]=digest
 mat=json.loads((runtime/'game-data/converted/geometry-water/terrain-materials.json').read_text())
 if mat['world']!='tutorial'or len(mat['tiles'])!=251:raise ValueError('Current tutorial material coverage differs')
 source=Sources(DEFAULT_SOURCE);native=TutorialTerrainGroups(image);rows=[];counts=collections.Counter();near=[]
 for tile in mat['tiles']:
  x,z=tile['tile'];name='world/tutorial/terrain/%04d_%04d.trn'%(x,z);raw=source.read(name)
  if mat['sources'][name]['sha256']!=sha(raw):raise ValueError('Current tutorial source SHA differs')
  native.read(raw);r=native.groups(source,tile['tile']);different=[]
  for j,(c,old)in enumerate(zip(r['chunks'],tile['chunks'])):
   if c['rawIndices']!=old['indices']or c['classes']!=old['maskClasses']or c['prunedIndices']!=old['effectiveIndices']:raise ValueError('Frozen tutorial pruning source differs')
   if bool(c['nativeFlags']&0x10000)!=old['sourceWaterPending']:raise ValueError('Frozen tutorial water flag differs')
   current=old['effectiveIndices'];final=c['finalIndices'];counts['chunks']+=1;counts['wet'if old['sourceWaterPending']else'dry']+=1
   c['currentEffectiveIndices']=current;c['currentActiveMask']=sum((1<<i)for i,v in enumerate(current)if v>=0)
   c['indicesDiffer']=current!=final;c['macroDiffers']=c['currentActiveMask']!=c['textureLayerMask']
   c['actualMaterialBinding']={'sourceEffect':24,'representative':c['representativeChunk'],'macro':c['textureLayerMask'],
    'samplers':[{'ordinal':i,'uniform':'texture'+str(i+1),'sourceIndex':v,'sourcePath':tile['textures'][v]['sourcePath']if v>=0 else None,
      'url':tile['textures'][v]['url']if v>=0 else None,'active':bool(c['textureLayerMask']&(1<<i))}for i,v in enumerate(final)],
    'water':c.get('representativeWaterDescriptor'),'source35127cFields':['effect@68','colorTable@88','samplerBytes@9c..a0']}
   if c['indicesDiffer']or c['macroDiffers']:
    different.append(c['chunk']);counts['differentChunks']+=1;counts['differentWet'if old['sourceWaterPending']else'differentDry']+=1
   if final[0]<0:counts['nativeMissingBase']+=1
   if current[0]<0:counts['currentMissingBase']+=1
  r.update(tile=tile['tile'],source=name,sourceSHA256=sha(raw),textures=tile['textures'],different=different)
  rows.append(r)
  if abs(x-(-41))<=2 and abs(z-(-1))<=2:near.append({'tile':tile['tile'],'different':different,'nativeGroups':r['nativeGroupCount']})
 routines={}
 for a in(0x358e08,0x359ad0,0x355f28,0x359d64,0x3563dc,0x3509c4,0x35127c,0x351690):
  m,_=image.routine(a);routines[hex(a)]={**m,'sha256':sha(image.read(int(m['start'],16),m['size']))}
 actual={name:sha((runtime/'prototype/public'/name).read_bytes())for name in('explore-map.js','terrain-materials-expanded.js','terrain-lighting-window.js','source-water-floor-swimming.js','source-map-geometry.js')}
 return {'format':'oc2-tutorial-terrain-final-group-audit-v2','world':'tutorial','mapId':5,'counts':dict(counts),'tiles':rows,
  'sourceRepresentativeMaterialTransfer':True,'nativeMaterialCopy':controlled_copy(image),'nativeLayerUniformTable':uniform_names(image),
  'sourceProofs':source.proofs,'nativeRoutines':routines,'pinnedOldFiles':loaded,'actualEntryModules':actual,'approvedEntryNearTiles':near,
  'entryPosition':[-2594,136,-64],'entryIsOriginalFirstSpawn':False,'originalAndroidGPUObserved':False,'runtimeChanged':False,'lightsChanged':False,'savesChanged':False,
  'limits':['Source fresh2527a10=0 branch with tutorial AWLD3/3/1. No original Android device/residency assertion.',
   'Index/sampler/macro differences are not automatically visible pixel errors; mask weights/filtering and actual textures must be compared.']}


if __name__=='__main__':
 from analyze_native_resources import NativeImage
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 out=local_output(a.output)
 if out.exists():raise ValueError('Preserve previous audit evidence')
 r=analyze(NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes()),a.runtime);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r['counts']))
