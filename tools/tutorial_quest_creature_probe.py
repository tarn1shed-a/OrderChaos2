"""Original Creature factory/message/qualification execution on explicit inputs.

No activity GUID, NPC availability, task offer or service rule is recovered by
these authored packet fixtures. Original assets and full reports stay private.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from tutorial_quest_request_probe import fixture_integer
from tutorial_quest_zone_probe import finite_f32
from tutorial_map_geometry import local_output

ROUTINES = {
    0xa302e0: (804, 'b4020407b3b67eb04e6c1ce25b99d8893f1aece7957516b8289bbb5aff51c7d9'),
    0xa3f8b8: (136, '7a1c39c1824fb51550a8670e83f490a056d842ed4686d96b5d063a809bffef15'),
    0xa3700c: (6592, '38814d00a0b17a098751c2ce22665378951b08f3640374b5944d7b7756342d24'),
    0xa77210: (360, 'ae3be4caf68f5fddf3370d76c3de3dea01838cffb54b7a9e686a09383e310534'),
    0x9055e0: (1668, 'b7383920ab5ad81b59ca0aeaeaf0f408652261dabb8e6b46d4d4e8c72d27282c'),
    0xa2aed8: (508, '98cf380139265bb897a91b085500438cc3022723fd4e24eb527a08c801a5a282'),
    0xa2b0d4: (536, '0b62e5bc5f12ee1756dffa2284cc8ee35315a91ade4bf9ecabd077e45238acdb'),
    0x9dd2c4: (824, 'c75e7e81fd660fb98b8b319f90ba88e5be281d316adfaaa29f16de9e63ba3fe9'),
    0x9dd5fc: (300, 'b444c866432726c746aab60d0cded7632e55c27b271859e9878331751eb0e640'),
    0x9dd728: (556, '70d235f94cf1d7ce108e2b927c7112774c65dbe643affbab45b58b84c22f8f60'),
    0x90bbb8: (200, '4e0b6f3066c4ca207413ddbd41bfb6e2167235b6e2b24df65280d48c1209f756'),
    0x9eba44: (300, '2e5ed5b9ee5068c239c2b694c79df857082045b85a5c181908b87610f5e56805'),
    0x915a90: (556, 'b985dc743396fb210611861f4f12200c6ae28e224185d5b1bdda596611a449da'),
    0x31f5fc: (264, '654b19a7bc05af40eec91623aede8d9c58653d87df01dcfe0db1c322f726ba39'),
    0x112b518: (104, '51295d2a690b4c2b48b4b880b48c07641881efabaf2e69911f35aa8e57e98f99'),
    0xa0b538: (1156, 'fb577984cc058c525bda002a366f4bc9e6ac49aece84057f2c42f3efc173066e'),
    0xa0b458: (224, '18d99dd02c53c1413a60143b7b8fc562bb7e77cfe6293b9a792cbf7e750fac7e'),
    0x91a1c8: (284, '8bbaa8ab331db6eecd5a401d940ed34ced732bf8ba5e014113febf0a0971d7b2'),
    0x669dec: (96, '2b25906291d5823b0f0a5ffe13aacb06178c8e75d57890118f197ca97537f306'),
    0xa03c28: (156, '704af8c29b57183446abfa1f88497f88698db11d8b6e32ca59ec5a4bd994d3c8'),
}
DESCRIPTORS = {
    'GS2C_ObjectCreate': (0x20297ec, 361, '9b885cd9c85fe6ccc241c05531c773e0fda176de821eca3e351e4dda8c5b389f'),
    'GS2C_ObjectCreature': (0x20294ed, 402, '6c44668e0e86243ea6b95fcce57a6dc5a4d6cedea89f47930b1c4091c05d3f1e'),
    'GS2C_FullObjectValue': (0x2028ec0, 62, '234cfe105e24fcefd8ce93dd94ac5cb211f8bc66a11215eb469f4e47e5c41020'),
}


def varint(value):
    fixture_integer(value, 64, 'wire value')
    result = bytearray()
    while value > 127:
        result.append(value & 127 | 128)
        value >>= 7
    return bytes(result)+bytes([value])


def nested(number, raw):
    return varint(number << 3 | 2)+varint(len(raw))+raw


def vector(values):
    if not isinstance(values, (list, tuple)) or len(values) != 3:
        raise ValueError('Three explicit float32 vector values required')
    return b''.join(varint((i+1) << 3 | 5)+struct.pack('<f', finite_f32(v))
                    for i, v in enumerate(values))


def packet_fixture(*, guid, entry, position, direction, values=(),
                   quest_status=None, quest_type=None, interactives=(),
                   display_id=None, name_id=None):
    """Author a bounded original-schema test packet, never a game producer."""
    fixture_integer(guid, 64, 'guid')
    fixture_integer(entry, 31, 'entry')
    if not isinstance(values, (tuple, list)) or len(values) > 158:
        raise ValueError('Creature allocation bounds explicit property inputs to158')
    properties = b''
    for v in values:
        fixture_integer(v, 32, 'raw property', signed=True)
        properties += b'\x08'+varint(v & ((1 << 64)-1))
    creature = b'\x08'+varint(entry)
    for number, v in ((2, quest_status), (3, quest_type), (4, name_id), (15, display_id)):
        if v is not None:
            fixture_integer(v, 31, 'creature field')
            creature += varint(number << 3)+varint(v)
    if not isinstance(interactives, (tuple, list)) or len(interactives) > 32:
        raise ValueError('Bounded explicit interaction fixtures required')
    for row in interactives:
        if not isinstance(row, (list, tuple)) or len(row) != 5 or type(row[4]) is not bool:
            raise ValueError('Four int32 and one bool interactive fixture required')
        item = b''
        for i, v in enumerate(row):
            if i < 4:
                fixture_integer(v, 32, 'interactive', signed=True)
            else:
                v = int(v)
            item += varint((i+1) << 3)+varint(v & ((1 << 64)-1))
        creature += nested(6, item)
    location = b'\x08\x05'+nested(2, vector(position))+nested(3, vector(direction))
    # Explicit empty Unit invokes its original constructor. Android's global
    # protobuf default-instance bootstrap has not run in this isolated host.
    return b'\x08'+varint(guid)+nested(2, location)+nested(4, creature)+nested(5, properties)+nested(6, b'')


def native_probe_type():
    from tutorial_npc_native_probe import TutorialNPCProbe
    from tutorial_quest_ui_wheel_probe import native_probe_type as wheel_type
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE
    from tutorial_quest_request_probe import QuestRequestProbe, quest_schema

    class CreatureProbe(TutorialNPCProbe, wheel_type()):
        SEND = QuestRequestProbe.SEND
        SENT = QuestRequestProbe.EXIT+0xf00
        SERIALIZERS = QuestRequestProbe.SERIALIZERS
        NOOP = SENT+4

        def __init__(self, image, source=DEFAULT_SOURCE):
            self.poison_actor_allocations = False
            self.creature_parse = False
            self.creature_dispatch = False
            self.creature_actor = None
            self.creature_services = []
            self.parsed_creature = None
            self.parse_ok = None
            self.init_calls = []
            self.query_mode = False
            self.as_results = []
            for at, (size, digest) in ROUTINES.items():
                if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
                    raise ValueError('Original Creature/input routine differs')
            from native_combat import descriptor_fields
            self.descriptor_proofs = {}
            for name, (at, size, digest) in DESCRIPTORS.items():
                raw = image.read(at, size)
                parsed = descriptor_fields(raw)
                if hashlib.sha256(raw).hexdigest() != digest or parsed['name'] != name:
                    raise ValueError('Original Creature/activity descriptor differs')
                self.descriptor_proofs[name] = {**parsed, 'address': hex(at), 'sha256': digest}
            relocs = {r['r_offset']: r['r_addend'] for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
            for off, target in ((0x18, 0xa67ba4), (0xb0, 0x90bbb8), (0x450, 0x9dd2c4),
                                (0x470, 0x9eba44), (0x478, 0x91abf4), (0x498, 0x91bc08)):
                if relocs.get(0x24222b8+off) != target:
                    raise ValueError('Original Creature virtual consumer differs')
            super().__init__(image, Sources(source))
            from unicorn import UC_HOOK_CODE
            self.creature_manager = self.alloc(0x300)
            self.w(0x2528df8, 'Q', self.creature_manager)
            self.w(self.creature_manager+0x68, 'Q', self.ui_hero)
            self.w(self.ui_hero+8, 'Q', 0x120a00000001)
            self.schema = quest_schema(image)
            self.pending = None
            self.packets = []
            self.quest_manager = self.alloc(0x980)
            self.call(0x49b828, {'X0': self.quest_manager})
            self.w(0x2528e40, 'Q', self.quest_manager)
            self.w(0x2528e30, 'Q', self.alloc(0x100))
            self.party_fixture = self.alloc(0x10)
            hv = self.r(self.ui_hero, 'Q')[0]
            for off, fn in ((0x290, 0xa0b538), (0x4e8, 0xa0b458), (0x168, self.FALSE),
                            (0x2e8, self.FALSE), (0x2d8, self.NOOP), (0x1e0, self.NOOP)):
                self.w(hv+off, 'Q', fn)
            self.call(0xa9995c, {'X0': self.r(self.ui_hero+0x18, 'Q')[0], 'W1': 0x120a})
            for offset in (0x10, 0xe8):
                h = self.creature_manager+offset
                self.w(h, 'Q', 0)
                self.w(h+8, '3Q', 0, h, h)
            self.call(0xa302e0, {'X0': self.creature_manager})
            for address in (0x36a218, 0x9ddb9c, 0x3a9250, 0x3afe28,
                            0xa3f90c, 0xa3700c, 0x9dd2c4, 0x9dd5fc,
                            self.SEND, self.SENT, self.NOOP, 0x1036c70,
                            0x5ae560, 0x5c1044, 0x904940, 0x41d470):
                self.uc.hook_add(UC_HOOK_CODE, self.hook, begin=address, end=address)

        def alloc(self, size):
            at = super().alloc(size)
            if self.poison_actor_allocations and size == 0xf30:
                self.uc.mem_write(at, b'\xa5'*size)
            return at

        def hook(self, uc, address, size, data):
            if address in (self.SEND, self.SENT):
                return QuestRequestProbe.hook(self, uc, address, size, data)
            if address == 0x41d470:
                self.creature_services.append({'source': hex(address), 'scope': 'Explicit empty party-vector input; no live party state observed'})
                self.set('X0', self.party_fixture)
                self.set('PC', self.get('X30'))
                return
            if address in (0x3a9250, 0x3afe28):
                return  # Original PRNG/default-slot copy execute.
            if address in (self.NOOP, 0x5ae560, 0x5c1044, 0x904940):
                self.creature_services.append({'source': hex(address), 'scope': 'Target presentation/reset boundary'})
                self.set('PC', self.get('X30'))
                return
            if address == 0x1036c70:
                self.as_results.append(bool(self.get('W1')))
                self.set('PC', self.get('X30'))
                return
            if address in (0x36a218, 0x9ddb9c):
                self.creature_services.append({'source': hex(address),
                    'scope': 'Unprepared external service/resource boundary; original activity/render completion not supplied'})
                self.set('W0', 0)
                self.set('PC', self.get('X30'))
                return
            if self.creature_parse and address == 0xa3f90c:
                self.parse_ok = bool(self.get('W0'))
                return
            if self.creature_parse and address == 0xa3700c:
                pointer = self.get('X1')
                self.parsed_creature = self.alloc(0x60)
                uc.mem_write(self.parsed_creature, bytes(uc.mem_read(pointer, 0x60)))
                self.set('PC', self.EXIT)
                return
            if address == 0xa3700c:
                return
            if address == 0x908634:
                return
            if address == 0x9dd9b4:
                return
            if address == 0x9dd2c4:
                self.creature_actor = self.get('X0')
                self.init_calls.append({'source': hex(address), 'scope': 'Original Creature v+450'})
                return
            if address == 0x9dd5fc:
                self.init_calls.append({'source': hex(address), 'entry': self.get('W1'),
                    'emote': self.get('W2'), 'emoteDelay': self.get('W3'), 'stagnateTime': self.get('W4')})
                return
            return super().hook(uc, address, size, data)

        def parse_creature_packet(self, raw):
            if not isinstance(raw, bytes) or not 0 < len(raw) <= 16384:
                raise ValueError('Bounded raw Creature packet fixture required')
            data, stream = self.alloc(len(raw)+4), self.alloc(0x40)
            self.w(data, 'I', len(raw))
            self.uc.mem_write(data+4, raw)
            self.w(stream+0x20, '2Q', data, data+len(raw)+4)
            self.creature_parse = True
            self.parse_ok = None
            self.parsed_creature = None
            try:
                self.call(0xa3f8b8, {'X1': stream}, limit=500000)
            finally:
                self.creature_parse = False
            if not self.parse_ok or not self.parsed_creature:
                raise ValueError('Original ObjectCreate parser rejected fixture')
            p = self.parsed_creature
            if self.r(p+0x5c, 'I')[0] & 0x58 != 0x58:
                raise ValueError('This host requires explicit location/Creature/Unit; original default-instance bootstrap is not run')
            if self.r(p+0x10, 'Q')[0] >> 32 != 0x40a:
                raise ValueError('This bounded host inspects only original factory kind0x40a; not an original wire rejection claim')
            return {'originalParserAccepted': True, 'guidFixture': self.r(p+0x10, 'Q')[0],
                    'presence': self.r(p+0x5c, 'I')[0],
                    'bytesConsumed': self.r(stream+0x10, 'Q')[0], 'realServerInput': False}

        def consume_creature_packet(self, *, update=False):
            if type(update) is not bool or not self.parsed_creature or (self.creature_actor is not None) != update:
                raise ValueError('One parsed packet per original creation fixture')
            if update and self.r(self.parsed_creature+0x10, 'Q')[0] != self.r(self.creature_actor+8, 'Q')[0]:
                raise ValueError('This bounded update requires the same fixture GUID')
            self.creature_dispatch = True
            try:
                self.call(0xa3700c, {'X0': self.creature_manager, 'X1': self.parsed_creature}, limit=1000000)
            finally:
                self.creature_dispatch = False
            if not self.creature_actor:
                raise ValueError('Original Creature initialization not reached')
            return self.snapshot_creature()

        def construct_only_fixture(self, *, poison=False):
            if type(poison) is not bool or self.creature_actor is not None:
                raise ValueError('One explicit constructor fixture per probe')
            self.poison_actor_allocations = poison
            try:
                self.creature_actor = self.call(0xa77210)
            finally:
                self.poison_actor_allocations = False
            return {'snapshot': self.snapshot_creature(),
                    'actorAllocationPoisoned': poison,
                    'messageInitializationExecuted': False,
                    'entryStorageIsNotAnInitializedNPCKey': True}

        def snapshot_creature(self):
            a = self.creature_actor
            if not a:
                raise ValueError('Original constructed Creature required')
            props = self.r(a+0x18, 'Q')[0]
            begin, end, capacity = self.r(a+0x5e8, '3Q')
            if not begin <= end <= capacity or (end-begin) % 8 or end-begin > 256:
                raise ValueError('Unbounded original Creature interactive cache')
            entries = []
            for p in range(begin, end, 8):
                q = self.r(p, 'Q')[0]
                entries.append([*self.r(q, '4i'), bool(self.r(q+16, 'B')[0])])
            return {'vtable': hex(self.r(a, 'Q')[0]), 'guidFixture': self.r(a+8, 'Q')[0],
                'entry': self.r(a+0xf20, 'I')[0], 'appearance': self.r(a+0xd2c, 'I')[0],
                'nameId': self.r(a+0xd30, 'I')[0], 'defaultDisplay': self.r(a+0xd40, 'I')[0],
                'selectedDisplay': self.r(a+0xd60, 'I')[0],
                'kind': self.call(0xa996a0, {'X0': props}),
                'property240': self.call(0xa996a0, {'X0': props+0x240}),
                'questStatus': self.r(a+0xc4, 'i')[0], 'questType': self.r(a+0x600, 'i')[0],
                'position': list(self.r(a+0x118, '3f')), 'interactives': entries,
                'modelWrapperPresent': bool(self.r(a+0x38, 'Q')[0]),
                'originalC1': self.r(a+0xc1, 'B')[0], 'original5a0': self.r(a+0x5a0, 'I')[0],
                'initializationCalls': list(self.init_calls), 'services': list(self.creature_services),
                'nativeFactoryRegistrationExecuted': True,
                'realActivityOrModelCompletionObserved': False}

        def explicit_model_boundary(self, *, node=False):
            if type(node) is not bool or not self.creature_actor:
                raise ValueError('Constructed Creature and explicit node boundary bool required')
            a = self.creature_actor
            wrapper = self.r(a+0x38, 'Q')[0]
            if not wrapper:
                wrapper = self.alloc(0x158)
                self.call(0x31f5fc, {'X0': wrapper})
                self.w(a+0x38, 'Q', wrapper)
            if node and not self.r(wrapper+8, 'Q')[0]:
                output, driver = self.alloc(8), self.alloc(0x100)
                self.call(0x112b518, {'X1': driver, 'X2': 0, 'X8': output})
                self.w(wrapper+8, 'Q', self.r(output, 'Q')[0])
            return {'wrapperConstructorExecuted': True,
                    'nativeTransformNodeExplicitlyAttached': bool(self.r(wrapper+8, 'Q')[0]),
                    'nativeNodeHostServices': list(self.host_services),
                    'originalBDAEOrGPUCompletionExecuted': False}

        def qualify_and_emit_creature(self):
            a = self.creature_actor
            if not a:
                raise ValueError('Original constructed Creature required')
            selection = bool(self.call(0x90bbb8, {'X0': a}) & 1)
            wrapper = bool(self.call(0x91bc08, {'X0': a}) & 1)
            mask = self.call(0x91abf4, {'X0': a})
            self.events = []
            self.visibility = []
            self.event_pointer = None
            self.wheel_active = True
            try:
                self.call(0xa038c8, {'X0': self.ui_hero, 'X1': a})
            finally:
                self.wheel_active = False
            return {'originalSelectionVb0': selection, 'originalWrapperV498': wrapper,
                    'originalMask': mask, 'events': list(self.events),
                    'visibilityBoundaries': list(self.visibility), 'liveStateObserved': False}

        def select_and_query_fixture(self):
            if not self.creature_actor:
                raise ValueError('Original constructed Creature required')
            self.wheel_active = True
            try:
                self.call(0xa0b538, {'X0': self.ui_hero, 'X1': self.creature_actor, 'W2': 0})
            finally:
                self.wheel_active = False
            selected = self.r(self.ui_hero+0x480, 'Q')[0]
            call, result = self.alloc(0x30), self.alloc(24)
            self.w(call, 'Q', result)
            self.w(call+0x20, 'I', 0)
            self.as_results = []
            self.packets = []
            self.call(0x669dec, {'X0': call})
            return {'selectedFixtureGuid': selected, 'asResultBoundary': list(self.as_results),
                    'packets': list(self.packets),
                    'managerTargetAndQueryGuid': list(self.r(self.quest_manager+0x90, '2Q')),
                    'queryCacheCount': (self.r(self.quest_manager+0x68, 'Q')[0]-self.r(self.quest_manager+0x60, 'Q')[0])//384,
                    'acceptedCacheCount': (self.r(self.quest_manager+0xb0, 'Q')[0]-self.r(self.quest_manager+0xa8, 'Q')[0])//384,
                    'serverResponseObserved': False, 'taskGranted': False}

    return CreatureProbe


def main():
    from analyze_native_resources import NativeImage
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--library', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    output = local_output(args.output)
    if output.exists():
        cli.error('Preserve existing evidence')
    image = NativeImage(args.library.read_bytes())
    C = native_probe_type()
    inputs = {'guid': 0x40a00001234, 'entry': 750,
              'position': (-2466.79, 136.291, -63.57), 'direction': (0, 0, 1)}
    ctor = C(image).construct_only_fixture(poison=True)
    e = C(image)
    values = [0]*73
    values[0], values[72] = 999, 4
    raw = packet_fixture(**inputs, values=values, quest_status=6, quest_type=1,
                         interactives=[[202, 1, 1, 99, True]])
    result = {'format': 'oc2-original-creature-input-fixtures-v1', 'constructorPoisonFixture': ctor,
              'descriptorProofs': e.descriptor_proofs,
              'authoredPacketHex': raw.hex(), 'parse': e.parse_creature_packet(raw),
              'creature': e.consume_creature_packet(), 'beforeModel': e.qualify_and_emit_creature(),
              'selectionBeforeModel': e.select_and_query_fixture()}
    result['wrapperOnlyBoundary'] = e.explicit_model_boundary()
    result['wrapperOnly'] = e.qualify_and_emit_creature()
    result['selectionWrapperOnly'] = e.select_and_query_fixture()
    result['nodeBoundary'] = e.explicit_model_boundary(node=True)
    result['withNode'] = e.qualify_and_emit_creature()
    result['selectionWithNode'] = e.select_and_query_fixture()
    # An independent instance verifies the original existing-object update path.
    update = C(image)
    update.parse_creature_packet(raw)
    update.consume_creature_packet()
    update.parse_creature_packet(packet_fixture(**inputs))
    result['sameGuidOmittedInteractionFields'] = update.consume_creature_packet(update=True)
    result['boundaries'] = ['Incoming activity/values/status/interactives and actor GUID are authored fixtures, never original server captures.',
        'Explicit empty Unit runs its original constructor; absent-Unit global protobuf bootstrap is not reconstructed.',
        'Original manager factory registration executes over host-initialized containers and a hero interface fixture.',
        'Original table rows are packed/copied by host providers, C++ strings and AS storage/dispatch/transport are recording boundaries.',
        'Atlas allocation36a218 and resource/appearance preparation9ddb9c remain unavailable service boundaries.',
        'Explicit wrapper/native transform-node insertion is not original BDAE/GPU completion, live eligibility, camera picking or a task grant.']
    result.update(productionChanged=False, savesReadOrWritten=False, hostAppearanceOrQuestRulesAdded=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(output), 'productionChanged': False}))


if __name__ == '__main__':
    main()
