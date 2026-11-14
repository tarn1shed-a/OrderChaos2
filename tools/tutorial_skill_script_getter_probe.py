"""Specific original skill_event getter and228/240 indicator-zero controls."""
import hashlib
import json
from tutorial_skill_script_probe import ROOT,RAW,SO


def run():
    from analyze_native_resources import NativeImage
    from source_physics import SourcePhysics
    from character_equipped_evidence import load_tables
    from unicorn import UC_HOOK_CODE
    image=NativeImage(SO.read_bytes());p=SourcePhysics(image);tables,_=load_tables()
    protos={x['skillId']:x for x in tables['skill_proto']['rows']}
    runes={x['id']:x for x in tables['skill_runes']['rows']};offset=0;offsets={}
    for name,kind in zip(tables['skill_runes']['columns'],tables['skill_runes']['physicalTypes']):
        offsets[name]=offset;offset+={'u':4,'i':4,'k':4,'c':1,'h':2,'f':4,'s':8}[kind]
    assert offsets['indicatorId']==0x28
    manager=p.alloc(0x300);getter=[]
    for value in(0,0x12345000,0x242ead8):
        p.w(manager+0x200,'Q',value);ret=p.call(0xc993f8,{'X0':manager},limit=8)
        assert ret==value;getter.append({'explicitPointer':hex(value),'returned':hex(ret),'pointeeDereferenced':False})
    cases=[]
    for skill in(228,240):
        for index in range(4):
            row=runes[protos[skill]['rune'+str(index)]];assert row['indicatorId']==0
            cached=p.alloc(0x80);rune=p.alloc(0x70);p.w(cached+0x30+8*index,'Q',rune)
            p.w(rune+0x28,'I',row['indicatorId'])
            seeds=[0x4444000000000000+i for i in range(4)];p.w(cached+0x58,'4Q',*seeds)
            trace=[]
            def observer(uc,at,size,data):trace.append(hex(at))
            hooks=[p.uc.hook_add(UC_HOOK_CODE,observer,begin=at,end=at)for at in(0x5b7de0,0x5b7e00,0x5b7e18)]
            try:p.call(0x5b7db4,{'X0':cached,'W1':index},limit=30)
            finally:
                for h in hooks:p.uc.hook_del(h)
            after=list(p.r(cached+0x58,'4Q'));assert after==seeds and not trace
            cases.append({'skill':skill,'rune':row['id'],'runeIndex':index,'sourceIndicatorId':row['indicatorId'],
                'nativeReader':'0x5b7db4','allocationOrTableLookupSites':trace,
                'cache58SentinelsUnchanged':True,'sourceRuneFieldPlacedExplicitly':True,
                'wholeRuneLoaderExecuted':False,'scriptLookupOrExecution':False})
    return {'format':'oc2-original-skill-event-getter-consumer-v1',
        'nativeSHA256':hashlib.sha256(SO.read_bytes()).hexdigest(),'actualGetter':'0xc993f8',
        'getterInstructions':image.routine(0xc993f8)[1],'actualDirectCall':'0x5b7e00',
        'eventRecordCacheProducer':'0x5b7db4','cacheOffset':'0x58 + runeIndex*8',
        'tableLookupKeySource':'loaded rune+0x28 indicatorId, not parentSkillId',
        'scriptStringFailureCleanup':'0x5b7e2c','getterControls':getter,'actualRuneControls':cases,
        'scriptNameExecutionFound':False,'allOtherConsumersRuledOut':False,
        'sharedOrProductionOrSaveChanged':False}


if __name__=='__main__':
    target=RAW/'getter-consumer-cpu-v1.json'
    if target.exists():raise ValueError('Preserve getter-consumer checkpoint')
    result=run();target.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'getterControls':3,'originalRuneControls':8,'scriptExecution':False}))
