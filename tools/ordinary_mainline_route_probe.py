"""Source map1 route feasibility for quest208, without task authorization.

Only two original dawnwatch cells and their original static PHY are supplied.
NPCs, geometry, source seams and saved characters are never moved or patched.
"""
import argparse
import collections
import hashlib
import json
import math
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from analyze_native_resources import NativeImage
from bdae_convert import BDAE
from map_loading_evidence import Sources,read_world_container
from native_device_instance_probe import NativeDeviceInstanceProbe
from ordinary_quest_map import DawnwatchGroups,LIBRARY_SHA
from resource_packs import DEFAULT_SOURCE
from scene_collision import apply_scene_transforms,decode_phy
from scene_lightmap_binding import material_request_slots
from scene_lightmaps import source_names,read_records,object_records
from scene_sampling import material_samplers
from selection_scene_candidate import settings
from skill_attachments import decode_ftable
from source_physics import SourcePhysics
from terrain_convert import read_instances
from terrain_materials import tile_materials,verify_native
from tutorial_map_geometry import ROOT,local_output,raw_tile,seam_audit
from tutorial_walk_collision import phy_candidates

FORMAT='oc2-ordinary-mainline208-route-v1'
CELLS=[(-5,0),(-4,0)]
sha=lambda b:hashlib.sha256(b).hexdigest()


def probe(output,source_path=DEFAULT_SOURCE,library=ROOT/'analysis/raw/beff-native/library.so'):
    output=local_output(output)
    if output.exists():raise ValueError('Choose a new private route output')
    image=NativeImage(Path(library).read_bytes())
    if sha(image.data)!=LIBRARY_SHA:raise ValueError('Wrong original ARM64 build')
    verify_native(image);source=Sources(source_path)
    world=read_world_container(source.read('world/dawnwatch.wld'))
    if world['configurationWords']!=[3,3,1]:raise ValueError('Original world configuration changed')
    spawns=decode_ftable(source.read('tables/creature_spawns.tbl'))['rows']
    endpoints=[next(r for r in spawns if r['id']==ident)for ident in(2335,2337)]
    if [(r['entry'],r['map'],r['phasing_id'],r['phase'])for r in endpoints]!=[(8,1,0,0),(778,1,0,0)]:raise ValueError('Original mainline endpoints differ')
    source_position=lambda r:[r['position_x'],r['position_y'],r['position_z']]
    a,b=map(source_position,endpoints)
    actual_cells={(math.floor(p[0]/64),math.floor(p[2]/64))for p in(a,b)}
    if actual_cells!=set(CELLS):raise ValueError('Original endpoint cell scope differs')
    output.mkdir(parents=True)
    def write(name,data):
        target=output/name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')
        return {'path':str(target.relative_to(ROOT)),'bytes':target.stat().st_size,'sha256':sha(target.read_bytes())}
    options,_=settings(image);levels=ET.fromstring(source.read('bdaeConfig.xml'));overrides=ET.fromstring(source.read('world/dawnwatch/bdaeInstanceConfig.xml'))
    query,gate=NativeDeviceInstanceProbe(image),NativeDeviceInstanceProbe(image)
    query.configure_levels([{'name':e.attrib['name'],'level':int(e.attrib['level']),'exceptions':[i.attrib['name']for i in e.findall('Instance')]}for e in levels.findall('Item')],
        [{'id':e.attrib['id'],'level':int(e.attrib['level'])}for e in overrides.findall('Item')]);gate.level_delegate=query.lookup
    entity=ET.fromstring(source.read('world/dawnwatch/EntityConfig.xml'))
    if any(len(entity.find(k))or entity.find(k).attrib for k in('Item','Object')):raise ValueError('New original static entity overrides')
    native=DawnwatchGroups(image);tiles=[];groups=[];placements=[];flags={};missing=[];model_rows=[];gaps=[];colliders=[];phy_sources={};source_files={}
    with tempfile.TemporaryDirectory(prefix='oc2-mainline-route-')as temp:
        for x,z in CELLS:
            stem=f'{x:04d}_{z:04d}';name=f'world/dawnwatch/terrain/{stem}.trn';raw=source.read(name)
            tile=raw_tile(raw,x,z);tile['tile']=[x,z];tiles.append(tile);material=tile_materials(raw)
            native.read(raw);group=native.groups(source,[x,z]);groups.append({'tile':[x,z],'source':name,'sourceSHA256':sha(raw),'textures':material['textures'],**group})
            flags[(x,z)]=[r['nativeFlags']for r in group['chunks']]
            for row in group['chunks']:
                absent=[material['textures'][i]for i in row['materialIndices']if i>=0 and not source.candidates(material['textures'][i])]
                if absent:missing.append({'tile':[x,z],'chunk':row['chunk'],'water':bool(row['nativeFlags']&0x10000),'paths':absent})
            itm=f'world/dawnwatch/items/{stem}.itm';raw_itm=source.read(itm);file=Path(temp)/(stem+'.itm');file.write_bytes(raw_itm);gate.load_itm(raw_itm)
            for index,row in enumerate(read_instances(file)):
                row['admission']=gate.admission(index,options['ModelDetailLevel'],options['DeviceLayer']);placements.append(row)
        for name in sorted({r['model']for r in placements if r['sourceType']==2}):
            instances=[r for r in placements if r['model']==name and r['sourceType']==2 and r['admission']=='admittedBeforeTypeFactory']
            row={'model':name,'sourcePresent':bool(source.candidates(name)),'admittedInstances':len(instances),'sourceTypes':[2]}
            if not row['sourcePresent']:
                gaps.append({'model':name,'stage':'model','reason':'Original resource absent'});model_rows.append(row);continue
            raw=source.read(name);row['sourceSHA256']=sha(raw);p=Path(temp)/'model.bdae';p.write_bytes(raw)
            try:
                reader=BDAE(p);data=apply_scene_transforms(reader,reader.parse());data['source']=name
                row['geometry']=write('models/'+sha(raw)+'.json',data)
                samplers=material_samplers(reader);row['effects']=sorted({r['effectPath']for r in samplers})
                row['textureReferences']=[{'material':r['material'],'slot':key,'path':value['texture'],'present':bool(source.candidates(value['texture']))}for r in samplers for key,value in r['samplers'].items()]
                row['partCount']=sum(len(m['groups'])for m in data['meshes']);row['meshCount']=len(data['meshes'])
            except ValueError as error:gaps.append({'model':name,'stage':'geometry','reason':str(error)})
            small,normal=phy_candidates(name);row['physicsCandidates']=[{'path':n,'present':bool(source.candidates(n))}for n in(small,normal)]
            if source.candidates(small):gaps.append({'model':name,'stage':'PHY','reason':'Original simplified PHY present; current mode unproven'})
            elif source.candidates(normal):
                raw_phy=source.read(normal)
                try:
                    decoded=decode_phy(raw_phy);phy_sources[normal]=decoded;target=output/'native-source'/normal;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw_phy)
                    source_files[normal]={'file':str(target.relative_to(output)),'sha256':sha(raw_phy)}
                    colliders.extend({**r,'sourcePHY':normal}for r in instances)
                except ValueError as error:gaps.append({'model':name,'stage':'PHY','reason':str(error)})
            bindings=[]
            for instance in instances:
                record=source_names('dawnwatch',*instance['tile'],slot=0)['record']
                if not source.candidates(record):bindings.append({'id':instance['id'],'record':record,'recordPresent':False});continue
                runs=material_request_slots(object_records(read_records(source.read(record)),instance['id']))
                atlases=[source_names('dawnwatch',*instance['tile'],slot=0,atlas=r['atlasIndex'])['texture']for r in runs]
                bindings.append({'id':instance['id'],'tile':instance['tile'],'record':record,'recordPresent':True,'partRows':len(runs),
                    'atlases':[{'path':p,'present':bool(source.candidates(p))}for p in atlases]})
            row['objectBindings']=bindings;model_rows.append(row)
    heights=[h for t in tiles for h in t['heights']]
    terrain={'format':'oc2-source-map-window-v1','world':'dawnwatch','mapId':1,'tileOrigin':[-5,0],'tileCount':[2,1],'grid':{'width':129},
        'bounds':{'min':[-320,min(heights)*.01,0],'max':[-192,max(heights)*.01,64]},'sourceTiles':tiles,'sourceVertexColorSummary':{'unique16':len({c for t in tiles for c in t['colors']})},
        'verification':{'seamDifferencesPreserved':seam_audit(tiles)},'scope':'Two original endpoint cells, not full scene residency'}
    collision={'format':'oc2-scene-collision-v2','world':'dawnwatch','mapId':1,'instances':colliders,'sources':phy_sources,'sourceFiles':source_files,'sourceWindow':terrain['bounds'],
        'scope':'Original normal PHY only when original simplified candidate absent; no collider generated from art.'}
    write('terrain.json',terrain);write('collision.json',collision);write('terrain-groups.json',groups);write('models.json',model_rows);write('placements.json',placements)
    physics=SourcePhysics(image);loaded=physics.load_world(terrain,collision,source.read,flags)
    endpoint_support=[{'spawnId':row['id'],'entry':row['entry'],'sourcePosition':source_position(row),'terrain':physics.sample(row['position_x'],row['position_z']),
        'ground':physics.ground(row['position_x'],row['position_z'],row['position_y']+2),'dryAvailable':physics.available(row['position_x'],row['position_z'])}for row in endpoints]
    line=[]
    for k in range(65):
        fraction=k/64;x=a[0]+(b[0]-a[0])*fraction;z=a[2]+(b[2]-a[2])*fraction
        cell=[math.floor(x/64),math.floor(z/64)];chunk=[math.floor(x-cell[0]*64)//8,math.floor(z-cell[1]*64)//8]
        group=next(g for g in groups if g['tile']==cell);r=group['chunks'][chunk[1]*8+chunk[0]]
        absent=[group['textures'][i]for i in r['materialIndices']if i>=0 and not source.candidates(group['textures'][i])]
        line.append({'fraction':fraction,'point':[x,z],'tile':cell,'chunk':chunk,'terrain':physics.sample(x,z),'ground':physics.ground(x,z,5),
            'dryAvailable':physics.available(x,z),'missingActiveTerrainTextures':absent})
    seam=[]
    cross=(a[2]+(b[2]-a[2])*(-256-a[0])/(b[0]-a[0]))
    for z in sorted({a[2],b[2],cross,*[float(i)for i in range(20,43)]}):
        seam.append({'z':z,'sides':[{'x':x,'terrain':physics.sample(x,z),'ground':physics.ground(x,z,5),'available':physics.available(x,z)}for x in(-256.001,-256.,-255.999)]})
    def walk(label,start,target):
        start=start[:];start[1]=physics.ground(start[0],start[2],start[1]+2)['height'];position=start[:];trace=[];crossed=False
        for step in range(1000):
            dx,dz=target[0]-position[0],target[2]-position[2];distance=math.hypot(dx,dz)
            if distance<.12:break
            delta=min(.12,distance);result=physics.move(position,[dx/distance*delta,0,dz/distance*delta]);new=result['position']
            if(position[0]<-256<=new[0])or(new[0]<-256<=position[0]):crossed=True
            trace.append({'step':step,'positionBefore':position,'distanceBefore':distance,**result});position=new
            if len(trace)>30 and max(math.dist(row['position'],position)for row in trace[-30:])<.001:break
        return {'label':label,'start':start,'target':target,'end':position,'horizontalDistanceRemaining':math.hypot(target[0]-position[0],target[2]-position[2]),
            'steps':len(trace),'crossedOriginalXMinus256Seam':crossed,'trace':trace,'scope':'Explicit .12-unit planar inputs through original a878c0; no task script or navigation inferred'}
    walks=[walk('NPC8-to-NPC778',a,b),walk('NPC778-to-NPC8',b,a)]
    def actor_walk(label,start,target):
        position=start[:];position[1]=physics.ground(position[0],position[2],position[1]+2)['height']
        initial=position[:];trace=[];crossed=False
        for step in range(600):
            dx,dz=target[0]-position[0],target[2]-position[2];distance=math.hypot(dx,dz)
            if distance<.18:break
            result=physics.actor_tick(label,position,(dx/distance*3.2,dz/distance*3.2),50,False)
            current=result['position']
            if(position[0]<-256<=current[0])or(current[0]<-256<=position[0]):crossed=True
            trace.append({'step':step,'positionBefore':position,'distanceBefore':distance,**result});position=current
            if len(trace)>30 and max(math.dist(r['position'],position)for r in trace[-30:])<.001:break
        return {'label':label,'start':initial,'target':target,'end':position,'horizontalDistanceRemaining':math.hypot(target[0]-position[0],target[2]-position[2]),
            'steps':len(trace),'crossedOriginalXMinus256Seam':crossed,'trace':trace,
            'scope':'Current SourcePhysics host actor + real original9e171c/9e1970, explicit50ms/3.2-unit-per-second input; not complete originalHero/animation/server'}
    actor_walks=[actor_walk('sourceActor-NPC8-to-NPC778',a,b),actor_walk('sourceActor-NPC778-to-NPC8',b,a)]
    all_missing=[r for r in model_rows for r in r.get('textureReferences',[])if not r['present']]
    report={'format':FORMAT,'mapId':1,'world':world,'taskId':208,'librarySHA256':LIBRARY_SHA,'endpoints':endpoints,'coordinates':CELLS,
        'counts':{'terrainTiles':2,'placements':len(placements),'sourceTypes':dict(collections.Counter(r['sourceType']for r in placements)),
            'sourceModels':len(model_rows),'decodedModels':sum('geometry'in r for r in model_rows),'physicsFiles':len(phy_sources),'physicsInstances':len(colliders)},
        'nativeWorld':loaded,'endpointSupport':endpoint_support,'lineSamples':line,'seamX':-256,'seamCrossingZ':cross,'seamSamples':seam,'walks':walks,'actorWalks':actor_walks,
        'missingTerrainChunks':missing,'missingModelTextures':all_missing,'gaps':gaps,'sourceProofs':source.proofs,
        'originalServerOrQuestApprovalProduced':False,'savesChanged':False,'lightsChanged':False,'runtimeChanged':False,
        'limits':['Original two-cell static host set; full native Hero frame, renderer/GPU, live object schedules and task approval not claimed.',
        'Native support and grounded walking only. Source NPC Y retained; support sampling never overwrites original table rows.',
        'Special shader family availability is recorded, not claimed rendered. No lighting or replacement texture produced.']}
    receipt=write('report.json',report)
    print(json.dumps({'report':receipt,'counts':report['counts'],'endpointSupport':endpoint_support,'walks':[{k:v for k,v in r.items()if k!='trace'}for r in walks],
        'actorWalks':[{k:v for k,v in r.items()if k!='trace'}for r in actor_walks],
        'missingTerrainChunks':len(missing),'missingModelTextures':len(all_missing),'gaps':gaps},ensure_ascii=False))
    return report


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--output',type=Path,required=True)
    cli.add_argument('--source',type=Path,default=DEFAULT_SOURCE);args=cli.parse_args();probe(args.output,args.source)
