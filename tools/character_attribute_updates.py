"""Original attribute-message parse and integer property-write probes.

Only explicit isolated actor/protocol fixtures are used. No character saves,
server connection, XP award, database or runtime deployment is accessed.
"""
import argparse
import bisect
import hashlib
import json
import struct
from pathlib import Path

from character_progression_evidence import local_output
from native_combat import descriptor_fields
from source_physics import SourcePhysics

ROOT=Path(__file__).resolve().parents[1]
FIELDS={'level':0x4d,'profession':0x7f,'xp':0x8a,'upgradeXp':0x8b,'skillPoints':0x91}
DESCRIPTORS={
    'GS2C_FullObjectValue':(0x2028ec0,62,'234cfe105e24fcefd8ce93dd94ac5cb211f8bc66a11215eb469f4e47e5c41020'),
    'GS2C_ObjectValueUpdate':(0x2028f00,78,'44c2ccd72c9353fb8d343460298fade787b20a02ce81a492cff8d2378ab292bd'),
    'GS2C_PlayerLevelUp':(0x202a934,70,'3ac48b83dbd19a3ce523eb1433abd743e2b1fbd4ce3f043747e360004f5f8c81'),
    'GS2C_ObjectCreate':(0x20297ec,361,'9b885cd9c85fe6ccc241c05531c773e0fda176de821eca3e351e4dda8c5b389f'),
    'GS2C_ObjectUpdate':(0x2029958,162,'e8835fb736da7408d10cd5225eb82a400420d56b0ec7c4d844137b1c1b13de3c'),
}
ROUTINES={
    0xa40760:(268,'32d790c67ac336ddbae8446997267f69799de8723a3d150ea65d6aba24919fdf'),
    0xa4086c:(588,'a3dc5920596e2673fccb6c0cd450dd7807acf055bcaf966222939295f511e299'),
    0xa390a4:(14052,'c4532dc5ef3da7a2b94a0aef035c45fee895ee0d5d9a77dc1263e5b5ff1ebe69'),
    0xa996a0:(40,'156f89d4de6aea1e301f013ab3cb7a62f74002c6770a4422e82e7b908cdd1956'),
    0xa996c8:(48,'0cd68d28f4d3d663fe480555bd67759a2e89e08162d6151e0479949a3705c436'),
    0xa999d4:(48,'317ad0b74981630784f7513bca2cb6148bebacb39f38700be4d52b12d2cf2dbd'),
    0xa9995c:(36,'89ddeb6e5870442a1b7406a8de9fb3563d8597bdbace6e19a07637d45c532342'),
    0x1bbd8c0:(68,'ca2679d9d92e7754bae64553756459f810083b56dfd6538fa27c72635582768e'),
    0x1bacaf8:(80,'2126eaba970ab7f9aa58bbeddd11c1f0b0960bd714c49756ea3240dbb0de0e1f'),
    0xa3f8b8:(136,'7a1c39c1824fb51550a8670e83f490a056d842ed4686d96b5d063a809bffef15'),
    0xa3700c:(6592,'38814d00a0b17a098751c2ce22665378951b08f3640374b5944d7b7756342d24'),
    0x589dd8:(32,'659ab7f2c424db7994a4501069d323ef6cd4100622519a77e0b9e2a7e36e8497'),
    0x58b3bc:(80,'02493cecb00890af5041db3ab6ccf7864e8e0d74b3ffdb5f98695ea606232340'),
    0x5809a8:(25108,'a01708e31abed7abbb85dee23a0c122b4cdc48255ed35f4c0f5b22dd4431c7c0'),
    0x1bbb94c:(64,'2c25da732b84fb5776637512deff498b7e73fe9ce88bfadb9c6e3af09759f472'),
    0x1ab7060:(660,'1551ba9b53a6ca7b563e1cc989bbdfef7199706317299b635edc5f2899a4281f'),
    0x668014:(7640,'b9d212b80a0a401faaddc9443a9241cb91b7542ca7e004df6eda62d1e5aa6fec'),
}


def varint(value,bits=64):
    if type(value)is not int or not 0<=value<(1<<bits):
        raise ValueError('Explicit bounded unsigned protocol fixture required')
    out=bytearray()
    while value>127:out.append((value&127)|128);value>>=7
    out.append(value);return bytes(out)


def int32(value):
    if type(value)is not int or not -(1<<31)<=value<(1<<31):
        raise ValueError('Explicit signed int32 protocol value required')
    return varint(value if value>=0 else(1<<64)+value)


def update_fixture(guid,changes,*,bit_count=None):
    if not isinstance(changes,dict) or any(type(i)is not int or not 0<=i<512 for i in changes):
        raise ValueError('Bounded explicit attribute-index map required')
    masks=[0]*((max(changes)//32)+1 if changes else 0)
    for index in changes:masks[index//32]|=1<<(index%32)
    count=len(masks)if bit_count is None else bit_count
    payload=b'\x08'+varint(count,32)
    payload+=b''.join(b'\x10'+varint(mask,32)for mask in masks)
    payload+=b''.join(b'\x18'+int32(changes[i])for i in sorted(changes))
    return b'\x08'+varint(guid)+b'\x12'+varint(len(payload))+payload


def full_fixture(guid,values,*,float_masks=()):
    if not isinstance(values,(list,tuple))or len(values)>512 or not isinstance(float_masks,(list,tuple))or len(float_masks)>16:
        raise ValueError('Bounded explicit full-value fixture required')
    payload=b''.join(b'\x08'+int32(v)for v in values)
    payload+=b''.join(b'\x10'+varint(mask,32)for mask in float_masks)
    return b'\x08'+varint(guid)+b'\x2a'+varint(len(payload))+payload


def source_attribute_view(snapshot=None):
    """Read-only candidate for an explicitly observed source attribute snapshot.

    No snapshot/absent individual fields stay unknown. A local prototype record
    is deliberately not accepted or converted from its cumulative xp/60 rule.
    """
    if snapshot is not None:
        if not isinstance(snapshot,dict)or any(type(i)is not int or not 0<=i<512 or type(v)is not int or not -(1<<31)<=v<(1<<31)for i,v in snapshot.items()):
            raise ValueError('Explicit original field-index/int32 snapshot required')
    return {'known':snapshot is not None,
            'fields':{name:None if snapshot is None else snapshot.get(index)for name,index in FIELDS.items()},
            'scope':'read-only original attribute projection; no XP award, threshold derivation, cumulative-XP conversion or save mutation'}


def audit_level_message(image):
    """Reproduce the bounded static search; absence is not a dead-code proof."""
    targets={0x1bda4f0:'constructor',0x1bda538:'copy-constructor',0x1bda72c:'new-instance',
             0x1bda794:'generated-parser',0x1bdaa68:'array-serializer'}
    direct=[];vtable_refs=[]
    for seg in image.elf.iter_segments():
        if seg['p_type']!='PT_LOAD'or not seg['p_flags']&1:continue
        raw=seg.data();base=seg['p_vaddr']
        for i,(word,)in enumerate(struct.iter_unpack('<I',raw[:len(raw)//4*4])):
            at=base+i*4
            if word>>26 in(0x25,0x5):
                delta=word&0x3ffffff
                if delta&(1<<25):delta-=1<<26
                target=at+delta*4
                if target in targets:
                    direct.append({'address':hex(at),'target':hex(target),'kind':targets[target],
                                   'fdeStart':hex(image.starts[bisect.bisect_right(image.starts,at)-1])})
            if word&0x9f000000!=0x90000000:continue
            immediate=(((word>>5)&0x7ffff)<<2)|((word>>29)&3)
            if immediate&(1<<20):immediate-=1<<21
            if (at&~4095)+(immediate<<12)!=0x24e3000:continue
            instructions=list(image.disassembler.disasm(image.read(at,32),at))
            if any('#0x330'in ins.op_str or '#0x340'in ins.op_str for ins in instructions):
                vtable_refs.append({'address':hex(at),'fdeStart':hex(image.starts[bisect.bisect_right(image.starts,at)-1]),
                                    'instructions':[ins.mnemonic+' '+ins.op_str for ins in instructions]})
    return {'targets':{hex(k):v for k,v in targets.items()},'directBranches':direct,
            'vtableAddressSequences':vtable_refs,'vtable':'0x24e3340','defaultInstance':'0x269ba68',
            'conclusion':'Dedicated transport registration/consumer not established; observed sequences are generated protobuf infrastructure. Indirect/generic dispatch and omitted analysis remain possible.'}


class CharacterAttributeProbe(SourcePhysics):
    # End the original update after the mask/value loop, before its UI/effects.
    UPDATE_STOPS=(0xa3b740,0xa3b7b0,0xa3bec4)
    FULL_START=0xa37958
    FULL_END=0xa37afc
    FULL_FIELD_SIDE_EFFECT=0xa379e8
    XP_DISPLAY_STOP=0x668814
    def __init__(self,image):
        for address,(size,expected)in ROUTINES.items():
            if hashlib.sha256(image.read(address,size)).hexdigest()!=expected:
                raise ValueError('Original attribute routine differs; retrace required')
        self.schema={}
        for name,(address,size,expected)in DESCRIPTORS.items():
            raw=image.read(address,size)
            if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('Original attribute descriptor differs')
            parsed=descriptor_fields(raw)
            if parsed['name']!=name:raise ValueError('Original attribute descriptor name differs')
            self.schema[name]=parsed
        self.mode=None;self.capturing=False
        super().__init__(image)
        from unicorn import UC_HOOK_CODE
        for address in (*self.UPDATE_STOPS,self.FULL_END,self.FULL_FIELD_SIDE_EFFECT,
                        self.XP_DISPLAY_STOP,0xa3700c,0xa407b4,0xa3f90c,0x41d470,0x908634,0xa9995c):
            self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=address,end=address)

    def hook(self,uc,address,size,data):
        if self.mode=='display'and address==self.XP_DISPLAY_STOP:
            value=self.get('W21')
            self.display_result={'xp':self.r(self.get('SP')+0xc,'i')[0],
                                 'upgradeXp':value-(1<<32)if value&(1<<31)else value,
                                 'level':self.get('W0')}
            self.set('PC',self.EXIT)
        elif self.mode=='update'and address in self.UPDATE_STOPS:
            if address==0xa3b740:
                sp=self.get('SP')
                self.core_flags={'levelChanged':bool(self.r(sp+0xbc,'I')[0]&1),
                                 'skillPointsChanged':bool(self.r(sp+0xb0,'I')[0]&1),
                                 'gaugesDirtyRequested':bool(self.r(sp+0x134,'I')[0]&1)}
            self.reached_core=True;self.set('PC',self.EXIT)
        elif self.mode=='full'and address==self.FULL_END:
            self.reached_core=True;self.set('PC',self.EXIT)
        elif self.mode=='full'and address==self.FULL_FIELD_SIDE_EFFECT:
            # Preserve source sequential writes/iteration, exclude per-field
            # model/appearance/table/UI side effects from this bounded slice.
            self.set('PC',0xa37aec)
        elif self.mode=='full'and address==0xa3700c:
            parsed=self.get('X1')
            if self.r(parsed+0x10,'Q')[0]!=self.guid:
                raise ValueError('Full-value probe requires the prepared actor GUID')
            self.set('X19',self.registry);self.set('X20',parsed);self.set('X21',self.actor)
            self.set('PC',self.FULL_START)
        elif address in (0xa407b4,0xa3f90c):
            self.parser_succeeded=bool(self.get('W0'))
        elif address==0x41d470:
            # Explicit empty interested-observer list, not an invented actor.
            self.set('X0',self.observers);self.set('PC',self.get('X30'))
        elif address==0x908634:
            self.set('X0',0);self.set('PC',self.get('X30'))
        elif address==0xa9995c:
            if self.capturing:
                offset=self.get('X0')-self.properties
                if offset%8 or not 0<=offset<512*8:raise ValueError('Unexpected source attribute write target')
                self.writes.append({'index':offset//8,'rawValue':self.get('W1')})
            # Original XOR/dual-copy store executes; do not replace its body.
        else:
            super().hook(uc,address,size,data)

    def actor_fixture(self,*,guid=0x120a00000001,initial=None):
        varint(guid)
        self.guid=guid;self.actor=self.alloc(0x1c00);self.properties=self.alloc(512*8)
        self.registry=self.alloc(0x200);self.observers=self.alloc(16)
        self.w(self.actor+8,'Q',guid);self.w(self.actor+0x18,'Q',self.properties)
        self.w(self.registry+0x68,'Q',self.actor);self.w(0x2528df8,'Q',self.registry)
        # Explicit process-key fixtures; the original getter/equality/setter
        # instructions apply both keys. No persistent Android state is claimed.
        self.w(0x2582f40,'2I',0x13579bdf,0x2468ace0)
        self.uc.mem_write(self.properties,struct.pack('<2I',0x13579bdf,0x2468ace0)*512)
        supplied={0:0x120a,FIELDS['level']:1,FIELDS['profession']:2,
                  FIELDS['xp']:0,FIELDS['upgradeXp']:2403,FIELDS['skillPoints']:0}
        supplied.update(initial or{})
        self.capturing=False
        for index,value in supplied.items():
            if type(index)is not int or not 0<=index<512 or type(value)is not int or not -(1<<31)<=value<(1<<32):
                raise ValueError('Invalid isolated actor property fixture')
            self.call(0xa9995c,{'X0':self.properties+index*8,'W1':value&0xffffffff},limit=100)
        return self.read_fields()

    def read_fields(self):
        # UI scvtf Wn and int32 protobuf values consume these raw bits as signed.
        result={}
        for name,index in FIELDS.items():
            value=self.call(0xa996a0,{'X0':self.properties+index*8},limit=100)&0xffffffff
            result[name]=value-(1<<32)if value&(1<<31)else value
        return result

    def xp_display(self):
        """Original getter slice reads actual updated dual-copy properties."""
        self.mode='display'
        self.call(0x668778,{'X27':self.actor},limit=1000)
        self.mode=None
        return dict(self.display_result)

    def receive(self,raw,*,kind='update',guid=0x120a00000001,initial=None):
        if kind not in('update','full')or not isinstance(raw,bytes)or len(raw)>16384:
            raise ValueError('Bounded explicit object-value packet fixture required')
        self.mode=None;before=self.actor_fixture(guid=guid,initial=initial)
        stream=self.alloc(0x40);data=self.alloc(len(raw)+4)
        self.w(data,'I',len(raw));self.uc.mem_write(data+4,raw)
        self.w(stream+0x10,'Q',0);self.w(stream+0x20,'2Q',data,data+len(raw)+4)
        self.mode=kind;self.parser_succeeded=None;self.reached_core=False;self.core_flags=None;self.writes=[];self.capturing=True
        self.call(0xa40760 if kind=='update'else 0xa3f8b8,{'X1':stream},limit=200000)
        self.capturing=False;self.mode=None
        after=self.read_fields()
        actor_type=self.call(0xa996a0,{'X0':self.properties},limit=100)&0xffffffff
        display=self.xp_display()
        return {'kind':kind,'fixtureGuid':hex(guid),'rawPayloadHex':raw.hex(),
                'parserSucceeded':self.parser_succeeded,'coreReached':self.reached_core,
                'before':before,'after':after,'sourceWrites':list(self.writes),
                'coreFlagsBeforePresentation':self.core_flags,
                'actorTypeField':actor_type,'sourceXPDisplay':display,
                'streamBytesConsumed':self.r(stream+0x10,'Q')[0],
                'scope':'original protobuf parse, attribute matching/mask or sequential integer writes, dual-copy XOR setter/getter; prepared actor/process-key/observer fixtures; stopped before presentation side effects',
                'fullActorFactoryExecuted':False,'liveServerOrSavesUsed':False}


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--library',type=Path,required=True);cli.add_argument('--output',type=Path,required=True)
    args=cli.parse_args()
    from analyze_native_resources import NativeImage
    probe=CharacterAttributeProbe(NativeImage(args.library.read_bytes()))
    guid=0x120a00000001
    changes={FIELDS['level']:2,FIELDS['xp']:17,FIELDS['upgradeXp']:4802,FIELDS['skillPoints']:1}
    values=[0]*146
    for index,value in changes.items():values[index]=value
    values[FIELDS['profession']]=2
    report={'schema':probe.schema,'update':probe.receive(update_fixture(guid,changes)),
            'full':probe.receive(full_fixture(guid,values),kind='full'),
            'wrongGuid':probe.receive(update_fixture(guid+1,changes))}
    report['xpOnlyAboveThreshold']=probe.receive(update_fixture(guid,{FIELDS['xp']:99999}))
    report['customIncomingThreshold']=probe.receive(update_fixture(guid,{FIELDS['upgradeXp']:12345}))
    report['levelMessageAudit']=audit_level_message(probe.image)
    report['registration']={'ObjectCreate':{'id':6,'registration':'0x580f4c..0x580f5c','handler':'0x589dd8 -> 0xa3f8b8'},
                            'ObjectUpdate':{'id':8,'registration':'0x581a50..0x581a60','handler':'0x58b3bc -> 0xa40760'},
                            'PlayerLevelUp':{'id':None,'handler':None,'status':'descriptor located; dedicated transport registration/consumer not established'}}
    out=local_output(args.output)/'attribute-updates-probe.json'
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'output':str(out),'serverOrSavesUsed':False}))


if __name__=='__main__':main()
