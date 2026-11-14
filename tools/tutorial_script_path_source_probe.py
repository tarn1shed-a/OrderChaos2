"""Original tutorial input path controls, not an observed Android file stream.

The original native directory getters/setters and complete path resolver execute.
Directory values, empty remap state, COW storage and bounded libc are explicit
research inputs. No open result, payload, quest approval or game rule is supplied.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from tutorial_script_entry_probe import ROOT, SO, probe_type

RAW = ROOT / 'analysis/raw/tutorial-script-path-source-20261115'
TARGETS = (0xc99370, 0xc994c8, 0xc993f8, 0x1542094, 0x10f75d4,
           0x1541f28, 0x1541fe0, 0x1542014, 0x1542048)


def direct_branches(image):
    """Cover aligned immediate B/BL opcodes, never computed/indirect calls."""
    section = image.elf.get_section_by_name('.text')
    raw, base = section.data(), section['sh_addr']
    found = {hex(a): [] for a in TARGETS}
    for offset, (word,) in enumerate(struct.iter_unpack('<I', raw)):
        opcode = word & 0xfc000000
        if opcode not in (0x94000000, 0x14000000):
            continue
        displacement = word & 0x3ffffff
        if displacement & 0x2000000:
            displacement -= 0x4000000
        address = base + offset * 4
        destination = address + displacement * 4
        if destination in TARGETS:
            found[hex(destination)].append({'at': hex(address),
                'branch': 'BL' if opcode == 0x94000000 else 'B'})
    return {'textBytes': len(raw), 'targets': found,
            'indirectCallsOrAliasesExcluded': False,
            'scope': 'Every aligned B/BL opcode in the original .text only'}


def run():
    from analyze_native_resources import NativeImage

    class PathProbe(probe_type()):
        def hook(self, uc, address, size, data):
            if address == 0x1de868c and self.mode == 'path':
                # All fixture strings already have private writable storage.
                self.set('PC', self.get('X30'))
                return
            if address in self.imports and self.imports[address] in ('strncmp', 'tolower', 'strcpy'):
                if self.imports[address] == 'tolower':
                    value = self.get('W0')
                    if value > 127:
                        raise ValueError('Only named ASCII path controls admitted')
                    self.set('W0', value + 32 if 65 <= value <= 90 else value)
                elif self.imports[address] == 'strcpy':
                    value = self.cstr(self.get('X1'))
                    uc.mem_write(self.get('X0'), value + b'\0')
                else:
                    count = self.get('X2')
                    if count > 2048:
                        raise ValueError('Unbounded path comparison rejected')
                    left = bytes(uc.mem_read(self.get('X0'), count)).split(b'\0')[0]
                    right = bytes(uc.mem_read(self.get('X1'), count)).split(b'\0')[0]
                    self.set('W0', 0 if left == right else 1 if left > right else 0xffffffff)
                self.set('PC', self.get('X30'))
                return
            return super().hook(uc, address, size, data)

    image = NativeImage(SO.read_bytes())
    probe = PathProbe(image)
    probe.mode = 'path'
    manager = probe.alloc(0x280)
    directory_controls = []
    for global_at, getter, setter, offset, value in (
            (0x2526fc0, 0x2f8738, 0x1541fe0, 8, b'/research-data'),
            (0x2526fc8, 0x2f8748, 0x1542014, 0x10, b'/research-save'),
            (0x2526fd0, 0x2f8758, 0x1542048, 0x18, b'/research-cache')):
        # Explicit JNI result storage; neither JNI nor Android preferences run.
        pointer = probe.cow(value)
        probe.w(global_at, 'Q', pointer)
        holder = probe.call(getter)
        assert holder == global_at
        source = probe.r(holder, 'Q')[0]
        probe.call(setter, {'X0': manager, 'X1': source})
        actual = probe.cstr(probe.r(manager + offset, 'Q')[0])
        assert actual == value
        directory_controls.append({'getter': hex(getter), 'setter': hex(setter),
            'globalStringHolder': hex(global_at), 'managerOffset': offset,
            'explicitDirectory': value.decode(), 'sourceAndDestinationEqual': True})

    paths = []
    # Empty remap container and no extra mount aliases are research conditions.
    probe.w(0x2691078, 'Q', 0)
    for lower in (False, True):
        probe.w(manager, 'B', int(lower))
        name, output = probe.alloc(32), probe.alloc(1024)
        probe.uc.mem_write(name, b'InitialFeed.dat\0')
        result = probe.call(0x15427d4, {'X0': manager, 'X1': name,
            'W2': 0, 'X3': output, 'X4': 1024})
        actual = probe.cstr(output).decode()
        assert result == 0
        assert actual == '/research-data/' + ('initialfeed.dat' if lower else 'InitialFeed.dat')
        assert not probe.paths
        paths.append({'explicitLowercaseFlag': lower, 'inputFlags': 0,
            'returnedFlags': result, 'completeOriginalResolverExecuted': True,
            'resolvedFixturePath': actual, 'originalOpenRequested': False})

    factory = []
    for current, supplied, expected in ((0, 0x12345000, 1),
            (0x12345000, 0x12346000, 0), (0x12345000, 0, 0)):
        probe.w(0x25ba0e0, 'Q', current)
        result = probe.call(0x10f75d4, {'X0': supplied}, limit=20)
        stored = probe.r(0x25ba0e0, 'Q')[0]
        assert result == expected and stored == (supplied if expected else current)
        factory.append({'explicitExistingPointer': hex(current),
            'explicitSuppliedPointer': hex(supplied), 'accepted': result,
            'storedPointer': hex(stored), 'pointeeDereferenced': False})

    return {'format': 'oc2-tutorial-script-path-source-v1',
        'nativeSHA256': hashlib.sha256(image.data).hexdigest(),
        'directories': directory_controls, 'pathControls': paths,
        'factoryRegisterOnlyIfEmptyControls': factory,
        'directBranches': direct_branches(image),
        'interfaces': ['JNI result strings supplied explicitly',
            'Empty path-remap state and zero extra aliases supplied explicitly',
            'Private writable COW storage and bounded ASCII libc'],
        'actualAndroidPreferencesOrStreamObserved': False,
        'originalPayloadOrQuestScriptRecovered': False,
        'gameOrSaveOrProductionAccessed': False}


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(RAW.resolve()) or output.exists():
        cli.error('Use a new file in the private script-path-source directory')
    result = run()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'directoryControls': len(result['directories']),
        'completePathControls': len(result['pathControls']),
        'scriptRecovered': False, 'output': str(output)}))
