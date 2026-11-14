"""Trace original tutorial table paths and script-name storage, without a VM.

Native instructions build the requested table paths and read original rows.
The file-open boundary stops before an open result; no successful load, script
execution, actor, quest approval, or game state is supplied by this probe.
Full original rows and traces remain in ignored analysis/raw/.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'analysis/raw/tutorial-script-entry-20261115'
SO = ROOT / 'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'
TABLES = {
    'quests': {'key': 'entry', 'id': 202, 'load': 0xce9c64, 'read': 0xceae50},
    'scripts': {'key': 'Id', 'id': 1, 'load': 0xd38660, 'read': 0xd399a4},
}


def private_output(path):
    path = Path(path).resolve()
    if not path.is_relative_to(RAW.resolve()):
        raise ValueError('Original evidence stays in the private script-entry directory')
    if path.exists():
        raise ValueError('Preserve the previous script-entry checkpoint')
    return path


def probe_type():
    from source_physics import SourcePhysics
    from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ

    class ScriptEntryProbe(SourcePhysics):
        def __init__(self, image):
            super().__init__(image)
            self.mode = None
            self.paths = []
            self.string_spans = []
            self.stream_events = []
            self.script_reads = []
            self.relocations = {r['r_offset']: r['r_addend'] for r in
                                image.elf.get_section_by_name('.rela.dyn').iter_relocations()
                                if r['r_info_type'] == 1027}
            for a in (0x1de6fb8, 0x1de8e34, 0x1de868c, 0xe881dc,
                      0xe87ca0, 0xa7b5f8, 0xa7b618, self.EXIT + 0x800, self.EXIT + 0x810):
                self.uc.hook_add(UC_HOOK_CODE, self.hook, begin=a, end=a)
            self.uc.hook_add(UC_HOOK_MEM_READ, self.observe_read)

        def cow(self, raw):
            # An explicitly supplied string-storage provider. The reference
            # count is a research control, never an original runtime default.
            p = self.alloc(24 + len(raw) + 1)
            self.w(p, 'QQiI', len(raw), len(raw), 1000, 0)
            self.uc.mem_write(p + 24, raw + b'\0')
            return p + 24

        def observe_read(self, uc, access, address, size, value, data):
            if self.mode == 'destroy' and address <= self.script_address < address + size:
                self.script_reads.append({'pc': hex(self.get('PC')), 'bytes': size})

        def hook(self, uc, a, size, data):
            if a == 0xe881dc and self.mode == 'row':
                offset, length = self.get('W1'), self.get('W2')
                self.string_spans.append({'offset': offset, 'length': length})
                # Observe, then execute the complete original bounds/seek/read
                # body. COW storage and the file interface remain named sinks.
                return
            elif a == 0x1de8e34 and self.mode == 'row':
                self.w(self.get('X0'), 'Q', self.cow(bytes(self.get('W1'))))
            elif a == 0x1de868c and self.mode == 'row':
                pass  # Every supplied COW buffer is private and writable.
            elif a == self.EXIT + 0x800 and self.mode == 'row':
                length = self.get('W2')
                raw = self.table_raw[self.stream_at:self.stream_at + length]
                if len(raw) != length:
                    raise ValueError('Original string reader requested a truncated source span')
                uc.mem_write(self.get('X1'), raw)
                self.stream_events.append({'operation': 'read', 'offset': self.stream_at, 'length': length})
                self.stream_at += length
                self.set('W0', 1)
            elif a == self.EXIT + 0x810 and self.mode == 'row':
                if self.get('W2') != 0:
                    raise ValueError('Unexpected original string seek mode')
                self.stream_at = self.get('W1')
                self.stream_events.append({'operation': 'seek', 'offset': self.stream_at})
                self.set('W0', 1)
            elif a == 0x1de8970 and self.mode == 'path':
                self.w(self.get('X0'), 'Q', self.cow(bytes(uc.mem_read(self.get('X1'), self.get('X2')))))
            elif a == 0x1de6fb8 and self.mode == 'path':
                destination = self.get('X0')
                old = self.cstr(self.r(destination, 'Q')[0])
                tail = bytes(uc.mem_read(self.get('X1'), self.get('X2')))
                self.w(destination, 'Q', self.cow(old + tail))
            elif a == 0xe87ca0 and self.mode == 'path':
                self.paths.append(self.cstr(self.get('X1')).decode('utf-8'))
                self.set('PC', self.EXIT)
                return
            elif a in (0xa7b5f8, 0xa7b618) and self.mode == 'path':
                self.set('W0', 0)  # Named OS mutex boundary, not native locking.
            else:
                return super().hook(uc, a, size, data)
            self.set('PC', self.get('X30'))

        def path_request(self, kind, *, flags, loaded_count=0, explicit=None):
            spec = TABLES[kind]
            slots = [a for a, target in self.relocations.items() if target == spec['load']]
            if len(slots) != 1:
                raise ValueError('Original table load vtable differs')
            vptr = slots[0] - 0x40
            # Explicit isolated table header. The original virtual +0x10
            # reads its backend +0xa4 count; this is not a full constructor.
            table = self.alloc(0x110)
            self.w(table, 'Q', vptr)
            self.w(table + 0xa4, 'I', loaded_count)
            argument = 0 if explicit is None else self.cow(explicit.encode())
            self.paths = []
            self.mode = 'path'
            try:
                result = self.call(spec['load'], {'X0': table, 'X1': argument, 'W2': flags})
            finally:
                self.mode = None
            return {'table': kind, 'flags': flags, 'loadedCountFixture': loaded_count,
                    'explicitPathFixture': explicit, 'requestedPaths': list(self.paths),
                    'originalFileOpenExecuted': False, 'fileOpenSuccessSupplied': False,
                    'wholeLoaderExecuted': False,
                    'completeAlreadyLoadedEarlyReturn': not self.paths and result == 1}

        def read_row(self, kind, sources):
            from skill_attachments import decode_ftable
            spec = TABLES[kind]
            raw = sources.read('tables/' + kind + '.tbl')
            table = decode_ftable(raw, spec['key'])
            row = next(r for r in table['rows'] if r[spec['key']] == spec['id'])
            _, count, _, ids_at, _, rows_at, stride, pool, _ = struct.unpack_from('<9I', raw, 8)
            ids = struct.unpack_from('<' + 'I' * count, raw, ids_at)
            at = rows_at + ids.index(spec['id']) * stride
            record = raw[at:at + stride]
            self.table_raw, self.string_pool, self.string_spans, self.stream_events = raw, pool, [], []
            data = self.alloc(len(record))
            self.uc.mem_write(data, record)
            stream, context, output = self.alloc(0x30), self.alloc(0x100), self.alloc(0x200)
            self.uc.mem_write(output, b'\xa5' * 0x200)
            self.w(stream + 0x18, '2Q', data, data + len(record))
            source_stream, source_vtable = self.alloc(0x30), self.alloc(0x30)
            self.w(source_stream, 'Q', source_vtable)
            self.w(source_vtable + 0x18, 'Q', self.EXIT + 0x800)
            self.w(source_vtable + 0x20, 'Q', self.EXIT + 0x810)
            self.w(context + 0x88, 'Q', source_stream)
            self.w(context + 0x88 + 0x3c, 'I', len(raw))
            self.last_facade = context + 0x88
            # Original callers construct the string members before reading.
            # e881dc intentionally leaves a zero-length string unchanged.
            initial_at = output
            widths = {'u': 4, 'k': 4, 'i': 4, 'c': 1, 'h': 2, 'f': 4, 's': 8}
            for physical in table['physicalTypes']:
                if physical == 's':
                    self.w(initial_at, 'Q', self.cow(b''))
                initial_at += widths[physical]
            self.mode = 'row'
            try:
                accepted = self.call(spec['read'], {'X0': context, 'X1': stream, 'X2': output})
            finally:
                self.mode = None
            cursor = output
            fields = {}
            for name, physical in zip(table['columns'], table['physicalTypes']):
                fmt = {'u': 'I', 'k': 'I', 'i': 'i', 'c': 'B', 'h': 'H', 'f': 'f', 's': 'Q'}[physical]
                value = self.r(cursor, fmt)[0]
                if physical == 's':
                    value = self.cstr(value).decode('utf-8')
                if value != row[name]:
                    raise ValueError('Original row reader differs at ' + name)
                fields[name] = {'offset': cursor - output, 'value': value}
                cursor += struct.calcsize('<' + fmt)
            if accepted != 1 or self.r(stream + 8, 'Q')[0] != len(record):
                raise ValueError('Original reader did not consume the exact record')
            result = {'table': kind, 'sourceSHA256': hashlib.sha256(raw).hexdigest(),
                      'id': spec['id'], 'sourceBytes': len(record), 'runtimeBytes': cursor - output,
                      'fields': fields, 'allFieldsEqual': True, 'stringStorageProvider': True,
                      'originalStringSpanBodyExecuted': True,
                      'stringSpans': list(self.string_spans), 'sourceStreamCalls': list(self.stream_events),
                      'emptyStringHoldersSuppliedBeforeReader': True,
                      'scriptExecuted': False}
            if kind == 'quests':
                self.script_address = output + fields['script']['offset']
                pointer = self.r(self.script_address, 'Q')[0]
                before = self.r(pointer - 8, 'i')[0]
                self.mode, self.script_reads = 'destroy', []
                try:
                    self.call(0x3e78a4, {'X0': output})
                finally:
                    self.mode = None
                result['scriptReferenceRelease'] = {'reads': list(self.script_reads),
                    'researchRefcountBefore': before, 'researchRefcountAfter': self.r(pointer - 8, 'i')[0],
                    'function': '0x3e78a4', 'bodyLoadedOrCalled': False}
            return result

        def original_span_controls(self):
            results = []
            for offset, length in ((0, 0), (len(self.table_raw), 1)):
                holder = self.alloc(8)
                pointer = self.cow(b'unchanged')
                self.w(holder, 'Q', pointer)
                self.mode, self.stream_events = 'row', []
                try:
                    accepted = self.call(0xe881dc, {'X0': self.last_facade,
                        'W1': offset, 'W2': length, 'X3': holder})
                finally:
                    self.mode = None
                results.append({'offset': offset, 'length': length, 'result': accepted,
                    'holderUnchanged': self.r(holder, 'Q')[0] == pointer,
                    'textUnchanged': self.cstr(pointer) == b'unchanged',
                    'fileCalls': list(self.stream_events)})
            return results

    return ScriptEntryProbe


def run():
    from analyze_native_resources import NativeImage
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE
    image = NativeImage(SO.read_bytes())
    engine = probe_type()(image)
    requests = []
    for kind in TABLES:
        for flags, loaded, explicit in ((0, 0, None), (4, 0, None),
                                        (0, 0, 'research/explicit-table.tbl'),
                                        (0, 1, None), (1, 1, None)):
            requests.append(engine.path_request(kind, flags=flags, loaded_count=loaded, explicit=explicit))
    sources = Sources(DEFAULT_SOURCE)
    rows = [engine.read_row(k, sources) for k in TABLES]
    return {'format': 'oc2-tutorial-script-table-entry-v2',
            'nativeSHA256': hashlib.sha256(image.data).hexdigest(),
            'pathRequests': requests, 'rows': rows,
            'originalStringSpanControls': engine.original_span_controls(),
            'originalScriptsLoaded': False, 'scriptVMFound': False,
            'scope': 'Original table-path prefix and exact native record readers; not script body loading',
            'savesOrProductionAccessed': False}


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    target = private_output(args.output)
    result = run()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'output': str(target), 'pathControls': len(result['pathRequests']),
                      'nativeRows': len(result['rows']), 'scriptsLoaded': False}))
