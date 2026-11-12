"""Source quest/camera clues, without inventing a first tutorial spawn.

The known camera-7 end position is a post-cinematic role position. Camera 8,
selected after OC_A, has no explicit end position. Missing server task scripts
and the first EnterMap payload remain missing.
"""
import configparser
import hashlib
import json
from pathlib import Path

def camera_track(section,index):
    """Preserve literal camera data, including CURRENT and P-target syntax."""
    prefix='w'+str(index);count=int(section[prefix+'pointcount'])
    if not 1<=count<=32:raise ValueError('Camera point count outside inspection scope')
    points=[]
    for i in range(1,count+1):
        # Missing required source fields are not filled with made-up coordinates.
        points.append({k:section[prefix+k+str(i)]for k in ('point','dir','speed')})
        if prefix+'delay'+str(i)in section:points[-1]['delay']=section[prefix+'delay'+str(i)]
    return {'index':index,'points':points,
            'endPosition':section.get(prefix+'endpos'),
            'endDirection':section.get(prefix+'enddir'),
            'endRadius':section.get(prefix+'endradius'),
            'canCancel':section.get(prefix+'cancancel')}

def source_clues():
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE
    from skill_attachments import decode_ftable
    from skill_icons import decode_localized_names
    source=Sources(DEFAULT_SOURCE)
    quests=decode_ftable(source.read('tables/quests.tbl'),'entry')['rows']
    quest,=[r for r in quests if r['script']=='tutorial_quest202'and r['QuestArea']=='Tutorial']
    objectives=decode_ftable(source.read('tables/quest_objective.tbl'),'id')['rows']
    logic=decode_ftable(source.read('tables/quest_objective_logic.tbl'),'id')['rows']
    zones=decode_ftable(source.read('tables/quests_zones.tbl'),'ID')['rows'];zones={r['ID']:r for r in zones}
    localized=decode_localized_names(source.read('tables/String_Quest_zh.tbl'),'SC')['values']
    route=[]
    for o in sorted((r for r in objectives if r['quest_id']==quest['entry']),key=lambda r:r['step']):
        linked=[r for r in logic if r['quest_id']==quest['entry']and r['obj_idx']==o['obj_idx']]
        for link in linked:
            zone=zones[link['zone']]
            if zone['map_id']!=5:raise ValueError('Tutorial objective no longer refers to map5')
            route.append({'step':o['step'],'objectiveIndex':o['obj_idx'],'objectiveRow':o['id'],
                          'text':localized[o['text']],'logicRow':link['id'],'zoneId':zone['ID'],
                          'mapId':zone['map_id'],'zonePosition':[zone[k]for k in ('x','y','z')],
                          'targetEntry':link['entry'],'sourceType':link['type']})
    confs={}
    for name in ('game.conf','game_a.conf','game_w.conf'):
        raw=source.read('conf/'+name);cfg=configparser.ConfigParser(strict=False);cfg.read_string(raw.decode())
        confs[name]={'tracks':{str(i):camera_track(cfg['camera'],i)for i in (6,7,8,9)},
                     'splashMapId':int(cfg['splash']['mapid']),
                     'splashCameraPosition':cfg['splash']['cameraposition'],
                     'splashCharacterPosition':cfg['splash']['characterposition']}
    names=[n for n in source.lookup if not n.endswith('/')]
    script='tutorial_quest202'
    return {'quest':{'id':quest['entry'],'title':localized[quest['Title']],'scriptReference':script,
                     'startGiverId':quest['StartGiverID'],'route':route},
            'configs':confs,'scriptBodyMatchingResourceNames':[n for n in names if script in n],
            'indexedResourcePaths':len(names),'sources':source.proofs,
            'originalFirstEntryKnown':False,'camera7IsProvedFirstEntry':False,
            'limits':['Task-zone centers are objective regions, not role spawn positions.',
                      'Cinematic index 7 is not map ID 7. Splash map7 is selection, not tutorial map5.',
                      'm_tutorial_start and m_tutorial_daemon_intro are audio labels, not recovered quest-script bodies.',
                      'No matching resource filename does not rule out every possible hidden or packed script representation.']}

def probe_runtime(runtime):
    from analyze_native_resources import NativeImage
    from native_tutorial_camera_probe import NativeTutorialCameraProbe
    cfg=json.loads((Path(runtime)/'prototype/native-physics.json').read_text())
    engine=NativeTutorialCameraProbe(NativeImage(Path(cfg['library']).read_bytes()))
    def source(name):
        row=cfg['sourceFiles'][name];raw=Path(row['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=row['sha256']:raise ValueError('Original PHY differs')
        return raw
    terrain=json.loads(Path(cfg['terrain']).read_text());profile=json.loads(Path(cfg['collision']).read_text())
    lighting=json.loads(Path(cfg['terrainLighting']).read_text())
    loaded=engine.load_world(terrain,profile,source,{tuple(t['tile']):t['runtimeFlags']for t in lighting['tiles']})
    clues=source_clues();tracks=clues['configs']['game.conf']['tracks'];seven=tracks['7'];eight=tracks['8']
    if seven['endRadius']is not None or eight['endPosition']is not None:
        raise ValueError('Observed absent camera defaults changed; retrace the source consumer')
    cases=[engine.end_position(seven['endPosition'].encode(),fraction=f)for f in (.25,.75)]
    cases.append(engine.end_position()) # Original missing endpos/radius literals: 0,0,0 and 0.
    return {'sources':clues,'loaded':loaded,'cases':cases,
            'sourceEndDirectionNumericSuffix':engine.vector(seven['endDirection'][2:].encode()),
            'gameplayChanged':False,'originalServerCommandObserved':False,
            'scope':'original vector parser/end-position acceptance/end cleanup through original Hero setter; host zero constructor fields, libc, explicit RNG and static scene; no full cinematic/first EnterMap'}

if __name__=='__main__':
    import argparse
    from tutorial_map_geometry import local_output
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=local_output(a.output)
    result=probe_runtime(a.runtime);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'output':str(out),'questSteps':len(result['sources']['quest']['route']),
                      'camera7Result':result['cases'][0]['resultPosition'],'firstEntryKnown':False}))
