"""Source interaction handoff and loot-message evidence; no server scripts.

The first playable branch uses the original contextual button and loot icon.
Camp wolf ownership/quantity/expiry/range stay explicitly local encounter rules.
"""
import hashlib
from pathlib import Path
from native_combat import descriptor_fields
from skill_attachments import decode_ftable

NATIVE_ROUTINES={
    0x9f11bc:(4016,'57f7c3c4fc2fb6fc5101b4806a1cfcf74d9b9dd2674717ef54f55c3dba3e4f1a'),
    0x65a42c:(212,'37220b3483777ed1964c9866d3485b9d42e9dd3a380d41111a06832697576fef'),
    0x5a0f10:(348,'6ea9e000b29cf2cb07a89c666626ebc809127103b4ccb904a0b10937f1e360ca'),
}
PROTOCOL={
    'C2GS_Loot':(0x2029f51,39,'8cb376e81f9477bd02d19c509447f9fc3a0648bfbb9f470c63daeeeb4fcd9464'),
    'C2GS_PickLootItem':(0x202a57d,50,'5aa966645e3e7194132fb5707f496f2cd8ca3dc42a0c1a233dcbfb14df3661e2'),
    'GS2C_LootList':(0x2029f7a,110,'f370202b17c7466b33316aff5a03b393e18888676ef3f722fabf163a28672466'),
    'QuestInteractiveInfo':(0x202aae6,139,'dfe133a7e6aa5746f8604eb7fde9a1b3399ca147098f11055587449ba2cca17d'),
    'C2GS_Interactive':(0x202ab73,74,'484f98c15c339f312ca1b69087fe2ce17edde60e0954a26cc01ec95920ec28f6'),
}
def verify_interaction_native(image):
    result={}
    for name,(address,size,digest) in PROTOCOL.items():
        raw=image.read(address,size)
        if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('Interaction descriptor changed; retrace required')
        parsed=descriptor_fields(raw)
        if parsed['name']!=name:raise ValueError('Interaction descriptor name mismatch')
        result[name]={**parsed,'address':hex(address),'bytes':size,'sha256':digest}
    return result

def recover_interactions(extract):
    tables={};proofs={}
    for name,key in [('npc_interactive','id'),('staticobject_proto','entry'),('staticobject_displayinfo','entry'),
                     ('staticobject_spawns','id'),('quests','entry'),('quest_objective','id'),
                     ('quest_objective_logic','id'),('quest_reward_item','id'),('quest_logic_item','id'),('loot','id')]:
        value=extract('tables/'+name+'.tbl');raw=bytes(value) if isinstance(value,(bytes,bytearray)) else Path(value).read_bytes()
        d=decode_ftable(raw,key);tables[name]=d['rows'];proofs[name]=d['verification']
    spawns=[r for r in tables['staticobject_spawns'] if r['map']==4 and -2752<=r['position_x']<=-2560 and 128<=r['position_z']<=320]
    ids={r['Entry'] for r in spawns};protos=[r for r in tables['staticobject_proto'] if r['entry'] in ids]
    display_ids={r['DisplayID'] for r in protos};quests={572,632}
    return {'format':'oc2-source-interaction-v1','tableProofs':proofs,'previewObjectSpawns':spawns,
        'previewObjectProtos':protos,'previewDisplays':[r for r in tables['staticobject_displayinfo'] if r['entry'] in display_ids],
        'questReferences':{name:[r for r in tables[name] if r['entry' if name=='quests' else 'quest_id'] in quests]
            for name in ['quests','quest_objective','quest_objective_logic','quest_reward_item','quest_logic_item']},
        'npcInteractionCount':len(tables['npc_interactive']),'lootRecordCount':len(tables['loot']),
        'button':{'eventFields':['Icon','Function','showFlag'],'tapCallback':'onInteractionClick',
            'nativeCallback':'Hero_SendInteraction','defaultPress':'Hero_SetJumpState','nonemptyFunctionReplacesJump':True},
        'limitations':['Source OperationPanel2 replaces jump press/release with a contextual tap when Function is nonempty, releasing an already-held jump first. Original script callback strings are never evaluated by the web runtime.',
            'Native 9f11bc selects interaction art; its loot branch uses ui/icons/interactive/loot.png. Full target ordering and source range initialization are not restored.',
            'Loot/open-list/pick-item and quest-interaction descriptors prove separate server-controlled data and requests, not an implemented original transport or reward algorithm.',
            'The playable branch collects the local camp reward from a corpse with one server-owned claim per eligible character. Quantity, personal ownership, radius, line-of-sight and lifetime are local rules; this is a one-item shortcut, not the original loot-list UI.',
            'Unclaimed drops are transient room state and vanish at corpse respawn or process restart. Claimed inventory uses the existing private character save; no save schema migration.',
            'Source preview objects610/621 reference quests572/632 and scripts. They are evidence, not activated without original phase/quest/server script rules.']}
