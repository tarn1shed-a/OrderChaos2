"""Read-only source collision/fall/initial-floor diagnostics at explicit positions.

No existing actor save, spawn, safe floor, runtime server or rescue rule is edited.
Paths are bounded keyboard inspection inputs, not a recovered player recording.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_CONFIG=ROOT/'analysis/raw/tutorial-elevator-20261114/four-inside-candidate/native-physics.json'


def fall_probe_type():
    from native_phy_stream import NativePHYStreamMixin
    from native_map_entry_probe import NativeMapEntryProbe
    from unicorn import UC_HOOK_CODE

    class FallProbe(NativePHYStreamMixin,NativeMapEntryProbe):
        def __init__(self,image):
            super().__init__(image);self.shape_sources={};self.fall_entries=[]
            self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=0x90d428,end=0x90d428)

        def hook(self,uc,at,size,data):
            if at==0x90d428:
                actor=self.get('X0');self.fall_entries.append({'position':list(self.r(actor+0x118,'3f')),
                    'pending':list(self.r(actor+0x1ac,'3f')),'originalEntry':'0x90d428',
                    'originalCaller':hex(self.get('X30')-4),'heightDifferenceS9':self.gf('S9'),
                    'restoredPriorHeightS10':self.gf('S10')})
                return  # Observe; the real instruction still executes.
            return super().hook(uc,at,size,data)

        def transform(self,head,instance):
            head=super().transform(head,instance);pointer=head
            while pointer:
                self.shape_sources[pointer]=instance;pointer=self.r(pointer+8,'Q')[0]
            return head

        def support(self,point,extra=.5):
            x,y,z=point;normal=self.scratch+0x4400;state=normal+0x100;result=normal+0x200
            self.uc.mem_write(normal,bytes(12));self.uc.mem_write(state,bytes(12));self.uc.mem_write(result,bytes(32))
            self.call(0xa8752c,{'X0':0,'W1':0,'X2':normal,'X3':0,'W4':0,'W5':0,'X6':state,'X7':result},
                      {'S0':x,'S1':z,'S2':y+extra})
            shape=self.r(result,'Q')[0];instance=self.shape_sources.get(shape)
            return {'height':self.gf('S0'),'normal':list(self.r(normal,'3f')),
                'shapePresent':bool(shape),'instanceId':self.objects.get(shape),
                'sourcePHY':instance.get('sourcePHY')if instance else None,
                'ownerTile':instance.get('tile')if instance else None,
                'rawShapeBounds':list(self.r(shape+0x20,'6f'))if shape else None,
                'shapeBoundsAreOrdered':bool(shape)and all(self.r(shape+0x20,'6f')[i]<=self.r(shape+0x20,'6f')[i+3]for i in range(3)),
                'topInput':y+extra,'sourceCellAvailable':self.available(x,z)}

    return FallProbe


def load_engine(config):
    from analyze_native_resources import NativeImage,NATIVE_SHA256
    cfg=json.loads(Path(config).read_text());raw=Path(cfg['library']).read_bytes()
    if cfg['nativeSHA256']!=NATIVE_SHA256 or hashlib.sha256(raw).hexdigest()!=NATIVE_SHA256:raise ValueError('Original native identity differs')
    image=NativeImage(raw);engine=fall_probe_type()(image);checked=set()
    def read(name):
        row=cfg['sourceFiles'][name];value=Path(row['path']).read_bytes()
        if hashlib.sha256(value).hexdigest()!=row['sha256']:raise ValueError('Original PHY differs: '+name)
        checked.add(name);return value
    terrain=json.loads(Path(cfg['terrain']).read_text());profile=json.loads(Path(cfg['collision']).read_text());lighting=json.loads(Path(cfg['terrainLighting']).read_text())
    loaded=engine.load_world(terrain,profile,read,{tuple(t['tile']):t['runtimeFlags']for t in lighting['tiles']})
    return engine,image,loaded,{'configSHA256':hashlib.sha256(Path(config).read_bytes()).hexdigest(),
        'collisionSHA256':hashlib.sha256(Path(cfg['collision']).read_bytes()).hexdigest(),
        'nativeSHA256':NATIVE_SHA256,'sourceFilesChecked':len(checked),'sourceFilesConfigured':len(cfg['sourceFiles'])}


def motion_case(engine,name,start,velocity,frames,settle_frames=0):
    if not engine.available(start[0],start[2]):raise ValueError('Inspection start is outside available source cells')
    result=[];before=len(engine.fall_entries);position=list(start)
    for i in range(frames+settle_frames):
        input_velocity=velocity if i<frames else [0,0]
        support_before=engine.support(position)
        frame=engine.actor_tick('fall-inspection-'+name,position,input_velocity,50)
        support_after=engine.support(frame['position'])
        result.append({'frame':i,'inputPosition':position,'inputVelocityXZ':input_velocity,'supportBefore':support_before,
                       **frame,'supportAfter':support_after})
        position=frame['position']
    falls=[row for row in result if not row['grounded']]
    edge=None
    if falls:
        first=falls[0];a=first['inputPosition'];b=first['position'];top=max(a[1],b[1])+.5;bottom=min(first['supportBefore']['height'],first['supportAfter']['height'])-.5
        edge={'beforeXZ':[a[0],a[2]],'afterXZ':[b[0],b[2]],
            'beforeTile':[math.floor(a[0])>>6,math.floor(a[2])>>6],
            'afterTile':[math.floor(b[0])>>6,math.floor(b[2])>>6],
            'beforeVerticalRay':engine.ray([a[0],top,a[2]],[a[0],bottom,a[2]]),
            'afterVerticalRay':engine.ray([b[0],top,b[2]],[b[0],bottom,b[2]]),
            'sourceRegistrationChangedDuringPath':False}
    return {'name':name,'inspectionInputNotPlayerRecording':True,'start':start,'horizontalVelocityInput':velocity,
        'hostStepMilliseconds':50,'hostSpeedNotRecoveredOriginal':True,'horizontalFrames':frames,'settleFrames':settle_frames,'frames':result,
        'fallConsumerEntries':engine.fall_entries[before:],'firstEdgeWitness':edge,
        'firstAirborneFrame':falls[0]['frame']if falls else None,
        'maxVerticalDrop':start[1]-min(row['position'][1]for row in result),
        'finalPosition':position,'finalGrounded':result[-1]['grounded'],
        'newRescueOrSafeFloorApplied':False}


def temple_edge_cases(engine):
    start=[-2611.41015625,172.3668975830078,185.84120178222656]
    base=engine.support(start);rows=[]
    if base['instanceId']!=715733128:raise ValueError('Original temple02 inspection support changed')
    for name,axis in [('minusX',[-1,0]),('plusX',[1,0]),('minusZ',[0,-1]),('plusZ',[0,1])]:
        samples=[];edge=None
        for n in range(1,65):
            point=[start[0]+axis[0]*n,start[1],start[2]+axis[1]*n];support=engine.support(point)
            samples.append({'distance':n,'point':point,'sourceSupport':support})
            if support['height']<base['height']-.5:edge=n;break
        motion=None
        if edge is not None:
            motion=motion_case(engine,'temple-roof-edge-'+name,start,[v*4.8 for v in axis],
                               min(400,math.ceil((edge+3)/.24)+20),80)
        rows.append({'axis':name,'sampledEdgeDistance':edge,'samples':samples,'motion':motion})
    chosen=next(r['motion']for r in rows if r['axis']=='plusZ')
    actor,entry=engine.entry_position(chosen['finalPosition'])
    return {'explicitRoofInspectionPoint':start,'originalSupport':base,'rows':rows,
        'postFallReentry':{'explicitSavedPositionFixture':chosen['finalPosition'],'entry':entry,
                          'initialSupport':engine.initial_support(actor),'userSaveReadOrWritten':False},
        'scope':'bounded source support scans then continuous CPU walks from the same source roof point; no player recording'}


def analyze(config=DEFAULT_CONFIG,temple_edges=False):
    engine,image,loaded,identity=load_engine(config)
    motions=[motion_case(engine,'bridge-center-hold',[-2533,136.53165,203],[0,0],20),
             motion_case(engine,'bridge-edge-minus-x',[-2533,136.53165,203],[-4.8,0],90),
             motion_case(engine,'old-upper-hold',[-2611.41015625,172.3668975830078,185.84120178222656],[0,0],20),
             motion_case(engine,'old-lower-hold',[-2611.41015625,132.34999084472656,185.84120178222656],[0,0],20),
             motion_case(engine,'w7-courtyard-hold',[-2594,135.72999572753906,-64],[0,0],20)]
    fall_end=motions[1]['finalPosition']
    recovered_actor,reentry=engine.entry_position(fall_end)
    post_fall_reentry={'explicitSavedPositionFixture':fall_end,'entry':reentry,'initialSupport':engine.initial_support(recovered_actor),'userSaveReadOrWritten':False}
    layers=[]
    for y in (132.34999084472656,150,172.3668975830078,196):
        actor,entry=engine.entry_position([-2611.41015625,y,185.84120178222656]);support=engine.initial_support(actor)
        layers.append({'entry':entry,'initialSupport':support,
                       'pendingYPlusHalfQuery':engine.support([-2611.41015625,y,185.84120178222656])})
    pins=[]
    for at in (0x90c348,0x90c610,0x90d428,0x9ec1e4,0x9e171c,0x9e1970,0x9e3fbc,0xa878c0,0xa8752c):
        m,_=image.routine(at);size=m['size'];pins.append({'address':hex(at),'size':size,'sha256':hashlib.sha256(image.read(at,size)).hexdigest()})
    return {'format':'oc2-source-temple-fall-diagnostics-v1','identity':identity,'loaded':loaded,
        'templeEdges':temple_edge_cases(engine)if temple_edges else None,'motions':motions,'postFallReentryFixture':post_fall_reentry,'sameXZInitialFloorCases':layers,'nativeRoutines':pins,
        'limits':['Explicit on-foot static actor binding, keyboard velocity and 50ms cadence; not original Android session.',
                  'Bridge path is a reproducible inspection input, not the users actual fall recording.',
                  'Original dynamic actors and full input/state gates remain absent; no fall-prevention policy is inferred.',
                  'Initial-support stage 1/4 is an explicit fixture; original first-entry network position remains unknown.'],
        'scope':{'safeGeometryAdded':False,'userSaveReadOrModified':False,'runtimeOrProductionModified':False,
                 'escapeRuleInvented':False,'wholeMapAccepted':False}}

if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--config',type=Path,default=DEFAULT_CONFIG);cli.add_argument('--output',type=Path,required=True);cli.add_argument('--temple-edges',action='store_true')
    args=cli.parse_args();output=args.output.resolve()
    if not output.is_relative_to((ROOT/'analysis/raw').resolve())or output.exists():raise ValueError('Use a fresh ignored evidence path')
    result=analyze(args.config,args.temple_edges);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'output':str(output),'motions':[{k:r[k]for k in ('name','firstAirborneFrame','maxVerticalDrop','finalPosition','finalGrounded')}for r in result['motions']],'newRescueApplied':False}))
