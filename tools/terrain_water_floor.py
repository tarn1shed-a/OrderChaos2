"""Original underwater terrain CPU data and the far-depth water-border pass.

Original files/full tables/GLSL remain in ignored local exports. Host allocation
and pow/powf are explicit adapters; no GPU completion or swimming is simulated.
"""
import hashlib
import json
import struct
from pathlib import Path
from terrain_water import ROOT,NativeWater

FORMAT='oc2-source-water-floor-border-v1'
PREFIX='/assets/geometry-water-floor/'


class NativeFloor(NativeWater):
    def __init__(self,image):
        super().__init__(image,host_math=True)

    def triangle_indices(self):
        # 3577ec's CPU producer and both original root selections; no GPU path.
        e=self.e;result={}
        for parity in (0,1):
            heads=e.alloc(16)
            e.call(0xa8e8c0,{'W0':12,'W1':int(parity==0),'X2':0x352ec8,
                'X3':0,'X4':heads,'X5':heads+8,'X6':0},limit=4000000)
            a,b=e.r(heads,'2Q');lookup=e.r(0x2506ee0,'Q')[0];out=e.alloc(0x6000);chunks=[]
            for j in range(64):
                indices=[]
                for half in (0,1):
                    offset=e.r(lookup+(j*4+(parity<<1)+half)*2,'H')[0]
                    base=a if offset<0x2000 else b
                    count=e.call(0xa8f064,{'X0':a+offset*4,'X1':base,'X2':out})
                    if count!=192:raise ValueError('Original full-resolution terrain index count changed')
                    indices.extend(e.r(out,f'{count}H'))
                cx,cz=j%8,j//8
                if any(not(cx*8<=v%65<=cx*8+8 and cz*8<=v//65<=cz*8+8)for v in indices):
                    raise ValueError('Original index buffer escaped its source chunk')
                chunks.append(indices)
            result[str(parity)]=chunks
        return result

    def descriptor(self,j):
        e=self.e;p=e.r(self.tile+0x80,'Q')[0]+j*0xa8
        e.set('SP',e.STACK);e.set('X0',p);self.fragment(0x350f90,0x350fec)
        height,factor,*color=e.r(e.STACK+0x14,'5f')
        return {'height':height,'factor':factor,'color':color,'packedColor':e.r(p+0x78,'I')[0],
                'enabled':bool(e.r(e.STACK+0x10,'B')[0])}

    def color_table(self,packed):
        e=self.e;e.set('W23',254);e.set('W24',0);self.fragment(0x3500f4,0x350148)
        out=e.alloc(1024);e.set('X0',out);e.set('W20',packed&255)
        e.set('W21',(packed>>8)&255);e.set('W22',(packed>>16)&255);e.set('W24',255)
        self.fragment(0x350150,0x350244)
        return bytes(e.uc.mem_read(out,1024))


def border_effect(source):
    from bdae_convert import BDAE
    from scene_render_state import _shader,read_pass_state
    from terrain_lighting import terrain_effect
    import tempfile
    with tempfile.TemporaryDirectory()as d:
        p=Path(d)/'effects';p.write_bytes(source.read('CustomEffects.bdae'));r=BDAE(p)
        if hashlib.sha256(r.b).hexdigest()!='9cdc85d1d4861e7245c90ba97575cb8c1a1fc447d7ddf02557cbfd2805c7e145':raise ValueError('Effect build differs')
        terrain_effect(r) # Also verify effect 24 shaders, defines and default/fade states.
        count,table=r.section(164)
        rows=[table+j*56 for j in range(count)if r.string(r.q(table+j*56))=='Terrain_Water_Border']
        if len(rows)!=1:raise ValueError('Original border effect missing/ambiguous')
        profiles=[]
        for field in (32,36):
            p=r.rel(rows[0]+field);t=r.rel(p+4);pa=r.rel(t+12)
            if r.string(r.q(t))!='default'or r.u(t+8)!=1:raise ValueError('Unsupported border technique')
            state=read_pass_state(r,pa+72);vp,fp=_shader(r,pa),_shader(r,pa+24)
            if state!=dict(blendEnabled=False,cullEnabled=True,cullFaceGL=0x405,frontFaceGLBeforeTargetXor=0x901,
                depthTestEnabled=True,depthWriteEnabled=False,depthFunctionGL=0x203):raise ValueError('Border state differs')
            if vp['file']!='water_border_vs.glsl'or fp['file']!='water_border_fs.glsl'or vp['defines']or fp['defines']:raise ValueError('Border shader differs')
            profiles.append({'field':field,'state':state,'vertex':vp,'fragment':fp})
        return profiles


def build(source,water,geometry,output):
    from PIL import Image
    from analyze_native_resources import NativeImage
    from map_loading_evidence import Sources
    from tutorial_map_geometry import local_output
    water,geometry,output=map(local_output,(water,geometry,output))
    if output.exists():raise ValueError('Choose a fresh ignored export directory')
    output.mkdir(parents=True);sources=Sources(source)
    image=NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes());native=NativeFloor(image)
    triangles=native.triangle_indices();native.e.cursor=native.start
    mats=json.loads((water/'terrain-materials.json').read_text())
    manifest=json.loads((water/'manifest.json').read_text());water_profile=json.loads((water/'terrain-water.json').read_text())
    geometry_data=json.loads((geometry/'base'/manifest['mapWindow']['url'].removeprefix('/assets/')).read_text())
    tiles=[];tables={};total=0
    for mat in mats['tiles']:
        raw=sources.read('world/tutorial/terrain/%04d_%04d.trn'%tuple(mat['tile']));chunks=native.read(raw);wet=[]
        for j,(chunk,m)in enumerate(zip(chunks,mat['chunks'])):
            if bool(chunk['flags']&0x10000)!=bool(m['sourceWaterPending']):raise ValueError('Water branch differs')
            if not m['sourceWaterPending']:continue
            desc=native.descriptor(j)
            if not desc['enabled']or m['effectiveIndices'][0]<0:raise ValueError('Unsupported wet material')
            packed=desc['packedColor'];key=str(packed)
            if key not in tables:
                data=native.color_table(packed);name=f'water-color-{packed:08x}.png'
                Image.frombytes('RGBA',(256,1),data).save(output/name)
                tables[key]={'url':PREFIX+name,'rgbaSHA256':hashlib.sha256(data).hexdigest()}
            wet.append({'chunk':chunk['chunk'],**desc});total+=1
        if wet:tiles.append({'tile':mat['tile'],'sourceSHA256':hashlib.sha256(raw).hexdigest(),'chunks':wet})
    # Shared border buffer is produced by the same original CPU stores as water.
    q=native.quad();e=native.e;out=e.alloc(128);manager=e.alloc(0x80);e.w(manager+0x50,'2I',3,1)
    e.set('X21',out);e.set('X22',manager);native.fragment(0x364984,0x3649f8)
    q['colors']=[v for j in range(4)for v in e.r(out+j*32+28,'4B')]
    if q['colors']!=[0,0,0,255]*4:raise ValueError('Original border vertex colors changed')
    shaders={}
    for name in ['TerrainVP.glsl','TerrainFP.glsl','water_border_vs.glsl','water_border_fs.glsl']:
        raw=sources.read(name);(output/name).write_bytes(raw)
        shaders[name]={'url':PREFIX+name,'sha256':hashlib.sha256(raw).hexdigest()}
    profile={'format':FORMAT,'tiles':tiles,'triangleIndices':triangles,'quad':q,'tables':tables,'shaders':shaders,
        'borderProfiles':border_effect(sources),'nativeSHA256':hashlib.sha256(image.data).hexdigest(),
        'selection':{'floorEffect':24,'borderEffect':32,'technique':'default','settledFade':1,'cameraWaterDepth':-100,
                     'defines':['IN_GAME','COLOR_TONE','COLOR0','LIGHTMAP','WATER'],
                     'mediumEnd':False,'lowEnd':False,'observedOriginalDevice':False},
        'limits':['Host pow/powf, allocation, browser matrix/sampler adapters are explicit; no original Android GPU result.',
                  'Original initial full-resolution CPU indices; runtime adaptive terrain LOD is not restored.',
                  'Border is original far-depth quad fill, not foam. No new shoreline artwork.',
                  'Underwater camera/swimming/wet-cell movement remain unavailable. Lighting inputs are unchanged.'],
        'sources':sources.proofs}
    (output/'terrain-water-floor.json').write_text(json.dumps(profile,separators=(',',':')))
    manifest['terrainWaterFloor']={'format':FORMAT,'url':PREFIX+'terrain-water-floor.json'}
    (output/'manifest.json').write_text(json.dumps(manifest,separators=(',',':')))
    audit={'tiles':len(tiles),'chunks':total,'colorTables':len(tables),'originalCPUTriangles':True,
           'originalShaders':True,'originalGPUExecuted':False,'lightingChanged':False,
           'sourceTerrainTiles':len(geometry_data['sourceTiles']),'preservedWaterTiles':len(water_profile['tiles'])}
    (output/'audit.json').write_text(json.dumps(audit,indent=2)+'\n');return audit


if __name__=='__main__':
    import argparse
    from resource_packs import DEFAULT_SOURCE
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('water','geometry','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(json.dumps(build(DEFAULT_SOURCE,a.water,a.geometry,a.output)))
