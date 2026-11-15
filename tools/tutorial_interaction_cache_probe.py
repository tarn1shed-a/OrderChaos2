"""Execute original interaction-cache routines on explicitly authored controls.

The pending queue, registry, message fields, property keys and actor memory are
laboratory inputs. They are never original server observations or game state.
Only allocation/libc/free and a void presentation notification are adapters;
cache lookup/copy/replacement/gates/removal execute original ARM64 instructions.
No actual cache-writer caller or task approval is supplied by these controls.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AREA = ROOT / 'analysis/raw/tutorial-interaction-cache-20261115'
SO = ROOT / 'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'
OBSERVED_FUNCTIONS = (0xa42690, 0xa427b4, 0x1d35ac0, 0x1d36bb0, 0xa42e14,
                      0xa4052c, 0x91a408, 0xa3fd00, 0xa3f6ec)


def probe_type():
    from source_physics import SourcePhysics
    from unicorn import UC_HOOK_CODE

    class Probe(SourcePhysics):
        def __init__(self, image):
            super().__init__(image)
            self.notifications, self.frees = [], []
            self.function_entries = {address: 0 for address in OBSERVED_FUNCTIONS}
            self.uc.hook_add(UC_HOOK_CODE, self.hook,
                             begin=self.EXIT + 0x800, end=self.EXIT + 0x800)
            for address in OBSERVED_FUNCTIONS:
                self.uc.hook_add(UC_HOOK_CODE, self.hook, begin=address, end=address)

        def hook(self, uc, address, size, data):
            if address in self.function_entries:
                self.function_entries[address] += 1
                return  # Observe only; the original instructions still execute.
            if address == self.EXIT + 0x800:
                self.notifications.append({'actor': hex(self.get('X0')),
                                           'voidPresentationBoundary': True})
                self.set('PC', self.get('X30'))
                return
            if self.imports.get(address) in ('_ZdlPv', '_ZdaPv'):
                self.frees.append(self.get('X0'))
            return super().hook(uc, address, size, data)

        def manager_fixture(self, guid):
            manager, row = self.alloc(0xc0), self.alloc(0x20)
            self.w(row, 'QI', guid, 6)
            self.w(manager + 8, '2Q', row, row + 0x20)
            for offset in (0x30, 0x60, 0x90):
                header = manager + offset + 8
                self.w(header + 0x10, '2Q', header, header)
            return manager, row

        def message_fixture(self, guid):
            message, item, chat = self.alloc(0x58), self.alloc(0x30), self.alloc(0x40)
            self.call(0x1d35ac0, {'X0': message})
            self.call(0x1bdde18, {'X0': item})
            self.call(0x1bdcbe0, {'X0': chat})
            # Explicit protobuf in-memory inputs, not a received/parsed packet.
            self.w(item + 0x10, '4i', 202, 1, 1, 99)
            self.w(item + 0x20, 'B', 0)
            self.w(item + 0x28, 'I', 0x1f)
            vector = self.alloc(8)
            self.w(vector, 'Q', item)
            self.w(message + 0x10, 'Q', guid)
            self.w(message + 0x18, 'Q', vector)
            self.w(message + 0x20, '3I', 1, 1, 1)
            self.w(message + 0x40, 'Q', chat)
            self.w(message + 0x48, 'B', 1)
            self.w(message + 0x50, 'I', 0x15)
            return message, item

        def cached(self, manager):
            count = self.r(manager + 0x58, 'Q')[0]
            if count == 0:
                return {'count': 0}
            if count != 1:
                raise ValueError('These controls cover a one-node cache only')
            node = self.r(manager + 0x40, 'Q')[0]
            message = self.r(node + 0x28, 'Q')[0]
            vector = self.r(message + 0x18, 'Q')[0]
            item = self.r(vector, 'Q')[0]
            return {'count': count, 'node': hex(node), 'message': hex(message),
                    'guid': self.r(message + 0x10, 'Q')[0],
                    'haschatmenu': bool(self.r(message + 0x48, 'B')[0]),
                    'item': hex(item), 'fields': list(self.r(item + 0x10, '4i'))}

        def registry_fixture(self):
            registry = self.alloc(0x200)
            self.w(0x2528df8, 'Q', registry)
            self.w(registry + 0x10, '3Q', registry + 0x10, 0, registry + 0x10)
            return registry

        def actor_fixture(self, registry, guid):
            actor, vtable, attributes = self.alloc(0x1000), self.alloc(0x100), self.alloc(8)
            self.w(actor, '2Q', vtable, guid)
            self.w(actor + 0x18, 'Q', attributes)
            self.w(vtable + 0x98, 'Q', self.EXIT + 0x800)
            # Native redundant-value getter sees explicit value0. This avoids
            # the separate 0x40a non-quest-interaction branch, not a real race.
            self.w(0x2582f40, '2I', 17, 29)
            self.w(attributes, '2I', 17, 29)
            node = self.alloc(0x30)
            self.w(node + 8, 'Q', registry + 0x10)
            self.w(node + 0x20, '2Q', guid, actor)
            self.w(registry + 0x18, 'Q', node)
            return actor

    return Probe


def run():
    from analyze_native_resources import NativeImage
    image = NativeImage(SO.read_bytes())
    probe = probe_type()(image)
    guid = 0x51510001
    manager, pending_row = probe.manager_fixture(guid)
    message, item = probe.message_fixture(guid)
    controls = []

    probe.call(0xa42690, {'X0': manager, 'X1': 0})
    assert probe.cached(manager) == {'count': 0}
    probe.w(pending_row + 8, 'I', 5)
    probe.call(0xa42690, {'X0': manager, 'X1': message})
    assert probe.cached(manager) == {'count': 0}
    probe.w(pending_row + 8, 'I', 6)
    probe.w(message + 0x10, 'Q', guid + 1)
    probe.call(0xa42690, {'X0': manager, 'X1': message})
    assert probe.cached(manager) == {'count': 0}
    controls.append({'case': 'null-message/wrong-kind/wrong-guid', 'cacheCount': 0})

    probe.w(message + 0x10, 'Q', guid)
    probe.call(0xa42690, {'X0': manager, 'X1': message})
    first = probe.cached(manager)
    assert first['count'] == 1 and first['fields'] == [202, 1, 1, 99]
    assert first['message'] != hex(message) and first['item'] != hex(item)
    probe.w(item + 0x10, 'i', 203)
    probe.w(message + 0x48, 'B', 0)
    assert probe.cached(manager) == first
    controls.append({'case': 'native-copy-and-source-mutation', 'cache': first})

    probe.call(0xa42690, {'X0': manager, 'X1': message})
    second = probe.cached(manager)
    assert second['message'] == first['message'] and second['count'] == 1
    assert second['fields'] == [203, 1, 1, 99] and not second['haschatmenu']
    controls.append({'case': 'replace-existing-guid', 'cache': second})

    registry = probe.registry_fixture()
    probe.call(0xa42e14, {'X0': manager, 'X1': guid})
    assert probe.cached(manager) == second
    actor = probe.actor_fixture(registry, guid)
    probe.w(actor + 0xc63, 'B', 1)
    probe.call(0xa42e14, {'X0': manager, 'X1': guid})
    assert probe.cached(manager) == second and not probe.notifications
    controls.append({'case': 'no-actor/actor-c63-set', 'cachePreserved': True})

    probe.w(actor + 0xc63, 'B', 0)
    probe.call(0xa42e14, {'X0': manager, 'X1': guid})
    assert probe.cached(manager) == {'count': 0} and len(probe.notifications) == 1
    begin, end = probe.r(actor + 0x5e8, '2Q')
    assert end - begin == 8
    copied = probe.r(begin, 'Q')[0]
    assert list(probe.r(copied, '4i')) == [203, 1, 1, 99]
    assert probe.frees.count(int(second['message'], 16)) == 1
    controls.append({'case': 'explicit-apply-after-gate-change', 'cacheCount': 0,
                     'actorFields': list(probe.r(copied, '4i')),
                     'voidPresentationNotifications': 1,
                     'automaticRetryPolicyObserved': False})

    probe.call(0xa42690, {'X0': manager, 'X1': message})
    probe.call(0xa3fd00, {'X0': manager, 'X1': guid})
    assert probe.cached(manager) == {'count': 0}
    probe.call(0xa42690, {'X0': manager, 'X1': message})
    probe.call(0xa3f6ec, {'X0': manager})
    assert probe.cached(manager) == {'count': 0}
    assert probe.r(manager + 8, 'Q')[0] == probe.r(manager + 0x10, 'Q')[0]
    controls.append({'case': 'explicit-guid-clear/global-clear', 'cacheCount': 0})
    assert all(probe.function_entries.values())

    return {'format': 'oc2-original-interaction-cache-controls-v1',
            'nativeSHA256': hashlib.sha256(image.data).hexdigest(), 'controls': controls,
            'observedOriginalFunctionEntries': {
                hex(address): count for address, count in probe.function_entries.items()},
            'boundaries': [
                'Explicit pending-kind6 row, in-memory protobuf fields and container/registry headers; not original queue insertion or received packet.',
                'Original protobuf constructors/copy routines execute; source repeated-pointer storage is a named input, not original parser output.',
                'Original gates/lookup/copy/replace/removal execute with allocation/libc/free adapters; frees recorded, arena storage not reclaimed.',
                'Actor is minimal input memory with explicit property value0 and c63 controls; not a constructed/rendered original NPC.',
                'Only actor virtual98 void presentation notification is recorded; no model, renderer, native frame, UI or task approval is executed.',
                'Explicit re-calling of apply does not establish a runtime retry policy or a reachable cache-writer call.',
            ], 'taskApproved': False, 'packetsSent': False, 'savesOrServicesChanged': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(AREA.resolve()) or output.exists():
        parser.error('Use a new output in the dedicated ignored evidence directory')
    result = run()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'output': str(output), 'controlGroups': len(result['controls']),
                      'taskApproved': False, 'packetsSent': False}))
