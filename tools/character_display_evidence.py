"""Pins for source character preview and name-display research.

No runtime profile or guessed original actor state is exported by this reader.
Complete original code, camera tables and reports remain private.
"""
import hashlib
from pathlib import Path

ROUTINES = {
    0x6181ec: (1072, '845e841471c301df7ac234b67fd8875832835862711e57a20b481cab6dc86b80'),
    0x619b10: (2620, '8443daa161cec83ec6cbbd5deea27ab9ba6110671d16097b8039c63c9a052bc0'),
    0x616564: (172, '4ae84ba590fe9d17ed7029983dda753d8594d8aa883d5c72a9257ee05a825dca'),
    0x61d870: (16296, '33e32e224f4f6c0af1bebe1fa8fae3f3dfc7b38f9781e410a26f74749af946cf'),
    0x62217c: (296, '85dccbed8934947bd4a9bc90a347c6d0771ccd1bbb17d27eb6727a365b00eb98'),
    0x12ba974: (688, 'a9025ae3bc5bedc153e4deada540761457358acfaa07a737d1c70bdabccd5aa9'),
    0x12baf08: (444, 'f7dad56e9ab923c2a86f6de5cd2c1d4103ef5a53500a95e4720ab37ecabc0db8'),
    0x13da1a8: (252, '06278ae10f339fe7fbf864b425d7b16f02c3632abf87dbf4a8cdbcbae01b147d'),
    0x11dd004: (504, '319cee3fb25ae28df19afdac10415a7e12a05eadeafc089160c3388ec3fe0975'),
    0x1414888: (2224, 'c81aa66ce682020a03c96a705cc9d04f1a3cecde377ee835f50d500eab0a2d3c'),
    0x8fe804: (132, '393ef1c29aefe7f3ee0c51b11675fcd1e166aa05f15dd7ce17bc201541673fc2'),
    0x909770: (124, 'fc8ec9dbeb53d0710bcd704c727217a49295d740b95b05daedd0073eac7396ef'),
    0x904fdc: (1176, 'a8a34fc89b0afccaa5bc5f19264c1f321ee8b05119ca85291908d32d9663f015'),
    0x9ec7c8: (3644, '0daa21bc08e926f30257c72c5d471aa025e1e0521355a35cb0b2ef62a5086ca9'),
    0x9dd168: (348, 'ea974dccbfb3ccdcec91992edd8c26b97b73bd5aa5ec8661f1f0c8f2ac23b79c'),
    0x900234: (5752, '337e2fbf7d2b5ed1b5c85a104b961ca74b1ca38f364b6de849d8b4d650b9c24f'),
}


def verify_native(image):
    for at, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
            raise ValueError('Original character display routine differs')
    rel = {r['r_offset']: r['r_addend'] for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()
           if r['r_info_type'] == 1027}
    for table, entries in {
        0x241b160: {0x98: 0x619b10},
        0x247e320: {0x340: 0x12baf08},
        0x24228a8: {0x2f8: 0x8fe804, 0x308: 0x909770},
        0x24222b8: {0x2f8: 0x9e9bc4},
    }.items():
        if any(rel.get(table+slot) != target for slot, target in entries.items()):
            raise ValueError('Original character display virtual dispatch differs')
    return {'routines': len(ROUTINES), 'originalAndroidStateObserved': False,
            'webPreviewReady': False, 'webNamesReady': False}


def model3d_evidence(read):
    from optimized_abc import extract_named_abc, parse_abc, named_method, disassemble
    raw = read('ui/Flash/MainUI.swf')
    block = extract_named_abc(raw, 'Common/gluicEx/components/ui/Model3D')
    if hashlib.sha256(block).hexdigest() != '9a30e0c4cdc6f085a5c340a15c2f19bad947676f0b055b780af3a108902c10ee':
        raise ValueError('Original Model3D changed')
    abc = parse_abc(block)
    for body in abc['bodies'].values():
        disassemble(body['code'], abc, body['exceptions'])
    cls = abc['classes'][0]
    return {'swfSHA256': hashlib.sha256(raw).hexdigest(),
            'abcSHA256': abc['sourceSHA256'], 'decodedBodies': len(abc['bodies']),
            'methods': {t['name']: {key: value for key, value in
                named_method(abc, cls['name'], t['name']).items() if key != 'instructions'}
                for t in cls['traits'] if 'method' in t}}


def main():
    import argparse
    import json
    from analyze_native_resources import NativeImage
    from resource_packs import ResourceArchive, DEFAULT_SOURCE
    from native_character_display_probe import CharacterDisplayProbe
    root = Path(__file__).resolve().parents[1]
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--native', type=Path, default=root/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so')
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    if not args.output.resolve().is_relative_to((root/'analysis/raw').resolve()):
        cli.error('Original research reports stay in ignored analysis/raw/')
    image = NativeImage(args.native.read_bytes())
    probe = CharacterDisplayProbe(image)
    record = {'format': 'oc2-source-character-display-research-v1',
              'native': verify_native(image),
              'model3D': model3d_evidence(ResourceArchive(args.source/'ui.bin').read),
              'lightConstructor': probe.light_defaults(),
              'projectionExamples': [dict(explicitInput={'aspect': a, 'fov': .7853981633974483,
                                                        'near': .1, 'far': 3000.},
                                          originalMatrix=probe.projection(aspect=a))
                                     for a in (.5, 1., 16/9)],
              'previewGates': {key: probe.preview_gate(**({key: False} if key != 'all' else {}))
                               for key in ('all', 'model', 'created', 'visible', 'texture')},
              'nameGates': [dict(flags=flags, relation=relation, selected=selected,
                                result=probe.name_gate(flags=flags, relation=relation, selected=selected))
                            for flags in (0, 0x40) for relation in (False, True) for selected in (False, True)],
              'unresolved': ['UI clone material variants and actual shader inputs',
                             'current actor name visibility/relation inputs and text projection',
                             'native RTT/GPU frame and complete browser preview integration'],
              'runtimeChanged': False, 'savesReadOrWritten': False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'runtimeChanged': False,
                      'nativeRoutines': len(ROUTINES), 'decodedModelBodies': record['model3D']['decodedBodies']}))


if __name__ == '__main__': main()
