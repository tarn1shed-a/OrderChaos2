"""Own HumanM Class show/idle queue and source-pose controls.

Only the original loaded-track boundary is hosted. Queue requests, both channel
records, range clocks, finish flags, and Class callbacks execute the source CPU.
No model/GPU ready result is supplied and no Three completion is substituted.
"""
import hashlib
import json
import math
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AREA = ROOT / 'analysis/raw/creation-human-class-animation-20261116'
NATIVE = ROOT / 'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'
BASE = ROOT / 'analysis/raw/character-human-idle02-20261116/candidate-v1/native-physics.world.json'
ANIMATION_RECEIPT = ROOT / 'analysis/raw/creation-class-source-20261116/animation-v2.json'
ANIMATION_RECEIPT_SHA = 'e8309a790fd7530d348df4d12bedfaea96194ff1e21abc250ec9b03b7178b0f5'
BODY_SHA = '2fb559ab9d1ed126cffb8c18d8b07ab11ccb32193487d7c778a64e6d19acb6b6'
ANIMATION_SHA = '1798ec8c3cc2fa0c136f8f3c278928b1ca6dbdf7c9bbc4871d3fb197cd50000e'
CODES = ('wr', 'rg', 'mg', 'ds', 'mk')
NAMES = tuple('login_' + code + suffix for code in CODES for suffix in ('_show', '_idle', '_idle02'))
IDENTITIES = tuple({'uiRace':0,'gender':0,'uiProfessionIndex':i,'profession':profession,'stage':1,
    'displayId':display,'sourceModelId':model,'sourceBodySHA256':BODY_SHA,'sourceAnimationSHA256':ANIMATION_SHA}
    for i,(profession,display,model) in enumerate(((1,2024,1),(3,2695,1),(2,2026,103),(5,2693,1),(4,2028,1))))
sha = lambda raw: hashlib.sha256(raw).hexdigest()
write = lambda p,v: p.write_text(json.dumps(v, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def checked_identity(identity):
    if not isinstance(identity,dict) or set(identity)!=set(IDENTITIES[0]):
        raise ValueError('Exact own HumanM Class identity required')
    index=identity['uiProfessionIndex']
    if type(index) is not int or not 0<=index<5 or any(type(identity[k])is not type(value)or identity[k]!=value for k,value in IDENTITIES[index].items()):
        raise ValueError('Wrong body/profession/display/stage; no foreign animation fallback')
    return dict(IDENTITIES[index])


def original_ranges():
    if sha(ANIMATION_RECEIPT.read_bytes()) != ANIMATION_RECEIPT_SHA:
        raise ValueError('Frozen original callback/range receipt differs')
    receipt = json.loads(ANIMATION_RECEIPT.read_text())
    rows = [r for r in receipt['ownAnimationRanges'] if r['sha256'] == ANIMATION_SHA]
    if len(rows) != 1:
        raise ValueError('Exact own Human animation source required')
    ranges = {r['name']:r for r in rows[0]['sourceRanges'] if r['name'] in NAMES}
    if set(ranges) != set(NAMES):
        raise ValueError('All15 original Human Class ranges required')
    return ranges


def probe_type():
    from source_stop_queue import SourceStopQueue
    from unicorn import UC_HOOK_CODE

    class ClassQueue(SourceStopQueue):
        def __init__(self, image):
            self.class_active = False
            super().__init__(image)
            self.ranges = original_ranges()
            self.stop_profile = {'ranges':self.ranges}
            cfg = json.loads(BASE.read_text())
            profile = json.loads(Path(cfg['sourceHumanComposition']['queue']['path']).read_text())
            self.blending_profile = profile['blending']
            for at in (0x331a18,0x53c740,0x396f4c,0x32b210,0x32b24c):
                self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=at,end=at)
            self.view = None
            self.requests = []; self.callback_events = []; self.finish_events = []; self.reports = []
            self.total_ms = 0

        def hook(self, uc, at, size, data):
            if self.class_active:
                if at == 0x331a18:
                    request = {'name':self.cstr(self.get('X2')).decode(), 'arg1':self.get('W1'),
                        'flags':self.get('W3'),'speed':self.gf('S0'),'begin':self.gf('S1'),'blend':self.gf('S2'),
                        'atMs':self.total_ms,'caller':hex(self.get('X30'))}
                    if request['name'] not in self.ranges:
                        raise ValueError('Unadmitted own Human Class track: '+request['name'])
                    self.requests.append(request)
                    return  # Actual331a18 ->32d86c ->32d58c instructions.
                if at == 0x53c740:
                    self.callback_events.append({'name':self.cstr(self.get('X0')).decode(),
                        'status':self.get('W1'),'channel':self.get('W2'),
                        'nodePresent':bool(self.get('X3')),'atMs':self.total_ms,
                        'caller':hex(self.get('X30'))})
                    return  # Original callback chooses/queues own next idle.
                if at in (0x32b210,0x32b24c):
                    self.finish_events.append({'channel':int(at==0x32b24c),'atMs':self.total_ms,
                        'originalClockEntry':hex(self.get('X30')),'clockMs':self.r(self.get('X0')+8,'f')[0]})
                    return
                if at == 0x396f4c:
                    self.reports.append({'values':[self.get('W'+str(i)) for i in range(1,5)],'atMs':self.total_ms})
                    self.set('W0',0); self.set('PC',self.get('X30')); return
                if at == 0x32f14c and self.queue_selection:
                    channel=self.get('W20'); record=bytes(uc.mem_read(self.get('SP')+0x60,0x58))
                    name=record[:64].split(b'\0')[0].decode()
                    if name not in self.ranges or self.r(self.get('SP')+0xb0,'Q')[0]:
                        raise ValueError('Unadmitted clip/event provider at original loaded-resource boundary')
                    self.selections.append((channel,record))
                    # No resource loader, resource return or graph success is supplied.
                    # Preserve source record copying and its own selection callback.
                    self.set('PC',0x32ff08); return
                if at == 0x32ffcc and self.queue_selection:
                    # SourceStopQueue suppresses this callback for old locomotion.
                    # Here the original stored pointer/argument are consumed by the
                    # original3302a0..3302c4 code, not a host completion callback.
                    self.set('X8',self.r(self.get('X19')+0x660,'Q')[0])
                    self.set('PC',0x3302a0); return
                if self.imports.get(at) == 'printf':
                    self.set('W0',0); self.set('PC',self.get('X30')); return
            return super().hook(uc,at,size,data)

        def create(self, profession_index):
            if type(profession_index) is not int or not 0 <= profession_index < 5 or self.view is not None:
                raise ValueError('One original Human Class selection per probe')
            actor={'address':self.alloc(0x1000)}
            q=self.queue_actor(actor)
            self.call(0x32c14c,{'X0':q['engine'],'W1':3})
            if self.r(q['engine']+0x1c,'B')[0] != 2:
                raise ValueError('Original Class two-channel manager required')
            second={k:q[k] for k in ('engine','controller','provider','record')}
            node=self.alloc(0xd8); weights=self.alloc(8); holder=self.alloc(8)
            self.w(node+0x48,'2Q',weights,weights+4);self.w(weights,'2f',1,0);self.w(node+0x90,'I',1);self.w(holder,'Q',node)
            second.update(control=None,current=None,previous=None,sequence=0,completions=0,blendNode=node,weights=weights,holder=holder)
            q['layers']=[q,second]
            view=self.alloc(0x180); self.w(view+0xa8,'Q',q['engine'])
            controller=self.alloc(0x300); self.w(controller+0x5c,'3i',0,0,profession_index)
            self.w(0x2534300,'Q',controller); self.w(0x2533fec,'2i',0,0)
            self.call(0x331d58,{'X0':view,'X1':0x53c740,'X2':view})
            self.view=view; self.q=q; self.profession_index=profession_index; self.controller=controller
            self.w(controller+0x88,'Q',view)
            return self

        def producer_before_display(self):
            """Actual538b74 prefix, stopping BEFORE the display/cache function."""
            seen=[]
            def boundary(uc,at,size,data):
                if at==0x53d3e8:
                    seen.append({'displayId':self.get('W1'),'arg2':self.get('W2'),'arg3':self.get('W3'),
                        'stoppedBeforeOriginalDisplayConstructor':True})
                    self.set('PC',self.EXIT)
            handle=self.uc.hook_add(UC_HOOK_CODE,boundary)
            self.w(self.controller+0x64,'i',-1)
            try:self.call(0x538b74,{'X0':self.controller,'W1':0xffffffff,'W2':0xffffffff,'W3':self.profession_index})
            finally:self.uc.hook_del(handle)
            if len(seen)!=1:raise ValueError('Original Class display request not reached')
            return seen[0]

        def post_display_branch(self):
            """Conditional source branch only: no synthetic53d3e8 success."""
            self.class_active=self.queue_native=True
            try:self.original_fragment(0x538c1c,0x538ca4,{'X19':self.controller,'W20':self.profession_index})
            finally:self.class_active=self.queue_native=False

        def request(self,name,flags):
            if self.view is None or name not in self.ranges or flags not in (1,8,16):
                raise ValueError('Own loaded Class request and exact control flag required')
            self.class_active=self.queue_native=True
            try:self.call(0x331a18,{'X0':self.view,'W1':0xffffffff,'X2':self.string(name.encode()),'W3':flags}, {'S0':1,'S1':0,'S2':-1})
            finally:self.class_active=self.queue_native=False

        def tick(self,milliseconds):
            if type(milliseconds) is not int or not 0<=milliseconds<=20000:
                raise ValueError('Explicit bounded source delta milliseconds required')
            self.selections=[]; self.class_active=self.queue_native=self.queue_selection=True
            try:self.call(0x330d0c,{'X0':self.q['engine'],'W1':milliseconds})
            finally:self.class_active=self.queue_native=self.queue_selection=False
            for channel,record in self.selections:
                self.bind_selected(self.q['layers'][channel],record,channel)
            self.total_ms+=milliseconds
            self.class_active=self.queue_native=True
            try:
                for layer in self.q['layers']:
                    for p in (layer['current'],layer['previous']):
                        if p:
                            self.call(0x11962c0,{'X0':p['control']},{'S0':milliseconds})
                            p['ageMs']=self.r(p['control']+8,'f')[0]-p['startMs']
            finally:self.class_active=self.queue_native=False
            layers=[]
            for channel,layer in enumerate(self.q['layers']):
                clean=lambda p:{k:v for k,v in p.items() if k not in ('control','startMs')} if p else None
                layers.append({'channel':channel,'current':clean(layer['current']),'previous':clean(layer['previous']),
                    'weights':self.blend_tick(layer,milliseconds),'sequence':layer['sequence'],
                    'managerCompletionFlags':self.r(self.q['engine']+0x10+channel*4,'B')[0],
                    'pending':self.r(self.q['engine']+0x2fa+channel*0x218,'b')[0]})
            if not all(layers[0][k]==layers[1][k] for k in ('current','previous','weights','sequence')):
                raise ValueError('Class two channels diverged; do not invent composition')
            return {'atMs':self.total_ms,'layers':layers,'counter':self.r(0x2533fec,'i')[0],
                'selected':self.r(0x2533ff0,'i')[0],'requests':list(self.requests),
                'callbacks':list(self.callback_events),'clockFinishes':list(self.finish_events)}

    return ClassQueue


def queue_controls(image):
    result=[]
    for index,code in enumerate(CODES):
        p=probe_type()(image).create(index)
        before=p.producer_before_display()
        p.post_display_branch()
        frames=[p.tick(0)]
        for suffix in ('_show','_idle','_idle02','_idle'):
            name='login_'+code+suffix
            if frames[-1]['layers'][0]['current']['clip']!=name:
                raise ValueError('Original Class queue sequence differs')
            duration=p.ranges[name]['endMs']-p.ranges[name]['startMs']
            age=frames[-1]['layers'][0]['current']['ageMs']
            frames.append(p.tick(int(duration-age)))
            if frames[-1]['layers'][0]['managerCompletionFlags']&1:
                raise ValueError('Original clock completed at exact end')
            frames.append(p.tick(1))
            if not frames[-1]['layers'][0]['managerCompletionFlags']&1:
                raise ValueError('Original clock failed to finish strictly after end')
            frames.append(p.tick(0))
        result.append({'uiProfessionIndex':index,'profession':(1,3,2,5,4)[index],
            'sourceDisplayRequest':before,'postDisplayBranchIsConditional':True,
            'frames':frames,'reports':p.reports,'originalClassCallbackExecuted':True,
            'ownLoadedTrackBoundary':True,'nativeModelOrGPUReadySupplied':False})
    return result


def pose_controls(image):
    from bdae_animation import BDAEAnimation
    from bdae_convert import BDAE
    from bdae_character import aliases
    from character_elf_male_binding import source_controller
    from character_human_queue_composition_probe import HumanCompositionProbe
    from character_world_motion_probe import parse_source_clock,host_source_pose,difference,source_track_sample
    from tutorial_npc_binding_probe import host_vertices,world_matrices
    import copy
    cfg=json.loads(BASE.read_text());desc=cfg['sourceHumanComposition']
    for field,digest in [('body',BODY_SHA),('animation',ANIMATION_SHA),('bodyData',desc['bodyData']['sha256'])]:
        if desc[field]['sha256']!=digest or sha(Path(desc[field]['path']).read_bytes())!=digest:
            raise ValueError('Exact own Human source input required: '+field)
    body=BDAE(desc['body']['path']);reader=BDAEAnimation(desc['animation']['path'])
    data=json.loads(Path(desc['bodyData']['path']).read_text())
    skin=source_controller(body,{'meshes':[data['meshes'][0]]},data['rig']['nodes'],0)
    p=HumanCompositionProbe(image,body,body,skin,0);p.animation(reader)
    if len(p.channels)!=135:raise ValueError('Own135 source properties required')
    parsed=parse_source_clock(reader,NAMES)
    by_name=aliases(skin['nodes']);bone_names=sorted({n for s in data['rig']['skins']for n in s['boneNames']})
    if len(bone_names)!=31:raise ValueError('Own31 source skin bones required')
    checks=[]
    for clip in parsed['clips']:
        start,end=clip['sourceRangeMs'];duration=end-start;cases=[]
        for age in (0.,33.3125,66.9375,duration/2,duration-.125,float(duration)):
            actual=p.pose(start+age);palette,values=host_source_pose(skin,clip,age/1000)
            prop_error=max(difference(row['value'],values[(row['node'],row['type'])]) for row in actual['samples'])
            palette_error=max(abs(a-b)for row,want in zip(actual['matrices'],palette)for a,b in zip(row,want))
            native_vertices=p.vertices(data['meshes'][0]['positions'])
            expected=host_vertices(skin,data['meshes'][0]['positions'],palette)
            vertex_error=max(abs(a-b)for a,b in zip(native_vertices,expected))
            host_nodes=copy.deepcopy(skin['nodes'])
            for track in clip['tracks']:
                host_nodes[by_name[track['node']]][track['type']]=list(source_track_sample(track,start,age/1000))
            world=world_matrices(host_nodes)
            bone_world={n:list(p.r(p.native_nodes[n]+0x28,'16f'))for n in bone_names}
            world_error=max(abs(a-b)for n in bone_names for a,b in zip(bone_world[n],world[by_name[n]]))
            if max(prop_error,palette_error,vertex_error,world_error)>.002:
                raise ValueError('Original Class property/bone/vertex differs; no threshold widening')
            cases.append({'ageMs':age,'sourceMs':start+age,'maximumPropertyError':prop_error,
                'maximumPaletteError':palette_error,'maximum31BoneWorldError':world_error,
                'maximumFirstMeshVertexError':vertex_error,'original135Properties':actual['samples'],
                'original31BoneWorldMatrices':bone_world,'originalFirstMeshPalette':actual['matrices']})
        checks.append({'name':clip['name'],'sourceRangeMs':clip['sourceRangeMs'],'cases':cases})
    write(AREA/'human-class-tracks-v1.json',parsed)
    result={'format':'oc2-own-human-class-source-pose-controls-v1','nativeSHA256':sha(image.data),
        'bodySHA256':BODY_SHA,'animationSHA256':ANIMATION_SHA,'bodyDataSHA256':desc['bodyData']['sha256'],
        'sourceProperties':135,'sourceSkinBones':31,'firstMeshPaletteBones':len(skin['bones']),
        'firstMeshVertices':len(data['meshes'][0]['positions'])//3,'comparisonTolerance':.002,
        'fullSourceTracksSHA256':sha((AREA/'human-class-tracks-v1.json').read_bytes()),
        'cases':checks,'sourceValuesOrRigOrWeightsOrClockChanged':False,
        'completeNativeModelLoaderOrGPUExecuted':False,'browserOrProductionChanged':False}
    write(AREA/'source-pose-controls-v1.json',result)
    return result


def boundary_controls(image):
    rows=[]
    for flag in (1,8,16):
        p=probe_type()(image).create(0)
        # Original callback setter clears the optional callback. This isolates
        # the original flag/clock paths without inserting a fake finish event.
        p.call(0x331d58,{'X0':p.view,'X1':0,'X2':0})
        p.request('login_wr_show',flag)
        first=p.tick(0);duration=p.ranges['login_wr_show']['endMs']-p.ranges['login_wr_show']['startMs']
        exact=p.tick(duration);over=p.tick(1)
        rows.append({'flags':flag,'initial':first,'exactEnd':exact,'oneMsAfterEnd':over})
    p=probe_type()(image).create(0);p.call(0x331d58,{'X0':p.view,'X1':0,'X2':0})
    p.request('login_wr_show',1);p.tick(0);p.request('login_wr_idle',8);p.request('login_wr_idle02',8)
    appended=[p.r(p.q['engine']+0x2fa+c*0x218,'b')[0]for c in range(2)]
    p.request('login_wr_idle02',1)
    replaced=[p.r(p.q['engine']+0x2fa+c*0x218,'b')[0]for c in range(2)]
    pendingNames=[]
    for channel in range(2):
        base=p.q['engine']+channel*0x218;head=p.r(base+0x2f8,'b')[0]
        pendingNames.append(p.cstr(base+0xe8+head*0x58).decode())
    same=probe_type()(image).create(0);same.w(same.controller+0x64,'i',0)
    same.class_active=same.queue_native=True
    try:same.call(0x538b74,{'X0':same.controller,'W1':0xffffffff,'W2':0xffffffff,'W3':0})
    finally:same.class_active=same.queue_native=False
    if same.requests:raise ValueError('Same source profession unexpectedly replayed show')
    # Original invalid-display fast path is real source behavior, not a
    # fabricated successful cache/model/graphics reply.
    invalid=probe_type()(image);owner=invalid.alloc(0x300)
    value=invalid.call(0x53d3e8,{'X0':owner,'W1':0,'W2':1,'W3':1})
    return {'format':'oc2-human-class-original-boundary-controls-v1','flagClockControls':rows,
        'appendPendingCounts':appended,'replacePendingCounts':replaced,'replacePendingNames':pendingNames,
        'sameProfessionRequestCount':len(same.requests),'originalInvalidDisplayReturn':value,
        'nativeDisplayOrGPUReadySupplied':False}


def transition_controls(image):
    from bdae_animation import BDAEAnimation
    from bdae_convert import BDAE
    from character_elf_male_binding import source_controller
    from character_human_queue_composition_probe import HumanCompositionProbe
    from character_world_motion_probe import difference
    cfg=json.loads(BASE.read_text());desc=cfg['sourceHumanComposition']
    body=BDAE(desc['body']['path']);reader=BDAEAnimation(desc['animation']['path'])
    data=json.loads(Path(desc['bodyData']['path']).read_text())
    skin=source_controller(body,{'meshes':[data['meshes'][0]]},data['rig']['nodes'],0)
    composer=HumanCompositionProbe(image,body,body,skin,0);composer.animation(reader);composer.prepare_composition(data)
    result=[]
    for index,code in enumerate(CODES):
        queue=probe_type()(image).create(index);queue.producer_before_display();queue.post_display_branch();queue.tick(0)
        name='login_'+code+'_show';duration=queue.ranges[name]['endMs']-queue.ranges[name]['startMs']
        queue.tick(duration);queue.tick(1)
        frames=[queue.tick(0),queue.tick(75),queue.tick(75)]
        points=[]
        for elapsed,frame in zip((0,75,150),frames):
            layer=frame['layers'][0];current=layer['current'];previous=layer['previous'];weights=layer['weights']
            values=composer.own_values(current['clip'],current['ageMs'],queue.ranges)
            old=composer.own_values(previous['clip'],previous['ageMs'],queue.ranges)
            mixed=composer.mix_loaded_values(values,old,weights)
            pose=composer.compose_values([mixed,mixed])
            error=max(difference(value,row['value'])for value,row in zip(mixed,pose['properties']))
            if error>.002:raise ValueError('Actual Class equal-channel source composition differs')
            points.append({'transitionElapsedMs':elapsed,'layers':frame['layers'],
                'currentOriginal135Values':values,'previousOriginal135Values':old,
                'originalIntraLayer135MixedValues':mixed,'original135ComposedProperties':pose['properties'],
                'original31BoneWorldMatrices':pose['allSkinBoneWorldMatrices'],
                'originalFirstMeshPalette':pose['nativeBoneMatrices'],
                'originalFirstMeshVertices':composer.vertices(data['meshes'][0]['positions']),
                'maximumEqualChannelCompositionError':error,
                'originalSetterCount':len(pose['originalSetterCalls']),
                'originalCombinationCalls':pose['originalCombinationCalls']})
        result.append({'uiProfessionIndex':index,'points':points})
    report={'format':'oc2-own-human-class-original-transition-controls-v1','nativeSHA256':sha(image.data),
        'sourceBodySHA256':BODY_SHA,'sourceAnimationSHA256':ANIMATION_SHA,
        'sourcePropertyOrder':[{'index':i,'node':c['node'],'type':c['type']}for i,c in enumerate(composer.channels)],
        'originalMixMode':0,'originalPropertyMix':'0x11894f8','originalComposition':'0x372318',
        'sourceChannels':2,'channelValuesEqualInTheseControls':True,'controls':result,
        'completeNativeFrameContextFactoryOrGPUExecuted':False}
    write(AREA/'transition-controls-v1.json',report)
    return report


def playback_contract(image):
    routines={}
    for at in (0x538b74,0x53d3e8,0x53ca0c,0x331a18,0x331d58,0x335b50,0x32c14c,0x32d86c,0x32d58c,
        0x330d0c,0x32ee00,0x32b210,0x32b24c,0x11962c0,0x11967dc,0x1196824,0x53c740,0x331d88,
        0x11894f8,0x372318):
        meta,lines=image.routine(at);start=int(meta['start'],16)
        file=AREA/(hex(start)+'.asm');file.write_text('\n'.join(lines)+'\n')
        routines[hex(at)]={'start':meta['start'],'bytes':meta['size'],'sha256':sha(image.read(start,meta['size'])),'assembly':file.name}
    matrix=json.loads((ROOT/'analysis/raw/creation-class-source-20261116/source-v2.json').read_text())
    choices=[]
    for identity,code in zip(IDENTITIES,CODES):
        row,=[r for r in matrix['choices']if (r['uiRace'],r['gender'],r['uiProfessionIndex'])==(0,0,identity['uiProfessionIndex'])]
        if (row['profession'],row['display']['ID'],row['model']['ID'],row['model']['ModelPath'])!=(identity['profession'],identity['displayId'],identity['sourceModelId'],'model/npc/character/human/male/oc2_human_m_body_01.bdae'):
            raise ValueError('Original Class identity/table differs')
        choices.append({'identity':checked_identity(identity),'initialShow':'login_'+code+'_show',
            'nextIdle':'login_'+code+'_idle','secondIdle':'login_'+code+'_idle02',
            'initialRequest':{'arg1':-1,'flags':1,'speed':1.,'beginMs':0.,'blendRequestMs':-1.},
            'callbackRequest':{'arg1':-1,'flags':8,'speed':1.,'beginMs':0.,'blendRequestMs':-1.},
            'sourceModelEffectsRemainIndependent':identity['sourceModelId']==103})
    files={name:{'path':name,'sha256':sha((AREA/name).read_bytes())}for name in ('human-class-tracks-v1.json','source-pose-controls-v1.json','queue-controls-v1.json','boundary-controls-v1.json','transition-controls-v1.json')}
    result={'format':'oc2-human-male-class-playback-contract-v1','nativeSHA256':sha(image.data),
        'bodySHA256':BODY_SHA,'animationSHA256':ANIMATION_SHA,'choices':choices,'ranges':original_ranges(),
        'sourceChannels':2,'sourceProperties':135,'sourceSkinBones':31,
        'rawFlagMeanings':{'bit0':'accept/replace immediate request branch; does not loop','bit3':'append queue (flags8)','bit4':'native clock loop (flags16), absent in Class show/idle requests'},
        'callback':{'entry':'0x53c740','producer':'0x32ee00:3302a0..3302c4','status':0,'channel':1,
            'meaning':'selected-new-source-clip; queues next own idle immediately','isClockCompletionCallback':False},
        'completion':{'clock':'0x11962c0','strictlyAfterSourceEnd':True,'finishConsumers':['0x32b210','0x32b24c'],
            'selectionConsumer':'0x330d0c','nativeWholeActorFrameOrGPUSchedulerClaimed':False},
        'blend':{'negativeRequestFallbackMs':150,'originalOldWeightCap':.9900000095367432,
            'originalActiveEpsilon':1.1920928955078125e-7,'originalPropertyMix':'0x11894f8','mode':0,
            'fullPropertyComposition':'0x372318','ordinaryThreeMixOrFinishedAllowed':False},
        'displayGate':{'entry':'0x53d3e8','callerBitTest':'0x538c18',
            'actualPositivePredicate':'exact display-ID scene-cache entry located; scene visibility/TRS bound',
            'notGPUReadyPredicate':True,'nativeConstructedCacheSuccessSupplied':False,
            'sourcePostGateBranch':'0x538c1c..538ca4','postGateBranchExecutedOnlyAsConditionalSourceFragment':True,
            'callerHostRequirement':'actual own Class actor and assets constructed before invoking this conditional branch; host adaptation, not native-ready proof'},
        'sampleContract':{'data':'human-class-tracks-v1.json','clock':'nativeClock absolute uint16 frame / original float32 rounded milliseconds',
            'pose':'source_property_order + original current/previous ages/weights; all135 targets; do not interpolate the finite oracle'},
        'files':files,'nativeRoutines':routines,
        'scope':{'humanBodies':1,'professions':5,'all45Complete':False,'originalModelGPUOrBEFFCompleted':False,
            'worldGameplayOrSkillsGranted':False,'sourceTimevalRNGOrMaterialChanged':False,'uiServicesSavesGitDeploymentChanged':False}}
    write(AREA/'playback-contract-v1.json',result)
    return result


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--queue',action='store_true');parser.add_argument('--poses',action='store_true');parser.add_argument('--transitions',action='store_true');parser.add_argument('--contract',action='store_true');args=parser.parse_args()
    if args.queue:
        from analyze_native_resources import NativeImage
        image=NativeImage(NATIVE.read_bytes());result=queue_controls(image);write(AREA/'queue-controls-v1.json',result)
        write(AREA/'boundary-controls-v1.json',boundary_controls(image))
        print(json.dumps({'professions':len(result),'frames':sum(len(r['frames'])for r in result),'callback':result[0]['frames'][0]['callbacks']}))
    if args.poses:
        from analyze_native_resources import NativeImage
        result=pose_controls(NativeImage(NATIVE.read_bytes()));print(json.dumps({'clips':len(result['cases']),'samples':sum(len(c['cases'])for c in result['cases']),'properties':result['sourceProperties']}))
    if args.transitions:
        from analyze_native_resources import NativeImage
        result=transition_controls(NativeImage(NATIVE.read_bytes()));print(json.dumps({'transitions':len(result['controls']),'samples':sum(len(c['points'])for c in result['controls'])}))
    if args.contract:
        from analyze_native_resources import NativeImage
        result=playback_contract(NativeImage(NATIVE.read_bytes()));print(json.dumps({'choices':len(result['choices']),'nativeRoutines':len(result['nativeRoutines'])}))
