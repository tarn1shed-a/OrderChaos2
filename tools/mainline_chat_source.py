"""Inspect original chat messages and execute only their window-selection tail.

This is an offline source probe, not a dialogue/task implementation. Its explicit
CPU inputs are authored controls, never recovered server replies. It stops before
constructing or dispatching a UI event and cannot accept/complete/reward a quest.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SO = ROOT / 'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'
WORLD = (0x2028b48, 64615,
         '40998743ad3be39eb76cb01d49030e2f73b0ccfc89b8a1654d8b45e82a01cbc1')
ROUTINES = {
    0x58b678: (968, 'f1c058c8fca8da665aafab2fdfe3fc7fbfc8205b11ec9c3533b37db762d3410a'),
    0x64121c: (584, '617182c002259519b998775f5db06f172ead1fceaa24d7e236cf020ec4f82366'),
    0x6448b0: (1052, 'c8478d032d73a174eb34803cc77ea74074caf795eb4709bf0aa50f720c1e3b75'),
    0x644fd8: (476, '335c24b8425382cfc9a9226ff4917abb8235b7b068b0bee8338e15c21a5a4357'),
    0xa03804: (196, 'd979574a4a0e5fb40183da67f3ec248841de27764836ba7f99015be2b16c4520'),
    0x5a106c: (348, 'bf84b5b99ef45d249fb5d4491f807101a87245e71c718008eac613c589a7cb1e'),
    0x5a11c8: (216, '909d44c3872634d0406f8bab86e35fc6dc0f5cc25ac9aed17c46387f4e962301'),
    0x6a984c: (272, 'a74a6f3d7991a99deb96f49d0c874c685be53e6bb4a7c73a74fb0f308d46e23d'),
}
NAMES = ('GS2C_ChatMenuOptionInfo', 'GS2C_ChatMenuInfo', 'GS2C_ChatMenuList',
         'C2GS_ChatMenuSelectOption', 'C2GS_GetChatMenuList')


def source(image):
    from native_combat import descriptor_fields
    from tutorial_quest_request_probe import wire_fields
    address, size, digest = WORLD
    raw = image.read(address, size)
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError('Original World.proto descriptor differs')
    messages = {}
    for number, wire, value, offset in wire_fields(raw):
        if number != 4:
            continue
        parsed = descriptor_fields(value)
        if parsed['name'] in NAMES:
            messages[parsed['name']] = {**parsed, 'address': hex(address + offset),
                'bytes': len(value), 'sha256': hashlib.sha256(value).hexdigest()}
    if set(messages) != set(NAMES):
        raise ValueError('Original chat message set differs')
    routines = {}
    for at, (length, sha) in ROUTINES.items():
        meta, lines = image.routine(at)
        if (meta['start'], meta['size']) != (hex(at), length):
            raise ValueError('Original routine extent differs')
        if hashlib.sha256(image.read(at, length)).hexdigest() != sha:
            raise ValueError('Original chat routine differs')
        routines[hex(at)] = {**meta, 'sha256': sha, 'instructions': lines}
    return {'messages': messages, 'routines': routines}


def selection_controls(image):
    """Run the original post-parse branch, stopping at event constructors.

    Count, parsed is_list/presence conjunction, registry presence, actor virtual
    interface mask, and hero+150c byte are explicit CPU inputs. The mask-return
    adapter is not a server eligibility predicate or a recovered live actor.
    """
    from source_physics import SourcePhysics
    from unicorn import UC_HOOK_CODE

    class Probe(SourcePhysics):
        MASK = SourcePhysics.EXIT + 0xa00

        def __init__(self):
            super().__init__(image)
            self.actor = self.alloc(0x500)
            self.hero = self.alloc(0x1600)
            vt = self.alloc(0x500)
            self.w(self.actor, 'Q', vt)
            self.w(vt + 0x478, 'Q', self.MASK)
            for at in (self.MASK, 0x58b944, 0x64121c, 0x644fd8, 0x6448b0):
                self.uc.hook_add(UC_HOOK_CODE, self.boundary, begin=at, end=at)

        def boundary(self, uc, address, size, data):
            if address == self.MASK:
                self.mask_reads += 1
                self.set('W0', self.mask)
                self.set('PC', self.get('X30'))
            elif address == 0x58b944:
                self.original_count = self.get('W0')
            else:
                self.event = {'constructor': hex(address),
                    'integerArguments': [self.get('W' + str(i)) for i in range(1, 6)]}
                self.set('PC', self.EXIT)

        def case(self, count, list_input, actor_present, mask, hero_byte):
            self.event = None
            self.mask_reads = 0
            self.original_count = None
            self.mask = mask
            self.w(self.hero + 0x150c, 'B', hero_byte)
            self.call(0x58b91c, {'W19': count}, stack=(0, int(list_input) << 32,
                self.actor if actor_present else 0, self.hero), limit=500)
            if self.event is None:
                raise ValueError('Original branch did not reach a reviewed UI boundary')
            return {'input': {'menuCount': count, 'effectiveIsList': list_input,
                'actorPresent': actor_present, 'virtual478Mask': mask,
                'hero150cByte': hero_byte}, 'eventBoundary': self.event,
                'virtualMaskReads': self.mask_reads,
                'originalHelperCount': self.original_count,
                'eventConstructed': False}

    probe = Probe()
    inputs = [(0, False, False, 0, 0), (1, False, False, 0, 0),
              (2, False, False, 0, 0), (1, True, False, 0, 0),
              (1, True, True, 0, 0), (1, True, True, 5, 0),
              (1, True, True, 5, 1), (2, True, True, 5, 0),
              (2, True, True, 0, 0), (1, False, True, 5, 0)]
    return [probe.case(*args) for args in inputs]


def audit():
    from analyze_native_resources import NativeImage
    image = NativeImage(SO.read_bytes())
    return {'format': 'oc2-original-mainline-chat-flow-v1',
        'originalSHA256': hashlib.sha256(image.data).hexdigest(), **source(image),
        'windowSelectionControls': selection_controls(image),
        'boundaries': [
            'Original descriptor/function bytes and bounded post-parse CPU branch only.',
            'No full message receive, Android session, original server input, UI event dispatch or rendered task chain.',
            'Static recommended menu64 and text IDs are not substituted for unknown actual reply values.',
            'No dialogue body, script side effect, quest approval, position or save is manufactured.',
        ], 'runtimeEnabled': False, 'savesAccessed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to((ROOT / 'analysis/raw').resolve()) or output.exists():
        parser.error('Use a new ignored analysis/raw output')
    result = audit()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'output': str(output), 'messages': len(result['messages']),
        'controls': len(result['windowSelectionControls']), 'runtimeEnabled': False}))
