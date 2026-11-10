"""Audit original tutorial environment/weather and export settled Default targets.

No new lighting, weather placement, random sequence or server state is supplied.
The preview remains an isolated historical viewer, not the original executable.
"""
import argparse
import hashlib
import json
import struct
import zipfile
from pathlib import Path

from map_loading_evidence import Sources
from map_selection_evidence import DEFAULT_APK
from resource_packs import DEFAULT_SOURCE
from scene_active_lighting import NativeTargetProbe
from scene_lighting import ZONE_SHA256, check_zone_layout, f32, zone_targets
from scene_rgb_offsets import WEATHER_SHA256, verify_native as verify_weather
from skill_attachments import decode_ftable

FORMAT = 'oc2-apk-default-environment-v1'
ROOT = Path(__file__).resolve().parents[1]
# Newly followed weather-extra -> sky effect request. Original symbols unknown.
ROUTINES = {
    0x36ffd4: (36, '4d3878c72d3d18d5fb2462de25364a776da056f5e3cf7804b5c1c49aeca66579'),
    0xa64a30: (732, '980e6e144c68d4d3d743c93b29c7ba2304427520aebfd7790e19b62c1d3fbd42'),
    0x3bb830: (12296, '66b21671ce1d7c411947e2c6580bc53b151c5ee21f522eb0a6b9dc116658315e'),
}
FOG_FIELDS = {'fog_color': (0x44, 'u'), 'fog_near': (0x48, 'f'), 'fog_half': (0x4c, 'f')}


def verify(image):
    verify_weather(image)
    for at, (size, sha) in ROUTINES.items():
        if hashlib.sha256(image.read(at, size)).hexdigest() != sha:
            raise ValueError('Original weather sky consumer changed; retrace required')
    reloc = {r['r_offset']: r['r_addend'] for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    if reloc.get(0x2506aa8) != 0x2528220 or reloc.get(0x25069f8) != 0x250b848:
        raise ValueError('Original fog configuration indirections changed')
    extra = []
    for index in range(5):
        at = reloc[0x2509358+8*index]
        extra.append(image.read(at, 128).split(b'\0')[0].decode())
    expected = ['', '', '', 'effects/scene/scene_weather_vortex_blue.beff',
                'effects/scene/scene_weather_vortex_red.beff']
    if extra != expected:
        raise ValueError('Original extra-weather name table changed')
    return extra


def fog_target(row, base, *, far_plane, coefficient):
    """4c6b88..4c6cc0, explicit EnableFogDistanceLimit=false, immediate targets."""
    owner = row if base is None or row['fog_half'] > 0 else base
    near = f32(owner['fog_near'])
    half = min(f32(owner['fog_half']), f32(f32(near+f32(far_plane))*.5))
    color_owner = row if base is None or row['fog_color'] != 0 else base
    color = [f32(((color_owner['fog_color'] >> shift) & 255)*f32(1/255)) for shift in (0, 8, 16)]
    return {'near': f32(near*f32(coefficient)), 'halfSpan': f32(half*f32(coefficient)),
            'color': color, 'distanceOwner': owner['ID'], 'colorOwner': color_owner['ID']}


class NativeDefaultFogProbe(NativeTargetProbe):
    """Execute the previously skipped original fog block; synthetic storage only."""
    def __init__(self, image):
        super().__init__(image)
        self.uc.mem_map(0x2506000, 4096)

    def run_fog(self, row, base, *, far_plane, coefficient):
        # Validate numeric inputs independently; oracle values do not feed native execution.
        fog_target(row, base, far_plane=far_plane, coefficient=coefficient)
        self.heap = 0x10010000
        self.uc.mem_write(0x10000000, bytes(0x40000))
        self.uc.mem_write(0x20000000, bytes(0x10000))
        manager, env, base_at, selected_at = 0x10000000, 0x10001000, 0x10002000, 0x10003000
        for source, at in ((base, base_at), (row, selected_at)):
            if source is not None:
                for key, (offset, kind) in FOG_FIELDS.items():
                    self._write(at+offset, 'f' if kind == 'f' else 'I', source[key])
        self._write(manager+0x88, 'Q', base_at if base is not None else 0)
        self._write(manager+0xc0, 'Q', env)
        for head in (env+0x48, env+0x68): self._write(head, 'QQ', head, head)
        self._write(0x2506aa8, 'Q', 0x10004000)
        self._write(0x10004000, 'Q', 0x10005000)
        self._write(0x10005024, 'f', 0.)  # Original Default EnableFogDistanceLimit=false.
        self._write(0x1000503c, 'f', coefficient)
        self._write(0x25069f8, 'Q', 0x10006000)
        self._write(0x10006000, 'f', far_plane)
        for index in range(31): self.uc.reg_write(getattr(self.reg, f'UC_ARM64_REG_X{index}'), 0)
        for index in range(32): self.uc.reg_write(getattr(self.reg, f'UC_ARM64_REG_Q{index}'), 0)
        for name, value in [('SP', 0x20008000), ('X19', manager), ('X27', selected_at)]:
            self.uc.reg_write(getattr(self.reg, 'UC_ARM64_REG_'+name), value)
        self.uc.reg_write(self.reg.UC_ARM64_REG_S8, struct.unpack('<I', struct.pack('<f', 1/255))[0])
        self.uc.emu_start(0x4c6b88, 0x4c6cc0, count=3000)
        if self.uc.reg_read(self.reg.UC_ARM64_REG_PC) != 0x4c6cc0:
            raise ValueError('Original fog block did not reach bounded end')
        return {'near': self._read(env+0x40, 'f')[0], 'halfSpan': self._read(env+0x44, 'f')[0],
                'color': list(self._read(env+0x58, 'fff'))}


def export(image, source, apk, output):
    from native_device_selection_probe import NativeDeviceSelectionProbe
    from beff_effects import decode_effect
    names = verify(image)
    with zipfile.ZipFile(apk) as z:
        apk_raw = z.read('assets/GameOptions.json'); options = json.loads(apk_raw)
    values = {}
    for group in ('GPU', 'MEM'):
        values.update(dict(NativeDeviceSelectionProbe(image).updates(options['profiles'][group], '')))
    config = {k: values[k] for k in ('CameraFarPlaneDis', 'EnableFogDistanceLimit', 'FogDisCoef')}
    if config != {'CameraFarPlaneDis': 240., 'EnableFogDistanceLimit': False, 'FogDisCoef': 1.}:
        raise ValueError('Original Default fog inputs changed; retrace required')
    sources = Sources(source)
    raw = sources.read('tables/zones.tbl')
    if hashlib.sha256(raw).hexdigest() != ZONE_SHA256: raise ValueError('Original zones changed')
    table = decode_ftable(raw, id_column='ID'); check_zone_layout(table)
    offsets, offset = {}, 0
    for name, kind in zip(table['columns'], table['physicalTypes']):
        offsets[name] = (offset, kind); offset += 8 if kind == 's' else 4
    if any(offsets[k] != v for k, v in FOG_FIELDS.items()): raise ValueError('Fog source schema changed')
    weather_raw = sources.read('tables/weather.tbl')
    if hashlib.sha256(weather_raw).hexdigest() != WEATHER_SHA256: raise ValueError('Original weather changed')
    weather = {r['weather_type']: r for r in decode_ftable(weather_raw, id_column='weather_type')['rows']}
    rows = {r['ID']: r for r in table['rows']}; base = rows[194]
    probe = NativeDefaultFogProbe(image)
    result = []
    for ident in (194, 195, 196, 197, 199):
        row = rows[ident]
        if row['definition'] != 0 or row['phasing_id'] != 0 or row['weather_festival']:
            raise ValueError('Unsupported tutorial polygon, phase or festival override')
        fallback = None if ident == 194 else base
        fog = fog_target(row, fallback, far_plane=config['CameraFarPlaneDis'], coefficient=config['FogDisCoef'])
        native = probe.run_fog(row, fallback, far_plane=config['CameraFarPlaneDis'], coefficient=config['FogDisCoef'])
        if native != {k: fog[k] for k in native}: raise ValueError('Original fog arithmetic differs')
        if fog['halfSpan'] < .5: raise ValueError('Fog upload clamp needs separate recovery')
        extra = int(row['weather_extra'] or '0')
        if extra not in (0, 4): raise ValueError('Tutorial extra-weather branch changed')
        bloom_owner = row if fallback is None or row['bloom_color_decrease'] > 0 or row['bloom_intensity'] > 0 else fallback
        if bloom_owner['bloom_color_decrease'] <= 0 and bloom_owner['bloom_intensity'] <= 0:
            raise ValueError('Retained bloom history is not supplied')
        colors = zone_targets(row, fallback)['colors']
        result.append({'id': ident, 'fog': fog,
                       'bloom': {'decrease': bloom_owner['bloom_color_decrease'], 'intensity': bloom_owner['bloom_intensity']},
                       'sourceLighting': {'ambient': colors['light_ambient'], 'diffuse': colors['light_diffuse']},
                       'weather': {'id': row['weather'], 'extraMode': extra,
                                   'effects': [weather[row['weather']]['effect'+str(i)] for i in (1, 2, 3)] if row['weather'] else [],
                                   'skyEffect': names[extra], 'lightning': extra == 1}})
    effects = {}
    for name in sorted({p for r in result for p in [*r['weather']['effects'][:1], r['weather']['skyEffect']] if p}):
        raw_effect = sources.read(name); decoded = decode_effect(raw_effect)
        effects[name] = {'sha256': hashlib.sha256(raw_effect).hexdigest(), 'emitters': len(decoded['emitters']),
                         'modelNodes': len(decoded['modelNodes']), 'completePayload': decoded['verification']['completePayload'],
                         'appliedToPreview': False}
    report = {'format': FORMAT, 'configuration': config, 'zoneSHA256': ZONE_SHA256,
              'APKOptionsSHA256': hashlib.sha256(apk_raw).hexdigest(), 'zones': result,
              'weatherExtraNames': names, 'effects': effects, 'sources': sources.proofs,
              'knownWeatherRGB': {'freshConstructor': [0, 0], 'tutorialLightning': False,
                                  'allOtherWritersRecovered': False, 'priorFlashHistoryObserved': False},
              'scope': 'Original Default settled targets; same selected pair drives light, fog and bloom.',
              'limits': ['Environment mode0 remains the historical viewer input; mode4 transitions are not replayed.',
                         'Ash and sky vortex files are decoded, but original placement/playback is not supplied.',
                         'Weather flash absence is conditional on these plain source rows and fresh history, not an exhaustive RGB writer proof.',
                         'No original Android frame or live server override is claimed.']}
    output = Path(output).resolve()
    if not output.is_relative_to((ROOT/'analysis/raw').resolve()): raise ValueError('Private source exports stay in analysis/raw')
    manifest_path = output/'manifest.json'; manifest = json.loads(manifest_path.read_text())
    if manifest['sourceSelection']['profile'] != 'APK_Default': raise ValueError('Expected original Default export')
    (output/'default-environment.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    manifest['defaultEnvironment'] = '/assets/verified/APK_Default/default-environment.json'
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    return report


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--apk', type=Path, default=DEFAULT_APK)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    from analyze_native_resources import NativeImage
    report = export(NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes()), args.source, args.apk, args.output)
    print(json.dumps({'zones': len(report['zones']), 'weatherFiles': len(report['effects']), 'configuration': report['configuration']}))
