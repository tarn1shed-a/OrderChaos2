"""Source-only audit of zone lighting targets and the scene vertex-color path.

No device state, transition queue, weather offset or browser color transfer is
invented. In particular, a skipped zone write retains state, not an identity.
"""
import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

from resource_packs import DEFAULT_SOURCE, ResourceArchive
from scene_lightmap_binding import verify_native as verify_binding
from scene_render_state import SHADERS
from skill_attachments import decode_ftable

FORMAT = 'oc2-scene-lighting-evidence-v1'
ZONE_SHA256 = '86bc1fe9b022edfa72badfe5f417a9d7f8ca2a10e3b72271e7457f3a61f92303'
ROUTINES = {
    0x4bf458: (4756, '6b2c585a8afe09636bc38da753adb203e05854c5121e354326a8c6b58af2d27a'),
    0x4c3614: (4816, '9987780b6ad34514162a54d44a2247440d9cd98c2d31866fcd5b792b2de54b37'),
    0x34d228: (1440, 'b9ca1f350be5d7b49ad0c388976b25b850665cbddd2c32738408d2d0af97e80b'),
    0x556588: (8, '2b59db05426e0f313d72b30f3398c65721de2562a59dc46ceeba224f98d0b876'),
    0x556568: (8, '2b59db05426e0f313d72b30f3398c65721de2562a59dc46ceeba224f98d0b876'),
    0x556558: (8, '2b59db05426e0f313d72b30f3398c65721de2562a59dc46ceeba224f98d0b876'),
    0x329c40: (80, '7ff54c4bdeed4db2f280c623e2c4321644a8d8422a05f43419f8b2e9a506db04'),
    0x329bf0: (80, 'b62053354464fa9bca6d6ecf0ad4bf77a68ba24ed380fd87456c13bb4132835d'),
    0x34e53c: (952, 'f3de2c906b9fecbe083c696484cb3597ea05372bc91eabb2c37d56f06294daf6'),
    0x4c48e4: (328, 'c39f8502a21c58f918ad4bb2a67cae81dd14d27088bece6b8b5804dba38e81f8'),
    0x4c4a2c: (276, '4f1a153553d0228c3b818fede73f9eb5b9a57a3464df6762f9529e7c61723e56'),
}
STRINGS = {0x1df9450: 'light_common', 0x1df945d: 'light_lightMap',
           0x1df946c: 'light_model_lightMap', 0x1e03b07: 'colorTone_DisParam',
           0x1e03b1a: 'colorTone_GainNear', 0x1e03b2d: 'colorTone_GainFar'}
GOT = {0x25053a8: 0x25092e8, 0x2507580: 0x25092ec, 0x2504580: 0x25092f0,
       0x2504a98: 0x25092f4, 0x2505a30: 0x25092f8, 0x2507190: 0x25092fc}
DEFAULTS = {'intensity_char_ambient': 1.03125, 'intensity_char_diffuse': 1.47265625,
            'intensity_char_specular': 1.05078125, 'intensity_common': 0.8500000238418579,
            'intensity_lightMap': 1.3300000429153442}
FIELDS = {'light_diffuse': (0x50, 'u'), 'light_ambient': (0x54, 'u'),
          'tone_near': (0x58, 'f'), 'tone_half': (0x5c, 'f'),
          'tone_color_near': (0x60, 'u'), 'tone_color_far': (0x64, 'u'),
          'intensity_char_ambient': (0x11c, 'f'), 'intensity_char_diffuse': (0x120, 'f'),
          'intensity_char_specular': (0x124, 'f'), 'intensity_common': (0x130, 'f'),
          'intensity_lightMap': (0x134, 'f'), 'model_intensity_lightMap': (0x158, 'f')}


def f32(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Expected a finite source float')
    try: result, = struct.unpack('<f', struct.pack('<f', value))
    except (OverflowError, struct.error) as error: raise ValueError('Source float32 overflow') from error
    if not math.isfinite(result): raise ValueError('Source float32 overflow')
    return result


def verify_native(image):
    verify_binding(image)
    for address, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(address, size)).hexdigest() != digest:
            raise ValueError('Scene lighting/zone consumer changed; retrace required')
    for address, text in STRINGS.items():
        if image.read(address, len(text)+1) != text.encode()+b'\0':
            raise ValueError('Scene lighting parameter name changed')
    constants = {0x1df7bc8: struct.pack('<d', -1e-6), 0x1df7bd0: struct.pack('<d', 1e-6),
                 0x1df7a60: struct.pack('<f', 0.1), 0x1df79e0: struct.pack('<f', 1/255),
                 0x1df7a84: struct.pack('<f', 255),
                 0x25092e8: struct.pack('<6f', *DEFAULTS.values(), DEFAULTS['intensity_lightMap'])}
    for address, raw in constants.items():
        if image.read(address, len(raw)) != raw: raise ValueError('Scene lighting source constant changed')
    rels = {r['r_offset']: r['r_addend'] for r in
            image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    if any(rels.get(address) != target for address, target in GOT.items()):
        raise ValueError('Scene lighting zone-writer relocation changed')
    return {'lightingRoutines': len(ROUTINES), 'parameterNames': len(STRINGS),
            'zoneWriterRelocations': len(GOT), 'emptyHooks': ['0x556558', '0x556568', '0x556588'],
            'appliedToRendering': False}


def check_zone_layout(table):
    # Packed ARM64 runtime fields expand source string spans to 8-byte pointers.
    # Check the relevant cumulative offsets against the pinned native consumers;
    # this is not a general native FTABLE loader implementation.
    offsets, at = {}, 0
    for name, kind in zip(table['columns'], table['physicalTypes']):
        if kind not in 'uifs': raise ValueError('Unsupported zone runtime field type')
        offsets[name] = (at, kind)
        at += 8 if kind == 's' else 4
    if any(offsets.get(name) != expected for name, expected in FIELDS.items()):
        raise ValueError('Zone schema no longer matches native lighting field offsets')
    return {'checkedFields': len(FIELDS), 'runtimeStride': at}


def near_zero(value):
    value = f32(value)
    # Strict open interval, after float32 -> double promotion. Not abs<=epsilon.
    return -1e-6 < value < 1e-6


def color_vector(packed):
    if type(packed) is not int or not 0 <= packed <= 0xffffff:
        raise ValueError('Expected a packed source RGB color')
    reciprocal = f32(1/255)
    return [f32(((packed >> shift) & 255)*reciprocal) for shift in (0, 8, 16)]


def tone_distance_uniform(near, half_span):
    return [f32(near), f32(-1/max(f32(half_span), f32(0.1)))]


def zone_targets(row, fallback=None):
    """4c3614 settled targets for an explicitly supplied base/overlay pair.

    Does not infer which pair the original manager selected or advance queues.
    """
    def chosen(name, missing):
        return fallback if fallback is not None and missing(row[name]) else row
    colors = {name: color_vector(chosen(name, lambda v: v == 0)[name])
              for name in ('light_ambient', 'light_diffuse')}
    intensities = {}
    for name, default in DEFAULTS.items():
        owner = chosen(name, near_zero)
        intensities[name] = default if near_zero(owner[name]) else f32(owner[name])
    # Source x24 still points to the row chosen for intensity_lightMap here.
    # model_intensity_lightMap does NOT select its base/overlay independently.
    owner = chosen('intensity_lightMap', near_zero)
    value = owner['model_intensity_lightMap']
    intensities['model_intensity_lightMap'] = (
        intensities['intensity_lightMap'] if near_zero(value) else f32(value))
    interval_owner = chosen('tone_half', lambda v: f32(v) <= 0)
    interval = raw_interval = None
    if f32(interval_owner['tone_half']) > 0:
        raw_interval = [f32(interval_owner['tone_near']), f32(interval_owner['tone_half'])]
        interval = tone_distance_uniform(*raw_interval)
    gains = {}
    for name in ('tone_color_near', 'tone_color_far'):
        value = chosen(name, lambda v: v == 0)[name]
        gains[name] = color_vector(value) if value else None
    return {'sourceZoneId': row['ID'], 'suppliedFallbackZoneId': fallback['ID'] if fallback else None,
            'colors': colors, 'intensities': intensities,
            'tone': {'rawDistance': raw_interval, 'distanceUniform': interval,
                     'distanceWrite': 'set' if interval else 'retain-previous',
                     'gainNear': gains['tone_color_near'], 'gainFar': gains['tone_color_far'],
                     'gainWriteWhenNull': 'retain-previous', 'offsetTargets': [0.0, 0.0, 0.0]}}


def lightmap_global(ambient, diffuse, intensity):
    """34d228 explicit RGB inputs, including any already-applied runtime offsets."""
    if len(ambient) != 3 or len(diffuse) != 3: raise ValueError('Expected source RGB inputs')
    intensity = f32(intensity)
    return [f32(f32(f32(a)+f32(f32(d)*0.5))*intensity) for a, d in zip(ambient, diffuse)]


def vertex_color(view_z, distance_uniform, gain_near, gain_far, light):
    """CPU oracle for the source VS branch; GPU must interpolate this result.

    Shader mediump precision is device-dependent. This oracle uses Python float,
    so it verifies the expression/stage, not original GPU bit-exact arithmetic.
    """
    if len(distance_uniform) != 2 or any(len(v) != 3 for v in (gain_near, gain_far, light)):
        raise ValueError('Invalid source vertex color inputs')
    values = [view_z, *distance_uniform, *gain_near, *gain_far, *light]
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
        raise ValueError('Non-finite source vertex color input')
    factor = 0.5**max((view_z+distance_uniform[0])*distance_uniform[1], 0)
    return [l*(far+(near-far)*factor) for l, near, far in zip(light, gain_near, gain_far)]


def analyze_lighting(source=DEFAULT_SOURCE):
    raw = ResourceArchive(Path(source)/'tables.bin').read('tables/zones.tbl')
    if hashlib.sha256(raw).hexdigest() != ZONE_SHA256:
        raise ValueError('Source zone table changed; review lighting schema and targets')
    table = decode_ftable(raw, id_column='ID')
    layout = check_zone_layout(table)
    rows = {r['ID']: r for r in table['rows']}
    zones = [zone_targets(rows[194]), zone_targets(rows[195], rows[194])]
    shaders = ResourceArchive(Path(source)/'res.bin')
    for name, digest in SHADERS.items():
        if hashlib.sha256(shaders.read(name)).hexdigest() != digest:
            raise ValueError('Source scene lighting shader changed; retrace required')
    for zone in zones:
        zone['modelLightBeforeRuntimeColorOffsets'] = lightmap_global(
            zone['colors']['light_ambient'], zone['colors']['light_diffuse'],
            zone['intensities']['model_intensity_lightMap'])
    return {'format': FORMAT, 'zones': zones, 'sourceTableSHA256': ZONE_SHA256,
            'schema': layout, 'sourceShaderSHA256': SHADERS,
            'libraryInitialIntensities': dict(DEFAULTS, model_intensity_lightMap=DEFAULTS['intensity_lightMap']),
            'appliedToRendering': False, 'nativeActiveStateObserved': False,
            'limits': [
                'Only settled lighting targets for explicitly supplied tutorial base194/overlay195 are audited; original zone selection is not reproduced.',
                'Zone mode4 enqueues 2000ms transitions; target writers and current queued blends are distinct. No queue is simulated here.',
                'Zero color/half-span can inherit or retain prior state. Missing values are not replaced with invented identity gains or distances.',
                'Multiplier zero uses the strict (-1e-6,+1e-6) float32-promoted interval. Nonzero negative values are not clamped.',
                'The model multiplier reads the row selected for generic lightMap, then falls back to that effective multiplier; it is not independently inherited.',
                '34e53c may add runtime scalar offsets to ambient/diffuse RGB before34d228. Reported static targets explicitly precede these offsets.',
                'IN_GAME/COLOR_TONE/PASS_COLOR lightmap branch multiplies sampled diffuse and atlas by interpolated source vertex color. Original mediump precision/active overrides are unobserved.',
                'No Three Standard light replacement, atlas selection, color-space bridge, fog/HDR pass or GPU rendering change is applied.']}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--native', type=Path, default=Path('analysis/raw/beff-native/library.so'))
    cli.add_argument('--output', type=Path, default=Path('analysis/raw/map-global-light/lighting.json'))
    args = cli.parse_args()
    from analyze_native_resources import NativeImage
    report = analyze_lighting(args.source)
    report['native'] = verify_native(NativeImage(args.native.read_bytes()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'output': str(args.output), 'zones': len(report['zones']), 'appliedToRendering': False}))


if __name__ == '__main__': main()
