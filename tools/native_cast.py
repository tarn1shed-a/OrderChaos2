"""Recover the verified client's execution stages and selected source spell data.

Original server decisions are not in the APK. Timed server acknowledgements,
damage, projectile travel and the collision lab's placement remain web policies.
"""
from pathlib import Path
from skill_attachments import decode_ftable
from bdae_animation import BDAEAnimation
from bdae_character import ACTION_SOURCES

STAGES = {-1:'preCastState',1:'chantState',2:'releaseState',3:'channellingState',6:'backState'}
# 5d1454/5d15a8 jump tables index (-1 or stage)+1, rune.moveinterrupt at +0x48.
MOVEMENT_BITS = {-1:(15,17),1:(18,20),2:(21,23),3:(24,26),6:(27,29)}
BINDINGS = {'fireball':17,'frost_blast':94,'arcane_missile':90}

def movement_policy(word, stage, attributes=0):
    stop,interrupt=MOVEMENT_BITS[stage]
    return {'stopOnEnter':bool(word&(1<<stop) or attributes&0x40),
            'interruptOnMove':bool(word&(1<<interrupt))}

def recover_cast(extract, animation):
    tables={}
    for name,key in [('skill_proto','skillId'),('skill_runes','id'),('skill_visual_state','id'),('c_animationdata','anim_id')]:
        value=extract('tables/'+name+'.tbl');raw=bytes(value) if isinstance(value,(bytes,bytearray)) else Path(value).read_bytes()
        decoded=decode_ftable(raw,key);tables[name]={r[key]:r for r in decoded['rows']}
    from skill_icons import decode_localized_names
    value=extract('tables/String_Skill_zh.tbl');names=decode_localized_names(bytes(value) if isinstance(value,(bytes,bytearray)) else Path(value).read_bytes(),'SC')['values']
    ranges={r['name']:r for r in animation.ranges()};actions={};spells={}
    range_aliases={v:k for k,v in ACTION_SOURCES['player'].items() if k.startswith('skill_')}
    for alias,identifier in BINDINGS.items():
        proto=tables['skill_proto'][identifier];rune=tables['skill_runes'][proto['rune0']];visuals={}
        for stage,column in STAGES.items():
            identifier_state=rune[column];row=tables['skill_visual_state'].get(identifier_state)
            record={'id':identifier_state,'movement':movement_policy(rune['moveinterrupt'],stage,proto['attributes'])}
            for field,tag in [('casterPreAnim','pre'),('casterLoopAnim','loop')]:
                anim=tables['c_animationdata'].get(row[field]) if row else None
                name=anim['anim_name'] if anim else None
                if not name:continue
                if name not in ranges:raise ValueError('Selected cast animation missing: '+name)
                # Reuse an existing spell alias when it names the SAME source
                # range. The character converter binds one alias per range.
                key=range_aliases.setdefault(name,f'skill_native_{alias}_{stage}_{tag}'.replace('-1','pre'))
                actions[key]=name;interval=ranges[name]
                record[tag]={'clip':key,'animationId':anim['anim_id'],'sourceName':name,'sourceRange':interval['sourceName'],
                    'durationMs':(round(interval['endMs']*.03)-round(interval['startMs']*.03))/.03}
            visuals[str(stage)]=record
        spells[alias]={'sourceSkillId':identifier,'displayName':names[rune['nameStrId']],'runeId':rune['id'],'editName':proto['editName'],
            'chantMs':rune['chantTime'],'channelMs':rune['channelTime'],'channelIntervalMs':rune['channelIntervalTime'],
            'cooldownMs':rune['coolDownTime'],'commonCD':proto['commonCD'],'postRockTime':proto['postRockTime'],
            'moveinterrupt':rune['moveinterrupt'],'attributes':proto['attributes'],'visuals':visuals,
            'scope':'Selected original player proto/rune/visual chain; local combat policy',
            'maxCastRange':rune['maxCastRange'],'powerCost':rune['powerCost'],'hitState':rune['hitState']}
    return {'format':'oc2-native-cast-v2','stages':{'prepare':0,'chant':1,'release':2,'channel':3,'end':6},
        'actionStates':{'stand':0x800,'chant':0x3000,'release':0x3800,'channel':0x4000},
        'serverWaitExtraMs':5000,'spells':spells,
        'limitations':['Client execution stages and movement flag bits are recovered; original server transitions, combat outcomes and protocol transport are not reproduced.',
            'The local server acknowledges chant/channel completion on a source-data schedule. The recovered +5000 ms value is a client watchdog, not added chant time.',
            'Damage, projectile travel and local item/character rules remain web policies. postRockTime is preserved as evidence, not used as an invented client-stage timer.',
            'Scorcher17 and ArcaneMissile90 use their own source actions/effects. Power/resource rules and original server hit decisions are not restored.']},actions
