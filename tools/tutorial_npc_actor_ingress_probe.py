"""Two original Creature instances in one native manager, with no ready node.

Messages are explicit CPU controls. Native registry identity and per-object
updates are verified without making an activity source, name substitution,
model completion or an approved quest.
"""
import argparse
import hashlib
import json
from pathlib import Path
from tutorial_npc_admission_probe import SO,ROOT,RAW,digest,json_write,private_path

AREA=RAW/'tutorial-npc-actor-ingress-20261115'


def probe_type():
    from tutorial_quest_creature_probe import native_probe_type
    from tutorial_npc_inventory import selected_names,NAME_TABLE
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE
    from unicorn import UC_HOOK_CODE
    Base=native_probe_type()
    class P(Base):
        def __init__(self,image):
            self.name_active=False;self.name_requests=[]
            self.name_frontier=None;super().__init__(image)
            appearance=next(v for v in self.table_by_handle.values()if v[0]=='creature_appearance')[2]
            wanted={appearance[k]['name']for k in (750,970,971,747)}
            self.name_values,self.name_source=selected_names(Sources(DEFAULT_SOURCE).read(NAME_TABLE),wanted)
            for at in (0xe81bbc,0x3e4710):
                self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=at,end=at)
        def hook(self,uc,at,size,data):
            if self.name_active and at==0xe81bbc:
                k=self.get('W0')
                if k not in self.name_values:raise ValueError('Requested original localized Creature name missing')
                raw=self.name_values[k].encode();dst=self.get('X1')
                self.name_requests.append({'entry':'0xe81bbc','textId':k,'localeArgument':self.get('W2'),
                    'sourceRawText':self.name_values[k],'hostOriginalTableProvider':True})
                uc.mem_write(dst,raw+b'\0');self.set('W0',1);self.set('PC',self.get('X30'));return
            if self.name_active and at==0x3e4710:
                self.name_frontier={'entry':'0x3e4710','inputText':self.cstr(self.r(self.get('X0'),'Q')[0]).decode(),
                    'nameSubstitutionExecuted':False,'nativeNamePublished':False}
                self.set('PC',self.EXIT);return
            return super().hook(uc,at,size,data)
        def registry_actor(self,guid):
            return self.call(0x9d99c0,{'X0':self.creature_manager,'X1':guid})
        def ingest_control(self,raw):
            before_initializers=len(self.init_calls);parsed=self.parse_creature_packet(raw)
            guid=self.r(self.parsed_creature+0x10,'Q')[0];previous=self.registry_actor(guid)
            self.creature_actor=previous or None
            snapshot=self.consume_creature_packet(update=bool(previous))
            actual=self.registry_actor(guid)
            if not actual or actual!=self.creature_actor:raise ValueError('Original manager registration differs from initialized object')
            gates=self.qualify_and_emit_creature();location=self.r(self.parsed_creature+0x28,'Q')[0]
            def vec(offset):return list(self.r(self.r(location+offset,'Q')[0]+0x10,'3f'))
            def wrapper(at):
                w=self.r(at,'Q')[0]
                return {'exists':bool(w),'nodeExists':bool(self.r(w+8,'Q')[0])if w else False,'visibility14':self.r(w+0x14,'B')[0]if w else None}
            native={'actualGuid':str(guid),'v18Key':self.call(0xa67ba4,{'X0':actual}),'kind0':snapshot['kind'],
                'c1':snapshot['originalC1'],'actor291':self.r(actual+0x291,'B')[0],
                'secondarySelected':bool(self.r(actual+0x4c,'B')[0]),'isLocalHero':actual==self.ui_hero,
                'attrs240':snapshot['property240'],'primary':wrapper(actual+0x38),'secondary':wrapper(actual+0x40),
                'interactionMask':gates['originalMask'],'selectedDisplay':snapshot['selectedDisplay'],
                'questStatus':snapshot['questStatus'],'questType':snapshot['questType']}
            owner={'parserAccepted':parsed['originalParserAccepted'],'afterObjectManager':{
                'guid':str(guid),'entry':snapshot['entry'],'nativeRegistryPresent':actual==self.registry_actor(guid),
                'location':{'mapId':self.r(location+0x28,'I')[0],'position':vec(0x10),'direction':vec(0x18)},'native':native}}
            return {'ownerSnapshot':owner,'parser':parsed,'nativeActorPointer':actual,'existingPointerBefore':previous,
                'initializerCountBefore':before_initializers,'initializerCountAfter':len(self.init_calls),
                'snapshot':snapshot,'gates':gates,'nativeActorCount':self.r(self.creature_manager+0x30,'Q')[0]}
        def snapshot_at(self,actor):
            self.creature_actor=actor;s=self.snapshot_creature()
            s['actorBytesSHA256']=hashlib.sha256(bytes(self.uc.mem_read(actor,0xf30))).hexdigest()
            s['propertiesPointer']=self.r(actor+0x18,'Q')[0]
            s['property80DisplayInput']=self.call(0xa996a0,{'X0':s['propertiesPointer']+0x280})
            s['nativeNameTextAt210']=self.cstr(self.r(actor+0x210,'Q')[0]).decode()
            s['nativeNameRelatedTextAtD50']=self.cstr(self.r(actor+0xd50,'Q')[0]).decode()
            return s
        def name_frontier_control(self,actor):
            self.name_active=True;self.name_frontier=None;self.name_requests=[]
            try:self.call(0x9eaf20,{'X0':actor})
            finally:self.name_active=False
            return {'nativeGetter':'0x9eaf20','nativeVtableSlot':'0x390','sourceRequests':list(self.name_requests),
                'firstMissingConsumer':self.name_frontier,
                'actualNameAfter':self.cstr(self.r(actor+0x210,'Q')[0]).decode(),
                'originalNameFullyObserved':self.name_frontier is None}
    return P


def run():
    from analyze_native_resources import NativeImage
    from tutorial_quest_creature_probe import packet_fixture
    image=NativeImage(SO.read_bytes());p=probe_type()(image)
    a={'guid':0x40a00001001,'entry':750,'position':(1,2,3),'direction':(0,0,1)}
    b={'guid':0x40a00001002,'entry':970,'position':(4,5,6),'direction':(1,0,0)}
    created_a=p.ingest_control(packet_fixture(**a));created_b=p.ingest_control(packet_fixture(**b))
    ap,bp=created_a['nativeActorPointer'],created_b['nativeActorPointer']
    b_before=p.snapshot_at(bp)
    updated_a=p.ingest_control(packet_fixture(**{**a,'entry':747},quest_status=6,quest_type=1,interactives=[[202,1,1,99,True]]))
    b_after=p.snapshot_at(bp);a_after=p.snapshot_at(ap)
    names=[p.name_frontier_control(ap),p.name_frontier_control(bp)]
    a_after_name=p.snapshot_at(ap);b_after_name=p.snapshot_at(bp)
    omitted_a=p.ingest_control(packet_fixture(**a))
    b_final=p.snapshot_at(bp)
    descriptor={name:row for name,row in p.descriptor_proofs.items()}
    functions={}
    for at in (0x9d99c0,0x9eaf20,0x9ea7cc,0x9dd2c4,0x9dd728):
        meta,asm=image.routine(at);functions[hex(at)]={**meta,'sha256':hashlib.sha256(image.read(at,meta['size'])).hexdigest()}
        json_write(AREA/(hex(at)+'-instructions.json'),{'metadata':functions[hex(at)],'instructions':asm})
    return {'format':'oc2-npc-original-two-actor-ingress-v1','library':digest(SO),
        'explicitPacketControls':{'A':a,'B':b},'createdA':created_a,'createdB':created_b,
        'updatedA':updated_a,'omittedA':omitted_a,'AAfterUpdate':a_after,'BBeforeAUpdate':b_before,
        'BAfterAUpdate':b_after,'AFollowingNameCall':a_after_name,'BFollowingNameCall':b_after_name,'BFinal':b_final,
        'originalFunctions':functions,'nameConsumers':names,'nativeLocaleSourceObserved':False,'nameSource':p.name_source,'descriptorProofs':descriptor,
        'registryReads':{'originalLookup':'0x9d99c0','nativeActorCount':p.r(p.creature_manager+0x30,'Q')[0],
            'lookupA':p.registry_actor(a['guid']),'lookupB':p.registry_actor(b['guid']),'lookupUnknown':p.registry_actor(0x40a00009999)},
        'sourceServerMessagesObserved':False,'originalAndroidModelCompleted':False,'wrapperNodeInserted':False,
        'legacyMeshSuccessEnabled':False,'savesAccessed':False,'packetsSent':False,
        'boundaries':['Explicit packet GUID/location/entry/status/interactives are isolated controls, not original server activity.',
            'Same native manager/parser/factory/register/update paths execute twice; no per-NPC miniature world or reused object is substituted.',
            'Original name getter9eaf20/9ea7cc executes through source table provider to3e4710; text substitution has not executed and no name is published.',
            '9ddb9c is recorded, not executed here; existing static evidence identifies sound metadata, not wrapper/node production.',
            'Original model/frame/selection gates remain false without a real wrapper/node; no EGL/context/GL success is supplied.']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=private_path(a.output)
    if out.exists():p.error('Preserve prior evidence')
    json_write(out,run());print(json.dumps({'output':str(out),'activityProvided':False}))
