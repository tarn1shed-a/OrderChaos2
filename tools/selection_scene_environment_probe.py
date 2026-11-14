"""Original map7 selection environment inputs, without changing the preview.

Original caller/routing/region comparison and light/fog arithmetic execute in
isolated ARM64 probes. Parsed source rows and absent actor/history are explicit
inputs. Unknown live mode, upload and RGB history never become invented values.
"""
import argparse
import configparser
import copy
import hashlib
import json
import struct
import zipfile
from pathlib import Path

from map_loading_evidence import Sources, NATIVE_SHA256
from map_selection_evidence import DEFAULT_APK
from resource_packs import DEFAULT_SOURCE
from selection_scene_candidate import ROOT, local_output, splash_configs
from scene_zone_selection import ZoneCatalog, ZoneRefresh, verify_native as verify_catalog
from scene_lighting import ZONE_SHA256, check_zone_layout, zone_targets, f32
from scene_active_lighting import NativeTargetProbe, state_record
from scene_environment_state import initial_environment, apply_zone_targets, sample
from default_environment import NativeDefaultFogProbe, fog_target
from skill_attachments import decode_ftable
from source_physics import SourcePhysics

FORMAT='oc2-selection-scene-environment-evidence-v1'
INPUT_FORMAT='oc2-selection-scene-environment-inputs-v1'
PINS={
 0x53ba74:(8,'61e9af8d621aacd105f923f91bc93c0e2d4ac943e9c2a3f214d4dfdfc3410ee5'),
 0x53bc78:(32,'cbf79c73274b3a5c3c377f7bde61533e971a5879c0c32f86ac5ebef2344d926b'),
 0x4c4e04:(132,'d93fa56fa07ff1b38d60505b8905f4d784fb1e4d99774c9b5f643f7d2bcefbe7'),
 0x4c89bc:(20,'6b1fecb55b052c164514956e7c6b8e24bc9164905b3ca97c58e5644313887a66'),
}


def verify(image):
    if hashlib.sha256(image.data).hexdigest()!=NATIVE_SHA256:
        raise ValueError('Wrong original client image')
    verify_catalog(image)
    for at,(size,digest)in PINS.items():
        if hashlib.sha256(image.read(at,size)).hexdigest()!=digest:
            raise ValueError('Original selection environment caller/query changed')
    reloc={r['r_offset']:r['r_addend']for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()if r['r_info_type']==1027}
    if reloc.get(0x2506870)!=0x252773c or reloc.get(0x25069f8)!=0x250b848:
        raise ValueError('Original camera/fog source pointer changed')


class SelectionEnvironmentProbe(SourcePhysics):
    """Original bounded caller, base selection and refresh, not a full game."""
    def __init__(self,image):
        verify(image);super().__init__(image)
        from unicorn import UC_HOOK_CODE
        self.mode=None;self.trace=[]
        for at in (0x4c1ac4,0x4c4cd0,0x53bc98,0x4c4e88,0x4c4de4,0x4c53f0,0x4c5550,0x4bf458):
            self.uc.hook_add(UC_HOOK_CODE,self.boundary,begin=at,end=at)

    def boundary(self,uc,at,size,data):
        if self.mode=='caller':
            if at==0x4c1ac4:
                self.trace.append({'entry':hex(at),'manager':self.get('X0'),'catalogRebuildRequested':True,'bodyExecuted':False})
            elif at==0x4c4cd0:
                self.trace.append({'entry':hex(at),'manager':self.get('X0'),'deltaMs':self.get('W1'),
                    'positionPointer':hex(self.get('X2')),'position':list(self.r(self.get('X2'),'3f')),
                    'forceFlags':self.get('W3'),'bodyExecutedSeparately':True})
            elif at==0x53bc98:self.set('PC',self.EXIT);return
            else:return
            self.set('PC',self.get('X30'));return
        if self.mode=='query' and at==0x4c4e88:
            self.chosen=self.get('X22');self.set('PC',self.EXIT);return
        if self.mode=='refresh' and at in(0x4c4de4,0x4c53f0,0x4c5550,0x4bf458):
            row={'entry':hex(at),'bodyExecuted':False}
            if at in(0x4c4de4,0x4c53f0):row['position']=list(self.r(self.get('X1'),'3f'))
            self.trace.append(row);self.set('PC',self.get('X30'));return

    def caller(self,position):
        self.trace=[];self.mode='caller';manager=self.alloc(0x200)
        self.w(0x2528e10,'Q',manager);self.w(0x252773c,'3f',*position)
        self.call(0x53bc78,{'X21':0x252773c})
        if len(self.trace)!=2:raise ValueError('Unexpected source caller trace')
        result=copy.deepcopy(self.trace);self.mode=None;return result

    def base_choice(self,rows,position):
        self.mode='query';manager=self.alloc(0x200);actor_manager=self.alloc(0x100)
        self.w(0x2528df8,'Q',actor_manager)
        pointers={}
        for row in rows:
            at=self.alloc(0x1f0);pointers[at]=row['ID']
            for offset,fmt,key in [(0,'I','ID'),(0x10,'I','phasing_id'),(0x14,'I','definition'),
                (0x20,'f','x'),(0x28,'f','z'),(0x30,'f','x1'),(0x38,'f','z1'),(0x40,'I','priority'),(0x154,'I','fly')]:
                self.w(at+offset,fmt,row[key]&0xffffffff if fmt=='I'else row[key])
        vector=self.alloc(max(8,8*len(rows)))
        for i,at in enumerate(pointers):self.w(vector+i*8,'Q',at)
        self.w(manager+0x58,'2Q',vector,vector+len(rows)*8)
        point=self.alloc(12);self.w(point,'3f',*position)
        self.call(0x4c4de4,{'X0':manager,'X1':point})
        if self.chosen and self.chosen not in pointers:raise ValueError('Original selector returned an unknown source row')
        self.mode=None
        return {'baseId':pointers.get(self.chosen),'originalPhaseRectanglePriorityExecuted':True,
                'catalogInput':'explicit source-filtered map7 base row pointers',
                'originalCatalogConstructionExecuted':False,'actorProvided':False,
                'stoppedBeforeCatalogMutationAndSideEffects':True}

    def refresh(self,position,delta_ms=0,force_flags=1,elapsed=1000,upload_enabled=False):
        if delta_ms!=0:
            raise ValueError('This exact entry fixture covers delta0; do not advance unconstructed environment queues')
        self.mode='refresh';self.trace=[];manager=self.alloc(0x200);env=self.alloc(0x300);actors=self.alloc(0x100)
        self.w(0x2528df8,'Q',actors);self.w(manager+0xb4,'I',elapsed);self.w(manager+0xc0,'Q',env)
        self.w(0x250a85c,'B',int(upload_enabled))
        point=self.alloc(12);self.w(point,'3f',*position)
        self.call(0x4c4cd0,{'X0':manager,'W1':delta_ms,'X2':point,'W3':force_flags})
        result={'trace':copy.deepcopy(self.trace),'elapsedAfter':self.r(manager+0xb4,'I')[0],
            'originalRefreshBodyExecuted':True,'actorProvided':False,'uploadEnabledInput':upload_enabled,
            'audioWeatherAndUploadAreRecordingBoundaries':True,'queueAdvanceExecuted':True}
        self.mode=None;return result


def apk_fog(image):
    from native_device_selection_probe import NativeDeviceSelectionProbe
    with zipfile.ZipFile(DEFAULT_APK)as z:raw=z.read('assets/GameOptions.json');options=json.loads(raw)
    values={};reader=NativeDeviceSelectionProbe(image)
    for group in('GPU','MEM'):values.update(dict(reader.updates(options['profiles'][group],'')))
    selected={k:values[k]for k in('CameraFarPlaneDis','EnableFogDistanceLimit','FogDisCoef')}
    if selected!={'CameraFarPlaneDis':240.,'EnableFogDistanceLimit':False,'FogDisCoef':1.}:
        raise ValueError('Original APK fog baseline changed')
    return {'source':'APK assets/GameOptions.json','sha256':hashlib.sha256(raw).hexdigest(),
            'values':selected,'savedAndRuntimeOverrideObserved':False}


def report(image,source_path=DEFAULT_SOURCE):
    source=Sources(source_path);configs=splash_configs(source)
    raw=source.read('tables/zones.tbl')
    if hashlib.sha256(raw).hexdigest()!=ZONE_SHA256:raise ValueError('Original zones changed')
    table=decode_ftable(raw,'ID');check_zone_layout(table)
    catalog=ZoneCatalog(table['rows'],7)
    if [r['ID']for r in catalog.base]!=[211,422,453,463]:raise ValueError('Map7 base catalog changed')
    children=[r for r in table['rows']if r['parent_ID']==211]
    if children:raise ValueError('Area211 now has child overlays')
    base,=[r for r in catalog.base if r['ID']==211]
    targets=zone_targets(base)
    original_config=configparser.ConfigParser(strict=False)
    original_config.read_string(source.read('conf/game.conf').decode('utf-8-sig'))
    character_position=[float(v)for v in original_config['splash']['characterPosition'].split(',')]
    probe=SelectionEnvironmentProbe(image);positions=[
        ('splash-camera',configs[0]['cameraPosition']),('splash-sceneCenter',configs[0]['sceneCenter']),
        ('source-characterPosition',character_position)]
    queries=[]
    for label,point in positions:
        native=probe.base_choice(catalog.base,point);oracle=catalog.select(point[0],point[2])
        expected=oracle['base']['ID']if oracle['base']else None
        if native['baseId']!=expected or expected!=211 or oracle['overlay']is not None:
            raise ValueError('Original selection point does not select area211')
        queries.append({'input':label,'position':point,**native,'overlayId':None})
    caller=probe.caller(positions[0][1]);refresh=probe.refresh(positions[0][1])
    clock=ZoneRefresh().tick(catalog,0,positions[0][1],force_flags=1)
    if caller[1]['deltaMs']!=0 or caller[1]['forceFlags']!=1 or caller[1]['positionPointer']!='0x252773c':
        raise ValueError('Original splash refresh arguments changed')
    target_probe=NativeTargetProbe(image);target_cases=[]
    for mode in(None,0,4):
        state=target_probe.run(initial_environment(),base,None,mode)
        expected=initial_environment();apply_zone_targets(expected,targets,2000 if mode==4 else 0)
        if state_record(state)!=state_record(expected):raise ValueError('Original area211 target writes differ')
        initial=sample(state)
        for value in state.values():value.advance(2000)
        target_cases.append({'explicitWorldMode':mode,'durationMs':2000 if mode==4 else 0,
            'initial':initial,'settled':sample(state),'native13TargetChannelsExecuted':True,
            'modeActualSourceValueProven':False,
            'settledEvaluation':'Previously verified queue numeric oracle after original target writes; not observed original elapsed frames'})
    if any(c['settled']!=target_cases[0]['settled']for c in target_cases):
        raise ValueError('Original conditional target branches do not settle to the same fields')
    from native_temple_ambient import TempleAmbientProbe
    rgb=TempleAmbientProbe(image).produce(base['light_ambient'],base['light_diffuse'],targets['intensities'],adds=(0.,0.))
    if rgb['submitted']['light_model_lightMap']!=target_cases[0]['settled']['modelLightBeforeRuntimeRGBAdds']:
        raise ValueError('Original renderer model RGB producer differs from target state')
    config=apk_fog(image);values=config['values'];fog=fog_target(base,None,far_plane=values['CameraFarPlaneDis'],coefficient=values['FogDisCoef'])
    native_fog=NativeDefaultFogProbe(image).run_fog(base,None,far_plane=values['CameraFarPlaneDis'],coefficient=values['FogDisCoef'])
    if native_fog!={k:fog[k]for k in native_fog}:raise ValueError('Original area211 fog block differs')
    # Source declaration is not a claim that a pre-existing weather controller
    # had no earlier flashes or that every runtime RGB writer was recovered.
    if base['weather']!=0 or base['weather_extra']!='0' or base['weather_festival']:
        raise ValueError('Area211 weather request branch changed')
    return {'format':FORMAT,'sourceNativeSHA256':NATIVE_SHA256,'sourceZoneSHA256':ZONE_SHA256,
        'world':'selection','mapId':7,'sourceCatalogIds':[r['ID']for r in catalog.base],
        'region':base,'directChildIds':[],'sourceSplashConfigs':configs,'queries':queries,
        'originalCaller':caller,'conditionalOriginalRefresh':refresh,'refreshOracle':clock,
        'targets':targets,'targetCases':target_cases,
        'nativeRGBBeforeRuntimeAdds':{'result':rgb,'suppliedRGBAdds':[0.,0.],
            'actualRuntimeAddsObserved':False,'scope':'Original settled region211 RGB producer at explicit zero additions; not proof of current weather/history'},
        'fog':{'apkBaseline':config,'targets':fog,'native':native_fog,
            'nativeCPU':True,'runtimeFarPlaneGlobal':'0x250b848','runtimeFarPlaneAndCoefficientObserved':False},
        'weather':{'sourceWeatherId':0,'sourceExtraMode':0,'festivalDeclaration':'','zoneRequestsNoWeatherEffect':True,
            'previousWeatherAndRendererRGBHistoryObserved':False},
        'sky':{'sourceModel':base['skybox'],'sourceHill':base['skybox_hill'],'activated':False},
        'bloom':{'sourceDecrease':base['bloom_color_decrease'],'sourceIntensity':base['bloom_intensity'],'activated':False},
        'unresolvedRuntimeInputs':['actor suspension guard on original refresh','world+178 -> +58 -> +40 mode for immediate versus2000ms targets',
            'prior environment queue/current values if re-entering selection','renderer RGB additions and previous weather history',
            'saved/debug/runtime fog settings and current far-plane global','environment uniform upload byte0x250a85c',
            'runtime area override/catalog replacement and original final Android frame'],
        'sourceProofs':source.proofs,'previewChanged':False,'savesChanged':False,'GPUCreated':False,
        'conclusion':'Original source map7 camera query selects base211 with no overlay. Settled source targets are derived; active timeline/uploads/history are not invented.'}


def export_inputs(evidence):
    """Minimal read-only handoff; this supplies targets, not a ready context."""
    if (evidence.get('format')!=FORMAT or evidence.get('mapId')!=7 or
        evidence.get('region',{}).get('ID')!=211 or evidence.get('directChildIds')!=[] or
        evidence.get('sourceZoneSHA256')!=ZONE_SHA256 or evidence.get('sourceNativeSHA256')!=NATIVE_SHA256):
        raise ValueError('Expected original map7 environment evidence')
    settled=evidence['targetCases'][0]['settled']
    return {'format':INPUT_FORMAT,'world':'selection','mapId':7,'sourceRegion':211,
        'selectionPoint':evidence['queries'][0]['position'],'sourceSelectionConditions':{
            'originalMapId':7,'sourceCatalogOnly':True,'actorNotSuspendedRequired':True,'noChildOverlay':True},
        'targets':evidence['targets'],'settledSourceStateBeforeRendererAdds':settled,
        'conditionalAPKDefaultFog':evidence['fog']['targets'],
        'originalRuntimeContextReady':False,'requiredRuntimeInputs':evidence['unresolvedRuntimeInputs'],
        'scope':'Source-only target inputs. No Three light, fog, sky, bloom or environment activation; caller must resolve or explicitly label runtime adaptation.'}


if __name__=='__main__':
    from analyze_native_resources import NativeImage
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--output',type=Path,required=True);a=cli.parse_args()
    output=local_output(a.output)
    if output.exists():raise ValueError('Use a fresh private evidence directory')
    evidence=report(NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes()))
    output.mkdir(parents=True)
    for name,data in [('evidence.json',evidence),('inputs.json',export_inputs(evidence))]:
        (output/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'mapId':7,'baseId':211,'overlayId':None,'nativeQueries':len(evidence['queries']),
        'runtimeContextReady':False,'fogNear':evidence['fog']['native']['near'],'fogHalf':evidence['fog']['native']['halfSpan'],'previewChanged':False}))
