"""Export original wet-cell metadata and compatible original swimming clips.

Source bytes/full tables remain in ignored local assets. Existing art is copied,
never overwritten; animation rest rebasing is the established browser adapter.
"""
import hashlib
import json
import tempfile
from pathlib import Path
from terrain_water import ROOT,NativeWater
from source_swimming import FORMAT


def metadata(image,sources,terrain):
    n=NativeWater(image);rows=[]
    for tile in terrain['sourceTiles']:
        raw=sources.read('world/tutorial/terrain/%04d_%04d.trn'%tuple(tile['tile']));n.read(raw);e=n.e;ptr=e.r(n.tile+0x80,'Q')[0]
        if not all(e.r(ptr+j*0xa8+0x90,'Q')[0]==n.tile for j in range(64)):raise ValueError('Original parent linkage differs')
        rows.append({'tile':tile['tile'],'sourceSHA256':hashlib.sha256(raw).hexdigest(),'waterType':e.r(n.tile+0x144,'h')[0],
            'chunks':[dict(zip(['flags','height','packedColor','factor'],e.r(ptr+j*0xa8+0x70,'IfIf')))for j in range(64)]})
    return {'format':FORMAT,'nativeSHA256':hashlib.sha256(image.data).hexdigest(),'tiles':rows}


def player_clips(sources,old):
    from equipment_appearance import BASE_MODEL,ANIMATION
    from bdae_character import convert_character,aliases
    names=['swim_idle','swim_forward']
    with tempfile.TemporaryDirectory()as d:
        body=Path(d)/'body.bdae';anim=Path(d)/'anim.bdae';body.write_bytes(sources.read(BASE_MODEL));anim.write_bytes(sources.read(ANIMATION))
        converted=convert_character(body,anim,body,extra_actions={n:n for n in names})
    source_nodes=converted['rig']['nodes'];target=aliases(old['rig']['nodes']);remap={}
    for i,node in enumerate(source_nodes):
        if node['name']not in target:raise ValueError('Original swimming skeleton alias missing')
        j=target[node['name']];other=old['rig']['nodes'][j]
        for k in ['position','quaternion','scale']:
            if node[k]!=other[k]:raise ValueError('Existing animation rest pose differs; retrace binding')
        remap[i]=j
    result=json.loads(json.dumps(old));clips=[c for c in converted['clips']if c['name']in names]
    if len(clips)!=2 or any(c['name']in names for c in old['clips']):raise ValueError('Unexpected swim clip set')
    for c in clips:
        for track in c['tracks']:track['node']=remap[track['node']]
    result['clips'].extend(clips)
    result['swimmingBinding']={'source':ANIMATION,'sourceSHA256':hashlib.sha256(sources.read(ANIMATION)).hexdigest(),
        'actions':names,'sourceCondition':'Original 90e26c IsSwimming; source ranges, existing rest rebasing; full original animation dispatcher remains missing'}
    return result


def underwater_effects(sources,image=None):
    from bdae_convert import BDAE
    from scene_render_state import _shader,read_pass_state
    from terrain_lighting import EFFECT_SHA256
    if image is None:
        from analyze_native_resources import NativeImage
        image=NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes())
    with tempfile.TemporaryDirectory()as d:
        p=Path(d)/'effects';p.write_bytes(sources.read('CustomEffects.bdae'));r=BDAE(p)
        if hashlib.sha256(r.b).hexdigest()!=EFFECT_SHA256:raise ValueError('Original effects build differs')
        count,table=r.section(164);rows={}
        for name in ['Terrain_Water','Terrain_Water_Border']:
            at=next(table+i*56 for i in range(count)if r.string(r.q(table+i*56))==name);profiles=[]
            for field in [32,36]:
                p=r.rel(at+field);tech=r.rel(p+4);n=r.u(p);matches=[tech+j*24 for j in range(n)if r.string(r.q(tech+j*24))=='under_water']
                if len(matches)!=1:raise ValueError('Original underwater technique missing')
                t=matches[0];pa=r.rel(t+12);vp,fp=_shader(r,pa),_shader(r,pa+24)
                if r.u(t+8)!=1 or vp['defines']!={'UNDER_WATER':''}or fp['defines']!={'UNDER_WATER':''}:raise ValueError('Original underwater pass differs')
                words=r.unpack('4I',pa+72);low=words[0]&255
                import struct
                equation=struct.unpack('<I',image.read(0x1f41908+((words[2]>>12)&7)*4,4))[0]
                factors=[struct.unpack('<I',image.read(0x1f4191c+i*4,4))[0]for i in [low&15,low>>4]]
                if (words[0]>>8)&255!=low:raise ValueError('Separate source alpha blend differs; retrace required')
                profiles.append({'field':field,'vertex':vp,'fragment':fp,'state':read_pass_state(r,pa+72),
                                 'equationGL':equation,'factorsGL':factors,'sameAlphaFactors':True})
            rows[name]=profiles
        return rows


def build(source,runtime,output):
    from tutorial_map_geometry import local_output
    from analyze_native_resources import NativeImage
    from map_loading_evidence import Sources
    runtime,output=map(local_output,(runtime,output))
    if output.exists():raise ValueError('Preserve previous exports; choose a fresh ignored directory')
    output.mkdir(parents=True);assets=runtime/'game-data/converted';cfg=json.loads((runtime/'prototype/native-physics.json').read_text())
    terrain=json.loads(Path(cfg['terrain']).read_text());image=NativeImage(Path(cfg['library']).read_bytes());sources=Sources(source)
    manifest=json.loads((assets/'geometry-water-floor/manifest.json').read_text());original=json.loads((assets/manifest['player']['url'].removeprefix('/assets/')).read_text())
    water=metadata(image,sources,terrain);player=player_clips(sources,original)
    (output/'water-native-metadata.json').write_text(json.dumps(water,separators=(',',':')))
    (output/'elf-female.json').write_text(json.dumps(player,separators=(',',':')))
    manifest['player']['url']='/assets/source-swimming/elf-female.json';manifest['sourceSwimming']={'format':FORMAT,'url':'/assets/source-swimming/swimming.json'}
    (output/'manifest.json').write_text(json.dumps(manifest,separators=(',',':')))
    from PIL import Image
    probe=NativeWater(image,host_math=True);e=probe.e;buf=e.alloc(256);e.set('X0',buf);probe.fragment(0x554540,0x554594)
    alpha=bytes(e.uc.mem_read(buf,256));a=Image.frombytes('L',(256,1),alpha);white=Image.new('L',(256,1),255)
    Image.merge('RGBA',(white,white,white,a)).save(output/'power-table.png')
    offset=e.r(e.r(0x2506608,'Q')[0],'f')[0]
    public={'format':FORMAT,'tiles':water['tiles'],'effects':underwater_effects(sources,image),'swimOffset':offset,
        'powerTable':{'url':'/assets/source-swimming/power-table.png','alphaSHA256':hashlib.sha256(alpha).hexdigest()},
        'originalCameraQuery':'34e8f4','nativeSHA256':water['nativeSHA256'],'sources':sources.proofs,
        'limits':['Surface swimming normal type0 only; original input speed/animation dispatcher/camera rig remain incomplete.',
                  'Underwater source shader branches only; model underwater shading and full wave postprocess remain unverified.']}
    (output/'swimming.json').write_text(json.dumps(public,separators=(',',':')))
    return {'tiles':len(water['tiles']),'clips':[c['name']for c in player['clips']if c['name'].startswith('swim_')]}


if __name__=='__main__':
    import argparse
    from resource_packs import DEFAULT_SOURCE
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print(json.dumps(build(DEFAULT_SOURCE,a.runtime,a.output)))
