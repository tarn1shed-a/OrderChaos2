"""Original UI constants and list appearance, not quest-unlock server rules."""
import hashlib
from optimized_abc import extract_named_abc,parse_abc,disassemble

BLOCK_SHA256='e52412f677339cb3abb773e85a7eb0f6dae60af95ba93ff480dd1b2e94745889'
CINIT_SHA256='774f8f06d2fab69a1a1ddab099d7f4b514628e165e16203379dd9cd4443cee6c'
EXPECTED_STATUS={
 'QMGR_QUEST_NOT_AVAILABLE':0,'QMGR_QUEST_AVAILABLELOW_LEVEL':1,'QMGR_QUEST_AVAILABLE_PERIOD_MISMATCH':2,
 'QMGR_QUEST_VAILABLE_BEGIN':3,'QMGR_QUEST_NOT_FINISHED':4,'QMGR_QUEST_DAILY_AVAILABLE':5,
 'QMGR_QUEST_AVAILABLE':6,'QMGR_QUEST_AVAILABLE_ENDLESS':7,'QMGR_QUEST_DAILY_FINISHED':8,'QMGR_QUEST_FINISHED':9}
EXPECTED_TYPES={'INVALID_QUEST':0,'QUEST_NORMAL':1,'QUEST_SUB_QUEST':2,'QUEST_INSTANT':3,'QUEST_LOCAL_EVENT':4,
 'QUEST_WORLD_EVENT':5,'SOLO_DUNGEON_QUEST':6,'DUNGEON_QUEST':7,'LEGEND_DUNGEON_QUEST':8,'DAILY_QUEST':9,'ENDLESS_QUEST':10}
NATIVE_ROUTINES={0x65e6b8:(4660,'337a700cc4b6fd255f349546dca2c0125ab1ded09dfe03b26a9fe37b1530599d')}

def constant_values(abc,cls,expected):
    """Require both integer Const traits and matching literal cinit assignments."""
    traits={t['name']:t for t in cls['staticTraits']};ins=disassemble(abc['bodies'][cls['cinit']]['code'],abc);values={}
    for name,wanted in expected.items():
        t=traits.get(name)
        if not t or t['kind']!=6 or t.get('valueKind')!=3 or not 0<t['value']<len(abc['ints']):raise ValueError('Unsupported quest constant trait')
        value=abc['ints'][t['value']];writes=[i for i,r in enumerate(ins) if r['op'] in ('initproperty','setproperty') and r['args'][0]==name]
        if len(writes)!=1:raise ValueError('Quest constant initializer missing or ambiguous')
        i=writes[0]
        if i<2 or ins[i-2]['op']!='findproperty' or ins[i-2]['args']!=[name] or ins[i-1]['op'] not in ('pushbyte','pushshort','pushint') or ins[i-1]['args']!=[value] or value!=wanted:raise ValueError('Quest constant initializer mismatch')
        values[name]=value
    return values

def recover_client_quest_states(raw):
    data=extract_named_abc(raw,'Common/ASDefines')
    if hashlib.sha256(data).hexdigest()!=BLOCK_SHA256:raise ValueError('Quest constants block changed; retrace required')
    abc=parse_abc(data);cls=next(c for c in abc['classes'] if c['name']=='Common::ASDefines');body=abc['bodies'][cls['cinit']]
    if hashlib.sha256(body['code']).hexdigest()!=CINIT_SHA256:raise ValueError('Quest constants initializer changed')
    status=constant_values(abc,cls,EXPECTED_STATUS);types=constant_values(abc,cls,EXPECTED_TYPES)
    return {'format':'oc2-client-quest-states-v1','status':status,'types':types,
        'statusIcons':{str(status['QMGR_QUEST_NOT_FINISHED']):'unfinished',str(status['QMGR_QUEST_FINISHED']):'complete',str(status['QMGR_QUEST_DAILY_FINISHED']):'dailyComplete'},
        'failedIcon':'failed','failureOverridesStatus':True,'bookGroups':{'normal':[types['QUEST_NORMAL'],types['QUEST_SUB_QUEST']],'daily':[types['DAILY_QUEST']]},
        'sourceUIListCountLabel':12,'proof':{'source':'ui/Flash/mainUI.swf','block':'Common/ASDefines','blockBytes':len(data),'blockSHA256':BLOCK_SHA256,'cinitBytes':len(body['code']),'cinitSHA256':CINIT_SHA256},
        'limits':['These are UI constants and branches. They do not establish original quest unlock, acceptance, completion reward or server script rules.',
            'Static-object quest_status and the server-wire QuestInfo.status have not been proven to share all UI semantics; do not relabel them using these enums.',
            'The /12 label is original interface text, not a recovered server capacity check.']}
