"""Bounded source scene diffuse address recovery; filtering stays a web adapter."""
import hashlib
import io
import struct
import tempfile
import zipfile
from pathlib import Path

from bdae_convert import BDAE
from scene_sampling import material_samplers, effect_profile_samplers, verify_native as verify_sampler_native

ROUTINES = {
    0x55138c:(408,'c02935e532c3367889291fd21108c57cf8467b4d70935a9944dc4242ee08138e'),
    0x1126cdc:(112,'fe7f1661d757e978a0a71c4f1aa87cb20c775a2e2bedf1d644da1502ed46c7e4'),
    0x143f5c4:(1628,'277b176295f2e6f09be8ed5db938a12f62f303396f3af11575dae2ef91e20fe0'),
    0x143fd80:(344,'79b1cad0bbed754f48322766cce234f4c96526de66650fc63f40cdfdcb42f670'),
    0x143fed8:(3256,'f88bdb1f30f994d10dc70a2d75010dd374df46acded939a27dcfd8bff3059630'),
    0x1440f08:(2016,'d15d61f0f0ba93d7ddb25110dd83d362fdb39680b309c7d578f85a875747dc78'),
    0x13d7c38:(340,'8f7764999409eec670ca58879e43ca3fd62c6ce529af7c2e43eb2a032d86a87b'),
    0x13d7d8c:(1084,'8ac4ab49e85bfe2b1282e6daa5bbb19a48b783961969e938bc87830acbc1f800'),
    0x140fe60:(136,'5e67ab40dd1ed8b0146cdb1a46cd29888d8e63ae50e7628bd77ddbd38711b9dd'),
    0x1424948:(200,'6c734969ba8ace6bc360bc1c1a455074a1e8d38f6f2aec490f6f11cc8e9eeb24'),
    0x146d33c:(364,'08aa4fd80682c8b4a3998878368fcddee11bc691ce6b67a54dde1dc21dc0b29f'),
    0x146d4a8:(1864,'dd5b323f78dacc1a56a936de64b3f8ed7adf66e5de349d049ce1de66d3b6f133'),
    0x146f728:(48,'b68d3f8e908a870c5e5e8d1f6deed5e30d164a7558b75c7753bd68fd85802e8b'),
    0x14417bc:(304,'99205d6b6698e16fe2cb8573e9a6f33308d75a97b9e3a292e8c32d88c38631ca'),
}
EFFECTS = {
    'ut_cull_lightmap_solid.bdae':'61556eb0430899ddf7588a1e63d2a39237a0d7c13b023b9c48bd394eb2340026',
    'ut_lightmap_solid.bdae':'b0a169c06aef00e817f77ad965696d1f42e7d445879e27b6036de0e36bfadb72',
    'ut_lightmap_trans.bdae':'4f440961fa2cd78dddec5f2a1fc40f3839168ec66112e99f88161f2288f98817',
}


def verify_native(image):
    verify_sampler_native(image)
    for address,(size,digest) in ROUTINES.items():
        if hashlib.sha256(image.read(address,size)).hexdigest()!=digest:
            raise ValueError('Scene texture loading changed; retrace required')
    rels={r['r_offset']:r['r_addend'] for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    if rels.get(0x2492cf0+0x248)!=0x1424948 or rels.get(0x2417c10+0x248)!=0x140fe60:
        raise ValueError('Scene texture factory changed')
    if image.read(rels[0x24995f0],7)!=b'Repeat\0':
        raise ValueError('Source Repeat name changed')
    return {'routineCount':len(ROUTINES),'sourceAddressMode':0,'sourceAddressName':'Repeat'}


def _pvr(raw):
    if len(raw)<52:raise ValueError('Truncated source PVR header')
    header,height,width,mips,flags,length,bpp,r,g,b,a,magic,surfaces=struct.unpack_from('<13I',raw)
    # Only the observed ETC1 2D branch. No cube, volume, PVRTC or guessed layout.
    if header!=52 or magic!=0x21525650 or surfaces!=1 or flags not in (0x36,0x136) or bpp!=4 or any((r,g,b,a)):
        raise ValueError('Unsupported source scene PVR branch')
    if not all(0<v<=8192 and v&(v-1)==0 for v in (width,height)):
        raise ValueError('Scene address recovery requires positive POT dimensions')
    expected=max(width,height).bit_length()-1 if flags&256 else 0
    if mips!=expected or length!=len(raw)-52:
        raise ValueError('Source PVR mip count or payload length differs')
    sizes=[(max(1,width>>level),max(1,height>>level)) for level in range(mips+1)]
    if sum(((w+3)//4)*((h+3)//4)*8 for w,h in sizes)!=length:
        raise ValueError('Incomplete source ETC1 mip payload')
    return {'width':width,'height':height,'typeId':1,'encoding':'ETC1','fileMipLevels':mips+1}


def texture_dimensions(raw):
    if not raw.startswith(b'PK\x03\x04'):return {**_pvr(raw),'container':'PVR2'}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names=archive.namelist()
        if len(names)!=3 or set(names)!={'SPLIT','rgb.pvr','alpha.pvr'} or sum(i.file_size for i in archive.infolist())>32*1024*1024:
            raise ValueError('Unsupported source scene split texture')
        if archive.read('SPLIT')!=bytes(4):raise ValueError('Unsupported source split mode')
        rgb,alpha=_pvr(archive.read('rgb.pvr')),_pvr(archive.read('alpha.pvr'))
        if rgb!=alpha:raise ValueError('Source split texture dimensions/mips differ')
    return {**rgb,'container':'ZIP-PVR2-split'}


def repeat_override(request):
    return request == {'addressU':0,'addressV':0,'minFilter':0,'magFilter':1}


def recover_scene_sampling(extract,reader,data,*,allow_repeat_override=False):
    records=material_samplers(reader)
    if len(records)!=len(data['materials']):raise ValueError('Scene material count differs')
    materials=[]
    with tempfile.TemporaryDirectory(prefix='oc2-scene-sampling-') as temp:
        effects={}
        for index,(record,converted) in enumerate(zip(records,data['materials'])):
            if record['material']!=converted['name'] or record['effectPath'] not in EFFECTS:
                raise ValueError('Unsupported source scene material/effect')
            if record['effectName']!='#'+Path(record['effectPath']).stem+'-fx':raise ValueError('Source scene effect identity differs')
            def raw(path):
                source=extract(path)
                return bytes(source) if isinstance(source,(bytes,bytearray,memoryview)) else Path(source).read_bytes()
            path=record['effectPath']
            if path not in effects:
                target=Path(temp)/path;target.write_bytes(raw(path));definition=BDAE(target)
                if hashlib.sha256(definition.b).hexdigest()!=EFFECTS[path]:raise ValueError('Source scene FX changed; retrace required')
                effect=effect_profile_samplers(definition)
                if effect['effectName']!=record['effectName'][1:]:raise ValueError('Source effect definition differs')
                if any(s['texture'] is not None for p in effect['profiles'] for s in p['samplers'].values()):raise ValueError('Non-null source FX default')
                effects[path]=effect
            source=record['samplers'].get('texture')
            if not source or source['texture']!=converted['diffuse'] or (any(v is not None for v in source['request'].values()) and not (allow_repeat_override and repeat_override(source['request']))):
                raise ValueError('Scene diffuse sampler override needs separate recovery')
            encoded=raw(source['texture']);dimensions=texture_dimensions(encoded)
            materials.append({'index':index,'name':record['material'],'texture':source['texture'],
                              'textureSHA256':hashlib.sha256(encoded).hexdigest(),'sourceTexture':dimensions,
                              'sourceRequest':source['request'],'addressU':0,'addressV':0})
    return {'format':'oc2-scene-sampling-v2'if allow_repeat_override else'oc2-scene-sampling-v1','materials':materials,'applied':['diffuse-address-U','diffuse-address-V'],
            'limits':['Fresh source 2D POT texture construction and current scene material skip-setter requests. External cache mutations are not recreated.',
                      'Only diffuse addressing is applied. Original file mips are counted, not uploaded. Browser filtering, anisotropy and orientation remain adapters. Explicit min0 may become4 under the original global switch; no active filter is asserted.']}
