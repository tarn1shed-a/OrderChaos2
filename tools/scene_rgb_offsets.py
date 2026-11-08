"""Recover one confirmed renderer RGB writer: the weather lightning phase.

The phase receives clocks AFTER native timer/random-strike processing. It is
not a complete weather scheduler, device observation or browser implementation.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from resource_packs import DEFAULT_SOURCE, ResourceArchive
from scene_active_lighting import verify_native as verify_active
from scene_lighting import ZONE_SHA256, check_zone_layout, f32, lightmap_global
from skill_attachments import decode_ftable

FORMAT = 'oc2-renderer-rgb-offset-evidence-v1'
WEATHER_SHA256 = '01e3923d940b537b0a92b64c4b822bfe5bebf933ca04003fdc1236ee6a92d258'
ROUTINES = {
    0x36ea38: (104, '555ca98526d9a0f48816c73eaa935a756b31af4b392a299868b66b80a9060311'),
    0x36ede8: (2100, '465035816a39a5e9fc0f056c7fa3f4fcd01d50d31489d622c12d0dcfa0bb3ec5'),
    0x556598: (8, '2b59db05426e0f313d72b30f3398c65721de2562a59dc46ceeba224f98d0b876'),
    0x36fa6c: (1004, '5bece1d7c91d67a29222bfbff5ab41faf58e28f292daf669c04e35d21455a89b'),
    0xc993e8: (8, 'b0360005080f14ed19be84f12c62fe0a0e03ebda6c8ab5217362a93dc4f3a5a5'),
    0xd03bec: (268, '4403a1e3c5d131d2130cbac2a59151b3564b1e7adb8251cfe9fe0452d1ecb27e'),
    0xd03ee0: (1372, 'cafc3612fa1fbbb05b257a237d6922764299435138cd005ec39e87f606b696b2'),
}
CALLSITES = {
    0x4cf194: (20, 'adbbde7cfa597bad8067da47022174e8d134ec3cae0d74cd60c501f06ba74ab5'),
    0x4d60ac: (12, 'c965141b84341766ee851700451163dc347f8661a00f126e04546f1fd63f7d39'),
    0xc8ce0c: (44, 'b5c558bd97c45924eb8b848cab82bf3f54638acc6ef860ed0777a1e24ba6b52b'),
}
# Research labels for 36ea38's nine parameters, not recovered original symbols.
PARAMETERS = {'intervalBase': 1000, 'intervalRange': 15000,
              'radiusBase': 20.0, 'radiusRange': 20.0,
              'plateauMs': 150, 'tailMs': 300,
              'ambientPeak': f32(.27), 'diffusePeak': f32(.36), 'hdrPeak': f32(.29)}


def verify_native(image):
    verify_active(image)
    for at, (size, digest) in (ROUTINES | CALLSITES).items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
            raise ValueError('Renderer RGB weather owner/writer changed; retrace required')
    strings = {0x1dfe537: b'ussss\0', 0x1f01117: b'weather\0', 0x1f00c16: b'.tbl\0',
               0x1df9aad: b'effects/scene/scene_nature_lighting.beff\0', 0x1df9ad6: b'sfx_thunder\0'}
    for at, raw in strings.items():
        if image.read(at, len(raw)) != raw: raise ValueError('Weather source name/schema changed')
    rels = {r['r_offset']: r['r_addend'] for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    if rels.get(0x242e850) != 0xd03bec or rels.get(0x242e878) != 0xd03ee0:
        raise ValueError('Weather table virtual lookup/reader binding changed')
    return {'newRoutines': len(ROUTINES), 'ownerCallsites': len(CALLSITES),
            'weatherController': 'world+0x288', 'rendererRGBAdds': ['world+0x1c0 ->+0xa0', 'world+0x1c0 ->+0xa4'],
            'phaseBlock': ['0x36f30c', '0x36f4cc'], 'emptyParameterHook': '0x556598',
            'allWritersRecovered': False, 'appliedToRendering': False}


def _integer(value, low, high):
    if type(value) is not int or not low <= value <= high: raise ValueError('Expected explicit native integer')
    return value


def flash_phase(extra_mode, remaining_ms, *, tail_ms=300, peaks=None, previous=None,
                next_strike_ms=900, hdr_enabled=False, context_available=True):
    """36f30c/36f3bc: explicit post-timer state, with no live effect object.

    An expired non-lightning mode does not unconditionally clear stale RGB.
    Signed remaining clocks and a positive tail length are the supported domain.
    """
    _integer(extra_mode, 0, 0xffffffff)
    _integer(remaining_ms, -(1 << 31), (1 << 31)-1)
    _integer(next_strike_ms, -(1 << 31), (1 << 31)-1)
    _integer(tail_ms, 1, (1 << 31)-1)
    if type(hdr_enabled) is not bool or type(context_available) is not bool:
        raise ValueError('Explicit native context/config gates required')
    peaks = [PARAMETERS[k] for k in ('ambientPeak', 'diffusePeak', 'hdrPeak')] if peaks is None else peaks
    if len(peaks) != 3: raise ValueError('Expected three native flash peaks')
    peaks = [f32(v) for v in peaks]
    previous = {'ambientAdd': 0.0, 'diffuseAdd': 0.0, 'hdrFlash': 0.0, 'hdrFlags': 0} if previous is None else previous
    value = {k: f32(previous[k]) for k in ('ambientAdd', 'diffuseAdd', 'hdrFlash')}
    value['hdrFlags'] = _integer(previous['hdrFlags'], 0, 0xffffffff)
    value.update(nextStrikeMs=next_strike_ms, remainingMs=remaining_ms)
    if not context_available: return value
    if extra_mode == 1 and remaining_ms >= 1:
        ratio = min(f32(f32(remaining_ms)/f32(tail_ms)), 1.0)
        if hdr_enabled:
            flags = value['hdrFlags'] | 0x10
            value['hdrFlags'] = flags | (0x08000000 if flags != value['hdrFlags'] else 0)
        # HDR uses the whole tail; RGB uses the plateau only, not a smooth fade.
        value['hdrFlash'] = f32(ratio*peaks[2])
        factor = ratio if ratio >= 1 else 0.0
        value['ambientAdd'], value['diffuseAdd'] = [f32(factor*p) for p in peaks[:2]]
    elif extra_mode == 1 or remaining_ms >= 1:
        flags = value['hdrFlags'] & 0xffffffef
        value['hdrFlags'] = flags | (0x08000000 if flags != value['hdrFlags'] else 0)
        value.update(ambientAdd=0.0, diffuseAdd=0.0, hdrFlash=0.0)
    if extra_mode != 1: value.update(nextStrikeMs=0, remainingMs=0)
    return value


def light_with_offsets(ambient, diffuse, adds, intensity):
    if len(ambient) != 3 or len(diffuse) != 3 or len(adds) != 2:
        raise ValueError('Expected source RGB/RGB and two scalar offsets')
    a, d = [f32(v) for v in adds]
    return lightmap_global([f32(f32(v)+a) for v in ambient], [f32(f32(v)+d) for v in diffuse], intensity)


class NativeFlashProbe:
    """Execute the original bounded phase; fake objects, no timer/RNG/BEFF I/O."""
    def __init__(self, image):
        verify_native(image)
        from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
        from unicorn import arm64_const
        self.reg = arm64_const
        self.uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        for at in (0x36e000, 0x36f000, 0x34e000):
            self.uc.mem_map(at, 4096); self.uc.mem_write(at, image.read(at, 4096))
        self.uc.mem_map(0x2528000, 4096)
        self.uc.mem_map(0x10000000, 0x10000)
        self.uc.mem_map(0x20000000, 0x10000)
        self.uc.mem_map(0x29e000, 4096)
        def memset(uc, at, size, data):
            if at != 0x29eaf0: raise ValueError('Unexpected native import')
            target = uc.reg_read(self.reg.UC_ARM64_REG_X0)
            count = uc.reg_read(self.reg.UC_ARM64_REG_X2)
            if target != 0x10004000 or count != 0x48: raise ValueError('Unexpected constructor clear')
            uc.mem_write(target, bytes(count)); uc.reg_write(self.reg.UC_ARM64_REG_PC, uc.reg_read(self.reg.UC_ARM64_REG_X30))
        self.uc.hook_add(UC_HOOK_CODE, memset, begin=0x29e000, end=0x29efff)
        self.uc.hook_add(UC_HOOK_CODE, lambda uc, at, size, data: uc.emu_stop(), begin=0x36f5f4, end=0x36f5f4)

    def write(self, at, fmt, *values): self.uc.mem_write(at, struct.pack('<'+fmt, *values))
    def read(self, at, fmt): return struct.unpack('<'+fmt, self.uc.mem_read(at, struct.calcsize('<'+fmt)))
    def register(self, name, value): self.uc.reg_write(getattr(self.reg, 'UC_ARM64_REG_'+name), value)

    def constructor(self):
        self.uc.mem_write(0x10004000, b'\xff'*0x70)
        self.register('SP', 0x20008000); self.register('X0', 0x10004000); self.register('X30', 0x36eaa0)
        self.uc.emu_start(0x36ea38, 0x36eaa0, count=200)
        return self.read(0x10004000, '72xIIffIIfff')

    def run(self, extra_mode, remaining_ms, **inputs):
        flash_phase(extra_mode, remaining_ms, **inputs)  # validate domain; no oracle result feeds execution
        previous = inputs.get('previous') or {'ambientAdd': 0, 'diffuseAdd': 0, 'hdrFlash': 0, 'hdrFlags': 0}
        self.uc.mem_write(0x10000000, bytes(0x10000))
        self.uc.mem_write(0x20000000, bytes(0x10000))
        self.write(0x2528db0, 'Q', 0x10000000); self.write(0x2528e00, 'Q', 0x10002000)
        self.write(0x2528220, 'Q', 0x10003000); self.write(0x100001c0, 'Q', 0x10001000)
        self.write(0x10001030, 'Q', 1 if inputs.get('context_available', True) else 0)
        self.write(0x100010a0, 'ff', previous['ambientAdd'], previous['diffuseAdd'])
        self.write(0x10002020, 'I', previous['hdrFlags']); self.write(0x10002164, 'f', previous['hdrFlash'])
        self.write(0x1000304c, 'B', inputs.get('hdr_enabled', False))
        self.write(0x10004038, 'ii', inputs.get('next_strike_ms', 900), remaining_ms)
        self.write(0x1000405c, 'I', inputs.get('tail_ms', 300))
        peaks = inputs.get('peaks') or [PARAMETERS[k] for k in ('ambientPeak', 'diffusePeak', 'hdrPeak')]
        self.write(0x10004060, 'fff', *peaks)
        for index in range(31): self.register(f'X{index}', 0)
        self.register('SP', 0x20008000); self.register('X0', 0x10004000); self.register('X19', 0x10004000)
        self.register('W8', remaining_ms & 0xffffffff)
        for name, at in (('X24', 0x1000405c), ('X23', 0x10004060), ('X22', 0x10004064), ('X21', 0x10004068)):
            self.register(name, at)
        if inputs.get('context_available', True):
            self.uc.emu_start(0x36f30c if extra_mode == 1 else 0x36f3bc, 0x36f4cc, count=500)
            if self.uc.reg_read(self.reg.UC_ARM64_REG_PC) != 0x36f4cc: raise ValueError('Native phase did not reach bounded end')
        else:
            self.uc.emu_start(0x36ee14, 0x36ee2c, count=30)
            if self.uc.reg_read(self.reg.UC_ARM64_REG_PC) != 0x36f5f4: raise ValueError('Native context gate changed')
        a, d = self.read(0x100010a0, 'ff'); hdr, = self.read(0x10002164, 'f'); flags, = self.read(0x10002020, 'I')
        clock, remaining = self.read(0x10004038, 'ii')
        return dict(ambientAdd=a, diffuseAdd=d, hdrFlash=hdr, hdrFlags=flags, nextStrikeMs=clock, remainingMs=remaining)

    def consumer_inputs(self, ambient, diffuse, adds):
        light_with_offsets(ambient, diffuse, adds, 1)  # validate finite source domain
        self.write(0x100010a0, 'ff', *adds)
        self.register('X21', 0x10001000)
        self.register('SP', 0x20008000); self.register('X29', 0x20008040)
        for index, value in enumerate([*diffuse, *ambient]):
            bits, = struct.unpack('<I', struct.pack('<f', value))
            self.register(f'S{index}', bits)
        self.uc.emu_start(0x34e5bc, 0x34e5f4, count=40)
        a = self.uc.reg_read(self.reg.UC_ARM64_REG_X1); d = self.uc.reg_read(self.reg.UC_ARM64_REG_X2)
        return list(self.read(a, 'fff')), list(self.read(d, 'fff'))


def analyze_offsets(image, source=DEFAULT_SOURCE):
    native = verify_native(image); archive = ResourceArchive(Path(source)/'tables.bin')
    raw = archive.read('tables/weather.tbl')
    if hashlib.sha256(raw).hexdigest() != WEATHER_SHA256: raise ValueError('Original weather table changed')
    weather = decode_ftable(raw, id_column='weather_type')
    if weather['physicalTypes'] != 'ussss' or weather['columns'] != ['weather_type', 'effect1', 'effect2', 'effect3', 'comment']:
        raise ValueError('Weather schema differs from original 0x24-byte runtime record')
    zone_raw = archive.read('tables/zones.tbl')
    if hashlib.sha256(zone_raw).hexdigest() != ZONE_SHA256: raise ValueError('Original zone table changed')
    zones = decode_ftable(zone_raw, id_column='ID'); check_zone_layout(zones)
    references = []
    for row in zones['rows']:
        if row['ID'] not in (194, 195, 196, 197, 199): continue
        if row['weather_extra'] not in ('', '4') or row['weather_festival']:
            raise ValueError('Tutorial weather selection needs retracing')
        references.append({'zoneId': row['ID'], 'weatherId': row['weather'], 'rawExtra': row['weather_extra'],
                           'plainExtraMode': int(row['weather_extra'] or '0'), 'lightningMode1': False})
    probe = NativeFlashProbe(image); samples = []
    if probe.constructor() != tuple(PARAMETERS.values()):
        raise ValueError('Original constructor parameters differ from recorded defaults')
    for mode in (1, 4):
        for remaining in (450, 300, 299, 150, 1, 0, -1):
            expected = flash_phase(mode, remaining, hdr_enabled=True)
            actual = probe.run(mode, remaining, hdr_enabled=True)
            if actual != expected: raise ValueError('Native RGB/HDR phase differs from oracle')
            samples.append({'explicitExtraMode': mode, 'postTimerRemainingMs': remaining, **actual})
    return {'format': FORMAT, 'native': native, 'sourceWeatherSHA256': WEATHER_SHA256,
            'sourceWeatherRowCount': len(weather['rows']), 'constructorParameters': PARAMETERS,
            'nativeConstructorParametersEqual': True,
            'tutorialPlainWeather': references, 'weather6Effects': next(r for r in weather['rows'] if r['weather_type'] == 6),
            'explicitPhaseSamples': samples, 'appliedToRendering': False, 'nativeActiveStateObserved': False,
            'limits': [
                'One confirmed RGB writer, not an exhaustive alias analysis: world+288 weather controller writes world+1c0 renderer+a0/a4; ctor zero is not a permanent global invariant.',
                'This phase receives remaining clocks after native dt/random-strike work. RNG state, placement, full event scheduling, BEFF playback, thunder sound and effect lifetime are not replayed.',
                'Mode1 flashes: RGB uses plateau only; HDR scalar fades through tail. Config+4c gates HDR flag activation, not RGB/scalar writes. Expired non-mode1 does not clear stale RGB unconditionally.',
                'The current tutorial plain source rows use extra0/4, not lightning1;195 weather6 references ash. Festival overrides, actual device state and other later writers remain outside this proof.',
                'Parameters are verified constructor defaults with an empty556598 hook in this build, not observed device settings. Positive tail length only; no zero-divide/NaN behavior is invented.',
                'Source flash adds occur before lightmap_global; model slot/config/distance, archive precedence, missing slot1 atlas, GPU color transfer and browser lightmap integration remain pending.']}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--native', type=Path, default=Path('analysis/raw/beff-native/library.so'))
    cli.add_argument('--output', type=Path, default=Path('analysis/raw/map-renderer-rgb/rgb-offsets.json'))
    args = cli.parse_args()
    from analyze_native_resources import NativeImage
    report = analyze_offsets(NativeImage(args.native.read_bytes()), args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'output': str(args.output), 'sourceQueries': len(report['tutorialPlainWeather']),
                      'phaseSamples': len(report['explicitPhaseSamples']), 'appliedToRendering': False}))


if __name__ == '__main__': main()
