"""Map5 original resource families and bounded983/984 default part requests.

Source rows, archive existence checks and explicit no-actor fixtures are kept
separate from activity messages, GUIDs, appearance overrides and quest state.
"""
import argparse
import hashlib
import json
from pathlib import Path

from tutorial_npc_weapon_probe import WeaponProbe
from tutorial_npc_additional_probe import AdditionalNPCProbe
from tutorial_npc_native_probe import TutorialNPCVisibilityProbe
from tutorial_npc_inventory import audit
from tutorial_map_geometry import local_output
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from skill_attachments import decode_ftable

ROOT=Path(__file__).resolve().parents[1]
FORMAT='oc2-tutorial-npc-catalog-native-v1'
BASE='model/npc/character/human/male/oc2_human_m_body_01.bdae'


class CatalogProbe(WeaponProbe):
    EXISTS=WeaponProbe.EXIT+0xea0

    def __init__(self,image,sources):
        super().__init__(image,sources)
        from unicorn import UC_HOOK_CODE
        self.sources=sources;self.exists_queries=[]
        self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=self.EXISTS,end=self.EXISTS)
        slot,app,fs,vt=self.alloc(8),self.alloc(0x100),self.alloc(0x100),self.alloc(0x100)
        self.w(0x2505078,'Q',slot);self.w(slot,'Q',app);self.w(app+0x50,'Q',fs);self.w(fs,'Q',vt);self.w(vt+0xd8,'Q',self.EXISTS)
        for at,size,digest in[(0x9d8570,832,'24355e06585db42ecad5cfb467debad98d0e094c7d997cd306dc8c5d67127d84')]:
            self.feature_fingerprint={'address':hex(at),'bytes':size,'sha256':hashlib.sha256(image.read(at,size)).hexdigest()}
            if self.feature_fingerprint['sha256']!=digest:raise ValueError('Original source feature branch changed')

    def hook(self,uc,at,size,data):
        if at==0x9d40cc and self.mode=='parts':return
        if self.imports.get(at)=='sprintf'and self.cstr(self.get('X1'))==b'texture/%s.tga':
            raw=b'texture/'+self.cstr(self.get('X2'))+b'.tga'
            uc.mem_write(self.get('X0'),raw+b'\0');self.set('W0',len(raw));self.set('PC',self.get('X30'));return
        if at==self.EXISTS:
            path=self.cstr(self.get('X1')).decode();n=len(self.sources.candidates(path));self.exists_queries.append({'path':path,'sourceCandidates':n})
            if n>1:raise ValueError('Ambiguous original feature lookup')
            if n:self.sources.read(path)
            self.set('W0',int(n==1));self.set('PC',self.get('X30'));return
        if at==0x32376c and self.weapon_mode=='resource':
            self.resource_request={'slot':self.get('W1'),'path':None,'action':'clear-original-slot','resourceLoaderExecuted':False}
            self.set('PC',self.EXIT);return
        return super().hook(uc,at,size,data)

    def part_resource(self,slot,value,face):
        owner,holder,model,vt=self.alloc(256),self.alloc(8),self.alloc(256),self.alloc(64)
        self.w(owner+0x40,'Q',holder);self.w(holder,'Q',model);self.w(model,'Q',vt);self.w(vt+0x10,'Q',self.MODEL_KIND)
        self.w(model+0x90,'Q',self.cpp_string(BASE.encode()));self.w(owner+0x4c,'I',face)
        self.weapon_mode='resource';self.resource_request=None;self.lookup_calls=[];self.exists_queries=[]
        try:self.call(0x9d64e8,{'X0':owner,'W1':slot,'W2':value,'W3':1})
        finally:self.weapon_mode=None
        if self.resource_request is None:raise ValueError('Original part did not reach a bounded resource/clear boundary')
        path=self.resource_request.get('path');candidates=len(self.sources.candidates(path))if path else 0
        if candidates>1:raise ValueError('Ambiguous original requested part resource')
        if path and candidates==1:self.sources.read(path)
        return {**self.resource_request,'sourceResourceCandidates':candidates,'inputValue':value,'explicitCurrentFace':face,'tableLookups':self.lookup_calls,
            'sourceExistsQueries':self.exists_queries,'noActorOwner':True,'explicitLoadedModelKind':3,
            'sourceModelPathFixture':BASE,'forcePartParameter':1}


class CatalogVisibilityProbe(TutorialNPCVisibilityProbe):
    def bind_original_parts(self,names):
        mapping=self.bind_source_names(names)
        # Complete the original initial body-to-fallback copy for0..8. This
        # matters when an original zero-feature request restores a base node.
        self.fragment(0x3203e8,0x32047c,{'X19':self.model})
        return mapping

    def feature_request(self,slot,name):
        node=self.node(name)if name else 0;holder=self.alloc(8);self.w(holder,'Q',node)
        if not node and self.r(self.model+0x158+slot*0x38,'Q')[0]==0:
            self.call(0x32165c,{'X0':self.model,'W1':slot,'X2':holder})
        else:self.fragment(0x32165c,0x321abc,{'X0':self.model,'W1':slot,'X2':holder})
        self.part_nodes[slot]=self.r(self.model+0xbf0+slot*8,'Q')[0]
        return {'slot':slot,'sourcePartName':self.names.get(self.part_nodes[slot]),'baseFallback':not bool(name)}


def recover(image,source=DEFAULT_SOURCE):
    sources=Sources(source);inventory=audit(source);probe=CatalogProbe(image,sources);single=AdditionalNPCProbe(image,sources)
    logic=decode_ftable(sources.read('tables/quest_objective_logic.tbl'),'id')['rows'];objectives=decode_ftable(sources.read('tables/quest_objective.tbl'),'id')['rows']
    entries=[];families={}
    for original in inventory['creatures']:
        entry=original['entry'];display_id=original['appearance']['creaturedisplayinfo_id']
        selected=next(c for c in original['appearanceCandidates']if c['display']['ID']==display_id);model=selected['model']
        family=families.setdefault(model['ID'],{'model':model,'entries':[],'sourcePath':model['ModelPath']});family['entries'].append(entry)
        refs=[]
        for target in logic:
            if target['quest_id']!=202 or target['entry']!=entry:continue
            matches=[o for o in objectives if o['quest_id']==202 and o['obj_idx']==target['obj_idx']]
            if len(matches)!=1:raise ValueError('Original quest objective join is ambiguous')
            refs.append({'logic':target,'objective':matches[0]})
        row={'entry':entry,'name':original['name'],'original':original,'defaultCandidate':selected,
            'defaultEntrySelection':probe.entry_selection(entry),'defaultIdle':probe.idle(entry,display_id),
            'quest202ObjectiveReferences':refs,'quest202Start':202 in original['questStartReferences'],
            'runtimeGUID':None,'activityAppearance':None,'activitySpawn':None,'questAvailability':None}
        script=original['prototype']['script']
        row['sourceScriptKey']=script
        row['scriptMemberBasenameMatches']=[path for path in sources.lookup if script and Path(path).stem==script.lower()]
        row['scriptImplementationRecovered']=False
        if model['Flags']&1:row['singleModel']=single.single_model_request(display_id)
        else:
            parts=probe.parts(display_id);row['parts']=parts;requests=[]
            # Slots7/8 have no source feature-name string in this native table.
            # Retain their raw inputs rather than inventing filenames/parts.
            if any(parts['slots'][i]for i in[7,8]):raise ValueError('Nonzero unnamed feature slot requires separate original recovery')
            for slot in range(7):requests.append(probe.part_resource(slot,parts['slots'][slot],parts['slots'][0]))
            for slot in range(9,15):
                if parts['slots'][slot]:requests.append(probe.part_resource(slot,parts['slots'][slot],parts['slots'][0]))
            row['resourceRequests']=requests
        entries.append(row)
    if {key:len(value['entries'])for key,value in families.items()}!={1:15,52:1,53:1,54:3,55:1,58:1}:
        raise ValueError('Original map5 resource-family scope changed')
    return {'format':FORMAT,'entries':entries,'families':list(families.values()),'sourceProofs':sources.proofs,
        'inventorySourceProofs':inventory['sourceProofs'],'nameProof':inventory['nameProof'],
        'summary':inventory['summary'],'featureBranchFingerprint':probe.feature_fingerprint,
        'limits':['Source type54 has mark paths and original names containing Trigger; no ordinary actor is created.',
            'Default no-actor part requests and source file existence are not asynchronous load completion or current activity appearance.',
            'Raw zero slots7/8 are preserved without inventing names; covered source body geometry remains separately checked.',
            'No GUID, world placement, task marker, acceptance, save or production changes.'],
        'savesReadOrWritten':False,'productionChanged':False}


if __name__=='__main__':
    from analyze_native_resources import NativeImage
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--native',type=Path,default=ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so')
    cli.add_argument('--source',type=Path,default=DEFAULT_SOURCE);cli.add_argument('--output',type=Path,required=True);args=cli.parse_args();output=local_output(args.output)
    if output.exists():cli.error('Existing catalog evidence is preserved')
    result=recover(NativeImage(args.native.read_bytes()),args.source);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'output':str(output),'entries':len(result['entries']),'families':len(result['families'])}))
