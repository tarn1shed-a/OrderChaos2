"""Original984 texture override gates with explicit reflected-name fixtures.

The real325ce0/325e5c/14006c4 instructions run. Material enumeration and
interned strings are interfaces; compiled reflection and texture/GPU success
are never inferred from the source effect sampler list.
"""
import argparse,hashlib,json,tempfile
from pathlib import Path
from source_physics import SourcePhysics
from tutorial_npc_catalog_probe import CatalogProbe
from tutorial_map_geometry import local_output
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from bdae_convert import BDAE
from scene_sampling import material_samplers,effect_profile_samplers
from scene_render_state import effect_render_state

ROOT=Path(__file__).resolve().parents[1]
FORMAT='oc2-npc984-ut-overrides-v1'
MODEL='model/item/weapon/5_polearm/oc2_polearm_1_qte_weapon/oc2_polearm_1_qte_weapon.bdae'
PINS={
 0x325ce0:(380,'fa2ce5f5e13b6ef909bbc928675a69ed1411ba5c26ec80592db3c4fd341897e8'),
 0x325e5c:(984,'49d9ba9d72fd0f780b372174a921ad14b8181eab332a29d0117dfc8b4f6b1ff9'),
 0x14006c4:(204,'6790121ddfe4612bc48de8c136f3c4bd87315f9c1d440883290e4110d88de49a'),
}


class OverrideProbe(SourcePhysics):
    COUNT=SourcePhysics.EXIT+0x900
    MATERIAL=SourcePhysics.EXIT+0x910

    def __init__(self,image):
        for at,(size,digest)in PINS.items():
            if hashlib.sha256(image.read(at,size)).hexdigest()!=digest:raise ValueError('Original984 override consumer differs')
        super().__init__(image)
        from unicorn import UC_HOOK_CODE
        for at in[self.COUNT,self.MATERIAL,0x11ddd2c,0x143f5c4,0x13dc85c,0x14006c4,0x325e5c]:
            self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=at,end=at)
        self.names={};self.intern_queries=[];self.lookups=[];self.consumer_calls=[];self.frontier=None;self.texture_set=False

    def text(self,value):
        raw=value.encode();p=self.alloc(len(raw)+1);self.uc.mem_write(p,raw+b'\0');return p

    def intern(self,value):
        if value not in self.names:
            pointer=self.alloc(24+len(value.encode())+1);self.w(pointer+0x10,'I',10000)
            self.uc.mem_write(pointer+24,value.encode()+b'\0');self.names[value]=pointer
        return self.names[value]

    def hook(self,uc,at,size,data):
        if at==self.COUNT:self.set('W0',1)
        elif at==self.MATERIAL:self.set('X0',self.material)
        elif at==0x11ddd2c:
            name=self.cstr(self.get('X1')).decode()
            if self.get('W2')!=0 or self.r(self.get('X0'),'I')[0]!=len(name.encode())+1:raise ValueError('Uncovered original interner input')
            self.intern_queries.append(name);self.set('X0',self.intern(name))
        elif at==0x14006c4:
            self.lookups.append({'name':self.cstr(self.get('X1')).decode(),'start':self.get('W2'),'actualOriginalLookupExecuted':True});return
        elif at==0x325e5c:
            self.consumer_calls.append({'sampler':self.cstr(self.get('X1')).decode(),'path':self.cstr(self.get('X2')).decode()});return
        elif at==0x143f5c4:
            if self.get('X2')!=0:raise ValueError('Uncovered original texture request flags')
            self.frontier={'kind':'original-named-texture-request-boundary','path':self.cstr(self.get('X1')).decode(),'textureCreated':False}
            self.set('PC',self.EXIT);return
        elif at==0x13dc85c:
            self.texture_set=True;raise ValueError('Texture success must not be fabricated')
        elif self.imports.get(at)=='snprintf':
            if self.cstr(self.get('X2'))!=b'texture/%s.tga':raise ValueError('Original override format changed')
            raw=b'texture/'+self.cstr(self.get('X3'))+b'.tga';n=self.get('X1')
            uc.mem_write(self.get('X0'),raw[:max(0,n-1)]+b'\0');self.set('W0',len(raw))
        else:return super().hook(uc,at,size,data)
        self.set('PC',self.get('X30'))

    def request(self,names,channel,stem,*,part=True):
        if not isinstance(names,list)or len(names)>16 or any(not isinstance(n,str)or not n or'\0'in n or len(n.encode())>96 for n in names)or len(set(names))!=len(names):raise ValueError('Explicit bounded reflected-name fixture required')
        if type(channel)is not int or not 0<=channel<=3 or not isinstance(stem,str)or'\0'in stem or len(stem.encode())>96:raise ValueError('Bounded explicit override input required')
        self.frontier=None;self.texture_set=False;self.lookups=[];self.intern_queries=[];self.consumer_calls=[]
        model,node,vt,effect,table=self.alloc(0xe20),self.alloc(0x200),self.alloc(0x200)+32,self.alloc(0x100),self.alloc(max(24,len(names)*24))
        self.w(node,'Q',vt);self.w(node+8,'I',10000);self.w(vt-0x20,'q',0);self.w(vt+0x148,'Q',self.COUNT);self.w(vt+0x138,'Q',self.MATERIAL)
        self.material=self.alloc(0x40);self.w(self.material,'IQ',10000,0);self.w(self.material+8,'Q',effect)
        self.w(effect+0x1a,'H',len(names));self.w(effect+0x40,'Q',table)
        for i,name in enumerate(names):self.w(table+i*24,'Q',self.intern(name))
        slot=18;self.w(model+0x158+slot*0x38,'Q',node if part else 0)
        # The positive control stops before this manager is dereferenced.
        manager,services=self.alloc(0x100),self.alloc(0x400);self.w(0x25276f8,'Q',manager);self.w(manager+0x10,'Q',services)
        value=self.text(stem);result=self.call(0x325ce0,{'X0':model,'W1':slot,'W2':channel,'X3':value})
        return {'explicitCompleteReflectedNames':names,'explicitChannel':channel,'explicitStem':stem,'explicitPartPresent':part,
          'originalConsumerCalls':self.consumer_calls,'originalLookups':self.lookups,'internQueries':self.intern_queries,
          'reachedBoundary':self.frontier,'nativeReturnRegister':result,'overrideCachePointer':self.r(model+slot*0x38+channel*8+0x168,'Q')[0],
          'textureSet':self.texture_set,'actualCompiledReflectionObserved':False,'actualActivityObserved':False}


def recover(image,source=DEFAULT_SOURCE):
    sources=Sources(source);selection=CatalogProbe(image,sources);native=OverrideProbe(image)
    slots=selection.slots(200029,0);request=selection.resource(slots['requests'][0]['slot'],200029)
    if request['path']!=MODEL or request['textureOverrides']!=['','oc2_polearm_1_qte_weapon','oc2_polearm_1_qte_weapon']:raise ValueError('Original984 weapon request differs')
    with tempfile.TemporaryDirectory(prefix='oc2-npc984-ut-')as tmp:
        model_path=Path(tmp)/'weapon';model_path.write_bytes(sources.read(MODEL));reader=BDAE(model_path)
        source_samplers=material_samplers(reader)
        fx_path=Path(tmp)/'ut_solid';fx_path.write_bytes(sources.read('ut_solid.bdae'));fx_reader=BDAE(fx_path)
        samplers=effect_profile_samplers(fx_reader);render=effect_render_state(fx_reader)
        if len(source_samplers)!=1 or source_samplers[0]['effectPath']!='ut_solid.bdae'or set(source_samplers[0]['samplers'])!={'texture'}:raise ValueError('Original984 ordinary source samplers differ')
        shader_proofs={}
        for profile in render['profiles']:
            for field in['vertexShader','fragmentShader']:
                shader=profile[field];raw=sources.read(shader['file']);shader_proofs[shader['file']]={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
                if shader['defines']:raise ValueError('Unexpected originalUT source defines')
        cases=[native.request(['texture'],i,s)for i,s in enumerate(request['textureOverrides'])]
        controls=[native.request(['texture'],0,'oc2_polearm_1_qte_weapon'),native.request(['texture','normalMap'],1,'oc2_polearm_1_qte_weapon'),
            native.request([],1,'oc2_polearm_1_qte_weapon'),native.request(['texture'],1,'oc2_polearm_1_qte_weapon',part=False)]
    from native_character_presentation_probe import PresentationProbe
    factory_probe=PresentationProbe(image);factory=factory_probe.rebuild_factory();macro_rows=[]
    if factory['flags']!=[0x807]:raise ValueError('Original modular initial factory flags differ')
    for bit in range(16):
        if factory['flags'][0]&(1<<bit):
            pointer=factory_probe.r(0x250afc0+bit*8,'Q')[0]
            macro_rows.append({'bit':bit,'sourceStringAddress':hex(pointer),'sourceText':factory_probe.cstr(pointer).decode()})
    return {'format':FORMAT,'originalWeaponRequest':request,'sourceMaterialSamplers':source_samplers,'sourceEffectSamplerProfiles':samplers,
      'sourceEffectRenderProfiles':render,'sourceShaderProofs':shader_proofs,'sourceDeclaredNameFixtures':cases,'explicitControlFixtures':controls,
      'originalInitialModularFactoryFixture':factory,'originalFactoryMacroStrings':macro_rows,'actual984FactoryMacroLifetimeKnown':False,
      'completeCompiledEffectReflectionKnown':False,'actualMaterialOverridesKnown':False,'actualAmbientFogInputsKnown':False,
      'limits':['Source declarations are not original compiled reflection. Source-name-only cases prove conditional consumers, not live no-op.',
        'Positive names reach original texture request boundary without supplying successful texture/material/GPU.',
        'No replacement shader/light/fog values or activity actor is supplied; existing frozen candidates stay unchanged.'],
      'sourceProofs':sources.proofs,'productionChanged':False,'savesReadOrWritten':False}


if __name__=='__main__':
    from analyze_native_resources import NativeImage
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--native',type=Path,default=ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so')
    cli.add_argument('--source',type=Path,default=DEFAULT_SOURCE);cli.add_argument('--output',type=Path,required=True);args=cli.parse_args();output=local_output(args.output)
    if output.exists():cli.error('Existing984 UT evidence stays preserved')
    result=recover(NativeImage(args.native.read_bytes()),args.source);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'output':str(output),'sourceCases':len(result['sourceDeclaredNameFixtures']),'controls':len(result['explicitControlFixtures']),'actualCompiledReflectionObserved':False}))
