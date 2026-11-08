"""Verify the selected-zone light/tone path against bounded ARM64 execution.

Only the 13 previously recovered channels are covered. Fog, quality mutation,
audio, weather and the other parts of either entry are deliberately excluded.
Unicorn executes copied code in isolated memory, never the native host process.
"""
import argparse
import copy
import hashlib
import json
import struct
from pathlib import Path

from resource_packs import DEFAULT_SOURCE, ResourceArchive
from scene_environment_state import (U32, apply_zone_targets, initial_environment,
    sample)
from scene_lighting import FIELDS, ZONE_SHA256, check_zone_layout, zone_targets
from scene_zone_selection import ZoneCatalog, verify_native as verify_selection
from skill_attachments import decode_ftable

FORMAT = 'oc2-active-zone-lighting-evidence-v1'
ROUTINES = {
    0x4c5b90: (6452, 'accfd4467363e76d4491cd1e8aa71b71bff6beb3c29de91d2aa4159f1ea9e42a'),
    0x1da989c: (28, 'e2b6601fd06bae532b04d276a749cdbbe4bf517e00c301f30a76ca3515ebc55e'),
}
# [begin,end) excludes the intervening fog/quality block and everything after
# the two zero tone-offset writes. Register setup is explicit at each boundary.
BLOCKS = {
    'selection': ((0x4c6510, 0x4c6b88), (0x4c6cc0, 0x4c6e04)),
    'override': ((0x4c3ae0, 0x4c414c), (0x4c427c, 0x4c43b8)),
}
CHANNELS = {
    'ambient': (0x0, 3), 'diffuse': (0x20, 3),
    'toneDistance': (0x78, 2), 'toneGainNear': (0x90, 3),
    'toneGainFar': (0xb0, 3), 'toneOffsetNear': (0xd0, 3), 'toneOffsetFar': (0xf0, 3),
    'intensity_char_ambient': (0x1b0, 1), 'intensity_char_diffuse': (0x1c8, 1),
    'intensity_char_specular': (0x1e0, 1), 'intensity_common': (0x1f8, 1),
    'intensity_lightMap': (0x210, 1), 'model_intensity_lightMap': (0x228, 1),
}


def verify_native(image):
    verify_selection(image)
    for address, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(address, size)).hexdigest() != digest:
            raise ValueError('Active environment path/list insertion changed; retrace required')
    return {'newRoutines': len(ROUTINES), 'boundedBlocks': BLOCKS,
            'verifiedChannelCount': len(CHANNELS), 'fullEntryEquivalent': False,
            'appliedToRendering': False}


def transition_duration(mode):
    # Both entries load global world+178 ->+58: absent object => immediate; +40 ==4
    # =>2000ms. The enum's original name/device state is not inferred.
    if mode is not None and (type(mode) is not int or not 0 <= mode <= U32):
        raise ValueError('Expected explicit native mode uint32 or absent object')
    return 2000 if mode == 4 else 0


def apply_selected_lighting(environment, base, overlay, mode):
    duration = transition_duration(mode)
    selected = overlay if overlay is not None else base
    if selected is None:
        return {'selectedZoneId': None, 'durationMilliseconds': duration, 'writes': {}}
    targets = zone_targets(selected, base)
    writes = apply_zone_targets(environment, targets, duration)
    return {'selectedZoneId': selected['ID'], 'durationMilliseconds': duration, 'writes': writes}


class NativeTargetProbe:
    """Run verified target blocks and real queue writers, with fake heap only.

    Only allocation/deallocation imports are substituted. The two vector
    writers, inline scalar writers and list insertion execute original bytes.
    No original assets or code are written to the repository by this helper.
    """
    def __init__(self, image):
        verify_native(image)
        from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
        from unicorn import arm64_const
        self.reg = arm64_const
        self.uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        for address, size in ((0x4c3000, 0x5000), (0x1da9000, 0x1000), (0x1df7000, 0x1000)):
            self.uc.mem_map(address, size)
            self.uc.mem_write(address, image.read(address, size))
        self.uc.mem_map(0x29f000, 0x1000)  # imported new/delete, intercepted below
        self.uc.mem_map(0x10000000, 0x40000)  # synthetic rows/manager/environment/heap
        self.uc.mem_map(0x20000000, 0x10000)  # synthetic stack
        self.uc.hook_add(UC_HOOK_CODE, self._import, begin=0x29f000, end=0x29ffff)
        self.heap = 0x10010000

    def _import(self, uc, address, size, data):
        if address == 0x29f0f0:
            size = uc.reg_read(self.reg.UC_ARM64_REG_X0)
            if not 0 < size <= 64 or self.heap+size >= 0x10040000:
                raise ValueError('Unexpected native allocation in bounded probe')
            uc.reg_write(self.reg.UC_ARM64_REG_X0, self.heap)
            self.heap += (size+15) & ~15
        elif address != 0x29f220:
            raise ValueError('Unexpected native import in bounded probe')
        uc.reg_write(self.reg.UC_ARM64_REG_PC, uc.reg_read(self.reg.UC_ARM64_REG_X30))

    def _write(self, address, fmt, *values):
        self.uc.mem_write(address, struct.pack('<'+fmt, *values))

    def _read(self, address, fmt):
        return struct.unpack('<'+fmt, self.uc.mem_read(address, struct.calcsize('<'+fmt)))

    def _node(self, value):
        address = self.heap
        self.heap += 48
        self._write(address+0x10, 'II', value['duration'], value['elapsed'])
        self._write(address+0x18, 'f'*len(value['target']), *value['target'])
        return address

    def run(self, environment, base, overlay, mode, *, entry='selection'):
        transition_duration(mode)
        if entry not in BLOCKS: raise ValueError('Unknown bounded target entry')
        selected = overlay if overlay is not None else base
        if selected is None: return copy.deepcopy(environment)
        self.heap = 0x10010000
        self.uc.mem_write(0x10000000, bytes(0x40000))
        self.uc.mem_write(0x20000000, bytes(0x10000))
        manager, env, base_at, selected_at, mode_at = (0x10000000, 0x10001000, 0x10002000, 0x10003000, 0x10004000)
        for row, address in ((base, base_at), (selected, selected_at)):
            if row is not None:
                for name, (offset, kind) in FIELDS.items():
                    self._write(address+offset, 'f' if kind == 'f' else 'I', row[name])
        self._write(manager+0x88, 'Q', base_at if base is not None else 0)
        self._write(manager+0xc0, 'Q', env)
        if mode is not None: self._write(mode_at+0x40, 'I', mode)
        for name, (offset, dim) in CHANNELS.items():
            value = environment[name]
            self._write(env+offset, 'f'*dim, *value.base)
            head = env+offset+(16 if dim == 3 else 8)
            nodes = [head, *[self._node(node) for node in value.pending]]
            for index, node in enumerate(nodes):
                self._write(node, 'QQ', nodes[(index+1) % len(nodes)], nodes[index-1])
        for index in range(31): self.uc.reg_write(getattr(self.reg, f'UC_ARM64_REG_X{index}'), 0)
        for index in range(32): self.uc.reg_write(getattr(self.reg, f'UC_ARM64_REG_Q{index}'), 0)
        stack = 0x20008000
        self.uc.reg_write(self.reg.UC_ARM64_REG_SP, stack)
        self.uc.reg_write(self.reg.UC_ARM64_REG_X19, manager)
        self.uc.reg_write(self.reg.UC_ARM64_REG_X23, mode_at if mode is not None else 0)
        row_reg = self.reg.UC_ARM64_REG_X27 if entry == 'selection' else self.reg.UC_ARM64_REG_X26
        self.uc.reg_write(row_reg, selected_at)
        self.uc.reg_write(self.reg.UC_ARM64_REG_X25, stack+0x108)
        for index, (begin, end) in enumerate(BLOCKS[entry]):
            if index and entry == 'selection':
                # Actual intervening 4c6b8c restores this scratch pointer.
                # Fog code changes only its own source fields/other channels.
                self.uc.reg_write(self.reg.UC_ARM64_REG_X25, stack+0x108)
            self.uc.emu_start(begin, end, count=20000)
            if self.uc.reg_read(self.reg.UC_ARM64_REG_PC) != end:
                raise ValueError('Native target block exceeded its bounded instruction limit')
        result = copy.deepcopy(environment)
        for name, (offset, dim) in CHANNELS.items():
            result[name].base = list(self._read(env+offset, 'f'*dim))
            result[name].pending = []
            head = env+offset+(16 if dim == 3 else 8)
            node, = self._read(head, 'Q')
            seen = set()
            while node != head:
                if node in seen or not 0x10010000 <= node < 0x10040000:
                    raise ValueError('Unexpected native target queue link')
                seen.add(node)
                duration, elapsed = self._read(node+0x10, 'II')
                result[name].pending.append({'duration': duration, 'elapsed': elapsed,
                                             'target': list(self._read(node+0x18, 'f'*dim))})
                node, = self._read(node, 'Q')
        return result


def state_record(environment):
    return {name: {'base': value.base, 'pending': value.pending} for name, value in environment.items()}


def analyze_active_lighting(image, source=DEFAULT_SOURCE):
    native = verify_native(image)
    raw = ResourceArchive(Path(source)/'tables.bin').read('tables/zones.tbl')
    if hashlib.sha256(raw).hexdigest() != ZONE_SHA256: raise ValueError('Original zone table changed')
    table = decode_ftable(raw, id_column='ID')
    check_zone_layout(table)
    catalog = ZoneCatalog(table['rows'], 5)
    probe = NativeTargetProbe(image)
    results = []
    for point in ((-2700, 187.3), (-2608, 187.3), (-2700, 0), (-2650, 0), (-2800, 0), (-1000, 0)):
        pair = catalog.select(*point)
        for mode in (None, 0, 4):
            environment = initial_environment()
            expected = copy.deepcopy(environment)
            routing = apply_selected_lighting(expected, **pair, mode=mode)
            active = probe.run(environment, **pair, mode=mode)
            alternate = probe.run(environment, **pair, mode=mode, entry='override')
            if state_record(active) != state_record(expected) or state_record(active) != state_record(alternate):
                raise ValueError('Source active/alternate target blocks differ from numeric oracle')
            results.append({'point': list(point), 'baseId': pair['base']['ID'] if pair['base'] else None,
                            'overlayId': pair['overlay']['ID'] if pair['overlay'] else None,
                            'explicitMode': mode, **routing, 'nativeBlocksEqualOracle': True,
                            'nativeBlocksExecuted': routing['selectedZoneId'] is not None,
                            'sample': sample(active)})
    return {'format': FORMAT, 'native': native, 'sourceTableSHA256': ZONE_SHA256,
            'explicitSourceQueries': results, 'appliedToRendering': False, 'nativeActiveStateObserved': False,
            'limits': [
                'Only 13 light/tone properties in two disjoint blocks of each entry are compared. Full functions are not equivalent: selected entry has extra notifications and other side effects.',
                'Native vector/scalar queue writers and list insertion run original bytes. Only allocation/deallocation use a synthetic heap; no original game process or network is invoked.',
                'Fog/quality source-row mutation between blocks, other environment properties, sky, audio and weather are not executed. Their registers do not feed these tone/light fields except the explicitly restored scratch pointer.',
                'Mode object absent or mode!=4 is immediate; mode4 uses2000ms. Native enum names and actual device mode/quality/upload gates remain unobserved.',
                'No selected row means no target update, not fallback194. Skipped tone writes retain pending state; model intensity stays coupled to generic lightMap source-row selection.',
                'This numeric/source proof does not resolve renderer RGB later writers, model-slot/device scope, color transfer or GPU precision. Atlas/UV1/source lighting are not applied to the browser.']}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--native', type=Path, default=Path('analysis/raw/beff-native/library.so'))
    cli.add_argument('--output', type=Path, default=Path('analysis/raw/map-active-lighting/active-lighting.json'))
    args = cli.parse_args()
    from analyze_native_resources import NativeImage
    report = analyze_active_lighting(NativeImage(args.native.read_bytes()), args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'output': str(args.output), 'explicitQueries': len(report['explicitSourceQueries']),
                      'appliedToRendering': False}))


if __name__ == '__main__': main()
