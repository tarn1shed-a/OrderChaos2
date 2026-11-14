"""Human-male combat source links and original weapon/name consumers.

The bank-one graph is a bounded source-table survey, not a fabricated skill
grant or complete combo-execution CPU. Name resolution and state initialization
execute original instructions with explicit inputs and own clip metadata.
"""
import hashlib
import json
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'analysis/raw/character-human-combat-20261115'
MODEL='model/npc/character/human/male/oc2_human_m_body_01.bdae'
ANIMATION='model/npc/character/human/male/anim/animations.bdae'
BASE=ROOT/'analysis/raw/character-world-motion-20261115/male-v4-final'
FORMAT='oc2-human-male-combat-source-v1'
SPELLS={'fireball':17,'frost_blast':94,'arcane_missile':90}
STAGES={-1:'preCastState',1:'chantState',2:'releaseState',3:'channellingState',6:'backState'}


def recover(image,source):
    from map_loading_evidence import Sources
    from skill_attachments import decode_ftable
    from bdae_animation import BDAEAnimation
    from animation_blending import action_map
    from character_world_motion_probe import MODELS
    from character_human_combat_names import CombatNameProbe,routine_proofs
    sources=Sources(source);tables={}
    for name,key in [('skill_combo','id'),('skill_proto','skillId'),('skill_runes','id'),
                     ('skill_visual_state','id'),('c_animationdata','anim_id'),('cls_weapon','id')]:
        tables[name]={r[key]:r for r in decode_ftable(sources.read('tables/'+name+'.tbl'),key)['rows']}
    raw=sources.read(ANIMATION)
    if hashlib.sha256(raw).hexdigest()!=MODELS['male']['animationSHA256']:raise ValueError('Original male animation identity differs')
    with tempfile.TemporaryDirectory(prefix='oc2-human-combat-source-')as tmp:
        path=Path(tmp)/'animations.bdae';path.write_bytes(raw);ranges=BDAEAnimation(path).ranges()
    names={r['name']for r in ranges}
    ambiguous={name for name in names if sum(r['name']==name for r in ranges)>1}
    normal=[r for r in tables['skill_combo'].values()if r['isNormalAttack']==1]
    seeds={r['id']for r in normal if r['skillId']==0 and r['summonNormalSkill']!=1 and r['reqOffWeaponType']==65535 and
           any(tables['skill_proto'][r['nextSkillId']]['reqProfession']in(0,7,p)for p in range(1,7))}
    reachable={r['nextSkillId']for r in normal if r['id']in seeds}
    while True:
        expanded=reachable|{r[k]for r in normal if r['skillId']in reachable for k in('nextSkillId','timeOutSkill')if r[k]}
        if expanded==reachable:break
        reachable=expanded
    combo=[r for r in normal if r['id']in seeds or r['skillId']in reachable]
    ids={r[k]for r in combo for k in('skillId','nextSkillId','timeOutSkill')if r[k]};skills=[];wanted=set()
    for identifier in sorted(ids):
        proto=tables['skill_proto'][identifier];rune=tables['skill_runes'].get(proto['rune0']);state=tables['skill_visual_state'].get(rune['releaseState'])if rune else None
        row=tables['c_animationdata'].get(state['casterPreAnim'])if state else None;name=row['anim_name']if row else None
        skills.append({'skillId':identifier,'reqProfession':proto['reqProfession'],'runeId':proto['rune0'],'releaseState':rune['releaseState']if rune else None,
                       'animationId':row['anim_id']if row else None,'sourceName':name,'availableInOwnSource':name in names})
        if name:wanted.add(name)
    spells={}
    for alias,identifier in SPELLS.items():
        proto=tables['skill_proto'][identifier];rune=tables['skill_runes'][proto['rune0']];phases={}
        for stage,column in STAGES.items():
            state=tables['skill_visual_state'].get(rune[column]);bindings={}
            for field,tag in [('casterPreAnim','pre'),('casterLoopAnim','loop')]:
                row=tables['c_animationdata'].get(state[field])if state else None
                if row:
                    name=row['anim_name'];wanted.add(name);bindings[tag]={'animationId':row['anim_id'],'sourceName':name,'availableInOwnSource':name in names}
            phases[str(stage)]={'stateId':rune[column],'sourceRuneField':column,**bindings}
        spells[alias]={'skillId':identifier,'runeId':proto['rune0'],'phases':phases}
    mapping=action_map(image);state_names={}
    for state in(0x4000,0x84000,0x6000,0x6800,0x95,0x1000,0x81000,0x2000):
        pair=mapping[state];state_names[hex(state)]={'pair':pair,'sourceNames':[tables['c_animationdata'][i]['anim_name']if i>0 else None for i in pair]}
    vm=CombatNameProbe(image,names);selection=[]
    # Actual rows supply the category numbers. The explicit -1/-1 row tests
    # the original no-weapon branch; it is not assigned to a saved character.
    words=[{'sourceClassWeaponRow':r['id'],'low':r['second_category'],'high':r['third_category']}for r in tables['cls_weapon'].values()]
    words.append({'sourceClassWeaponRow':None,'low':0xffffffff,'high':0xffffffff,'explicitNoWeaponRecord':True})
    generic=[('combat_01',0),('combat_02',0),('combat_ready',0),('hurt_battle',1),('hurt_battle',2),('hurt_battle',3),('hurt_heavy',0),('die_ground',0),('dead_ground',0)]
    for profession in range(1,7):
        actor,controller=vm.actor(profession)
        for word in words:
            weapon=vm.weapon(actor,word['low'],word['high']);resolved=[vm.resolve(actor,controller,name,variant)for name,variant in generic]
            for r in resolved:
                if r['output']in names:wanted.add(r['output'])
            selection.append({'explicitProfession':profession,**word,'weapon':weapon,'names':resolved})
    return{'format':FORMAT,'sourceModel':MODEL,'sourceAnimation':ANIMATION,'sourceAnimationSHA256':hashlib.sha256(raw).hexdigest(),
        'ownRangeCount':len(ranges),'normalBank':1,'comboSurvey':{'rows':combo,'skills':skills,'seedRows':sorted(seeds),'weightedChoiceCPUExecuted':False},
        'spells':spells,'stateActions':state_names,'nameSelections':selection,'sourceClipNames':sorted(names),
        'demandedActions':sorted(wanted),'availableActions':sorted((wanted&names)-ambiguous),'missingActions':sorted(wanted-names),
        'ambiguousActions':sorted(wanted&ambiguous),'unselectedAmbiguousRanges':sorted(ambiguous-wanted),
        'routines':routine_proofs(image),'sourceProofs':sources.proofs,'originalNameCPUExecuted':True,
        'modelOrGPUCompletionExecuted':False,'originalServerDefaultLookOrGearKnown':False,'originalHurtVariantProducerKnown':False,
        'savesReadOrWritten':False,'productionChanged':False,
        'scope':'Own human male source clips and native name selection for explicit profession/weapon inputs. Original weighted combo/variant producer, original server skills and equipment grants not supplied.'}


if __name__=='__main__':
    from analyze_native_resources import NativeImage
    from resource_packs import DEFAULT_SOURCE
    out=RAW/'source-private.json'
    if out.exists():raise ValueError('Preserve existing source probe result')
    result=recover(NativeImage((ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so').read_bytes()),DEFAULT_SOURCE)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'bank1Rows':len(result['comboSurvey']['rows']),'skills':len(result['comboSurvey']['skills']),'nativeNameCases':sum(len(r['names'])for r in result['nameSelections']),'availableActions':len(result['availableActions']),'missingActions':result['missingActions']},ensure_ascii=False))
