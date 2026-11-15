"""Bounded original chat-request callers, never a mainline approval source.

Original dispatch/request/framing/serialization instructions execute offline.
Actor/GUID/socket/button inputs and the two partial caller entries are explicit
controls. No server response, NPC eligibility, dialogue or save is manufactured.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from mainline_chat_source import SO, WORLD
from native_combat import descriptor_fields
from source_physics import SourcePhysics
from tutorial_quest_request_probe import fixture_integer, wire_fields

ROOT = Path(__file__).resolve().parents[1]
PINS = {
    0x9e51a8: (3388, 'ab317752e4fbb4b96188edb0da22f6b3bbef1d47644e94aa537c0b1bcc5e7f39'),
    0xa03f98: (1240, '08c199f3aa471d020a31a90bc1aa0be47ac0a1d3e056d5f2543dffb1190176f9'),
    0x5a11c8: (216, '909d44c3872634d0406f8bab86e35fc6dc0f5cc25ac9aed17c46387f4e962301'),
    0x5ac05c: (204, 'b30745adcaeae186809e811405582a405aa65203ef4b7d72b0e10db669e971a0'),
    0x1bdf300: (56, '1d7d4a290c1b35da04d7d0899eca7434612a9f5de674dd65d90f38225ba4e284'),
    0x1bdf490: (52, 'ee2cf35a93c11ec5a9eedb65bdce607aa38b77381eafe63e8d874149ead5a256'),
    0x1bdf7b8: (96, 'bee421a1c3c859e4cefd4dfb6989922a9de45d02694cb0e6313a2b987c235378'),
    0x1bdf758: (96, '5f3ee2cbdf24fe1e2bcdb97833a70728763889cc0dc4f072010acf1373e5d917'),
    0x91abb0: (68, '9a8c51ac2c5d2d4fabd3aaedd004b50fa27df1261b95e1eccbdff68d1a869a24'),
    0x3e810c: (16, '38ff10c39919ebea80df90ed73d2e3c54da671fde766e0af427a56e439b921e4'),
}
TABLE = (0x1e632bc, 68,
         'ad6c2e66aa150f0cdb4dc34eefa440459fd062c476fbb720836fe05c9f6f1a2f')


def source(image):
    routines = {}
    for address, (size, sha) in PINS.items():
        meta, _ = image.routine(address)
        if (meta['start'], meta['size']) != (hex(address), size):
            raise ValueError('Original chat caller extent differs')
        if hashlib.sha256(image.read(address, size)).hexdigest() != sha:
            raise ValueError('Original chat caller bytes differ')
        routines[hex(address)] = {'size': size, 'sha256': sha}
    at, size, sha = TABLE
    raw = image.read(at, size)
    if hashlib.sha256(raw).hexdigest() != sha:
        raise ValueError('Original button dispatch table differs')
    buttons = {str(i): hex(at + row[0]) for i, row in
               enumerate(struct.iter_unpack('<i', raw))}
    at, size, sha = WORLD
    raw = image.read(at, size)
    if hashlib.sha256(raw).hexdigest() != sha:
        raise ValueError('Original World.proto differs')
    messages = [descriptor_fields(v) for n, w, v, _ in wire_fields(raw) if n == 4]
    matching = [v for v in messages if v['name'] == 'C2GS_GetChatMenuList']
    if len(matching) != 1:
        raise ValueError('Original chat request descriptor absent/ambiguous')
    return {'routines': routines, 'buttonDispatch': buttons,
            'requestSchema': matching[0]}


class ChatRequestProbe(SourcePhysics):
    BUTTON = SourcePhysics.EXIT + 0xa00

    def __init__(self, image):
        from unicorn import UC_HOOK_CODE
        self.evidence = source(image)
        super().__init__(image)
        self.network = self.alloc(0x100)
        self.socket = self.alloc(0x200)
        self.actor = self.alloc(0x1100)
        self.hero = self.alloc(0x1600)
        self.attrs = self.alloc(0x1000)
        self.vector = self.alloc(24)
        self.item = self.alloc(16)
        self.w(self.actor + 0x18, 'Q', self.attrs)
        self.call(0xa99910, {'X0': self.attrs, 'W1': 0x40a})
        vt = self.alloc(0x500)
        self.w(self.actor, 'Q', vt)
        self.w(vt + 0x490, 'Q', self.BUTTON)
        # Explicit post-request presentation guard, not NPC interaction proof.
        self.w(vt + 0x2b8, 'Q', self.TRUE)
        self.w(0x2528e30, 'Q', self.network)
        self.packets = []
        self.secondary = []
        self.reached = []
        for at in (self.BUTTON, 0x5802ec, 0x5a7d3c, 0xa038c8,
                   0x9e5b30, 0x9e5b6c, 0x9e5c20):
            self.uc.hook_add(UC_HOOK_CODE, self.hook, begin=at, end=at)

    def hook(self, uc, at, size, data):
        if at == self.BUTTON:
            self.set('W0', self.button)
        elif at in (0x5a7d3c, 0xa038c8):
            self.secondary.append({'entry': hex(at), 'argumentX1': str(self.get('X1')),
                                   'executed': False})
        elif at in (0x9e5b30, 0x9e5b6c, 0x9e5c20):
            self.reached.append(hex(at))
            self.set('PC', self.EXIT)
            return
        elif at == 0x5802ec:
            packet = self.get('X1')
            code = self.r(packet, 'H')[0]
            stream = packet + 8
            length = self.r(stream + 0x10, 'Q')[0]
            begin, end, capacity = self.r(stream + 0x18, '3Q')
            if code not in (0x9a, 0x21) or not 0 < length <= 256:
                raise ValueError('Request outside bounded chat control')
            if not begin <= begin + length <= end <= capacity:
                raise ValueError('Original request stream span differs')
            raw = bytes(uc.mem_read(begin, length))
            if code == 0x9a:
                if len(raw) < 4 or int.from_bytes(raw[:4], 'little') != len(raw)-4:
                    raise ValueError('Original protobuf framing differs')
                fields = wire_fields(raw[4:])
                schema = self.evidence['requestSchema']['fields']
                if len(schema) != 1 or len(fields) != 1:
                    raise ValueError('Original chat request field set differs')
                number, wire, guid, _ = fields[0]
                if (number, wire) != (schema[0]['number'], 0):
                    raise ValueError('Original GUID field differs')
            else:
                if len(raw) != 8:
                    raise ValueError('Original interaction request width differs')
                guid = int.from_bytes(raw, 'little')
            self.packets.append({'opcode': code, 'framedHex': raw.hex(),
                                 'guid': str(guid), 'transportExecuted': False})
            self.set('W0', 1)
        elif self.imports.get(at) == '_ZNSt6vectorIhSaIhEE17_M_default_appendEm':
            # Host STL storage adapter. Application code writes all payloads.
            vector, count = self.get('X0'), self.get('X1')
            begin, end, capacity = self.r(vector, '3Q')
            if not 0 <= count <= 256 or not begin <= end <= end+count <= capacity:
                raise ValueError('Control exceeds preallocated vector capacity')
            uc.mem_write(end, bytes(count))
            self.w(vector + 8, 'Q', end + count)
        else:
            return super().hook(uc, at, size, data)
        self.set('PC', self.get('X30'))

    def configure(self, guid, *, connected=True, suppressed=False,
                  socket_present=True, network_socket=True):
        fixture_integer(guid, 64, 'explicit_control_guid')
        if any(type(v) is not bool for v in
               (connected, suppressed, socket_present, network_socket)):
            raise ValueError('Explicit socket control booleans required')
        self.packets, self.secondary, self.reached = [], [], []
        self.w(self.actor + 8, 'Q', guid)
        self.w(self.network + 8, 'Q', self.socket if network_socket else 0)
        self.w(self.socket + 0x15c, 'B', int(connected))
        self.w(self.socket + 0xd8, 'Q', int(socket_present))
        self.w(self.network + 0x8b, 'B', int(suppressed))

    def result(self, inputs):
        return {'controls': inputs, 'packets': list(self.packets),
                'unexecutedSecondaryBoundaries': list(self.secondary),
                'stopBoundaries': list(self.reached), 'serverReply': None,
                'taskAcceptedOrAdvanced': False}

    def constructor(self, guid, **socket):
        self.configure(guid, **socket)
        self.call(0x5a11c8, {'X0': self.network, 'X1': guid})
        return self.result({'entry': '0x5a11c8', 'guid': str(guid), **socket})

    def dispatch(self, button, guid):
        fixture_integer(button, 32, 'explicit_button_control')
        if button not in (0, 2, 9, 11, 12, 15, 16, 17):
            raise ValueError('Button path outside reviewed bounded controls')
        self.configure(guid)
        self.button = button
        self.call(0xa03f98, {'X0': self.hero, 'X1': self.actor})
        return self.result({'entry': '0xa03f98', 'guid': str(guid),
                            'buttonVirtual490': button, 'eligibilityRecovered': False})

    def count_slice(self, count, guid, *, fallthrough_button=17):
        fixture_integer(count, 32, 'explicit_count_control', signed=True)
        if type(fallthrough_button) is not int or fallthrough_button not in (2, 17):
            raise ValueError('Explicit reviewed fallthrough button required')
        self.configure(guid)
        self.button = fallthrough_button
        self.call(0x9e5a6c, {'X19': self.hero, 'X20': guid,
                           'X21': self.actor, 'W9': count})
        return self.result({'entry': '0x9e5a6c', 'guid': str(guid),
                            'computedCountSupplied': count,
                            'fallthroughButtonVirtual490': fallthrough_button,
                            'fullCallerExecuted': False})

    def list_slice(self, guid, *, blocked, has_vector, nonempty):
        if any(type(v) is not bool for v in (blocked, has_vector, nonempty)):
            raise ValueError('Explicit list control booleans required')
        self.configure(guid)
        self.w(self.actor + 0xc63, 'B', int(blocked))
        self.w(self.actor + 0xb00, 'Q', self.vector if has_vector else 0)
        self.w(self.vector, '3Q', self.item, self.item + (16 if nonempty else 0),
               self.item + 16)
        self.call(0x9e5b50, {'X19': self.hero, 'X20': guid, 'X21': self.actor})
        return self.result({'entry': '0x9e5b50', 'guid': str(guid),
                            'actorC63': blocked, 'vectorPresent': has_vector,
                            'vectorNonempty': nonempty, 'fullCallerExecuted': False})


def run(image):
    p = ChatRequestProbe(image)
    guid = (0x40a << 32) | 2337  # Explicit control, NOT recovered actor identity.
    constructors = [p.constructor(v) for v in (0, 127, 128, guid, (1 << 64)-1)]
    constructors += [p.constructor(guid, **v) for v in
                     ({'connected': False}, {'suppressed': True},
                      {'socket_present': False}, {'network_socket': False})]
    return {'format': 'oc2-original-chat-request-callers-v1',
            'sourceSHA256': hashlib.sha256(image.data).hexdigest(),
            'source': p.evidence, 'constructors': constructors,
            'buttonControls': [p.dispatch(v, guid) for v in (0, 2, 9, 11, 12, 15, 16, 17)],
            'countSlices': [p.count_slice(v, guid, fallthrough_button=b)
                            for b in (17, 2) for v in (-1, 0, 1, 2, 3)],
            'listSlices': [p.list_slice(guid, blocked=b, has_vector=h, nonempty=n)
                           for b, h, n in ((False, True, True), (True, True, True),
                                          (False, False, False), (False, True, False))],
            'boundaries': [
                'No actual NPC778 GUID, virtual490 result, eligibility, server response or mainline approval.',
                'Two9e51a8 slices bypass preceding registry/distance/model/interaction count production.',
                'Onlya03f98 dispatch body and5a11c8 constructor/framing/serialization are complete here.',
                'Secondary5a7d3c/a038c8 are recording boundaries, not executed original side effects.',
                'STL storage/libc/allocation/socket recording are host interfaces. No game/save/server is used.',
            ], 'runtimeEnabled': False, 'savesAccessed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to((ROOT/'analysis/raw').resolve()) or out.exists():
        parser.error('Use a new ignored analysis/raw output')
    from analyze_native_resources import NativeImage
    report = run(NativeImage(SO.read_bytes()))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'output': str(out), 'controls': sum(len(report[k]) for k in
                      ('constructors', 'buttonControls', 'countSlices', 'listSlices')),
                      'runtimeEnabled': False}))
