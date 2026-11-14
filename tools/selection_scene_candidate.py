"""Export the original selection-map static background into an isolated candidate.

This never writes the running preview, delivery scripts or character saves.
Archive geometry and original DAT part order are retained. Unsupported effects,
missing source bindings and unobserved residency are explicit gaps, not fillers.
"""
import argparse
import copy
import configparser
import hashlib
import json
import math
import struct
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from bdae_convert import BDAE
from map_loading_evidence import Sources, read_world_container
from map_selection_evidence import DEFAULT_APK
from resource_packs import DEFAULT_SOURCE
from scene_alpha import recover_scene_alpha
from scene_baked_lighting import recover_model_lighting
from scene_collision import apply_scene_transforms
from scene_culling import recover_scene_culling
from scene_lightmap_binding import material_request_slots
from scene_lightmaps import read_records, object_records, source_names
from scene_lighting import zone_targets, ZONE_SHA256, f32
from scene_sampling import material_samplers
from scene_texture_sampling import recover_scene_sampling
from skill_attachments import decode_ftable
from terrain_convert import read_instances
from terrain_lighting import lightmap_requests, terrain_texture_encoding, loaded_chunk_flags, final_water_flags
from terrain_materials import tile_materials, mask_channels, effective_indices, SHADERS
from terrain_missing_textures import texture_image
from tutorial_map_geometry import ROOT, local_output, raw_tile, seam_audit

FORMAT = 'oc2-source-selection-scene-candidate-v1'
NAMESPACE = 'source-selection-scene'
WORLD_SHA = 'e0dabf946c541befa8bd2ede3aa59204e9724dfb253cf144418c41f81a16fc00'
ENTITY_SHA = 'b5258ac1adac8a09061c2d53260c5efc267db7ca9acedcd120b5e72f209a9f53'
CONFIGS = {
 'conf/game.conf':'df5b69a98d0422a59bf691c09f89447cae72f4c5776517d5578e93569dcf3565',
 'conf/game_a.conf':'523f61d1659df8513fbb808186b35c1f55207d4bd99651a6deb4567831995742',
 'conf/game_w.conf':'a07fdee8b2474afce4dfa1b4a60be5bd59869fe4d993f1b981e16dfc09493b77',
}
SCENE_CENTER = [-2583.0, -124.5, -100.0]
CAMERA_POSITION = [-2559.42, 140.26, -16.42]
BASE_REGION = 211


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def static_materials(source, reader, data):
    """Reuse verified source converters; unsupported branches fail closed."""
    data['sceneSampling'] = recover_scene_sampling(source.read, reader, data, allow_repeat_override=True)
    data['sceneAlpha'] = recover_scene_alpha(source.read, reader, data)
    data['sceneCulling'] = recover_scene_culling(source.read, reader, data)
    data['sceneBakedLighting'] = recover_model_lighting(reader, data, allow_repeat_override=True)
    return data


def settings(image):
    from native_device_selection_probe import NativeDeviceSelectionProbe
    from tutorial_preview_selection import mask_baseline
    with zipfile.ZipFile(DEFAULT_APK) as archive:
        config = json.loads(archive.read('assets/GameOptions.json'))
    selector = NativeDeviceSelectionProbe(image)
    result = dict(selector.updates(config['profiles']['GPU'], ''))
    keys = ('ModelDetailLevel', 'ForceModelLodLevel', 'DeviceLayer', 'ShowModelLightMap',
            'ShowTerrainLightMap', 'TerrainTileSight')
    result = {k: result[k] for k in keys}
    result['DeviceLayer'] = selector.layer_clamp(result['DeviceLayer'])
    if result != {'ModelDetailLevel': 0, 'ForceModelLodLevel': 0, 'DeviceLayer': 4,
                  'ShowModelLightMap': True, 'ShowTerrainLightMap': True, 'TerrainTileSight': 2}:
        raise ValueError('Original APK default map settings changed')
    return result, mask_baseline(config)


def binding_rows(source, item):
    path = source_names('selection', *item['tile'], slot=0)['record']
    if not source.candidates(path):
        return path, []
    records = object_records(read_records(source.read(path)), item['id'])
    result = []
    for r in material_request_slots(records):
        name = source_names('selection', *item['tile'], slot=0, atlas=r['atlasIndex'])['texture']
        result.append({'ordinal': r['sortKey'], 'atlas': name,
                       'uvTransform': r['uvParameter']['whenUniformPresent'],
                       'sourcePayload16Hex': r['payload16Hex']})
    return path, result


def splash_configs(source):
    result=[]
    for name,digest in CONFIGS.items():
        raw=source.read(name)
        if sha(raw)!=digest:raise ValueError('Original splash configuration changed')
        config=configparser.ConfigParser(strict=False);config.read_string(raw.decode('utf-8-sig'))
        splash=config['splash']
        center=[float(v)for v in splash['sceneCenter'].split(',')]
        camera=[float(v)for v in splash['cameraposition'].split(',')]
        if center!=SCENE_CENTER or camera!=CAMERA_POSITION or int(splash['mapid'])!=7:
            raise ValueError('Original selection-map configuration differs')
        result.append({'source':name,'sha256':digest,'sceneCenter':center,'cameraPosition':camera,'mapId':7})
    return result


def build(image, source_path, verified_assets, output):
    from native_device_instance_probe import NativeDeviceInstanceProbe
    from native_map_streaming_probe import NativeMapStreamingProbe
    from native_part_lightmaps import PartLightmapProbe
    from bres_world_bounds_evidence import inner_bres
    from scene_part_lightmaps import verify as verify_parts
    from terrain_materials import verify_native as verify_terrain
    from terrain_lighting import verify_native as verify_light

    output = local_output(output)
    if output.exists():
        raise ValueError('Choose a fresh candidate directory; existing work is preserved')
    source = Sources(source_path)
    original_world = source.read('world/selection.wld')
    entity = source.read('world/selection/EntityConfig.xml')
    if sha(original_world) != WORLD_SHA or sha(entity) != ENTITY_SHA:
        raise ValueError('Original selection container/configuration changed')
    if source.candidates('world/selection/bdaeInstanceConfig.xml'):
        raise ValueError('Selection now has a local override: retrace it')
    world = read_world_container(original_world)
    if list(world['configurationWords']) != [3, 3, 1]:
        raise ValueError('Original selection world words changed')
    if any(list(e) or e.attrib for e in ET.fromstring(entity)):
        raise ValueError('Selection EntityConfig is no longer empty')
    options, mask_policy = settings(image)
    configurations=splash_configs(source)
    verify_terrain(image); verify_light(image); verify_parts(image)
    for name, digest in SHADERS.items():
        if sha(source.read(name)) != digest:
            raise ValueError('Original terrain program changed')
    phase_table = decode_ftable(source.read('tables/phasing_area.tbl'), 'id')
    if any(r['map_id'] == 7 for r in phase_table['rows']):
        raise ValueError('Selection phase rows need separate recovery')
    zones_raw = source.read('tables/zones.tbl')
    if sha(zones_raw) != ZONE_SHA256:
        raise ValueError('Original zone table changed')
    zones = decode_ftable(zones_raw, 'ID')['rows']
    region, = [r for r in zones if r['ID'] == BASE_REGION and r['map_id'] == 7]
    # This is a source-backed bounded archive window, not proof of live residency.
    offsets = NativeMapStreamingProbe(image).offsets(options['TerrainTileSight'])['offsets']
    center_tile = [math.floor(f32(SCENE_CENTER[i]))>>6 for i in (0,2)]
    coordinates = sorted([[center_tile[0]+x, center_tile[1]+z] for x,z in offsets], key=lambda p:(p[1],p[0]))
    alternate = sorted([[-40+x, -1+z] for x,z in offsets], key=lambda p:(p[1],p[0]))

    model_levels = ET.fromstring(source.read('bdaeConfig.xml'))
    query, gate = NativeDeviceInstanceProbe(image), NativeDeviceInstanceProbe(image)
    query.configure_levels([{'name': e.attrib['name'], 'level': int(e.attrib['level']),
        'exceptions': [e.attrib['name'] for _ in e.findall('Instance')]}
        for e in model_levels.findall('Item')], [])
    gate.level_delegate = query.lookup
    assets = Path(verified_assets)
    old_manifest = json.loads((assets/'source-temple-sampling/manifest.json').read_text())
    old_models = {e['model']: e for e in old_manifest['scenery']}
    destination = output/'assets'/NAMESPACE
    destination.mkdir(parents=True)
    textures = {}
    files = []
    from terrain_missing_textures import recover_native_fallback, fallback_image, MISSING_PATH
    terrain_null_fallback = recover_native_fallback(image)
    def write(name, obj):
        target = destination/name; target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(obj, ensure_ascii=False, separators=(',',':'), allow_nan=False))
        files.append(name)
        return '/assets/'+NAMESPACE+'/'+name
    def texture(name, *, terrain_layer=False):
        if name in textures: return textures[name]['url']
        missing = not source.candidates(name)
        if missing and not (terrain_layer and name==MISSING_PATH):
            raise ValueError('No original source texture: '+name)
        raw = None if missing else source.read(name)
        decoded, fallback = texture_image(source, name, lambda n:fallback_image(n,terrain_null_fallback), terrain_layer=terrain_layer)
        filename = 'textures/'+(sha(decoded.tobytes()) if missing else sha(raw))+'.png'
        path = destination/filename; path.parent.mkdir(parents=True, exist_ok=True); decoded.save(path)
        textures[name] = {'url': '/assets/'+NAMESPACE+'/'+filename, 'sourceSHA256': None if missing else sha(raw),
                          'width':decoded.width, 'height':decoded.height,
                          'adapter':'ETC1/split source decoded to RGBA; existing browser sampler, not original GPU'}
        if fallback:textures[name]['nativeNullProviderFallback']=fallback
        files.append(filename)
        return textures[name]['url']

    tiles, material_tiles, light_tiles, placements, admissions = [], [], [], [], []
    pending_water = []
    with tempfile.TemporaryDirectory(prefix='oc2-selection-map-') as tmp:
        for x,z in coordinates:
            stem = f'{x:04d}_{z:04d}'
            name = f'world/selection/terrain/{stem}.trn'
            raw = source.read(name)
            tile = raw_tile(raw, x,z); tiles.append(tile)
            material = tile_materials(raw)
            names = [f'world/selection/layers/{stem}_{c}.msk' for c in range(4)]
            channels = [source.read(n) if source.candidates(n) else None for n in names]
            mask, classes = mask_channels(channels)
            material['mask'] = None
            if mask:
                filename = f'masks/{stem}.png'; path=destination/filename; path.parent.mkdir(parents=True,exist_ok=True); mask.save(path);files.append(filename)
                material['mask'] = {'url':'/assets/'+NAMESPACE+'/'+filename,'width':mask.width,'height':mask.height,
                    'flipY':False,'channels':[n if c is not None else None for n,c in zip(names,channels)]}
            minimum = f32(min(tile['heights'])*f32(.01)); flags=[]
            for i,(chunk, cl) in enumerate(zip(material['chunks'], classes)):
                water = struct.unpack_from('<h', raw, 24+i*material['recordStride']+4)[0]
                flag = final_water_flags(loaded_chunk_flags(chunk['flags']), f32(water*f32(.01)), minimum)
                flags.append(flag)
                chunk.update(maskClasses=cl, effectiveIndices=effective_indices(chunk['indices'],cl), sourceWaterPending=bool(flag&0x10000))
                if flag&0x10000:pending_water.append({'tile':[x,z],'chunk':chunk['chunk']})
            material['textures'] = [{'sourcePath':n,'url':texture(n,terrain_layer=True)} for n in material['textures']]
            material_tiles.append(material)
            requests = lightmap_requests('selection',x,z)
            chosen = next((n for n in requests if source.candidates(n)),None)
            if chosen is None: raise ValueError('No original terrain lightmap candidate')
            encoded = source.read(chosen)
            light_tiles.append({'tile':[x,z],'source':name,'sourceSHA256':sha(raw),'runtimeFlags':flags,
                'waterClearedByTileMinimumBound':not any(f&0x10000 for f in flags),
                'lightmap':{'sourcePath':chosen,'url':texture(chosen),'sha256':sha(encoded),
                    'fallback':chosen!=requests[0],**terrain_texture_encoding(encoded)},
                'requests':[{'sourcePath':n,'present':bool(source.candidates(n))}for n in requests]})
            itm = f'world/selection/items/{stem}.itm'
            if not source.candidates(itm):continue
            raw_itm=source.read(itm); file=Path(tmp)/(stem+'.itm'); file.write_bytes(raw_itm)
            gate.load_itm(raw_itm)
            for i,row in enumerate(read_instances(file)):
                status=gate.admission(i,options['ModelDetailLevel'],options['DeviceLayer'])
                placements.append(row)
                admissions.append({**row,'admission':status,'sourceITM':itm,
                    'modelSlot':0 if row['sourceType']==2 else None})

        if len(placements)!=163 or sum(r['sourceType']==2 for r in placements)!=151:
            raise ValueError('Bounded original placement population changed')
        part_probe=PartLightmapProbe(image)
        models=[]; gaps=[]; reused=[]; bindings=[]
        for name in sorted({r['model']for r in placements if r['sourceType']==2}):
            original=source.read(name); filename=Path(tmp)/'source.bdae';filename.write_bytes(original)
            reader=BDAE(filename); fresh=apply_scene_transforms(reader,reader.parse())
            data=None
            try:
                if name in old_models:
                    data=json.loads((assets/old_models[name]['url'][8:]).read_text())
                    if data['sourceSHA256']!=sha(original) or any(fresh[k]!=data[k] for k in ('materials','meshes','sceneNodes')):
                        # Existing converters can add UV2/3 to mesh dictionaries;
                        # compare all raw/source-node fields, not derived additions.
                        if data['sourceSHA256']!=sha(original) or fresh['materials']!=data['materials'] or len(fresh['meshes'])!=len(data['meshes']) or any(
                            any(old.get(k)!=v for k,v in current.items()) for current,old in zip(fresh['meshes'],data['meshes'])):
                            raise ValueError('Previously verified conversion differs from original model/node bytes')
                    reused.append({'model':name,'sourceSHA256':sha(original),'priorURL':old_models[name]['url']})
                    data=copy.deepcopy(data)
                else:
                    data=static_materials(source,reader,fresh)
                if len(data['meshes'])!=1:raise ValueError('Multiple source meshes require their own part traversal')
                order=[r['material']for r in data['meshes'][0]['groups']]
                if sorted(order)!=list(range(len(data['materials']))):
                    raise ValueError('Shared or absent part/material references require separate recovery')
                refs=part_probe.references(inner_bres(original))
                if [r['localIndex']for r in refs]!=order or any(r['material']!=data['materials'][r['localIndex']]['name']for r in refs):
                    raise ValueError('Original part reference order differs')
                for material in data['materials']:texture(material['diffuse'])
                instances=[]; model_bindings=[]
                for row in admissions:
                    if row['model']!=name or row['sourceType']!=2:continue
                    if row['admission']!='admittedBeforeTypeFactory':
                        gaps.append({'id':row['id'],'model':name,'reason':'Original APK default admission rejected'})
                        continue
                    record,requests=binding_rows(source,row)
                    if not requests:
                        gaps.append({'id':row['id'],'model':name,'tile':row['tile'],'reason':'No original slot0 object DAT run','record':record})
                        continue
                    if [r['ordinal']for r in requests]!=list(range(len(requests))):
                        raise ValueError('Original material binding ordinal is not contiguous')
                    for b in requests:texture(b['atlas'])
                    model_bindings.append({'objectId':row['id'],'model':name,'tile':row['tile'],'recordPath':record,'bindings':requests})
                    instances.append({k:copy.deepcopy(row[k])for k in ('id','model','sourceType','sourceWord8','position','quaternion','scale','tile')})
                if instances:
                    bindings.extend(model_bindings)
                    data['source']=name
                    models.append({'model':name,'sourceSHA256':sha(original),
                        'url':write('models/'+sha(original)+'.json',data),'partToMaterial':order,'instances':instances})
            except ValueError as error:
                gaps.append({'model':name,'ids':[r['id']for r in placements if r['model']==name],
                    'reason':str(error),'sourceSHA256':sha(original),
                    'sourceEffects':sorted({m['effectPath']for m in material_samplers(reader)})})

    effects=[r for r in admissions if r['sourceType']!=2]
    # Preserve the source record and settled targets. Do not activate guessed
    # weather, extra lights or sky. The parent supplies verified scene uniforms.
    environment={'region':region,'settledTargets':zone_targets(region),
                 'activeOriginalStateObserved':False,'skyNotRestored':True,'runtimeWeatherNotRestored':True}
    geometry={'format':'oc2-source-map-window-v1','world':'selection','tileOrigin':[-43,-4],
        'tileCount':[5,5],'grid':{'width':321},'sourceTiles':tiles,
        'sourceVertexColorSummary':{'unique16':len({c for t in tiles for c in t['colors']}),
            'white16':all(c==65535 for t in tiles for c in t['colors'])},
        'verification':{'seamDifferencesPreserved':seam_audit(tiles),'sourceTileCount':len(tiles)},
        'scope':'25 original files in explicit sceneCenter conditional window; live center writer not yet proven'}
    from terrain_lighting import terrain_effect
    with tempfile.TemporaryDirectory()as tmp:
        p=Path(tmp)/'CustomEffects.bdae';p.write_bytes(source.read('CustomEffects.bdae')); effect=terrain_effect(BDAE(p))
    material_profile={'format':'oc2-terrain-materials-v1','world':'selection','tiles':material_tiles,
                      'fallback':texture('texture/white.tga') if source.candidates('texture/white.tga') else None,
                      'sources':source.proofs}
    # Existing loader requests unused -1 layers; a source base texture is a
    # safe transport placeholder only when the source shader prunes that layer.
    if material_profile['fallback']is None:
        material_profile['fallback']=material_tiles[0]['textures'][0]['url']
    terrain_profile={'format':'oc2-terrain-lighting-v1','world':'selection','effect':effect,
        'vertexColor':{'source':'RGB565','mode':'per-source-tile'},'tiles':light_tiles,
        'configuration':{'phase':0,'lightmapEnabled':True,'techniqueIndex':0,'shadowMap':False,
            'observedOriginalDevice':False,'sourceGeometryWindow':True},'sources':source.proofs}
    manifest={'format':FORMAT,'world':'selection','mapId':7,'profile':'APK_Default',
        'worldContainer':world,'originalSettings':options,'originalMaskBaseline':mask_policy,
        'originalSplashConfigs':configurations,
        'conditionalWindow':{'center':SCENE_CENTER,'centerTile':center_tile,'radius':2,'tiles':coordinates,
            'alternateCameraPosition':CAMERA_POSITION,'alternateCameraWindow':alternate,
            'originalRequestOffsets':offsets,'originalLiveCenterProven':False},
        'terrain':write('terrain.json',geometry),'terrainMaterials':write('terrain-materials.json',material_profile),
        'terrainLighting':write('terrain-lighting.json',terrain_profile),'models':models,
        'bindings':bindings,'textures':textures,'environment':environment,'gaps':gaps,
        'pendingEffects':effects,'pendingWaterChunks':pending_water,
        'inventedLights':False,'inventedGeometry':False,'savesChanged':False,
        'scope':'Original selection map static candidate; no camera, character, UI, weather, GPU success or complete original frame claimed'}
    write('manifest.json',manifest)
    audit={'format':FORMAT,'tiles':len(tiles),'staticSourceInstances':151,'sourceEffects':12,
        'displayedModels':len(models),'displayedStaticInstances':sum(len(m['instances'])for m in models),
        'sourceModelCount':43,'reusedSourceModels':reused,'gaps':gaps,'pendingWaterChunks':pending_water,
        'admissions':admissions,'sourceProofs':source.proofs,'files':sorted(set(files)),
        'sourceSceneCenterChainGap':'53b5c8 parses conf sceneCenter into splash+68; 539674 passes world+164 to streamer. Connecting writer remains unproven.',
        'lightingChanged':False,'liveOriginalResidencyObserved':False,'savesChanged':False}
    (output/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
    return audit


if __name__=='__main__':
    from analyze_native_resources import NativeImage
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--verified-assets',type=Path,required=True)
    cli.add_argument('--output',type=Path,required=True)
    cli.add_argument('--source',type=Path,default=DEFAULT_SOURCE)
    a=cli.parse_args()
    r=build(NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes()),a.source,a.verified_assets,a.output)
    print(json.dumps({**{k:r[k]for k in ('tiles','staticSourceInstances','sourceEffects','displayedModels','displayedStaticInstances','sourceModelCount')},'pendingWaterChunks':len(r['pendingWaterChunks'])}))
