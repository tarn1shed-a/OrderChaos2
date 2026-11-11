"""Recover original vegetation whose serialized shakeSpeed makes displacement zero.

The nonzero model is retained as a gap: no invented clock epoch, active quality
macro or wind is supplied. Static specialization follows the original formula.
"""
import hashlib,json,math,struct
from pathlib import Path
from bdae_attributes import primitive_bindings,verify_native as verify_attributes
from scene_gray_materials import HASHES as GRAY_HASHES,EXTRAS as GRAY_EXTRAS,FORMAT as GRAY_FORMAT,native_values
from scene_texture_sampling import recover_scene_sampling
from scene_alpha import recover_scene_alpha
from scene_culling import recover_scene_culling
from scene_baked_lighting import recover_model_lighting
from scene_render_state import SHADERS

FORMAT='oc2-source-wind-identity-v1'
EFFECT='ut_lightmap_shake_gray_trans.bdae'
HASH='bf9eaa1705d69268539cb12157cf2e3e7786c7c42dbf2aebcde28819bfe1769e'
HASHES={**GRAY_HASHES,EFFECT:HASH}
EXTRAS={**GRAY_EXTRAS,EFFECT:{'shakeSpeed':8,'lightmap_gray_color':10,'lightmap_gray_rate':8}}
MODELS=tuple('model/scene/region_whitepike/'+n+'.bdae'for n in('whi_plant_pinetree_snow01','whi_plant_pinetree_snow02','wp_plant_big_conifers002','wp_plant_big_conifers003','wp_plant_cedar002','wp_plant_cedar003','wp_plant_pinetree003','wp_plant_pinetree005','wp_plant_pinetree006'))
NONZERO='model/scene/region_whitepike/wp_plant_pinetree001.bdae'


def source_properties(reader):
    n,t=reader.section(172);rows=[]
    for i in range(n):
        at=t+80*i;effect=reader.string(reader.q(at+8));fields={};count,p=reader.u(at+32),reader.rel(at+36)
        for j in range(count):
            a=p+j*32;name=reader.string(reader.q(a))
            if name not in EXTRAS.get(effect,{}):continue
            kind=EXTRAS[effect][name]
            if name in fields or reader.u(a+16)!=kind or reader.u(a+20)!=1 or reader.unpack('2I',reader.rel(a+24))!=(1,0):raise ValueError('Original wind property shape differs')
            values=list(reader.unpack('f'if kind==8 else'3f',reader.rel(a+28)))
            if not all(math.isfinite(v)for v in values):raise ValueError('Non-finite original wind input')
            fields[name]=values
        if effect==EFFECT and set(fields)!=set(EXTRAS[EFFECT]):raise ValueError('Missing source wind/gray parameters')
        rows.append({'index':i,'name':reader.string(reader.q(at)),'effect':effect,'values':fields})
    return rows


def native_scalar(image,value):
    from source_physics import SourcePhysics
    # The original generic type8 writer was traced by scene_gray_materials.
    if hashlib.sha256(image.read(0x13e0b30,2960)).hexdigest()!='a8bf6500e4b7ced06f9357377a44cb51e1d0b818abfb5dd14210f26ce29cfecb':raise ValueError('Original property-copy routine changed')
    v=SourcePhysics(image);m=v.alloc(128);fx=v.alloc(80);d=v.alloc(24);p=v.alloc(4);v.w(m+8,'Q',fx);v.w(fx+0x1a,'H',1);v.w(fx+0x40,'Q',d);v.w(d+0x11,'B',8);v.w(d+0x14,'H',1);v.w(p,'f',value)
    if v.call(0x13e0b30,{'X0':m,'W1':0,'W2':8,'X3':p,'W4':0,'W5':1,'W6':4})!=1:raise ValueError('Original wind scalar write failed')
    result=v.r(m+0x40,'f')[0]
    if result!=value:raise ValueError('Source float32 speed differs')
    return {'value':result,'nativeCPU':True,'resourceOrGPUCreated':False}


def verify_uv2(image):
    verify_attributes(image)
    rels={r['r_offset']:r['r_addend']for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    if rels.get(0x2499a60)!=0x1f4c13e or rels.get(0x250e770)!=0x1f4c13e or image.read(0x1f4c13e,10)!=b'texcoord2\0'or image.read(0x2499a68,4)!=struct.pack('<I',3):raise ValueError('Original UV2 semantic alias differs')
    # Source 12db438 compares source semantic i+4; at i2 this is6.
    # Runtime stream-mask instruction 12db478 sets 2<<i, hence runtime3.
    from source_physics import SourcePhysics
    v=SourcePhysics(image);v.set('W13',2);v.uc.emu_start(0x12db438,0x12db43c,count=2)
    if v.get('W18')!=6:raise ValueError('Original UV2 source semantic differs')
    v.set('W14',2);v.uc.emu_start(0x12db478,0x12db47c,count=2)
    if v.get('W3')!=8:raise ValueError('Original UV2 runtime semantic differs')
    return {'sourceSemantic':6,'runtimeSemantic':3,'runtimeName':'texcoord2','nativeCPU':True}


def uv2_streams(reader,data):
    n,t=reader.section(180)
    if n!=len(data['meshes']):raise ValueError('Original wind mesh count differs')
    for j,mesh in enumerate(data['meshes']):
        w=reader.rel(t+j*24+20);a=reader.q(w+8)+((reader.u(w+4)&0xffffff)-1)*8;nc=reader.u(a+16);np,pt=reader.u(a+96),reader.rel(a+100);bindings=[primitive_bindings(reader,pt+i*88,nc).get(6)for i in range(np)]
        if not bindings or bindings[0]is None or len(set(bindings))!=1:raise ValueError('Original UV2 requires separate primitive geometry')
        idx=bindings[0];desc=[reader.u(reader.rel(a+off)+idx*4)for off in(20,28,36,44)];stride,off,kind,count=desc;nv=reader.u(a+12);vp,size=reader.q(a+64),reader.q(a+72)
        if kind!=6 or count!=2 or not 0<stride<=65535 or off+8>stride or(nv-1)*stride+off+8>size:raise ValueError('Unsupported or truncated original UV2 stream')
        values=[]
        for i in range(nv):values.extend(reader.unpack('2f',vp+i*stride+off))
        if not all(math.isfinite(v)for v in values):raise ValueError('Non-finite original UV2')
        mesh['sourceUV2']=values;mesh['sourceWindAttributes']={'sourceSemantic':6,'runtimeSemantic':3,'attributeIndex':idx,'stride':stride,'offset':off,'type':kind,'components':count}


def recover(extract,reader,data,image):
    properties=source_properties(reader)
    speeds=[r['values']['shakeSpeed'][0]for r in properties if r['effect']==EFFECT]
    if not speeds or any(s!=0 for s in speeds):raise ValueError('Nonzero source shakeSpeed needs original frame inputs; no static replacement')
    semantic=verify_uv2(image);uv2_streams(reader,data)
    data['sceneSampling']=recover_scene_sampling(extract,reader,data,allow_repeat_override=True,effect_hashes=HASHES,fx_properties=EXTRAS)
    data['sceneAlpha']=recover_scene_alpha(extract,reader,data,effect_hashes=HASHES,extra_properties=EXTRAS,extra_defines={EFFECT:{'LIGHTMAP_GRAY':'','VERTEX_ANIM':''}})
    data['sceneCulling']=recover_scene_culling(extract,reader,data,effect_hashes=HASHES,extra_properties=EXTRAS)
    data['sceneBakedLighting']=recover_model_lighting(reader,data,allow_repeat_override=True)
    gray=[];wind=[]
    for p in properties:
        enabled=p['effect']==EFFECT;row={'index':p['index'],'name':p['name'],'enabled':enabled};g=dict(row)
        if enabled:
            color=p['values']['lightmap_gray_color'];rate=p['values']['lightmap_gray_rate'][0];g.update(color=color,rate=rate,nativePropertyCopy=native_values(image,color,rate));row.update(speed=0,nativePropertyCopy=native_scalar(image,p['values']['shakeSpeed'][0]))
        gray.append(g);wind.append(row)
    data['sourceGray']={'format':GRAY_FORMAT,'materials':gray,'shaderSHA256':SHADERS,'scope':'original zero-shake gray material; original lighting inputs unchanged'}
    data['sourceWindIdentity']={'format':FORMAT,'materials':wind,'semantic':semantic,'shaderSHA256':SHADERS,'zeroDisplacementVerified':True,'dynamicRendererInputsRestored':False,'scope':'Original sin(time * zero speed) makes finite-input displacement zero; quality macros disabling VERTEX_ANIM give the same identity. Nonzero model is not admitted.'}


def export(runtime,output):
    from scene_tree_recovery import export as base_export
    return base_export(runtime,output,models=MODELS,namespace='source-map-zero-wind',base_manifest='source-map-gray/manifest.json',material_builder=recover,audit_format=FORMAT,audit_key='sourceWindIdentityRecovery')


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=export(a.runtime,a.output);print(json.dumps({k:r[k]for k in('displayedModels','displayedInstances','omittedInstances','lightsChanged')}))
