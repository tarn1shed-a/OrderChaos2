"""Bounded original shader prefix injection, separate from live shader selection.

Original prefix bodies and source shaders are read locally, never embedded here.
The token rewriter, modern GLSL versions, device selection and GPU stay pending.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from scene_shader_metadata import verify_native as verify_metadata
from scene_material_cache import word

FORMAT = 'oc2-shader-prefix-injection-evidence-v1'
ROUTINES = {
    0x141de74: (168, '4e04572591031968ba3e7257ba625239183ffd2e4d0707650c1be8412d61d726'),
    0x1da989c: (28, 'e2b6601fd06bae532b04d276a749cdbbe4bf517e00c301f30a76ca3515ebc55e'),
    0x1494480: (264, 'bdeb95cb19a46da88584df32d17622e027de6495b120740d25616a9d0ec936b7'),
}
CONSTANTS = {
    0x1f4c256: (34, '3838ea2e20f3b7f419bd7a2474d35b9042f3106c23761d59b892623f09b69f88'),
    0x1f4c278: (63, '1680ad9ec3f431eb1c6c34430558ac640bec7d52cfd3ac0cc294f88d31b2bd0a'),
    0x1f4c2b7: (200, '5ec400ecf435e7ef122866eae7b29972d07c5d54aa44642d5207966b3e19709d'),
    0x1f4c37f: (36, '9d40da1901f19227b9f4e637caf24e6141b176e9d6cf314e556c666e89c4f712'),
    0x1f4c3a3: (18, 'a582120cc11463918189995e40459639407b7ab30235700fbf5ecea19d20ae87'),
    0x1f4c451: (15, '4c0af5c2fd52886cb20e5035dc7242817085fea359f330d3925a5540d24d51cb'),
    0x1f4c492: (155, 'b7d9a6fd5b6952df0ef780d268ee6aa7e3507a26b50fc2da2d02f5eac8fcdb1a'),
    0x1f4c52d: (26, '54b7f81a60e1a6140eaf1dbac5a147dd5efe9c182e2a3687c8fc8d51705dd0db'),
    0x1f4c547: (25, '59fb3ef28a5de75819b50a79b988efd8df5e6f5a75867b4c473937a40f38d092'),
    0x1f4c560: (31, 'e00ae450b7a3bd372152a8a2ab9c381b7c8b41635925ea54190dfa596a27b89d'),
    0x1f4c57f: (9, '0c6388da887d29bd5d1207f6105845aa08e7b207744addb7e8c163e7434399ec'),
    0x1f4fad3: (35, '47f1512b00213aa12a78c3f657fbcebd3d27655eacef74b37918090c4b08af97'),
    0x1f0c448: (1, '6e340b9cffb37a989ca544e6bb780a2c78901d3fb33738768511a30617afa01d'),
    0x1f3c5ec: (32, '501a85c7b4e2357bee24455a7eb76b5b6b80ea2a729aaec602613b663e19e384'),
    0x1f3df9d: (5, 'debc2f07db78d52d2def07b7bc620d7042367501d9439a62ba09b559a98e0957'),
    0x1f3e7ba: (9, '871738f1e0c5b17a758afe514c272c7209d8a678f8c64c98a0fa889cf58cfa4f'),
    0x1f3e7c3: (9, 'b36eb76b70f7fac8eb1742e76110cc983a76794ce295115260e14471f6a66b0d'),
    0x1f3e7cc: (8, '1b068dfc9eaddd61427c304ee7f88f6f0199e6f53e2a535a519337126b525e80'),
    0x1f3e7d4: (9, 'a138dd04baa8526859a52d42fdf224183871bf2d27a277d4a15e3c8b912bc80d'),
    0x1f3e7dd: (9, '2fde2ea2ab96d5d6d765aa59229951411fb13655cebac84a5c77e1397524b722'),
    0x1f3e7e6: (8, '2bb7f7450987622e78f3d39238c4e0a0a3ef86722b185c1563dfbe085afa8a8f'),
    0x1dfd321: (6, '98151954f217a510702d236de168cc35d0ab2f99c4479cc9b07eeede7ef73a66'),
    0x1f3cfde: (4, 'e7ddd3da3b5407c30cb46b26d5dd435ab4f37914261f699b11292f73447afe15'),
}
ALPHA_EXPRESSIONS = (0x1f3df9d, 0x1f3e7ba, 0x1f3e7c3, 0x1f3e7cc,
                     0x1f3e7d4, 0x1f3e7dd, 0x1f3e7e6, 0x1dfd321)
PREDICATES = ('always discard', 'a >= ref', 'a != ref', 'a > ref',
              'a <= ref', 'a == ref', 'a < ref', 'never discard')


def verify_native(image):
    verify_metadata(image)
    for at, (size, digest) in {**ROUTINES, **CONSTANTS}.items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
            raise ValueError('Original shader prefix code/constant changed')
    return {'newRoutines': len(ROUTINES), 'constants': len(CONSTANTS), 'appliedAsLiveState': False}


def prefix_plan(stage, flags=16, allow_alpha=1, alpha_func=2, extra=None):
    # Probe bounds: original supports more device/version/rewrite branches.
    if type(stage) is not int or not 0 <= stage <= 2: raise ValueError('Expected shader index0..2')
    word(flags, 32); word(allow_alpha, 8)
    if flags & ~0x37: raise ValueError('Only basic capability bits0/1/2/4/5 are covered')
    if type(alpha_func) is not int or not 0 <= alpha_func <= 7: raise ValueError('Expected AlphaFunc0..7')
    if extra is not None and (not isinstance(extra, bytes) or len(extra) > 96 or b'\0' in extra):
        raise ValueError('Expected bounded optional extra-prefix bytes')
    enabled = stage == 1 and not flags & 32 and bool(allow_alpha & 1)
    plan = [] if flags & 16 else ['version120', 'precision-compatibility']
    for bit, name in [(1, 'highp'), (2, 'bias'), (4, 'force-bias')]:
        if flags & bit: plan.append(name)
    if extra is not None: plan.append('extra')
    if enabled: plan.append('alpha-function')
    plan += ['alpha-uniform' if enabled and alpha_func not in (0, 7) else 'empty-alpha-uniform',
             'alpha-discard' if enabled else ('alpha-noop' if stage == 1 else 'empty'),
             'line1', 'source']
    return {'segments': plan, 'alphaEnabled': enabled,
            'discardPredicate': PREDICATES[alpha_func] if enabled else None,
            'normalizedVersion': 100 if flags & 16 else 120}


def source_view(source):
    if not isinstance(source, bytes) or len(source) > 8192 or b'\0' in source:
        raise ValueError('Expected bounded original or fixture source bytes')
    try: source.decode('ascii')
    except UnicodeError as error: raise ValueError('Only ASCII source fixtures are covered') from error
    explicit = re.match(rb'#version (?:100|120)\r?\n', source)
    if source.startswith(b'#version') and not explicit:
        raise ValueError('Only explicit100/120 or context-default versions are covered')
    return (b'//'+source[2:] if explicit else source)+b'\n'


def constant(image, at):
    return image.read(at, CONSTANTS[at][0]-1)


def expected_segments(image, source, stage, flags=16, allow_alpha=1, alpha_func=2, extra=None):
    plan = prefix_plan(stage, flags, allow_alpha, alpha_func, extra); body = source_view(source)
    pointers = {'precision-compatibility': 0x1f4c492, 'highp': 0x1f4c52d, 'bias': 0x1f4c547,
                'force-bias': 0x1f4c560, 'alpha-uniform': 0x1f4c278, 'empty-alpha-uniform': 0x1f4c256,
                'alpha-discard': 0x1f4c2b7, 'alpha-noop': 0x1f4c37f, 'empty': 0x1f0c448, 'line1': 0x1f4c57f}
    values = []
    for name in plan['segments']:
        if name == 'version120': value = constant(image, 0x1f4c451) % (120, b'')
        elif name == 'alpha-function':
            value = constant(image, 0x1f4fad3)+constant(image, ALPHA_EXPRESSIONS[alpha_func])+b'\n'
        elif name == 'extra': value = extra
        elif name == 'source': value = body
        else: value = constant(image, pointers[name])
        values.append(value)
    return values


def source_shaders(extract):
    from scene_sky import SOURCE_HASHES
    result = []
    for stage, name in enumerate(('sky_box_vs.glsl', 'sky_box_fs.glsl')):
        data = extract(name)
        if hashlib.sha256(data).hexdigest() != SOURCE_HASHES[name]: raise ValueError('Original sky shader changed')
        source_view(data); result.append({'stage': stage, 'name': name, 'data': data})
    return result


def analyze_preprocess(image, extract):
    shaders = source_shaders(extract)
    return {'format': FORMAT, 'native': verify_native(image),
            'sources': [{'name': row['name'], 'stage': row['stage'], 'bytes': len(row['data']),
                         'sha256': hashlib.sha256(row['data']).hexdigest()} for row in shaders],
            'alphaGate': 'stage==1 AND context.wordC.bit5==0 AND stack8.bit0==1',
            'independentSwitches': {
                'alphaPermission': '148c160 entrySP+8 <-1424d2c incomingSP+8 <-141d368 W3.bit0',
                'tokenRewrite': '148c160 entrySP+18 <-1424d2c key[-4]==0 (or descriptor absent:true)'},
            'uniformGate': 'enabled AND AlphaFunc not0/7', 'discardPredicates': list(PREDICATES),
            'features': {'wordC.bit0': 'GLITCH_USE_HIGHP', 'bit1': 'GLITCH_USE_BIAS', 'bit2': 'GLITCH_FORCE_USE_BIAS'},
            'orderedSegments': 'version/compatibility, capability defines, optional caller prefix, alpha function, uniform macro, alpha macro, line marker, source',
            'execution': ['full148c160 with rewrite stack18=0', '141de74 expression selector',
                          '1da989c original intrusive list insertion', '1494480 empty macro-map lookup',
                          '148ca60 complete cleanup for produced allocations/source mutations'],
            'fixtures': ['allocator/free and bounded sscanf/sprintf/strncpy bodies',
                         'explicit shader index/capabilities/AlphaFunc/allow/extra-prefix/default version inputs'],
            'coveredVersions': 'context defaults100 GLES /120 desktop and explicit100/120; basic capability mask37 only',
            'tokenRewriterExecuted': False, 'activeSkyInputsRecovered': False, 'GPUExecuted': False,
            'appliedAsLiveState': False,
            'limits': ['This proves original prefix construction and cleanup under explicit bounded inputs; no browser shader replacement or GPU compilation occurs.',
                       '14836bc token rewriting, modern version/UBO paths, nonempty macro maps, error formatting and device-selected inputs remain pending.',
                       'A discard macro definition is not proof of a call site, active macro expansion or actual pixel discard. Source shaders do not select metadata bits.',
                       'Actual file.map and effect/profile/modifier inputs remain missing or unclosed. Never apply fixture capabilities/AlphaFunc as original live sky state.',
                       'Original prefix/source text and full execution output remain in ignored local reports, with no runtime/UI/art/private-save changes.']}


def main():
    from analyze_native_resources import NativeImage
    from resource_packs import DEFAULT_SOURCE, ResourceArchive, index, normalize_resource_name
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--native', type=Path, default=Path('analysis/raw/beff-native/library.so'))
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--output', type=Path, default=Path('analysis/raw/shader-preprocess/report.json'))
    cli.add_argument('--execute', action='store_true', help='Write controlled original-source execution output locally')
    args = cli.parse_args(); entries = {}; packs = {}
    for row in index(args.source): entries.setdefault(normalize_resource_name(row['path']), []).append(row)
    def extract(name):
        found = entries.get(normalize_resource_name(name), [])
        if len(found) != 1: raise ValueError('Missing or ambiguous original shader: '+name)
        entry = found[0]; pack = entry['pack']
        if pack not in packs: packs[pack] = ResourceArchive(args.source/pack)
        return packs[pack].read(name)
    image = NativeImage(args.native.read_bytes()); report = analyze_preprocess(image, extract)
    if args.execute:
        from native_shader_preprocess_probe import NativeShaderPreprocessProbe
        probe = NativeShaderPreprocessProbe(image); cases = []
        for row in source_shaders(extract):
            for flags in (0, 16):
                for allow in (0, 1):
                    for alpha in (0, 2, 7):
                        result = probe.preprocess(row['data'], row['stage'], flags, allow, alpha)
                        if result['segments'] != expected_segments(image, row['data'], row['stage'], flags, allow, alpha):
                            raise ValueError('Original-source prefix mismatch')
                        cases.append({'source': row['name'], 'fixtureFlags': flags, 'fixtureAllow': allow,
                                      'fixtureAlphaFunc': alpha, 'sourceRestored': result['sourceRestored'],
                                      'segments': [s.decode('ascii') for s in result['segments']]})
        report['controlledOriginalSourceCases'] = cases
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'format': FORMAT, 'cases': len(report.get('controlledOriginalSourceCases', [])),
                      'appliedAsLiveState': False}))


if __name__ == '__main__': main()
