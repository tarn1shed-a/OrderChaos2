"""Original effect table/pass assembly and the source blend-bit queue boundary.

Compiled programs and reflection tables remain explicit empty fixtures. Source
declarations are not treated as an observed active profile or GPU state.
"""
import argparse
import hashlib
import json
import struct
import tempfile
from pathlib import Path

from bdae_convert import BDAE
from scene_sky_binding import verify_native as verify_binding
from scene_material_cache import word
from scene_sky import EFFECT, SOURCE_HASHES, analyze_sky

FORMAT = 'oc2-sky-effect-pass-assembly-evidence-v1'
ROUTINES = {
    0x1400050: (524, 'c010c6f0742f0e53283a49636dd9af743fb85de108f65d51750e9defafb39dcc'),
    0x13feedc: (3372, '347264e47555d59f958aa4de093fed72e17aa2d8a9a8f50c263da48c1338c37b'),
    0x1488cd0: (108, 'd238aeb49c212f7994ba36c5f718df45f61837ccbb9b43ae6dcc9f239f68eb10'),
    0x148b650: (64, '4fe879373d53dc4932d2176733dcb12b888ede72146763d4fa0019eeb4bf8903'),
    0x114dd1c: (600, '9a77d4d5e4db7e6cbadde627c1536847f186cc710c96b0b884959bdd8ea28954'),
    0x1427c74: (296, 'a136c582991c305275bf67867804cb0b27c666b3bad9294b6e49e2324249da25'),
}


def verify_native(image):
    verify_binding(image)
    for at, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
            raise ValueError('Effect/pass assembly code changed')
    if image.read(0x1df7a84, 4) != struct.pack('<f', 255):
        raise ValueError('Source state color scale changed')
    return {'routines': len(ROUTINES), 'colorScale': 255, 'appliedAsLiveState': False}


def source_blend(source_state):
    if not isinstance(source_state, bytes) or len(source_state) != 88:
        raise ValueError('Expected explicit88-byte source render state')
    return bool(struct.unpack_from('<I', source_state, 12)[0] & (1 << 19))


def validate_assembly(techniques, modifier_names, effect_name, index):
    def name(value):
        if not isinstance(value, str) or '\0' in value or not 0 < len(value.encode()) <= 96:
            raise ValueError('Expected bounded explicit effect/modifier/technique name')
    name(effect_name); word(index, 16)
    if not isinstance(modifier_names, (list, tuple)) or len(modifier_names) > 5:
        raise ValueError('Expected0..5 explicit modifier names')
    for value in modifier_names: name(value)
    if not isinstance(techniques, list) or not 1 <= len(techniques) <= 8:
        raise ValueError('Expected1..8 explicit technique inputs')
    passes = 0
    for technique in techniques:
        if not isinstance(technique, dict) or set(technique) != {'name', 'passes'}:
            raise ValueError('Expected technique name/pass input')
        name(technique['name'])
        if not isinstance(technique['passes'], list) or not 1 <= len(technique['passes']) <= 3:
            raise ValueError('Expected1..3 explicit passes per technique')
        for record in technique['passes']:
            if not isinstance(record, dict) or set(record) != {'state', 'programWordE2', 'programByteDF'}:
                raise ValueError('Expected state and explicit program flag fixtures')
            if not isinstance(record['state'], bytes) or len(record['state']) != 28:
                raise ValueError('Expected original28-byte translated state')
            word(record['programWordE2'], 16); word(record['programByteDF'], 8)
            passes += 1
    if passes > 16: raise ValueError('Pass input exceeds bounded probe arena')
    return passes


def assembly_layout(techniques, modifier_names, effect_name='fixture-effect', index=0):
    count = validate_assembly(techniques, modifier_names, effect_name, index)
    return {'packedWord': len(modifier_names) | (len(techniques) << 8),
            'allocationBytes': 0x69+28*len(techniques)+72*count+8*len(modifier_names)+len(effect_name.encode()),
            'techniques': [{'name': t['name'], 'passCount': len(t['passes']),
                            'headerByte11': int(len(t['passes']) == 1 and bool(t['passes'][0]['programWordE2'] & 0x400)),
                            'firstPassBlendBit': (t['passes'][0]['state'][6] & 1),
                            'passCopyBits': [int(not bool(p['programByteDF'] & 4)) for p in t['passes']]}
                           for t in techniques]}


def source_states(extract):
    raw = extract(EFFECT)
    if hashlib.sha256(raw).hexdigest() != SOURCE_HASHES[EFFECT]:
        raise ValueError('Source sky effect changed')
    with tempfile.TemporaryDirectory(prefix='oc2-sky-assembly-') as temp:
        path = Path(temp)/EFFECT; path.write_bytes(raw); reader = BDAE(path)
        count, effect = reader.section(164)
        if count != 1: raise ValueError('Expected verified single sky effect')
        result = []
        for field in (32, 36):
            profile = reader.rel(effect+field); n, start = reader.u(profile), reader.rel(profile+4)
            if n != 3: raise ValueError('Source sky technique count changed')
            rows = []
            for i in range(n):
                at = start+24*i
                if reader.u(at+8) != 1: raise ValueError('Source sky pass count changed')
                state = reader.rel(at+12)+72
                rows.append({'name': reader.string(reader.q(at)), 'sourceState': reader.b[reader.at(state, 88):state+88]})
            result.append({'sourcePointerField': field, 'techniques': rows})
        return result


def analyze_assembly(image, extract):
    sky = analyze_sky(extract, image); profiles = source_states(extract)
    return {'format': FORMAT, 'native': verify_native(image), 'sources': sky['sources'],
            'sourceBlend': [{'sourcePointerField': p['sourcePointerField'],
                             'techniques': [{'name': t['name'], 'blend': source_blend(t['sourceState'])} for t in p['techniques']]}
                            for p in profiles],
            'identityCorrection': {'selectedTableEntry': 'effect+0x30, 24-byte entries',
                                   'entryPlus8': '72-byte pass array, not the24-byte table header',
                                   'queueLegacyTechniqueFlagsArgument': 'firstPass+6 byte; alias retained for compatibility',
                                   'queueOtherObject': 'firstPass+0x20 -> compiled program object',
                                   'programLabelIsResearchName': True,
                                   'independentHeaderFlag': 'entry+0x11 = (passCount==1) & firstProgram.wordE2.bit10'},
            'blendChain': ['source state word+0xc bit19', '114dd1c ->translated word+4 bit16 /byte6 bit0',
                           '1488cd0 copies28 bytes into each pass', '12f368c reads firstPass.byte6.bit0'],
            'assembly': {'factory': '1400050 ->13feedc', 'packedLowByte': 'modifier provider virtual10',
                         'packedHighByte': 'explicit technique input count', 'passRecord': '1488cd0;72 bytes',
                         'tableEntry': '148b650;24 bytes', 'sourceListNode': '1427c74 also uses1488cd0; static only'},
            'actualCompiledProgramFlagsRecovered': False, 'activeProfileRecovered': False,
            'appliedAsLiveState': False,
            'limits': ['Full effect allocation/construction executes with explicit modifier interface/names, technique/pass inputs and empty ordinary/global/reflection/binding arrays. Upstream shader compilation/table expansion and active-device context are not executed.',
                       'Source88-byte render-state translation executes; tests compare blend bit and exact subsequent28-byte copying, not an independent model of every state field/float conversion.',
                       'Compiled program wordE2/byteDF are explicit fixtures. Entry header byte11 and queue first-pass byte6 are distinct, even when some inputs happen to agree.',
                       'Queue3 executes against the assembled table and real selector with profile=-1. Node getters and allocation are fixtures; the40-byte distance branch stops at12f3acc before insertion.',
                       'Program+e2 bit6 producer, manager profile/remapping, full reflection/property resources, GPU, sorting, matrices/HDR and final sky remain pending. No live browser, assets, UI or saves change.']}


def main():
    from analyze_native_resources import NativeImage
    from resource_packs import DEFAULT_SOURCE, ResourceArchive, index, normalize_resource_name
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--native', type=Path, default=Path('analysis/raw/beff-native/library.so'))
    cli.add_argument('--output', type=Path, default=Path('analysis/raw/sky-effect-assembly/report.json'))
    args = cli.parse_args(); entries = {}; archives = {}
    for entry in index(args.source): entries.setdefault(normalize_resource_name(entry['path']), []).append(entry)
    def extract(name):
        found = entries.get(normalize_resource_name(name), [])
        if len(found) != 1: raise ValueError('Source missing or ambiguous: '+name)
        pack = found[0]['pack']
        if pack not in archives: archives[pack] = ResourceArchive(args.source/pack)
        return archives[pack].read(name)
    report = analyze_assembly(NativeImage(args.native.read_bytes()), extract)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'format': FORMAT, 'appliedAsLiveState': False}))


if __name__ == '__main__': main()
