"""Execute the original name formatter and getter on two real CPU actors.

Local Hero/context and packets remain explicit isolated inputs. C++ string
storage/libc/localized bytes are host interfaces, not native Android state.
No name is installed in a game, world, save or browser UI.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from tutorial_npc_actor_ingress_probe import probe_type as ingress_type,SO,ROOT,RAW,digest,json_write,private_path
AREA=RAW/'tutorial-npc-name-completion-20261115'


def probe_type():
    from unicorn import UC_HOOK_CODE
    Base=ingress_type()
    class P(Base):
        def __init__(self,image):
            self.formatter_active=False;self.formatter_calls=[];self.finds=[];self.context_missing=False;self.partial_hero=None;self.name_writes=[];self.bootstrap_active=False;self.formatter_returned=False
            super().__init__(image)
            for at in (0x3f9df4,0x1de7400,0x3e5498,0x3e4774,0x9ec7c8,0x2a5d24,0x2a6264,0x2a6280,0x3e5540,0x2b93e0,0xe854d8,0x9ea854):self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=at,end=at)
        def hook(self,uc,at,size,data):
            if self.bootstrap_active=='fallback' and at==0x2b93e0:self.set('PC',self.EXIT);return
            if at==0x2b93e0:return
            if self.name_active and at==0x9ea854:self.formatter_returned=True;return
            if at==0x9ea854:return
            if self.name_active and at==0xe854d8:
                self.context_missing='fallback-general-text-provider';self.set('PC',self.EXIT);return
            if at==0xe854d8:return
            if self.bootstrap_active and at in (0x2a5d24,0x2a6264,0x2a6280):
                self.set('PC',{0x2a5d24:0x2a6244,0x2a6264:0x2a6274,0x2a6280:self.EXIT}[at]);return
            if at in (0x2a5d24,0x2a6264,0x2a6280):return
            if self.formatter_active and at==0x3e5540:
                value=self.get('X0');self.finds[-1]['originalResult']=value-(1<<64) if value&(1<<63) else value;return
            if at==0x3e5540:return
            if at==0x9ec7c8:self.partial_hero=self.get('X0');return
            if self.name_active and at==0x1de8970 and self.get('X0')==self.current_name_actor+0x210:
                self.name_writes.append({'entry':'0x1de8970','nativeCallSite':hex(self.get('X30')-4),'actualActor':self.current_name_actor})
            if self.name_active and at==0x3e4710:
                self.formatter_active=True;self.formatter_calls.append({'entry':'0x3e4710','originalInstructionsExecute':True,
                    'entityArgument':self.get('X1'),'replacementString':self.cstr(self.r(self.get('X2'),'Q')[0]).decode()})
                return
            if self.formatter_active and at==0x3f9df4:
                self.formatter_calls.append({'entry':'0x3f9df4','key':self.cstr(self.get('X0')).decode(),'originalInstructionsExecute':True});return
            if self.formatter_active and at==0x1de7400:
                self.finds.append({'needleHex':self.cstr(self.get('X1')).hex(),'start':self.get('X2'),'bytes':self.get('X3')});return
            if self.formatter_active and at==0x3e4774:
                if not self.get('X8'):
                    self.context_missing='localHero.name210';self.set('PC',self.EXIT)
                return
            if self.formatter_active and at==0x3e5498:
                manager=self.get('X8')
                if not manager:
                    self.context_missing='global2528e60';self.set('PC',self.EXIT)
                return
            if at in (0x3f9df4,0x1de7400,0x3e5498,0x3e4774,0x9ec7c8,0x2a5d24,0x2a6264,0x2a6280,0x3e5540,0x2b93e0,0xe854d8,0x9ea854):return
            name=self.imports.get(at)
            if name=='strtol':
                raw=self.cstr(self.get('X0'));base=self.get('W2')
                if base not in (0,10) or len(raw)>128:raise ValueError('Unexpected constructor numeric conversion')
                match=re.match(rb'[ \t\r\n]*[+-]?[0-9]+',raw);value=int(match[0]) if match else 0
                if not -(1<<63)<=value<(1<<63):raise ValueError('Numeric overflow requires actual libc errno')
                if self.get('X1'):self.w(self.get('X1'),'Q',self.get('X0')+(match.end() if match else 0))
                self.set('X0',value&((1<<64)-1));self.set('PC',self.get('X30'));return
            if name=='memcmp':
                count=self.get('X2')
                if count>8192:raise ValueError('Bounded original string comparison required')
                left=bytes(uc.mem_read(self.get('X0'),count));right=bytes(uc.mem_read(self.get('X1'),count))
                self.set('W0',((left>right)-(left<right))&0xffffffff);self.set('PC',self.get('X30'));return
            if name=='tolower':
                value=self.get('W0')
                if value>127:raise ValueError('Only observed ASCII constructor tolower is adapted')
                self.set('W0',value+32 if 65<=value<=90 else value);self.set('PC',self.get('X30'));return
            if self.formatter_active and name=='strcpy':
                raw=self.cstr(self.get('X1'))
                if len(raw)>1024:raise ValueError('Bounded original formatter C string required')
                uc.mem_write(self.get('X0'),raw+b'\0');self.set('PC',self.get('X30'));return
            if self.formatter_active and name=='sprintf':
                fmt=self.cstr(self.get('X1'));number=self.get('W2');number=number-(1<<32)if number&0x80000000 else number
                if fmt not in (b'GENERAL_PLAYER_RACE_%d',b'GENERAL_PLAYER_CLASS_%d',b'%%d'):raise ValueError('Unexpected original formatter format '+repr(fmt))
                raw=b'%d'if fmt==b'%%d'else fmt.replace(b'%d',str(number).encode())
                uc.mem_write(self.get('X0'),raw+b'\0');self.set('W0',len(raw));self.set('PC',self.get('X30'));return
            return super().hook(uc,at,size,data)
        def bootstrap_original_formatter_globals(self):
            self.bootstrap_active=True
            try:self.call(0x2a5d10)
            finally:self.bootstrap_active=False
            self.bootstrap_active='fallback'
            try:self.call(0x2b93c4)
            finally:self.bootstrap_active=False
            return {'fallbackInitializerFragment':'_INIT_123 2b93c4..2b93e0','sourceInitializer':'_INIT_28','fragments':['2a5d10..2a5d24','2a6244..2a6264','2a6274..2a6280'],
                'output2532b00':self.r(0x2532b00,'Q')[0],'generalKeyRegistryEmpty':self.r(0x2529ac0+0x10,'Q')[0]==0,
                'wholeInitializerAndGeneralTableRegistrationExecuted':False}

        def construct_hero_prefix(self):
            from unicorn import UC_HOOK_MEM_WRITE
            writes=[]
            def watch(uc,access,address,size,value,data):
                writes.append({'address':address,'bytes':size,'value':value,'pc':hex(self.get('PC'))})
            handle=self.uc.hook_add(UC_HOOK_MEM_WRITE,watch,begin=self.ARENA,end=self.ARENA+0x4000000-1)
            try:
                returned=self.call(0xa771e0);complete=True;stop=None
            except RuntimeError:
                returned=self.partial_hero;complete=False;stop=hex(self.get('PC'))
            finally:self.uc.hook_del(handle)
            if not returned or not complete and stop!='0x5be87c':raise ValueError('Unexpected Hero constructor frontier '+str(stop))
            # Explicit research context binding only: the original entry
            # message/global localHero publisher has not been executed.
            self.w(self.creature_manager+0x68,'Q',returned)
            props=self.r(returned+0x18,'Q')[0];skill=self.r(returned+0x770,'Q')[0]
            fields={}
            for label,address,fmt in [(f'actor+{o:x}',returned+o,'Q' if o==0x770 else 'I' if o==0x5a0 else 'B')for o in (0x4c,0x114,0x5a0,0x641,0xf24,0x770)]+[('props+40',props+0x40,'2I')]+([('skill+10',skill+0x10,'Q')]if skill else []):
                import struct
                width=struct.calcsize('<'+fmt);observed=[w for w in writes if w['address']<address+width and w['address']+w['bytes']>address]
                fields[label]={'address':address,'value':list(self.r(address,fmt)),'originalWrites':observed,
                    'initializedByObservedOriginalStore':bool(observed)}
            self.constructor_field_receipt={'fields':fields,'skillPointer':skill,'allUnwrittenAllocationZerosRemainUnknown':True}
            return {'originalFactory':'0xa771e0','constructor':'0x9ec7c8','pointer':returned,
                'fieldReceipt':self.constructor_field_receipt,'constructorCompleted':complete,'stop':stop,'vptr':hex(self.r(returned,'Q')[0]),
                'name210Pointer':self.r(returned+0x210,'Q')[0],
                'propertiesPointer':self.r(returned+0x18,'Q')[0],
                'localHeroBindingIsExplicitResearchInput':True,'liveEntryExecuted':False}

        def construct_context(self):
            pointer=self.alloc(0x98);self.call(0x421d2c,{'X0':pointer})
            if self.r(0x2528e60,'Q')[0]!=pointer:raise ValueError('Original context global registration missing')
            return {'nativeConstructor':'0x421d2c','pointer':pointer,'vptr':hex(self.r(pointer,'Q')[0]),
                'field10':self.r(pointer+0x10,'Q')[0],'originalFreshConstructorExecuted':True,'liveContextObserved':False}
        def complete_name_control(self,actor):
            self.name_active=True;self.formatter_active=False;self.formatter_calls=[];self.finds=[];self.name_requests=[];self.context_missing=False;self.current_name_actor=actor;self.name_writes=[];self.formatter_returned=False
            try:returned=self.call(0x9eaf20,{'X0':actor})
            finally:self.name_active=False;self.formatter_active=False
            text=self.cstr(self.r(actor+0x210,'Q')[0]).decode()
            return {'nativeActorPointer':actor,'actualGuid':str(self.r(actor+8,'Q')[0]),'entry':self.r(actor+0xf20,'I')[0],
                'selectedDisplay':self.r(actor+0xd60,'I')[0],'nativeGetter':'0x9eaf20','returnedPointer':returned,
                'actorNamePointer':self.r(actor+0x210,'Q')[0],'text':text,'originalFormatterReturned':self.formatter_returned,'originalNameFullyObserved':not self.context_missing,
                'textSubstitutionExecuted':self.formatter_returned,
                'missingContext':self.context_missing,'originalActorNameWrites':list(self.name_writes),'formatterCalls':list(self.formatter_calls),'originalFindCalls':list(self.finds),
                'originalNameRequests':list(self.name_requests),'sourceActivityObserved':False}
    return P


def run():
    from analyze_native_resources import NativeImage
    from tutorial_quest_creature_probe import packet_fixture
    image=NativeImage(SO.read_bytes());p=probe_type()(image)
    a=p.ingest_control(packet_fixture(guid=0x40a00001001,entry=750,position=(1,2,3),direction=(0,0,1)))
    b=p.ingest_control(packet_fixture(guid=0x40a00001002,entry=970,position=(4,5,6),direction=(1,0,0)))
    bootstrap=p.bootstrap_original_formatter_globals()
    missing=p.complete_name_control(a['nativeActorPointer'])
    hero_context=p.construct_hero_prefix()
    missing_other=p.complete_name_control(a['nativeActorPointer'])
    context=p.construct_context();completed=[p.complete_name_control(r['nativeActorPointer'])for r in (a,b)]
    cached=[p.complete_name_control(r['nativeActorPointer'])for r in (a,b)]
    hero=p.r(p.creature_manager+0x68,'Q')[0];props=p.r(hero+0x18,'Q')[0]
    return {'format':'oc2-npc-original-name-completion-v1','library':digest(SO),'createdA':a,'createdB':b,
        'formatterBootstrap':bootstrap,'missingContextControl':missing,'missingOtherContextControl':missing_other,'heroConstructorPrefix':hero_context,'constructedContext':context,'completed':completed,'cachedGetterCalls':cached,
        'localHeroContext':{'pointer':hero,'name':p.cstr(p.r(hero+0x210,'Q')[0]).decode(),
            'raceProperty':p.call(0xa996a0,{'X0':props+0x278}),'classProperty':p.call(0xa996a0,{'X0':props+0x3f8}),
            'sourceRuntimeHeroObserved':False},'sourceActivityObserved':False,'liveNamesInstalled':False,
        'boundary':['Incoming object controls and LocalHero/property/current context are explicit research inputs, not live server activity.',
            'Original name getter/formatter/search and fresh421d2c context constructor execute; string storage/libc and localized source bytes remain host interfaces.',
            'No native context/metadata is inferred from the apparent absence of ASCII tokens; original code decides each token search.']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=private_path(a.output)
    if out.exists():p.error('Preserve earlier evidence')
    json_write(out,run());print(json.dumps({'output':str(out),'liveNamesInstalled':False}))
