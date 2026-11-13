"""Execute original quest-button dispatch on explicit cached-state fixtures.

No quest is accepted, completed or rewarded by this tool. Original protobuf
payloads are captured at the transport boundary; no network or save is used.
"""
import argparse
import hashlib
import json
from pathlib import Path

from native_combat import descriptor_fields
from source_physics import SourcePhysics
from tutorial_map_geometry import local_output

DESCRIPTOR = (0x203f414, 0xf46,
              'ff9220aa6df9363586ce1debe190a61a1d06dd787b69dd6e26c4381a27b677a7')
ROUTINES = {
    0x49b828: (580, '54a917007274bc5c5d0c1d4f4b7e3011d4e63da282b3260de7d62fc84f5af6f7'),
    0x49dfe4: (1256, '7dceb8660dc480ff59f48878dd9b635ea0634f9f201a1b5ddbc3a07b763f062b'),
    0x65cb50: (168, 'ee361d6ffb54c2b5273c52af45823171ea41595d0fef895e3c1de41ec6c2de38'),
    0x1d28124: (60, 'a7b9b80ed21e54bd22e429772bf4f43c61959ae21579a2d4cbd980a1b6b41571'),
    0x1d332f8: (64, 'eed723bce0aeff4a13770f42a409391e3051c918e4894df04162a069f8a5304c'),
    0x1d28694: (208, '2fbb7c99ea8a3c66b609d245e596c5748b36524efad871c20479e5bf6b2f1ee0'),
    0x1d33aa0: (252, 'ab85167206bb7f7c42274540bc97e088c5729d37c23f4815cc720457cd448b17'),
}


def wire_fields(raw):
    """Bounded varint/length-field inspection for this pinned descriptor/payload."""
    if not isinstance(raw, bytes):
        raise ValueError('Quest wire inspection requires bytes')
    def varint(at):
        value = 0
        for shift in range(0, 70, 7):
            if at >= len(raw):
                raise ValueError('Truncated protobuf integer')
            byte = raw[at]; at += 1
            if shift == 63 and byte > 1:
                raise ValueError('Oversized protobuf integer')
            value |= (byte & 127) << shift
            if byte < 128:
                return value, at
        raise ValueError('Oversized protobuf integer')
    at = 0; rows = []
    while at < len(raw):
        tag, at = varint(at); number, wire = tag >> 3, tag & 7
        if not 1 <= number <= 0x1fffffff:
            raise ValueError('Invalid protobuf field number')
        if wire == 0:
            start = at; value, at = varint(at)
        elif wire == 2:
            size, at = varint(at); start = at
            if size > len(raw) - at:
                raise ValueError('Truncated protobuf span')
            value = raw[at:at+size]; at += size
        else:
            raise ValueError('Unsupported protobuf wire in quest inspection')
        rows.append((number, wire, value, start))
    return rows


def enum_descriptor(raw):
    """Preserve original names/numbers; these do not produce quest state."""
    fields = wire_fields(raw)
    names = [v for n,w,v,_ in fields if n == 1 and w == 2]
    if len(names) != 1:
        raise ValueError('Missing or duplicate quest enum name')
    values = {}
    for number, wire, value, _ in fields:
        if number != 2:
            continue
        parts = wire_fields(value)
        name = [v for n,w,v,_ in parts if n == 1 and w == 2]
        numeric = [v for n,w,v,_ in parts if n == 2 and w == 0]
        if len(name) != 1 or len(numeric) != 1 or name[0].decode() in values:
            raise ValueError('Invalid quest enum value')
        values[name[0].decode()] = numeric[0]
    return names[0].decode(), values


def quest_file_schema(image):
    address, size, digest = DESCRIPTOR; raw = image.read(address, size)
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError('Original Quest.proto descriptor differs')
    fields = wire_fields(raw)
    if [v for n,w,v,_ in fields if n == 1] != [b'Quest.proto']:
        raise ValueError('Different descriptor file')
    result = {}; enums = {}
    for number, wire, value, offset in fields:
        if number == 5:
            name, values = enum_descriptor(value)
            if name in enums:
                raise ValueError('Duplicate quest enum')
            enums[name] = values
        if number != 4:
            continue
        parsed = descriptor_fields(value)
        nested = {}; descriptions = {}
        for n,w,v,_ in wire_fields(value):
            if n == 4:
                name, values = enum_descriptor(v)
                if name in nested:
                    raise ValueError('Duplicate nested quest enum')
                nested[name] = values
            elif n == 2:
                parts = wire_fields(v)
                name = next(v for n,w,v,_ in parts if n == 1).decode()
                descriptions[name] = {key: v.decode() for n,w,v,_ in parts
                                      for field,key in ((6,'typeName'),(7,'defaultValue'))
                                      if n == field and w == 2}
        for field in parsed['fields']:
            field.update(descriptions[field['name']])
        if parsed['name'] in result:
            raise ValueError('Duplicate quest message')
        result[parsed['name']] = {**parsed, 'address': hex(address+offset),
                                 'bytes': len(value),
                                 'sha256': hashlib.sha256(value).hexdigest(),
                                 'enums': nested}
    return {'messages': result, 'enums': enums}


def quest_schema(image):
    return quest_file_schema(image)['messages']


def decoded_payload(schema, name, raw):
    """Check original output against its pinned schema, including presence."""
    fields = {r['number']: r for r in schema[name]['fields']}
    values = {}
    for number, wire, value, _ in wire_fields(raw):
        if number not in fields or wire != 0:
            raise ValueError('Unexpected source quest payload field')
        field = fields[number]
        if field['type'] in (13, 14) and value > 0xffffffff:
            raise ValueError('Source quest payload exceeds uint32/enum width')
        if field['label'] == 3:
            values.setdefault(field['name'], []).append(value)
        else:
            if field['name'] in values:
                raise ValueError('Duplicate source scalar field')
            values[field['name']] = value
    if any(r['label'] == 2 and r['name'] not in values for r in fields.values()):
        raise ValueError('Required source quest payload field absent')
    return values


def fixture_integer(value, bits, name, *, signed=False):
    """Host-memory packing boundary, not an original quest eligibility rule."""
    low, high = (-(1 << (bits-1)), (1 << (bits-1))-1) if signed else (0, (1 << bits)-1)
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{name} must fit {"int" if signed else "uint"}{bits}')
    return value


class QuestRequestProbe(SourcePhysics):
    SEND = 0x567094
    SENT = SourcePhysics.EXIT + 0x900
    SERIALIZERS = {0x24f9f50: ('C2GS_QuestQuery', 0x1d28694),
                   0x24fa790: ('C2GS_QuestComplete', 0x1d33aa0)}

    def __init__(self, image):
        from unicorn import UC_HOOK_CODE
        for address, (size, digest) in ROUTINES.items():
            if hashlib.sha256(image.read(address, size)).hexdigest() != digest:
                raise ValueError('Original quest-request routine differs')
        super().__init__(image)
        source_schema = quest_file_schema(image)
        self.schema = source_schema['messages']; self.schema_enums = source_schema['enums']
        self.packets = []; self.pending = None
        self.registry = self.alloc(0x100); self.hero = self.alloc(0x1800)
        self.w(self.hero+0x18, 'Q', self.alloc(0x400))
        self.w(self.registry+0x68, 'Q', self.hero)
        self.w(0x2528df8, 'Q', self.registry)
        self.w(0x2528e30, 'Q', self.alloc(0x100))
        for address in (self.SEND, self.SENT):
            self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=address,end=address)

    def hook(self, uc, address, size, data):
        if address == self.SEND:
            if self.pending is not None:
                raise ValueError('Nested source send not supported')
            message = self.get('X2'); vtable = self.r(message,'Q')[0]
            if vtable not in self.SERIALIZERS:
                raise ValueError('Unexpected source quest message class')
            name, serializer = self.SERIALIZERS[vtable]
            if self.r(vtable+0x58,'Q')[0] != serializer:
                raise ValueError('Original serializer virtual slot differs')
            buffer = self.alloc(1024)
            self.pending = (self.get('X30'),self.get('W1'),name,buffer)
            # Execute the original array serializer in this call stack. Only
            # the socket/send boundary is replaced by a recording sink.
            self.set('X0',message); self.set('X1',buffer)
            self.set('X30',self.SENT); self.set('PC',serializer)
        elif address == self.SENT:
            return_address, code, name, buffer = self.pending
            length = self.get('X0')-buffer
            if not 0 <= length <= 1024:
                raise ValueError('Unbounded original quest payload')
            raw = bytes(uc.mem_read(buffer,length))
            values = decoded_payload(self.schema, name, raw)
            self.packets.append({'id':code,'message':name,'hex':raw.hex(),'fields':values})
            self.pending = None
            self.set('W0',1); self.set('X30',return_address); self.set('PC',return_address)
        else:
            super().hook(uc,address,size,data)

    def click(self, status, *, quest_id=202, guid=0x1234567887654321,
              quest_type=1, cached=True, argument_type=2, argument_count=1,
              reward_ids=(), selected_reward=-1):
        """Explicit incoming-state/layout fixture, never a runtime quest record."""
        for value,bits,name in ((status,32,'status'),(quest_id,32,'quest_id'),
                                (guid,64,'guid'),(quest_type,32,'quest_type'),
                                (argument_type,8,'argument_type'),
                                (argument_count,32,'argument_count')):
            fixture_integer(value,bits,name)
        fixture_integer(selected_reward,32,'selected_reward',signed=True)
        if type(cached) is not bool:
            raise ValueError('cached must be an explicit bool')
        if not isinstance(reward_ids,(tuple,list)):
            raise ValueError('reward_ids must be an explicit list or tuple')
        for value in reward_ids:
            fixture_integer(value,32,'reward_id')
        if self.pending is not None:
            raise ValueError('Previous original send is unfinished')
        manager = self.alloc(0x980)
        self.call(0x49b828,{'X0':manager})
        row = self.alloc(0x180)
        self.w(row+8,'I',status); self.w(row+0x18,'Q',guid)
        self.w(row+0x20,'I',quest_id); self.w(row+0x28,'I',quest_type)
        self.w(manager+0x60,'2Q',row,row+0x180 if cached else row)
        self.w(manager+0x78,'I',int(cached))
        if reward_ids:
            rewards = self.alloc(4*len(reward_ids))
            self.w(rewards,str(len(reward_ids))+'I',*reward_ids)
            self.w(row+0xa8,'2Q',rewards,rewards+4*len(reward_ids))
        self.w(manager+0x88,'i',selected_reward)
        output=self.alloc(24); argument=self.alloc(24); vector=self.alloc(8)
        self.w(argument,'B',argument_type); self.w(argument+8,'d',float(quest_id))
        self.w(vector,'Q',argument)
        # The callback reads the low count word and a signed high-word start
        # index. This fixture supplies exactly one value at index zero.
        call=self.alloc(0x30); self.w(call,'Q',output)
        self.w(call+0x18,'Q',vector); self.w(call+0x20,'Q',argument_count)
        self.packets=[]
        self.call(0x65cb50,{'X0':call})
        return {'fixture':{'cacheSupplied':cached,'status':status,'questId':quest_id,
                           'questType':quest_type,'argumentType':argument_type,
                           'argumentCount':argument_count,
                           'rewardIds':list(reward_ids),'selectedReward':selected_reward},
                'callbackValid':bool(self.r(output+8,'B')[0]),
                'cachedStatusAfter':self.r(row+8,'I')[0],
                'packets':list(self.packets),
                'liveServerOrSavesUsed':False,
                'scope':'original callback/dispatch/constructors/serialization; explicit cache/hero-layout fixture; recording transport'}


def main():
    from analyze_native_resources import NativeImage
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--library',type=Path,required=True)
    cli.add_argument('--output',type=Path,required=True)
    args=cli.parse_args(); output=local_output(args.output)
    engine=QuestRequestProbe(NativeImage(args.library.read_bytes()))
    cases=[engine.click(status) for status in range(11)]
    cases.extend([engine.click(6,cached=False),engine.click(6,argument_type=1),
                  engine.click(6,argument_count=0),engine.click(7,quest_type=10),
                  engine.click(9,reward_ids=(40001,40002),selected_reward=1)])
    report={'format':'oc2-original-quest-request-fixtures-v1','cases':cases,
            'schema':engine.schema,'schemaEnums':engine.schema_enums,
            'acceptedQuest':None,'completedQuest':None,
            'serverScriptsRecovered':False,'productionUpdated':False}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'cases':len(cases),'acceptedQuest':None,'productionUpdated':False}))


if __name__=='__main__':
    main()
