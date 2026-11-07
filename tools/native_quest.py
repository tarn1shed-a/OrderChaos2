"""Bounded quest/client-state evidence. No original server scripts execute."""
import hashlib
from pathlib import Path
from native_combat import descriptor_fields
from native_interaction import recover_interactions
from skill_icons import decode_localized_names

PROTOCOL={
 'GS2C_ObjectStaticObj':(0x2029120,558,'0879594cceac9c52685f4c636c1a9a87c3dec8dd19885a5a630e3bb4dddccf77'),
 'GS2C_QuestBrief':(0x203f521,78,'d61a7e4a83114014067abe408f084e862810d952b2793350c30bd2fd26c66d0b'),
 'GS2C_QuestDetail':(0x203f572,192,'e8906381b4642447c82eb0d5e1b512b26cc13719dbb0dcd7c34da3d8e2f314ca'),
 'GS2C_QuestStep':(0x203f7b5,74,'3fbe503bbc7fa9b4b2c2faf0d4ef1e18886816be81e6e1046dece0183119628c'),
 'GS2C_QuestInfo':(0x203f978,585,'b74b190c9110fa5bdf23630db6c6670d73566222cffb7aa517a0cd1c6444067f'),
}
def verify_quest_native(image):
 result={}
 for name,(address,size,digest) in PROTOCOL.items():
  raw=image.read(address,size)
  if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('Quest descriptor changed; retrace required')
  parsed=descriptor_fields(raw)
  if parsed['name']!=name:raise ValueError('Quest descriptor name mismatch')
  result[name]={**parsed,'address':hex(address),'bytes':size,'sha256':digest}
 return result

def recover_quest_data(extract):
 def raw(path):
  value=extract(path);return bytes(value) if isinstance(value,(bytes,bytearray)) else Path(value).read_bytes()
 interaction=recover_interactions(extract);localized=decode_localized_names(raw('tables/String_Quest_zh.tbl'),'SC')
 names=localized['values'];catalog=[]
 for row in interaction['questReferences']['quests']:
  texts={key:names[row[key]] for key in ('Title','Details','Objectives','CompletionText','IncompleteText')}
  catalog.append({'id':row['entry'],'title':texts['Title'],'description':texts['Details'],'objective':texts['Objectives'],
   'minLevel':row['MinLevel'],'sourceType':row['Type'],'sourcePrerequisite':row['RequiredQuest'],
   'sourceScript':row['script'],'sourceReward':{'money':row['RewMoney'],'xp':row['RewXP']},
   'textIds':{k:row[k] for k in texts},'sourceObjects':[r['entry'] for r in interaction['previewObjectProtos'] if f'quest{row["entry"]}_' in r['script']]})
 objects=[]
 for spawn in interaction['previewObjectSpawns']:
  proto=next(r for r in interaction['previewObjectProtos'] if r['entry']==spawn['Entry'])
  objects.append({'id':'source-static-'+str(spawn['id']),'spawnId':spawn['id'],'entry':proto['entry'],
   'sourceType':proto['Type'],'sourceState':spawn['State'],'sourcePosition':[spawn['position_x'],spawn['position_y'],spawn['position_z']],
   'sourceScript':proto['script'],'sourceSpell':proto['spellid'],'sourceRange':proto['interactiveRange'],
   'sourceRefresh':proto['refreshTime'],'sourceDisplayId':proto['DisplayID']})
 return {'format':'oc2-source-quests-v1','catalog':catalog,'objects':objects,'tableProofs':interaction['tableProofs'],
  'localizedProof':localized['verification'],'serverScriptsRecovered':False,
  'limits':['Original task data is reference material, not an accepted quest or a reward entitlement.',
   'Source spawn State is not the runtime quest_status/can_loot/interactives supplied by the server. Missing fields stay unknown.',
   'Original quest accept/abandon/completion/collection and static-object visibility scripts are not implemented. Objects are inspected in the journal, not spawned into the live world.']}
