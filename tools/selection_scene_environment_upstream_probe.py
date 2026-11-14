"""Original startup/selection state and map catalog producers.

Only parsed FTABLE storage, allocator/string storage and label lookup are host
boundaries. No Android startup, account success, model creation or GPU result is
fabricated. The state dispatcher stops before invoking the selection factory.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from source_physics import SourcePhysics
from selection_scene_environment_probe import ROOT,verify,report,local_output
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from scene_lighting import ZONE_SHA256
from skill_attachments import decode_ftable

FORMAT='oc2-selection-environment-upstream-v1'


class UpstreamProbe(SourcePhysics):
    def __init__(self,image):
        verify(image);super().__init__(image)
        from unicorn import UC_HOOK_CODE
        self.phase=None;self.labels=[];self.frontier=None
        self.table=None;self.map_lookup_requests=[]
        for at in(0x5385e4,0x538ff4,0x537714,0x34d834,0x4c4e88,0xc99350,0xc999e8,0xc99270,0xe8581c,0x1de9e8c):
            self.uc.hook_add(UC_HOOK_CODE,self.boundary,begin=at,end=at)
        self.world=self.alloc(0x600);self.w(0x2528db0,'Q',self.world)

    def string(self,text):
        raw=text.encode();p=self.alloc(24+len(raw)+1)
        self.w(p,'QQq',len(raw),len(raw),1000000000)
        self.uc.mem_write(p+24,raw+b'\0');return p+24

    def hook(self,uc,at,size,data):
        if at==0x1de8970:
            # Explicit standard-library string storage; never a name/model or
            # resource acquisition success, and never SourcePhysics.filename.
            length=self.get('X2');raw=bytes(uc.mem_read(self.get('X1'),length))
            value=self.string(raw.decode());self.w(self.get('X0'),'Q',value)
            self.set('PC',self.get('X30'));return
        if self.imports.get(at)=='_ZNSt6vectorIfSaIfEEaSERKS1_':
            a,b=self.get('X0'),self.get('X1')
            if self.r(a,'3Q')!=(0,0,0) or self.r(b,'3Q')!=(0,0,0):
                raise ValueError('Only original empty, lazily unparsed rectangle vectors are hosted')
            self.set('PC',self.get('X30'));return
        super().hook(uc,at,size,data)

    def boundary(self,uc,at,size,data):
        if self.phase=='outer-prefix' and at==0x5385e4:
            self.set('PC',self.EXIT);return
        if self.phase=='install' and at==0x538ff4:
            self.set('PC',self.EXIT);return
        if self.phase=='dispatch' and at==0x537714:
            self.frontier={'factory':hex(self.get('X8')),'parentCurrentStage':self.r(self.outer+0x40,'i')[0],
                'parentRequestedStage':self.r(self.outer+0x44,'i')[0],
                'worldModeAtFactoryBoundary':self.r(self.r(self.r(self.world+0x178,'Q')[0]+0x58,'Q')[0]+0x40,'i')[0],
                'factoryExecuted':False}
            self.set('PC',self.EXIT);return
        if self.phase=='renderer-prefix'and at==0x34d834:
            self.set('PC',self.EXIT);return
        if self.phase=='actual-catalog-query'and at==0x4c4e88:
            pointer=self.get('X22');self.selected_id=self.r(pointer,'I')[0]if pointer else None
            self.set('PC',self.EXIT);return
        if at==0xc99350:
            if self.table is None:raise ValueError('No explicit original parsed zone table')
            self.set('X0',self.table)
        elif at==0xc999e8:
            # Source rows are already in parsed storage. Real VFS/table reload
            # and locks are not executed by this explicit data boundary.
            self.set('W0',0)
        elif at==0xc99270:
            self.map_lookup_requests.append({'consumer':'original map-info handle request','mapInfoReadExecuted':False})
            self.set('X0',0)
        elif at==0xe8581c:
            self.labels.append(self.get('W0'));self.set('W0',0)
        elif at==0x1de9e8c:
            self.w(self.get('X0'),'Q',self.r(self.get('X1'),'Q')[0])
        else:return
        self.set('PC',self.get('X30'))

    def source_table(self,table):
        """Explicit parsed std::map layout. Native traversal remains native."""
        self.table=self.alloc(0x70);head=self.table+0x30
        runtime_size=sum(8 if k=='s'else 4 for k in table['physicalTypes'])
        if runtime_size!=0x164:raise ValueError('Original serialized zone layout changed')
        nodes=[]
        for row in sorted(table['rows'],key=lambda r:r['ID']):
            # Original row objects also own lazily computed polygon vectors
            # after the serialized fields. Run their real constructor instead
            # of reading past a short FTABLE-only allocation.
            p=self.alloc(0x24+0x1f0);self.w(p,'I',1);self.w(p+0x20,'I',row['ID'])
            self.call(0x4c0a18,{'X0':p+0x24})
            at=p+0x24
            for key,kind in zip(table['columns'],table['physicalTypes']):
                value=row[key]
                if kind=='s':self.w(at,'Q',self.string(value));at+=8
                elif kind=='f':self.w(at,'f',value);at+=4
                else:self.w(at,'I',value&0xffffffff);at+=4
            nodes.append(p)
        def tree(lo,hi,parent):
            if lo>=hi:return 0
            middle=(lo+hi)//2;p=nodes[middle];self.w(p+8,'Q',parent)
            self.w(p+0x10,'2Q',tree(lo,middle,p),tree(middle+1,hi,p));return p
        root=tree(0,len(nodes),head);self.w(head,'I',0)
        self.w(head+8,'3Q',root,nodes[0],nodes[-1]);self.w(head+0x20,'Q',len(nodes))
        return {'sourceRows':len(nodes),'layout':'explicit parsed FTABLE and ordered tree storage','originalFTABLEParserExecuted':False}

    def startup_dispatch(self,requested_stage=1):
        self.machine=self.alloc(0x70);self.call(0x538dac,{'X0':self.machine})
        initial=self.r(self.machine+0x58,'Q')[0]
        self.w(self.world+0x178,'Q',self.machine)
        self.outer=self.alloc(0x70);self.phase='outer-prefix'
        self.call(0x538570,{'X0':self.outer})
        self.phase=None
        self.call(0x5388bc,{'X0':self.outer})
        self.phase='install';self.call(0x538f50,{'X0':self.machine,'X1':self.outer})
        installed=self.r(self.machine+0x58,'Q')[0]==self.outer
        self.phase=None
        # Requested stage is an explicit dispatcher input. The registry and
        # current-stage assignment are executed original code, not supplied.
        self.w(self.outer+0x44,'i',requested_stage)
        self.phase='dispatch';self.call(0x537608,{'X0':self.outer})
        self.phase=None
        return {'initialCurrentStateNull':initial==0,'outerInstalledByOriginalFunction':installed,
            'requestedStageInput':requested_stage,**self.frontier,
            'originalRegistryExecuted':True,'originalDispatcherExecuted':True,
            'loginApprovalTriggerExecuted':False,'scope':'Original branch leading to factory1, not original account login success'}

    def catalog_and_queues(self,table,*,prior_target=True):
        from unicorn import UC_HOOK_MEM_WRITE
        storage=self.source_table(table)
        self.manager=self.alloc(0x568);self.call(0x4c06ec,{'X0':self.manager})
        env=self.r(self.manager+0xc0,'Q')[0]
        if not env:raise ValueError('Original environment constructor did not produce owned state')
        self.env=env
        if prior_target:
            vector=self.alloc(12);self.w(vector,'3f',.25,.5,.75)
            self.call(0x4c48e4,{'X0':env,'X1':vector,'W2':2000})
        first=self.r(env+0x10,'Q')[0]
        if prior_target and first==env+0x10:raise ValueError('Original queued target fixture was not constructed')
        before=bytes(self.uc.mem_read(env,0x270));node_before=bytes(self.uc.mem_read(first,48))
        info_before=self.r(self.world+0x278,'I')[0]
        self.call(0x4d7c04,{'X0':self.world,'W1':7})
        map7=self.r(self.world+0x278,'I')[0]
        writes=[]
        def watch(uc,access,address,size,value,user_data):writes.append({'address':hex(address),'bytes':size})
        h=self.uc.hook_add(UC_HOOK_MEM_WRITE,watch,begin=env,end=env+0x26f)
        try:self.call(0x4c1ac4,{'X0':self.manager},limit=2000000)
        finally:self.uc.hook_del(h)
        start,end=self.r(self.manager+0x58,'2Q')
        rows=[self.r(self.r(p,'Q')[0],'I')[0]for p in range(start,end,8)]
        after=bytes(self.uc.mem_read(env,0x270));node_after=bytes(self.uc.mem_read(first,48))
        return {'parsedTable':storage,'mapBefore':info_before,'mapAfter':map7,'nativeCatalogIds':rows,
            'originalMapSetterExecuted':True,'originalCatalogRebuildExecuted':True,
            'originalDerivedCatalogPostprocessExecuted':True,'labelLookupBoundaryIds':self.labels,
            'environmentObjectSame':self.r(self.manager+0xc0,'Q')[0]==env,
            'environmentBytesUnchanged':before==after,'queuedTargetBytesUnchanged':node_before==node_after,
            'environmentWrites':writes,'queueExistsAfterRebuild':first!=env+0x10 and self.r(env+0x10,'Q')[0]==first,
            'priorTargetSupplied':prior_target,
            'mapInfoRequests':self.map_lookup_requests,
            'queueResetByTheseTwoFunctions':False,'scope':'Original full source-table traversal with explicit parsed storage; not table I/O or Android execution'}

    def fresh_producers(self,table,region):
        from scene_active_lighting import CHANNELS,NativeTargetProbe
        from scene_environment_state import EnvironmentValue,sample
        from native_temple_ambient import TempleAmbientProbe
        queues=self.catalog_and_queues(table,prior_target=False)
        native_initial={name:EnvironmentValue(list(self.r(self.env+offset,str(dim)+'f')))
                        for name,(offset,dim)in CHANNELS.items()}
        point=self.alloc(12);self.w(point,'3f',-2559.42,140.26,-16.42)
        self.phase='actual-catalog-query';self.call(0x4c4de4,{'X0':self.manager,'X1':point});self.phase=None
        if self.selected_id!=211:raise ValueError('Real rebuilt source catalog did not choose211')
        actual_mode=self.r(self.outer+0x40,'i')[0]
        state=NativeTargetProbe(self.image).run(native_initial,region,None,actual_mode)
        current=sample(state)
        if any(current['queueLengths'].values()):raise ValueError('Original mode1 did not write immediate source targets')
        # Original renderer initialization explicitly clears these fields. Dirty
        # the allocation first so the result cannot come from zero-filled BSS.
        renderer=self.alloc(0xb8);self.uc.mem_write(renderer,b'\xff'*0xb8)
        self.phase='renderer-prefix';self.call(0x34d7fc,{'X0':renderer,'X1':0});self.phase=None
        adds=list(self.r(renderer+0xa0,'2f'))
        weather=self.alloc(0x70);self.uc.mem_write(weather,b'\xff'*0x70)
        self.call(0x36ea38,{'X0':weather});weather_before=list(self.r(weather,'18I'))
        self.w(self.world+0x1c0,'Q',renderer);self.w(self.world+0x288,'Q',weather)
        self.call(0x36fa6c,{'X0':weather,'W1':region['weather'],'W2':int(region['weather_extra'])})
        weather_after=list(self.r(weather,'18I'))
        if adds!=[0.,0.] or weather_before!=[0]*18 or weather_after!=[0]*18:
            raise ValueError('Fresh original renderer/weather values differ')
        intensities={name:values[0]for name,values in current['values'].items()if name.startswith('intensity_')or name=='model_intensity_lightMap'}
        rgb=TempleAmbientProbe(self.image).produce(region['light_ambient'],region['light_diffuse'],intensities,adds=adds)
        if rgb['submitted']['light_model_lightMap']!=current['modelLightBeforeRuntimeRGBAdds']:
            raise ValueError('Fresh original renderer RGB differs')
        return {'worldModeFromOriginalDispatch':actual_mode,'durationMs':0,'catalog':queues,
            'selectedBaseIdFromOriginalRebuiltCatalog':self.selected_id,'initialValuesFromOriginalConstructor':sample(native_initial),
            'immediateValuesFromOriginalTargetWriter':current,
            'rendererRGBAddsFromOriginalConstructor':adds,
            'weatherFirst72BytesBeforeRequest':weather_before,'weatherFirst72BytesAfterOriginalZeroRequest':weather_after,
            'sourceWeatherId':region['weather'],'sourceWeatherExtra':int(region['weather_extra']),
            'nativeRGB':rgb,'freshStartOnly':True,'interveningWorldFramesSimulated':False,
            'sourceConditions':['new original environment, renderer and weather objects','normal selection factory1 dispatcher branch',
                'original APK_Default profile without saved/debug overrides','no intervening played world/flash history'],
            'fieldInputsReadyForConditionalFreshStart':True,'originalCompleteFrameOrGPUClaimed':False}


def investigate(image):
    source=Sources(DEFAULT_SOURCE);raw=source.read('tables/zones.tbl')
    if hashlib.sha256(raw).hexdigest()!=ZONE_SHA256:raise ValueError('Original zone table changed')
    table=decode_ftable(raw,'ID')
    probe=UpstreamProbe(image);dispatch=probe.startup_dispatch(1)
    if dispatch['factory']!='0x54b2a8'or dispatch['worldModeAtFactoryBoundary']!=1:
        raise ValueError('Original source selection factory/stage differs')
    queues=probe.catalog_and_queues(table)
    if queues['nativeCatalogIds']!=[211,422,453,463]or not queues['environmentBytesUnchanged']or not queues['queuedTargetBytesUnchanged']:
        raise ValueError('Original map7 catalog or preservation differs')
    fresh_probe=UpstreamProbe(image);fresh_probe.startup_dispatch(1)
    region,=[r for r in table['rows']if r['ID']==211]
    fresh=fresh_probe.fresh_producers(table,region)
    return {'format':FORMAT,'sourceNativeSHA256':hashlib.sha256(image.data).hexdigest(),
        'sourceZoneSHA256':ZONE_SHA256,'dispatch':dispatch,'mapAndQueues':queues,
        'normalSelectionBranchMode':1,'normalSelectionBranchDurationMs':0,
        'priorQueueAutomaticallyCleared':False,'completeOriginalStartupExecuted':False,'freshStart':fresh,
        'remaining':['Source login approval/next-stage request1 trigger is not executed here; this proves the original dispatcher branch when it creates selection.',
            'Fresh environment is initialized by original4c06ec/4be824, but full prior startup frame history is not yet traced.',
            'Renderer RGB additions, first upload gate and runtime fog settings still need their startup producers.',
            'Returning from an already played world retains queue state across these two calls; do not reuse fresh-start assumptions.'],
        'previewChanged':False,'savesChanged':False,'GPUCreated':False}


def fresh_inputs(upstream,environment_evidence):
    """Source field bridge for a named fresh-start branch, never a reentry."""
    if upstream.get('format')!=FORMAT or upstream.get('freshStart',{}).get('worldModeFromOriginalDispatch')!=1:
        raise ValueError('Original fresh-start mode not established')
    if environment_evidence.get('region',{}).get('ID')!=211:
        raise ValueError('Wrong original environment region')
    fresh=upstream['freshStart'];v=fresh['immediateValuesFromOriginalTargetWriter'];rgb=fresh['nativeRGB']['submitted']
    fog=environment_evidence['fog']['native']
    return {'format':'oc2-selection-environment-fresh-inputs-v1','world':'selection','mapId':7,'sourceSelectionRegion':211,
        'freshStartOnly':True,'fieldInputsReady':True,'actualAndroidFrameOrGPUObserved':False,
        'sourceConditions':fresh['sourceConditions'],'reentrySupported':False,'skyActivated':False,'bloomActivated':False,
        'uniformInputs':{'sourceModelLight':rgb['light_model_lightMap'],'sourceTerrainLight':rgb['light_lightMap'],
            'sourceToneDistance':v['toneDistanceUniform'],'sourceToneNear':v['values']['toneGainNear'],
            'sourceToneFar':v['values']['toneGainFar'],'sourceToneOffsetNear':v['values']['toneOffsetNear'],
            'sourceToneOffsetFar':v['values']['toneOffsetFar'],'sourceFogNear':fog['near'],'sourceFogSpan':fog['halfSpan'],
            'sourceFogColor':fog['color']},
        'sourceCharacterLight':{'ambient':rgb['light_ambient_char'],'diffuse':rgb['light_diffuse_char'],'specular':rgb['light_specular_char']},
        'fogConfiguration':environment_evidence['fog']['apkBaseline'],
        'scope':'Original conditional fresh-start field values for browser uniform transport; no invented light objects or hand-tuned RGB/fog.'}


if __name__=='__main__':
    from analyze_native_resources import NativeImage
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);a=parser.parse_args()
    out=local_output(a.output)
    if out.exists():raise ValueError('Use a fresh evidence filename')
    result=investigate(NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes()))
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    original_environment=json.loads((ROOT/'analysis/raw/selection-scene-environment-20261115/v3/evidence.json').read_text())
    inputs=fresh_inputs(result,original_environment)
    out.with_name(out.stem+'-fresh-inputs.json').write_text(json.dumps(inputs,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'worldMode':result['normalSelectionBranchMode'],'duration':result['normalSelectionBranchDurationMs'],
        'sourceCatalog':result['mapAndQueues']['nativeCatalogIds'],'oldQueuePreserved':result['mapAndQueues']['queuedTargetBytesUnchanged'],'previewChanged':False}))
