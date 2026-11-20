"""Original object interaction cache/qualification -> original NPC wheel events.

Wire packets, async model completion and hero UI gates remain explicit inputs.
The source does not prove any live 739 GUID, original server interaction, or quest.
"""
import argparse
import hashlib
import json
from pathlib import Path
from tutorial_quest_request_probe import fixture_integer,wire_fields
from tutorial_map_geometry import local_output

INTERACTIVE_DESCRIPTOR=(0x202aae6,139,'dfe133a7e6aa5746f8604eb7fde9a1b3399ca147098f11055587449ba2cca17d')
ROUTINES={10717908: (200, '0e614ae606472bb6da4439ae2533011eef05dccca8982520ae6adfd7ed84f86e'), 9544612: (100, 'd1667a615df7cb8a897cc78be5babe05e50e7293e1b3f64cb983b26472f6bda7'), 9544712: (308, '42d0e1f0586a87cf8ba2ffb59890891044d69746503b2ca3b2026a2cb359a4a1'), 9546740: (168, '7e1f412199ca49f4db04eb4d95dc72ac104a6c70dc4016170b768703f473ffc4'), 9550856: (168, 'dd46f22f155c56e4a7a4d8826ce2d6e7c621985b9172d5173644b8c86fb03d73'), 10839892: (388, '8860d8e1e40cd62be0e492c383479d2fd70f53c14076c48e5754e66dad002047'), 9546244: (348, '4ba7c3e811d581ab2bb05e07ad16c79e0be46b68c95aeddb5b168d679f7d1e06'), 9544512: (68, '37d5517ad3f30814ef01ef4710d1c7c613822d14e1054c9b8a13bd9561b367c1'), 10500296: (628, '72af2b027a40e6ebab0ba7d4fa529e10860aaee2d6e5b6a59b56c9b123a939a3'), 6572208: (1052, 'c8478d032d73a174eb34803cc77ea74074caf795eb4709bf0aa50f720c1e3b75')}


def _varint(value):
    out=bytearray()
    while value>127:out.append(value&127|128);value>>=7
    return bytes(out)+bytes([value])


def _nested(number,raw):return _varint(number<<3|2)+_varint(len(raw))+raw


def add_interaction_fixture(raw,entries,*,quest_status=None,quest_type=None):
    """Append explicit original schema fields to one ObjectStaticObj fixture."""
    if not isinstance(raw,bytes)or len(raw)>16384 or type(entries)is not list or len(entries)>32:raise ValueError('Bounded ObjectCreate/interactives fixture required')
    required={'quest_id','quest_type','quest_interact_type'};optional={'interact_id','instant_quest_first'}
    extra=b''
    for row in entries:
        if type(row)is not dict or not required<=row.keys()or row.keys()-required-optional:raise ValueError('Original interactive fields required')
        child=b''
        for n,key in enumerate(['quest_id','quest_type','quest_interact_type','interact_id','instant_quest_first'],1):
            if key not in row:continue
            value=row[key]
            if n==5:
                if type(value)is not bool:raise ValueError('Explicit instant_quest_first bool required')
                value=int(value)
            else:fixture_integer(value,32,key,signed=True);value&=(1<<64)-1
            child+=_varint(n<<3)+_varint(value)
        extra+=_nested(6,child)
    for number,value in [(12,quest_status),(13,quest_type)]:
        if value is not None:fixture_integer(value,32,'quest_field',signed=True);extra+=_varint(number<<3)+_varint(value&((1<<64)-1))
    parts=[value for n,w,value,_ in wire_fields(raw)if n==7 and w==2]
    if len(parts)!=1 or not raw.endswith(_nested(7,parts[0])):raise ValueError('One final source StaticObject field required')
    return raw[:-len(_nested(7,parts[0]))]+_nested(7,parts[0]+extra)


def native_probe_type():
    """Lazy native dependencies let public fixture-boundary checks run alone."""
    from tutorial_elevator_admission_probe import ElevatorAdmissionProbe
    class StaticWheelProbe(ElevatorAdmissionProbe):
        MASK=ElevatorAdmissionProbe.EXIT+0xd00
        SCRATCH=MASK+4
        HERO_GATE=MASK+8
        DISPATCH=MASK+12

        def __init__(self,image):
            self.cache_enabled=False;self.wheel_active=False;self.event_properties={};self.event_pointer=None
            self.events=[];self.visibility=[];self.marker_boundaries=[];self.hero_gate_fixture=False
            for address,(size,digest)in ROUTINES.items():
                if hashlib.sha256(image.read(address,size)).hexdigest()!=digest:raise ValueError('Original wheel/qualification routine differs')
            at,n,sha=INTERACTIVE_DESCRIPTOR
            if hashlib.sha256(image.read(at,n)).hexdigest()!=sha:raise ValueError('Original QuestInteractiveInfo descriptor differs')
            super().__init__(image)
            from unicorn import UC_HOOK_CODE
            for a in [0xa38ad4,0xa56edc,0xa038c8,0x6448b0,0x60ae50,0xfc2b30,0xfc6148,0x10387f8,0x1036890,0xfbfebc,0x3de09c,0x64b928,self.SCRATCH,self.HERO_GATE,self.DISPATCH]:self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=a,end=a)
            self.ui_hero=self.alloc(0x1800);hv=self.alloc(0x500);self.w(self.ui_hero,'Q',hv)
            attrs=self.alloc(0x2000);self.w(self.ui_hero+0x18,'Q',attrs)
            self.w(hv+0x488,'Q',self.SCRATCH);self.w(hv+0x1e8,'Q',self.HERO_GATE)
            self.ui_dispatcher=self.alloc(0x100);vt=self.alloc(0x100);self.w(self.ui_dispatcher,'Q',vt);self.w(vt+0x40,'Q',self.DISPATCH)

        def hook(self,uc,a,n,data):
            if a==0xa38ad4 and self.cache_enabled:return # execute source body, replacing parent's earlier boundary
            if a==0xa56edc:
                self.marker_boundaries.append('original quest/head marker refresh boundary');self.set('PC',self.get('X30'));return
            if not self.wheel_active:return super().hook(uc,a,n,data)
            if a==0xa038c8:return
            if a==0x6448b0:self.event_properties={};self.event_pointer=self.get('X0');return
            if a==0xfc2b30:
                count=self.get('W1')
                if not 0<count<=256:raise ValueError('Unbounded original AS key')
                if count>22:self.w(self.get('X0'),'B',255);self.w(self.get('X0')+16,'Q',self.alloc(count+1))
            elif a==0xfc6148:
                raw=self.cstr(self.get('X2'))
                if len(raw)>255:raise ValueError('Unbounded original AS property')
                uc.mem_write(self.get('X0'),raw+b'\0')
            elif a==0x10387f8:self.w(self.get('X0'),'B',3);self.w(self.get('X0')+8,'Q',self.get('X1'))
            elif a==0x60ae50:
                p=self.get('X1');p=self.r(p+16,'Q')[0]if self.r(p,'B')[0]==255 else p+1;key=self.cstr(p).decode();v=self.get('X2');typ=self.r(v,'B')[0]
                value=bool(self.r(v+8,'B')[0])if typ==1 else self.r(v+8,'d')[0]if typ==2 else self.cstr(self.r(v+8,'Q')[0]).decode()if typ==3 else None
                if value is None:raise ValueError('Unsupported source event AS value')
                self.event_properties[key]=value
            elif a in (0x1036890,0xfbfebc,self.SCRATCH):pass
            elif a==self.HERO_GATE:self.set('W0',int(self.hero_gate_fixture))
            elif a==0x3de09c:self.set('X0',self.ui_dispatcher)
            elif a==self.DISPATCH:
                if self.get('X1')==self.event_pointer:self.events.append(dict(self.event_properties));self.event_pointer=None
            elif a==0x64b928:self.visibility.append({'window':self.cstr(self.get('X1')).decode(),'show':bool(self.get('W2'))})
            elif (self.imports.get(a)or'').startswith('_ZNSt6vectorISs')and'_M_emplace_back_aux'in self.imports[a]:
                vec=self.get('X0');b,e,c=self.r(vec,'3Q')
                if b!=e:raise ValueError('Source wheel target vector exceeds one element')
                at=self.alloc(8);self.w(at,'Q',self.r(self.get('X1'),'Q')[0]);self.w(vec,'3Q',at,at+8,at+8)
            elif a==0x39e034:pass # event destruction at browser/AS storage boundary
            else:return super().hook(uc,a,n,data)
            self.set('PC',self.get('X30'))

        def prepare_interactive_fixture(self,raw):
            if self.lift:raise ValueError('One packet/model completion per independent probe')
            packet=self.parse_packet(raw);self.cache_enabled=True
            try:model=self.prepare_model_completion_boundary()
            finally:self.cache_enabled=False
            return {'packet':packet,'modelCompletionBoundary':model,'cache':self.interaction_cache()}

        def interaction_cache(self):
            if not self.lift:raise ValueError('Original parsed/prepared actor required')
            a=self.lift['actor'];begin,end,capacity=self.r(a+0x5e8,'3Q')
            if not begin<=end<=capacity or(end-begin)%8 or end-begin>256:raise ValueError('Unbounded original interaction vector')
            rows=[]
            for p in range(begin,end,8):
                q=self.r(p,'Q')[0];v=self.r(q,'4i')
                rows.append(dict(zip(['quest_id','quest_type','quest_interact_type','interact_id'],v),instant_quest_first=bool(self.r(q+16,'B')[0])))
            return {'interactives':rows,'quest_status':self.r(a+0xc4,'i')[0],'quest_type':self.r(a+0x600,'i')[0],'wrapperFlag14':self.r(self.model_wrapper+0x14,'B')[0],'markerRefreshBoundaries':list(self.marker_boundaries)}

        def qualify_and_emit(self,*,hero_v1e8_fixture=False):
            if type(hero_v1e8_fixture)is not bool:raise ValueError('Explicit hero v+1e8 fixture bool required')
            a=self.lift['actor'];self.hero_gate_fixture=hero_v1e8_fixture
            cache=self.interaction_cache();props=self.r(a+0x18,'Q')[0]
            cache['qualificationInputs']={'kind':self.call(0xa996a0,{'X0':props}),'kind12Flags':self.call(0xa996a0,{'X0':props+0x30}),'ownerField8':self.call(0xa996a0,{'X0':props+8}),'actorFlag4c':self.r(a+0x4c,'B')[0],'chatMenuPresent':bool(self.r(a+0xb00,'Q')[0])}
            original_mask=self.call(0x91abf4,{'X0':a})
            generic=self.call(0x91a340,{'X0':a});wrapper=self.call(0x91bc08,{'X0':a})
            self.events=[];self.visibility=[];self.event_pointer=None;self.wheel_active=True
            try:self.call(0xa038c8,{'X0':self.ui_hero,'X1':a})
            finally:self.wheel_active=False
            return {'cache':cache,'originalMask':original_mask,'originalGenericInteraction':bool(generic&1),'originalWrapperGate':bool(wrapper&1),'events':list(self.events),'visibility':list(self.visibility),
                    'heroV1e8Fixture':hero_v1e8_fixture,'nativeCacheQualificationMapperAndEventConstructorExecuted':True,
                    'boundaries':['Original packet values and async model-completion/node attachment are explicit fixtures; no live739 GUID or BDAE/GPU completion.','Hero v+488 scratch/v+1e8 result, AS property/vector storage, event dispatch/visibility and quest-marker refresh are host boundaries.'],
                    'nativeTargetSelectionExecuted':False,'nativeScreenProjectionExecuted':False,'originalServerResult':None,'acceptedQuestProduced':False,'productionUpdated':False}

        def gate_fixture(self,*,wrapper_flag14=None,kind12_flags=None):
            if wrapper_flag14 is not None:
                if type(wrapper_flag14)is not bool:raise ValueError('Explicit wrapper byte gate fixture required')
                self.w(self.model_wrapper+0x14,'B',int(wrapper_flag14))
            if kind12_flags is not None:
                fixture_integer(kind12_flags,32,'kind12_flags');props=self.r(self.lift['actor']+0x18,'Q')[0]
                self.call(0xa9995c,{'X0':props+0x30,'W1':kind12_flags})
    return StaticWheelProbe


def main():
    from analyze_native_resources import NativeImage
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--library',type=Path,required=True);cli.add_argument('--packet',type=Path,required=True);cli.add_argument('--output',type=Path,required=True);args=cli.parse_args();out=local_output(args.output)
    e=native_probe_type()(NativeImage(args.library.read_bytes()));prepared=e.prepare_interactive_fixture(args.packet.read_bytes());r={'format':'oc2-original-object-wheel-fixture-v1','prepared':prepared,'wheel':e.qualify_and_emit()}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({'events':len(r['wheel']['events']),'mask':r['wheel']['originalMask'],'acceptedQuestProduced':False,'output':str(out)}))
if __name__=='__main__':main()
