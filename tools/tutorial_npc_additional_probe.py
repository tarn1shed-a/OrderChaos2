"""Bounded original single-model selection for Tutorial entries747 and970.

Reuses the frozen750 table/string fixtures read-only. Model construction,
resource success, weapon attachment and activity messages remain boundaries.
"""
import argparse
import hashlib
import json
from pathlib import Path

from tutorial_npc_native_probe import TutorialNPCProbe
from tutorial_npc_inventory import audit
from tutorial_map_geometry import local_output
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from skill_attachments import decode_ftable

ENTRIES=(747,970)
FORMAT='oc2-tutorial-npc-additional-native-v1'


class AdditionalNPCProbe(TutorialNPCProbe):
    def __init__(self,image,sources):
        super().__init__(image,sources)
        from unicorn import UC_HOOK_CODE
        for at in [0x9d5104,0x9d54dc,0x9d89b8]:
            self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=at,end=at)
        self.additional_mode=None

    def hook(self,uc,at,size,data):
        if at==0x9d5104 and self.additional_mode=='single':
            row=self.get('X2')
            self.single_request={'modelId':self.r(row,'I')[0],
                'modelFlags':self.r(row+4,'I')[0],
                'path':self.cstr(self.r(row+8,'Q')[0]).decode(),
                'animationRequest':self.cstr(self.get('X5')).decode(),
                'part37LoopReached':False,'modelLoaderExecuted':False}
            self.set('X0',0)
        elif at==0x9d54dc and self.additional_mode=='single':
            self.weapon_requests.append({'mainHand':self.get('W1'),'offHand':self.get('W2'),
                'arg3':self.get('W3'),'resourceAndAttachmentExecuted':False})
        elif at==0x9d54dc and self.additional_mode=='weapon-pair':
            return # Execute the original weapon pair classifier.
        elif at==0x9d89b8 and self.additional_mode=='weapon-pair':
            self.weapon_pairs.append({'itemKey':self.get('W1'),'arg2':self.get('W2'),
                'arg3':self.get('W3'),'partAttachmentExecuted':False})
        elif at in [0x9d5104,0x9d54dc,0x9d89b8]:
            return super().hook(uc,at,size,data)
        else:return super().hook(uc,at,size,data)
        self.set('PC',self.get('X30'))

    def single_model_request(self,display):
        owner,holder=self.alloc(256),self.alloc(8)
        self.w(owner+0x40,'Q',holder)
        self.single_request=None;self.weapon_requests=[];self.lookup_calls=[]
        self.additional_mode='single'
        try:self.call(0x9d40cc,{'X0':owner,'W1':display,'X4':self.cpp_string(b'idle')})
        finally:self.additional_mode=None
        if self.single_request is None:raise ValueError('Original single model branch not reached')
        return {'request':self.single_request,'weapons':list(self.weapon_requests),
            'tableLookups':list(self.lookup_calls),'explicitNoActorOwner':True,
            'modelHolderIsEmptyFixture':True}

    def weapon_pair(self,main_hand,off_hand,arg3):
        self.weapon_pairs=[];self.lookup_calls=[];self.additional_mode='weapon-pair'
        try:self.call(0x9d54dc,{'X0':self.alloc(256),'W1':main_hand,'W2':off_hand,'W3':arg3})
        finally:self.additional_mode=None
        return {'calls':list(self.weapon_pairs),'tableLookups':list(self.lookup_calls),
                'mountOrPostureDecision':None,'resourceAndAttachmentExecuted':False}


def recover(image,source=DEFAULT_SOURCE):
    sources=Sources(source);probe=AdditionalNPCProbe(image,sources)
    inventory=audit(source);selected=[]
    objectives=decode_ftable(sources.read('tables/quest_objective.tbl'),'id')['rows']
    logic=decode_ftable(sources.read('tables/quest_objective_logic.tbl'),'id')['rows']
    for entry in ENTRIES:
        original=next(r for r in inventory['creatures']if r['entry']==entry)
        display=original['appearance']['creaturedisplayinfo_id']
        request=probe.single_model_request(display)
        references=[]
        for target in logic:
            if target['quest_id']!=202 or target['entry']!=entry:continue
            matches=[o for o in objectives if o['quest_id']==202 and o['obj_idx']==target['obj_idx']]
            if len(matches)!=1:raise ValueError('Original objective join is missing or ambiguous')
            references.append({'logic':target,'objective':matches[0]})
        if len(references)!=1:raise ValueError('Expected one original tutorial objective relation')
        selected.append({'entry':entry,'name':original['name'],'original':original,
            'questObjectiveReferences':references,
            'entrySelection':probe.entry_selection(entry),
            'singleModel':request,'defaultIdle':probe.idle(entry,display),
            'weaponPairRequests':[probe.weapon_pair(r['mainHand'],r['offHand'],r['arg3'])for r in request['weapons']],
            'liveGUID':None,'worldPlacement':None,'questAvailability':None,'activitySpawn':None})
    return {'format':FORMAT,'nativeSHA256':hashlib.sha256(image.data).hexdigest(),
        'entries':selected,'sourceProofs':sources.proofs,
        'scope':'Explicit original table/default/no-owner selection fixtures; native instruction execution through request boundaries only.',
        'productionChanged':False,'savesReadOrWritten':False}


if __name__=='__main__':
    from analyze_native_resources import NativeImage
    root=Path(__file__).resolve().parents[1];cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--native',type=Path,default=root/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so')
    cli.add_argument('--source',type=Path,default=DEFAULT_SOURCE);cli.add_argument('--output',type=Path,required=True)
    args=cli.parse_args();output=local_output(args.output)
    if output.exists():cli.error('Preserve existing evidence')
    report=recover(NativeImage(args.native.read_bytes()),args.source)
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'output':str(output),'entries':list(ENTRIES),'productionChanged':False}))
