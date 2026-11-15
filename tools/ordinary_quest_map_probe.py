"""Execute original static PHY/terrain queries on the isolated quest461 map.

Source row locations and explicit movement vectors are inspection inputs. No
quest approval, actual Android residency or full Hero frame is fabricated.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from analyze_native_resources import NativeImage
from ordinary_quest_map import FORMAT,NAMESPACE,LIBRARY_SHA
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from skill_attachments import decode_ftable
from source_physics import SourcePhysics
from tutorial_map_geometry import ROOT,local_output


def probe(candidate,output,library=ROOT/'analysis/raw/beff-native/library.so'):
    candidate,output=local_output(candidate),local_output(output)
    if output.exists():raise ValueError('Preserve previous original movement reports')
    assets=candidate/'assets'/NAMESPACE
    load=lambda n:json.loads((assets/n).read_text())
    manifest=load('manifest.json');terrain=load('terrain.json');collision=load('collision.json');ground=load('terrain-lighting.json')
    if manifest['format']!=FORMAT or any(r['world']!='dawnwatch'for r in(manifest,terrain,collision,ground))or terrain['mapId']!=1:
        raise ValueError('Not the isolated original map1 context')
    data=Path(library).read_bytes()
    if hashlib.sha256(data).hexdigest()!=LIBRARY_SHA:raise ValueError('Original native version differs')
    files=collision['sourceFiles']
    def raw(name):
        record=files[name];p=(candidate/record['file']).resolve()
        if candidate.resolve()not in p.parents:raise ValueError('Candidate source file escapes private export')
        value=p.read_bytes()
        if hashlib.sha256(value).hexdigest()!=record['sha256']:raise ValueError('Original collision byte hash differs')
        return value
    physics=SourcePhysics(NativeImage(data))
    result=physics.load_world(terrain,collision,raw,{tuple(t['tile']):t['runtimeFlags']for t in ground['tiles']})
    source=Sources(DEFAULT_SOURCE)
    npc=next(r for r in decode_ftable(source.read('tables/creature_spawns.tbl'))['rows']if r['id']==6598)
    objects=[r for r in decode_ftable(source.read('tables/staticobject_spawns.tbl'))['rows']if r['map']==1 and r['Entry']==467 and r['phasing_id']==0]
    if len(objects)!=11:raise ValueError('Original ordinary-object population changed')
    points=[]
    for kind,row in[('npc',npc)]+[('gear',r)for r in objects]:
        x,y,z=(row['position_'+axis]for axis in'xyz')
        points.append({'kind':kind,'spawnId':row['id'],'sourcePosition':[x,y,z],
            'terrain':physics.sample(x,z),'ground':physics.ground(x,z,y+2),'available':physics.available(x,z)})
    if not all(p['available']for p in points):raise ValueError('A required source task point is not in a dry cell')
    start=copy.deepcopy(points[0]['sourcePosition']);start[1]=points[0]['ground']['height'];position=start[:];trace=[]
    for frame in range(30):
        movement=physics.move(position,[0,0,-.16]);trace.append(movement);position=movement['position']
    if position[2]>=start[2]-4.7:raise ValueError('Original southward dry movement did not advance')
    report={'format':'oc2-ordinary-quest-map1-native-movement-v1','world':'dawnwatch','mapId':1,'librarySHA256':LIBRARY_SHA,
        'load':result,'sourcePoints':points,'sourceTerrainLightFlagsUsed':True,
        'straightSourceMove':{'start':start,'inputPerStep':[0,0,-.16],'steps':30,'end':position,'trace':trace},
        'sourceRoutines':['a8674c','a8b790','a8752c','a878c0','3394b4'],
        'savesChanged':False,'originalFullHeroFrameExecuted':False,
        'limits':['Explicit four-cell static containers and test planar input, not actual Android residency or full Hero update.',
        'Dry task ground only. Water/airborne/dynamic actor registration are not inferred.','Source NPC/object placements are retained; sampled support height does not overwrite their original table Y.']}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return report


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--candidate',type=Path,required=True);cli.add_argument('--output',type=Path,required=True)
    args=cli.parse_args();r=probe(args.candidate,args.output)
    print(json.dumps({'tiles':r['load']['tiles'],'instances':r['load']['instances'],'shapes':r['load']['shapes'],'drySourcePoints':len(r['sourcePoints']),'movementEnd':r['straightSourceMove']['end']}))
