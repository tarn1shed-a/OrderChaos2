"""Original relocation-prefix and existing private worker reset comparison.

The courtyard is an authorized WEB trial target, not an original server escape
destination. All actors are isolated CPU/stdio fixtures. No save or running
service is opened, and the shared worker is executed without modifications.
"""
import argparse
import hashlib
import json
import selectors
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_CONFIG=ROOT/'analysis/raw/tutorial-elevator-20261114/four-inside-candidate/native-physics.json'
COURTYARD=[-2594,135.72999572753906,-64]
ROOF=[-2611.41015625,172.3668975830078,185.84120178222656]
WATER=[-2324,108.55000305175781,68]
NATIVE_ROUTINES=(0x9037d4,0x9ec22c,0xa0902c,0x906ad4,0x90c348,0x9e171c,0x9e1970,0xa2fa14,0xa82030)


def evidence_output(path):
    path=Path(path).resolve()
    if not path.is_relative_to((ROOT/'analysis/raw').resolve())or path.exists():
        raise ValueError('Use a new ignored evidence path')
    return path


def state(engine,actor):
    a=actor['address'];m=a+0x118;direction=list(engine.r(m+0xc,'3f'));speed=engine.r(m+0x18,'f')[0]
    value={'position':list(engine.r(a+0x118,'3f')),'pending':list(engine.r(a+0x1ac,'3f')),
        'direction':direction,'speed':speed,'velocityY':direction[1]*speed,
        'acceleration':list(engine.r(m+0x1c,'3f')),'specialMotionPointer':engine.r(m+0xd0,'Q')[0],
        'positionDirty':engine.r(a+0x1d0,'B')[0],'jumpByte':engine.r(a+0x1d4,'B')[0],
        'stance':engine.r(a+0x38c,'I')[0],'hostGrounded':actor['grounded'],
        'hostJumpAge':actor['jumpAge'],'hostAge':actor['age'],
        'waterContactWords':list(engine.r(a+0x43c,'3I'))}
    if 'camera'in actor:
        c=actor['camera'];value['cameraWords']={'yawPitchDesiredActualDistance':list(engine.r(c+0x68,'4f')),
            'trackingFlags':engine.r(c+0x22c,'I')[0],
            'inspectionCameraBlockSHA256':hashlib.sha256(bytes(engine.uc.mem_read(c,0x400))).hexdigest()}
    return value


def relocate_prefix(engine,actor):
    """Execute the same original prefix on dry and complete water/camera hosts."""
    from unicorn import UC_HOOK_CODE
    a=actor['address'];point=engine.alloc(12);engine.w(point,'3f',*COURTYARD)
    engine.w(engine.r(a,'Q')[0]+0x68,'Q',0xa0902c)
    root=engine.r(0x2528db0,'Q')[0];engine.w(root+0x278,'I',5)
    ends=[]
    def boundary(uc,at,size,data):
        ends.append(at);engine.set('PC',engine.EXIT)
    hook=engine.uc.hook_add(UC_HOOK_CODE,boundary,begin=0x903858,end=0x903858)
    try:engine.call(0x9037d4,{'X0':a,'X1':point,'X2':0,'X3':0},limit=2000)
    finally:engine.uc.hook_del(hook)
    if ends!=[0x903858]:raise ValueError('Original Hero relocation prefix did not reach its boundary')


def walk_fall(engine,identity,frames=261):
    pos=ROOF[:];rows=[]
    for i in range(frames):
        row=engine.actor_tick(identity,pos,[0,4.8]if i<283 else[0,0],50)
        rows.append({'frame':i,**row});pos=row['position']
    return rows


def native_cases(config):
    from tutorial_fall_recovery_probe import load_engine
    from unicorn import UC_HOOK_CODE
    engine,image,loaded,identity=load_engine(config);out=[];trace=[]
    def observe(uc,at,size,data):
        trace.append({'entry':hex(at),'actorOrMotion':hex(engine.get('X0')),'caller':hex(engine.get('X30')-4)})
    hooks=[engine.uc.hook_add(UC_HOOK_CODE,observe,begin=a,end=a)for a in (*NATIVE_ROUTINES[:5],0xa2fa14,0xa82030)]
    try:
        for mode,n in [('setter-only',261),('hero-relocation-prefix',261),('fallen-hero-prefix',301)]:
            name='reentry-native-'+mode;frames=walk_fall(engine,name,n);actor=engine.actors[name];a=actor['address']
            before=state(engine,actor);point=engine.alloc(12);engine.w(point,'3f',*COURTYARD)
            start=len(trace)
            if mode=='setter-only':engine.call(0xa0902c,{'X0':a,'X1':point})
            else:
                # Bind the verified original Hero virtual setter, rather than
                # substituting a host coordinate write. The later singleton /
                # non-Hero dispatch is a named, unexecuted boundary.
                relocate_prefix(engine,actor)
            after=state(engine,actor)
            support=engine.initial_support(actor);after_support=state(engine,actor)
            follow=[];pos=after_support['position']
            for i in range(30):
                row=engine.actor_tick(name,pos,[0,0]if i<20 else[4.8,0],50)
                follow.append({'frame':i,**row});pos=row['position']
            out.append({'mode':mode,'fallFrames':frames,'before':before,'afterRelocation':after,
                'afterInitialSupport':after_support,'initialSupport':support,'follow':follow,
                'calls':trace[start:],'prefixBoundary':'0x903858'if mode!='setter-only'else None,
                'explicitLoadingStage':[1,4],'explicitMapRequestKey':5 if mode!='setter-only'else None,
                'fullOriginalEnterMapExecuted':False,'originalEscapeDestinationKnown':False})
        name='reentry-native-complete-hero';frames=walk_fall(engine,name);actor=engine.actors[name];a=actor['address']
        before=state(engine,actor);point=engine.alloc(12);engine.w(point,'3f',*COURTYARD)
        engine.w(engine.r(a,'Q')[0]+0x68,'Q',0xa0902c)
        singleton_before=engine.r(0x2543c10,'Q')[0];calls=[];after=[]
        for _ in range(2):
            start=len(trace);returned=engine.call(0x9037d4,{'X0':a,'X1':point,'X2':0,'X3':0})
            calls.append({'returnedX0':returned,'trace':trace[start:]});after.append(state(engine,actor))
        singleton=engine.r(0x2543c10,'Q')[0]
        if not singleton:raise ValueError('Original relocation singleton constructor did not publish')
        complete={'before':before,'afterFirst':after[0],'afterSecond':after[1],'calls':calls,
            'singletonBefore':singleton_before,'singletonAfter':singleton,
            'singletonVtable':hex(engine.r(singleton,'Q')[0]),
            'singletonSecondaryVtable':hex(engine.r(singleton+0x40,'Q')[0]),
            'fullOriginalHeroMethodReturned':True,'fullOriginalEnterMapExecuted':False,
            'hostKindBinding':'normal on-foot 0x120a; original ctor, not a supplied singleton'}
    finally:
        for hook in hooks:engine.uc.hook_del(hook)
    pins=[]
    for at in NATIVE_ROUTINES:
        routine,_=image.routine(at);size=routine['size']
        pins.append({'address':hex(at),'size':size,'sha256':hashlib.sha256(image.read(at,size)).hexdigest()})
    return {'identity':identity,'loaded':loaded,'cases':out,'completeHeroRelocation':complete,'nativeRoutines':pins,
            'allSpecialMotionPointersEmpty':all(r['before']['specialMotionPointer']==0 for r in out),
            'cameraOrOriginalWaterResetProven':False}


def wet_jump_prefix_cases(config):
    """Original prefix on real jump/dive state, without calling the web reset."""
    from analyze_native_resources import NativeImage
    from native_phy_stream import NativePHYStreamMixin
    from native_map_entry_probe import NativeMapEntryProbe
    from source_layer_queue import SourceLayerQueue
    cfg=json.loads(Path(config).read_text());raw=Path(cfg['library']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=cfg['nativeSHA256']:raise ValueError('Original native identity differs')
    engine=type('ReentryFullEngine',(NativePHYStreamMixin,SourceLayerQueue),{})(NativeImage(raw));checked=set()
    def read(name):
        item=cfg['sourceFiles'][name];value=Path(item['path']).read_bytes()
        if hashlib.sha256(value).hexdigest()!=item['sha256']:raise ValueError('Original PHY differs: '+name)
        checked.add(name);return value
    terrain=json.loads(Path(cfg['terrain']).read_text());collision=json.loads(Path(cfg['collision']).read_text())
    light=json.loads(Path(cfg['terrainLighting']).read_text())
    engine.load_world(terrain,collision,read,{tuple(r['tile']):r['runtimeFlags']for r in light['tiles']})
    engine.load_water(json.loads(Path(cfg['swimming']).read_text()));engine.load_diving(json.loads(Path(cfg['diving']).read_text()))
    engine.load_shore();engine.load_animation_blending(json.loads(Path(cfg['animationBlending']).read_text()))
    engine.load_stop_queue(json.loads(Path(cfg['stopQueue']).read_text()));engine.load_layer_queue(json.loads(Path(cfg['layerQueue']).read_text()))
    out=[]
    for scenario in ('jump','underwater'):
        name='reentry-prefix-'+scenario;pos=(COURTYARD if scenario=='jump'else WATER)[:];frames=[]
        for i in range(1 if scenario=='jump'else 30):
            control=None if scenario=='jump'else{'forward':True,'pitchDelta':-40 if i==0 else 0,'yawDelta':-90 if i==0 else 0}
            row=engine.actor_tick(name,pos,[0,0]if scenario=='jump'else[4.8,0],50,scenario=='jump',control)
            frames.append(row);pos=row['position']
        actor=engine.actors[name];before=state(engine,actor);relocate_prefix(engine,actor);after=state(engine,actor)
        # This method uses call/read/write only, avoiding the different fragment
        # signatures on the original camera and map-entry inspection hosts.
        support=NativeMapEntryProbe.initial_support(engine,actor);after_support=state(engine,actor)
        follow=[];pos=after_support['position']
        for i in range(20):
            row=engine.actor_tick(name,pos,[0,0],50,False);follow.append(row);pos=row['position']
        out.append({'scenario':scenario,'preparationFrames':frames,'before':before,'afterRelocation':after,
            'initialSupport':support,'afterInitialSupport':after_support,'follow':follow,
            'wholeOriginalEnterMapExecuted':False,'webResetCalled':False,'prefixBoundary':'0x903858'})
    return {'cases':out,'sourceFilesChecked':len(checked),'cameraResetScope':'only observed; no camera fields manually reset',
            'waterSeedScope':'preparation uses the existing source water metadata and movement predicates'}


class Worker:
    """Unmodified existing stdin protocol, no network and no character storage."""
    def __init__(self,config,log):
        self.log=Path(log).open('w');self.records=[]
        self.process=subprocess.Popen([sys.executable,str(ROOT/'tools/source_physics_worker.py'),str(config)],
            cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,text=True,bufsize=1)
        self.selector=selectors.DefaultSelector();self.selector.register(self.process.stdout,selectors.EVENT_READ)

    def request(self,operation,data=None):
        request={'operation':operation,'data':data or{}}
        self.process.stdin.write(json.dumps(request,separators=(',',':'))+'\n');self.process.stdin.flush()
        if not self.selector.select(60):raise ValueError('Independent physics worker response timed out')
        line=self.process.stdout.readline()
        if not line:raise ValueError('Independent physics worker exited; see its private stderr log')
        reply=json.loads(line);self.records.append({'request':request,'reply':reply})
        if'error'in reply:raise ValueError('Existing worker rejected fixture: '+reply['error'])
        return reply['result']

    def tick(self,identity,pos,velocity=(0,0),jump=False,control=None):
        return self.request('tick',{'identity':identity,'position':pos,'velocity':list(velocity),
            'milliseconds':50,'jump':jump,'control':control})

    def close(self):
        self.process.stdin.close()
        try:self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:self.process.terminate();self.process.wait(timeout=5)
        self.selector.close();self.process.stdout.close();self.log.close()


def follow_reset(worker,identity,operation):
    if operation=='reset':result=worker.request('reset',{'identity':identity,'position':COURTYARD})
    elif operation=='forget':result=worker.request('forget',{'identity':identity})
    else:raise ValueError('Unknown reset comparison')
    rows=[];pos=COURTYARD[:]
    for i in range(30):
        row=worker.tick(identity,pos,(0,0)if i<20 else(4.8,0));rows.append({'frame':i,**row});pos=row['position']
    return {'operation':operation,'response':result,'frames':rows}


def worker_cases(config,log):
    cfg=json.loads(Path(config).read_text())
    if not all(cfg.get(k)for k in ('swimming','diving','shoreTransitions','animationBlending','stopQueue','layerQueue','nativeArchiveStream')):
        raise ValueError('Compare the full existing movement/water/camera/animation worker')
    worker=Worker(config,log)
    try:
        initialized=worker.request('init');cases=[]
        watcher='reentry-unaffected';watch_before=worker.tick(watcher,COURTYARD)
        for operation in ('reset','forget'):
            name='reentry-fall-'+operation;pos=ROOF[:];frames=[]
            for i in range(261):
                row=worker.tick(name,pos,(0,4.8));frames.append({'frame':i,**row});pos=row['position']
            # Negative control: the same cached identity does NOT ingest a new
            # input position as a reset. Never present this as a repair path.
            stale=worker.tick(name,COURTYARD)
            restored=follow_reset(worker,name,operation)
            cases.append({'scenario':'airborne-fall','identity':name,'fallFrames':frames,
                          'coordinateOnlyNegativeControl':stale,**restored})
        name='reentry-jump-reset';jump=worker.tick(name,COURTYARD,jump=True)
        cases.append({'scenario':'jump','identity':name,'before':jump,**follow_reset(worker,name,'reset')})
        for operation in ('reset','forget'):
            name='reentry-dive-'+operation;pos=WATER[:];frames=[]
            for i in range(30):
                control={'forward':True,'pitchDelta':-40 if i==0 else 0,'yawDelta':-90 if i==0 else 0}
                row=worker.tick(name,pos,(4.8,0),control=control);frames.append({'frame':i,**row});pos=row['position']
            cases.append({'scenario':'underwater','identity':name,'diveFrames':frames,**follow_reset(worker,name,operation)})
        watch_after=worker.tick(watcher,COURTYARD)
        pins=[]
        for name in ('source_physics_worker.py','source_physics.py','source_swimming.py','source_diving.py',
                     'source_shore.py','source_animation_blending.py','source_stop_queue.py','source_layer_queue.py'):
            path=ROOT/'tools'/name;pins.append({'path':'tools/'+name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        return {'initialized':initialized,'cases':cases,'unaffectedControl':{'before':watch_before,'after':watch_after},
            'workerFiles':pins,'requestCount':len(worker.records),'protocolTranscript':worker.records,
            'cameraScope':'existing source camera CPU with named host projection/render setters; not Android render session',
            'resetScope':'existing worker deletes cached identity then allocates a fresh host-bound actor/camera',
            'reconnectScope':'forget then first tick makes a fresh actor; no real browser socket tested here'}
    finally:worker.close()


def analyze(config,output):
    cfg_path=Path(config).resolve();output=evidence_output(output);output.parent.mkdir(parents=True,exist_ok=True)
    if any(output.with_suffix(suffix).exists()for suffix in ('.native-progress.json','.worker-stderr.txt')):
        raise ValueError('Use fresh evidence sidecar paths')
    cfg=json.loads(cfg_path.read_text());native=native_cases(cfg_path)
    native['wetJumpPrefix']=wet_jump_prefix_cases(cfg_path)
    output.with_suffix('.native-progress.json').write_text(json.dumps(native,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    worker=worker_cases(cfg_path,output.with_suffix('.worker-stderr.txt'))
    from tutorial_reentry_reset_binding_probe import binding_cases
    binding=binding_cases()
    result={'format':'oc2-source-reentry-reset-comparison-v1','nativeSHA256':cfg['nativeSHA256'],
        'configSHA256':hashlib.sha256(cfg_path.read_bytes()).hexdigest(),'target':COURTYARD,
        'targetProvenance':'authorized web cinematic7 trial entry; NOT original escape or first spawn',
        'native':native,'worker':worker,'binding':binding,
        'scope':{'originalEscapeDestinationKnown':False,'wholeOriginalEnterMapRestored':False,
                 'userSaveReadOrModified':False,'sharedWorkerChanged':False,'productionChanged':False,
                 'newMovementRuleOrFloorAdded':False,'actualBrowserAccepted':False}}
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    return result


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--config',type=Path,default=DEFAULT_CONFIG)
    cli.add_argument('--output',type=Path,required=True);args=cli.parse_args()
    report=analyze(args.config,args.output)
    print(json.dumps({'output':str(args.output),'nativeCases':len(report['native']['cases']),
                      'workerCases':len(report['worker']['cases']),'workerRequests':report['worker']['requestCount'],
                      'saveChanged':False}))
