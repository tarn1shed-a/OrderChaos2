"""Original material-group representative and full35127c transfer evidence.

Original group order, representative selection and copy instructions execute.
The copy probe uses explicit opaque refcounted handles and sampler slot bytes;
it is not original GPU resource creation or observed Android sampler numbering.
"""
import argparse,copy,hashlib,json
from pathlib import Path
from selection_scene_candidate import ROOT,local_output
from selection_scene_water_floor_native import SelectionWaterFloorNative
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
sha=lambda b:hashlib.sha256(b).hexdigest()
FORMAT='oc2-selection-water-floor-group-copy-evidence-v1'


def uniform_names(image):
 n=SelectionWaterFloorNative(image);e=n.e
 names=[e.cstr(e.r(0x240dec0+i*8,'Q')[0]).decode('ascii')for i in range(5)]
 if names!=['texture1','texture2','texture3','texture4','texture5']:raise ValueError('Original351690 layer uniform table differs')
 return {'table':'0x240dec0','names':names,'consumer':'0x351690 ->14006c4 name lookup -> material texture reference set',
  'sourceTableRead':True,'full351690OrGPUExecuted':False}


def controlled_copy(image):
 n=SelectionWaterFloorNative(image);e=n.e;source=e.alloc(0xa8);target=e.alloc(0xa8);effect=e.alloc(0x40);table=e.alloc(0x50)
 e.w(effect,'I',100);e.w(table+8,'I',100);e.w(source+0x68,'Q',effect);e.w(source+0x88,'Q',table)
 slots=[4,19,82,1,254];e.w(source+0x9c,'5B',*slots);e.w(target+0x9c,'5B',*([203]*5));e.w(target+0x50,'5h',5,6,7,8,9)
 before=bytes(e.uc.mem_read(target,0xa8));e.call(0x35127c,{'X0':target,'X1':source});after=bytes(e.uc.mem_read(target,0xa8))
 allowed=set(range(0x68,0x70))|set(range(0x88,0x90))|set(range(0x9c,0xa1))
 if any(a!=b and i not in allowed for i,(a,b)in enumerate(zip(before,after))):raise ValueError('Original material copy changed unexpected member data')
 if e.r(target+0x68,'Q')[0]!=effect or e.r(target+0x88,'Q')[0]!=table or list(e.r(target+0x9c,'5B'))!=slots:raise ValueError('Original copy did not transfer actual bindings')
 if e.r(effect,'I')[0]!=101 or e.r(table+8,'I')[0]!=101 or list(e.r(target+0x50,'5h'))!=[5,6,7,8,9]:raise ValueError('Original copy changed index fields or ownership differs')
 return {'fullOriginal35127cExecuted':True,'effectOffset':'0x68','colorTableOffset':'0x88','samplerByteOffsets':['0x9c','0x9d','0x9e','0x9f','0xa0'],
  'controlledSamplerBytes':slots,'copiedSamplerBytes':list(e.r(target+0x9c,'5B')),'effectRefcount':[100,101],'tableRefcount':[100,101],
  'memberIndexFieldsUnchanged':True,'resourceOrGPUCreated':False,'opaqueHandlesAndSamplerNumbersAreControlledCPUInputs':True,'actualAndroidSamplerSlotsObserved':False}


def analyze(image):
 if sha(image.data)!='77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4':raise ValueError('Original native image differs')
 source=Sources(DEFAULT_SOURCE);base=ROOT/'analysis/raw/selection-scene-water-20261115/floor-v4/assets/source-selection-water-floor/overlay.json';p=json.loads(base.read_text());native=SelectionWaterFloorNative(image);tiles=[];fixes=[];checked=0
 for row in p['tiles']:
  raw=source.read(row['source'])
  if sha(raw)!=row['sourceSHA256']:raise ValueError('Frozen original TRN differs')
  native.read(raw);layers=native.layers(source,row['tile']);e=native.e;count=e.r(native.tile+0xb0,'I')[0];order=list(e.r(e.r(native.tile+0xa0,'Q')[0],'64B'));offsets=list(e.r(e.r(native.tile+0xa8,'Q')[0],str(count+1)+'B'))
  if sorted(order)!=list(range(64))or offsets[0]!=0 or offsets[-1]!=64:raise ValueError('Original group lists differ')
  reps=[];changes=[]
  for g in range(count):
   e.set('X19',native.tile);e.set('W24',offsets[g]);e.set('X25',0xa8);native.fragment(0x35650c,0x356524)
   rep=e.get('W27');chunks=e.r(native.tile+0x80,'Q')[0]
   if rep!=order[offsets[g]]or e.get('X0')!=chunks+rep*0xa8:raise ValueError('Original3563dc representative selection differs')
   reps.append({'group':g,'representativeIndex':rep,'representativeChunk':[rep%8,rep//8],'members':order[offsets[g]:offsets[g+1]],'source35650cExecuted':True})
  for old in row['chunks']:
   j=old['chunk'][1]*8+old['chunk'][0];member=layers['rows'][j];rep=reps[member['sourceGroup']]['representativeIndex'];representative=layers['rows'][rep]
   desc=native.descriptor(j);rd=native.descriptor(rep);checked+=1
   if desc!=rd:raise ValueError('Group representative water uniforms/color table differ; cannot replace just samplers')
   if member['groupedIndices']!=old['groupedIndices']or member['textureLayerMask']!=old['textureLayerMask']:raise ValueError('Frozen v4 member result differs')
   if representative['groupedIndices']!=old['groupedIndices']or representative['textureLayerMask']!=old['textureLayerMask']:
    # Raw source TRN material table; not filenames guessed from the water name.
    from terrain_materials import tile_materials
    paths=tile_materials(raw)['textures'];vector=representative['groupedIndices']
    fix={'tile':row['tile'],'chunk':old['chunk'],'sourceGroup':member['sourceGroup'],'representativeChunk':[rep%8,rep//8],
     'oldMemberIndices':old['groupedIndices'],'oldMemberMacro':old['textureLayerMask'],'materialIndices':vector,'materialMacro':representative['textureLayerMask'],
     'sourceSamplerPaths':[paths[i]if i>=0 else None for i in vector],'memberWaterDescriptor':desc,'representativeWaterDescriptor':rd,
     'source':row['source'],'sourceSHA256':sha(raw),'source35650cExecuted':True,'copyFields':['effect@68','colorTable@88','samplerBytes@9c..a0'],'memberIndexFieldsAreNotCopied':True}
    fixes.append(fix);changes.append(fix)
  tiles.append({'tile':row['tile'],'sourceSHA256':sha(raw),'groupOrder':order,'groupOffsets':offsets,'representatives':reps,'changedWetMembers':changes})
 expected={(-39,-3,3,2),(-39,-3,4,2),(-40,-2,0,1)}
 if {(*r['tile'],*r['chunk'])for r in fixes}!=expected or checked!=152:raise ValueError('Unexpected frozen v4 correction population')
 routines={}
 for a in(0x355f28,0x3563dc,0x35127c,0x3509c4,0x351690,0x350f6c):
  m,_=image.routine(a);routines[hex(a)]={**m,'sha256':sha(image.read(int(m['start'],16),m['size']))}
 return {'format':FORMAT,'world':'selection','mapId':7,'sourceRegion':211,'floorV4SHA256':sha(base.read_bytes()),'fixes':fixes,'tiles':tiles,'wetMembersChecked':checked,'representativeWaterUniformsAndColorTableEqual':True,
  'copyEvidence':controlled_copy(image),'nativeRoutines':routines,'sourceProofs':source.proofs,
  'sourceChain':'355f28 a0/a8 ->35650c representative ->3509c4 effect/350f6c water uniforms ->3566e8 five texture requests/351690 bindings ->356c28 full35127c transfer',
  'limits':['Full35127c controlled CPU transfer is not GPU creation or actual Android slot-number observation.',
   'Original source paths/final vector come from actual original group lists and TRN; representative water descriptors are equal for all152 wet members.',
   'Original Android resource completion, complete original frame/residency/LOD remain unproved.']}


def build(evidence,output):
 output=local_output(output)
 if output.exists():raise ValueError('Preserve all old floor payloads')
 base=ROOT/'analysis/raw/selection-scene-water-20261115/floor-v4/assets/source-selection-water-floor/overlay.json';old=base.read_bytes()
 if sha(old)!=evidence['floorV4SHA256']:raise ValueError('Frozen floor-v4 differs')
 p=copy.deepcopy(json.loads(old))
 for fix in evidence['fixes']:
  tile=next(t for t in p['tiles']if t['tile']==fix['tile']);c=next(c for c in tile['chunks']if c['chunk']==fix['chunk'])
  c['groupedIndices']=fix['materialIndices'];c['textureLayerMask']=fix['materialMacro']
 p.update(nativeGroupRepresentativeMaterials=True,priorFloorV4SHA256=sha(old),sourceMaterialCopyFields=['effect@68','colorTable@88','samplerBytes@9c..a0'],
  correctedMaterialGroups=[{'tile':r['tile'],'chunk':r['chunk'],'representativeChunk':r['representativeChunk']}for r in evidence['fixes']],
  groupCopyEvidenceSHA256=sha((json.dumps(evidence,ensure_ascii=False,indent=2)+'\n').encode()))
 dest=output/'assets/source-selection-water-floor-groups';dest.mkdir(parents=True);raw=(json.dumps(p,ensure_ascii=False,separators=(',',':'))+'\n').encode();(dest/'overlay.json').write_bytes(raw)
 (output/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
 audit={'format':FORMAT,'correctedWetMembers':3,'payloads':1,'bytes':len(raw),'overlaySHA256':sha(raw),'oldFloorV4Unchanged':base.read_bytes()==old,'factoryUnchanged':True,'sourceGeometryChanged':False,'sourceLightsChanged':False,'savesChanged':False}
 (output/'audit.json').write_text(json.dumps(audit,indent=2)+'\n');return audit


if __name__=='__main__':
 from analyze_native_resources import NativeImage
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(build(analyze(NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes())),a.output)))
