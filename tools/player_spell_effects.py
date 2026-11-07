"""Resolve selected player spell FX by exact proto/rune/state/group references.

Scorcher hit group has an unavailable effect 39 in this source table. Retain
that gap explicitly; never mask its group key or substitute an unrelated FX.
"""
from pathlib import Path
from skill_attachments import decode_ftable,_scale

SELECTION={
 'playerFireCast':(17,'chantState',67,'casterRHandEff',24,['casterRHand','casterLHand']),
 'playerFireMissile':(17,'releaseState',32,'casterRHandEff',23,['casterRHand']),
 'playerFireHit':(17,'hitState',35,'targetGroundEff',27,['targetGround']),
 'arcaneCast':(90,'channellingState',130,'casterRHandEff',110,['casterRHand']),
 'arcaneMissile':(90,'releaseState',128,'casterRHandEff',59,['casterRHand']),
 'arcaneHit':(90,'hitState',131,'targetChestEff',60,['targetChest']),
}
BINDINGS={'fireball':{'cast':'playerFireCast','missile':'playerFireMissile','hit':'playerFireHit'},
 'arcane_missile':{'cast':'arcaneCast','missile':'arcaneMissile','hit':'arcaneHit'},
 'frost_blast':{'hit':'frostHit'}}

def recover_player_effects(extract):
 tables={};proofs={}
 for name,key in [('skill_proto','skillId'),('skill_runes','id'),('skill_visual_state','id'),('skill_visual_effect','id'),('skill_visual_effect_group','id')]:
  value=extract('tables/'+name+'.tbl');d=decode_ftable(bytes(value) if isinstance(value,(bytes,bytearray)) else Path(value).read_bytes(),key)
  tables[name]={r[key]:r for r in d['rows']};proofs[name]=d['verification']
 result={};gaps=[]
 for alias,(pid,field,sid,slot,eid,slots) in SELECTION.items():
  p=tables['skill_proto'][pid];r=tables['skill_runes'][p['rune0']];s=tables['skill_visual_state'][sid];f=tables['skill_visual_effect'][eid]
  if r[field]!=sid:raise ValueError('Player rune/state mismatch')
  reference=s[slot];group=[v for v in tables['skill_visual_effect_group'].values() if v['groupId']==reference]
  if reference!=eid and eid not in [v['effectId'] for v in group]:raise ValueError('Player state/group/effect mismatch')
  if alias=='playerFireCast' and s['casterLHandEff']!=eid:raise ValueError('Player fire hand mismatch')
  for entry in group:
   if entry['effectId'] not in tables['skill_visual_effect']:gaps.append({'stateId':sid,'slot':slot,'groupId':reference,**entry})
  scale,raw=_scale(f)
  result[alias]={'effectId':eid,'sourceSkillId':pid,'runeId':r['id'],'sourceStateIds':[sid],
   'sourceRuneField':field,'sourceSlotField':slot,'sourceReference':reference,'groupRows':group,
   'path':f['pathName'],'slots':slots,'slot':slots[0] if len(slots)==1 else None,
   'scale':scale,'particleScale':sum(scale)/3,'decodedScalePercent':raw,
   'missileType':f['missileType'],'missileCount':f['missileNum'],'missileSpeed':f['missileSpeed']}
 return {'effects':result,'bindings':BINDINGS,'unresolvedReferences':gaps,'tables':proofs,
  'limitations':['Scorcher hit group 0x90000023 resolves effect27 and unavailable effect39; the unavailable layer is not fabricated.',
   'Source release/hand/chest/ground and BEFF parameters are recovered. Missile trajectories, server acknowledgements and damage remain local policies.']}
