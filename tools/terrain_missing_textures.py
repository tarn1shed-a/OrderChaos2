"""Original missing-terrain-texture branch, not replacement terrain artwork.

The fallback's bytes are obtained by executing bounded original instructions.
No renderer/context or successful original GPU creation is fabricated.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MISSING_PATH='texture/tiles/default.tga'


def recover_native_fallback(image):
    from source_physics import SourcePhysics
    from texture_sampling import verify_sampling
    verify_sampling(image)
    e=SourcePhysics(image);u=e.uc
    def fragment(start,stop,count=200):
        u.emu_start(start,stop,count=count)
        if e.get('PC')!=stop:raise ValueError('Original missing-texture fragment did not reach its boundary')
    # Actual initializer writes; do not treat zero-filled BSS as the color.
    e.set('X19',0x25dd610);fragment(0x2cf3a8,0x2cf3e0)
    colors=[list(u.mem_read(0x25dd630+i*4,4))for i in range(2)]
    sp=e.STACK;sdk=e.alloc(0x400);manager=e.alloc(0x400)
    e.w(sdk+0x300,'Q',manager);e.w(sp+0x10,'Q',sdk);e.set('SP',sp)
    fragment(0x3569ec,0x3569fc)
    if e.get('X0')!=manager or[e.get('W1'),e.get('W2')]!=[0,1]:raise ValueError('Original terrain fallback arguments differ')
    e.set('W24',1);e.set('SP',sp);fragment(0x1444bac,0x1444bd4)
    descriptor=list(e.r(sp+0x10,'8I'))
    if descriptor!=[1,22,0,0,1,1,1,0]:raise ValueError('Original fallback descriptor differs')
    pixels=[]
    for color_class in range(2):
        pointer=e.alloc(4)
        for name,value in {'X21':pointer,'W28':1,'W27':descriptor[5],'W25':descriptor[4],
                           'W26':descriptor[6],'W23':color_class}.items():e.set(name,value)
        fragment(0x1444c3c,0x1444cf4);pixels.append(list(u.mem_read(pointer,4)))
    if pixels!=colors:raise ValueError('Original constructor/fill results disagree')
    reloc={r['r_offset']:r['r_addend']for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()if r['r_info_type']==1027}
    def string(address):return image.read(reloc[address],80).split(b'\0')[0].decode()
    native_name=string(0x2496ef0)+'-'+string(0x2499530).lower()
    routines={}
    for address in (0x354de4,0x3563dc,0x143f5c4,0x1445120,0x1444b68,0x2cf358):
        m,_=image.routine(address);start=int(m['start'],16)
        routines[hex(address)]={'start':m['start'],'bytes':m['size'],'sha256':hashlib.sha256(image.read(start,m['size'])).hexdigest()}
    return {'kind':'original-null-request-fallback','nativeName':native_name,'nativeSHA256':hashlib.sha256(image.data).hexdigest(),
            'width':1,'height':1,'formatId':descriptor[1],'format':'RGBA8','pixelRGBA':pixels[0],
            'colorTableRGBA':colors,'descriptor':descriptor,'class':0,'dimension':1,'nativeRoutines':routines,
            'GPUCreationExecuted':False,'originalTextureRecovered':False,
            'scope':'Explicit cold-cache local-provider-miss branch; original numeric instructions only. Actual Android caches/GL success are not observed.'}


def fallback_image(name,proof):
    from PIL import Image
    if name!=MISSING_PATH or proof.get('kind')!='original-null-request-fallback' or proof.get('nativeName')!='glitch.texture-not-found-2d':
        raise ValueError('This terrain miss has no verified original fallback binding')
    return Image.frombytes('RGBA',(proof['width'],proof['height']),bytes(proof['pixelRGBA'])),{**proof,'requestedPath':name}


def texture_image(sources,name,fallback=None,*,terrain_layer=False):
    """Missing source files fail except an explicitly verified terrain-layer miss.

    Ambiguous/existing/corrupt sources never enter the null-provider branch.
    Model textures, masks and baked lightmaps cannot use this fallback.
    """
    from texture_decode import decode
    if terrain_layer and fallback is not None and not sources.candidates(name):
        return fallback(name)
    return decode(sources.read(name)),None


def build(source,atlas,legacy,output):
    from analyze_native_resources import NativeImage
    from map_loading_evidence import Sources
    from tutorial_map_geometry import build as geometry_build,source_coordinates,local_output
    from tutorial_map_expansion import collision
    from terrain_lighting import lightmap_requests,terrain_texture_encoding
    image=NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes());proof=recover_native_fallback(image)
    sources=Sources(source);coordinates=source_coordinates(sources)
    inventory=json.loads((Path(atlas)/'inventory.json').read_text())
    if {tuple(r['tile'])for r in inventory['tileFiles']}!={tuple(t)for t in coordinates}:
        raise ValueError('Original atlas inventory differs; retrace source selection first')
    for x,z in coordinates:
        candidates=[p for p in lightmap_requests('tutorial',x,z)if sources.candidates(p)]
        if not candidates or terrain_texture_encoding(sources.read(candidates[0]))['encoding']!='ETC1':
            raise ValueError('Unsupported original lightmap; no substitute permitted')
    if sources.candidates(MISSING_PATH):raise ValueError('The original texture now exists; do not replace it with a fallback')
    output=local_output(output)
    report=geometry_build(image,source,legacy,output,coordinates=coordinates,namespace='missing-terrain',
        texture_fallback=lambda name:fallback_image(name,proof),preview_namespace='geometry-missing-terrain')
    report['nativeMissingTextureFallback']=proof
    report['collision']=collision(source,output,output/'physics')
    (output/'geometry-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return {'tiles':report['tileCount'],'displayedInstances':report['preview']['displayedInstances'],
            'originalTextureRecovered':False,'fallback':proof['nativeName'],'pixelRGBA':proof['pixelRGBA']}


if __name__=='__main__':
    from resource_packs import DEFAULT_SOURCE
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--legacy',type=Path,required=True)
    p.add_argument('--atlas',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(build(DEFAULT_SOURCE,a.atlas,a.legacy,a.output)))
