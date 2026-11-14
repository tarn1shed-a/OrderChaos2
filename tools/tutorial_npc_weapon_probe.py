"""Bounded original NPC weapon posture, resource and attachment execution.

Inputs are explicit review fixtures. Source table/string/scene interfaces are
host boundaries; no activity actor, model-ready callback or GPU is created.
"""
import argparse
import hashlib
import json
from pathlib import Path

from tutorial_npc_native_probe import TutorialNPCProbe, TutorialNPCVisibilityProbe
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from skill_attachments import decode_ftable
from tutorial_map_geometry import local_output

ROOT=Path(__file__).resolve().parents[1]
FORMAT='oc2-tutorial-npc-weapon-native-v1'
PINS={
    0x9d89b8:(1360,'cb1830d57f51bbdcfcbf3a572bc9b510210aad0b2e9f77a998dcdee63c53f145'),
    0x9d54dc:(304,'8e9184b8378975392b4a4712643a41bf52eee8c10ff2074583759234881b7aef'),
    0x91661c:(552,'008ec17bd091ece27410a17d4190725a73fd6fab782dee54c43efabea67334e3'),
    0x323b44:(5244,'9f84a5db86729084024efc2699b93af1c4b30ac2cd5762bf020db321430aac03'),
    0x3255a0:(1856,'512b66543900fc6104f40d20f4b4c94d4d0847a70028638084b052da561d9d97'),
    0x9e8d74:(352,'7a274c446cbcc2b442f4a01bf700ae8c379141dc4fdbfd5ab22b9842e52d44b0'),
    0x912124:(16,'3a90653185e5eb0e61c8e73ecc85b58bc210a87b8fabf369b4b545dbf1f559ef'),
}


def verify(image):
    for at,(size,digest)in PINS.items():
        if hashlib.sha256(image.read(at,size)).hexdigest()!=digest:
            raise ValueError('Original weapon routine changed')


class WeaponProbe(TutorialNPCProbe):
    MODEL_KIND=TutorialNPCProbe.EXIT+0xe80

    def __init__(self,image,sources):
        verify(image);super().__init__(image,sources)
        from unicorn import UC_HOOK_CODE
        self.weapon_mode=None
        for at,name in {0xc993a0:'itemdisplayinfo',0xc993c0:'itemmodeldata'}.items():
            parsed=decode_ftable(sources.read('tables/'+name+'.tbl'),'ID')
            handle,vt=self.alloc(32),self.alloc(32);self.w(handle,'Q',vt);self.w(vt+0x18,'Q',self.LOOKUP)
            self.table_handles[at]=handle
            self.table_by_handle[handle]=(name,parsed,{r['ID']:r for r in parsed['rows']})
            self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=at,end=at)
        for at in [self.MODEL_KIND,0x9d40cc,0x9d54dc,0x9d64e8,0x32376c,
                   0x3255a0,0x9163f4,0x323b44]:
            self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=at,end=at)

    def hook(self,uc,at,size,data):
        if at==self.MODEL_KIND:self.set('W0',3)
        elif at==0x91661c and self.weapon_mode=='posture':return
        elif at==0x9d54dc and self.weapon_mode=='slot':return
        elif at==0x9d64e8 and self.weapon_mode=='resource':return
        elif at==0x9d40cc and self.weapon_mode=='posture':
            self.model_requests.append({'display':self.get('W1'),'armedParameter':self.get('W5')})
        elif at==0x9d54dc and self.weapon_mode=='posture':
            self.posture_requests.append({'mainHand':self.get('W1'),'offHand':self.get('W2'),'armedParameter':self.get('W3')})
        elif at==0x9163f4 and self.weapon_mode=='posture':pass
        elif at==0x9d64e8 and self.weapon_mode=='slot':
            self.slot_requests.append({'slot':self.get('W1'),'itemKey':self.get('W2'),
                'arg3':self.get('W3'),'arg4':self.get('W4')})
            self.set('W0',0) # Part-resource continuation is a separate fixture.
        elif at==0x32376c and self.weapon_mode=='slot':self.removed_slots.append(self.get('W1'))
        elif at==0x3255a0 and self.weapon_mode=='slot':
            raise ValueError('Fresh fixture unexpectedly entered an existing-resource move')
        elif at==0x323b44 and self.weapon_mode=='resource':
            descriptor=self.get('X2')
            self.resource_request={'slot':self.get('W1'),'path':self.cstr(self.r(descriptor,'Q')[0]).decode(),
                'textureOverrides':[self.cstr(self.r(descriptor+8*i,'Q')[0]).decode()for i in range(1,4)],
                'positionAnchor':self.cstr(self.r(descriptor+64,'Q')[0]).decode()if self.r(descriptor+64,'Q')[0]else None,
                'itemKey':self.get('W3'),'raceSelector':self.get('W4'),'genderSelector':self.get('W5'),
                'resourceLoaderExecuted':False}
            self.set('PC',self.EXIT);return
        elif self.imports.get(at)=='strstr':
            a,b=self.cstr(self.get('X0')),self.cstr(self.get('X1'));index=a.find(b)
            self.set('X0',self.get('X0')+index if index>=0 else 0)
        elif self.imports.get(at)=='memcmp':
            length=self.get('X2');a,b=[bytes(uc.mem_read(self.get(reg),length))for reg in['X0','X1']]
            self.set('W0',((a>b)-(a<b))&0xffffffff)
        else:return super().hook(uc,at,size,data)
        self.set('PC',self.get('X30'))

    def row(self,name,key):
        for table,parsed,rows in self.table_by_handle.values():
            if table==name:return parsed,rows[key]
        raise ValueError('Unknown verified source table')

    def posture(self,display,kind,state_byte,*,main_override=0,off_override=0):
        actor,attrs=self.alloc(0x2000),self.alloc(0x1000)
        self.w(actor,'Q',0x24222b8);self.w(actor+0x18,'Q',attrs);self.w(actor+0x5a0,'B',state_byte)
        if self.r(0x24222b8+0x1e8,'Q')[0]!=0x912124:raise ValueError('Original Creature getter differs')
        for off,value in [(0,kind),(0x358,main_override),(0x368,off_override)]:
            self.call(0xa9995c,{'X0':attrs+off,'W1':value})
        parsed,row=self.row('creaturedisplayinfo',display);native_row=self.alloc(256)
        self.uc.mem_write(native_row,self.pack_row(parsed,row))
        self.model_requests=[];self.posture_requests=[];self.lookup_calls=[];self.weapon_mode='posture'
        try:self.call(0x91661c,{'X0':actor,'X1':actor+0x4e8,'X2':native_row})
        finally:self.weapon_mode=None
        return {'explicitDisplay':display,'explicitKindProperty0':kind,'explicitStateByte5a0':state_byte,
            'explicitMainOverride':main_override,'explicitOffOverride':off_override,
            'modelRequests':self.model_requests,'weaponRequests':self.posture_requests,
            'tableLookups':self.lookup_calls,'activityInputsObserved':False,
            'actualGetterExecuted':'912124 reads (actor+5a0)&6',
            'modelAndWeaponResourceExecuted':False}

    def slots(self,item,armed):
        owner,holder,model,vt=self.alloc(256),self.alloc(8),self.alloc(256),self.alloc(64)
        self.w(owner+0x40,'Q',holder);self.w(holder,'Q',model);self.w(model,'Q',vt)
        self.w(vt+0x10,'Q',self.MODEL_KIND)
        self.slot_requests=[];self.removed_slots=[];self.lookup_calls=[];self.weapon_mode='slot'
        try:self.call(0x9d54dc,{'X0':owner,'W1':item,'W2':0,'W3':armed})
        finally:self.weapon_mode=None
        return {'item':item,'explicitArmed':armed,'requests':self.slot_requests,'removedSlots':self.removed_slots,
            'tableLookups':self.lookup_calls,'explicitNoActorOwner':True,'explicitModelKind':3,
            'resourceLoaded':False,'mounted':False}

    def posture_event(self,display,kind,event,*,byte114=1,cached=0):
        actor,attrs,wrapper=self.alloc(0x2000),self.alloc(0x1000),self.alloc(0x100)
        self.w(actor+0x18,'Q',attrs);self.w(actor+0x114,'B',byte114)
        self.w(wrapper,'Q',actor);self.w(wrapper+0xbc,'i',cached)
        for off,value in[(0,kind),(0x280,display)]:self.call(0xa9995c,{'X0':attrs+off,'W1':value})
        extra_id=self.row('creaturedisplayinfo',display)[1]['ExtraDisplayInformation']
        parsed,extra=self.row('creaturedisplayinfoextra',extra_id);native_row=self.alloc(256)
        self.uc.mem_write(native_row,self.pack_row(parsed,extra))
        self.call(0x906c1c,{'X0':actor,'X1':native_row})
        self.model_requests=[];self.posture_requests=[];self.lookup_calls=[];self.weapon_mode='posture'
        try:self.call(0x9e8d74,{'X0':wrapper,'W1':event&0xffffffff})
        finally:self.weapon_mode=None
        return {'explicitDisplay':display,'explicitKindProperty0':kind,'explicitEvent':event,
            'explicitByte114':byte114,'explicitCachedEvent':cached,'cachedEventAfter':self.r(wrapper+0xbc,'i')[0],
            'originalCachedWeaponKeys':list(self.r(actor+0xb88,'I'))+list(self.r(actor+0xb90,'I')),
            'requests':self.posture_requests,'tableLookups':self.lookup_calls,
            'eventProducerOrActivityExecuted':False,'resourceLoaderExecuted':False}

    def resource(self,slot,item):
        owner,holder,model,vt=self.alloc(256),self.alloc(8),self.alloc(256),self.alloc(64)
        self.w(owner+0x40,'Q',holder);self.w(holder,'Q',model);self.w(model,'Q',vt);self.w(vt+0x10,'Q',self.MODEL_KIND)
        self.weapon_mode='resource';self.resource_request=None;self.lookup_calls=[]
        try:self.call(0x9d64e8,{'X0':owner,'W1':slot,'W2':item})
        finally:self.weapon_mode=None
        if self.resource_request is None:raise ValueError('Original weapon resource request missing')
        return {**self.resource_request,'tableLookups':self.lookup_calls}


class WeaponMountProbe(TutorialNPCVisibilityProbe):
    def __init__(self,image):
        verify(image);super().__init__(image)
        self.node_indices={};self.lookup_events=[]

    def hook(self,uc,at,size,data):
        if at==0x1364108:
            name=self.cstr(self.get('X1')).decode();self.lookup_events.append(name)
            self.w(self.get('X8'),'Q',self.lookup_nodes.get(name,0))
            self.set('PC',self.get('X30'));return
        return super().hook(uc,at,size,data)

    def attachment(self,body_nodes,weapon_nodes,slot,anchor):
        from bdae_character import aliases
        body_aliases=aliases(body_nodes);weapon_aliases=aliases(weapon_nodes)
        self.lookup_nodes={name:self.node(name)for name in body_aliases}
        self.lookup_events=[]
        # Actual original lookup loop, not a host slot-name mapping.
        self.fragment(0x32047c,0x320558,{'X19':self.model})
        pointer=self.r(self.model+0xd10+(slot-15)*8,'Q')[0]
        name=self.cstr(self.r(0x25090f0+(slot-15)*8,'Q')[0]).decode()
        target=body_aliases.get(name)
        weapon=self.node('weapon-root');self.scene_events=[]
        # Source resource has already been read; this fragment begins after
        # original resource creation, before its selected scene attach.
        self.fragment(0x3245e4,0x324ac8,{'X20':self.model,'W21':slot,'X26':weapon})
        parent=self.r(weapon+0xe8,'Q')[0]
        if parent!=(pointer or self.root):raise ValueError('Original mount parent differs')
        self.lookup_nodes={}
        if anchor:
            if anchor in weapon_aliases:
                selected=weapon_nodes[weapon_aliases[anchor]]
                node=self.node(anchor);self.w(node+0x100,'3f',*selected['position']);self.lookup_nodes[anchor]=node
        handle=self.alloc(8);self.w(handle,'Q',weapon)
        self.fragment(0x32165c,0x321abc,{'X0':self.model,'W1':slot,'X2':handle,
            'X3':self.cpp_cstring(anchor)if anchor else 0})
        return {'slot':slot,'sourceSlotNodeName':name,'sourceNodeIndex':target,
            'sourceNodePresent':bool(pointer),'rootFallback':not bool(pointer),
            'positionAnchor':anchor,'positionAnchorPresent':anchor in weapon_aliases if anchor else None,
            'rootLocalTranslation':list(self.r(weapon+0x100,'3f')),
            'sceneEvents':self.scene_events,'nameLookups':self.lookup_events,
            'rotationOrScaleRewritten':False,'sourceRootGeometryTransformPreserved':True,
            'nativeAttachFragment':'323b44:3245e4..324ac8 then32165c..321abc',
            'continuationMaterialEffectsExecuted':False,'hostSceneHandlesAndAttach':True}

    def cpp_cstring(self,value):
        pointer=self.alloc(len(value.encode())+1);self.uc.mem_write(pointer,value.encode()+b'\0');return pointer


def recover(image,source=DEFAULT_SOURCE):
    sources=Sources(source);probe=WeaponProbe(image,sources);entries=[]
    cases=[(750,741,200069),(970,949,200010)]
    for entry,display,item in cases:
        parsed,row=probe.row('creaturedisplayinfo',display)
        extra=probe.row('creaturedisplayinfoextra',row['ExtraDisplayInformation'])[1]
        if extra['MainHand']!=item or extra['OffHand']!=0:raise ValueError('Original default weapon changed')
        entries.append({'entry':entry,'display':display,'extra':extra,
            'postureFixtures':[probe.posture(display,0x40a,b)for b in[0,2,4,6]],
            'nonCreatureKindFixture':probe.posture(display,0,0),
            'explicitOverrideFixture':probe.posture(display,0x40a,0,main_override=200010 if item==200069 else 200069),
            'postureEventFixtures':[probe.posture_event(display,0x40a,event)for event in[-1,1,2]],
            'eventByte114ZeroFixture':probe.posture_event(display,0x40a,2,byte114=0),
            'eventCachedSameFixture':probe.posture_event(display,0x40a,2,cached=2),
            'weapons':[{'armed':armed,'slots':probe.slots(item,armed)}for armed in[0,1]],
            'currentActivityState':None})
        for choice in entries[-1]['weapons']:
            choice['resources']=[probe.resource(r['slot'],r['itemKey'])for r in choice['slots']['requests']if r['itemKey']]
    return {'format':FORMAT,'nativeSHA256':hashlib.sha256(image.data).hexdigest(),'entries':entries,
        'samplerCPU':sampler_cases(image),
        'sourceProofs':sources.proofs,'actualGUID':None,'activityPosture':None,
        'scope':'Explicit property/state fixtures over original CPU; no network/resource-completion evidence.',
        'productionChanged':False,'savesReadOrWritten':False}


def sampler_cases(image):
    from source_physics import SourcePhysics
    from scene_texture_sampling import verify_native
    verify_native(image);vm=SourcePhysics(image)
    texture,state,caps=vm.alloc(0x100),vm.alloc(0x100),vm.alloc(0x200)
    vm.uc.mem_write(state,bytes([255])*0x100)
    # The constructor's allocation/name/capability interfaces precede this
    # fragment. Execute its actual state initialization, not a chosen mode.
    TutorialNPCVisibilityProbe.fragment(vm,0x146d434,0x146d488,
        {'X19':texture,'X25':state,'X23':caps})
    vm.w(texture+0x30,'3I',512,512,1)
    initial=vm.r(state+0x60,'I')[0]
    vm.call(0x146f58c,{'X0':texture,'W1':0,'W2':2})
    after=vm.r(state+0x60,'I')[0]
    names={i:vm.cstr(vm.r(0x24995f0+i*8,'Q')[0]).decode()for i in[0,2]}
    if names!={0:'Repeat',2:'Clamp to Edge'}:raise ValueError('Source address enums differ')
    return {'sourceInitFragment':'146d434..146d488','sourceSetter':'146f58c',
        'freshDefaultUV':[(initial>>shift)&7 for shift in[23,26]],
        'explicitU2AfterUV':[(after>>shift)&7 for shift in[23,26]],'originalEnumNames':names,
        'GPUOrLiveCacheExecuted':False,'POTDimensionsAreExplicitFixture':[512,512,1]}


if __name__=='__main__':
    from analyze_native_resources import NativeImage
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--native',type=Path,default=ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so')
    cli.add_argument('--source',type=Path,default=DEFAULT_SOURCE);cli.add_argument('--output',type=Path,required=True)
    args=cli.parse_args();output=local_output(args.output)
    if output.exists():cli.error('Existing evidence is preserved')
    result=recover(NativeImage(args.native.read_bytes()),args.source);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'output':str(output),'entries':[r['entry']for r in result['entries']]}))
