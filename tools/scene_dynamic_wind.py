"""Recover the one source nonzero vegetation branch for explicit APK defaults.

Original math/parameters and bounded CPU consumers are checked. Browser time,
GPU compilation and draw scheduling remain declared host interfaces.
"""
import hashlib,json,math,struct,zipfile
from pathlib import Path
from scene_wind_identity import NONZERO,uv2_streams,verify_uv2,native_scalar,HASHES as OLD_HASHES
from scene_texture_sampling import recover_scene_sampling
from scene_alpha import recover_scene_alpha
from scene_culling import recover_scene_culling
from scene_baked_lighting import recover_model_lighting
from scene_render_state import SHADERS

FORMAT='oc2-source-dynamic-wind-v1'
EFFECT='ut_lightmap_shake_trans.bdae'
HASH='150990c43a8d59a947727d3c16be2b6562fed28cbb46f7d9fc74c3a2e34ec4d6'
HASHES={**OLD_HASHES,EFFECT:HASH};EXTRAS={EFFECT:{'shakeSpeed':8}}
ROUTINES={
 0x333940:(216,'949fbdb5171c30fdc950abc89d4b34b9686dae356d5c5fcf156e5efc2fa7de5b'),
 0x12b55f0:(64,'e2b22ae33171dd34860649881221d5b16f9b48dd44aa4b1b650f2113478fd954'),
 0x12b5a28:(72,'db40aaa82d94346599fb1ba490075bfb1f3139ab4b87ef8c176bad230f881b54'),
 0x12b59d0:(68,'c4a283bed272ec2312a23f1c64d33628c5a54fac99b681c290dbaaa3bc5aaa8a'),
 0x1413868:(564,'1595bf40f356e70a20f5a9c00a2143faa190a48ca2d97cca014ff60a53a545fc'),
 0x148cfc4:(2788,'bb4ee286910720e0142b99a8479a4982956fd11c1ee2eb536d19718726d65d75'),
 0x1415b44:(2336,'70ad22b0af79cfb57533aec1523441fa29c10564ffb641b185a0e24b874fbdd8'),
 0x10f54d8:(1264,'912ba6988c185731445ff2635db3fb2685bcb31fb0540c3fb5cbab20ea7b2f39'),
}


def verify_native(image):
    for at,(size,digest)in ROUTINES.items():
        if hashlib.sha256(image.read(at,size)).hexdigest()!=digest:raise ValueError('Original wind frame consumer changed')
    if image.read(0x250e6a4,4)!=struct.pack('<f',1)or image.read(0x1df79f4,4)!=struct.pack('<f',.001):raise ValueError('Original wind time constants changed')
    rel={r['r_offset']:r['r_addend']for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    macros=[]
    for i in range(26):
        at=rel.get(0x250afc0+i*8);s=image.read(at,110).split(b'\0')[0].decode()if at else'';macros.append(s)
    if 'MEDIUM_END'not in macros[14]or'LOW_END'not in macros[15]or any('DCC_MAX'in x for x in macros):raise ValueError('Original game macro table differs')
    return {'routines':len(ROUTINES),'timeScale':1,'millisecondsToSeconds':struct.unpack('<f',image.read(0x1df79f4,4))[0],'gameMacroDCCMax':False,'AndroidGPUObserved':False}


class NativeWind:
    def __init__(self,image):
        from source_physics import SourcePhysics
        from unicorn import UC_HOOK_CODE
        verify_native(image);self.vm=SourcePhysics(image);self.microseconds=0
        def clock(uc,a,n,d):self.vm.set('X0',self.microseconds);self.vm.set('PC',self.vm.get('X30'))
        self.vm.uc.hook_add(UC_HOOK_CODE,clock,begin=0x1505828,end=0x1505828)
        self.vm.call(0x12b55f0)
        if self.vm.r(0x25dc130,'2I')!=(0,0):raise ValueError('Fresh original clock is not unpaused/base zero')
    def time(self,microseconds):
        if type(microseconds)is not int or not 0<=microseconds<=0xffffffff*1000:raise ValueError('Expected bounded monotonic microseconds')
        self.microseconds=microseconds;self.vm.call(0x12b5a28);ticks=self.vm.call(0x12b59d0)&0xffffffff
        self.vm.set('W0',ticks);self.vm.sf('S10',struct.unpack('<f',self.vm.image.read(0x1df79f4,4))[0]);self.vm.uc.emu_start(0x141619c,0x14161a4,count=2)
        return {'ticks':ticks,'seconds':self.vm.gf('S0')}
    def quality(self,level,flags=0):
        if type(level)is not int or level not in(0,1,2):raise ValueError('Only source shader levels0/1/2')
        v=self.vm;obj=v.alloc(0x100);custom=v.alloc(0x100);config=v.alloc(0x100);v.w(obj+0xb0,'Q',custom);v.w(custom+0xc,'I',flags);v.w(config+0x50,'I',level);v.w(0x2528220,'Q',config)
        v.call(0x333940,{'X0':obj});return v.r(custom+0xc,'I')[0]
    def world_t(self,matrix):
        if len(matrix)!=16 or not all(math.isfinite(x)for x in matrix):raise ValueError('Finite source world matrix required')
        v=self.vm;device=v.alloc(0x3000);m=v.alloc(64);box=v.alloc(24);v.w(m,'16f',*matrix)
        v.call(0x1413868,{'X0':device,'W1':2,'X2':m,'X3':box,'W4':0})
        result=v.call(0x148cfc4,{'X0':device+0x2070,'W1':87,'W2':0})
        return list(v.r(result,'16f'))


def source_speeds(reader):
    n,t=reader.section(172);out=[]
    for i in range(n):
        at=t+80*i;effect=reader.string(reader.q(at+8));r={'index':i,'name':reader.string(reader.q(at)),'enabled':effect==EFFECT}
        if r['enabled']:
            fields=[]
            for j in range(reader.u(at+32)):
                q=reader.rel(at+36)+j*32
                if reader.string(reader.q(q))=='shakeSpeed':
                    if reader.u(q+16)!=8 or reader.u(q+20)!=1 or reader.unpack('2I',reader.rel(q+24))!=(1,0):raise ValueError('Original speed property shape differs')
                    fields.append(reader.unpack('f',reader.rel(q+28))[0])
            if len(fields)!=1 or not math.isfinite(fields[0])or fields[0]<=0:raise ValueError('Missing/nonpositive original dynamic speed')
            r['speed']=fields[0]
        out.append(r)
    if sum(r['enabled']for r in out)!=3:raise ValueError('Original three wind materials differ')
    return out


def shader_block(extract):
    b=extract('ut_common_vs.glsl')
    if hashlib.sha256(b).hexdigest()!=SHADERS['ut_common_vs.glsl']:raise ValueError('Original wind shader changed')
    s=b.decode().replace('\r\n','\n');begin=s.index('#ifdef VERTEX_ANIM',s.index('vec4 vert ='));end=s.index('gl_Position = WorldViewProjectionMatrix * vert;',begin)
    return s[begin:end]


def recover(extract,reader,data,image):
    rows=source_speeds(reader);verify_uv2(image);uv2_streams(reader,data);probe=NativeWind(image)
    for row in rows:
        if row['enabled']:row['nativePropertyCopy']=native_scalar(image,row['speed'])
    data['sceneSampling']=recover_scene_sampling(extract,reader,data,allow_repeat_override=True,effect_hashes=HASHES,fx_properties=EXTRAS)
    data['sceneAlpha']=recover_scene_alpha(extract,reader,data,effect_hashes=HASHES,extra_properties=EXTRAS,extra_defines={EFFECT:{'VERTEX_ANIM':''}})
    data['sceneCulling']=recover_scene_culling(extract,reader,data,effect_hashes=HASHES,extra_properties=EXTRAS)
    data['sceneBakedLighting']=recover_model_lighting(reader,data,allow_repeat_override=True)
    from map_selection_evidence import DEFAULT_APK,apk_config
    from native_device_selection_probe import NativeDeviceSelectionProbe
    apk_config(DEFAULT_APK)
    with zipfile.ZipFile(DEFAULT_APK)as z:cfg=json.loads(z.read('assets/GameOptions.json'))
    defaults=dict(NativeDeviceSelectionProbe(image).updates(cfg['profiles']['GPU'],''));level=defaults['ShadersLevel'];mask=probe.quality(level)
    if level!=2 or mask&0xc000:raise ValueError('Only original APK default wind-enabled branch')
    block=shader_block(extract)
    data['sourceDynamicWind']={'format':FORMAT,'materials':rows,'effect':EFFECT,'shaderSHA256':SHADERS,'vertexBlockSHA256':hashlib.sha256(block.encode()).hexdigest(),'vertexBlockURL':'/assets/source-map-dynamic-wind/wind-block.glsl',
      'quality':{'profile':'APK_Default','ShadersLevel':level,'qualityMask':mask,'DCC_MAX':False,'actualDeviceObserved':False},
      'clock':{'initialBase':0,'initialPauseCount':0,'scale':1,'unit':'microseconds-input/milliseconds-integer/seconds-float32','secondsScale':verify_native(image)['millisecondsToSeconds'],'nativeExamples':[{'microseconds':u,**probe.time(u)}for u in(0,1000,1234567,9876543)],'hostOrigin':True},
      'matrix':{'sourceSetter':hex(0x1413868),'semantic':87,'operation':'transpose-full-world-matrix','nativeCPU':True,'hostMatrixSubmission':True},'native':verify_native(image),'fullOriginalFrameRestored':False}


def export(runtime,output):
    from scene_tree_recovery import export as base_export
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE
    r=base_export(runtime,output,models=(NONZERO,),namespace='source-map-dynamic-wind',base_manifest='source-map-zero-wind/manifest.json',material_builder=recover,audit_format=FORMAT,audit_key='sourceDynamicWindRecovery')
    (output/'wind-block.glsl').write_text(shader_block(Sources(DEFAULT_SOURCE).read));return r


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=export(a.runtime,a.output);print(json.dumps({k:r[k]for k in('displayedModels','displayedInstances','omittedInstances','lightsChanged')}))
