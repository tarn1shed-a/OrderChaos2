"""Run the original track-blender property mask on original human targets.

This is not a hand-written upper-body list. The 27 names, four special names,
matching checks, weights, index cache and fallback all come from source CPU.
Loaded child metadata getters are the explicit host boundary; no GPU claim.
"""
import hashlib
import json
import tempfile
from pathlib import Path
from character_human_combat_probe import ROOT,MODEL,ANIMATION
from character_elf_male_binding import ElfControllerProbe,source_controller
RAW=ROOT/'analysis/raw/character-human-queue-bones-20261115'
DATA=ROOT/'analysis/raw/character-human-combat-20261115/candidate-v1/assets/character.json'


class HumanMaskProbe(ElfControllerProbe):
    def __init__(self,*args):
        self.mask_mode=False;self.weight_calls=[];self.manager=None
        super().__init__(*args)
        from unicorn import UC_HOOK_CODE
        for at in(0x1103d9c,0x110c954):self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=at,end=at)

    def hook(self,uc,at,size,data):
        if at==0x1103d9c:self.manager=self.get('X0');return
        if self.mask_mode and at==0x110c954:
            import struct
            self.weight_calls.append({'index':self.get('W1'),'weight':struct.unpack('<f',struct.pack('<I',self.get('S0')&0xffffffff))[0],'originalSetterExecuted':True});return
        return super().hook(uc,at,size,data)

    def fragment(self,start,end,**regs):
        self.regs()
        for key,value in regs.items():self.set(key,value)
        self.run(start,end)

    def source_names(self):
        # Original static initializer prologue establishes X20=25282e0.
        # X9 is unrelated zero storage on entry to this bounded fragment.
        self.fragment(0x2a4538,0x2a4578,X20=0x25282e0,X9=self.alloc(8))
        special=[self.c(self.r(0x25282e0+0x270+i*8,'Q')[0]).decode()for i in range(4)]
        lower=[self.c(self.r(0x24122c8+i*8,'Q')[0]).decode()for i in range(27)]
        return lower,special

    def mask(self,*,mismatch_descriptor=False):
        if self.manager is None:raise ValueError('Actual original animation metadata must be loaded first')
        managers=[self.manager,self.manager]
        if mismatch_descriptor:
            # A clearly marked negative loaded-view fixture, not a new source
            # file or renamed gameplay bone. Only descriptor type0 is changed.
            manager=self.alloc(0x100);self.uc.mem_write(manager,bytes(self.uc.mem_read(self.manager,0x100)))
            count=self.r(manager+0x40,'I')[0];old=self.r(manager+0x10,'Q')[0];targets=self.alloc(count*8)
            self.uc.mem_write(targets,bytes(self.uc.mem_read(old,count*8)));old_target=self.r(targets,'Q')[0];target=self.alloc(16);self.uc.mem_write(target,bytes(self.uc.mem_read(old_target,16)));self.w(target+8,'I',10);self.w(targets,'Q',target);self.w(manager+0x10,'Q',targets)
            managers[1]=manager
        root=self.alloc(0x120);weights=self.alloc(8)
        self.w(root+0x48,'3Q',weights,weights+8,weights+8);self.w(weights,'2f',0,1)
        self.w(root+0x90,'I',1);self.w(root+0xfa,'B',1)
        # The complete frame-context factory is not reconstructed. Supply
        # bounded vectors/bitsets, then run the real fill, descriptor matching,
        # name checks, setter and special-index code without changing them.
        count=len(self.channels);helper=self.alloc(0x48);values=self.alloc(count*4)
        self.w(helper+0x10,'3Q',values,values+count*4,values+count*4)
        for off in(0x30,0x38,0x40):
            bits=self.alloc(0x20);buffer=self.alloc(((count+31)//32)*4);self.w(bits+0x10,'Q',buffer);self.w(helper+off,'Q',bits)
        self.invoke(0x11036a0,time=0,X0=helper)
        self.fragment(0x371a74,0x371aa0,X19=root)
        self.regs();sp=self.get('SP');self.w(sp,'4Q',managers[0],managers[0],managers[1],helper);self.set('X19',root);self.set('X20',managers[1])
        from unicorn import UC_HOOK_CODE
        boundaries=[]
        def stop(uc,at,size,data):
            if at in(0x371ea4,0x371ee0,0x371eb4):boundaries.append(at);self.set('PC',self.EXIT)
        hook=self.uc.hook_add(UC_HOOK_CODE,stop)
        self.weight_calls=[];self.mask_mode=True
        try:self.run(0x371c58)
        finally:self.mask_mode=False;self.uc.hook_del(hook)
        if len(boundaries)!=1:raise ValueError('Original mask fragment did not reach its boundary')
        if boundaries[0]==0x371ee0:self.fragment(0x371f58,0x371fd8,X19=root)
        return {'sourceProperties':count,'inputLayerRootWeights':[0,1],'afterLayerRootWeights':list(self.r(weights,'2f')),'propertiesCompatible':bool(self.r(root+0xb8,'B')[0]),'cachedSpecialIndices':list(self.r(root+0xbc,'8i')),'originalWeightSetterCalls':list(self.weight_calls),'sourcePropertyWeights':list(self.r(values,str(count)+'f')),'negativeDescriptorFixture':mismatch_descriptor,'originalEntry':'0x371a40','executedFragments':[['0x371a74','0x371aa0'],['0x371c58',hex(boundaries[0])]]+([['0x371f58','0x371fd8']]if boundaries[0]==0x371ee0 else[]),'originalWeightFill':'0x11036a0','originalWeightSetter':'0x110c954','maskCreatedByOriginalCPU':True,'distinctBonePoseApplied':False,'originalFrameContextFactoryExecuted':False,'loadedDescriptorAndBitsetStorageHostInterface':True}


def recover(image,source):
    from map_loading_evidence import Sources
    from bdae_convert import BDAE
    from bdae_animation import BDAEAnimation
    from character_world_motion_probe import MODELS
    sources=Sources(source);data=json.loads(DATA.read_text());expected=MODELS['male']
    with tempfile.TemporaryDirectory(prefix='oc2-original-human-mask-')as tmp:
        files=[]
        for name,key in((MODEL,'bodySHA256'),(ANIMATION,'animationSHA256')):
            path=Path(tmp)/Path(name).name;raw=sources.read(name)
            if hashlib.sha256(raw).hexdigest()!=expected[key]:raise ValueError('Original human source identity differs')
            path.write_bytes(raw);files.append(path)
        reader,animation=BDAE(files[0]),BDAEAnimation(files[1]);skin=source_controller(reader,{'meshes':[data['meshes'][0]]},data['rig']['nodes'],0)
        probe=HumanMaskProbe(image,reader,reader,skin,0);probe.animation(animation);lower,special=probe.source_names();good=probe.mask();bad=probe.mask(mismatch_descriptor=True)
        routines={}
        for at in(0x2a3f6c,0x371a40,0x11036a0,0x110c954,0x372318,0x3732ac,0x3734f4):
            m,_=image.routine(at);routines[hex(at)]={'start':m['start'],'bytes':m['size'],'sha256':hashlib.sha256(image.read(int(m['start'],16),m['size'])).hexdigest()}
        result={'format':'oc2-human-original-layer-property-mask-v1','nativeSHA256':hashlib.sha256(image.data).hexdigest(),'sourceProofs':sources.proofs,'sourceBodySHA256':expected['bodySHA256'],'sourceAnimationSHA256':expected['animationSHA256'],'bodyDataSHA256':hashlib.sha256(DATA.read_bytes()).hexdigest(),'routines':routines,'originalLowerNames':lower,'originalSpecialNames':special,'sourcePropertyOrder':[{'index':i,'node':p['node'],'type':p['type']}for i,p in enumerate(probe.channels)],'compatible':good,'incompatibleFixture':bad,'bodyNativeTreeAndPropertyManagerExecuted':True,'originalGPUOrCompleteBlendClaimed':False,'next':'Execute372318/3732ac/3734f4 property composition and real target setters before admitting mixed poses'}
        result['bodyDataCanonicalSHA256']=hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest();result['sha256']=mask_hash(result);return result


def mask_hash(report):
    return hashlib.sha256(json.dumps({k:v for k,v in report.items()if k!='sha256'},sort_keys=True,separators=(',',':')).encode()).hexdigest()


def bind_original_mask(report,data):
    from bdae_character import aliases
    from analyze_native_resources import NATIVE_SHA256
    if not isinstance(report,dict)or report.get('format')!='oc2-human-original-layer-property-mask-v1'or report.get('sha256')!=mask_hash(report)or report.get('nativeSHA256')!=NATIVE_SHA256 or report.get('originalGPUOrCompleteBlendClaimed')is not False or report.get('compatible',{}).get('distinctBonePoseApplied')is not False:raise ValueError('Verified original property mask required')
    if report.get('bodyDataCanonicalSHA256')!=hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest():raise ValueError('Original human body data differs')
    by_name=aliases(data['rig']['nodes']);order=report['sourcePropertyOrder'];weights=report['compatible']['sourcePropertyWeights']
    if len(order)!=135 or len(weights)!=len(order)or not report['compatible']['propertiesCompatible']:raise ValueError('Complete original compatible human property order required')
    result=[]
    for i,(row,weight)in enumerate(zip(order,weights)):
        if row['index']!=i or row['node']not in by_name or row['type']not in(1,5,10)or weight not in(0.,.5,1.):raise ValueError('Uncovered original property binding')
        result.append({'sourcePropertyIndex':i,'node':by_name[row['node']],'sourceNode':row['node'],'sourceType':row['type'],'originalPropertyWeight':weight})
    return result


if __name__=='__main__':
    from analyze_native_resources import NativeImage
    from resource_packs import DEFAULT_SOURCE
    out=RAW/'source-property-mask-final.json'
    if out.exists():raise ValueError('Preserve existing source property-mask evidence')
    result=recover(NativeImage((ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so').read_bytes()),DEFAULT_SOURCE)
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'properties':result['compatible']['sourceProperties'],'compatible':result['compatible']['propertiesCompatible'],'maskWrites':len(result['compatible']['originalWeightSetterCalls']),'negativeCompatible':result['incompatibleFixture']['propertiesCompatible']}))
