"""Original jump input counter/header contract, not a jump approval fixture."""
import hashlib,json,struct
from pathlib import Path
from source_physics import SourcePhysics

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'analysis/raw/player-choice-elf-female-input-contract-20261116'
LIB=ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'
CURRENT=0x2527ad9;PENDING=0x2527b59
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
write=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')

class SourceJumpInputMixin:
    """Only map allocation/libc storage is supplied, not bool permissions."""
    def __init__(self,image,*args,**kwargs):
        self.maps={};self.storage_calls=[];self.jump_input_audit=False;self.jump_input_storage_active=False;self.jump_free_nodes=[];self.jump_as_input=None;super().__init__(image,*args,**kwargs)

    def hook(self,uc,at,size,data):
        name=self.imports.get(at,'')
        if self.jump_input_storage_active and name=='_ZNSt3mapIiiSt4lessIiESaISt4pairIKiiEEEixERS3_':
            owner=self.get('X0');key=self.r(self.get('X1'),'i')[0];nodes=self.maps.setdefault(owner,{})
            if key not in nodes:
                node=self.jump_free_nodes.pop()if self.jump_free_nodes else self.alloc(0x30)
                self.uc.mem_write(node,bytes(0x30));self.w(node+0x20,'i',key);nodes[key]=node
                def link(rows):
                    if not rows:return 0
                    middle=len(rows)//2;k=rows[middle];p=nodes[k]
                    self.w(p+0x10,'2Q',link(rows[:middle]),link(rows[middle+1:]));return p
                self.w(owner+0x10,'Q',link(sorted(nodes)))
            if self.jump_input_audit:self.storage_calls.append({'hostMapIndex':key,'sourceCaller':hex(self.get('X30')-4)})
            self.set('X0',nodes[key]+0x24);self.set('PC',self.get('X30'));return
        if self.jump_input_storage_active and name=='_ZNSt8_Rb_treeIiSt4pairIKiiESt10_Select1stIS2_ESt4lessIiESaIS2_EE8_M_eraseEPSt13_Rb_tree_nodeIS2_E':
            # The source wrapper reuses the same stack slot on the next call.
            # Retire this host map identity as its destructor requests, or a
            # later constructor could retain old nodes behind a zeroed root.
            retired=self.maps.pop(self.get('X0'),{})
            self.jump_free_nodes.extend(retired.values())
            if self.jump_input_audit:self.storage_calls.append({'hostMapCleanup':True,'originalStdlibEraseExecuted':False})
            self.set('PC',self.get('X30'));return
        return super().hook(uc,at,size,data)

    def controls(self):
        return {'current':self.r(CURRENT+14,'b')[0],'pending':self.r(PENDING+14,'b')[0],
            'input25':self.call(0x37d494,{'X0':0,'W1':25,'W2':0,'W3':0xffffffff})&1}

    def press(self,value):
        if type(value)is not bool:raise ValueError('Explicit source Boolean required')
        if self.jump_input_storage_active:raise ValueError('No recursive input call on the synchronous native VM')
        if self.jump_as_input is None:self.jump_as_input=(self.alloc(0x18),self.alloc(0x18),self.alloc(8),self.alloc(0x40))
        result,argument,holder,frame=self.jump_as_input
        for p,n in zip(self.jump_as_input,(0x18,0x18,8,0x40)):self.uc.mem_write(p,bytes(n))
        self.w(argument,'B',1);self.w(argument+8,'B',int(value));self.w(holder,'Q',argument)
        self.w(frame,'Q',result);self.w(frame+0x18,'Q',holder);self.w(frame+0x20,'Q',1)
        before=self.controls();self.jump_input_storage_active=True
        try:self.call(0x65a34c,{'X0':frame})
        finally:self.jump_input_storage_active=False
        return {'sourceBoolean':value,'entry':'Hero_SetJumpState/0x65a34c','before':before,'after':self.controls(),
            'resultBoolean':bool(self.r(result+8,'B')[0]),'fullFlashVMExecuted':False,'hostMapStorageOnly':True}

    def counter_frame(self):
        before=self.controls();self.call(0x37d210,{})
        return {'entry':'0x37d210','before':before,'after':self.controls(),'callerSchedulingObserved':False}

    def input_header(self,fields):
        """Explicit minimal layout controls; never runs actor qualification.

        These are branch tests, not a newly created/source-default character.
        Every byte that could let the branch continue must be named by caller.
        """
        required={'actor1498Busy','uiContextPresent','actor3b0','controller1b0','uiContext84','actor638Present','actor2b4','inputCount','uiFallback1d8'}
        if not isinstance(fields,dict)or set(fields)!=required or any(type(v)is not int or v not in(0,1)for k,v in fields.items()if k!='inputCount')or type(fields['inputCount'])is not int or not -128<=fields['inputCount']<=127:
            raise ValueError('Complete named raw input-header control required, no defaults')
        from unicorn import UC_HOOK_CODE
        actor=self.alloc(0x1600);controller=self.alloc(0x200);root=self.alloc(0x400);ui_manager=self.alloc(0x100);ui_context=self.alloc(0x100);ui=self.alloc(0x13d0)
        self.w(actor+0x698,'Q',controller);self.w(controller+0x1b0,'B',fields['controller1b0']);self.w(actor+0x3b0,'B',fields['actor3b0']);self.w(actor+0x2b4,'B',fields['actor2b4'])
        self.w(actor+0x638,'Q',self.alloc(8)if fields['actor638Present']else 0)
        if fields['actor1498Busy']:
            busy=self.alloc(0x30);self.w(busy+0x20,'Q',self.alloc(8));self.w(actor+0x1498,'Q',busy)
        self.w(root+0x178,'Q',ui_manager);self.w(ui_manager+0x58,'Q',ui_context if fields['uiContextPresent']else 0);self.w(ui_context+0x84,'B',fields['uiContext84'])
        self.w(0x2528db0,'Q',root);self.w(0x2527ad0,'Q',ui);self.w(ui+0x1d8,'B',fields['uiFallback1d8']);self.w(CURRENT+14,'b',fields['inputCount'])
        boundaries=[]
        def boundary(uc,at,size,data):
            if at in(0x9fd594,0x9fd5c0,0x9fd904):boundaries.append(hex(at));self.set('PC',self.EXIT)
        handles=[self.uc.hook_add(UC_HOOK_CODE,boundary,begin=at,end=at)for at in(0x9fd594,0x9fd5c0,0x9fd904)]
        try:self.call(0x9fd4e8,{'X0':actor,'W1':0})
        finally:
            for h in handles:self.uc.hook_del(h)
        if len(boundaries)!=1:raise ValueError('Exact original input-header boundary required')
        return {'explicitNonCharacterLayoutControls':dict(fields),'reachedOriginalBoundary':boundaries[0],
            'actualActorEligibilityOrJumpExecuted':False,'originalPlayerDefaultsSupplied':False,'nativeInputHeaderExecuted':True}

class InputContractProbe(SourceJumpInputMixin,SourcePhysics):
    def __init__(self,image):super().__init__(image);self.jump_input_audit=True

class SourceJumpInputContexts:
    """Per-local-client storage for the original global input arrays.

    The host owns identities/lifetime; original code owns all counter updates.
    It never copies this state into actor/weapon/skill fields or grants a jump.
    """
    REGIONS=((CURRENT,128),(PENDING,128),(0x25093c4,7))
    def __init__(self,engine):
        if not isinstance(engine,SourceJumpInputMixin):raise ValueError('Native input mixin on the same owned VM required')
        self.engine=engine;self.contexts={}
    def _read(self):return tuple(bytes(self.engine.uc.mem_read(p,n))for p,n in self.REGIONS)
    def _write(self,values):
        for (p,n),raw in zip(self.REGIONS,values):
            if len(raw)!=n:raise ValueError('Exact original input storage extent required')
            self.engine.uc.mem_write(p,raw)
    def create(self,identity):
        if not isinstance(identity,str)or not 0<len(identity)<=128 or identity in self.contexts:raise ValueError('Explicit new input identity required')
        previous=self._read()
        try:
            self.engine.call(0x3a5c04,{}) # Actual original input-array reset.
            self.engine.call(0x3a5dc4,{}) # Actual original clear-delay operation.
            self.contexts[identity]=self._read()
        finally:self._write(previous)
        return {'identity':identity,'originalResetEntries':['0x3a5c04','0x3a5dc4'],'hostNewControlSession':True,'originalServerStateClaimed':False}
    def _run(self,identity,fn):
        if identity not in self.contexts:raise ValueError('Existing explicit input identity required')
        previous=self._read();self._write(self.contexts[identity])
        try:
            result=fn();self.contexts[identity]=self._read();return result
        finally:self._write(previous)
    def press(self,identity,pressed):return self._run(identity,lambda:self.engine.press(pressed))
    def frame(self,identity):return self._run(identity,self.engine.counter_frame)
    def inspect(self,identity):return self._run(identity,self.engine.controls)

def request_from_owned_web_input(engine,contexts,identity,*,event_owner):
    """Explicit web event routing + original local actor checks, no force.

    This does NOT claim to run9fd4e8's original scene-manager/UI phase. Its
    event owner is the real host event-routing result, not a guessed native84.
    All actor/weapon/skill fields remain untouched by this adapter.
    """
    if event_owner not in('world','captured','inactive'):raise ValueError('Actual current host event owner required')
    if not isinstance(contexts,SourceJumpInputContexts)or contexts.engine is not engine:raise ValueError('Same VM/input owner required')
    if event_owner!='world':return {'requested':False,'reason':'host-event-'+event_owner,'originalHeaderExecuted':False}
    if not contexts.inspect(identity)['input25']:return {'requested':False,'reason':'original-input25-not-held','originalHeaderExecuted':False}
    if not hasattr(engine,'bindings')or identity not in engine.bindings or not hasattr(engine,'scope'):raise ValueError('Existing bound native actor required; no actor/default creation')
    def run(h):
        a=h['actor']['address'];vt=engine.r(a,'Q')[0]
        expected={0x60:0x90e26c,0x138:0x90e3b8,0x2b8:0x912ce4}
        for off,target in expected.items():
            if engine.r(vt+off,'Q')[0]!=target:raise ValueError('Missing original qualification virtual '+hex(off)+'; do not substitute false')
        if engine.r(vt+0x70,'Q')[0]not in(0x904f7c,engine.POSITION):raise ValueError('Actual reviewed source-position getter required')
        busy=engine.r(a+0x1498,'Q')[0]
        if busy and engine.call(0x4ad704,{'X0':busy})&1:return {'requested':False,'reason':'original-controller1498-busy','originalHeaderExecuted':False}
        if engine.r(a+0x3b0,'B')[0]:return {'requested':False,'reason':'original-actor3b0','originalHeaderExecuted':False}
        if not engine.r(a+0x698,'Q')[0]:raise ValueError('Actual original motion controller required')
        if engine.call(0x90d4b8,{'X0':a}):return {'requested':False,'reason':'original-motion-controller1b0','originalHeaderExecuted':False}
        if engine.r(a+0x638,'Q')[0]:return {'requested':False,'reason':'original-actor638','originalHeaderExecuted':False}
        if engine.r(a+0x2b4,'B')[0]:return {'requested':False,'reason':'original-actor2b4','originalHeaderExecuted':False}
        skill=engine.r(a+0x770,'Q')[0]
        if not skill:raise ValueError('Actual known skill container required; do not synthesize it')
        if engine.r(skill+0x10,'Q')[0]:raise ValueError('Active skill virtual60 requires its actual reviewed source object')
        prior=engine.native_state;engine.native_state=True
        try:result=engine.call(0x90ac5c,{'X0':a,'W1':0x28,'W2':0},{'S0':0,'S1':0,'S2':0,'S3':0})&1
        finally:engine.native_state=prior
        return {'requested':bool(result),'nativeReturn':result,'originalActorJumpEntry':'0x90ac5c','forceFlag':0,
            'entryAdapter':'web-owned-event','originalHeaderExecuted':False,'actorHeaderConditionsFromOriginal':True,
            'knownEmptySkillUsesOriginalLocalBranch':True,'originalServerApprovalClaimed':False}
    # Keep the same client's complete source input storage current while
    # native state entry executes too, not only during the initial query.
    return contexts._run(identity,lambda:engine.scope(identity,run))

def fresh_header_stores(image):
    from tutorial_npc_name_completion_probe import probe_type
    from unicorn import UC_HOOK_MEM_WRITE
    p=probe_type()(image);writes=[]
    def watch(uc,access,address,size,value,data):writes.append({'address':address,'bytes':size,'value':value,'pc':hex(p.get('PC'))})
    handle=p.uc.hook_add(UC_HOOK_MEM_WRITE,watch,begin=p.ARENA,end=p.ARENA+0x4000000-1)
    try:receipt=p.construct_hero_prefix()
    finally:p.uc.hook_del(handle)
    actor=receipt['pointer'];fields={}
    targets=[(f'actor+{o:x}',actor+o,'Q'if o in(0x1498,0x638,0x698)else'B')for o in(0x1498,0x638,0x698,0x3b0,0x2b4)]
    controller=p.r(actor+0x698,'Q')[0]
    if controller:targets.append(('motionController+1b0',controller+0x1b0,'B'))
    for name,address,fmt in targets:
        n=struct.calcsize('<'+fmt);hit=[r for r in writes if r['address']<address+n and r['address']+r['bytes']>address]
        fields[name]={'address':address,'value':list(p.r(address,fmt)),'writes':hit,'originalStoreObserved':bool(hit)}
        if not hit:raise ValueError('Do not interpret allocation zero as source initialization '+name)
    return {'format':'oc2-original-hero-input-fresh-prefix-v1','constructorReceipt':receipt,'extraInputFields':fields,
        'noQualifiedJumpOrLiveRoleExecuted':True,'freshValuesNotOverridesForRunningCharacters':True}

def known_source_producers(image):
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE
    from optimized_abc import extract_abc,parse_abc,named_method
    from control_assets import PROGRAMS,METHODS
    sources=Sources(DEFAULT_SOURCE);raw=sources.read('ui/Flash/OperationPanel2.swf');program=parse_abc(extract_abc(raw))
    if program['sourceSHA256']!=PROGRAMS['OperationPanel2']:raise ValueError('Original control ABC differs')
    methods={}
    for name in('onJumpPress','onJumpRelease'):
        m=named_method(program,'OperationPanel2',name)
        if m['codeSHA256']!=METHODS['OperationPanel2.'+name]:raise ValueError('Original jump method differs')
        methods[name]=m
    rel={r['r_offset']:r['r_addend']for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    slots={hex(o):hex(rel[0x24228a8+o])for o in(0x60,0x70,0x138,0x2b8)}
    stores={}
    for entry,expected in[(0x9ec7c8,'009ecc88 str      xzr, [x19, #0x1498]'),(0x39c690,'0039ca34 strb     wzr, [x19, #0x1d8]')]:
        meta,lines=image.routine(entry)
        if expected not in lines:raise ValueError('Original fresh constructor store differs')
        stores[hex(entry)]={'actualInstruction':expected,'completeConstructorOrLiveValueExecutedHere':False}
    return {'format':'oc2-source-jump-input-producers-v1','sourceASMethods':methods,'sourceProofs':sources.proofs,
        'originalHeroVtable':'0x24228a8','realVtableSlotTargets':slots,'constructorStoresStaticOnly':stores,
        'registration':'0x64c850..0x64c860: Hero_SetJumpState ->0x65a34c via10011a4',
        'oldAirResearchVirtual138WasExplicitFalse':True,'existingSourceDivingActorInstallsRealWaterVirtuals':True}

def recover(image):
    e=InputContractProbe(image);mapping=struct.unpack('<i',image.read(0x1df8820+24*4,4))[0]
    if mapping!=14:raise ValueError('Original action25 key mapping changed')
    e.call(0x3a5c04,{})
    steps=[{'reset':e.controls()},e.press(True),e.counter_frame(),e.counter_frame(),e.press(False),e.counter_frame(),e.counter_frame()]
    neutral={'actor1498Busy':0,'uiContextPresent':1,'actor3b0':0,'controller1b0':0,'uiContext84':1,'actor638Present':0,'actor2b4':0,'inputCount':1,'uiFallback1d8':0}
    cases=[]
    for label,delta in [('named-continue-to-qualification',{}),('input-released',{'inputCount':0}),('negative-input-count',{'inputCount':-1}),
            ('fallback-local-ui-flag',{'inputCount':0,'uiFallback1d8':1}),('actor-controller-busy',{'actor1498Busy':1}),('no-ui-context',{'uiContextPresent':0}),
            ('actor-3b0',{'actor3b0':1}),('controller-1b0',{'controller1b0':1}),('ui-context-84',{'uiContext84':0}),
            ('actor-638',{'actor638Present':1}),('actor-2b4',{'actor2b4':1})]:
        cases.append({'label':label,**e.input_header({**neutral,**delta})})
    skill=e.alloc(0x40);none=e.call(0x5be240,{'X0':skill})
    threshold_cases=[]
    for value in(-.001,-.000001,0.,.000001,.001):
        a=e.alloc(0x200);e.w(a+0x138,'f',value)
        from unicorn import UC_HOOK_CODE
        reached=[]
        def stop(uc,at,size,data):
            reached.append('original-posture-provider');e.set('PC',e.EXIT)
        h=e.uc.hook_add(UC_HOOK_CODE,stop,begin=0x9e0438,end=0x9e0438)
        try:result=e.call(0x90e50c,{'X0':a})
        finally:e.uc.hook_del(h)
        threshold_cases.append({'explicitAccelerationY':value,'nextUnprovidedInput':reached[0]if reached else None,'nativeReturnWhenFullyReturned':result if not reached else None,
            'noOtherActorAttributeOrWeaponSkillProvided':True})
    contexts=SourceJumpInputContexts(e);saved=contexts._read();created=[contexts.create('a'),contexts.create('b')]
    contexts.press('a',True);context_steps=[{'a':contexts.frame('a'),'b':contexts.frame('b')}]
    context_steps.append({'a':contexts.frame('a'),'b':contexts.frame('b')});contexts.press('a',False)
    context_steps.append({'a':contexts.frame('a'),'b':contexts.frame('b')})
    if contexts._read()!=saved:raise ValueError('Scoped source input leaked outside its identity')
    return {'format':'oc2-source-elf-female-input-contract-cpu-v1','nativeSHA256':hashlib.sha256(image.data).hexdigest(),
        'inputMapping':{'action':25,'keyIndex':14,'pressBitmask':0x4000,'currentBase':hex(CURRENT),'pendingBase':hex(PENDING)},
        'pressReleaseSteps':steps,'mapStorageCalls':e.storage_calls,'inputHeaderCases':cases,
        'actualEmptyActiveSkillContainerBranch':{'entry':'0x5be240','containerPlus10':0,'nativeReturn':none,'notNetworkApproval':True},
        'accelerationQualificationCases':threshold_cases,'wholeActorEligibilityPassClaimed':False,'liveCharacterValuesClaimed':False,
        'perIdentityHostStorageAdapter':{'created':created,'interleaved':context_steps,'outerOriginalInputStorageUnchanged':True,'actorOrWeaponSkillModified':False}}

def source_proofs(image):
    source={}
    for at in(0x9fd4e8,0x65a34c,0x37dbe4,0x3ccee8,0x3ccf20,0x3ccfd8,0x3cd024,0x3a5c04,0x3a5dc4,0x37d210,0x37d494,
            0x4ad704,0x90d4b8,0x90ac5c,0x90e50c,0x5be240,0x912ce4,0x90e3b8,0x9e0438,0xa52b68,0x39c690,0x9ec7c8,0x905638,0xa2e774):
        meta,lines=image.routine(at);start=int(meta['start'],16)
        source[hex(start)]={'bytes':meta['size'],'sha256':hashlib.sha256(image.read(start,meta['size'])).hexdigest()}
        (RAW/(hex(start)+'.asm')).write_text('\n'.join(lines)+'\n')
    return source

def input_contract():
    return {'format':'oc2-source-jump-input-integration-contract-v1','targetBody':{'modelId':2,'internalRace':1,'gender':1},
        'readyLocalInputs':[
            {'field':'input25','source':'OperationPanel2 ->65a34c ->37dbe4 ->key14 pending ->37d210 ->37d494','hostMapping':'actual world-owned Pointer/keyboard pressed/released Boolean','needsOriginalServerPermission':False},
            {'field':'actor1498/638/3b0/2b4/controller1b0','source':'observed original fresh constructor stores','hostMapping':'source initialization only for newly owned host actor, then actual current native controller state; never overwrite running character','needsExternalSessionForFreshInitialization':False},
            {'field':'motion+vertical acceleration and posture','source':'current authoritative native physics and original three-axis animation manager','hostMapping':'reuse same existing actor, not web animation aliases or a guessed grounded state'},
            {'field':'virtual60/138 water checks','source':'real Hero vtable90e26c/90e3b8, source scene contact/water fields','hostMapping':'existing SourceDiving.actor +bind_body(existing_actor=True), never false stubs'},
            {'field':'active skill container+10','source':'actual current container;5be240 original null-active branch returns1','hostMapping':'known no active native action can use original empty branch; learned/equipped/catalog are not current active action'}],
        'keptUnknown':[
            {'field':'original state-manager current-object+84','sourceRead':'9fd550','meaningAndActualNonzeroWriterClosed':False,'mustNotInferFrom':'DOM window count or inGame Boolean'},
            {'field':'UI singleton+1d8 nonzero producer','sourceRead':'9fd588..9fd590','knownFreshStore':'39ca34=0','neededWhen':'input25 is not held and original handler tries this separate fallback'},
            {'field':'props+40 business semantic','sourceRead':'90e58c ->a996c8','mustNotInferFrom':'old web HP/XP/level','use':'actual current encoded native property container'},
            {'field':'non-null active-skill virtual60','sourceRead':'5be248..5be250','use':'requires actual reviewed skill object; helper refuses instead of granting'}],
        'hostAdapter':{'mixin':'SourceJumpInputMixin','contexts':'SourceJumpInputContexts','dispatch':'request_from_owned_web_input',
            'actorCreatedOrFieldsFilled':False,'forcedJumpFlag':0,'original9fd4e8HeaderClaimed':False,
            'eventOwnerMustBeExplicit':['world','captured','inactive'],'unknownEventOwnerRejected':True},
        'notReexecuted':['13 admitted animation ranges','32-frame jump/landing tests','browser/servers/Docker/saves/deployment']}

def run():
    from analyze_native_resources import NativeImage
    if (RAW/'native-cpu-v1.json').exists():raise ValueError('New ignored input-contract output required')
    RAW.mkdir(exist_ok=True);image=NativeImage(LIB.read_bytes());write(RAW/'source-index-v1.json',source_proofs(image))
    write(RAW/'source-producers-v1.json',known_source_producers(image))
    write(RAW/'fresh-header-stores-v1.json',fresh_header_stores(image))
    write(RAW/'input-contract-v1.json',input_contract())
    result=recover(image);write(RAW/'native-cpu-v1.json',result)
    print(json.dumps({'pressReleaseSteps':len(result['pressReleaseSteps']),'headerControls':len(result['inputHeaderCases']),
        'actualActorEligibilityPassClaimed':False,'input25IsSignedCounter':True}))

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path);args=parser.parse_args()
    if args.output is not None:
        selected=args.output.resolve()
        if not selected.is_relative_to(ROOT/'analysis/raw')or selected.exists():raise ValueError('New ignored contract output required')
        RAW=selected
    run()
