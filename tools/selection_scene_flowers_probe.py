"""Run original lightMap override selection for the two map7 flower records.

The actual342194, reflected-name lookup, texture getter/setter, C++ name copy
and UV getter/setter run. Material declarations, retained texture identities
and string interning are explicit CPU interfaces, never shader/GPU success.
"""
import argparse
import hashlib
import json
from pathlib import Path

from source_physics import SourcePhysics
from scene_lightmap_binding import verify_native
from selection_scene_candidate import ROOT,local_output,binding_rows
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE

MODEL='model/scene/region_whisper_island/whi_plant_flower005.bdae'
MODEL_SHA='5d08863bac80a932a54e9738696866d7da351e427e8b3897c1a181c142cd6b8d'
LIGHTMAP='texture/lightmap02.tga'
LIGHTMAP_SHA='822acc1f548307aeeb52e8f3ac4d376d9e6c5250043d4eb2235e88690f04a26b'
IDS=[967639024,967638880]
FORMAT='oc2-selection-flowers-lightmap-probe-v1'
PINS={
 0x13e4214:(332,'d16aeb762cf66b0c7152746940c689800ca10f534e92237a6ca005bb459c5cb2'),
 0x14006c4:(204,'6790121ddfe4612bc48de8c136f3c4bd87315f9c1d440883290e4110d88de49a'),
 0x316c7c:(340,'3091e4abf970b6216592fa4b5e2f2ac2dbebcf007327ce5f328332bc15d54ee2'),
}


class FlowerLightmapProbe(SourcePhysics):
    def __init__(self,image):
        verify_native(image)
        for a,(size,digest)in PINS.items():
            if hashlib.sha256(image.read(a,size)).hexdigest()!=digest:raise ValueError('Original flower binding consumer changed')
        super().__init__(image)
        self.names={};self.active=False;self.trace=[]
        from unicorn import UC_HOOK_CODE
        for a in(0x11ddd2c,0x14006c4,0x13e4214,0x13dc85c,0x13e3f44,0x13dc360,0x316c7c):
            self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=a,end=a)

    def intern(self,value):
        if value not in self.names:
            p=self.alloc(24+len(value.encode())+1);self.w(p+0x10,'I',10000)
            self.uc.mem_write(p+24,value.encode()+b'\0');self.names[value]=p
        return self.names[value]

    def string(self,value):
        raw=value.encode();p=self.alloc(24+len(raw)+1);self.w(p,'QQI',len(raw),len(raw),10000)
        self.uc.mem_write(p+24,raw+b'\0');return p+24

    def hook(self,uc,a,n,d):
        if a==0x11ddd2c:
            name=self.cstr(self.get('X1')).decode()
            if name not in('lightMap','uvTransform')or self.get('W2')!=0:raise ValueError('Uncovered original flower name query')
            self.set('X0',self.intern(name));self.set('PC',self.get('X30'));return
        if self.active and a in(0x14006c4,0x13e4214,0x13dc85c,0x13e3f44,0x13dc360,0x316c7c):
            row={'address':hex(a),'originalExecuted':True}
            if a==0x14006c4:row['name']=self.cstr(self.get('X1')).decode()
            elif a==0x13dc85c:row['texture']='atlas'if self.r(self.get('X3'),'Q')[0]==self.atlas else'other'
            elif a==0x13dc360:row['uvTransform']=list(self.r(self.get('X3'),'4f'))
            self.trace.append(row);return
        if self.imports.get(a)=='strcmp':
            x,y=self.cstr(self.get('X0')),self.cstr(self.get('X1'))
            self.set('W0',int(x>y)-int(x<y));self.set('PC',self.get('X30'));return
        return super().hook(uc,a,n,d)

    def run_binding(self,name,dat_uv,*,initial_uv=(0,0,0,0),with_uv=True,prior_policy=None):
        self.trace=[]
        owner,material,effect,table=self.alloc(0x200),self.alloc(0x100),self.alloc(0x100),self.alloc(48)
        self.call(0x33db74,{'X0':owner})
        if self.r(owner+0x179,'2B')!=(1,0):raise ValueError('Original fresh owner policy flags differ')
        self.w(material,'I',10000);self.w(material+8,'Q',effect);self.w(effect+0x1a,'H',2 if with_uv else 1);self.w(effect+0x40,'Q',table)
        for i,(field,offset,kind)in enumerate((('lightMap',0,16),('uvTransform',8,11))):
            self.w(table+i*24,'Q',self.intern(field));self.w(table+i*24+8,'Q',offset)
            self.w(table+i*24+0x11,'B',kind);self.w(table+i*24+0x14,'H',1)
        def retained_texture(path):
            t=self.alloc(0x80);state=self.alloc(0x100);self.w(state+0x60,'I',1)
            self.w(t+8,'I',10000);self.w(t+0x20,'Q',self.string(path));self.w(t+0x28,'Q',state)
            # Type1 is the actual source2D category. Unread texture dimensions
            # and GPU storage are deliberately not supplied by this CPU probe.
            self.w(t+0x3c,'h',-1);return t
        original=retained_texture(name)if name is not None else 0
        self.atlas=retained_texture('texture/lightmap/selection/lightmap/probe.tga')
        self.w(material+0x40,'Q',original);self.w(material+0x48,'4f',*initial_uv)
        if prior_policy is not None:self.w(owner+0x179,'BB',int(prior_policy),1)
        model_holder,mat_holder,tex_holder,uv,scale=[self.alloc(n)for n in(8,8,8,8,8)]
        self.w(model_holder,'Q',self.alloc(8));self.w(mat_holder,'Q',material);self.w(tex_holder,'Q',self.atlas)
        self.w(uv,'2f',*dat_uv[:2]);self.w(scale,'2f',*dat_uv[2:])
        self.active=True
        try:result=self.call(0x342194,dict(X0=owner,X1=model_holder,X2=mat_holder,X3=tex_holder,X4=uv,X5=scale))
        finally:self.active=False
        current=self.r(material+0x40,'Q')[0]
        return {'sourceName':name,'DATTransform':list(dat_uv),'originalReturn':result,
            'replacementAllowed':bool(self.r(owner+0x179,'B')[0]),'policyCached':bool(self.r(owner+0x17a,'B')[0]),
            'atlasReplacedOriginal':current==self.atlas,'originalTextureRetained':current==original,
            'uvTransform':list(self.r(material+0x48,'4f'))if with_uv else None,
            'originalCalls':list(self.trace),'withUVDeclaration':with_uv,'priorCachedPolicy':prior_policy,
            'nativeCPU':True,'originalOwnerConstructorExecuted':True,'materialAndTextureIdentitiesAreInterfaces':True,'actualCompiledReflectionObserved':False,'GPUCreated':False}


def analyze(image):
    from bdae_convert import BDAE
    from scene_sampling import material_samplers
    from terrain_convert import read_instances
    import tempfile
    source=Sources(DEFAULT_SOURCE);raw=source.read(MODEL)
    if hashlib.sha256(raw).hexdigest()!=MODEL_SHA:raise ValueError('Original flower model changed')
    with tempfile.TemporaryDirectory()as td:
        p=Path(td)/'model.bdae';p.write_bytes(raw);r=BDAE(p);records=material_samplers(r)
        if len(records)!=1 or records[0]['samplers']['lightMap']['texture']!=LIGHTMAP:raise ValueError('Original flower lightMap differs')
        rows=[]
        for stem in('-041_-001','-040_-001'):
            p=Path(td)/(stem+'.itm');p.write_bytes(source.read('world/selection/items/'+stem+'.itm'))
            rows.extend(i for i in read_instances(p)if i['id']in IDS)
    probe=FlowerLightmapProbe(image);results=[]
    for row in rows:
        record,bindings=binding_rows(source,row)
        if len(bindings)!=1:raise ValueError('Original flower object DAT changed')
        results.append({'instance':row,'recordPath':record,'DATBindings':bindings,
            'bindingPolicy':probe.run_binding(LIGHTMAP,bindings[0]['uvTransform'])})
    controls=[probe.run_binding(n,[.25,.5,.75,1])for n in('texture/lightmap.tga','',None,LIGHTMAP)]
    controls.append(probe.run_binding(LIGHTMAP,[.25,.5,.75,1],with_uv=False))
    controls.append(probe.run_binding(LIGHTMAP,[.25,.5,.75,1],initial_uv=(.1,.2,.3,.4)))
    source_lightmap=source.read(LIGHTMAP)
    if hashlib.sha256(source_lightmap).hexdigest()!=LIGHTMAP_SHA:raise ValueError('Original default lightmap02 changed')
    from texture_decode import decode
    im=decode(source_lightmap)
    return {'format':FORMAT,'instances':results,'controls':controls,'sourceProofs':source.proofs,
        'defaultTexture':{'path':LIGHTMAP,'sha256':LIGHTMAP_SHA,'size':list(im.size),'extrema':im.getextrema(),
            'candidatePacks':[r['pack']for r in source.candidates(LIGHTMAP)]},
        'scope':'Original342194 keeps custom lightMap02 and does not apply selection atlas or DAT UV; identity is the source reset from explicit fresh zero UV.',
        'limits':['Runtime material/declaration/texture identities and string interning are explicit CPU fixtures, not original compiled/GPU objects.',
            'Only the fresh policy branch is selected. Cached previous policy on a reused owner is not guessed for live Android.',
            'Source DAT records are retained as request evidence even when the original material replacement gate rejects them.']}


if __name__=='__main__':
    from analyze_native_resources import NativeImage
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=analyze(NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes()));dest=local_output(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():raise ValueError('Use a fresh flower evidence file')
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'instances':len(result['instances']),'atlasReplacement':[r['bindingPolicy']['atlasReplacedOriginal']for r in result['instances']],
        'uvTransforms':[r['bindingPolicy']['uvTransform']for r in result['instances']],'default':result['defaultTexture']}))
