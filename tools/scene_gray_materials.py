"""Recover the static LIGHTMAP_GRAY branch from original typed properties.

No VERTEX_ANIM, new light target, shader fallback or invented color is supplied.
The private export keeps original files and full results outside Git.
"""
import hashlib,math,struct
from pathlib import Path
from scene_texture_sampling import EFFECTS,recover_scene_sampling
from scene_alpha import recover_scene_alpha
from scene_culling import recover_scene_culling
from scene_baked_lighting import recover_model_lighting
from scene_render_state import SHADERS

FORMAT='oc2-source-scene-gray-v1'
EFFECT='ut_lightmap_gray_trans.bdae'
HASH='3d9e22b852aabb52c3f7d09b54d6bb10d3481da8e9005a098a1300b19f7507dc'
EXTRAS={EFFECT:{'lightmap_gray_color':10,'lightmap_gray_rate':8}}
HASHES={**EFFECTS,EFFECT:HASH}
MODELS=('model/scene/region_whisper_island/whi_plant_grass002.bdae',
        'model/scene/region_whisper_island/whi_plant_grass003.bdae',
        'model/scene/region_whitepike/wp_plant_big_conifers001.bdae')


def typed_values(reader):
    count,table=reader.section(172);result=[]
    for i in range(count):
        at=table+80*i;effect=reader.string(reader.q(at+8));fields={}
        n,p=reader.u(at+32),reader.rel(at+36)
        for j in range(n):
            prop=p+j*32;name=reader.string(reader.q(prop))
            if name not in EXTRAS.get(effect,{}):continue
            kind=EXTRAS[effect][name]
            if name in fields or reader.u(prop+16)!=kind or reader.u(prop+20)!=1 or reader.unpack('2I',reader.rel(prop+24))!=(1,0):raise ValueError('Original gray property shape differs')
            value=list(reader.unpack('3f'if kind==10 else'f',reader.rel(prop+28)))
            if not all(math.isfinite(v)and 0<=v<=1 for v in value):raise ValueError('Gray values outside this observed source branch')
            fields[name]=value
        if effect==EFFECT and set(fields)!=set(EXTRAS[EFFECT]):raise ValueError('Missing original gray material values')
        result.append({'index':i,'name':reader.string(reader.q(at)),'enabled':effect==EFFECT,**({'color':fields['lightmap_gray_color'],'rate':fields['lightmap_gray_rate'][0]}if fields else{})})
    return result


def native_values(image,color,rate):
    from source_physics import SourcePhysics
    if hashlib.sha256(image.data).hexdigest()!='77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4'or hashlib.sha256(image.read(0x13e0b30,2960)).hexdigest()!='a8bf6500e4b7ced06f9357377a44cb51e1d0b818abfb5dd14210f26ce29cfecb':raise ValueError('Wrong original uniform-copy evidence')
    if struct.unpack('<I',image.read(0x1f31038+8*4,4))[0]!=8 or struct.unpack('<I',image.read(0x1f31038+10*4,4))[0]!=10:raise ValueError('Original property conversion type changed')
    vm=SourcePhysics(image);mat=vm.alloc(0x100);effect=vm.alloc(0x80);decl=vm.alloc(48);vm.w(mat+8,'Q',effect);vm.w(effect+0x1a,'H',2);vm.w(effect+0x40,'Q',decl);out=[]
    for i,(kind,values)in enumerate([(10,color),(8,[rate])]):
        at=decl+i*24;vm.w(at+8,'Q',i*16);vm.w(at+0x11,'B',kind);vm.w(at+0x14,'H',1);src=vm.alloc(16);vm.w(src,str(len(values))+'f',*values)
        if vm.call(0x13e0b30,{'X0':mat,'W1':i,'W2':kind,'X3':src,'W4':0,'W5':1,'W6':4*len(values)})!=1:raise ValueError('Original gray uniform write failed')
        actual=list(vm.r(mat+0x40+i*16,str(len(values))+'f'))
        if actual!=[struct.unpack('<f',struct.pack('<f',v))[0]for v in values]:raise ValueError('Original gray value copy differs')
        out.append(actual)
    return {'color':out[0],'rate':out[1][0],'nativeCPU':True,'resourceOrGPUCreated':False}


def recover(extract,reader,data,image):
    data['sceneSampling']=recover_scene_sampling(extract,reader,data,allow_repeat_override=True,effect_hashes=HASHES,fx_properties=EXTRAS)
    data['sceneAlpha']=recover_scene_alpha(extract,reader,data,effect_hashes=HASHES,extra_properties=EXTRAS,extra_defines={EFFECT:{'LIGHTMAP_GRAY':''}})
    data['sceneCulling']=recover_scene_culling(extract,reader,data,effect_hashes=HASHES,extra_properties=EXTRAS)
    data['sceneBakedLighting']=recover_model_lighting(reader,data,allow_repeat_override=True)
    materials=typed_values(reader)
    for m in materials:
        if m['enabled']:m['nativePropertyCopy']=native_values(image,m['color'],m['rate'])
    data['sourceGray']={'format':FORMAT,'materials':materials,'shaderSHA256':SHADERS,'formula':'diffuse.rgb * mix(atlas.rgb, sourceColor, sourceRate); existing vertex light and fog follow','scope':'static original material properties; no new environment/light targets or wind animation'}


def export(runtime,output):
    from scene_tree_recovery import export as base_export
    return base_export(runtime,output,models=MODELS,namespace='source-map-gray',base_manifest='source-map-trees/manifest.json',material_builder=recover,audit_format=FORMAT,audit_key='sourceGrayRecovery')


if __name__=='__main__':
    import argparse,json
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=export(a.runtime,a.output);print(json.dumps({k:r[k]for k in('displayedModels','displayedInstances','omittedInstances','lightsChanged')}))
