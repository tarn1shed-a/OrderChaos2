"""Original ATIL water records and bounded original CPU buffer production.

The host supplies bytes, allocation and libc. No GPU result is manufactured.
Full exports and shaders belong only in the ignored local preview.
"""
import hashlib
import json
import struct
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FORMAT='oc2-source-terrain-water-v1'


def effect_state(image,source):
    from bdae_convert import BDAE
    from scene_render_state import _shader,read_pass_state
    import tempfile
    raw=source.read('CustomEffects.bdae')
    with tempfile.TemporaryDirectory()as d:
        p=Path(d)/'effect.bdae';p.write_bytes(raw);r=BDAE(p);count,table=r.section(164)
        if hashlib.sha256(r.b).hexdigest()!='9cdc85d1d4861e7245c90ba97575cb8c1a1fc447d7ddf02557cbfd2805c7e145':
            raise ValueError('Original water effect build differs')
        rows=[table+j*56 for j in range(count)if r.string(r.q(table+j*56))=='Terrain_Water']
        if len(rows)!=1:raise ValueError('Original water effect is ambiguous')
        profile=r.rel(rows[0]+32);tech=r.rel(profile+4);pa=r.rel(tech+12)
        if r.string(r.q(tech))!='default'or r.u(tech+8)!=1:raise ValueError('Original water technique changed')
        vp,fp=_shader(r,pa),_shader(r,pa+24)
        if vp['file']!='water_vs.glsl'or fp['file']!='water_fs.glsl'or vp['defines']or fp['defines']:raise ValueError('Original water shaders differ')
        state=read_pass_state(r,pa+72);words=r.unpack('4I',pa+72);low=words[0]&255
        equation=struct.unpack('<I',image.read(0x1f41908+((words[2]>>12)&7)*4,4))[0]
        factors=[struct.unpack('<I',image.read(0x1f4191c+k*4,4))[0]for k in [low&15,low>>4]]
        if [equation,*factors]!=[0x8006,0x302,0x303]or state!=dict(blendEnabled=True,cullEnabled=False,cullFaceGL=0x405,
                frontFaceGLBeforeTargetXor=0x901,depthTestEnabled=True,depthWriteEnabled=False,depthFunctionGL=0x203):
            raise ValueError('Original water GL state is outside supported branch')
        return {'state':state,'equationGL':equation,'factorsGL':factors,'separateAlphaFactors':False,'vertex':vp,'fragment':fp}


def native_probe(image,*,host_math=False):
    from source_physics import SourcePhysics
    class Probe(SourcePhysics):
        def hook(self,uc,address,size,data):
            if self.imports.get(address)in ('strncmp','memcmp'):
                n=self.get('X2');a=bytes(uc.mem_read(self.get('X0'),n));b=bytes(uc.mem_read(self.get('X1'),n))
                if self.imports[address]=='strncmp':a=a.split(b'\0')[0];b=b.split(b'\0')[0]
                self.set('W0',(next((x-y for x,y in zip(a,b)if x!=y),len(a)-len(b)))&0xffffffff)
                self.set('PC',self.get('X30'))
            elif host_math and self.imports.get(address)in ('pow','powf'):
                import math
                if self.imports[address]=='pow':self.df('D0',math.pow(self.gd('D0'),self.gd('D1')))
                else:self.sf('S0',math.pow(self.gf('S0'),self.gf('S1')))
                self.set('PC',self.get('X30'))
            else:super().hook(uc,address,size,data)
    return Probe(image)


class NativeWater:
    def __init__(self,image,*,host_math=False):
        self.image=image;self.e=native_probe(image,host_math=host_math);e=self.e
        root=e.alloc(0x400);cfg=e.alloc(0x200);e.w(root+0x270,'Q',cfg);e.w(0x2528db0,'Q',root)
        e.w(cfg+0x84,'3I',3,3,1);self.start=e.cursor

    def fragment(self,start,stop):
        self.e.uc.emu_start(start,stop,count=2000000)
        if self.e.get('PC')!=stop:raise ValueError('Original water fragment exceeded its boundary')

    def read(self,raw):
        e=self.e;e.cursor=self.start;tile=e.alloc(0x200);source=e.alloc(len(raw));e.uc.mem_write(source,raw)
        x,z=struct.unpack_from('<2i',raw,8);e.w(tile+8,'2i',x,z)
        e.call(0x358e08,{'X0':tile,'X1':source})
        self.tile=tile;chunks=e.r(tile+0x80,'Q')[0]
        self.chunks=[{'chunk':[j%8,j//8],'minimum':e.r(chunks+j*0xa8+0x3c,'f')[0],
            'flags':e.r(chunks+j*0xa8+0x70,'I')[0],'waterHeight':e.r(chunks+j*0xa8+0x74,'f')[0]}for j in range(64)]
        return self.chunks

    def depth(self):
        e=self.e;out=e.alloc(16384);sp=e.STACK;e.set('SP',sp)
        e.w(sp+0x128,'64f',*[c['waterHeight']if c['flags']&0x10000 else -100.0 for c in self.chunks])
        e.w(sp+0x28,'64f',*[5.0]*64);e.set('X19',out);e.set('X20',self.tile)
        self.fragment(0x357030,0x35724c)
        return bytes(e.uc.mem_read(out,16384))

    def quad(self):
        e=self.e;out=e.alloc(128);manager=e.alloc(0x80);e.w(manager+0x50,'2I',3,1)
        e.set('X21',out);e.set('X22',manager);self.fragment(0x364984,0x3649f8)
        raw=bytes(e.uc.mem_read(out,128));idx=e.alloc(12);e.set('X0',idx)
        self.fragment(0x364a04,0x364a24)
        return {'positions':[v for j in range(4)for v in struct.unpack_from('<3f',raw,j*32)],
                'uvs':[v for j in range(4)for v in struct.unpack_from('<2f',raw,j*32+12)],
                'indices':list(e.r(idx,'6H')),'sourceVertexStride':32,'sourceCPUBytesSHA256':hashlib.sha256(raw).hexdigest()}

    def bump(self,milliseconds):
        e=self.e;e.set('SP',e.STACK);e.set('W0',milliseconds);manager=e.alloc(0xb00)
        e.set('X25',manager);self.fragment(0x360d44,0x360de4)
        return list(e.r(e.STACK+0x78,'4f'))


def build(source,geometry,output):
    from PIL import Image
    from analyze_native_resources import NativeImage
    from map_loading_evidence import Sources
    from tutorial_map_geometry import local_output
    from texture_decode import decode
    output=local_output(output);geometry=local_output(geometry)
    if output.exists():raise ValueError('Preserve previous exports; choose a fresh local directory')
    output.mkdir(parents=True);prefix='/assets/geometry-water/'
    image=NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes());native=NativeWater(image);sources=Sources(source)
    manifest=json.loads((geometry/'verified/manifest.json').read_text())
    terrain=json.loads((geometry/'base'/manifest['mapWindow']['url'].removeprefix('/assets/')).read_text())
    mats=json.loads((geometry/'verified/terrain-materials.json').read_text());lights=json.loads((geometry/'verified/terrain-lighting.json').read_text())
    def write(name,data):
        (output/name).write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')));return prefix+name
    cache={}
    def texture(name):
        if name not in cache:
            raw=sources.read(name);im=decode(raw);fn='water-texture-'+hashlib.sha256(raw).hexdigest()+'.png';im.save(output/fn)
            cache[name]={'url':prefix+fn,'sourcePath':name,'sourceSHA256':hashlib.sha256(raw).hexdigest(),'size':list(im.size)}
        return cache[name]
    from terrain_materials import tile_materials
    from terrain_lighting import loaded_chunk_flags,final_water_flags
    from scene_lighting import f32
    water=[];corrected=0;count=0;proof_rows=[]
    for tile,mat,light in zip(terrain['sourceTiles'],mats['tiles'],lights['tiles']):
        x,z=tile['tile'];name=f'world/tutorial/terrain/{x:04d}_{z:04d}.trn';raw=sources.read(name)
        cs=native.read(raw);flags=[];active=[];parsed=tile_materials(raw)
        for j,(c,m)in enumerate(zip(cs,mat['chunks'])):
            cx,cz=c['chunk'];minimum=f32(min(tile['heights'][(cz*8+zz)*65+cx*8+xx]for zz in range(9)for xx in range(9))*f32(.01))
            original=parsed['chunks'][j]['flags'];height=f32(struct.unpack_from('<h',raw,24+j*parsed['recordStride']+4)[0]*f32(.01))
            if minimum!=c['minimum']or final_water_flags(loaded_chunk_flags(original),height,minimum)!=c['flags']:
                raise ValueError('Native chunk bounds/flags do not match the original source')
            wet=bool(c['flags']&0x10000);corrected+=int(bool(m['sourceWaterPending'])and not wet)
            m['sourceWaterPending']=wet;flags.append(c['flags'])
            if wet:active.append({'chunk':c['chunk'],'height':c['waterHeight'],'minimum':c['minimum']});count+=1
        light['runtimeFlags']=flags;light['waterClearedByTileMinimumBound']=not active
        proof_rows.append({'tile':tile['tile'],'sourceSHA256':hashlib.sha256(raw).hexdigest(),'chunks':cs})
        if not active:continue
        kind=struct.unpack_from('<H',raw,22)[0]
        if kind!=0:raise ValueError('Original nonzero water type is outside the verified surface branch')
        index=struct.unpack_from('<H',raw,20)[0]
        reflection='texture/tiles/textures/reflection_r.tga'if index==65535 else parsed['textures'][index]
        depth=native.depth();fn=f'water-depth-{x}_{z}.png'
        alpha=Image.frombytes('L',(128,128),depth);white=Image.new('L',alpha.size,255)
        Image.merge('RGBA',(white,white,white,alpha)).save(output/fn)
        water.append({'tile':tile['tile'],'type':kind,'chunks':active,'reflection':texture(reflection),
                      'depth':{'url':prefix+fn,'width':128,'height':128,'format':'A8','cpuSHA256':hashlib.sha256(depth).hexdigest()}})
    shaders={}
    for name in ['water_vs.glsl','water_fs.glsl']:
        raw=sources.read(name);(output/name).write_bytes(raw);shaders[name]={'url':prefix+name,'sha256':hashlib.sha256(raw).hexdigest()}
    routines={}
    for address in [0x358e08,0x356f74,0x3648d0,0x35bce0,0x3758b8,0x360b48,0x554bb4,0x34d228]:
        m,_=image.routine(address);routines[hex(address)]={**m,'sha256':hashlib.sha256(image.read(int(m['start'],16),m['size'])).hexdigest()}
    quad=native.quad();scale,rate1,rate2,rate3=struct.unpack('<4d',image.read(0x1df7c30,32))
    profile={'format':FORMAT,'tiles':water,'quad':quad,'effectState':effect_state(image,sources),'bump':texture('texture/tiles/textures/Waterbump_normal.tga'),
        'fresnel':texture('texture/tiles/textures/water_fresnel.png'),'shaders':shaders,
        'scroll':{'scale':scale,'rates':[0,rate1,rate2,rate3],'operation':'float32(fract(float64(uint32(ticks))*scale*rate)-1)',
                  'probe':{str(t):native.bump(t)for t in [0,1,1000,123456,4294967295]}},
        'selection':{'sourceEffect':31,'name':'Terrain_Water','technique':'default','underWater':False,'waterType':0,
                     'shaderEnabled':True,'legacyOverrideWord':0,'scope':'Explicit shader-enabled local preview; original Android active device not observed'},
        'nativeSHA256':hashlib.sha256(image.data).hexdigest(),'nativeRoutines':routines,'sources':sources.proofs,
        'limits':['Original CPU tile reader/depth/quad executed; original GPU creation not executed.',
                  'Browser clock origin and scene scheduling are adapters; no original swimming, underwater frame or water-border pass is claimed.',
                  'Wet-cell ground/animation/navigation remain unavailable; original shoreline dry cells and existing static scene are retained.']}
    manifest['terrainWater']={'url':write('terrain-water.json',profile),'format':FORMAT}
    manifest['map']['materials']['url']=write('terrain-materials.json',mats)
    manifest['terrainLighting']['url']=write('terrain-lighting.json',lights)
    write('manifest.json',manifest)
    audit={'tiles':len(terrain['sourceTiles']),'waterTiles':len(water),'waterChunks':count,'dryChunksPreviouslyHidden':corrected,
           'lightingChanged':False,'sourceRead':'original full 358e08 with host libc/allocation','originalGPUCreationExecuted':False,
           'nativeProofs':proof_rows,'sources':sources.proofs}
    write('water-audit.json',audit)
    return {k:v for k,v in audit.items()if k not in ['nativeProofs','sources']}


if __name__=='__main__':
    import argparse
    from resource_packs import DEFAULT_SOURCE
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--geometry',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    x=a.parse_args();print(json.dumps(build(DEFAULT_SOURCE,x.geometry,x.output)))
