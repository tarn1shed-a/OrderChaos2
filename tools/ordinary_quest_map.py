"""Bounded original map1/dawnwatch context for the ordinary quest461 adapter.

Only the reviewed four-cell quest461 or two-cell quest208 original windows,
their own masks/textures/DAT and PHY enter the output. This creates no quest
rules, saves, scenery or source server code. Default461 bytes stay unchanged.
Unsupported material families remain explicit omissions, never generic fills.
"""
import argparse
import collections
import copy
import hashlib
import json
import re
import struct
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from analyze_native_resources import NativeImage
from bdae_convert import BDAE
from map_loading_evidence import Sources, read_world_container
from resource_packs import DEFAULT_SOURCE
from scene_baked_lighting import recover_model_lighting
from scene_collision import apply_scene_transforms, decode_phy
from scene_lightmap_binding import material_request_slots
from scene_lightmaps import source_names, read_records, object_records
from selection_scene_candidate import ROOT, local_output, settings, static_materials
from selection_scene_water_floor_group_copy import controlled_copy, uniform_names
from skill_attachments import decode_ftable
from terrain_convert import read_instances
from terrain_lighting import lightmap_requests, terrain_texture_encoding, terrain_effect
from terrain_materials import tile_materials, mask_channels, effective_indices, verify_native
from terrain_missing_textures import texture_image
from terrain_water_floor import NativeFloor
from tutorial_map_geometry import raw_tile, seam_audit
from tutorial_walk_collision import phy_candidates

FORMAT='oc2-ordinary-quest-map1-v1'
NAMESPACE='source-ordinary-quest-map1'
COORDINATES=[(x,z)for z in(-5,-4)for x in(-1,0)]
LIBRARY_SHA='77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4'
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def area_inputs(coordinates=None,namespace=None,source_area=None):
    """Only the two reviewed task windows; this is not a full-map exporter."""
    area=source_area or 'quest461'
    allowed={'quest461':COORDINATES,'mainline208':[(-5,0),(-4,0)]}
    if area not in allowed:raise ValueError('Only reviewed original quest461/mainline208 areas are supported')
    rows=allowed[area]if coordinates is None else coordinates
    if not isinstance(rows,(list,tuple))or not rows or any(not isinstance(r,(list,tuple))or len(r)!=2 or any(type(v)is not int for v in r)for r in rows):
        raise ValueError('Expected explicit original integer cell coordinates')
    rows=[tuple(r)for r in rows]
    if len(set(rows))!=len(rows)or set(rows)!=set(allowed[area]):raise ValueError('Coordinates differ from the bounded original task area')
    rows=sorted(rows,key=lambda p:(p[1],p[0]))
    name=namespace or(NAMESPACE if area=='quest461'else'source-mainline208-map1')
    if not isinstance(name,str)or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}',name):raise ValueError('Expected one safe private asset namespace')
    if area=='mainline208'and name==NAMESPACE:raise ValueError('Mainline208 cannot replace the frozen quest461 namespace')
    return rows,name,area


class DawnwatchGroups(NativeFloor):
    """Same pinned original grouping consumer, with dawnwatch-owned mask bytes."""
    def slice(self,start,stop):
        from unicorn import UC_HOOK_CODE
        e=self.e;h=e.uc.hook_add(UC_HOOK_CODE,lambda uc,a,n,d:uc.emu_stop(),begin=stop,end=stop)
        try:e.uc.emu_start(start,stop,count=2000000)
        finally:e.uc.hook_del(h)
        if e.get('PC')!=stop:raise ValueError('Original grouping slice exceeded boundary')

    def groups(self,source,tile):
        e=self.e;chunks=e.r(self.tile+0x80,'Q')[0]
        original=[list(e.r(chunks+j*168+0x50,'5h'))for j in range(64)];loaded=[]
        for channel in range(4):
            name='world/dawnwatch/layers/%04d_%04d_%d.msk'%(*tile,channel)
            if not source.candidates(name):continue
            raw=source.read(name);p=e.alloc(len(raw));e.uc.mem_write(p,raw)
            e.call(0x359ad0,{'X0':self.tile,'W1':channel,'X2':p,'W3':len(raw)});loaded.append(name)
        classes=[list(e.r(chunks+j*168+0x5e,'4B'))for j in range(64)]
        e.set('SP',e.STACK);e.set('X0',self.tile);self.slice(0x355f48,0x3560b8)
        pruned=[list(e.r(chunks+j*168+0x50,'5h'))for j in range(64)]
        if pruned!=[effective_indices(a,c)for a,c in zip(original,classes)]:raise ValueError('Native pruning differs')
        for j,a in enumerate(original):e.w(chunks+j*168+0x50,'5h',*a)
        e.call(0x355f28,{'X0':self.tile},limit=5000000)
        count=e.r(self.tile+0xb0,'I')[0];order=list(e.r(e.r(self.tile+0xa0,'Q')[0],'64B'))
        offsets=list(e.r(e.r(self.tile+0xa8,'Q')[0],str(count+1)+'B'))
        if sorted(order)!=list(range(64))or offsets[0]!=0 or offsets[-1]!=64:raise ValueError('Original material group traversal differs')
        members=[]
        for j in range(64):
            p=chunks+j*168;e.set('X19',p);self.slice(0x3509fc,0x350a40)
            members.append({'chunk':[j%8,j//8],'rawIndices':original[j],'maskClasses':classes[j],
                'memberIndices':list(e.r(p+0x50,'5h')),'memberMacro':e.get('W0'),
                'sourceGroup':e.r(p+0x5c,'H')[0],'nativeFlags':e.r(p+0x70,'I')[0]})
        representatives=[]
        for group in range(count):
            e.set('X19',self.tile);e.set('W24',offsets[group]);e.set('X25',0xa8);self.slice(0x35650c,0x356524)
            rep=e.get('W27')
            if rep!=order[offsets[group]]or e.get('X0')!=chunks+rep*168:raise ValueError('Original representative selection differs')
            representatives.append(rep)
        for j,row in enumerate(members):
            group=row['sourceGroup'];rep=representatives[group]
            if j not in order[offsets[group]:offsets[group+1]]:raise ValueError('Original membership differs')
            representative=members[rep]
            row.update(representativeChunk=representative['chunk'],materialIndices=representative['memberIndices'],materialMacro=representative['memberMacro'])
        return {'chunks':members,'groupOrder':order,'groupOffsets':offsets,'representatives':representatives,
            'maskSources':loaded,'nativeFull355f28':True,'native35650c':True,'freshGlobal2527a10':e.r(0x2527a10,'B')[0]}


def build(output,source_path=DEFAULT_SOURCE,library=ROOT/'analysis/raw/beff-native/library.so',*,coordinates=None,namespace=None,source_area=None):
    coordinates,namespace,source_area=area_inputs(coordinates,namespace,source_area)
    output=local_output(output)
    if output.exists():raise ValueError('Choose a new isolated output directory')
    image=NativeImage(Path(library).read_bytes())
    if sha(image.data)!=LIBRARY_SHA:raise ValueError('Original ARM64 library differs')
    verify_native(image);source=Sources(source_path)
    maprow=next(r for r in decode_ftable(source.read('tables/map_info.tbl'),'map_id')['rows']if r['map_id']==1)
    if maprow['file']!='world/dawnwatch.wld':raise ValueError('Original map resource mapping differs')
    world=read_world_container(source.read(maprow['file']))
    if world['configurationWords']!=[3,3,1]:raise ValueError('Original world tile configuration differs')
    entity=ET.fromstring(source.read('world/dawnwatch/EntityConfig.xml'))
    if any(len(entity.find(key))or entity.find(key).attrib for key in('Item','Object')):raise ValueError('New original static entity overrides need review')
    options,mask_policy=settings(image)
    from native_device_instance_probe import NativeDeviceInstanceProbe
    levels=ET.fromstring(source.read('bdaeConfig.xml'));overrides=ET.fromstring(source.read('world/dawnwatch/bdaeInstanceConfig.xml'))
    query=NativeDeviceInstanceProbe(image);gate=NativeDeviceInstanceProbe(image)
    query.configure_levels([{'name':e.attrib['name'],'level':int(e.attrib['level']),
        'exceptions':[i.attrib['name']for i in e.findall('Instance')]}for e in levels.findall('Item')],
        [{'id':e.attrib['id'],'level':int(e.attrib['level'])}for e in overrides.findall('Item')])
    gate.level_delegate=query.lookup
    destination=output/'assets'/namespace;destination.mkdir(parents=True)
    textures={};files=[]
    def write(name,data):
        p=destination/name;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n');files.append(p)
        return '/assets/'+namespace+'/'+name
    def texture(name,terrain=False):
        if name in textures:return textures[name]['url']
        if not source.candidates(name):raise ValueError('Original texture absent: '+name)
        raw=source.read(name);decoded,proof=texture_image(source,name,None,terrain_layer=terrain)
        if proof:raise ValueError('No invented texture fallback in this map')
        filename='textures/'+sha(raw)+'.png';p=destination/filename;p.parent.mkdir(parents=True,exist_ok=True);decoded.save(p);files.append(p)
        textures[name]={'url':'/assets/'+namespace+'/'+filename,'sourceSHA256':sha(raw),'width':decoded.width,'height':decoded.height}
        return textures[name]['url']
    tiles=[];materials=[];lighting=[];placements=[];admissions=[];groups=[];pending_water=[];missing_terrain=[]
    native=DawnwatchGroups(image);indices=native.triangle_indices()
    with tempfile.TemporaryDirectory(prefix='oc2-ordinary-map-')as temp:
        for x,z in coordinates:
            stem=f'{x:04d}_{z:04d}';name=f'world/dawnwatch/terrain/{stem}.trn';raw=source.read(name)
            tile=raw_tile(raw,x,z);tile['tile']=[x,z];tiles.append(tile);profile=tile_materials(raw)
            native.read(raw);group=native.groups(source,[x,z]);group.update(tile=[x,z],source=name,sourceSHA256=sha(raw));groups.append(group)
            channels=[source.read(p)if source.candidates(p)else None for p in [f'world/dawnwatch/layers/{stem}_{i}.msk'for i in range(4)]]
            mask,classes=mask_channels(channels);profile['mask']=None
            if mask:
                file='masks/'+stem+'.png';p=destination/file;p.parent.mkdir(parents=True,exist_ok=True);mask.save(p);files.append(p)
                profile['mask']={'url':'/assets/'+namespace+'/'+file,'width':mask.width,'height':mask.height,'flipY':False}
            flags=[]
            for chunk,row,cl in zip(profile['chunks'],group['chunks'],classes):
                if row['rawIndices']!=chunk['indices']or row['maskClasses']!=cl:raise ValueError('Original material input differs')
                chunk.update(maskClasses=cl,rawEffectiveIndices=effective_indices(chunk['indices'],cl),
                    effectiveIndices=row['materialIndices'],textureLayerMask=row['materialMacro'],representativeChunk=row['representativeChunk'],
                    sourceWaterPending=bool(row['nativeFlags']&0x10000),nativeFlags=row['nativeFlags'])
                absent=[profile['textures'][i]for i in row['materialIndices']if i>=0 and not source.candidates(profile['textures'][i])]
                if absent:
                    chunk['sourceResourcePending']=absent
                    missing_terrain.append({'tile':[x,z],'chunk':chunk['chunk'],'water':chunk['sourceWaterPending'],'missingTextures':absent})
                flags.append(row['nativeFlags'])
                if chunk['sourceWaterPending']:pending_water.append({'tile':[x,z],'chunk':chunk['chunk']})
            profile['textures']=[{'sourcePath':n,'url':texture(n,True)if source.candidates(n)else None}for n in profile['textures']];materials.append(profile)
            requests=lightmap_requests('dawnwatch',x,z);selected=next((n for n in requests if source.candidates(n)),None)
            if selected is None:raise ValueError('Original dawnwatch terrain lightmap absent')
            encoded=source.read(selected);lighting.append({'tile':[x,z],'source':name,'sourceSHA256':sha(raw),'runtimeFlags':flags,
                'waterClearedByTileMinimumBound':not any(f&0x10000 for f in flags),'lightmap':{'sourcePath':selected,'url':texture(selected),
                'sha256':sha(encoded),'fallback':selected!=requests[0],**terrain_texture_encoding(encoded)}})
            itm=f'world/dawnwatch/items/{stem}.itm'
            if not source.candidates(itm):continue
            raw_itm=source.read(itm);p=Path(temp)/(stem+'.itm');p.write_bytes(raw_itm);gate.load_itm(raw_itm)
            for index,row in enumerate(read_instances(p)):
                status=gate.admission(index,options['ModelDetailLevel'],options['DeviceLayer'])
                row['admission']=status;placements.append(row);admissions.append({'tile':[x,z],'id':row['id'],'status':status})
        scenery=[];bindings=[];gaps=[];colliders=[];phy_sources={};source_files={}
        for name in sorted({r['model']for r in placements if r['sourceType']==2}):
            instances=[r for r in placements if r['sourceType']==2 and r['model']==name and r['admission']=='admittedBeforeTypeFactory']
            if not instances:continue
            original=source.read(name);p=Path(temp)/'model.bdae';p.write_bytes(original);reader=BDAE(p)
            small,normal=phy_candidates(name)
            if source.candidates(small):gaps.append({'model':name,'stage':'collision','reason':'Simplified PHY exists; active mode needs explicit source provider'})
            elif source.candidates(normal):
                raw_phy=source.read(normal);decoded=decode_phy(raw_phy);phy_sources[normal]=decoded
                relative='native-source/'+normal;target=output/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw_phy)
                source_files[normal]={'file':str(target.relative_to(output)),'sha256':sha(raw_phy)}
                colliders.extend({**copy.deepcopy(r),'sourcePHY':normal}for r in instances)
            try:
                data=apply_scene_transforms(reader,reader.parse())
                effects={m['effectPath']for m in __import__('scene_sampling').material_samplers(reader)}
                if 'ut_lightmap_shake_gray_trans.bdae'in effects:
                    __import__('scene_wind_identity').recover(source.read,reader,data,image)
                elif 'ut_lightmap_gray_trans.bdae'in effects:
                    __import__('scene_gray_materials').recover(source.read,reader,data,image)
                else:
                    data['sceneSampling']=__import__('scene_texture_sampling').recover_scene_sampling(source.read,reader,data,allow_repeat_override=True)
                    data['sceneAlpha']=__import__('scene_alpha').recover_scene_alpha(source.read,reader,data)
                    data['sceneCulling']=__import__('scene_culling').recover_scene_culling(source.read,reader,data)
                    data['sceneBakedLighting']=recover_model_lighting(reader,data,allow_repeat_override=True)
                if len(data['meshes'])!=1:raise ValueError('Multiple source meshes need original part traversal')
                order=[g['material']for g in data['meshes'][0]['groups']]
                if sorted(order)!=list(range(len(data['materials']))):raise ValueError('Shared or absent source part/material references')
                for material in data['materials']:texture(material['diffuse'])
                accepted=[]
                for instance in instances:
                    record=source_names('dawnwatch',*instance['tile'],slot=0)['record']
                    if not source.candidates(record):raise ValueError('Original object lightmap DAT absent')
                    rows=material_request_slots(object_records(read_records(source.read(record)),instance['id']))
                    if not rows:raise ValueError('Original object DAT run absent')
                    b=[]
                    for r in rows:
                        atlas=source_names('dawnwatch',*instance['tile'],slot=0,atlas=r['atlasIndex'])['texture'];texture(atlas)
                        b.append({'ordinal':r['sortKey'],'atlas':atlas,'uvTransform':r['uvParameter']['whenUniformPresent'],'sourcePayload16Hex':r['payload16Hex']})
                    if [r['ordinal']for r in b]!=list(range(len(b))):raise ValueError('Original material ordinal is not contiguous')
                    bindings.append({'objectId':instance['id'],'model':name,'tile':instance['tile'],'recordPath':record,'bindings':b});accepted.append(instance)
                data['source']=name;data['sourceSHA256']=sha(original)
                scenery.append({'model':name,'sourceSHA256':sha(original),'url':write('models/'+sha(original)+'.json',data),'partToMaterial':order,'instances':accepted})
            except ValueError as error:gaps.append({'model':name,'stage':'material','instances':[r['id']for r in instances],'reason':str(error)})
        p=Path(temp)/'effects.bdae';p.write_bytes(source.read('CustomEffects.bdae'));effect=terrain_effect(BDAE(p))
    colors={v for t in tiles for v in t['colors']}
    minimum_x,minimum_z=(min(p[i]for p in coordinates)for i in(0,1))
    maximum_x,maximum_z=(max(p[i]for p in coordinates)for i in(0,1))
    width,height=maximum_x-minimum_x+1,maximum_z-minimum_z+1
    terrain={'format':'oc2-source-map-window-v1','world':'dawnwatch','mapId':1,'tileOrigin':[minimum_x,minimum_z],'tileCount':[width,height],'grid':{'width':width*64+1},
        'sourceTiles':tiles,'sourceVertexColorSummary':{'unique16':len(colors),'white16':colors=={65535}},
        'bounds':{'min':[minimum_x*64,min(min(t['heights'])for t in tiles)*.01,minimum_z*64],'max':[(maximum_x+1)*64,max(max(t['heights'])for t in tiles)*.01,(maximum_z+1)*64]},
        'verification':{'sourceTileCount':len(tiles),'seamDifferencesPreserved':seam_audit(tiles)}}
    first_available=next(t['url']for p in materials for t in p['textures']if t['url'])
    material_profile={'format':'oc2-terrain-materials-v1','world':'dawnwatch','tiles':materials,'fallback':first_available,
        'sources':source.proofs,'nativeRepresentativeMaterialTransfer':True}
    terrain_lighting={'format':'oc2-terrain-lighting-v1','world':'dawnwatch','tiles':lighting,'effect':effect,'vertexColor':{'source':'RGB565','mode':'per-source-tile'},
        'configuration':{'phase':0,'lightmapEnabled':True,'techniqueIndex':0,'shadowMap':False,'observedOriginalDevice':False,'sourceGeometryWindow':True},'sources':source.proofs}
    collision={'format':'oc2-scene-collision-v2','world':'dawnwatch','mapId':1,'instances':colliders,'sources':phy_sources,
        'sourceFiles':source_files,'sourceWindow':terrain['bounds'],'inspectionUnavailableTiles':[],
        'limits':['Explicit source static set, not full Android residency or dynamic actor registry.','No substitute collider when original PHY is absent.']}
    from scene_lighting import zone_targets,color_vector
    from native_temple_ambient import TempleAmbientProbe
    zone_rows=decode_ftable(source.read('tables/zones.tbl'),'ID')['rows'];base=next(r for r in zone_rows if r['ID']==3)
    zone_evidence=None
    if source_area=='mainline208':
        from ordinary_mainline_zone_probe import verify_route_region
        zone_evidence=verify_route_region(image,source)
    overlay_id=zone_evidence['overlayId']if zone_evidence else 9
    overlay=next(r for r in zone_rows if r['ID']==overlay_id)
    if base['map_id']!=1 or overlay['parent_ID']!=3 or overlay['phasing_id']!=0:raise ValueError('Original quest coastal environment changed')
    targets=zone_targets(overlay,base)
    rgb=TempleAmbientProbe(image).produce(overlay['light_ambient'],overlay['light_diffuse'],targets['intensities'],adds=(0.,0.))
    environment={'format':'oc2-ordinary-map1-source-environment-v1','world':'dawnwatch','mapId':1,'sourceRegionId':3,'sourceOverlayId':9,
        'base':base,'overlay':overlay,'targets':targets,'nativeRGB':rgb,
        'fog':{'near':overlay['fog_near'],'halfSpan':overlay['fog_half'],'color':color_vector(overlay['fog_color'])},
        'phaseFlagsInput':0,'environmentHistoryObserved':False,'originalFullZoneQueryExecuted':False,
        'compatibilityInitialization':'Settled original region3/overlay9 targets with explicit zero runtime RGB additions; no invented lamps or hand-tuned colors.',
        'selectionScope':'Quest461/NPC6598 and all11 phase0 gear coordinates lie in rectangle9. Phase2 overlays disabled. Remote polygon priorities/whole-world live updates not asserted.',
        'limits':['Explicit settled-target compatibility context, not original frame history, live region transition or recovered original server scene.','No weather effects, sky or extra lights constructed.']}
    if zone_evidence:
        environment.update(sourceOverlayId=overlay_id,
            compatibilityInitialization='Settled original region3/overlay5 targets with explicit zero runtime RGB additions; no invented lamps or hand-tuned colors.',
            selectionScope='Original4c2bcc/4c2cf4 containment at65 quest208 route points selects3/5, including actual polygon preparation. Full world-manager update/history not asserted.',
            sourceRouteRegionEvidence=zone_evidence)
    manifest={'format':FORMAT,'world':'dawnwatch','mapId':1,'profile':'APK_Default','sourceWorld':world,'sourceMapInfo':maprow,'originalSettings':options,
        'terrain':write('terrain.json',terrain),'terrainMaterials':write('terrain-materials.json',material_profile),'terrainLighting':write('terrain-lighting.json',terrain_lighting),
        'environment':write('environment.json',environment),
        'collision':write('collision.json',collision),'scenery':scenery,'models':scenery,'bindings':bindings,'textures':textures,'gaps':gaps,'admissions':admissions,
        'originalTerrainTriangleIndices':indices,'nativeGrouping':{'tiles':groups,'copyEvidence':controlled_copy(image),'uniforms':uniform_names(image)},
        'pendingEffects':[r for r in placements if r['sourceType']!=2],'pendingWaterChunks':pending_water,'missingTerrainChunks':missing_terrain,'sourceFiles':source_files,
        'geometryChanged':False,'savesChanged':False,'worldWrapperIsWebAdapter':True,'sourceProofs':source.proofs,
        'limits':['Original map1 archive window serving quest461. Compatibility gameplay is separate from original server approval.',
        'Unsupported decoration/shader branches remain omitted, not substituted. Water/sky are not claimed restored here.',
        'Lighting caller must supply this world own original region inputs; tutorial/selection profiles are forbidden.']}
    if source_area=='mainline208':
        manifest['sourceArea']={'name':source_area,'questId':208,'coordinates':coordinates,'namespace':namespace}
        manifest['limits'][0]='Original map1 archive window serving the original quest208 route. Task compatibility execution is separate from original server approval.'
    url=write('manifest.json',manifest)
    summary={'format':FORMAT,'manifest':url,'mapId':1,'world':'dawnwatch','tiles':len(tiles),'sourcePlacements':len(placements),
        'sourceStaticModels':len({r['model']for r in placements if r['sourceType']==2}),'renderModels':len(scenery),
        'renderInstances':sum(len(r['instances'])for r in scenery),'nativeColliders':len(colliders),'nativePHYFiles':len(phy_sources),
        'pendingWaterChunks':len(pending_water),'missingTerrainChunks':missing_terrain,'gaps':gaps,'savesChanged':False,'gpuVerified':False,'nativeMovementVerified':False,'librarySHA256':LIBRARY_SHA,
        'files':[{'path':str(p.relative_to(output)),'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size}for p in sorted(set(files))]}
    (output/'audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    return summary


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--output',type=Path,required=True)
    cli.add_argument('--source',type=Path,default=DEFAULT_SOURCE);cli.add_argument('--library',type=Path,default=ROOT/'analysis/raw/beff-native/library.so')
    cli.add_argument('--coordinates',help='JSON array of the already reviewed original cells');cli.add_argument('--namespace')
    cli.add_argument('--source-area',choices=['quest461','mainline208'])
    args=cli.parse_args();report=build(args.output,args.source,args.library,coordinates=json.loads(args.coordinates)if args.coordinates else None,namespace=args.namespace,source_area=args.source_area)
    print(json.dumps({k:report[k]for k in('tiles','sourcePlacements','renderModels','renderInstances','nativeColliders','nativePHYFiles','pendingWaterChunks')},ensure_ascii=False))
