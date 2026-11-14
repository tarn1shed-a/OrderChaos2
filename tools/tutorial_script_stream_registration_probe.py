"""Read-only original InitialFeed filesystem-cache/mount source contract.

This verifies pinned native code and saved read-only Ghidra references. It does
not provide a file stream, pretend that an open succeeded, or replay Android
startup. Full source evidence stays private. Alias/path resolution is a separate
upstream contract; the cache below is not labelled as an alias table.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'analysis/raw/tutorial-script-stream-registration-20261115'
PINS = {
    0x54b2d4: (100, 'f0c5e4ae4183d21d4ed13caf20fa6e7826fed17c8aaf71ecfd1f83149a5b64f6'),
    0x54bc84: (748, '125450cb635a577fea5ea2a03f058265f4a7b35534214c828f12f0a6e64f800b'),
    0x54bf70: (528, '89637c5368b8a0b8be8147fa0219f8f5bb949cc3a30eaa2637c5e42abe2aa317'),
    0x54c180: (348, '4a569a45a9734e27972f9a74b1e5dd9980205b8ccc7b13945f4eb1a2615bd5d2'),
    0x54c2dc: (144, 'c4fd6aa7b508961ba5aad0cb46d033b1a5d22f9d7db8cec4ed4072d7939fe398'),
    0x54c36c: (52, '4611c59a27d39118ef3429f2d1f2d07104d75e042485c237ab78333af41c1882'),
    0x54b6c8: (172, '442f95e6a3f959f9c9de24327e6925160827b33e143d0ebe405dcf97f2d2bc11'),
    0x54b774: (172, '74fbf7440c2de40bac0ff117430ccf568567a8f8f85fe694b953c219c26ada2f'),
    0x54b820: (416, 'ae416e98e83b1a0763b620c9661a21f4a7023c12756a794251aa6e9b33f6944f'),
    0x54b9c0: (332, '57f5cdc5b9b2ce9a522a623236f0908d0635bb265fa09ee4066fb06867dfe238'),
    0x54bb0c: (236, 'a5e5b8bd0441253fb73afc4792e85826ad2aaafb9813ed6c46a9bf223bc9b6f5'),
    0x54bbf8: (140, '446be441f5870c4fd96e1eee4e1d04b1714290fc066324db9506fc6b648d59f3'),
    0x9dc308: (3680, '48dac70c5ec981f834498d12f335cfbe30e420c04fa2f9c25d115815671dee47'),
    0x9da8bc: (488, '74a90b7826130e8570f20ed84365ff04863f42d0bc146439a5ae7819ae47b651'),
    0x9daab4: (3336, '5de4e0afb3f8ea432eb4ef0abcc1f21eb034a9f98d1298a701a05c85bd689f20'),
    0x8f7a14: (1720, 'a4ca88ce5969d98aff954d14b79ad6e1daa9a24ade6e435599e623f0d2bc73a1'),
    0x8f8508: (1340, 'd0cde87d363feeb7076aedd8a06125ea94f9a720d6f7952174360d106c50c8b6'),
    0x8f9778: (1784, 'ea6a11de75684d64fc8615f53ed62de7a49805c6ac7c7cea06e9d94501517cbd'),
    0x8f8a44: (1180, 'd4f7dce21fd00111f66815e2793fbbab30135bca5026f4f599925b00bcc5d9cd'),
    0x8f8ee0: (1168, 'a20befd3f8684585633c63a06a0f3a86a471d0e9568907c71aaf2767ff853119'),
    0x8f9f8c: (1140, '8266ebd2ea3f4a213876e365e9dd2d142c063e30356a738d89ca1642c570e41b'),
}
CALLS = {0x54b2f0: 0x126fb94, 0x54bccc: 0x54bf70, 0x54bf68: 0x1270178,
         0x54c1a4: 0x54bf70, 0x54c21c: 0x55d400, 0x9dc398: 0x54c180,
         0x9dab38: 0x54c2dc, 0x8f9b24: 0x54b820, 0x8f8e10: 0x54b9c0,
         0x8f92a4: 0x54b9c0, 0x8fa2e0: 0x54bb0c, 0x8f9fe4: 0x54bbf8}


def section_at(image, address):
    for section in image.elf.iter_sections():
        if section['sh_addr'] <= address < section['sh_addr'] + section['sh_size']:
            return section.name
    return None


def saved_refs(image, path):
    from analyze_native_resources import NATIVE_SHA256
    data = json.loads(path.read_text())
    if data['program']['sha256'] != NATIVE_SHA256:
        raise ValueError('Saved Ghidra references are for another program')
    result = []
    for query in data['queries']:
        if query['request']['tool'] != 'get_xrefs_to':
            continue
        response = query['result']
        if response['has_more'] or response['total'] != len(response['items']):
            raise ValueError('Truncated native reference result')
        rows = []
        for row in response['items']:
            address = int(row['from'], 16)
            section = section_at(image, address)
            rows.append({**row, 'sourceSection': section,
                'unwindMetadataOnly': section in ('.eh_frame', '.eh_frame_hdr')})
        result.append({'target': query['request']['args']['address'], 'references': rows})
    return result


def inspect(image, raw=RAW):
    from analyze_native_resources import NATIVE_SHA256
    for address, (length, digest) in PINS.items():
        if hashlib.sha256(image.read(address, length)).hexdigest() != digest:
            raise ValueError('Original stream/cache/mount instructions differ: ' + hex(address))
    for address, expected in CALLS.items():
        word, = struct.unpack('<I', image.read(address, 4))
        delta = word & 0x3ffffff
        if delta & (1 << 25):
            delta -= 1 << 26
        if word & 0xfc000000 != 0x94000000 or address + delta * 4 != expected:
            raise ValueError('Original native producer call differs: ' + hex(address))
    relocations = {r['r_offset']: r['r_addend'] for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()
                   if r['r_info_type'] == 1027}
    expected_slots = {0x18: 0x54bc84, 0xd8: 0x54c3a0, 0x138: 0x54b6c8, 0x140: 0x54b774}
    if any(relocations.get(0x24160f0 + slot) != value for slot, value in expected_slots.items()):
        raise ValueError('Default project filesystem vtable differs')
    references = []
    for name in ('map-writers-xrefs-response-v1.json', 'mount-callers-response-v1.json', 'task-constructor-xrefs-v1.json'):
        references.extend(saved_refs(image, raw / name))
    result = {'format': 'tutorial-script-stream-registration-v1', 'nativeSHA256': NATIVE_SHA256,
        'verification': {'pinnedRoutines': len(PINS), 'directCalls': {hex(a): hex(t) for a, t in CALLS.items()},
            'filesystemVtable': {hex(a): hex(t) for a, t in expected_slots.items()},
            'execution': 'static original instructions and saved read-only Ghidra xrefs; no provider or Android execution'},
        'cache': {'ownerOffset': 'FS+e0 tree / header+e8', 'sourceConstructor': '54b2d4',
            'constructorStateOnly': {'root': 0, 'size': 0, 'mountedVectorsEmpty': True},
            'originalLookup': '54bf70', 'key': 'copied std::string bytes; memcmp and length comparison',
            'normalizationInThisLookup': None, 'notAnAliasOrDecoder': True,
            'producer': '54c180: lookup first; FS v18 open second; only non-null stream reaches55d400 insertion',
            'producerDirectCaller': '9dc308 state0 at9dc398',
            'producerFilenameSource': 'original task+40 vector indexed by task+1c; copied by9da8bc from caller arg5',
            'producerConstructorDirectSites': ['9010ec', '9017e0', '9e83b8', 'a55c6c'],
            'removeByStreamIdentity': '9daab4 ->54c2dc', 'clear': '54c36c',
            'actualInitialFeedRegistered': None, 'actualRuntimeCache': None},
        'openOrder': [
            {'field': 'cache+e8', 'consumer': '54bf70'},
            {'field': '+98', 'consumer': 'provider v18', 'writer': '54b820', 'knownProducer': '8f9778 patch packs'},
            {'field': '+b0', 'consumer': 'provider v18', 'writer': '54b9c0', 'knownProducer': '8f8a44/8f8ee0 texture segment packs'},
            {'field': '+c8', 'consumer': 'provider v18', 'writer': '54bb0c', 'knownProducer': '8f9f8c lightmap packs'},
            {'field': '+80', 'consumer': 'provider v18', 'writer': '54b774 FS v140', 'knownProducer': '8f7a14 base/hotfix packs;8f8508 textures'},
            {'field': '+28', 'consumer': 'provider v20', 'writer': '54b6c8 FS v138', 'knownProducer': None},
            {'field': '+40', 'consumer': 'provider v20', 'writer': None, 'knownProducer': None},
            {'field': '+58', 'consumer': 'provider v20', 'writer': None, 'knownProducer': None},
            {'field': '+78==0', 'consumer': '1270178 loose provider fallback'}],
        'sourceMountBranch': {'originalInitializer': '8f7a14',
            'baseOrder': ['hotfix.bin', 'res.bin', 'res_a.bin', 'ui.bin', '8f80cc', '8f8508'],
            'eachNamedPackGate': 'currentFS vD8 exists -> v18 actual open ->5565f0 archive constructor ->v140 mount',
            'sourceExistsNotActualOpenSuccess': True,
            'hotfixPresentInSuppliedFiles': (ROOT / 'game-data/com.gameloft.android.ANMP.GloftO2HM/files/hotfix.bin').is_file(),
            'hotfixContainsInitialFeedOrScript': None},
        'references': references,
        'missing': ['Actual selected factory/FS and upstream path-alias resolution (separate root-owned branch)',
            'Actual cache/provider state at8e3864; no call/name evidence links InitialFeed to54c180',
            'Ordering of these conditional resource initialization paths against actual8e3864 virtual invocation',
            'Any actual hotfix.bin bytes or a mount-success observation in the supplied original session',
            'The actual logical InitialFeed stream bytes/length/flags required by the prior envelope decoder'],
        'noOriginalOpenSuccessSupplied': True, 'noInputBytesInvented': True,
        'scriptBodyRecovered': False, 'runtimeSaveOrDeploymentChanged': False}
    return result


def main():
    from analyze_native_resources import NativeImage
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--library', type=Path, default=ROOT / 'analysis/raw/beff-native/library.so')
    cli.add_argument('--raw', type=Path, default=RAW)
    cli.add_argument('--output', type=Path, default=RAW / 'source-contract-v1.json')
    args = cli.parse_args()
    if not args.output.resolve().is_relative_to(ROOT / 'analysis/raw'):
        cli.error('Complete original references stay private')
    result = inspect(NativeImage(args.library.read_bytes()), args.raw)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'output': str(args.output), 'pinnedRoutines': len(PINS),
        'callsVerified': len(CALLS), 'actualInitialFeedStreamRecovered': False,
        'hotfixPresentInSuppliedFiles': result['sourceMountBranch']['hotfixPresentInSuppliedFiles']}))


if __name__ == '__main__':
    main()
