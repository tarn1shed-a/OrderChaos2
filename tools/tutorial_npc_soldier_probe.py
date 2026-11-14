"""Original749/1632 defaults and explicit null-descriptor recording correction.

Source null override pointers are retained as null. They are never decoded by
reading ELF address0 and are not confused with a genuine empty C string.
"""
import argparse,hashlib,json
from pathlib import Path
from tutorial_npc_catalog_probe import CatalogProbe,BASE
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from tutorial_map_geometry import local_output
from tutorial_npc_inventory import audit
from skill_attachments import decode_ftable

ROOT=Path(__file__).resolve().parents[1]
FORMAT='oc2-npc-soldier-native-v1'


def strict_original_skin(reader,data,*,external_nodes=None):
    # Keep every old structural/rest/weight validity check, then retain the
    # literal source float weights instead of the older reader's v/sum step.
    from bdae_skin import recover_skin
    rig=recover_skin(reader,data,external_nodes=external_nodes)
    count,table=reader.section(188)
    records={reader.string(reader.q(table+i*24+8)):table+i*24 for i in range(count)}
    for skin in rig['skins']:
        record=records[skin['name']];wrapper=reader.rel(record+16);prefix=reader.u(wrapper+4)&0xffffff
        body=reader.q(wrapper+8)+(prefix-1)*8;maximum=reader.u(body+176);at=reader.q(body+104)
        raw=[];vertices=data['meshes'][skin['mesh']]['vertexCount']
        for index in range(vertices):raw.extend(list(reader.unpack(str(maximum)+'f',at+index*(maximum+1)*4+4))+[0.]*(4-maximum))
        if len(raw)!=len(skin['skinWeights']):raise ValueError('Literal source weight span differs from verified skin')
        skin['skinWeights']=raw;skin['verification']['normalizationApplied']=False
        skin['verification']['sourceFloatWeightsRetainedAfterStrictValidation']=True
    return rig


class SoldierProbe(CatalogProbe):
    def hook(self,uc,at,size,data):
        if at==0x323b44 and self.weapon_mode=='resource':
            descriptor=self.get('X2');pointers=[self.r(descriptor+i*8,'Q')[0]for i in range(1,4)]
            nullable=[self.cstr(p).decode()if p else None for p in pointers]
            super().hook(uc,at,size,data)
            self.resource_request.update({'textureOverrides':nullable,'originalOverridePointers':pointers,
                'overrideNullPointers':[p==0 for p in pointers],'nullPointerDecodedAsString':False})
            return
        return super().hook(uc,at,size,data)


def recover(image,source=DEFAULT_SOURCE):
    sources=Sources(source);probe=SoldierProbe(image,sources);entries=[];corrections=[];inventory=audit(source)
    originals={r['entry']:r for r in inventory['creatures']}
    quest_logic=decode_ftable(sources.read('tables/quest_objective_logic.tbl'),'id')['rows']
    if any(r['quest_id']==202 and r['entry']in[749,1632]for r in quest_logic):raise ValueError('Selected soldier202 relationship scope changed')
    for entry,display in[(749,740),(1632,1602),(983,960),(984,961)]:
        selection=probe.entry_selection(entry)
        if selection['result']['selectedDisplayAtD60']!=display:raise ValueError('Original selected soldier/correction display differs')
        parts=probe.parts(display);requests=[]
        for slot in range(7):requests.append(probe.part_resource(slot,parts['slots'][slot],parts['slots'][0]))
        for slot in range(9,15):
            if parts['slots'][slot]:requests.append(probe.part_resource(slot,parts['slots'][slot],parts['slots'][0]))
        original=originals[entry]
        candidate=next(c for c in original['appearanceCandidates']if c['display']['ID']==display)
        result={'entry':entry,'name':original['name'],'original':original,'defaultCandidate':candidate,
          'quest202Start':202 in original['questStartReferences'],'quest202ObjectiveReferences':[],
          'sourceScriptKey':original['prototype']['script'],'explicitDefaultDisplay':display,'entrySelection':selection,'parts':parts,'resourceRequests':requests,
          'defaultIdle':probe.idle(entry,display),'actualGUID':None,'actualAppearanceOverrides':None,'questAvailability':None}
        if entry in[749,1632]:entries.append(result)
        else:
            corrections.append({'entry':entry,'featureDescriptors':[r for r in requests if r['slot']<7],
              'correction':'Prior catalog descriptor recorder read ELF address0 for null texture override pointers. These fields are null, not source ELF-header strings.',
              'priorRenderedFeatureMaterialDidNotConsumeDescriptorOverrides':True,'oldFilesChanged':False})
    return {'format':FORMAT,'entries':entries,'families':[{'model':entries[0]['defaultCandidate']['model'],'entries':[749,1632]}],
       'catalogFeatureCorrection':corrections,'sourceProofs':sources.proofs,'inventorySourceProofs':inventory['sourceProofs'],
       'nativeSHA256':hashlib.sha256(image.data).hexdigest(),'actualActorsOrOverridesObserved':False,'productionChanged':False,'savesReadOrWritten':False}


if __name__=='__main__':
    from analyze_native_resources import NativeImage
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--native',type=Path,default=ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so')
    cli.add_argument('--source',type=Path,default=DEFAULT_SOURCE);cli.add_argument('--output',type=Path,required=True);args=cli.parse_args();output=local_output(args.output)
    if output.exists():cli.error('Existing soldier/correction evidence stays preserved')
    result=recover(NativeImage(args.native.read_bytes()),args.source);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'output':str(output),'entries':len(result['entries']),'corrections':len(result['catalogFeatureCorrection'])}))
