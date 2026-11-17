"""Own Class2116 main-body/Display.Effect1 gates, without ready replies.

Original load prefix stops before33566c. Post-body/effect/visibility fragments
are explicitly conditional source controls. A null BEFF attachment is a negative
input, never a successful effect or GPU/provider result.
"""
import hashlib,json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
AREA=ROOT/'analysis/raw/creation-elf-md-animation-20261116'
INDEX=ROOT/'analysis/raw/creation-class-source-20261116/source-v2.json'
EFFECT='Effects/skill/mage/electric_arc_aggregated_cast_hand_loop.beff'
NODE='Dummy_Left_Hand-node'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
write=lambda p,x:p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def gate_type():
    from tutorial_npc_robe_probe import RobeProbe
    from unicorn import UC_HOOK_CODE
    class GateProbe(RobeProbe):
        def __init__(self,image,sources):
            self.gate_mode=None;self.trace=[];self.frontier=None;self.parts_snapshot=None
            super().__init__(image,sources)
            for at in(0x9d5104,0x33566c,0x334fa4,0x3360a0,0x335ec8):self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=at,end=at)

        def hook(self,uc,at,size,data):
            if self.gate_mode and self.imports.get(at)=='strcmp':
                a,b=self.cstr(self.get('X0')),self.cstr(self.get('X1'))
                self.set('W0',((a>b)-(a<b))&0xffffffff);self.set('PC',self.get('X30'));return
            if self.gate_mode and self.imports.get(at)=='strcpy':
                raw=self.cstr(self.get('X1'));self.uc.mem_write(self.get('X0'),raw+b'\0')
                self.set('PC',self.get('X30'));return
            if self.gate_mode and self.imports.get(at)=='strrchr':
                base=self.get('X0');raw=self.cstr(base)+b'\0';index=raw.rfind(bytes([self.get('W1')&255]))
                self.set('X0',base+index if index>=0 else 0);self.set('PC',self.get('X30'));return
            if self.gate_mode=='body-prefix'and at==0x9d5104:return
            if self.gate_mode=='descriptor'and at==0x9d40cc:return
            if self.gate_mode=='descriptor'and at==0x9d4c48:
                self.trace.append({'entry':hex(at),'sourceModelId':self.get('W2'),'flags':self.get('W3')});return
            if self.gate_mode=='descriptor'and at==0x9d5104:
                self.model,self.display=self.get('X2'),self.get('X1')
                self.trace.append({'entry':hex(at),'sourceModelId':self.r(self.model,'I')[0],
                    'sourceModelFlags':self.r(self.model+4,'I')[0],'sourceBodyPath':self.cstr(self.r(self.model+8,'Q')[0]).decode(),
                    'requestedInitialClip':self.cstr(self.get('X5')).decode(),'engineFlags':self.get('W3'),
                    'displayEffects':[self.cstr(self.r(self.display+0x34+i*8,'Q')[0]).decode()for i in range(6)],
                    'stoppedBeforeOriginalBodyLoader':True})
                # Preserve the actual table rows before a later standalone call
                # reuses the native stack. The COW string allocations stay live.
                for field,table in(('model','creaturemodeldata'),('display','creaturedisplayinfo')):
                    parsed=next(p for n,p,rows in self.table_by_handle.values()if n==table)
                    width=sum({'s':8,'u':4,'k':4,'i':4,'f':4,'c':1,'h':2}[k]for k in parsed['physicalTypes'])
                    raw=bytes(self.uc.mem_read(getattr(self,field),width));target=self.alloc(width)
                    self.uc.mem_write(target,raw);setattr(self,field,target)
                self.set('PC',self.EXIT);return
            if self.gate_mode=='body-prefix'and at==0x33566c:
                self.frontier={'entry':hex(at),'path':self.cstr(self.get('X1')).decode(),
                    'resourceLoadReturnOrCallbackSupplied':False,'wrapperNodeAt8':self.r(self.get('X0')+8,'Q')[0]}
                self.set('PC',self.EXIT);return
            if self.gate_mode=='post-body':
                if at==0x335b50:
                    self.trace.append({'entry':hex(at),'initialClip':self.cstr(self.get('X1')).decode(),
                        'arg2':self.get('W2'),'engineFlags':self.get('W3'),'conditionalBodyLoadedBranch':True})
                    self.set('PC',self.get('X30'));return  # Void graph construction interface; not model/GPU success.
                if at==0x334fa4:
                    self.trace.append({'entry':hex(at),'conditionalBodyLoadedBranch':True});self.set('PC',self.get('X30'));return
                if at==0x3360a0:
                    self.trace.append({'entry':hex(at),'node':self.cstr(self.get('X1')).decode(),
                        'effect':self.cstr(self.get('X2')).decode(),'scale':self.gf('S0'),'arg3':self.get('W3'),
                        'effectLoaderExecuted':False,'effectSuccessSupplied':False})
                    self.set('PC',self.get('X30'));return  # Record a void request, no ready result.
                if(self.imports.get(at)or'').startswith('_ZNSt6vectorISs')and'_M_emplace_back_aux'in self.imports[at]:
                    vector=self.get('X0');begin,end,capacity=self.r(vector,'3Q');count=(end-begin)//8 if begin else 0
                    if not 0<=count<=3:raise ValueError('Bounded original comma split exceeded3 fields')
                    new=self.alloc((count+1)*8)
                    if count:self.uc.mem_write(new,bytes(self.uc.mem_read(begin,count*8)))
                    self.w(new+count*8,'Q',self.r(self.get('X1'),'Q')[0]);self.w(vector,'3Q',new,new+(count+1)*8,new+(count+1)*8)
                    self.set('PC',self.get('X30'));return
                if self.imports.get(at)=='atof':
                    raw=self.cstr(self.get('X0')).decode()
                    if raw!='100':raise ValueError('Only actual source2116 percent100 expected')
                    self.df('D0',100.);self.set('PC',self.get('X30'));return
            return super().hook(uc,at,size,data)

        def capture_descriptor(self,display):
            self.component=self.alloc(0x100);self.holder=self.alloc(8);self.wrapper=self.alloc(0x158)
            self.call(0x31f5fc,{'X0':self.wrapper})
            self.w(self.holder,'Q',self.wrapper);self.w(self.component+0x40,'Q',self.holder);self.w(self.component+0x48,'i',-1)
            self.gate_mode='descriptor';self.trace=[]
            try:self.call(0x9d40cc,{'X0':self.component,'W1':display,'W2':3,'W3':0,'X4':self.cpp_string(b'idle'),'W5':1,'W6':0})
            finally:self.gate_mode=None
            return list(self.trace)

        def body_prefix(self):
            context=self.alloc(0x400);config=self.alloc(0x100);self.w(0x2528db0,'Q',context);self.w(0x2528220,'Q',config)
            self.w(self.r(0x2506fc8,'Q')[0],'B',0)
            self.frontier=None;self.gate_mode='body-prefix'
            try:self.call(0x9d5104,{'X0':self.component,'X1':self.display,'X2':self.model,'W3':3,'W4':0,'X5':self.cpp_string(b'idle'),'W6':0})
            finally:self.gate_mode=None
            if not self.frontier:raise ValueError('Original main body load frontier not reached')
            return self.frontier

        def after_body_condition(self):
            from unicorn import UC_HOOK_CODE
            stops=[]
            def stop(uc,at,size,data):
                if at==0x9d5404:stops.append(at);self.set('PC',self.EXIT)
            handle=self.uc.hook_add(UC_HOOK_CODE,stop,begin=0x9d5404,end=0x9d5404)
            self.trace=[];self.gate_mode='post-body'
            try:self.call(0x9d5230,{'X19':self.component,'X21':self.display,'X24':self.model,'X23':self.cpp_string(b'idle'),'W22':3},stack=(0,0))
            finally:self.gate_mode=None;self.uc.hook_del(handle)
            if stops!=[0x9d5404]:raise ValueError('Original conditional effect loop did not finish')
            return list(self.trace)
    return GateProbe


def native_node_controls(image):
    from creation_elf_wr_animation_probe import prepared_pose
    from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_WRITE
    p,reader,skin,data,nodes=prepared_pose(image)
    if NODE not in p.native_nodes:raise ValueError('Own Model62 source requested hand node not actually constructed')
    wrapper=p.alloc(0xe20);p.w(wrapper+8,'Q',p.root);effect_holder=p.alloc(8);text=p.alloc(len(NODE)+1);p.uc.mem_write(text,NODE.encode()+b'\0')
    before=bytes(p.uc.mem_read(p.root,0x140));p.invoke(0x335ec8,X0=wrapper,X1=text,X2=effect_holder)
    after=bytes(p.uc.mem_read(p.root,0x140))
    if before!=after:raise ValueError('Null BEFF should not mutate source root')
    # Execute real3360a0's root/path gates. A valid request stops at the
    # original effect loader entry, never returns an invented result.
    path=p.alloc(len(EFFECT)+1);p.uc.mem_write(path,EFFECT.encode()+b'\0');empty=p.alloc(1);requests=[]
    def effect_boundary(uc,at,size,data):
        requests.append({'entry':hex(at),'path':p.c(p.get('X1')).decode(),'arg2':p.get('W2'),
                         'stoppedBeforeEffectFactory':True,'resultNotSupplied':True});p.set('PC',p.EXIT)
    loader=p.uc.hook_add(UC_HOOK_CODE,effect_boundary,begin=0x3768e0,end=0x3768e0)
    effect_gates=[]
    try:
        for name,root,pointer in(('no-body',0,path),('no-path',p.root,0),('empty-path',p.root,empty),('body-and-source-path',p.root,path)):
            p.w(wrapper+8,'Q',root);requests.clear();p.invoke(0x3360a0,X0=wrapper,X1=text,X2=pointer,W3=0)
            effect_gates.append({'control':name,'bodyIsActuallyConstructed':bool(root),'effectFactoryBoundary':list(requests),
                                 'fullModelOrEffectSuccessSupplied':False})
    finally:p.uc.hook_del(loader);p.w(wrapper+8,'Q',p.root)
    holder=p.alloc(8);p.w(holder,'Q',wrapper);component=p.alloc(0x100);p.w(component+0x40,'Q',holder)
    calls=[];writes=[]
    def observe(uc,at,size,data):calls.append({'entry':hex(at),'argument1':p.get('W1'),'argument2':p.get('W2'),'originalRoot':p.get('X0')==p.root})
    def written(uc,access,at,size,value,data):writes.append({'sourcePC':hex(p.get('PC')),'rootOffset':at-p.root,'bytes':size,'value':value})
    h=p.uc.hook_add(UC_HOOK_CODE,observe,begin=0x1362320,end=0x1362320)
    w=p.uc.hook_add(UC_HOOK_MEM_WRITE,written,begin=p.root+0x128,end=p.root+0x133)
    try:p.fragment(0x9d4fb8,0x9d4ff8,X19=component)
    finally:p.uc.hook_del(h);p.uc.hook_del(w)
    return {'sourceBodyBoneEmptyRootActuallyConstructed':True,'requestedEffectNode':NODE,
        'requestedEffectNodeFoundInOriginal110':True,'effectNodeHasNoGpuMeshAttachmentRequired':True,
        'nullEffectAttachmentEntry':'0x335ec8','nullEffectOriginalRootBytesUnchanged':before==after,
        'actualEffectRequestGates':effect_gates,
        'finalVisibleSetterFragment':['0x9d4fb8','0x9d4ff8'],'actualSourceVisibleSetterCalls':calls,
        'actualRootFlagWrites':writes,'visibleBranchEnteredAsConditionalSourceFragment':True,
        'wholeNativeBodyGpuOrEffectLoaderReturnedSuccess':False,'sourceWrapperRootStorageIsExplicitHostBinding':True}


def recover(image,output=None):
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE
    output=AREA if output is None else Path(output)
    if (output/'freeze-manifest-v1.json').exists():raise ValueError('Frozen gate evidence may not be overwritten')
    source=Sources(DEFAULT_SOURCE);rows=json.loads(INDEX.read_text())['choices'];results=[]
    for display in(2116,2703):
        row,=[r for r in rows if r['display']['ID']==display];p=gate_type()(image,source)
        trace=p.capture_descriptor(display);frontier=p.body_prefix();post=p.after_body_condition()
        results.append({'displayId':display,'sourceModelId':row['model']['ID'],'sourceModel':row['model'],
            'sourceDisplayEffects':[row['display']['Effect'+str(i)]for i in range(1,7)],
            'actualDescriptorToBodyBoundary':trace,'actualBodyLoadPrefix':frontier,'postBodyConditionalTrace':post,
            'actualMainBodyReadyReturnSupplied':False})
    candidates=source.candidates(EFFECT);raw=source.read(EFFECT)if len(candidates)==1 else None
    report={'format':'oc2-elf-female-mage2116-body-effect-gates-v1','nativeSHA256':hashlib.sha256(image.data).hexdigest(),
        'choices':results,'effectResource':{'path':EFFECT,'candidateCount':len(candidates),'sha256':hashlib.sha256(raw).hexdigest()if raw else None,
            'effectBytesDecodedOrExecuted':False},'actualOwnNodeAndNullEffectControls':native_node_controls(image),
        'sourceOrder':['mainbody virtual58 returnbit0','335b50 initialidle/334fa4','Display.Effect1..6 comma parsing','3360a0 effect request','37parts/weapon processing','1362320 body visibility'],
        'independentOutcome':'No effect result is tested before the final body-visible fragment; full body must still be genuinely constructed. Unknown BEFF is not a native global body-deny or fake effect-success rule.',
        'sourceReads':source.proofs,'fullNativeCacheModelGpuReadySupplied':False,'sharedRuntimeOrSourceFilesChanged':False}
    report['hostInterfaces']=['Verified original table rows through getter/lookup ABI; actual temporary rows copied before standalone stack reuse',
        'Allocation and bounded libc strings/atof100/stdvector<COWstring> storage, not application result replies',
        '335b50 and334fa4 void view-graph interfaces in explicitly conditional post-body fragment',
        '3360a0 request recording in the conditional effect loop; separate complete root/path gate stops before3768e0',
        'Source wrapper+8 explicitly binds an actually constructed110-node bone/empty tree; no whole model GPU readiness']
    routines={}
    for address in(0x9d40cc,0x9d4c48,0x9d5104,0x33566c,0x335b50,0x334fa4,0x3360a0,0x335ec8,0x3768e0,0x1362320,0x139a2d0):
        meta,lines=image.routine(address);file=hex(address)+'.asm';(output/file).write_text('\n'.join(lines)+'\n')
        routines[hex(address)]={**meta,'sha256':hashlib.sha256(image.read(int(meta['start'],16),meta['size'])).hexdigest(),'file':file}
    report['sourceRoutines']=routines
    report['sourceClassIndexSHA256']=sha(INDEX)
    write(output/'display-gates-v1.json',report);return report

if __name__=='__main__':
    from analyze_native_resources import NativeImage
    result=recover(NativeImage((ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so').read_bytes()))
    print(json.dumps({'choices':len(result['choices']),'postBody':[r['postBodyConditionalTrace']for r in result['choices']],'node':result['actualOwnNodeAndNullEffectControls']}))
