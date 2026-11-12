"""Audit the source/default static temple combination; never manufacture a fix.

The rectangle and position are explicit inspection inputs. Source/native CPU
requests and fresh detached completions are not an original Android frame.
"""
import hashlib
import itertools
import json
import math
import struct
import tempfile
import zipfile
from pathlib import Path

AREA=(-2640,-2540,140,250)
POINT=(-2611.41015625,185.84120178222656)

def in_area(position,area=AREA):
    return area[0]<position[0]<area[1]and area[2]<position[2]<area[3]

def transformed_box(bounds,matrix):
    corners=[[sum(matrix[c*4+r]*v[c]for c in range(3))+matrix[12+r]for r in range(3)]
             for v in itertools.product(*zip(*bounds))]
    return [min(v[r]for v in corners)for r in range(3)]+[max(v[r]for v in corners)for r in range(3)]

def compare_instance(original,preview):
    for key in ('id','model','sourceType','sourceWord8','position','quaternion','scale','tile'):
        if original[key]!=preview[key]:raise ValueError('Original/preview placement differs: '+key)

def layers(runtime,point=POINT):
    """Query the two explicitly supplied height ranges; do not select a spawn."""
    from analyze_native_resources import NativeImage
    from source_physics import SourcePhysics
    cfg=json.loads((Path(runtime)/'prototype/native-physics.json').read_text())
    engine=SourcePhysics(NativeImage(Path(cfg['library']).read_bytes()))
    def source(name):
        row=cfg['sourceFiles'][name];raw=Path(row['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=row['sha256']:raise ValueError('Original PHY differs')
        return raw
    terrain=json.loads(Path(cfg['terrain']).read_text());collision=json.loads(Path(cfg['collision']).read_text())
    lighting=json.loads(Path(cfg['terrainLighting']).read_text());flags={tuple(t['tile']):t['runtimeFlags']for t in lighting['tiles']}
    engine.load_world(terrain,collision,source,flags)
    return {'point':list(point),'explicitTopInputs':[132.84999084472656,173,196],
            'results':[engine.ground(point[0],point[1],top)for top in (132.84999084472656,173,196)],
            'scope':'original a8752c against a host-built static source container; top values are inspection inputs, not original spawn state'}

def entry_evidence():
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE
    from skill_attachments import decode_ftable
    source=Sources(DEFAULT_SOURCE)
    maps=decode_ftable(source.read('tables/map_info.tbl'),'map_id')
    tutorial,=[r for r in maps['rows']if r['map_id']==5 and r['file']=='world/tutorial.wld']
    spawns=decode_ftable(source.read('tables/player_spawn.tbl'),'Id')['rows']
    return {'mapInfoEnterPosition':[tutorial['enter_pos_'+a]for a in 'xyz'],
            'mapInfoEnterOrientation':tutorial['enter_pos_o'],
            'playerSpawnRows':len(spawns),'playerSpawnMapIDs':sorted({r['map_id']for r in spawns}),
            'tutorialPlayerSpawnRows':sum(r['map_id']==5 for r in spawns),
            'originalRuntimeEntryPositionKnown':False,'sources':source.proofs,
            'scope':'source table evidence; zero enter_pos is not assigned as a spawn; original parsed-message location is unavailable'}

def audit(runtime):
    from tutorial_map_geometry import local_output
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE
    from map_selection_evidence import DEFAULT_APK,apk_config
    from analyze_native_resources import NativeImage
    from native_device_selection_probe import NativeDeviceSelectionProbe
    from native_device_instance_probe import NativeDeviceInstanceProbe
    from native_entity_model_probe import NativeEntityModelProbe
    from device_instance_evidence import level_inputs
    from native_map_streaming_probe import NativeMapStreamingProbe
    from bdae_convert import BDAE
    from bdae_skin import compose,multiply
    from scene_collision import geometry_transforms
    from terrain_convert import read_instances
    from bres_world_bounds_evidence import inner_bres
    from native_bres_world_bounds_probe import NativeBresWorldBoundsProbe
    runtime=local_output(runtime);assets=runtime/'game-data/converted'
    manifest=json.loads((assets/'source-temple-sampling/manifest.json').read_text())
    cfg=json.loads((runtime/'prototype/native-physics.json').read_text());image=NativeImage(Path(cfg['library']).read_bytes())
    source=Sources(DEFAULT_SOURCE);apk=apk_config(DEFAULT_APK)
    with zipfile.ZipFile(DEFAULT_APK)as archive:options=json.loads(archive.read('assets/GameOptions.json'))
    selector=NativeDeviceSelectionProbe(image);settings={};configuration=[]
    for group,profile in options['profiles'].items():
        values=dict(selector.updates(profile,''));settings.update(values)
        configuration.append({'group':group,'values':{k:v for k,v in values.items()if k in ('ModelDetailLevel','ForceModelLodLevel','DeviceLayer','TerrainTileSight')}})
    settings={k:settings[k]for k in ('ModelDetailLevel','ForceModelLodLevel','DeviceLayer','TerrainTileSight')}
    settings['DeviceLayer']=selector.layer_clamp(settings['DeviceLayer'])
    if settings!=dict(ModelDetailLevel=0,ForceModelLodLevel=0,DeviceLayer=4,TerrainTileSight=2):raise ValueError('Original default selection changed')
    streaming=NativeMapStreamingProbe(image);center=streaming.center(*POINT);offsets=streaming.offsets(settings['TerrainTileSight'])['offsets']
    tiles={(center[0]+x,center[1]+z)for x,z in offsets}
    levels,overrides,_=level_inputs(source);query,gate=NativeDeviceInstanceProbe(image),NativeDeviceInstanceProbe(image)
    query.configure_levels(levels,overrides);gate.level_delegate=query.lookup
    requests=NativeEntityModelProbe(image);requests.load(source.read('world/tutorial/EntityConfig.xml'))
    initial=requests.static_initial(settings['ForceModelLodLevel'])
    originals=[];gated=[];window_rows=[]
    with tempfile.TemporaryDirectory()as tmp:
        for name in sorted(source.lookup):
            if not(name.startswith('world/tutorial/items/')and name.endswith('.itm')):continue
            raw=source.read(name);tx,tz=struct.unpack_from('<2i',raw,8)
            if (tx,tz)not in tiles:continue
            path=Path(tmp)/Path(name).name;path.write_bytes(raw);rows=read_instances(path);gate.load_itm(raw)
            for i,row in enumerate(rows):
                status=gate.admission(i,settings['ModelDetailLevel'],settings['DeviceLayer'])
                if row['sourceType']==2 and status=='admittedBeforeTypeFactory':window_rows.append(row)
                if not in_area(row['position']):continue
                gated.append({'id':row['id'],'model':row['model'],'tile':row['tile'],'sourceType':row['sourceType'],'admission':status})
                if row['sourceType']==2 and status=='admittedBeforeTypeFactory':originals.append(row)
        # Include every source owner tile in the original R2 request, not only
        # objects whose origins fall in the close inspection rectangle.
        all_preview={(tuple(i['tile']),i['id']):(item,i)for item in manifest['scenery']for i in item['instances']}
        window_requests={}
        for row in window_rows:
            key=tuple(row['tile']),row['id']
            if key not in all_preview:raise ValueError('Source request-window static object missing')
            item,inst=all_preview[key];compare_instance(row,inst)
            if row['model']not in window_requests:
                request=requests.fresh(row['model'],initial['requestedSlot'],initial['forceSingleSlot'],lambda n:bool(source.candidates(n)))
                if request['requests']!=[{'slot':0,'path':item['model']}]or len(source.candidates(item['model']))!=1:raise ValueError('Source request-window model differs')
                window_requests[row['model']]=request
        preview={(tuple(i['tile']),i['id']):(item,i)for item in manifest['scenery']for i in item['instances']if in_area(i['position'])}
        expected={(tuple(i['tile']),i['id'])for i in originals}
        if expected!=set(preview):raise ValueError('Original static combination differs from preview')
        models=[];completions=[]
        for name in sorted({i['model']for i in originals}):
            raw=source.read(name);path=Path(tmp)/'model.bdae';path.write_bytes(raw);reader=BDAE(path);parsed=reader.parse();nodes=geometry_transforms(reader,parsed)
            rows=[r for r in originals if r['model']==name]
            item=preview[(tuple(rows[0]['tile']),rows[0]['id'])][0]
            current=json.loads((assets/item['url'][8:]).read_text())
            if current['sourceSHA256']!=hashlib.sha256(raw).hexdigest()or len(current['meshes'])!=len(parsed['meshes']):raise ValueError('Model identity changed')
            for k,(a,b)in enumerate(zip(current['meshes'],parsed['meshes'])):
                if any(a.get(field)!=b.get(field)for field in ('positions','normals','uvs','indices','groups'))or a.get('sourceNodeTransform')!=nodes[k]:raise ValueError('Original geometry/node differs from preview')
            requested=requests.fresh(name,initial['requestedSlot'],initial['forceSingleSlot'],lambda n:bool(source.candidates(n)))
            if requested['requests']!=[{'slot':0,'path':name}]or requested['existsQueries']:raise ValueError('Default source model request differs')
            probe=NativeBresWorldBoundsProbe(image)
            for row in rows:
                compare_instance(row,preview[(tuple(row['tile']),row['id'])][1])
                # Re-read the original BRES each time. Re-preparing an already
                # prepared removable wrapper is not a fresh-load experiment.
                loaded=probe.load(inner_bres(raw));root=probe.scene(loaded['info'])
                native=probe.finish(root,row['position']+row['quaternion']+row['scale'],name)
                if len(parsed['meshes'])!=1:raise ValueError('New multiple-mesh assembly needs explicit union recovery')
                world=multiply(compose(row['position'],row['quaternion'],row['scale']),nodes[0]['matrix'])
                box=transformed_box(parsed['bounds'],world);delta=max(abs(a-b)for a,b in zip(box,native['worldBox']))
                tolerance=4*2**(math.floor(math.log2(max(1,*map(abs,box))))-23)
                if delta>tolerance:raise ValueError('Native completion/preview world bounds differ')
                completions.append({'model':name,'tile':row['tile'],'id':row['id'],'nativeBox':native['worldBox'],'previewBox':box,'maxDelta':delta,'tolerance':tolerance})
            models.append({'model':name,'sourceSHA256':hashlib.sha256(raw).hexdigest(),'instances':len(rows),'request':requested,'geometryAndNodesEqual':True})
    return {'format':'oc2-temple-assembly-evidence-v1','APK':apk,'configuration':configuration,'settings':settings,
            'inspectionArea':list(AREA),'explicitPoint':list(POINT),'nativeTileCenter':center,'sourceOffsetOrder':offsets,
            'gateRecords':gated,'models':models,'instances':completions,'sources':source.proofs,
            'requestWindow':{'staticCandidates':[{'model':r['model'],'tile':r['tile'],'id':r['id']}for r in window_rows],
                             'modelRequests':window_requests,'missingStaticInstances':0},
            'summary':{'models':len(models),'instances':len(completions),'missingStaticInstances':0,'extraStaticInstances':0},
            'scope':'APK defaults without override; phase0, empty dynamic-ID provider; original pre-factory/request/BRES/scene/completion CPU with named storage/graphics adapters',
            'layerQueries':layers(runtime),
            'entryEvidence':entry_evidence(),
            'originalAndroidFrameObserved':False,'nativeGPUSuccessSupplied':False,'gameplayOrGeometryChanged':False,
            'limits':['This is a conditional source/default request list, not original live asynchronous residency or final GPU drawing.',
                      'Bounding-box equality alone does not prove pixel equivalence or establish the original playable layer/spawn.',
                      'No missing surfaces, supports, positions, phase values or server scripts are invented.']}

if __name__=='__main__':
    import argparse
    from tutorial_map_geometry import local_output
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=local_output(a.output)
    if out.exists():raise ValueError('Preserve earlier evidence')
    result=audit(a.runtime);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result['summary']))
