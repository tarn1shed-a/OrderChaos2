"""Original material selector cache writers, separate from source FX declarations.

The generic property-provider entry is not assumed to be the BDAE loader.
No runtime device state, queue flags or live sky is manufactured here.
"""
import argparse
import hashlib
import json
from pathlib import Path

from scene_sky_queue import verify_native as verify_queue, word
from scene_sky import analyze_sky

FORMAT = 'oc2-material-selector-cache-evidence-v1'
ROUTINES = {
    0x13ecc24: (316, 'e3a7b1829b75498706dd292892269a954dd7f31dcb62db0b2d60d24f7e178240'),
    0x13ed094: (172, '1b9d886bcf76e2e3117f3ad9bb3e6e540223cec609cd8cc0ffac8042e5d8a622'),
    0x13ed1fc: (220, 'a916fe21d494fdefde3661950768489602b51d5333f42ac0036f867d6d00dace'),
    0x13eda68: (568, '17aa432a28d14ad22cb94be7a15016b2423f2a1e33e2885b753d21c4b12b48ac'),
    0x140025c: (116, 'dcac546af847f16869649d2382f19949479796fc28f5e5fb79459ea696ecdc95'),
    0x1400310: (76, '7764e3e021464306598d41daf707d3dca036fb40e25b84f1760a71e9b5367946'),
}
STRINGS = {0x1f3d7a1: b'Base Technique\0', 0x1f3d7c2: b'Technique Modifiers\0',
           0x1f370bf: b'Group\0', 0x1fd62ca: b'Parameters\0'}


def verify_native(image):
    verify_queue(image)
    for at, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
            raise ValueError('Material cache writer/lookup code changed')
    for at, expected in STRINGS.items():
        if image.read(at, len(expected)) != expected:
            raise ValueError('Material property-provider field name changed')
    return {'routines': len(ROUTINES), 'providerFieldNames': len(STRINGS), 'appliedAsLiveState': False}


def reset_selector(base, shift):
    word(base, 8); word(shift, 8)
    return base & (((1 << (shift & 31))+0xff) & 0xffffffff)


def validate_table(names, feature_bits):
    # These are explicit pointer identities, not source strings or a file format.
    if (not isinstance(names, (tuple, list)) or not 0 <= len(names) <= 255 or
            type(feature_bits) is not int or not 0 <= feature_bits <= 5 or
            len(names)*(1 << feature_bits) > 255):
        raise ValueError('Expected bounded explicit grouped-name pointer table')
    for name in names: word(name, 64)


def lookup_name(names, feature_bits, name_pointer):
    """140025c, valid bounded table: compare interned pointers, first match wins."""
    validate_table(names, feature_bits); word(name_pointer, 64)
    if not name_pointer: return 0xff
    return next((i for i, value in enumerate(names) if name_pointer == value), 0xff)


def apply_selector(base, variation, names, feature_words, name_pointer,
                   group_nonempty=False, group_word=0):
    word(base, 8); word(variation, 8); word(group_word, 32)
    if not isinstance(feature_words, (list, tuple)) or type(group_nonempty) is not bool:
        raise ValueError('Expected explicit provider modifier/group inputs')
    for value in feature_words: word(value, 32)
    bits = len(feature_words)
    choice = lookup_name(names, bits, name_pointer)
    result = (reset_selector(base, bits) | ((choice << bits) & 0xffffffff)) & 0xff
    for i, value in enumerate(feature_words):
        if value & 1: result |= (1 << i)
        else: result &= (0xff ^ (1 << i))
    return {'baseByte': result, 'variationByte': (group_word & 0xff) if group_nonempty else variation,
            'baseOrdinal': choice}


def analyze_cache(image, extract):
    sky = analyze_sky(extract, image)
    return {'format': FORMAT, 'native': verify_native(image),
            'sourceDeclaration': {'sources': sky['sources'], 'techniqueByName': sky['material']['technique'],
                                  'providerBindingRecovered': False},
            'writers': {'constructor': {'target': '0x13ecc24', 'headerInput': 'X3',
                                        'base': 'uint16[X3] -> material+0x10',
                                        'variation': 'uint8[X3+8] -> material+0x18'},
                        'reset': {'target': '0x13ed094', 'variation': 0,
                                  'base': 'base & ((1 << (effect.byte1c & 31)) + 0xff), low8',
                                  'dirtyBytes1aTo1d': 'ffffffff'},
                        'copy': {'target': '0x13ed1fc', 'sameObject': 'return1, unchanged',
                                 'differentEffect': 'return0, unchanged',
                                 'sameEffect': 'copy bytes10/18; property/auxiliary handling follows'}},
            'providerApplication': {'target': '0x13eda68',
                                    'fields': [v[:-1].decode() for v in STRINGS.values()],
                                    'lookup': 'interned pointer equality; grouped 24-byte table entries',
                                    'missingBaseOrdinal': 255, 'modifierResult': 'low bit of virtual+0x1d8',
                                    'group': 'nonempty -> 13edca0 result low8; empty preserves byte18',
                                    'sourceBDAELoaderIdentityProven': False},
            'lookups': {'grouped': '140025c steps 1 << effect.byte1c; returns grouped ordinal',
                        'complete': '1400310 steps each 24-byte entry up to effect.byte1d',
                        'missing': 255, 'pointerIdentityNotStringComparison': True},
            'appliedAsLiveState': False,
            'limits': ['Material header input, effect counts/names, provider callbacks and group ID are explicit fixtures, not original active-device state.',
                       'Constructor/reset/copy execute with zero property count; constructor has null name. Property cleanup/fixup and named-material allocation remain pending.',
                       'Full 13eda68 body executes, but strlen, string interning, group lookup and Parameters application are explicit stub boundaries. No BDAE/provider identity is inferred.',
                       'Only bounded grouped tables with 0..5 modifier bits and total entries <=255 execute; malformed/wrapping loops are rejected by the tool, not claimed as native validation.',
                       'Source CurrentTechnique solid is preserved separately; the four generic provider field names do not prove its binding. Effect packed-word/driver profile/remapping and runtime technique+6/pass+e2 producers remain pending.',
                       'No queue sorting, GPU, matrices, HDR, live sky, converted assets, UI or private saves change.']}


def main():
    from analyze_native_resources import NativeImage
    from resource_packs import DEFAULT_SOURCE, ResourceArchive, index, normalize_resource_name
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--native', type=Path, default=Path('analysis/raw/beff-native/library.so'))
    cli.add_argument('--output', type=Path, default=Path('analysis/raw/sky-runtime-material/report.json'))
    args = cli.parse_args(); entries = {}; archives = {}
    for entry in index(args.source): entries.setdefault(normalize_resource_name(entry['path']), []).append(entry)
    def extract(name):
        matches = entries.get(normalize_resource_name(name), [])
        if len(matches) != 1: raise ValueError('Source missing or ambiguous: '+name)
        pack = matches[0]['pack']
        if pack not in archives: archives[pack] = ResourceArchive(args.source/pack)
        return archives[pack].read(name)
    report = analyze_cache(NativeImage(args.native.read_bytes()), extract)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'format': FORMAT, 'appliedAsLiveState': False}))


if __name__ == '__main__': main()
