"""Trace original map requests and tile residency, without generating a game.

Function labels and field descriptions are research labels. Pinned functions
include unread branches; hashes establish identity, not whole-function meaning.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from map_loading_evidence import Sources, verify_native as verify_loading
from skill_attachments import decode_ftable

ROOT = Path(__file__).resolve().parents[1]
ROUTINES = {
    0xa34f28: (6120, '696fe369680d77e7d54a7553d7909072e37ccd76f5c45192b96be5bbc9d96c38'),
    0xc99270: (8, '9f68aa97a5258a1e1fbe41f1226846f8b2e5cde4fa5f5b786f7a74d470a04298'),
    0xc88aa8: (212, '8d72102be9c22a4a2e59f36a75f99d5a5f2b150995542c9f737b4bdc53e0abe8'),
    0x3bb830: (12296, '66b21671ce1d7c411947e2c6580bc53b151c5ee21f522eb0a6b9dc116658315e'),
    0xc4277c: (12, '0c7038b04e3d0a56f44181ce2cc6a6ff4aa50edc6d7f9aee97fbb8a67514497e'),
    0xc4abf0: (8, '1ebb19eaea3bbc0205160d9a7467e11e2636ad9ac1e88e4cd761389a9591d5c0'),
    0xc62564: (56, 'e18d674a85841fcbbd74b938da0b688096f93f67a0a7615c2d9bf14315c1115c'),
    0x35b1a0: (100, '223068e51937845368d525a86a4c521219e1cca8f059cd3bd81eb1a59b6c1c06'),
    0x35b204: (296, 'f027de597edbb97328f767dcfce7ba3cf903c4a57d784a5d531f80809ffef983'),
    0x35b32c: (2104, '4ce4625a8d0f74ea4b24bb59048b554f35d370c1818575430786350f3b61b29d'),
    0xa6761c: (276, 'cf236b80559010d0ad59ffc332d130c79fd9ede9c12056a49ce55eb1f8de6204'),
    0xa678b8: (588, 'e9df73cf82899bf8ba5b25c4ee57c96c832106c18f28bebb6210b9c0049bb51e'),
    0x366ca0: (1808, '9fb08e42e4198b6bd6c0ece6f4f851b14040ade8d21af420ffbe8f3450137e4d'),
    0x367684: (276, '8dc471f51378e46a9902c750545622eb5596f0efc3a5654490c3e15f76e32ecc'),
    0x35200c: (744, '2d764c85ace815b7fa483ca7d7f01182b6620e8465abf63069db324d9683c495'),
    0x35a6dc: (292, 'f0528dbd6f070f4436d15cfcae930d83590a0e0bb2a2a7cc68a0ae5512202a8f'),
    0x3412a0: (236, '0d3b7a8c20cc5ee50906341b87a99fa3b4ca54a27f469ebfa4a7dbe994f9a30d'),
    0x3673b0: (428, 'dcea6b6a61073d3ae6942e8f45178ecb7356da7bd4ae05af026a2cfe5741c5ac'),
    0x367884: (540, '2f475e3113a41fbdb8b4caa0e8874f58ce20d07b6057a7721feadafdecce81d8'),
    0xa5f518: (216, 'e6e2a9928337056b3043e5babadd93c5a6a85faf0abac329c7c5faae622a6e6f'),
    0xa61f34: (160, 'f8aba7962fd6891e763ddcd1c3eb9f120f54a318a114daa5ab09d3f963a6b7bb'),
    0x3664e0: (484, '86f7e8cc01ba4b7031c9ef32c614cc4dd78326b04384d7c9515ba3d95fad1dd9'),
    0x352354: (2836, '3858cdd6c57cb7c33c6aaefdffe6347e599ba42f8e6389a1b69f806058520ddd'),
    0x3a7bcc: (316, '3a61ad426303606523cb1b903f19880fbc0c91bacf79b8052f0041fbf2f66683'),
    0xa62c90: (428, '163d295f14fd546f02d9a9067376f34b2d2b4902d4f8708f4697b225a6fc3773'),
    0x35a5e8: (244, '276384c5b53c9445666031a7a562bbbea5e9bb5e8a32a7bd22e291e3ee87d848'),
    0x3668dc: (724, '8751641151a0ab5267054028d0949dd4f5f5f403c0b1e44af7d8377f6b7f9014'),
    0x4d7c04: (112, '89cd1ab263ea5eb37264de98d7ffd6fbca9bf7c778804c151b885fc53f65c99c'),
}
CALLS = {
    0xa35848: (0xc99270, 'bl'), 0xa358a4: (0x29f4e0, 'bl'),
    0x3bbd10: (0xc4277c, 'bl'), 0xc42784: (0xc4abf0, 'b'),
    0xc4abf4: (0xc62564, 'b'), 0x35b1f8: (0x35b204, 'bl'),
    0xa67678: (0x35b1a0, 'bl'), 0xa67688: (0x35b32c, 'bl'),
    0x53967c: (0x366ca0, 'bl'), 0xa679dc: (0x366ca0, 'bl'),
    0x367224: (0x367684, 'bl'), 0x367764: (0x35200c, 'bl'),
    0x367794: (0x35a6dc, 'b'), 0x35a7fc: (0x3412a0, 'b'),
    0x367508: (0x3668dc, 'bl'), 0x36751c: (0x367884, 'bl'),
    0x367a30: (0xa5f518, 'bl'), 0x367a7c: (0xa61f34, 'b'),
    0xa61fbc: (0x3412a0, 'bl'), 0x366e8c: (0x3664e0, 'bl'),
    0x3665c0: (0x352354, 'bl'), 0x36661c: (0x352354, 'bl'),
    0xa62ccc: (0x336d70, 'bl'),
    0x5395d8: (0x4d7c04, 'bl'),
}


def verify_native(image):
    verify_loading(image)
    for address, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(address, size)).hexdigest() != digest:
            raise ValueError(f'Original streaming routine changed: {address:#x}')
    for at, (target, kind) in CALLS.items():
        word, = struct.unpack('<I', image.read(at, 4))
        expected = 0x94000000 if kind == 'bl' else 0x14000000
        if word & 0xfc000000 != expected:
            raise ValueError('Original streaming call/branch kind changed')
        delta = word & 0x3ffffff
        if delta & (1 << 25):
            delta -= 1 << 26
        if at + delta * 4 != target:
            raise ValueError('Original streaming call target changed')
    strings = {0x1dfd818: 'TerrainTileSight',
               0x1dfde06: 'TerrainTileSight            => %d'}
    for at, value in strings.items():
        if image.read(at, len(value)+1) != value.encode()+b'\0':
            raise ValueError('Original terrain radius key changed')
    rels = {r['r_offset']: r['r_addend'] for r in
            image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    for at, target in {0x240df18: 0x354ca0, 0x2423fb8: 0xa60a60,
                       0x2423f50: 0xa62c90}.items():
        if rels.get(at) != target:
            raise ValueError('Original terrain/item task update slot changed')
    return {'routines': len(ROUTINES), 'callEdges': len(CALLS),
            'taskUpdateVtables': {'0x240df18': '0x354ca0', '0x2423fb8': '0xa60a60',
                                 '0x2423f50': '0xa62c90'},
            'scope': 'static bytes, calls and relocations; not full original process execution'}


def analyze(image, source):
    native = verify_native(image)
    sources = Sources(source)
    maps = decode_ftable(sources.read('tables/map_info.tbl'), 'map_id')
    native_format = image.read(0x1ef0c8d, 128).split(b'\0')[0].decode('ascii')
    if native_format != maps['physicalTypes']:
        raise ValueError('Source map table and native record format differ')
    # The native c88aa8 prefix is packed; strings occupy eight runtime bytes.
    prefix_offsets, offset = {}, 0
    for name, kind in zip(maps['columns'], maps['physicalTypes']):
        prefix_offsets[name] = offset
        if name == 'file':
            break
        if kind not in 'ufis':
            raise ValueError('Map record prefix width needs separate native recovery')
        offset += 8 if kind == 's' else 4
    if prefix_offsets.get('file') != 0x40:
        raise ValueError('Map filename offset differs from original producer')
    tutorials = [r for r in maps['rows'] if r['file'] == 'world/tutorial.wld']
    if len(tutorials) != 1:
        raise ValueError('Original tutorial association is ambiguous')
    config = json.loads(sources.read('options/GO_ios.json'))
    overrides = []
    def visit(value, path):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == 'TerrainTileSight':
                    overrides.append({'sourcePath': path+[key], 'value': child})
                visit(child, path+[key])
        elif isinstance(value, list):
            for i, child in enumerate(value):
                visit(child, path+[i])
    visit(config, [])
    return {
        'format': 'oc2-map-streaming-evidence-v1', 'native': native, 'sources': sources.proofs,
        'mapRequest': {'producer': '0xa35840-0xa35900 within 0xa34f28',
                       'parsedNestedObjectMapKey': '+0x28 (wire name/dispatch not recovered)',
                       'tableGetter': '0xc99270: manager+0x78',
                       'nativeTableFormatMatchesSource': True, 'runtimeFilenameOffset': '0x40',
                       'tutorialMapId': tutorials[0]['map_id'], 'tutorialFile': tutorials[0]['file'],
                       'writes': {'requestPath': 'global context+0xe4', 'mapId': '+0xc8',
                                  'position': '+0x164/+0x168/+0x16c', 'reloadFlag': '+0xb9'}},
        'radius': {'sourceKey': 'TerrainTileSight', 'lookupFallbackArgument': 2,
                   'fallbackConsumer': '0xc62564 keeps w2 if key is absent',
                   'field': 'config+0x38 -> 0x2527a70',
                   'offsetCount': '(2*R+1)^2', 'cacheSide': '2*R+2', 'cacheSlots': '(2*R+2)^2',
                   'sourceConfigOverrides': overrides, 'actualAndroidValueObserved': False,
                   'configCaveat': 'GO_ios.json profiles are not selected as Android runtime settings'},
        'residency': {'center': 'floor(float32(x/z)) arithmetic-shift by manager+0x4c + manager+0x50',
                      'constructorShiftWords': [3, 3],
                      'shiftCaveat': 'Constructor inputs are known; complete writer/override inventory is not asserted',
                      'loadOffsets': 'Original 0x35b204 ring order; not a fabricated square traversal',
                      'retainDistanceBranch': 'abs(tileX-centerX)<=R+1 AND abs(tileZ-centerZ)<=R+1',
                      'guards': ['center/map-context-key change', 'caller arg2.bit0 / arg3.bit0 and manager+0x48/+0x58',
                                 'primary/pending slot state', 'source center-tile mask and phase candidates'],
                      'tileArrays': {'resident': 'manager+8', 'pending': 'manager+0x10'},
                      'publish': '0x3673b0 moves completed pending tiles then 0x367884 requests building tasks',
                      'unload': '0x3664e0 handles task IDs/cancel state, detach/defer of buildings, and 0x352354 cleanup'},
        'gaps': ['Network message name/opcode and complete dispatch/parse/default branches are unconfirmed.',
                 'Actual device radius/profile, all shift writers and live center getter types are unobserved.',
                 'Complete phase table semantics and center-tile skip-mask producer are not closed.',
                 'Enqueue/cancel edges do not prove all worker scheduling and completion races.',
                 'No game runtime, reconstructed map, replacement streaming policy or actual device state is produced.']}


def main():
    from analyze_native_resources import NativeImage
    from resource_packs import DEFAULT_SOURCE
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--native', type=Path, default=ROOT/'analysis/raw/beff-native/library.so')
    cli.add_argument('--output', type=Path, default=ROOT/'analysis/raw/map-streaming-20261108/evidence.json')
    cli.add_argument('--probe', action='store_true', help='Run bounded original fragments with explicit fixtures')
    args = cli.parse_args()
    if not args.output.resolve().is_relative_to((ROOT/'analysis/raw').resolve()):
        cli.error('Original research output must remain in ignored analysis/raw/')
    image = NativeImage(args.native.read_bytes())
    result = analyze(image, args.source)
    if args.probe:
        from native_map_streaming_probe import NativeMapStreamingProbe
        p = NativeMapStreamingProbe(image)
        result['fragmentExperiments'] = {
            'inputsAreFixtures': True, 'allocationIsStubbed': True,
            'offsetTables': [p.offsets(r) for r in (0, 1, 2)],
            'centers': [{'inputXZ': [x, z], 'tileXZ': p.center(x, z)}
                        for x, z in [(-2752, 128), (-0.01, 63.99), (-64.01, -64), (64, 64)]],
            'retention': [{'tile': t, **p.retain_distance_branch([0, 0], t, 2)}
                          for t in [[3, 3], [-3, -3], [4, 0], [0, -4]]],
            'notExecuted': ['actual settings/profile selection', 'world/asset loading',
                            'complete streaming/scheduler/unload state', 'original game process']}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'routines': result['native']['routines'],
                      'callEdges': result['native']['callEdges'], 'actualDeviceValueObserved': False}))


if __name__ == '__main__':
    main()
