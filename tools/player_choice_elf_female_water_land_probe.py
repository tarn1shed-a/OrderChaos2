"""Bounded same-actor land completion/water-state observation, no shared edits."""
import copy,hashlib,json,math,struct,sys
from pathlib import Path
from player_choice_elf_female_air_integration_worker import load
ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'analysis/raw/player-choice-elf-female-water-land-20261116'
CONFIG=ROOT/'analysis/raw/player-choice-elf-female-air-integration-20261116/candidate-v7/native-physics.world.json'
write=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')

def advance_active_rotation_phase(engine,identity,milliseconds):
    """Only the proven active-timer branch; not a substitute whole Hero tick."""
    if identity not in engine.bindings or engine.species_actors.get(identity)!='elf-female'or type(milliseconds)is not int or not 1<=milliseconds<=1000:raise ValueError('Existing own Model2 actor and actual bounded source dt required')
    at=engine.bindings[identity]['actor']['address'];before=engine.r(at+0x684,'f')[0]
    low=struct.unpack('<d',engine.image.read(0x1df7bc8,8))[0];high=struct.unpack('<d',engine.image.read(0x1df7bd0,8))[0]
    if not math.isfinite(before):raise ValueError('Original actor timer must be finite')
    if before<=0 or low<before<high:return{'active':False,'entry':'0x9ff1a0','fullZeroTimerBranchExecuted':False,'reason':'outside-bounded-active-timer-branch'}
    engine.scope(identity,lambda h:engine.call(0x9ff1a0,{'X0':at,'W1':milliseconds}))
    return{'active':True,'entry':'0x9ff1a0','dtMs':milliseconds,'before':before,'after':engine.r(at+0x684,'f')[0],
        'originalHeroV20Caller':'0x9fef78','completeHeroV20OrGlobalCallerExecuted':False,'sourceFieldsWrittenByHost':False}

def states(e,identity):
    a=e.bindings[identity]['actor']['display']['animation'];rows=[]
    for offset in(0x160,0x1c0,0x220):
        p=e.r(a+offset,'Q')[0]
        rows.append({'axis':hex(offset),'stateAddress':p,'id':e.r(p+8,'I')[0]if p else None,
            'virtualFunctions':{hex(o):hex(e.r(e.r(p,'Q')[0]+o,'Q')[0])for o in(0x18,0x28)}if p else{}})
    return rows

def run(out,*,active_rotation_step=False):
    if out.exists()or not out.resolve().is_relative_to(ROOT/'analysis/raw'):raise ValueError('Fresh ignored output required')
    out.mkdir(parents=True);e,info=load(CONFIG);events=[];frame=-1
    from unicorn import UC_HOOK_CODE
    entries=(0xa6906c,0x91b198,0xa528bc,0xa50148,0xa52ec0,0xa50098,0xa4f5ac,0x90e26c,0xa3cf28,0x9ff1a0)
    def observe(uc,pc,size,data):
        events.append({'frame':frame,'entry':hex(pc),'caller':hex(e.get('X30')-4),'x0':e.get('X0'),'x1':e.get('X1'),'w1':e.get('W1'),'w0':e.get('W0')})
    handles=[e.uc.hook_add(UC_HOOK_CODE,observe,begin=a,end=a)for a in entries+(0xa69320,0xa69504,0xa6965c)]
    pos=[-60.,-1.4500000476837158,-316.];e.fresh_actor('water-land',pos,2,{})
    actor=e.bindings['water-land']['actor']['address'];writes=[]
    e.qa_original_pose_evidence=True;native_wire=[]
    from unicorn import UC_HOOK_MEM_WRITE
    def store(uc,access,address,size,value,data):
        for off in(0xecc,0x684,0x688,0x2b0):
            if address<=actor+off<address+size:writes.append({'frame':frame,'pc':hex(e.get('PC')),'field':hex(off),'address':address,'bytes':size,'rawValue':value})
    handles.append(e.uc.hook_add(UC_HOOK_MEM_WRITE,store,begin=actor,end=actor+0x2000-1))
    rows=[]
    try:
        for frame in range(65):
            before=len(events);prior=states(e,'water-land')
            timer_prior=e.r(actor+0x684,'f')[0];timer_step=None
            if active_rotation_step and timer_prior>0:
                # A named bounded original phase, not a blanket Hero frame:
                # execute the REAL complete9ff1a0 positive-timer branch. No
                # writes of the state, angle, timer or source water fields.
                timer_step=advance_active_rotation_phase(e,'water-land',50)
            request={'identity':'water-land','position':pos,'velocity':[0,0],'milliseconds':50,'jump':frame<5,'control':{'forward':False},'eventOwner':'world','timeval':[1700000000+(frame+1)//20,((frame+1)%20)*50000]}
            result=e.tick_own(request);native_wire.append({'request':{'operation':'tick','data':request},'response':{'result':result},'namedAdditionalOriginalPhase':timer_step})
            pos=result['position'];rows.append({'frame':frame,'priorStates':prior,'states':states(e,'water-land'),'position':pos,'water':result['currentWater'],
                'actualSelectorInputs':{'ecc':e.r(actor+0xecc,'f')[0],'684':e.r(actor+0x684,'f')[0],'688':e.r(actor+0x688,'f')[0],'2b0':e.r(actor+0x2b0,'I')[0]},'namedOriginalPhase':timer_step,
                'layers':result['sourceAnimation']['layers'],'nativePostureNotifications':result['nativePostureNotifications'],'nativeFrameEvidence':result['nativeFrameEvidence'],'calls':copy.deepcopy(events[before:])})
        frame=1000;before=len(events)
        def selector(h):
            old=e.native_state;e.native_state=True
            try:e.call(0xa6906c,{'X0':0,'X1':h['actor']['display']['animation']})
            finally:e.native_state=old
            return states(e,'water-land')
        try:manual={'controlledOriginalSelectorCall':True,'states':e.scope('water-land',selector),'callerObservedInOriginalHeroFrame':False}
        except Exception as error:manual={'controlledOriginalSelectorCall':True,'error':str(error),'pc':hex(e.get('PC')),'callerObservedInOriginalHeroFrame':False}
        manual['calls']=events[before:]
    finally:
        for h in handles:e.uc.hook_del(h)
        write(out/'native-observation-v1.json',{'format':'oc2-model2-water-land-native-observation-v1','configSHA256':hashlib.sha256(CONFIG.read_bytes()).hexdigest(),'frames':rows,'controlledSelector':locals().get('manual'),'actualSelectorInputWrites':writes,'noNativeStateOrWaterGateForced':True,'noWholeHeroFrameClaimed':True})
        write(out/'native-wire-v1.json',{'format':'oc2-model2-water-land-source-phase-wire-v1','activeRotationPhaseEnabled':active_rotation_step,'rows':native_wire})
    for at in(0xa6906c,0xa52ec0,0xa50148,0x91b198,0x9fef78,0x9ff1a0,0x912e24,0xa6a80c,0xa6d50c):
        meta,asm=e.image.routine(at);(out/(hex(at)+'.asm')).write_text('\n'.join(asm)+'\n')
    return {'frames':len(rows),'autoSelectorCalls':sum(x['entry']=='0xa6906c'and x['frame']<1000 for x in events),'controlledSelector':manual,'lastStates':rows[-1]['states']}

if __name__=='__main__':
    import argparse
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--output',type=Path,default=RAW/'observation-v3');cli.add_argument('--active-rotation-step',action='store_true');args=cli.parse_args()
    print(json.dumps(run(args.output.resolve(),active_rotation_step=args.active_rotation_step)))
