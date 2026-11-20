"""Index the seven remaining Class bodies through the original bank/range path.

The native resource-reference carrier is an explicit offline byte owner. It is
not a loaded game resource/cache reply, model/GPU readiness or an actor grant.
Original subresource construction, prefix lookup and range clocks execute CPU.
"""
import argparse,hashlib,json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
NATIVE=ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'
INDEX=ROOT/'analysis/raw/creation-class-source-20261116/source-v2.json'
OLD=ROOT/'analysis/raw/creation-class-source-20261116/animation-v2.json'
INDEX_SHA='ae5517200752946de28884cdebc38dd38fa016ffe1a8930a7a6041e984491d9f'
OLD_SHA='e8309a790fd7530d348df4d12bedfaea96194ff1e21abc250ec9b03b7178b0f5'
BODIES={(0,1):'human-female',(1,0):'mendel-male',(1,1):'mendel-female',
 (2,0):'elf-male',(3,0):'orc-male',(3,1):'orc-female',(4,0):'kartan'}
CODES=('wr','rg','mg','ds','mk')
sha=lambda b:hashlib.sha256(b).hexdigest()
write=lambda p,x:p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def verify_inputs():
    if sha(INDEX.read_bytes())!=INDEX_SHA or sha(OLD.read_bytes())!=OLD_SHA:
        raise ValueError('Frozen source selection/range receipts changed')
    original=json.loads(INDEX.read_text());previous=json.loads(OLD.read_text())
    choices=[r for r in original['choices']if(r['uiRace'],r['gender'])in BODIES]
    if len(choices)!=35 or any(sum((r['uiRace'],r['gender'],r['uiProfessionIndex'])==(a,b,i)for r in choices)!=1
                                  for a,b in BODIES for i in range(5)):
        raise ValueError('Exact seven-body/five-profession source matrix required')
    return choices,previous


def path_probe_type():
    from creation_elf_mage_gate_probe import gate_type
    from unicorn import UC_HOOK_CODE
    base=gate_type()
    class PathProbe(base):
        def __init__(self,*args):
            self.bank_mode=False;self.bank_requests=[]
            super().__init__(*args)
            self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=0x7d6244,end=0x7d6244)
        def hook(self,uc,at,size,data):
            if self.bank_mode:
                if self.imports.get(at)=='sprintf':
                    if self.cstr(self.get('X1'))!=b'%sanim/animations.bdae':raise ValueError('Wrong original bank format')
                    text=self.cstr(self.get('X2'))+b'anim/animations.bdae'
                    if len(text)>=0x100:raise ValueError('Original bounded bank name exceeded')
                    uc.mem_write(self.get('X0'),text+b'\0');self.set('W0',len(text));self.set('PC',self.get('X30'));return
                if at==0x7d6244:
                    self.bank_requests.append(self.cstr(self.r(self.get('X1'),'Q')[0]).decode())
                    self.set('PC',self.EXIT);return
            return super().hook(uc,at,size,data)
        def path(self,display):
            self.capture_descriptor(display);frontier=self.body_prefix();view=self.r(self.holder,'Q')[0]
            directory=self.cstr(self.r(view+0x90,'Q')[0]).decode();base_name=self.cstr(self.r(view+0x98,'Q')[0]).decode()
            engine=self.alloc(0x700);self.w(engine+8,'Q',view);self.bank_requests=[];self.bank_mode=True
            # Actual constructor suffix starts after queue initialization; it
            # only formats the native owner directory, then stops BEFORE cache.
            try:self.call(0x32beb4,{'X19':engine})
            finally:self.bank_mode=False
            if len(self.bank_requests)!=1:raise ValueError('Native bank cache frontier not reached')
            return {'sourceBodyPath':frontier['path'],'ownerDirectoryAt90':directory,'ownerBasenameAt98':base_name,
                    'bankCacheRequest':self.bank_requests[0],'modelResourceLoaderExecuted':False,
                    'cacheLookupReturned':False,'GPUOrModelReadySupplied':False}
    return PathProbe


def selection_probe_type():
    from source_physics import SourcePhysics
    from unicorn import UC_HOOK_CODE
    class Selection(SourcePhysics):
        def __init__(self,image):
            super().__init__(image);self.active=False;self.result=None
            for a in(0x53d3e8,0x331a18):self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=a,end=a)
        def hook(self,uc,a,n,d):
            if self.active and self.imports.get(a)=='printf':
                self.set('W0',0);self.set('PC',self.get('X30'));return  # Diagnostic sink only.
            if self.active and a in(0x53d3e8,0x331a18):
                self.result=({'displayId':self.get('W1'),'arg2':self.get('W2'),'arg3':self.get('W3')}
                  if a==0x53d3e8 else{'name':self.cstr(self.get('X2')).decode(),'flags':self.get('W3'),
                    'speed':self.gf('S0'),'begin':self.gf('S1'),'blend':self.gf('S2')})
                self.set('PC',self.EXIT);return
            return super().hook(uc,a,n,d)
        def selection(self,row):
            ctl=self.alloc(0x300);self.w(ctl+0x5c,'3i',row['uiRace'],row['gender'],-1)
            self.active=True
            try:
                self.call(0x538b74,{'X0':ctl,'W1':0xffffffff,'W2':0xffffffff,'W3':row['uiProfessionIndex']});request=self.result
                self.w(ctl+0x88,'Q',self.alloc(0x180))
                self.call(0x538c1c,{'X19':ctl,'W20':row['uiProfessionIndex']});show=self.result
            finally:self.active=False
            if request!=row['request']:raise ValueError('Real original Class display request differs')
            return {'displayRequest':request,'displayConstructorExecuted':False,'showRequest':show,
                    'showIsExplicitConditionalPostDisplayBranch':True,'displayReadyResultSupplied':False}
    return Selection


def bank_probe_type():
    from native_bres_world_bounds_probe import NativeBresWorldBoundsProbe
    class Bank(NativeBresWorldBoundsProbe):
        def invoke(self,a,**regs):
            self.regs()
            for k,v in regs.items():self.set(k,v)
            self.run(a);return self.get('X0')
        def build(self,reader):
            self.reader=reader;self.loaded=self.load(reader.b);info=self.loaded['info']
            count=self.r(info+0x64,'I')[0];package=info+0x68+self.r(info+0x68,'i')[0]
            if count!=1 or self.c(self.r(package,'Q')[0])!=b'package0':raise ValueError('Exact source package0 required')
            count=self.r(package+0x1c,'I')[0];default=package+0x20+self.r(package+0x20,'i')[0]
            if count!=1 or self.c(self.r(default,'Q')[0])!=b'default':raise ValueError('Exact own source default object required')
            # Native 1101eb0 reads one source animation-reference name and builds
            # its integer resource-index array. Here only the existing byte owner
            # is provided, not its generic file/provider loader or cache success.
            count=self.r(package+0x14,'I')[0];refs=package+0x18+self.r(package+0x18,'i')[0]
            if count!=1 or self.c(self.r(refs,'Q')[0])!=b'animations.bdae':raise ValueError('Own bank resource reference differs')
            res,fac=self.alloc(0x100),self.alloc(16);self.w(res+8,'I',10000);self.w(res+0x48,'Q',self.loaded['main']);self.w(fac,'Q',0x244d308)
            parent=self.alloc(0x90);self.w(parent+0x18,'2Q',res,fac);self.w(parent+0x28,'Q',package)
            resources=self.alloc(16);self.w(resources,'2Q',res,0);context=self.alloc(0x100);self.w(context+0x80,'Q',resources)
            self.w(parent+0x30,'Q',context);indexes=self.alloc(4);self.w(indexes,'I',0);self.w(parent+0x38,'3Q',indexes,indexes+4,indexes+4)
            self.object=self.alloc(0x80);self.invoke(0x10f92d8,X0=self.object,X1=parent,X2=default,X3=0)
            if self.r(self.object,'Q')[0]!=0x244be80:raise ValueError('Actual original range-object vtable differs')
            self.lookup=self.r(0x244be80+0x18,'Q')[0]
            if self.lookup!=0x10f9ee0:raise ValueError('Original range lookup slot differs')
            self.range_count=self.r(default+0x10,'I')[0]
            self.range_refs=default+0x14+self.r(default+0x14,'i')[0]
            if self.range_count!=(self.r(self.object+0x48,'Q')[0]-self.r(self.object+0x40,'Q')[0])//8:
                raise ValueError('Actual original constructor range-reference count differs')
            self.names=[self.c(self.r(self.range_refs+i*24,'Q')[0]).decode()for i in range(self.range_count)]
            if self.names!=sorted(self.names):raise ValueError('Source lower-bound table is not sorted')
            return {'sourcePackage':'package0','sourceObject':'default','sourceResource':'animations.bdae',
                    'sourceRangeReferences':self.range_count,'nativeConstructor':'0x10f92d8',
                    'nativeLookup':'0x10f9ee0 -> 0x10f9e10',
                    'byteOwnerAndResourceIndex0AreExplicitHostCarriers':True,
                    'fullBankFactoryOrCacheReadyClaimed':False}
        def query(self,name):
            text=self.alloc(len(name)+2);self.uc.mem_write(text,name.encode()+b'-\0')
            pointer=self.invoke(self.lookup,X0=self.object,X1=text)
            if not pointer:return None
            start=self.r(self.object+0x40,'Q')[0];index=(pointer-start)//8
            if not 0<=index<self.range_count or pointer!=start+index*8:raise ValueError('Native range pair escaped its own vector')
            resource,range_index=self.r(pointer,'2I');rows=self.reader.ranges()
            if resource!=0 or range_index>=len(rows):raise ValueError('Original range pair outside own resource/ranges')
            ref=self.names[index];selected=rows[range_index]
            # Original lookup is lower_bound+strstr on the full requested prefix.
            if name+'-'not in ref or selected['sourceName']!=self.c(self.r(self.range_refs+index*24+16,'Q')[0]).decode():
                raise ValueError('Native prefix/ref/global-range relationship differs')
            header=self.alloc(32);self.w(header,'Ii',1,4);_,ranges=self.reader.section(84)
            src=self.loaded['info']+0x58+self.r(self.loaded['info']+0x58,'i')[0]+range_index*24
            self.uc.mem_write(header+8,bytes(self.uc.mem_read(src,24)))
            clock=self.alloc(0x70);self.invoke(0x1195f3c,X0=clock);self.invoke(0x1196824,X0=clock,X1=header)
            times=self.r(clock+0x20,'2f')
            if times!=(selected['startMs'],selected['endMs']):raise ValueError('Actual native range clock differs')
            return {'requestedName':name,'requestedSubresourceKey':name+'.bdae','prefix':name+'-',
                    'sourceRangeReferenceIndex':index,'resourceIndex':resource,'sourceRangeIndex':range_index,
                    'sourceRange':selected,'nativeClockMs':list(times)}
    return Bank


def recover(output,source=None):
    from analyze_native_resources import NativeImage
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE
    from bdae_animation import BDAEAnimation
    from character_world_motion_probe import parse_source_clock
    output=Path(output).resolve()
    if ROOT/'analysis/raw'not in output.parents or output.exists():raise ValueError('New ignored raw output directory required')
    output.mkdir(parents=True);choices,previous=verify_inputs();image=NativeImage(NATIVE.read_bytes());sources=Sources(source or DEFAULT_SOURCE)
    prepath='preload/animations_bdae_list.txt';preload=sources.read(prepath);(output/'preload-list.txt').write_bytes(preload)
    prelines=preload.decode('ascii').splitlines();paths=path_probe_type()(image,sources);selection=selection_probe_type()(image);bodies=[];combinations=[]
    idle=previous['originalTables']['0x2415cf8'];idle02=previous['originalTables']['0x2415d30']
    reloc={r['r_offset']:r['r_addend']for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    for address,want in((0x2415cf8,idle),(0x2415d30,idle02)):
        got=[image.read(reloc[address+i*8],100).split(b'\0')[0].decode()for i in range(7)]
        if got!=want:raise ValueError('Original idle/idle02 pointer table changed')
    if reloc.get(0x244be80+0x18)!=0x10f9ee0 or reloc.get(0x244be80+0x10)!=0x10f9e10:
        raise ValueError('Original default range-object dispatch differs')
    oldbanks={b['path']:b for b in previous['ownAnimationRanges']}
    for(a,b),key in BODIES.items():
        rows=[r for r in choices if(r['uiRace'],r['gender'])==(a,b)];frontiers=[];selected=[]
        for row in rows:
            front=paths.path(row['display']['ID']);sel=selection.selection(row)
            if front['sourceBodyPath']!=row['model']['ModelPath']:raise ValueError('Original wrapper path differs from model table')
            if sel['showRequest']['name']!='login_'+CODES[row['uiProfessionIndex']]+'_show':raise ValueError('Actual show producer differs')
            frontiers.append(front);selected.append(sel)
        banks={r['bankCacheRequest']for r in frontiers}
        if len(banks)!=1:raise ValueError('This body has multiple actual bank requests; must be classified separately')
        path,=banks
        if prelines.count(path)!=1:raise ValueError('Own exact bank not uniquely listed by original preload input')
        raw=sources.read(path)
        if path not in oldbanks or sha(raw)!=oldbanks[path]['sha256']:raise ValueError('Own source bank differs from frozen original index')
        local=output/(key+'-bank.bdae');local.write_bytes(raw);reader=BDAEAnimation(local)
        engine=bank_probe_type()(image);constructor=engine.build(reader);names=[];query_rows=[]
        for i,row in enumerate(rows):
            requested=(selected[i]['showRequest']['name'],idle[row['uiProfessionIndex']+1],idle02[row['uiProfessionIndex']+1])
            clip_rows=[]
            for name in requested:
                query=engine.query(name);query_rows.append({'name':name,'nativeResult':query})
                if query:names.append(name)
                clip_rows.append({'originalName':name,'virtualRequestKey':frontiers[i]['ownerDirectoryAt90']+'anim/'+name+'.bdae',
                    'literalIndividualFileCandidates':len(sources.candidates(frontiers[i]['ownerDirectoryAt90']+'anim/'+name+'.bdae')),
                    'nativeRange':query,'absentExactPrefixInThisOwnBank':query is None})
            combinations.append({'body':key,'uiRace':a,'gender':b,'uiProfessionIndex':row['uiProfessionIndex'],'profession':row['profession'],
                'displayId':row['display']['ID'],'modelId':row['model']['ID'],'modelFlags':row['model']['Flags'],
                'bodyPath':row['model']['ModelPath'],'bankPath':path,'bankSHA256':sha(raw),'sourceSelection':selected[i],
                'sourcePathFrontier':frontiers[i],'clips':clip_rows,'poseOrGPUAdmission':False})
        parsed=parse_source_clock(reader,sorted(set(names)));clocks=[]
        for clip in parsed['clips']:
            tracks=clip['tracks'];clocks.append({'name':clip['name'],'sourceRangeFrames':clip['sourceRangeFrames'],
                'sourceRangeMs':clip['sourceRangeMs'],'durationMs':clip['sourceRangeMs'][1]-clip['sourceRangeMs'][0],
                'properties':len(tracks),'nativeClock':{'timeType':3,'valueType':6,'timeComponents':1,
                    'msPerFrameBits':'0x42055555','framesPerMsBits':'0x3cf5c290','sourceValuesChanged':False},
                'channels':[{'index':j,'node':t['node'],'type':t['type'],'components':t['nativeClock']['components'],
                    'keyCount':len(t['nativeClock']['frames']),'firstFrame':t['nativeClock']['frames'][0],
                    'lastFrame':t['nativeClock']['frames'][-1],
                    'originalNativeClockSHA256':sha(json.dumps(t['nativeClock'],sort_keys=True,separators=(',',':'),allow_nan=False).encode())}
                    for j,t in enumerate(tracks)]})
        controls={name:engine.query(name)for name in('__unregistered_class_probe__', 'LOGIN_WR_SHOW')}
        if any(controls.values()):raise ValueError('Wrong-case/unregistered prefix unexpectedly admitted')
        bodies.append({'key':key,'uiRace':a,'gender':b,'path':path,'sha256':sha(raw),'sourcePackage':constructor,
            'sourceProof':sources.proofs[path],'classCombinations':5,'uniqueRequestedClips':15,
            'nativeAdmittedPrefixes':len(set(names)),'nativeAbsentPrefixes':[r['name']for r in query_rows if r['nativeResult']is None],
            'clockIndex':clocks,'negativePrefixControls':controls,'sourceOwnRigNotReconstructedByThisIndex':True})
        write(output/(key+'-native-range-lookup.json'),{'body':key,'constructor':constructor,'queries':query_rows,'negativeControls':controls})
    routines={}
    for a in(0x3354a4,0x32bcac,0x32e4cc,0x7d586c,0x7d5ba4,0x7d5fcc,0x7d6244,0x7d62a0,0x1117584,0x11240dc,0x112be8c,0x1101eb0,0x10fa08c,0x1189dc4,0x10f92d8,0x10f91c0,0x10f9e10,0x10f9ee0):
        meta,lines=image.routine(a);(output/(hex(a)+'.asm')).write_text('\n'.join(lines)+'\n');routines[hex(a)]={'bytes':meta['size'],'sha256':sha(image.read(a,meta['size']))}
    report={'format':'oc2-creation-seven-body-bank-index-v1','nativeSHA256':sha(image.data),'originalSourceIndexSHA256':INDEX_SHA,
      'previousAnimationIndexSHA256':OLD_SHA,'preloadListSourceProof':sources.proofs[prepath],'preloadListTotalLines':len(prelines),
      'originalDispatch':{'defaultObjectVtable':'0x244be80','lookupSlot18':'0x10f9ee0','nameSlot10':'0x10f9e10',
       'preloadReader':'0x7d586c','preloadRegister':'0x7d5ba4 -> 0x1117584 -> 0x11240dc(package0) -> 0x7d62a0',
       'cachedLookup':'0x32bcac -> 0x7d6244','subresourceLookup':'0x32e4cc -> 0x10fa08c -> v18',
       'pairSemantics':'resource index + source range index; these two uint32 words are not start/end milliseconds'},
      'bodyCount':len(bodies),'classCombinationCount':len(combinations),'requestedClips':sum(len(r['clips'])for r in combinations),
      'nativeMatchedPrefixes':sum(r['nativeAdmittedPrefixes']for r in bodies),'bodies':bodies,'combinations':combinations,'originalRoutines':routines,
      'limits':['Actual default subresource constructor/query/range-clock CPU only; byte ownership and same-resource index0 are explicit offline carriers.',
       'Generic resource load, animation preload/cache registration in a live session, model/GPU readiness not executed or supplied.',
       'An absent source prefix is restricted to the exact pinned own bank; not proof that no other resource/fallback exists.',
       'Native-clock indices are not CPU pose/rig/mix or browser admission; old ten profiles remain unchanged.'],
      'sharedRuntimeChanged':False,'savesTouched':False,'browserServiceGitOrDeployment':False}
    write(output/'index-v1.json',report);return report


def main():
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--output',type=Path,required=True);args=cli.parse_args()
    r=recover(args.output);print(json.dumps({k:r[k]for k in('bodyCount','classCombinationCount','requestedClips','nativeMatchedPrefixes')}))
if __name__=='__main__':main()
