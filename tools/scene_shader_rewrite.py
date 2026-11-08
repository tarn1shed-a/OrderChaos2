"""Original token tables and bounded property-name rewriting, without live GL.

Source/prefix bytes and native tables remain local. Uniform-block expansion,
other property keys and runtime-selected inputs are explicitly separate work.
"""
import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import re

from scene_shader_preprocess import (verify_native as verify_prefix, source_view,
                                     expected_segments as prefix_segments, source_shaders)

FORMAT = 'oc2-shader-property-rewrite-evidence-v1'
ROUTINES = {
    0x14836bc: (5496, 'f2dec731cbdb2ff06cc96fd89042fa4ce711c1dd464d26198a1ad35765ac7c5b'),
    0x1484cd0: (8, '4bc015890630bc5092fceea76bc90c1134b48c4b845ed8ad2a2c2eb13eb20621'),
    0x1484ce8: (88, 'e1b8eec6fca58e9fce5c8ab19287b1fdaff43030c25716d34d179d67a1bfeaf1'),
    0x14902f8: (236, 'b2e400e04545a4fd87fcb6a80bbe8aabc6d21488b231a0ac74b26750914d9337'),
    0x14903e4: (212, 'c57a47cbff8e2cffd511b8969855be0651d334fe70835942b6d0c43fd421e4b7'),
}
TABLES = {
    0x1f4fbac: (256, '39278a63e310a3285110b6164dff2e21147386468c5860d366256b99efb09f41'),
    0x1f4fcac: (100, '6e8549c1d31738cd6ea739479418b806ea0e59ce425c93ccff5fa7f0eee7a292'),
    0x1f4fd10: (100, 'b57130f50da643a65eda0a706603acf5ba116c634e81368618d1c40258c882e4'),
    0x1f4fd74: (100, '42e01dea4e843471bf77a4f78516e389421bc43f19518d2ba23586a084a472d0'),
    0x1f42388: (28, '22b81eeb1353bdfc68f441fab4637a482729354ca56c5689c8eb2b4b8f02f7fe'),
    0x1f4fdd8: (256, '51d0a1ee52442db5cbc2ee686c71ea448f71c0d6a274f35a7d83f7b0c3b553b0'),
    0x1f4fed8: (51, 'ae962ebb8f5ea23bf2623ba533eaf7d191e4250bdf4ccbbb639ef19e3626b328'),
    0x1f4ff0b: (51, 'aa99274d9b57ec674c5dddf00fe2e36b6de638b00a4219308efb63420702dc05'),
    0x1f4ff3e: (51, '335b2674545de1599916c0cb9ffca95197e6327b289f2bfe455ef31b0d10c68d'),
    0x1f4ff71: (256, 'ab23b779ea07b054dd30ce0dbe006352f576a232c4fc3a06d0c00d725ea1aeac'),
    0x1f50071: (9, 'c8a5c94901bc3d3734f4aea578c155dfe9f46bb7f30918c0a2217a78b8eef8f9'),
    0x1f5007a: (9, '47e4ee7f211f73265dd17658f6e21c1318bd6c81f37598e20a2756299542efcf'),
    0x1f50083: (9, 'f8348e0b1df00833cbbbd08f07abdecc10c0efb78829d7828c62a7f36d0cc549'),
    0x1f423a4: (40, 'b7f92cd620fa5c1f0ccb876c5db75f77d3e315f7c19675b9b1c13440ac6e59ee'),
    0x1f4a177: (13, '25cfdc11785af44604a51b5a008efb4ea8c38f9069480cecf5680d2885456831'),
}
PROPERTY_SOURCE = 'UnlitTexturedFP.glsl'
PROPERTY_SHA = 'efa8375dd4438d8004c5269f6364428f871f0440c10e405a8eb9a0509f4585a8'
BLOCK_MARKERS = ('GLITCH_IN_BLOCK', 'GLITCH_UNIFORM_BLOCK', 'GLITCH_BEGIN_UNIFORM_BLOCK', 'GLITCH_END_UNIFORM_BLOCK')
IDENTIFIER = rb'[A-Za-z_][A-Za-z0-9_]*'
PROPERTY_MARKER = re.compile(rb'GLITCH_(?:UNIFORM|ATTRIBUTE)_PROPERTIES')
PROPERTY_RECORD = re.compile(rb'(GLITCH_(UNIFORM|ATTRIBUTE)_PROPERTIES)\s*\(\s*('+IDENTIFIER+rb')\s*,\s*\(([^()]*)\)\s*\)')


def verify_native(image):
    verify_prefix(image)
    for at, (size, digest) in {**ROUTINES, **TABLES}.items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
            raise ValueError('Original shader rewriter code/table changed')
    return {'routines': len(ROUTINES), 'tablesAndConstants': len(TABLES), 'appliedAsLiveState': False}


def machine(image, base, count):
    return tuple(image.read(at, size) for at, size in [(base, 256), (base+256, count),
                 (base+256+count, count), (base+256+2*count, count)])


def validate_machine(tables):
    if not isinstance(tables, (list, tuple)) or len(tables) != 4: raise ValueError('Expected four FSM tables')
    if any(not isinstance(row, bytes) for row in tables): raise ValueError('Expected immutable FSM bytes')
    classes, labels, targets, siblings = tables; count = len(labels)
    if (len(classes) != 256 or not 1 <= count <= 255 or len(targets) != count or len(siblings) != count or
            any(v > count for v in targets) or any(v >= count for v in siblings)):
        raise ValueError('Invalid bounded FSM table layout')


def fsm_step(tables, origin, char):
    classes, labels, targets, siblings = tables; state = origin
    for _ in range(len(labels)+1):
        if classes[char] == labels[state]:
            # Original dispatch retains the incoming state, even after a sibling match.
            return (0, origin) if targets[state] == len(labels) else (targets[state], None)
        state = siblings[state]
        if state == origin: return 0, None
    raise ValueError('FSM sibling cycle does not return to its origin')


def discover_tokens(tables):
    validate_machine(tables); pending = deque([(0, b'')]); seen = {0}; found = {}
    while pending:
        state, path = pending.popleft()
        for char in range(32, 127):
            target, accepted = fsm_step(tables, state, char)
            if accepted is not None: found.setdefault(accepted, (path+bytes([char])).decode('ascii').rstrip(' '))
            if target not in seen:
                seen.add(target); pending.append((target, path+bytes([char])))
    return found


def property_spans(source):
    """Independent bounded model for semantic/texcoord annotations only.

    Experiment guards are stricter than native syntax. Like the native scanner,
    this does not interpret GLSL comments, strings or preprocessor conditions.
    """
    source_view(source)
    if any(name.encode() in source for name in BLOCK_MARKERS): raise ValueError('Block expansion is outside this probe')
    records = []
    for token in PROPERTY_MARKER.finditer(source):
        match = PROPERTY_RECORD.match(source, token.start())
        if match is None or len(records) >= 8: raise ValueError('Uncovered property annotation shape/count')
        name = match[3]; values = {}
        for entry in match[4].split(b','):
            field = re.fullmatch(rb'\s*(semantic|texcoord)\s*=\s*('+IDENTIFIER+rb')\s*', entry)
            if field is None or field[1] in values or (match[2] == b'ATTRIBUTE' and field[1] != b'semantic'):
                raise ValueError('Only unique semantic/texcoord identifier properties are covered')
            values[field[1]] = field[2]
        if len(name) > 64 or any(len(v) > 64 for v in values.values()): raise ValueError('Bounded property identifiers required')
        text = b'#define '+name+b' '+name+b'_glitchprops'
        for key, tag in [(b'semantic', b'_sem'), (b'texcoord', b'_tc')]:
            if key in values: text += tag+values[key]
        records.append({'start': match.start(), 'end': match.end(), 'text': text, 'owned': 1})
    return records


def expected_rewrite(image, source, stage=1, flags=16, allow_alpha=1, alpha_func=2, extra=None, enabled=True):
    if type(enabled) is not bool: raise ValueError('Expected explicit rewrite switch')
    validated = property_spans(source); spans = validated if enabled else []
    segments = prefix_segments(image, source, stage, flags, allow_alpha, alpha_func, extra)
    body = segments.pop(); cursor = 0
    for row in spans:
        segments += [body[cursor:row['start']], row['text']]; cursor = row['end']
    return segments+[body[cursor:]]


def rewrite_sources(extract):
    rows = source_shaders(extract); data = extract(PROPERTY_SOURCE)
    if hashlib.sha256(data).hexdigest() != PROPERTY_SHA: raise ValueError('Original property shader changed')
    property_spans(data); rows.append({'name': PROPERTY_SOURCE, 'stage': 1, 'data': data})
    return rows


def analyze_rewrite(image, extract):
    rows = rewrite_sources(extract)
    return {'format': FORMAT, 'native': verify_native(image),
            'recognizedMarkers': discover_tokens(machine(image, 0x1f4fbac, 100)),
            'recognizedUniformKeys': discover_tokens(machine(image, 0x1f4fdd8, 51)),
            'recognizedAttributeKeys': discover_tokens(machine(image, 0x1f4ff71, 9)),
            'sources': [{'name': row['name'], 'bytes': len(row['data']), 'sha256': hashlib.sha256(row['data']).hexdigest(),
                         'modeledPropertyRecords': len(property_spans(row['data']))} for row in rows],
            'execution': ['148c160 stack18=1 ->complete14836bc', '1484cd0 allocation adapter',
                          '14902f8 successful delimiter parsing', '1484ce8 original48-byte insertion record ->1da989c',
                          '148c160 source-array reconstruction', '148ca60 source restoration and allocation cleanup'],
            'recordLayout': {'size': 48, 'start': 16, 'end': 24, 'text': 32, 'ownedByte': 40},
            'fixtures': ['allocator/free, bounded C-copy/stdio and ASCII isalpha/isalnum/isspace bodies',
                         'basic capability/default version/alpha/extra-prefix inputs; empty macro map, rewriter modeW1=0'],
            'skyObservedRewrites': 0, 'automaticSkyAlphaCallInserted': False,
            'activeSkyInputsRecovered': False, 'GPUExecuted': False, 'appliedAsLiveState': False,
            'limits': ['Original sky shaders pass through this rewriter unchanged; prefix assembly still adds its controlled definitions. Never infer an active HasDiscard metadata bit from that result.',
                       'The decoded marker set describes block/property forms, not alpha-call insertion. An explicit GLITCH_ALPHA_TEST call in fixture source is preserved, not newly generated.',
                       'Only semantic/texcoord property-name expansion is independently modeled. Other recognized uniform keys and structural/uniform-block expansion, UBO mode1 and error formatting remain pending.',
                       'The scan is not treated as a general GLSL lexer: comments, quoted strings and preprocessor branches are not evaluated by this bounded model.',
                       'Actual file.map, caller capabilities/alpha/profile/modifier values, modern version paths, reflection, binding and GPU remain unclosed. No browser/runtime/UI/art/save changes.']}


def main():
    from analyze_native_resources import NativeImage
    from resource_packs import DEFAULT_SOURCE, ResourceArchive, index, normalize_resource_name
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--native', type=Path, default=Path('analysis/raw/beff-native/library.so'))
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--output', type=Path, default=Path('analysis/raw/shader-rewrite/report.json'))
    args = cli.parse_args(); entries = {}; packs = {}
    for row in index(args.source): entries.setdefault(normalize_resource_name(row['path']), []).append(row)
    def extract(name):
        found = entries.get(normalize_resource_name(name), [])
        if len(found) != 1: raise ValueError('Missing/ambiguous original shader: '+name)
        row = found[0]; pack = row['pack']
        if pack not in packs: packs[pack] = ResourceArchive(args.source/pack)
        return packs[pack].read(name)
    image = NativeImage(args.native.read_bytes()); report = analyze_rewrite(image, extract)
    from native_shader_rewrite_probe import NativeShaderRewriteProbe
    probe = NativeShaderRewriteProbe(image); cases = []
    for row in rewrite_sources(extract):
        for flags in (0, 16):
            for allow in (0, 1):
                result = probe.rewrite(row['data'], row['stage'], flags, allow)
                if (result['segments'] != expected_rewrite(image, row['data'], row['stage'], flags, allow) or
                        not result['sourceRestored'] or result['remainingAllocations']):
                    raise ValueError('Original-source rewrite/cleanup mismatch')
                cases.append({'source': row['name'], 'fixtureFlags': flags, 'fixtureAlphaAllow': allow,
                              'records': [{**r, 'text': r['text'].decode()} for r in result['records']],
                              'segments': [s.decode('ascii') for s in result['segments']], 'sourceRestored': True})
    report['controlledOriginalSourceCases'] = cases
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'format': FORMAT, 'cases': len(cases), 'appliedAsLiveState': False}))


if __name__ == '__main__': main()
