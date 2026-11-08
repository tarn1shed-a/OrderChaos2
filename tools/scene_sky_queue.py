"""Bounded technique selection and source queue3/8 routing/insertion evidence.

Runtime material/technique flag producers are not inferred from source FX GL
declarations. The distance-record branch stops at an explicit frontier; no
sorting, GPU consumption, HDR or live browser sky is installed here.
"""
import argparse
import hashlib
import json
from pathlib import Path

from scene_sky_material import verify_native as verify_material
from scene_sky import analyze_sky

FORMAT = 'oc2-sky-queue-insertion-evidence-v1'
ROUTINES = {
    0x13ed140: (188, '6d1ca4a264ada4d284442e25c94253af16f47f4c924b9ebc88d5b9fbf3b49f3b'),
    0x12f3c5c: (300, '86412ffbd81df999eece5cb93796e1fd847e0158261788504b7489c1c276a2f2'),
    0x132056c: (344, '3e9d593bd86da1d9545fc287517766810c62a32d528d89b8fd31b0b838c0e590'),
}


def verify_native(image):
    verify_material(image)
    for at, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
            raise ValueError('Sky technique/queue insertion code changed')
    return {'routines': len(ROUTINES), 'techniqueTarget': '0x13ed140',
            'queueTarget': '0x12f368c', 'appliedAsLiveState': False}


def word(value, bits):
    if type(value) is not int or not 0 <= value < 1 << bits:
        raise ValueError('Expected explicit source uint'+str(bits))
    return value


def technique_selection(base, variation, packed, profile, stride, remap):
    """13ed140 consumer, including W-register shift masking and wrap.

    Valid small explicit lookup tables only. Their shape/contents and driver
    profile are supplied inputs, not reconstructed original-device state.
    """
    base, variation, packed = word(base, 8), word(variation, 8), word(packed, 16)
    profile, stride = word(profile, 32), word(stride, 32)
    if remap is not None and (not isinstance(remap, bytes) or not 1 <= len(remap) <= 4096):
        raise ValueError('Expected bounded explicit technique lookup bytes')
    result, index = base, None
    if profile != 0xffffffff and remap is not None:
        shift = packed & 31  # ARM W-register variable shifts mask to 5 bits.
        profile_variation = (stride*profile+variation) & 0xffffffff
        index = ((((packed >> 8) >> shift) & 0xff)*profile_variation+(base >> shift)) & 0xffffffff
        if index >= len(remap): raise ValueError('Explicit technique lookup outside fixture')
        preserve = ((1 << shift)+0xff) & 0xffffffff
        result = (base & preserve) | ((remap[index] << shift) & 0xffffffff)
    return {'returnWord': result, 'queueIndex': result & 0xff, 'mapIndex': index,
            'lockCalls': 0 if profile == 0xffffffff else 2}


def queue_route(code, material=False, technique_flags=0, pass_byte_e2=0,
                scene_byte_2a8=0, node_word_210=0, node_word_200=0):
    """Legacy technique_flags argument is firstPass.byte6, not table-entry flags.

    Effect table entry+8 points to72-byte passes (verified by scene_sky_assembly).
    The numeric API is retained so previous bounded routing probes stay usable.
    """
    if code not in (3, 8) or type(code) is not int or type(material) is not bool:
        raise ValueError('Only source queue codes3/8 are covered')
    for v in (technique_flags, pass_byte_e2, scene_byte_2a8): word(v, 8)
    for v in (node_word_210, node_word_200): word(v, 32)
    if code == 8:
        return {'queueOffset': 0x88, 'recordBytes': 16, 'completed': True, 'selectorCalls': 0}
    calls = 0
    if material:
        calls = 1
        if technique_flags & 1 and scene_byte_2a8 == 0:
            return {'queueOffset': 0x160, 'recordBytes': 40, 'completed': False, 'selectorCalls': calls}
        calls = 2
        if pass_byte_e2 & 0x40:
            return {'queueOffset': 0x148, 'recordBytes': 32, 'completed': True, 'selectorCalls': calls}
    if node_word_210 & node_word_200 & 1:
        return {'queueOffset': None, 'recordBytes': 0, 'completed': True, 'selectorCalls': calls}
    return {'queueOffset': 0x130, 'recordBytes': 32, 'completed': True, 'selectorCalls': calls}


def analyze_queue(image, extract):
    sky = analyze_sky(extract, image)
    solid = [t for t in sky['effect']['profiles'][0]['techniques'] if t['name'] == sky['material']['technique']['name']][0]
    return {'format': FORMAT, 'native': verify_native(image),
            'sourceDeclaration': {'sources': sky['sources'], 'techniqueByName': sky['material']['technique'],
                                  'state': solid['state'], 'usedAsRuntimeQueueFlags': False},
            'selectedRecordIdentity': {'tableEntryBytes': 24, 'entryPlus8': '72-byte pass array',
                                       'legacyTechniqueFlags': 'firstPass.byte6; not table header',
                                       'passByteE2': 'firstPass+0x20 -> compiled program.byteE2',
                                       'producerEvidence': 'scene_sky_assembly; this older report does not derive source flags'},
            'techniqueSelector': {'target': '0x13ed140', 'baseByte': 'material+0x10',
                                  'variationByte': 'material+0x18', 'packedWord': 'effect+0x1c',
                                  'profileWord': 'driver+0x320', 'manager': 'driver+0x2f8',
                                  'strideWord': 'manager+0xa0', 'profileMinus1ReturnsBase': True,
                                  'queueUsesLow8OfReturn': True, 'argumentProducersRecovered': False},
            'queues': {'3': {'entry': '0x12f3788', 'plain32': 'scene+0x130', 'passBit6_32': 'scene+0x148',
                              'techBit0WithoutSceneByte_40': 'scene+0x160; execution frontier',
                              'node210And200LowBit': 'skip; original returns1'},
                       '8': {'entry': '0x12f3934', 'pairs16': 'scene+0x88'}},
            'records': {'32': ['node64', 'part64', 'material64', 'priority32', 'nodeTag32'],
                        '16': ['node64', 'part64'],
                        'prioritySentinel': '0x7fffffff selects node virtual+0x1e8',
                        'tagGetter': 'node virtual+0x58(part)', 'capacityGrowth': 'n+max(n,1)',
                        'nativeRefcountWritesInCoveredAppend': False},
            'appliedAsLiveState': False,
            'limits': ['Queue inputs and manager/remapping bytes are explicit fixtures. Material cache/profile/technique/pass flag producers and device override state remain pending.',
                       'Source named-solid FX GL declarations are reported separately. No assumption maps its depth/blend flags to runtime pass+0xe2 or technique+6.',
                       'Queue3/8 entry, real technique selector and 16/32-byte append/growth/copy/free execute. Node getters, mutex bodies and allocator are synthetic boundaries.',
                       'The scene+0x160 40-byte distance-record path is identified by original control flow but stops before insertion/distance computation. Other queue codes are outside this tool.',
                       'Only bounded valid containers and small lookup tables execute. Saturation/allocator failure, lifetimes, sorting/consumption, caller flags0xe/0xc/0xa, matrices, HDR and final sky sampling remain pending.',
                       'No browser/runtime/UI/art/converted resources or private saves are changed.']}


def main():
    from analyze_native_resources import NativeImage
    from resource_packs import DEFAULT_SOURCE, ResourceArchive, index, normalize_resource_name
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--native', type=Path, default=Path('analysis/raw/beff-native/library.so'))
    cli.add_argument('--output', type=Path, default=Path('analysis/raw/sky-queue/report.json'))
    args = cli.parse_args(); entries = {}; archives = {}
    for e in index(args.source): entries.setdefault(normalize_resource_name(e['path']), []).append(e)
    def extract(name):
        matches = entries.get(normalize_resource_name(name), [])
        if len(matches) != 1: raise ValueError('Source missing or ambiguous: '+name)
        pack = matches[0]['pack']
        if pack not in archives: archives[pack] = ResourceArchive(args.source/pack)
        return archives[pack].read(name)
    report = analyze_queue(NativeImage(args.native.read_bytes()), extract)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'format': FORMAT, 'appliedAsLiveState': False}))


if __name__ == '__main__': main()
