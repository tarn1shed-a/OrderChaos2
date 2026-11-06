"""Recover the tutorial preview's source HDR defaults and zone fog metadata.

The fixed HDR defaults are transcribed from the SHA-verified ARM64 setter, not
selected for appearance. Zone data is decoded from CRC-checked source tables by
the caller. Device-quality fog changes, runtime LUT overrides, weather and zone
transition interpolation are deliberately reported as unresolved.
"""
import hashlib
import math
import struct
from pathlib import Path

from skill_attachments import decode_ftable

WORLD_PATH = 'world/tutorial.wld'
PREVIEW_BOUNDS = (-2752.0, 128.0, -2560.0, 320.0)
LUT_PATH = 'texture/lut_standard.tga'
NATIVE_SHA256 = '77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4'
SHADER_PATHS = (
    'HDR_tonemap_bloom_FS.glsl', 'HDR_tonemap_bloom_VS.glsl',
    'BloomDownscaleExtractFS.glsl', 'BloomDownscaleExtractVS.glsl',
    'Bloom_Blur_FS.glsl', 'Bloom_Blur_VS.glsl',
    'TerrainVP.glsl', 'EfflibEffectVS.glsl',
)


def _bytes(value):
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value)
    return Path(value).read_bytes()


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def source_color(value):
    """Original zone color: low byte red, next green, next blue (0x00BBGGRR)."""
    if not isinstance(value, int) or not 0 <= value <= 0xffffff:
        raise ValueError('Unsupported source zone color')
    return [((value >> shift) & 255) / 255 for shift in (0, 8, 16)]


def _intersects(a, b):
    return a[0] <= b[2] and a[2] >= b[0] and a[1] <= b[3] and a[3] >= b[1]


def build_scene_profile(extract, bounds=PREVIEW_BOUNDS):
    """Return JSON-safe metadata; extract(name) returns checked bytes or a Path.

    The builder owns archive mounting/CRC validation, source extraction and PNG
    conversion. Only source table rows overlapping the existing preview are
    included. Raw zone bounds stay in original game coordinates.
    """
    bounds = tuple(bounds)
    if len(bounds) != 4 or not all(math.isfinite(n) for n in bounds):
        raise ValueError('Invalid scene bounds')
    if bounds[0] > bounds[2] or bounds[1] > bounds[3]:
        raise ValueError('Reversed scene bounds')
    map_bytes = _bytes(extract('tables/map_info.tbl'))
    zone_bytes = _bytes(extract('tables/zones.tbl'))
    maps = decode_ftable(map_bytes, id_column='map_id')
    source_zones = decode_ftable(zone_bytes, id_column='ID')
    matches = [row for row in maps['rows'] if row['file'] == WORLD_PATH]
    if len(matches) != 1:
        raise ValueError('Expected one source tutorial map')
    world = matches[0]
    zones = []
    for row in source_zones['rows']:
        if row['map_id'] != world['map_id']:
            continue
        aabb = [min(row['x'], row['x1']), min(row['z'], row['z1']),
                max(row['x'], row['x1']), max(row['z'], row['z1'])]
        if not _intersects(aabb, bounds):
            continue
        if row['definition'] != 0 or row['box_orientation'] != 0 or row['phasing_id'] != 0:
            raise ValueError('Preview overlaps unsupported zone shape or phase')
        half = max(.5, row['fog_half'])
        zones.append({
            'id': row['ID'], 'parentId': row['parent_ID'], 'level': row['level'],
            'priority': row['priority'], 'bounds': aabb,
            'rawBounds': {key: row[key] for key in
                          ('x', 'y', 'z', 'x1', 'y1', 'z1', 'radius', 'box_orientation', 'definition')},
            'fog': {
                'color': source_color(row['fog_color']), 'rawColor': row['fog_color'],
                'near': row['fog_near'], 'halfSpan': half,
                'rawHalfSpan': row['fog_half'], 'rate': 1.0,
                'sourceStartEnd': [row['fog_near'], row['fog_near'] + half, 1 / half],
            },
            'bloom': {'decrease': row['bloom_color_decrease'], 'intensity': row['bloom_intensity']},
            'sourceLighting': {
                'diffuse': source_color(row['light_diffuse']),
                'ambient': source_color(row['light_ambient']),
                'characterAmbientIntensity': row['intensity_char_ambient'],
                'characterDiffuseIntensity': row['intensity_char_diffuse'],
                'characterSpecularIntensity': row['intensity_char_specular'],
            },
            'skybox': row['skybox'].replace('\\', '/'),
            'weather': row['weather'],
        })
    if not zones:
        raise ValueError('No source zones intersect the preview')
    zones.sort(key=lambda row: (row['priority'], row['level'], row['id']))
    lut_bytes = _bytes(extract(LUT_PATH))
    # The recovered native fallback is an uncompressed 512x16 TGA in this data set.
    if len(lut_bytes) < 18 or lut_bytes[2] != 2 or struct.unpack_from('<2H', lut_bytes, 12) != (512, 16):
        raise ValueError('Unexpected source fallback LUT dimensions or encoding')
    shaders = {path: {'sha256': _sha(_bytes(extract(path)))} for path in SHADER_PATHS}
    return {
        'version': 1, 'format': 'oc2-scene-render-v1', 'defaultZoneId': 194,
        'world': {'path': WORLD_PATH, 'mapId': world['map_id'], 'name': world['name'],
                  'viewingDistance': world['viewing_distance'], 'previewBounds': list(bounds)},
        'hdr': {
            'exposure': 1.0, 'whitePoint': 1.2000000476837158,
            'brightness': -0.0, 'contrast': 1.0, 'scale': 1.2999999523162842,
            'thresholdOffset': 0.6399999856948853, 'maxThreshold': 1.0, 'maxIntensity': 1.0,
            'gamma': 2.2, 'luma': [.2126, .7152, .0722],
            'gaussianWeights': [.0205, .0855, .232, .324, .232, .0855, .0205],
            'blurWidth': 2.0, 'blurWidths': [2.0, 4.0], 'blurIterations': 2,
            'downscale': .5, 'bloomDivisor': 2, 'qualityFlag': True,
            'blurSettingsOrigin': 'verified-native-constructor-default; active overrides unresolved',
            'blurWidthRule': 'iteration * integerMultiplier * (qualityFlag ? 1 : 0.5)',
            'vignetteEnabled': False,
            'sourceColorSpace': 'gamma-encoded HDR scene; bloom added after linear tone mapping',
        },
        'zones': zones,
        'fog': {'mode': 'exponential-half-distance', 'sourceDepth': 'negative-view-z',
                'positiveDepthFormula': 'pow(0.5, max((depth-near)/halfSpan,0)*rate)',
                'minimumHalfSpan': .5, 'zoneColorPacking': '0x00BBGGRR'},
        'lutPath': LUT_PATH,
        'lut': {'width': 512, 'height': 16, 'blueSlices': 32,
                'flipY': False, 'colorSpace': 'none', 'sourceSHA256': _sha(lut_bytes),
                'mode': 'verified-native-fallback; runtime override unresolved'},
        'sources': {
            'nativeSHA256': NATIVE_SHA256,
            'nativeHDRSetter': '0x34ad74', 'nativeFogUniformSetter': '0x4bf458',
            'nativeFogZoneColorDecode': '0x4c4238-0x4c4260',
            'nativeFogHalfSpan': '0x4bfd50-0x4bfdc8',
            'nativeBloomSetter': '0x34a9fc', 'nativeBlurWidth': '0x34c238',
            'nativeHDRConstructor': '0x343394', 'nativeBloomResolution': '0x34bb58',
            'nativeBloomDivisorTable': '0x1df7cb8',
            'tables/map_info.tbl': maps['verification'],
            'tables/zones.tbl': source_zones['verification'],
            'shaders': shaders,
        },
        'limitations': [
            'Source zone rows and native defaults recovered; original lighting and weather are incomplete.',
            'Device-quality fog clamps/distance scaling and smooth zone transitions are not restored.',
            'Blur and resolution use verified native constructor defaults; active device-quality overrides remain unresolved.',
            'Native fallback LUT recovered; runtime LUT overrides and death-only HDR variation are not restored.',
        ],
    }
