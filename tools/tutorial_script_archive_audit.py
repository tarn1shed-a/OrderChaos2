"""Bounded audit of original script-search container coverage.

This does not rescan all GBMP payloads. It reuses the frozen full-search evidence,
indexes source metadata, and opens only format-backed nested SWF/audio/config
candidates. Original bytes and decoded local settings remain private.
"""
import argparse
import collections
import hashlib
import json
import re
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'analysis/raw/tutorial-script-archive-20261115/v2'
AUDIT_NAME = 'audit-v2.json'
NEEDLES = (
    'tutorial_quest202', 'tutorial_npc972_ai', 'tutorial_obj188_trigger',
    'tutorial_obj190_khalin_hammer', 'Skill240_OnSkillHit', 'Skill228_OnSkillHit',
)
sha = lambda b: hashlib.sha256(b).hexdigest()


def hits(data):
    return [{'name': n, 'encoding': enc, 'offset': at}
            for n in NEEDLES for enc in ('ascii', 'utf-16-le', 'utf-16-be')
            if (at := data.find(n.encode(enc))) >= 0]


def expand_swf(data):
    """Use the observed FWS/CWS format, never try speculative transforms."""
    if len(data) < 13 or data[:3] not in (b'FWS', b'CWS'):
        raise ValueError('Not an observed original SWF format')
    length, = struct.unpack_from('<I', data, 4)
    if not 13 <= length <= 32 * 1024 * 1024:
        raise ValueError('Invalid or unbounded SWF length')
    if data[:3] == b'CWS':
        dec = zlib.decompressobj()
        body = dec.decompress(data[8:], length - 8 + 1)
        if not dec.eof or dec.unused_data or len(body) != length - 8:
            raise ValueError('Invalid CWS zlib checksum/extent')
        data = b'FWS' + data[3:8] + body
    if len(data) != length:
        raise ValueError('SWF declared length mismatch')
    return data


def swf_actions(data):
    from ui_assets import Bits, tags
    bits = Bits(data, 8)
    bits.rect()
    counts = collections.Counter()

    def visit(start, end, depth=0):
        if depth > 32:
            raise ValueError('Unbounded nested sprite')
        for kind, at, size in tags(data, start, end):
            if kind in (12, 59, 72, 82, 300):
                counts[kind] += 1
            elif kind == 39:
                if size < 4:
                    raise ValueError('Truncated DefineSprite')
                visit(at + 4, at + size, depth + 1)
    visit(bits.pos() + 4, len(data))
    return dict(counts)


def optimized_abc_metadata(data):
    """Include this client's real tag300; no bytecode execution or VM claims."""
    from ui_assets import Bits, tags
    from character_portraits import decode_abc_metadata
    bits = Bits(data, 8)
    bits.rect()
    rows = []
    def visit(start, end, depth=0):
        if depth > 32:
            raise ValueError('Unbounded nested sprite')
        for kind, at, size in tags(data, start, end):
            if kind == 39:
                if size < 4:
                    raise ValueError('Truncated sprite')
                visit(at + 4, at + size, depth + 1)
            elif kind == 300:
                payload = data[at:at + size]
                split = payload.find(b'\0', 4)
                if split < 4:
                    raise ValueError('Invalid original optimized-ABC wrapper')
                name = payload[4:split].decode('utf-8')
                abc = payload[split + 1:]
                row = {'wrapperName': name, 'bytes': len(abc), 'sourceSHA256': sha(abc)}
                try:
                    meta = decode_abc_metadata(abc)
                    row.update({'constantPoolDecoded': True, 'version': meta['version'],
                        'strings': len(meta['strings']), 'multinames': len(meta['multinames']),
                        'constantPoolBytes': meta['constantPoolBytes'],
                        'unparsedMethodBytes': meta['unparsedMethodBytes'],
                        'targetNamePoolHits': [n for n in NEEDLES
                            if any(n in s for s in meta['strings'] + meta['multinames'])]})
                except ValueError as error:
                    row.update({'constantPoolDecoded': False, 'failure': str(error)})
                rows.append(row)
    visit(bits.pos() + 4, len(data))
    return rows


def swf_audit(source, entries):
    from resource_packs import read_entry
    rows = []
    for entry in entries:
        if not entry['path'].lower().endswith('.swf'):
            continue
        original = read_entry(entry, source)  # Outer GBMP size and CRC mandatory.
        decoded = expand_swf(original)
        rows.append({'pack': entry['pack'], 'path': entry['path'],
            'outerCRCValidated': True, 'magic': original[:3].decode('ascii'),
            'bytes': len(original), 'decodedBytes': len(decoded),
            'sourceSHA256': sha(original), 'expandedSHA256': sha(decoded),
            'actionTagCounts': swf_actions(decoded),
            'optimizedABC': optimized_abc_metadata(decoded), 'hits': hits(decoded)})
    return {'count': len(rows), 'magicCounts': dict(collections.Counter(r['magic'] for r in rows)),
        'newlyExpandedCount': sum(r['magic'] == 'CWS' for r in rows),
        'filesWithActionTags': sum(bool(r['actionTagCounts']) for r in rows),
        'filesWithStandardActionTags': sum(any(k != 300 for k in r['actionTagCounts']) for r in rows),
        'filesWithOptimizedABC': sum(300 in r['actionTagCounts'] for r in rows),
        'optimizedABCBlocks': sum(len(r['optimizedABC']) for r in rows),
        'optimizedABCMetadataFailures': [{'path': r['path'], 'block': block}
            for r in rows for block in r['optimizedABC'] if not block['constantPoolDecoded']],
        'optimizedABCNamePoolHits': [{'path': r['path'], 'block': block}
            for r in rows for block in r['optimizedABC'] if block.get('targetNamePoolHits')],
        'hits': [r for r in rows if r['hits']], 'rows': rows,
        'actionExecution': False, 'scope': 'UI bytecode container only; not quest approval'}


def native_local_config(image, data):
    """Execute the actual two block functions and verify exact re-encoding.

    Native callers a7a430/a7aaf4 fix 0x4000 bytes, 8-byte stride, rounds16,
    byte-order flag0 and the key at 1e662e0. No source file is written.
    """
    from source_physics import SourcePhysics
    if len(data) != 0x4000:
        raise ValueError('Original local-settings reader requires exactly 0x4000 bytes here')
    engine = SourcePhysics(image)  # Only memory/ABI runner; no physics entry is called.
    context, inp, out = engine.alloc(32), engine.alloc(8), engine.alloc(8)
    engine.w(context, 'II', 16, 0)
    engine.uc.mem_write(context + 8, image.read(0x1e662e0, 16))
    decoded, back = bytearray(), bytearray()
    for at in range(0, len(data), 8):
        engine.uc.mem_write(inp, data[at:at + 8])
        engine.call(0xa7a978, {'X0': context, 'X1': inp, 'X2': out})
        block = bytes(engine.uc.mem_read(out, 8))
        decoded.extend(block)
        engine.uc.mem_write(inp, block)
        engine.call(0xa7ad64, {'X0': context, 'X1': inp, 'X2': out})
        back.extend(engine.uc.mem_read(out, 8))
    if bytes(back) != data:
        raise ValueError('Original decode/encode did not reproduce source bytes')
    text = bytes(decoded).split(b'\0', 1)[0]
    lines = text.splitlines()
    if not lines or not all(b' ' in line for line in lines if line):
        raise ValueError('Decoded bytes do not match original key/value parser')
    return bytes(decoded), {'bytes': len(data), 'sourceSHA256': sha(data),
        'decodedSHA256': sha(decoded), 'roundTripMatchesOriginal': True,
        'plaintextLengthBeforeNul': len(text), 'lineCount': len(lines),
        'allNonemptyLinesHaveKV': True, 'hits': hits(decoded),
        'valuesExcludedFromReport': True, 'originalBlockFunctions': ['0xa7a978', '0xa7ad64']}


def vox_directory(data):
    """Read the directory extents consumed by original 15c0418.

    Both source directory copies are checked here. This is not a recovered audio
    payload decoder or an assertion about unresolved header checksum fields.
    """
    if len(data) < 128 or data[:8] != b'Voxarch1':
        raise ValueError('Not the original audio archive header')
    count, names_length = struct.unpack_from('<II', data, 16)
    table_a, table_b, names_a, names_b, strings = struct.unpack_from('<5I', data, 24)
    if not 0 < count < 100000 or not 0 < names_length < 16 * 1024 * 1024:
        raise ValueError('Unbounded original audio directory')

    def span(start, size):
        if start < 128 or start + size > len(data):
            raise ValueError('Audio directory range exceeds source archive')
        return data[start:start + size]

    rec_a, rec_b = span(table_a, count * 16), span(table_b, count * 16)
    idx_a, idx_b = span(names_a, count * 4), span(names_b, count * 4)
    names = span(strings, names_length)
    if rec_a != rec_b or idx_a != idx_b:
        raise ValueError('These two source audio directories no longer match; review native mode selection')
    rows = []
    for i, (hashed, size, offset) in enumerate(struct.iter_unpack('<QII', rec_a)):
        pos, = struct.unpack_from('<I', idx_a, i * 4)
        if pos >= len(names):
            raise ValueError('Audio name index exceeds original string region')
        end = names.find(b'\0', pos)
        if end < 0 or end - pos > 2048:
            raise ValueError('Unterminated original audio member name')
        name = names[pos:end].decode('ascii')
        if not name or offset + size > len(data):
            raise ValueError('Audio member range exceeds source archive')
        rows.append({'name': name, 'hash64': f'{hashed:016x}', 'offset': offset,
            'bytes': size, 'head8': data[offset:offset + min(8, size)].hex(),
            'hits': hits(data[offset:offset + size])})
    return {'count': count, 'sourceBytes': len(data), 'sourceSHA256': sha(data),
        'directoryCopiesIdentical': True, 'allNamesAndPayloadExtentsValidated': True,
        'extensions': dict(collections.Counter(Path(r['name']).suffix for r in rows)),
        'hits': [r for r in rows if r['hits']], 'rows': rows,
        'CRCValidated': False,
        'integrityBoundary': 'No decoded-payload CRC field has been recovered for Voxarch1; bounds and source SHA only'}


def native_vox_validate(image, data, directory):
    """Native magic and filename-hash lookup, with host byte-stream ABI only.

    Directory words are copied unchanged from source. Every source name must
    resolve to its exact source ordinal through original 15c0d54; no fake return
    from the original lookup or hash function is installed.
    """
    from source_physics import SourcePhysics
    from unicorn import UC_HOOK_CODE

    class ContainerProbe(SourcePhysics):
        BYTE_READ = 0x30000800
        def __init__(self, source_image):
            super().__init__(source_image)
            self.uc.hook_add(UC_HOOK_CODE, self.hook, begin=self.BYTE_READ, end=self.BYTE_READ)
            self.uc.hook_add(UC_HOOK_CODE, self.hook, begin=0x15761b8, end=0x15761b8)
            self.audio_stream, self.audio_vtable = self.alloc(32), self.alloc(64)
            self.w(self.audio_stream, 'Q', self.audio_vtable)
            self.w(self.audio_vtable + 0x10, 'Q', self.BYTE_READ)
        def hook(self, uc, at, size, userdata):
            if at == self.BYTE_READ:
                amount = self.get('W2') * self.get('W3')
                chunk = self.input_bytes[:amount]
                uc.mem_write(self.get('X1'), chunk)
                self.set('W0', len(chunk))
                self.set('PC', self.get('X30'))
            elif at == 0x15761b8:
                # Diagnostics after range extraction, never a lookup result.
                self.set('PC', self.get('X30'))
            else:
                super().hook(uc, at, size, userdata)

    engine = ContainerProbe(image)
    engine.input_bytes = data[:128]
    valid = engine.call(0x15c0ffc, {'X0': engine.audio_stream})
    engine.input_bytes = b'?' + data[1:128]
    bad_magic = engine.call(0x15c0ffc, {'X0': engine.audio_stream})
    engine.input_bytes = data[:127]
    short = engine.call(0x15c0ffc, {'X0': engine.audio_stream})
    if (valid, bad_magic, short) != (1, 0, 0):
        raise ValueError('Original Voxarch1 magic consumer disagrees')
    count, = struct.unpack_from('<I', data, 16)
    table_offset, = struct.unpack_from('<I', data, 24)
    actor, table, name, ordinal, off, length = [engine.alloc(n) for n in (160, count * 16, 2049, 4, 4, 4)]
    engine.uc.mem_write(table, data[table_offset:table_offset + count * 16])
    engine.w(actor + 8, '4B', 1, 0, 0, 1)
    engine.w(actor + 0x28, 'I', count)
    engine.w(actor + 0x30, 'Q', table)
    engine.uc.mem_write(actor + 0x70, data[44:52])
    for i, row in enumerate(directory['rows']):
        engine.uc.mem_write(name, row['name'].encode('ascii') + b'\0')
        found = engine.call(0x15c0d54, {'X0': actor, 'X1': name, 'X2': ordinal})
        if found != 1 or engine.r(ordinal, 'I')[0] != i:
            raise ValueError('Native hash lookup disagrees with source name directory')
        found = engine.call(0x15c0e88, {'X0': actor, 'X1': name, 'X2': off, 'X3': length})
        if found != 1 or engine.r(off, 'I')[0] != row['offset'] or engine.r(length, 'I')[0] != row['bytes']:
            raise ValueError('Native archive member range disagrees with source directory')
    engine.uc.mem_write(name, b'__audit_missing_tutorial_script__.lua\0')
    missing = engine.call(0x15c0d54, {'X0': actor, 'X1': name, 'X2': ordinal})
    if missing != 0:
        raise ValueError('Original archive lookup unexpectedly accepted missing name')
    return {'originalHeaderConsumer': '0x15c0ffc', 'validHeader': valid == 1,
        'badMagicRejected': bad_magic == 0, 'shortHeaderRejected': short == 0,
        'originalHashLookup': '0x15c0d54', 'originalRangeGetter': '0x15c0e88',
        'allMemberNamesOrdinalsAndRangesNativeVerified': count,
        'missingNameRejected': True,
        'boundaries': ['host stream/allocations/diagnostics',
            'original directory copied from source; no live Android mount or audio payload decompression',
            'CRC/checksum semantic fields remain unverified; do not report cryptographic integrity']}


def manifest_groups(data, source):
    groups = collections.defaultdict(list)
    for value in data.decode('utf-8').splitlines():
        name = re.sub('/+', '/', value.replace('\\', '/')).removeprefix('./')
        base = re.sub(r'\.split_\d+$', '', name)
        groups[base].append(name)
    rows = []
    for base, values in groups.items():
        exact = source / base
        mapped = None
        # Preserve the literal log entry. These are explicit directory-string
        # differences in this export, not a generic resource-name rewrite.
        if not exact.is_file():
            if base.startswith('sound2') and '/' not in base:
                mapped = source / 'sound2' / base[len('sound2'):]
            elif base.startswith('ui/Font') and base.count('/') == 1:
                mapped = source / 'ui/Font' / base[len('ui/Font'):]
        rows.append({'literalBase': base, 'splitCount': sum('.split_' in n for n in values),
            'exactFilePresent': exact.is_file(),
            'explicitExportPathCandidate': str(mapped.relative_to(source)) if mapped else None,
            'candidatePresent': mapped.is_file() if mapped else False,
            'sourceManifestDoesNotSupplyIntegrityForMergedFile': True})
    return {'lineCount': sum(map(len, groups.values())), 'groupCount': len(rows), 'rows': rows,
        'absentAfterExplicitExportPathComparison': [r for r in rows if not r['exactFilePresent'] and not r['candidatePresent']]}


def dlc_metadata(source):
    result = {}
    for name, key in [('DLC_Info.json', 'DLCpack'), ('DLC_UniversalPack.json', 'UniversalPack')]:
        data = (source / name).read_bytes()
        groups = json.loads(data)[key]
        identifiers = sorted({n for row in groups.values() for n in row['files']})
        result[name] = {'sourceSHA256': sha(data), 'groupCount': len(groups),
            'uniqueFileIdentifiers': len(identifiers), 'identifiers': identifiers,
            'tutorialAndSelectionGroups': {k: row for k, row in groups.items()
                if any(n in row.get('worldname', []) for n in ('tutorial.wld', 'selection.wld'))},
            'boundary': 'Original DLC identifiers are not assumed to be filesystem paths; no downloads or mount success inferred'}
    return result


def loose_text_audit(source):
    # These are actual original text/config inputs with observed text headers;
    # do not apply this list to OF_PP.bin/InitialFeed.dat or guess their codec.
    names = ('ControllerConfig.xml', 'ControllerSpecifics.xml', 'DLC_Info.json',
             'DLC_UniversalPack.json', 'snsconfig.json', 'preloadTextures.txt',
             'd_o_w_n_l_o_a_d_e_d.txt', 'sound2/project_info.json')
    rows = []
    for name in names:
        data = (source / name).read_bytes()
        if name.endswith('.xml') and not data.startswith(b'<'):
            raise ValueError('Original XML header differs')
        if name.endswith('.json') and not data.lstrip().startswith(b'{'):
            raise ValueError('Original JSON header differs')
        rows.append({'path': name, 'bytes': len(data), 'sourceSHA256': sha(data), 'hits': hits(data)})
    return {'count': len(rows), 'bytes': sum(r['bytes'] for r in rows),
        'rows': rows, 'hits': [r for r in rows if r['hits']],
        'boundary': 'Literal bytes in known text inputs; no forced UTF8 conversion of legacy sound description bytes'}


def run(source, output):
    from resource_packs import index, ResourceArchive
    from analyze_native_resources import NativeImage, NATIVE_SHA256
    output = output.resolve()
    if not output.is_relative_to(ROOT / 'analysis/raw'):
        raise ValueError('All original and decoded evidence must remain private')
    output.mkdir(parents=True, exist_ok=True)
    entries = index(source)
    swf = swf_audit(source, entries)
    image = NativeImage((ROOT / 'analysis/raw/beff-native/library.so').read_bytes())
    decoded, local = native_local_config(image, (source / 'LocalConfig.cnfg').read_bytes())
    (output / 'local-config-decoded-private.bin').write_bytes(decoded)
    audio = {}
    for path in sorted((source / 'sound2').glob('*.voxpack')):
        data = path.read_bytes()
        directory = vox_directory(data)
        directory['native'] = native_vox_validate(image, data, directory)
        audio[path.name] = directory
    groups = manifest_groups((source / 'd_o_w_n_l_o_a_d_e_d.txt').read_bytes(), source)
    dlc = dlc_metadata(source)
    loose = loose_text_audit(source)
    for name, record in [('swf-inner-v2.json', swf), ('local-config-native-v2.json', local),
                         ('vox-directories-v1.json', audio), ('download-manifest-v2.json', groups),
                         ('dlc-metadata-v2.json', dlc), ('loose-text-v1.json', loose)]:
        (output / name).write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    report = {'format': 'tutorial-script-container-audit-v2', 'nativeSHA256': NATIVE_SHA256,
        'versionCorrection': 'v1 counted standard Action/DoABC tags only; v2 includes actual original tag300 optimized ABC and constant-pool metadata; v1 retained unchanged',
        'scope': 'metadata index + named original containers; original 39665-body scan not rerun',
        'GBMP': {'packCount': len({r['pack'] for r in entries}), 'records': len(entries),
            'fileCount': sum(not r['path'].endswith('/') for r in entries),
            'directoryCount': sum(r['path'].endswith('/') for r in entries),
            'topLevelOnly': True, 'originalIKPIndexContainsFilePayloads': False,
            'originalIndexChecks': {n: ResourceArchive(source / n).index_validation
                for n in sorted({r['pack'] for r in entries})}},
        'SWF': {k: swf[k] for k in ('count', 'magicCounts', 'newlyExpandedCount', 'filesWithActionTags',
            'filesWithStandardActionTags', 'filesWithOptimizedABC', 'optimizedABCBlocks',
            'optimizedABCMetadataFailures', 'optimizedABCNamePoolHits', 'hits')},
        'localConfig': local,
        'audio': {k: {f: v[f] for f in ('count', 'sourceBytes', 'directoryCopiesIdentical',
            'allNamesAndPayloadExtentsValidated', 'extensions', 'hits', 'CRCValidated')} for k, v in audio.items()},
        'downloadManifest': {k: groups[k] for k in ('lineCount', 'groupCount', 'absentAfterExplicitExportPathComparison')},
        'DLCWorldDependencies': dlc['DLC_Info.json']['tutorialAndSelectionGroups'],
        'knownLooseText': {k: loose[k] for k in ('count', 'bytes', 'hits')},
        'externalOBB': {'sourceRequestedBy': '38ab74 -> 3865b0 -> audioFS v20',
            'literal': 'main.31320.com.gameloft.android.ANMP.GloftO2HM.obb',
            'presentUnderExportRoot': any(source.parent.rglob('*.obb')),
            'containsQuestScripts': None, 'missingIsNotProofItWasRequiredInThisRun': True},
        'unknown': ['InitialFeed.dat supplied as initial data to ed1aac CrmManager; encoding not recovered here',
            'OF_PP.bin is a 156-byte non-GBMP loose file; original filename consumer/encoding not yet established',
            'Native-supported model ZIP inner directory/payloads not exhaustively inventoried by the former literal scan',
            'Android internal getFilesDir/Android/obb outside the supplied files export not observed',
            'DLC metadata describes optional packs; actual original download/mount state not observed'],
        'scriptBodyRecovered': False, 'gameRuntimeOrSaveChanges': False}
    (output / AUDIT_NAME).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'output': str(output / AUDIT_NAME),
        'GBMP': {k: report['GBMP'][k] for k in ('packCount', 'records', 'fileCount')},
        'SWF': report['SWF'], 'audioCounts': {k: v['count'] for k, v in audio.items()},
        'localConfigRows': local['lineCount'], 'scriptBodyRecovered': False}, ensure_ascii=False))
    return report


def main():
    from resource_packs import DEFAULT_SOURCE
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--output', type=Path, default=RAW)
    args = cli.parse_args()
    run(args.source, args.output)


if __name__ == '__main__':
    main()
