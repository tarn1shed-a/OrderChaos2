"""Build an explicit source tile window, preserving original per-tile samples.

No artificial terrain, placement, physics or lighting rules are generated.
Original residency offsets/instance admission are separately executed by the
existing native probes. This exports a conditional static inspection window.
"""
import argparse
import collections
import copy
import hashlib
import json
import re
import shutil
import struct
import tempfile
from pathlib import Path

from bdae_convert import BDAE
from map_loading_evidence import Sources
from map_selection_evidence import DEFAULT_APK
from resource_packs import DEFAULT_SOURCE
from scene_alpha import recover_scene_alpha
from scene_baked_lighting import recover_model_lighting
from scene_collision import apply_scene_transforms
from scene_culling import recover_scene_culling
from scene_texture_sampling import recover_scene_sampling
from terrain_convert import read_tile, read_instances
from terrain_lighting import loaded_chunk_flags, final_water_flags, lightmap_requests, terrain_texture_encoding
from terrain_materials import SHADERS, tile_materials, mask_channels, effective_indices
from texture_decode import decode
from tutorial_preview_selection import resolve, export_preview

ROOT = Path(__file__).resolve().parents[1]
FORMAT = 'oc2-source-map-window-v1'


def local_output(path):
    result = Path(path).resolve()
    if not result.is_relative_to((ROOT/'analysis/raw').resolve()):
        raise ValueError('Source geometry exports stay in ignored analysis/raw')
    return result


def raw_tile(raw, x, z):
    with tempfile.TemporaryDirectory(prefix='oc2-source-tile-') as tmp:
        p = Path(tmp)/f'{x:04d}_{z:04d}.trn'; p.write_bytes(raw); tile = read_tile(p)
    return {'tile':[x,z], **{k:list(tile[k]) for k in ('heights','normals','colors')}}


def seam_audit(tiles):
    """Record actual duplicated samples; never weld, average or repair them."""
    seen, differences = {}, collections.Counter()
    for tile in tiles:
        tx,tz = tile['tile']
        for z in range(65):
            for x in range(65):
                i=z*65+x; key=(tx*64+x,tz*64+z)
                value=(tile['heights'][i],tile['normals'][i*3:i*3+3],tile['colors'][i])
                if key in seen:
                    for k,name in enumerate(('height','normal','color')):
                        if seen[key][k]!=value[k]: differences[name]+=1
                seen[key]=value
    return dict(differences)


def source_coordinates(sources):
    """Enumerate actual TRN names; holes in the archive are not filled."""
    coordinates=[]
    for name in sources.lookup:
        match=re.fullmatch(r'world/tutorial/terrain/(-?\d+)_(-?\d+)\.trn',name)
        if match:coordinates.append([int(v)for v in match.groups()])
    if not coordinates:raise ValueError('No original tutorial terrain files')
    return sorted(coordinates,key=lambda p:(p[1],p[0]))


def build(image, source, legacy, output, center=(-42,3), radius=2):
    from native_map_streaming_probe import NativeMapStreamingProbe
    from map_streaming_evidence import verify_native as verify_streaming
    from terrain_lighting import verify_native as verify_terrain
    from scene_collision import decode_phy
    verify_streaming(image); verify_terrain(image)
    output=local_output(output); base=output/'base'; destination=output/'verified'
    if base.exists() or destination.exists(): raise ValueError('Choose a fresh geometry output; existing work is preserved')
    legacy=Path(legacy); shutil.copytree(legacy,base,ignore=shutil.ignore_patterns('verified'))
    manifest=json.loads((legacy/'verified/APK_Default/manifest.json').read_text())
    materials=copy.deepcopy(json.loads((legacy/'maps/terrain-materials.json').read_text()))
    ground=copy.deepcopy(json.loads((legacy/'rendering/terrain-lighting.json').read_text()))
    sources=Sources(source); added=[]
    for name,sha in SHADERS.items():
        if hashlib.sha256(sources.read(name)).hexdigest()!=sha:
            raise ValueError('Original terrain shader changed; source layer/color branches need retracing')
    def write(path,value):
        p=base/path; p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False))
        added.append(path); return '/assets/'+path
    def texture(name):
        if name in manifest['textures']:return manifest['textures'][name]
        raw=sources.read(name);path='textures/window/'+hashlib.sha256(raw).hexdigest()+'.png'
        p=base/path;p.parent.mkdir(parents=True,exist_ok=True);decode(raw).save(p)
        added.append(path);manifest['textures'][name]='/assets/'+path;return manifest['textures'][name]
    offsets=NativeMapStreamingProbe(image).offsets(radius)['offsets']
    coordinates=sorted(([center[0]+x,center[1]+z] for x,z in offsets),key=lambda p:(p[1],p[0]))
    tiles,records,mat_tiles,light_tiles,texture_rows=[],[],[],[],[]
    phy_models={}
    for x,z in coordinates:
        stem=f'{x:04d}_{z:04d}';name=f'world/tutorial/terrain/{stem}.trn';raw=sources.read(name)
        tile=raw_tile(raw,x,z);tiles.append(tile);parsed=tile_materials(raw)
        mask_names=[f'world/tutorial/layers/{stem}_{i}.msk' for i in range(4)]
        channels=[sources.read(p) if sources.candidates(p) else None for p in mask_names]
        mask,classes=mask_channels(channels);parsed['mask']=None
        if mask:
            path=f'maps/window-mask-{stem}.png';mask.save(base/path);added.append(path)
            parsed['mask']={'url':'/assets/'+path,'width':mask.width,'height':mask.height,
                            'channels':[p if c is not None else None for p,c in zip(mask_names,channels)],'flipY':False}
        for chunk,cl in zip(parsed['chunks'],classes):
            chunk.update(maskClasses=cl,effectiveIndices=effective_indices(chunk['indices'],cl))
        texture_rows.append({'tile':[x,z],'textures':parsed['textures'][:]})
        parsed['textures']=[{'sourcePath':p,'url':texture(p)} for p in parsed['textures']];mat_tiles.append(parsed)
        from scene_lighting import f32
        minimum=f32(min(tile['heights'])*f32(.01));flags=[]
        for i,chunk in enumerate(parsed['chunks']):
            water=struct.unpack_from('<h',raw,24+i*parsed['recordStride']+4)[0]
            flag=final_water_flags(loaded_chunk_flags(chunk['flags']),f32(water*f32(.01)),minimum)
            flags.append(flag)
            # No invented water material: retain the source data but leave its
            # unsupported color-pass chunks out of this inspection frame.
            chunk['sourceWaterPending']=bool(flag&0x10000)
        requests=lightmap_requests('tutorial',x,z); candidates=[p for p in requests if sources.candidates(p)]
        if not candidates:raise ValueError('Original terrain lightmap unavailable')
        selected=candidates[0];encoded=sources.read(selected)
        light_tiles.append({'tile':[x,z],'source':name,'sourceSHA256':hashlib.sha256(raw).hexdigest(),
                            'waterClearedByTileMinimumBound':not any(f&0x10000 for f in flags),'runtimeFlags':flags,
                            'lightmap':{'sourcePath':selected,'url':texture(selected),**terrain_texture_encoding(encoded),
                                        'sha256':hashlib.sha256(encoded).hexdigest(),'fallback':selected!=requests[0]},
                            'requests':[{'sourcePath':p,'present':bool(sources.candidates(p))}for p in requests]})
        itm=f'world/tutorial/items/{stem}.itm'
        if sources.candidates(itm):
            with tempfile.TemporaryDirectory(prefix='oc2-source-itm-')as tmp:
                p=Path(tmp)/'tile.itm';p.write_bytes(sources.read(itm));records+=read_instances(p)
    if len({r['id']for r in records})!=len(records):raise ValueError('Duplicate source object IDs require separate recovery')
    models=[];gaps=[]
    for name in sorted({r['model']for r in records}):
        raw=sources.read(name)
        with tempfile.TemporaryDirectory(prefix='oc2-source-scene-')as tmp:
            p=Path(tmp)/'model.bdae';p.write_bytes(raw);reader=BDAE(p);data=apply_scene_transforms(reader,reader.parse())
            gap=None
            try:
                data['sceneSampling']=recover_scene_sampling(sources.read,reader,data)
                data['sceneAlpha']=recover_scene_alpha(sources.read,reader,data)
                data['sceneCulling']=recover_scene_culling(sources.read,reader,data)
                data['sceneBakedLighting']=recover_model_lighting(reader,data)
            except ValueError as error:
                gap=str(error);gaps.append({'model':name,'reason':gap})
            data['source']=name
        for material in data['materials']:
            if material['diffuse']:texture(material['diffuse'])
        path='models/source-'+hashlib.sha256(raw).hexdigest()+'.json'
        item={'url':write(path,data),'model':name,'vertices':sum(m['vertexCount']for m in data['meshes']),
              'triangles':sum(m['triangleCount']for m in data['meshes']),
              'instances':[{**r,'flags':r['sourceType']}for r in records if r['model']==name]}
        if gap:item['sourcePreviewGap']=gap
        models.append(item)
        phy=name[:-5]+'.phy'
        if sources.candidates(phy):
            raw_phy=sources.read(phy)
            try:
                parsed_phy=decode_phy(raw_phy);phy_models[name]={'path':phy,'shapes':len(parsed_phy['shapes']),
                     'sha256':parsed_phy['sourceSHA256'],'scope':'available source geometry, not selected live collision branch'}
            except ValueError as error:
                phy_models[name]={'path':phy,'sha256':hashlib.sha256(raw_phy).hexdigest(),'gap':str(error),'appliedToPhysics':False}
    values={v for t in tiles for v in t['colors']}
    terrain={'schema':FORMAT,'world':'tutorial','tileOrigin':[min(x for x,z in coordinates),min(z for x,z in coordinates)],
             'tileCount':[2*radius+1,2*radius+1],'grid':{'width':(2*radius+1)*64+1},
             'bounds':{'min':[min(x for x,z in coordinates)*64,min(min(t['heights'])for t in tiles)*.01,min(z for x,z in coordinates)*64],
                       'max':[(max(x for x,z in coordinates)+1)*64,max(max(t['heights'])for t in tiles)*.01,(max(z for x,z in coordinates)+1)*64]},
             'sourceTiles':tiles,'sourceTextures':texture_rows,'sourceVertexColorSummary':{'unique16':len(values),'white16':values=={65535}},
             'verification':{'seamDifferencesPreserved':seam_audit(tiles),'sourceTileCount':len(tiles)},
             'scope':'explicit center/radius candidate window; original per-tile data, not observed residency or spawn'}
    manifest['mapWindow']={'url':write('maps/tutorial-window.json',terrain),'center':list(center),'radius':radius,'format':FORMAT}
    manifest['scenery']=models
    materials.update(tiles=mat_tiles,sources=sources.proofs)
    ground.update(tiles=light_tiles,vertexColor={'source':'RGB565','mode':'per-source-tile'},sources=sources.proofs)
    ground['configuration']['sourceGeometryWindow']=True
    write('maps/terrain-materials.json',materials);write('rendering/terrain-lighting.json',ground);write('manifest.json',manifest)
    report,provider=resolve(image,source,DEFAULT_APK,'APK_Default',base)
    if report['settings']['TerrainTileSight']!=radius:raise ValueError('Requested window differs from original Default radius')
    preview=export_preview(report,provider,base,destination,asset_prefix='/assets/geometry-map/')
    audit={'format':FORMAT,'sourceCenter':list(center),'sourceRadius':radius,'nativeOffsetOrder':offsets,
           'tileCount':len(tiles),'instanceCount':len(records),'modelCount':len(models),'preview':preview,
           'geometryGaps':gaps,'seamDifferencesPreserved':seam_audit(tiles),'sourceVertexColors':len(values),
           'pendingWaterChunks':sum(bool(f&0x10000)for t in light_tiles for f in t['runtimeFlags']),
           'sourcePHYModels':phy_models,'sources':sources.proofs,'addedAssetFiles':sorted(set(added)),
           'legacyActorCoordinateFramePreserved':True,'lightingSettingsChanged':False,'liveResidencyObserved':False}
    (output/'geometry-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
    return audit


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--legacy',type=Path,required=True);cli.add_argument('--output',type=Path,required=True)
    args=cli.parse_args()
    from analyze_native_resources import NativeImage
    result=build(NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes()),DEFAULT_SOURCE,args.legacy,args.output)
    print(json.dumps({k:result[k]for k in ('tileCount','instanceCount','modelCount','preview','seamDifferencesPreserved','sourceVertexColors')}))
