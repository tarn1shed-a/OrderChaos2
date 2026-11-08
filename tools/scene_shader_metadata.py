"""Original shader file.map metadata producer; never infer flags from GLSL text."""
import argparse
import hashlib
import json
from pathlib import Path

from scene_sky_object_flags import verify_native as verify_object
from scene_material_cache import word

FORMAT = 'oc2-shader-map-metadata-evidence-v1'
ROUTINES = {
    0x141cf60: (1032, 'b40f9529695f5d639fd86db3589f3f703fc55f312e37d09b07bf928aaeefb740'),
    0x1435f54: (272, '1c2af53271aaa6b8861c867af443b456a774caf936e250dea520d9a85d64f885'),
    0x141d368: (2740, '025245850e88bdd3dd4e6de599c88e2365d82cf2998b7a15c056821a454053d4'),
    0x1424d2c: (528, '3a739acae424d94c4ecb2f959571a6b90deec6805838c9726be53d40ac173add'),
    0x148c07c: (228, '9c50e6cafe92d8d72ca4ef97cfcba3f00e9b223a6ae6ffe57e2fe424a9cfc493'),
    0x148c160: (1884, '5a76c82312d6832a381ac6ae2db5054b669c1c30f0c8a4be13a9f0eae482ec8a'),
    0x148ca60: (224, 'c7c8b6e0827af659ddfa7b08f89f2332ba4ffe4d7083e8124261fbc52d70f0ed'),
    0x14368e4: (392, '06b78b0f6991c069db622de9c10102c694c754c3d687770b72e9459c09478d77'),
    0x146abd0: (84, 'bf56593c08bb4112db2836322a3b679c3baa52bc0bdbbfd8de20b2b29978c194'),
}
CONSTANTS = {0x1f3e705: b'%s/file.map\0',
             0x1f419d0: bytes.fromhex('318b0000308b0000b9910000')}


def verify_native(image):
    verify_object(image)
    for at, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
            raise ValueError('Shader metadata producer code changed')
    for at, expected in CONSTANTS.items():
        if image.read(at, len(expected)) != expected:
            raise ValueError('Shader metadata constant changed')
    return {'routines': len(ROUTINES), 'constants': len(CONSTANTS), 'appliedAsLiveState': False}


def map_fixture(data):
    """Independent model for bounded well-formed LF/CRLF fixtures, not a general parser.

    Native parser mutates the buffer and does not validate the delimiter positions.
    These guards belong to the experiment, not the original file format contract.
    """
    if not isinstance(data, bytes) or len(data) > 8192 or b'\0' in data:
        raise ValueError('Expected bounded NUL-free shader map fixture')
    rows = []; offset = 0
    for line in data.splitlines(keepends=True):
        if not line.endswith(b'\n') or len(rows) >= 8:
            raise ValueError('Only at most eight complete LF/CRLF records are covered')
        body = line[:-2] if line.endswith(b'\r\n') else line[:-1]
        fields = body.split(b';')
        if (len(fields) != 4 or len(fields[1]) != 1 or len(fields[2]) != 1 or
                not 1 <= len(fields[3]) <= 80 or len(fields[0]) > 80 or
                any(c < 32 or c > 126 for c in body)):
            raise ValueError('Expected alias;single-byte;single-byte;key record fixture')
        semicolon = offset+len(fields[0]); key_offset = semicolon+5
        rows.append({'key': fields[3].decode('ascii'), 'alias': fields[0].decode('ascii') or None,
                     'keyOffset': key_offset, 'firstFlag': int(fields[1] != b'0'),
                     'discardFlag': int(fields[2] != b'0')})
        offset += len(line)
    return rows


def shader_word(stage, flag, compiled=False):
    if type(stage) is not int or not 0 <= stage <= 2 or type(compiled) is not bool:
        raise ValueError('Expected explicit shader table index0..2 and compile fixture')
    word(flag, 32)
    return stage | ((flag & 1) << 4) | (8 if compiled else 0)


def manifest_inventory(paths):
    """Inventory file names only; no claim about a runtime mounted path/root."""
    return sorted(p for p in paths if p.replace('\\', '/').rsplit('/', 1)[-1].lower() == 'file.map')


def analyze_metadata(image):
    return {'format': FORMAT, 'native': verify_native(image),
            'producer': {'mapPathFormat': '%s/file.map', 'parser': '141cf60',
                         'recordFixtureShape': 'alias;firstCharacter;secondCharacter;key followed by LF or CRLF',
                         'normalization': 'characters at semicolon+1/+3 become character!=ASCII0 bytes',
                         'storedPointers': 'key at semicolon+5; optional alias at record start;1435f54 stores the pointer pair at tree node+20/+28',
                         'header': 'key[-4] first flag, key[-2] discard flag after in-place normalization'},
            'consumer': {'manager': '141d368 looks up key, passes node+20 descriptor to driver virtual+48',
                         'factory': '1424d2c: descriptor absent -> W5=0; otherwise W5=key[-2]!=0',
                         'preprocessInput': 'descriptor absent ->true; otherwise key[-4]==0, passed at stack+18 to148c160',
                         'shader': '14368e4 /146abd0: initialize stage then replace word18.bit4 with W5.bit0',
                         'GLTable': [0x8b31, 0x8b30, 0x91b9],
                         'backend': '1436534 copies slot1 shader.bit4 to object E2.HasDiscard by OR; verified in preceding branch'},
            'executionScope': {'parser': 'complete141cf60; stream imports/provider/tree insertion are fixtures; original in-place bytes retained into factory',
                               'factory': 'complete1424d2c and148c07c capability mapping with explicit capability callback; empty148ca60 cleanup',
                               'shader': 'complete14368e4 /146abd0 /316b60 with driver logging disabled',
                               'staticOnly': ['1435f54 tree insertion', '141d368 manager lookup/cached-source paths', '148c160 preprocessing/injection'],
                               'fixtures': ['allocator and name-copy bodies', 'provider/stream and tree insertion callback',
                                            'preprocessed source-array and success/failure', 'GL create/source/compile result']},
            'shaderFlagWriteRecovered': True, 'activeSkyDiscardRecovered': False,
            'preprocessedSkySourceRecovered': False, 'appliedAsLiveState': False,
            'limits': ['Manifest fixtures prove the original producer/consumer instruction chain, not actual file.map contents or the live manager selection.',
                       'Preprocessor is a callback boundary. GLITCH_ALPHA_TEST constant presence does not select an active macro or prove the resulting shader text.',
                       'GL compile/link/GPU, shader pak cache, full tree/cache/destruction and active effect/modifier/profile inputs remain pending.',
                       'No lexical discard search is used to assign metadata. No runtime, UI, map extent, art or private save changes.']}


def main():
    from analyze_native_resources import NativeImage
    from resource_packs import DEFAULT_SOURCE, index
    import zipfile
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--native', type=Path, default=Path('analysis/raw/beff-native/library.so'))
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--apk', type=Path)
    cli.add_argument('--output', type=Path, default=Path('analysis/raw/sky-shader-flags/report.json'))
    args = cli.parse_args(); report = analyze_metadata(NativeImage(args.native.read_bytes()))
    entries = index(args.source)
    report['localInventory'] = {'packEntries': len(entries),
                                'packManifestPaths': manifest_inventory([e['path'] for e in entries]),
                                'runtimeMountAndProviderRootObserved': False}
    if args.apk:
        with zipfile.ZipFile(args.apk) as archive:
            report['localInventory']['apk'] = {'sha256': hashlib.sha256(args.apk.read_bytes()).hexdigest(),
                                               'entries': len(archive.namelist()),
                                               'manifestPaths': manifest_inventory(archive.namelist())}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'format': FORMAT, 'appliedAsLiveState': False}))


if __name__ == '__main__': main()
