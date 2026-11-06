"""Extract verified BEFF v9 ARM64 parsing and particle sampling evidence.

Static analysis only. Function labels are research labels, not recovered symbols.
This accepts the exact original 3.1.3a build supported by NativeImage; it neither
executes the APK nor writes original data into tracked source directories.
"""
import argparse
import json
import struct
import zipfile
from pathlib import Path

from analyze_native_resources import NativeImage, NATIVE_SHA256


ANCHORS = {
    'beff_header_dependencies_nodes_loader': 0xeb2cf0,
    'emitter_v9_loader': 0xeb3cb8,
    'collada_node_loader': 0xeb46c0,
    'int_keydata_loader': 0xeb4d7c,
    'float_keydata_loader': 0xeb5104,
    'vector_keydata_loader': 0xeb53b0,
    'particle_v9_loader': 0xeb55ac,
    'affector_loader': 0xeb59e8,
    'scalar_key_sampler': 0xe8b9dc,
    'point_emitter_spawn': 0xe8bd74,
    'disc_emitter_spawn': 0xe8b048,
    'sphere_emitter_spawn': 0xe8c420,
    'emission_update': 0xe8ed28,
    'emitter_transform_update': 0xe8f6e8,
    'emitter_particle_update': 0xe907a4,
    'particle_lifetime_and_color_initialization': 0xe9de20,
    'particle_common_update': 0xe9e778,
    'billboard_particle_update': 0xe9f5a0,
    'particle_material_setter': 0xe97e78,
    'material_id_selection': 0xe8e024,
    'material_library_factory': 0xeb7f24,
    'effect_library_startup': 0x4cdf50,
    'material_library_order_loading': 0xeb8260,
    'free_particle_quad_update': 0xea1b14,
    'directional_particle_quad_update': 0xea1508,
    'gravity_affector_apply': 0xea6000,
    'acceleration_affector_apply': 0xea586c,
    'random_affector_apply': 0xea6394,
    'random_affector_interval': 0xea6354,
}

# Claims are kept narrow: each points at actual instruction ranges. Original
# shader text, binary tables, screenshots and disassembly stay in ignored output.
EVIDENCE = {
    'header': {
        'instructionRanges': ['0xeb2d64-0xeb2d80', '0xeb2e28-0xeb2e40'],
        'finding': 'Reads a 48-byte header, requires version 9, then reads a separate 32-bit dependency count.',
    },
    'emitterLayout': {
        'instructionRanges': ['0xeb3cf0-0xeb3e00', '0xeb422c-0xeb4334'],
        'finding': 'Two length-prefixed strings, a 32-bit child count, 80-byte fixed data; after two more strings reads 17 key tracks: 15 float, one integer, one vector3.',
    },
    'particleLayout': {
        'instructionRanges': ['0xeb55dc-0xeb55e8', '0xeb5720-0xeb5878', '0xeb58e4-0xeb59c4'],
        'finding': 'Reads 116 fixed bytes, three 32-bit dependency indices, seven integer tracks and twelve float tracks.',
    },
    'timeConstants': {
        'virtualAddresses': {'millisecondsPerFrame': '0x1f02100', 'framesPerMillisecond': '0x1f02104'},
        'values': {'millisecondsPerFrame': 33.33333206176758, 'framesPerMillisecond': 0.029999999329447746},
    },
    'scalarSampling': {
        'instructionRanges': ['0xe8b9dc-0xe8bb48'],
        'finding': 'Milliseconds are truncated to an integer 30 FPS frame before linear interpolation. A looping track wraps after trunc((lastFrame+1)*millisecondsPerFrame) milliseconds; a non-looping track holds the last value.',
    },
    'qualityEmission': {
        'instructionRanges': ['0xe8ee94-0xe8ef10', '0xe90940-0xe909f0'],
        'finding': 'Quality >=2, ==1, or <1 selects one of three emission count curves and corresponding interval frame fields. Interval is at least one 33.333ms frame. These three fields are not random min/max ranges.',
    },
    'particleLifetime': {
        'instructionRanges': ['0xe9de48-0xe9deb0'],
        'finding': 'Particle header index 3 is lifetime in 30 FPS frames. Index 4 is signed percentage variation; sample an integer between min(percent,0) and max(percent,0), inclusive, multiply lifetime by 1+sample*0.01, then truncate milliseconds.',
    },
    'sizeRandomness': {
        'instructionRanges': ['0xe9e1b4-0xe9e268'],
        'finding': 'Size samples a signed integer percentage q between min(r,0) and max(r,0), inclusive, then uses 1-q*0.01. Positive size variation shrinks. XY shares the sample only when keep-XY is set; otherwise each axis samples independently.',
    },
    'sourceColors': {
        'instructionRanges': ['0xe9df00-0xe9dfe4'],
        'finding': 'First four integer curves supply RGBA for vertex color0; the next three supply RGB for vertex color1 and reuse alpha. Their shader meaning depends on the selected material, not inherently emissive.',
    },
    'velocityTracks': {
        'instructionRanges': ['0xe8bdc0-0xe8bf80'],
        'finding': 'Emitter float track 13 supplies random-direction speed, track 14 directed speed, track 15 a cone-angle control; vector track 16 supplies a normalized direction. Random-direction sampling uses three signed ten-bit components and normalization.',
    },
    'velocityIntegration': {
        'instructionRanges': ['0xe9ea6c-0xe9eaa8'],
        'finding': 'Particle position advances by velocity * dtMilliseconds * 0.001; decoded initial speeds are world units per second.',
    },
    'gravityAffector': {
        'instructionRanges': ['0xea6028-0xea60d0'],
        'finding': 'Samples strength and normalized direction at particle age; adds direction * strength * dtMilliseconds * 0.03 to velocity. A constant strength 0.15 corresponds to acceleration 4.5 world units per second squared.',
    },
    'accelerationAffector': {
        'instructionRanges': ['0xea5880-0xea58d0'],
        'finding': 'Multiplies velocity by 1 + (strength - 1) * dtMilliseconds * 0.03; at a 30 FPS step, strength 0.95 scales velocity by 0.95.',
    },
    'integrationOrdering': {
        'instructionRanges': ['0xe90d1c-0xe90d84'],
        'finding': 'Each particle first advances and renders from its existing velocity, then each enabled affector updates that velocity for the following step.',
    },
    'ellipsoidShape': {
        'instructionRanges': ['0xe8c46c-0xe8c5a0'],
        'finding': 'Shape 1 normalizes three signed ten-bit random coordinates, multiplies axes by outer XYZ, then applies independently sampled signed inner-percentage shrink factors to each axis.',
    },
    'discShape': {
        'instructionRanges': ['0xe8b100-0xe8b25c'],
        'finding': 'Shape 2 uses the XZ plane. Outer Y is a distribution-count control: values above one place particles on floor(360/count)-degree spokes by emission sequence; otherwise signed ten-bit random XZ coordinates are normalized. Outer XZ and independent inner-percentage factors set the position.',
    },
    'freeParticleQuad': {
        'instructionRanges': ['0xea1cd0-0xea1db4'],
        'finding': 'Zero-angle FREE particles form an XZ quad with normal Y. Euler basis is Rz * Ry * Rx: width axis (cy*cz,cy*sz,-sy); height axis (cx*sy*cz+sx*sz,cx*sy*sz-sx*cz,cx*cy).',
    },
    'directionalParticleQuad': {
        'instructionRanges': ['0xea159c-0xea1770', '0xea1954-0xea196c'],
        'finding': 'Type 3 uses normalized particle velocity as its height axis. Its width axis is velocity cross world-up, with up rotated around velocity by rotation Z; the zero-cross fallback is (vy,vx,vz).',
    },
    'materialOrdering': {
        'instructionRanges': ['0x4cef84-0x4cef98', '0xeb8024-0xeb8034', '0xeb82f4-0xeb8378', '0xe8e024-0xe8e050'],
        'finding': 'EfflibEffects.bdae is passed to the material manager, which loads source effect indices 0..20 in order into handle slots 23..43. Numeric particle material IDs 0..20 select those corresponding source effects; they are not a two-value blend enum.',
    },
    'limitations': [
        'Instruction labels are local research labels; original C++ names are unavailable.',
        'A format layout alone does not establish every material flag or rendering mode.',
        'Binary parsing and shader references do not by themselves verify visual equivalence to the original running game.',
    ],
}


def analyze(apk, output):
    with zipfile.ZipFile(apk) as archive:
        image = NativeImage(archive.read('lib/arm64-v8a/libOrderChaos2.so'))
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    report = {'nativeSHA256': NATIVE_SHA256, 'abi': 'arm64-v8a',
              'analysis': 'Static, original executable not run; function labels assigned by this project.',
              'evidence': EVIDENCE, 'routines': {}}
    for name, address in ANCHORS.items():
        metadata, lines = image.routine(address)
        metadata['disassembly'] = name + '.txt'
        (output / metadata['disassembly']).write_text('\n'.join(lines) + '\n')
        report['routines'][name] = metadata
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return {'nativeSHA256': NATIVE_SHA256, 'routines': len(report['routines']),
            'report': str(output / 'report.json')}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('apk', type=Path)
    cli.add_argument('--output', type=Path, default=Path('analysis/raw/native-effects'))
    args = cli.parse_args()
    try:
        print(json.dumps(analyze(args.apk, args.output), ensure_ascii=False))
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, struct.error) as error:
        cli.exit(1, f'error: {error}\n')


if __name__ == '__main__':
    main()
