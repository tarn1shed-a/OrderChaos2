"""Export source-backed APK Default postprocessing for the isolated viewer.

Ordinary settled frame only. Does not select hardware or invent environment,
weather, shadow, underwater, death or server state. Original shaders stay local.
"""
import argparse
import hashlib
import json
import math
import struct
import zipfile
from pathlib import Path

from map_loading_evidence import Sources
from map_selection_evidence import DEFAULT_APK, apk_config
from resource_packs import DEFAULT_SOURCE

ROOT = Path(__file__).resolve().parents[1]
SHADERS = {
    'pe_common_vs.glsl':'20aab1818712d964571c0a351c928da653283b5b9e7e3188e64117e819c6e8da',
    'pe_common_fs.glsl':'db5ba51b12631e3eea18e714c9c77e0110fe516a6044221468fd3d0085a15169',
}
ROUTINES = {
    0x345c2c:(1308,'35d97d4968c180557dda854d25c2cd66929cc252d3ac756e22819a7047c9817c'),
    0x346574:(11152,'5ed16403ab68c2ca9874eab0e51fb858dc81fd3a4066f0db998ed5192c964675'),
    0x349104:(4944,'6e3802da45d6b2acb0fd635ad3d94b7ff7843baeba1c7c84197df5e3013bf555'),
    0x34aa30:(356,'51f2b6c9340019e7afd03f573a9d46fe3e27c974759c176b57ea3432347f4038'),
}
MACROS = {0:'HAS_DOWN_SAMPLE\n#define HAS_ADJUST_BY_LUMIN',2:'HAS_BLUR_HORIZONTAL',
          3:'HAS_BLUR_VERTICAL',4:'HAS_BLOOM',13:'HAS_BLOOM_HDR',14:'COLOR_GRADING'}


def verify(image):
    for at,(size,sha)in ROUTINES.items():
        if hashlib.sha256(image.read(at,size)).hexdigest()!=sha:
            raise ValueError('Original default postprocess code changed')
    rel={r['r_offset']:r['r_addend']for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    for bit,name in MACROS.items():
        at=rel[0x2509270+bit*8]
        if image.read(at,len(name)+11)!=('\n#define '+name+'\n\0').encode():
            raise ValueError('Original postprocess macro table changed')
    for index,name in [(12,'RGB8'),(22,'RGBA8'),(30,'RGBA16F')]:
        at=rel[0x2498d88+index*8]
        if image.read(at,len(name)+1)!=name.encode()+b'\0':
            raise ValueError('Original render-target format identity changed')
    if image.read(0x1df7a4c,4)!=struct.pack('<f',.2):
        raise ValueError('Original bloom intensity coefficient changed')


class NativeDefaultPostProbe:
    """Run two small original arithmetic branches, without resources or GL."""
    def __init__(self,image):
        from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM
        from unicorn import arm64_const
        verify(image)
        self.reg=arm64_const
        self.uc=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
        for at,size in [(0x347000,0x2000),(0x34a000,0x1000),(0x1df7000,0x1000)]:
            self.uc.mem_map(at,size);self.uc.mem_write(at,image.read(at,size))
        self.uc.mem_map(0x10000000,0x10000)
    def combine_mask(self,flags,hdr):
        u,r=self.uc,self.reg
        u.mem_write(0x1000019c,bytes([hdr]))
        u.reg_write(r.UC_ARM64_REG_X19,0x10000000)
        u.reg_write(r.UC_ARM64_REG_W8,flags)
        u.emu_start(0x34782c,0x347890,count=64)
        return u.reg_read(r.UC_ARM64_REG_W0)
    def intensity(self,decrease,intensity):
        u,r=self.uc,self.reg
        u.mem_write(0x10000184,struct.pack('<2f',decrease,intensity))
        u.reg_write(r.UC_ARM64_REG_X19,0x10000000)
        u.reg_write(r.UC_ARM64_REG_SP,0x10008000)
        u.emu_start(0x34aad4,0x34aaf4,count=16)
        return struct.unpack('<f',u.mem_read(0x1000800c,4))[0]


def export(image,source,apk,output):
    from native_device_selection_probe import NativeDeviceSelectionProbe
    verify(image);apk_proof=apk_config(apk)
    with zipfile.ZipFile(apk)as z:config=json.loads(z.read('assets/GameOptions.json'))
    values={}
    for group in ('GPU','MEM','ColorCorrection'):
        values.update(dict(NativeDeviceSelectionProbe(image).updates(config['profiles'][group],'')))
    keys=('EnableRTTCreating','RTTViewportScale','EnableBloom','EnableBloomHDR')
    selected={k:values[k]for k in keys}
    if selected!={'EnableRTTCreating':True,'RTTViewportScale':1.,'EnableBloom':True,'EnableBloomHDR':False}:
        raise ValueError('APK defaults no longer match the recovered ordinary LDR branch')
    probe=NativeDefaultPostProbe(image)
    mask=probe.combine_mask(1,False)
    if mask!=0x10:raise ValueError('Original default combine mask differs')
    sources=Sources(source);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    shader_urls={}
    for name,sha in SHADERS.items():
        raw=sources.read(name)
        if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('Original common postprocess shader changed')
        (output/name).write_bytes(raw);shader_urls[name]='/assets/verified/APK_Default/'+name
    report={'format':'oc2-apk-default-postprocess-v1','configuration':selected,
            'APK':apk_proof,'sourceShaders':sources.proofs,'shaders':shader_urls,
            'nativeRoutines':{hex(k):{'bytes':n,'sha256':s}for k,(n,s)in ROUTINES.items()},
            'combine':{'nativeMask':mask,'defines':['HAS_BLOOM'],'HDR':False,'LUT':False},
            'targets':{'sceneSourceFormat':'RGB8','smallSourceFormat':'RGBA8','bloomDivisor':4,
                       'webSceneFormat':'RGBA8 (unused alpha=1; same RGB precision)'},
            'passes':[['HAS_DOWN_SAMPLE','HAS_ADJUST_BY_LUMIN'],['HAS_BLUR_HORIZONTAL'],
                      ['HAS_BLUR_VERTICAL'],['HAS_BLOOM']],
            'bloom':{'intensityFormula':'(decrease + sqrt(intensity)) * float32(0.2)',
                     'coordOffsetScale':1.,'downsampleOffset':1.25/1024,
                     'blurOffsets':[1.4/256,3.3/256],'blurWeights':[11/32,5/32]},
            'actualDeviceObserved':False,'baseline':'original APK defaults explicitly requested by user',
            'limits':['Ordinary settled frame only, with no radial blur, flash, water or death effect.',
                      'Source shader text is used with mechanical WebGL2 syntax/attribute adaptation.',
                      'Existing scene camera, environment mode and original-frame pixel matching remain separate gaps.']}
    (output/'default-postprocess.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    manifest_path=output/'manifest.json'
    manifest=json.loads(manifest_path.read_text())
    if manifest['sourceSelection']['profile']!='APK_Default':raise ValueError('Expected an APK Default selection export first')
    manifest['defaultPostprocess']='/assets/verified/APK_Default/default-postprocess.json'
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    return report


def audit_materials(source,legacy):
    """Compare the viewer's material names/samplers and diffuse pixels to BDAE.

    This checks identity, not active shader variants or original GPU sampling.
    """
    import tempfile
    from PIL import Image
    from bdae_convert import BDAE
    from texture_decode import decode
    sources=Sources(source);legacy=Path(legacy)
    manifest=json.loads((legacy/'manifest.json').read_text())
    models=[];textures={}
    with tempfile.TemporaryDirectory(prefix='oc2-default-materials-')as folder:
        for item in manifest['scenery']:
            converted=json.loads((legacy/item['url'].removeprefix('/assets/')).read_text())
            path=Path(folder)/'model.bdae';path.write_bytes(sources.read(item['model']))
            original=BDAE(path).parse()
            equal=original['materials']==converted['materials']
            streams=('material','positions','normals','uvs','sourceUV1','indices','groups')
            geometry_equal=len(original['meshes'])==len(converted['meshes'])and all(
                all(a.get(k)==b.get(k)for k in streams)for a,b in zip(original['meshes'],converted['meshes']))
            models.append({'model':item['model'],'materialCount':len(original['materials']),
                           'originalNamesAndSamplersMatch':equal,'meshCoreStreamsExact':geometry_equal})
            if not equal:raise ValueError('Converted material list differs from original BDAE')
            if not geometry_equal:raise ValueError('Converted mesh/UV/index streams differ from original BDAE')
            for mat in original['materials']:
                name=mat['diffuse']
                if name in textures:continue
                expected=decode(sources.read(name));actual=Image.open(legacy/manifest['textures'][name].removeprefix('/assets/')).convert('RGBA')
                textures[name]={'sourceSHA256':sources.proofs[name]['sha256'],'size':list(expected.size),
                                'RGBPixelsExact':expected.size==actual.size and expected.convert('RGB').tobytes()==actual.convert('RGB').tobytes(),
                                'RGBAPixelsExact':expected.size==actual.size and expected.tobytes()==actual.tobytes()}
                if not textures[name]['RGBPixelsExact']:raise ValueError('Converted diffuse pixels differ from original texture')
    return {'models':models,'diffuseTextures':textures,'sourceFiles':sources.proofs,
            'scope':'Original material declarations and base-level decoded pixels only; runtime filtering/mips and original frame remain unobserved.'}


if __name__=='__main__':
    from analyze_native_resources import NativeImage
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native',type=Path,default=ROOT/'analysis/raw/beff-native/library.so')
    parser.add_argument('--apk',type=Path,default=DEFAULT_APK)
    parser.add_argument('--source',type=Path,default=DEFAULT_SOURCE)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not args.output.resolve().is_relative_to((ROOT/'analysis/raw').resolve()):parser.error('Original shader files stay in ignored analysis/raw/')
    report=export(NativeImage(args.native.read_bytes()),args.source,args.apk,args.output)
    print(json.dumps({'configuration':report['configuration'],'combine':report['combine'],'output':str(args.output)}))
