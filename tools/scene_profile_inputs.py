"""Original profile-input gates and scoped driver writes; device values pending."""
import argparse
import hashlib
import json
from pathlib import Path

from scene_effect_remapping import verify_native as verify_remapping
from scene_material_cache import word

FORMAT = 'oc2-driver-profile-input-evidence-v1'
ROOT_TAG = 'GLITCHTECHNIQUEMAPS'
VERSION = '0.0.2'
ROUTINES = {
    0x14098e4: (7588, '5c6fbc7c21492e66a0b4b3de2f067df6aab594539da44be4855ebce99a4478b4'),
    0x147f24c: (60, '7383fa56fe1097ad05820067b9e3c8af50517610c508b9d9afecea83e1d30080'),
    0x147f288: (44, 'a0f94226062d8d1e99eaa89a84b26cee1d3a73407755d53669ff77d39959e99d'),
    0x140b688: (260, '61e0645150312694fa85ed8d834e5e97ae8467e98edeec8bcdedb38432769b42'),
    0x12fc848: (52, 'e18d2fd16b97441d24d5de9b01c687d196dfd8f8aa32811e82db9f33fd460cc5'),
    0x12fc87c: (44, '641f6c7a1d69bd146813bc3a5abadd1333d655318bb1e46c5661a601c6b9a231'),
    0x12fce90: (52, '81c2018157ec90b319c93166b80992771524a7cc3b9bc72429c24c06c319c28e'),
    0x12fcec4: (44, '405d191576090131716eb2b83d4fea552d9841c3432a58e44e3fc42ead5166be'),
    0x1365e34: (176, '4f59d6fb2efc8e10c548fbf12bfc5fd43781211aa203a1d1fdcd21d1f674d22e'),
    0x1365ee4: (128, '7545e9ff864f09915de9c64b8a131c0784ff5c74f867683b82de6bec56da4b6a'),
}
STRINGS = {0x1f3f823: ROOT_TAG, 0x1f3f837: VERSION, 0x1f4c449: 'version'}


def verify_native(image):
    verify_remapping(image)
    for at, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != digest: raise ValueError('Profile-input code changed')
    for at, value in STRINGS.items():
        if image.read(at, len(value)+1) != value.encode()+b'\0': raise ValueError('Original profile-document keyword changed')
    return {'routines': len(ROUTINES), 'keywords': len(STRINGS), 'appliedAsLiveState': False}


def header_contract(tag=ROOT_TAG, version=VERSION, node_type=1, reader_word=1, document=True):
    word(node_type, 32); word(reader_word, 32)
    if type(document) is not bool: raise ValueError('Expected explicit parsed-document presence')
    for s in (tag, version):
        if s is not None and (not isinstance(s, str) or '\0' in s or len(s.encode()) > 64):
            raise ValueError('Expected bounded document header fixture')
    accepted = document and bool(reader_word & 1) and node_type == 1 and tag == ROOT_TAG
    return {'headerAccepted': accepted, 'messages': int(document and (not accepted or version != VERSION))}


def profile_after_load(previous, result_word):
    word(previous, 32); word(result_word, 32)
    return 0xffffffff if result_word & 1 else previous


def analyze_inputs(image):
    return {'format': FORMAT, 'native': verify_native(image), 'documentRoot': ROOT_TAG, 'runtimeVersion': VERSION,
            'loader': {'target': '14098e4', 'executedRange': 'entry to1409fc8 accepted header or1409b04/1409bb8 rejected/missing parsed node',
                       'versionMismatchIsHeaderWarning': True, 'fullParserExecuted': False,
                       'fieldCommitStaticOnly': '1409ec0..1409edc transfer temporary buffer/counts to registry88/90/98/A0/A8'},
            'driverWriters': ['147f24c calls loader and resets driver320 to-1 only when result.bit0 is1',
                              '147f288 calls clear delegate then unconditionally resets driver320 to-1',
                              '12fc848/12fc87c save driver320 at node3c, switch to node40, then restore',
                              '12fce90/12fcec4 save at node40, switch to node44, then restore',
                              'Original1365e34/1365ee4 parent bodies execute around driver virtual130/138 callbacks'],
            'limits': ['Header probe supplies one parsed node then EOF;1273160 parser and diagnostics bodies are callbacks. Accepted header is not full document-load success; header stops before cleanup.',
                       'Load/clear wrapper tests use explicit delegate-return fixtures, separately from header admission. Full14098e4 rule compilation and140b688 clearing are not executed by those wrappers.',
                       'Scene node target fields and initial driver value remain explicit fixtures. Actual nodes/active scene values, loaded configuration and rule counts are unobserved.',
                       'Parent render-state virtual push/pop bodies are callbacks. Original refcounts/active flag/scoped profile stores execute, not a real GL state stack.',
                       'Writer inventory is a candidate scan of unsigned-immediate STRW320, not complete alias/STP/STUR/memcpy/type evidence. No device-wide absence of configuration inferred. No runtime/UI/art/save changes.'],
            'actualDeviceRulesRecovered': False, 'activeSceneProfileRecovered': False,
            'shaderCompilerExecuted': False, 'GPUExecuted': False, 'appliedAsLiveState': False}


def main():
    from analyze_native_resources import NativeImage
    from native_profile_inputs_probe import NativeProfileInputsProbe
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--native', type=Path, default=Path('analysis/raw/beff-native/library.so'))
    cli.add_argument('--output', type=Path, default=Path('analysis/raw/effect-profile-loading/report.json'))
    args = cli.parse_args(); image = NativeImage(args.native.read_bytes()); p = NativeProfileInputsProbe(image)
    report = analyze_inputs(image)
    report['headerCases'] = [p.header(version=v) for v in (VERSION, None, 'different')]
    p.init_driver(7); report['loadWrapper'] = p.load_wrapper(1)
    report['scopeCases'] = []
    for kind in (0, 1):
        p.init_driver(0xffffffff); report['scopeCases'].append({'kind': kind, 'begin': p.push_profile(1, kind), 'end': p.pop_profile()})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'format': FORMAT, 'headerCases': 3, 'scopedPairs': 2, 'appliedAsLiveState': False}))


if __name__ == '__main__': main()
