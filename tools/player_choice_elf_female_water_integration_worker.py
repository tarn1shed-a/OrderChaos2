"""Derived opt-in same-actor air/water worker; frozen v7 source stays intact."""
import base64,hashlib,json,struct,sys
from pathlib import Path
from types import FunctionType
import player_choice_elf_female_air_integration_worker as frozen
from player_choice_elf_female_water_land_probe import advance_active_rotation_phase

PINS={
 'tools/player_choice_elf_female_air_integration_worker.py':'a77b68da1c694e3d8b13b4df747b980075f49ed8728bc9574387f2c24522d299',
 'tools/player_choice_elf_female_water_land_probe.py':'5d9a254cfb43ecf511e1c575ff7ff9f35d20b969e0e2de3a2395c27950726a69'}

class ElfFemaleWaterIntegration(frozen.ElfFemaleAirIntegration):
    def press_event(self,identity,pressed):
        if identity not in self.bindings or type(pressed)is not bool:raise ValueError('Known own input identity and Boolean edge required')
        changed=self.input_pressed[identity]!=pressed
        if changed:
            self.inputs.press(identity,pressed);self.input_pressed[identity]=pressed
        return{'identity':identity,'held':pressed,'edgeProduced':changed,'originalInputCallback':'0x65a34c'if changed else None,
            'counterFrameAlreadyAdvanced':False,'state':self.inputs.inspect(identity)}

    def tick_own(self,data):
        # Validate every parent-v7 input BEFORE advancing the new source phase.
        # Rejected packets cannot advance another actor's source timer.
        required={'identity','position','velocity','milliseconds','jump','control','eventOwner','timeval'}
        if not isinstance(data,dict)or set(data)!=required:raise ValueError('Complete explicit own actor tick required')
        identity=data['identity'];ms=data['milliseconds'];control=data['control'];tv=data['timeval']
        if identity not in self.bindings or type(ms)is not int or not 1<=ms<=1000 or not frozen.vector(data['velocity'],2)or not isinstance(control,dict)or set(control)!={'forward'}or type(control['forward'])is not bool:
            raise ValueError('Bound actor/source dt/forward input required')
        if any(data['velocity'])and not control['forward']:raise ValueError('Unrecovered side/back input remains refused')
        if type(data['jump'])is not bool or data['jump']!=self.input_pressed[identity]:raise ValueError('Tick held state must match its actual press/release producer')
        if data['eventOwner']not in('world','captured','inactive')or not isinstance(tv,(list,tuple))or len(tv)!=2 or any(type(v)is not int for v in tv)or not 0<=tv[0]<=0x7fffffff or not 0<=tv[1]<1000000:raise ValueError('Actual event owner and explicit source clock required')
        at=self.bindings[identity]['actor']['address'];current=list(self.r(at+0x118,'3f'))
        if not frozen.vector(data['position'],3)or struct.pack('<3f',*data['position'])!=struct.pack('<3f',*current):raise ValueError('Current authoritative source float32 position required')
        phase=advance_active_rotation_phase(self,identity,ms)
        result=super().tick_own(data);result['sourceActiveRotationPhase']=phase
        if self.qa_original_pose_evidence:
            # The real parent transport JSON.stringify normalizes audit -0.
            # Keep an independent packed copy of the ORIGINAL full property
            # list before that JSON hop. The gameplay thin packet is unchanged.
            audit=result['qaOriginalPoseEvidence'];values=[v for row in audit['properties']for v in row['value']]
            raw=struct.pack('<'+str(len(values))+'f',*values)
            audit['nativeFloat32LE']={'valueBytes':len(raw),'values':base64.b64encode(raw).decode(),'source':'full-original-composition-properties-before-JSON'}
        return result

def load(config):
    for name,digest in PINS.items():
        if hashlib.sha256((frozen.ROOT/name).read_bytes()).hexdigest()!=digest:raise ValueError('Frozen inherited source differs '+name)
    cfg=json.loads(Path(config).read_text())
    if cfg.get('format')!='oc2-model2-air-water-integration-v1'or cfg.get('sourceActiveRotationPhase')!='named-active-rotation-before-partial-tick-v1':raise ValueError('Explicit reviewed own active-timer phase configuration required')
    inherited=FunctionType(frozen.load.__code__,{**frozen.load.__globals__,'ElfFemaleAirIntegration':ElfFemaleWaterIntegration})
    engine,info=inherited(config)
    info.update(sourceInputEvents=['press','release'],sourceActiveRotationPhase='named-active-rotation-before-partial-tick-v1',
        fullHeroV20OrZeroTimerBranchClaimed=False,sourceHostForkUsesScopedIdentities=True)
    return engine,info

def start(config):
    e,info=load(config)
    for line in sys.stdin:
        try:
            q=json.loads(line);op=q['operation'];d=q.get('data',{})
            if op=='init':result=info
            elif op=='prepareOwnBody':
                if d!={'species':'elf-female'}:raise ValueError('Own Model2 preparation required')
                from player_choice_all_worker import resident_bytes
                result={'key':'elf-female','ready':True,'pose':{'field':frozen.FIELD,'bindingId':info[frozen.FIELD]['bindingId'],'valueBytes':1536},'milliseconds':e.preparation_milliseconds,'rssBytes':resident_bytes()}
            elif op=='ground':result=e.ground(*d['point'])
            elif op=='sample':result=e.sample(*d['point'])
            elif op=='ray':result=e.ray(d['from'],d['to'],d.get('capsule',False))
            elif op=='reset':
                if set(d)!={'identity','position','species','profession','equipment'}or d['species']!='elf-female':raise ValueError('Explicit own Model2 reset required')
                result=e.fresh_actor(d['identity'],d['position'],d['profession'],d['equipment'])
            elif op in('press','release'):
                if set(d)!={'identity'}:raise ValueError('Exact owned input event required')
                result=e.press_event(d['identity'],op=='press')
            elif op=='tick':result=e.tick_own(d)
            elif op=='forget':result=e.disconnect(d['identity'])
            elif op=='input-state':result=e.inputs.inspect(d['identity'])
            elif op=='water':result=e.water_state(d['identity'])
            else:raise ValueError('Unsupported own air/water stdin operation')
            print(json.dumps({'result':result},allow_nan=False,separators=(',',':')),flush=True)
        except Exception as error:print(json.dumps({'error':str(error)},ensure_ascii=False),flush=True)

if __name__=='__main__':start(sys.argv[1])
