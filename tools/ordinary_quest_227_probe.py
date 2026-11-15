"""Original quest227 source/asset inventory; never an activity or executor.

Full source rows/resources stay ignored. No actor spawn, drop roll, task state,
script interpretation, save, browser or service is created by this tool.
"""
import hashlib
import json
import math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
AREA=ROOT/'analysis/raw/ordinary-quest-neighbors-20261116'
SO=ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'
SHA=lambda raw:hashlib.sha256(raw).hexdigest()
TABLES={'quests':'entry','quest_objective':'id','quest_objective_logic':'id','quest_logic_item':'id','quest_reward_item':'id',
 'creature_proto':'entry','creature_spawns':'id','creature_appearance':'entry','creaturedisplayinfo':'ID','creaturedisplayinfoextra':'ID','creaturemodeldata':'ID',
 'staticobject_proto':'entry','staticobject_spawns':'id','staticobject_displayinfo':'entry','quests_zones':'ID',
 'items':'entry','itemdisplayinfo':'ID','itemmodeldata':'ID','loot':'id','loot_display_filter':'ID','loot_feature':'FeatureID','loot_feature_items':'id',
 'creature_display_filter':'ID','staticobject_display_filter':'id','quest_visible_control':'id'}


def only(rows,key,value):
    found=[r for r in rows if r[key]==value]
    if len(found)!=1:raise ValueError('Original key not unique '+str((key,value)))
    return found[0]


def original_requests(image,sources,model_path):
    from tutorial_npc_robe_probe import RobeProbe
    from tutorial_npc_catalog_ut_probe import OverrideProbe
    from bdae_convert import BDAE
    import tempfile
    class FemaleRequestProbe(RobeProbe):
        def part_for_source_model(self,slot,value,face):
            # Reuse the original consumer with its actual Model32 filename.
            # Do not invoke the older Catalog wrapper's male BASE constant.
            owner,holder,model,vt=self.alloc(256),self.alloc(8),self.alloc(256),self.alloc(64)
            self.w(owner+0x40,'Q',holder);self.w(holder,'Q',model);self.w(model,'Q',vt);self.w(vt+0x10,'Q',self.MODEL_KIND)
            self.w(model+0x90,'Q',self.cpp_string(model_path.encode()));self.w(owner+0x4c,'I',face)
            self.weapon_mode='resource';self.resource_request=None;self.lookup_calls=[];self.exists_queries=[]
            try:self.call(0x9d64e8,{'X0':owner,'W1':slot,'W2':value,'W3':1})
            finally:self.weapon_mode=None
            if self.resource_request is None:raise ValueError('Source resource request boundary not reached')
            return{**self.resource_request,'inputValue':value,'sourceModelPathFixture':model_path,'explicitCurrentFace':face,
              'explicitLoadedModelKind':3,'noActorOwner':True,'tableLookups':self.lookup_calls,'existsQueries':self.exists_queries}
    p=FemaleRequestProbe(image,sources);selection=p.entry_selection(872);parts=p.parts(852)
    if selection['result']['selectedDisplayAtD60']!=852 or parts['modelId']!=32:raise ValueError('Original NPC872 default differs')
    requests=[]
    for slot in [*range(7),11,14]:
        try:requests.append(p.part_for_source_model(slot,parts['slots'][slot],parts['slots'][0]))
        except ValueError as error:requests.append({'slot':slot,'inputValue':parts['slots'][slot],'boundary':str(error),'resourceLoaderExecuted':False})
    override=OverrideProbe(image)
    for request in requests:
        request['overrideResources']=[]
        for channel,stem in enumerate(request.get('textureOverrides',[])):
            if not stem:continue
            # Descriptor strings are stems, not archive names. Execute the
            # original formatter with explicit source sampler-name inputs.
            with tempfile.TemporaryDirectory(prefix='oc2-q227-override-')as tmp:
                path=Path(tmp)/'part.bdae';path.write_bytes(sources.read(request['path']))
                for material in BDAE(path).parse()['materials']:
                    proof=override.request(list(material['samplers']),channel,stem)
                    boundary=proof['reachedBoundary']
                    request['overrideResources'].append({'channel':channel,'stem':stem,'material':material['name'],
                      'path':boundary['path']if boundary else None,'originalRequest':proof,
                      'compiledReflectionObserved':False,'sourceSamplerNamesAreExplicitInputs':True})
    return{'npc872':{'selection':selection,'parts':parts,'requests':requests,'idle':p.idle(872,852)},
      'crocodile638Idle':p.idle(638,630),'nativeSHA256':SHA(image.data),'actorOrModelCompleted':False,'tableAndStringPortsExplicit':True}


def recover(output,*,include_native=True):
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE,read_entry
    from skill_attachments import decode_ftable
    from skill_icons import decode_localized_names
    from tutorial_npc_inventory import selected_names
    from ordinary_mainline_evidence import references,id_list
    out=Path(output)
    if out.exists():raise ValueError('Preserve original quest227 inventory')
    if not out.resolve().is_relative_to(AREA.resolve()):raise ValueError('Original data only in owned ignored area')
    out.mkdir(parents=True);s=Sources(DEFAULT_SOURCE)
    tables={n:decode_ftable(s.read('tables/'+n+'.tbl'),k)for n,k in TABLES.items()}
    t={n:v['rows']for n,v in tables.items()};quest=only(t['quests'],'entry',227);names=decode_localized_names(s.read('tables/String_Quest_zh.tbl'),'SC')['values']
    npc_entries=[872,638];apps={entry:only(t['creature_appearance'],'entry',entry)for entry in npc_entries}
    creature_names,name_proof=selected_names(s.read('tables/String_Creature_zh.tbl'),{apps[e]['name']for e in npc_entries})
    item=only(t['items'],'entry',50051);item_strings=[p for p in s.lookup if p.startswith('tables/string_item')and p.endswith('_zh.tbl')]
    item_name=None;item_name_boundary=None
    if len(item_strings)==1:
        try:item_name=selected_names(s.read(item_strings[0]),{item['name1']})[0][item['name1']]
        except ValueError as e:item_name_boundary=str(e)
    else:item_name_boundary='String item table name not unique: '+repr(item_strings)
    grave_proto=only(t['staticobject_proto'],'entry',218);grave_display=only(t['staticobject_displayinfo'],'entry',grave_proto['DisplayID'])
    static_names,static_name_proof=selected_names(s.read('tables/String_Staticobject_zh.tbl'),{grave_proto['NameID']})
    actors={}
    for entry in npc_entries:
        appearance=apps[entry];display=only(t['creaturedisplayinfo'],'ID',appearance['creaturedisplayinfo_id']);model=only(t['creaturemodeldata'],'ID',display['Model'])
        actors[str(entry)]={'appearance':appearance,'display':display,'model':model,'proto':only(t['creature_proto'],'entry',entry),
          'extra':only(t['creaturedisplayinfoextra'],'ID',display['ExtraDisplayInformation'])if display['ExtraDisplayInformation']else None,
          'spawns':[r for r in t['creature_spawns']if r['entry']==entry and r['map']==1],
          'name':creature_names[appearance['name']],'displayFilter':only(t['creature_display_filter'],'ID',appearance['creature_display_filter_id'])}
    grave={'proto':grave_proto,'display':grave_display,'name':static_names[grave_proto['NameID']],
      'spawns':[r for r in t['staticobject_spawns']if r['Entry']==218 and r['map']==1],
      'displayFilter':only(t['staticobject_display_filter'],'id',grave_proto['display_filter'])}
    source_edges=references(t['quests']);ordinary_map1=[q for q in t['quests']if q['ZoneId']==1 and q['Type']==2]
    objectives=sorted([r for r in t['quest_objective']if r['quest_id']==227],key=lambda r:(r['step'],r['obj_idx']))
    logic=[r for r in t['quest_objective_logic']if r['quest_id']==227]
    victim_loot=[r for r in t['loot']if r['VictimID']==638 and r['VictimType']==1]
    filters=[];seen=set();pending=[r['LootFilterID']for r in victim_loot]
    while pending:
        key=pending.pop(0)
        if not key or key in seen:continue
        seen.add(key);row=only(t['loot_display_filter'],'ID',key);filters.append(row);pending.append(row['filterParent'])
    features=[r for r in t['loot_feature']if r['DisplayFilter']in seen]
    feature_items=[r for r in t['loot_feature_items']if r['FeatureID']in{f['FeatureID']for f in features}]
    relevant=[r for r in feature_items if r['LootItemID']==50051]
    routes=[]
    for row in relevant:
        feature=only(features,'FeatureID',row['FeatureID']);direct=[r for r in victim_loot if r['LootFilterID']==feature['DisplayFilter']]
        routes.append({'victimRows':direct,'displayFilter':only(filters,'ID',feature['DisplayFilter']),'feature':feature,'item':row})
    native=None
    if include_native:
        from analyze_native_resources import NativeImage
        native=original_requests(NativeImage(SO.read_bytes()),s,actors['872']['model']['ModelPath'])
    resources={};material_records={};animation_records={};gaps=[]
    def asset(name,purpose):
        if name in resources:return resources[name]
        candidates=s.candidates(name);records=[]
        for e in candidates:
            raw=read_entry(e,s.root);records.append({'pack':e['pack'],'bytes':len(raw),'crc32':f"{e['crc']:08x}",'sha256':SHA(raw)})
        value={'purpose':purpose,'candidates':records,'candidateCount':len(records),'selected':None}
        resources[name]=value
        if len(candidates)!=1:
            gaps.append({'resource':name,'reason':'missing'if not candidates else'different archive candidates require original selection','purpose':purpose});return value
        raw=s.read(name);target=out/'original-resources'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        value.update(selected=records[0],copiedTo=str(target.relative_to(out)))
        return value
    models={actors[e]['model']['ModelPath']for e in ['872','638']}|{grave_display['strPath']}
    if native:
        for r in native['npc872']['requests']:
            if r.get('path'):models.add(r['path'])
            for override in r.get('overrideResources',[]):
                if override['path']:asset(override['path'],'original NPC872 texture request with explicit source sampler-name inputs')
                else:gaps.append({'slot':r['slot'],'reason':'original texture request boundary not reached','override':override})
            if r.get('boundary'):gaps.append({'slot':r['slot'],'reason':r['boundary']})
    from bdae_convert import BDAE
    from scene_sampling import material_samplers
    from bdae_animation import BDAEAnimation
    for model in sorted(models):
        a=asset(model,'original selected model/part')
        if not a['selected']:continue
        try:
            reader=BDAE(out/a['copiedTo']);records=material_samplers(reader);material_records[model]=records
            for record in records:
                asset(record['effectPath'],'source material effect')
                for sampler in record['samplers'].values():
                    if sampler['texture']:asset(sampler['texture'],'source material texture')
        except ValueError as e:gaps.append({'resource':model,'reason':'material reader boundary: '+str(e)})
    for entry in ['872','638']:
        model=actors[entry]['model']['ModelPath'];companion=model.rsplit('/',1)[0]+'/anim/animations.bdae'
        a=asset(companion,'same-family original animation companion; native idle request is independent evidence')
        if not a['selected']:continue
        try:
            clip=BDAEAnimation(out/a['copiedTo']).parse(['idle'])['clips'][0]
            animation_records[entry]={'path':companion,'name':clip['name'],'duration':clip['duration'],'tracks':len(clip['tracks']),
              'sourceRange':{k:v for k,v in clip.items()if k in ['startMs','endMs','duration']},'actualLoaderResolvedThisPath':False,
              'sourceClipDecodedNotBoundOrRendered':True}
        except ValueError as e:gaps.append({'resource':companion,'reason':'idle decode boundary: '+str(e)})
    world=ROOT/'analysis/raw/plain-quest-map1-20261115/candidate-v3/assets/source-ordinary-quest-map1/manifest.json'
    world_data=json.loads(world.read_text())if world.exists()else None
    result={'format':'oc2-original-quest227-inventory-v2','quest':quest,'localized':{k:names[quest[k]]for k in ['Title','Details','Objectives','CompletionText','IncompleteText','EndText']},
      'objectives':[{**r,'localized':names[r['text']]}for r in objectives],'logic':logic,'takeback':[r for r in t['quest_logic_item']if r['quest_id']==227],
      'itemRewards':[r for r in t['quest_reward_item']if r['quest_id']==227],'item50051':{'row':item,'name':item_name,'nameBoundary':item_name_boundary},
      'npcAndMonster':actors,'finishObject':grave,'zones':[r for r in t['quests_zones']if r['ID']in{quest['start_zone'],quest['finish_zone'],*[r['zone']for r in logic if r['zone']]}],
      'loot':{'victimRows':victim_loot,'filterParentClosure':filters,'features':features,'sourceItemPaths':routes,'otherItemRowCount':len(feature_items)-len(relevant),
        'ChanceIsRawFieldNotProvenProbability':True,'originalDropRollOrKillApprovalRecovered':False},
      'nativeDefaultRequests':native,'resources':resources,'materialRecords':material_records,'idleDefinitions':animation_records,
      'sourceGapOrAmbiguity':gaps,'siblingContext':{'map1TotalQuests':sum(q['ZoneId']==1 for q in t['quests']),
        'ordinaryType2Rows':[{k:q[k]for k in ['entry','RequiredQuest','RequiredOneOfQuest','QuestLinkID','StartGiverType','StartGiverID','FinishGiverType','FinishGiverID','script','NotOnMap']}for q in ordinary_map1],
        'edgesTouchingOrdinary':[r for r in source_edges if r['from']in{q['entry']for q in ordinary_map1}or r['to']in{q['entry']for q in ordinary_map1}],
        'questTableHasNextQuestColumn':any('nextquest'in c.lower()for c in tables['quests']['columns']),
        'quest227Prerequisites':id_list(quest['RequiredQuest']),'notSuccessorOf461':True},
      'existingMapModelReuse':{'manifest':str(world.relative_to(ROOT)),'sha256':SHA(world.read_bytes())if world_data else None,
        'matchingCrocOrGraveScenery':[r for r in world_data['scenery']if r['model']in models]if world_data else[]},
      'admissionUnknowns':['Original activity GUID/location/attrs, phase/filter evaluation and actual actor construction not supplied','Kill/loot approval, Chance/BoxValue/RNG semantics and item grant not inferred from strings','Static grave Display.scale0 is preserved separately from spawn.scale1.40258 and unknown runtime properties','Native model/resource completion, strict composed skin/mesh visibility/idle binding and GPU still unverified'],
      'v1Correction':'candidate-v1 incorrectly queried a descriptor texture stem as an archive path. It remains preserved as an intermediate receipt. v2 executes original325ce0/325e5c formatter with explicit source sampler-name inputs; this is not compiled reflection or texture success.',
      'sourceProofs':s.proofs,'localizedSelectedRows':{'creature':name_proof,'static':static_name_proof},'resourceReaderDependencies':{p:SHA((ROOT/p).read_bytes())for p in ['tools/bdae_convert.py','tools/scene_sampling.py','tools/bdae_animation.py']},
      'originalActorOrTaskCreated':False,'runtimeEnabled':False,'savesServicesOrDeploymentTouched':False}
    target=out/'source-v1.json';target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return{'file':str(target),'sha256':SHA(target.read_bytes()),'resourceCount':len(resources),'gaps':gaps,'lootItemPaths':len(routes),'runtimeEnabled':False}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=AREA/'candidate-v1');p.add_argument('--without-native',action='store_true');a=p.parse_args()
    print(json.dumps(recover(a.output,include_native=not a.without_native),ensure_ascii=False,indent=2))
