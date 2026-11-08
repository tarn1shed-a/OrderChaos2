import json
import math
import struct
import unittest
from pathlib import Path

from resource_packs import DEFAULT_SOURCE
from scene_lighting import (DEFAULTS, FIELDS, GOT, ROUTINES, STRINGS, analyze_lighting,
    check_zone_layout, color_vector, f32, lightmap_global, near_zero,
    tone_distance_uniform, verify_native, vertex_color, zone_targets)

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'


def row(ident=1, **overrides):
    values = {'ID': ident, 'light_ambient': 0xffffff, 'light_diffuse': 0xffffff,
              'tone_near': 0.0, 'tone_half': 0.0, 'tone_color_near': 0, 'tone_color_far': 0,
              **{name: 0.0 for name in DEFAULTS}, 'model_intensity_lightMap': 0.0}
    return values | overrides


class SceneLightingTests(unittest.TestCase):
    def test_native_float32_zero_interval_does_not_clamp_negative_or_tiny_boundary_values(self):
        self.assertTrue(near_zero(0))
        self.assertTrue(near_zero(1e-6))  # float32 rounds below source double bound.
        self.assertTrue(near_zero(-1e-6))
        boundary = struct.unpack('<I', struct.pack('<f', 1e-6))[0]
        outside = struct.unpack('<f', struct.pack('<I', boundary+1))[0]
        self.assertFalse(near_zero(outside))
        self.assertFalse(near_zero(-outside))
        self.assertFalse(near_zero(-2))
        for invalid in (True, math.nan, math.inf, 1e100, '1'):
            with self.assertRaises(ValueError): f32(invalid)

    def test_zero_intensity_uses_native_defaults_but_model_override_uses_generic_lightmap_owner(self):
        base = row(1, intensity_lightMap=2.0, model_intensity_lightMap=3.0)
        overlay = row(2, model_intensity_lightMap=9.0)
        targets = zone_targets(overlay, base)
        self.assertEqual(targets['intensities']['intensity_lightMap'], 2.0)
        self.assertEqual(targets['intensities']['model_intensity_lightMap'], 3.0)
        overlay['intensity_lightMap'] = 4.0
        self.assertEqual(zone_targets(overlay, base)['intensities']['model_intensity_lightMap'], 9.0)
        overlay['model_intensity_lightMap'] = 0
        self.assertEqual(zone_targets(overlay, base)['intensities']['model_intensity_lightMap'], 4.0)
        targets = zone_targets(row())
        for field, value in DEFAULTS.items(): self.assertEqual(targets['intensities'][field], value)
        self.assertEqual(targets['intensities']['model_intensity_lightMap'], DEFAULTS['intensity_lightMap'])
        self.assertEqual(zone_targets(row(intensity_common=-2))['intensities']['intensity_common'], -2)

    def test_skipped_tone_writes_retain_state_and_only_explicit_fallbacks_supply_gains_or_distance(self):
        result = zone_targets(row())
        self.assertIsNone(result['tone']['distanceUniform'])
        self.assertEqual(result['tone']['distanceWrite'], 'retain-previous')
        self.assertIsNone(result['tone']['gainNear'])
        base = row(1, tone_near=10, tone_half=20, tone_color_near=0x112233,
                   tone_color_far=0x445566, light_ambient=0x0000ff)
        overlay = row(2, tone_near=99, light_ambient=0)
        result = zone_targets(overlay, base)
        self.assertEqual(result['tone']['distanceUniform'], [10, f32(-1/20)])
        self.assertEqual(result['tone']['gainNear'], color_vector(0x112233))
        self.assertEqual(result['colors']['light_ambient'], color_vector(0x0000ff))
        overlay['tone_half'] = -4  # Nonpositive half-span inherits the pair.
        self.assertEqual(zone_targets(overlay, base)['tone']['distanceUniform'][0], 10)
        self.assertEqual(zone_targets(row(light_ambient=0))['colors']['light_ambient'], [0, 0, 0])

    def test_tone_half_span_floor_is_point_one_and_near_is_not_replaced_or_negated(self):
        self.assertEqual(tone_distance_uniform(23, 0), [23, -10])
        self.assertEqual(tone_distance_uniform(-23, -5), [-23, -10])
        self.assertEqual(tone_distance_uniform(23, 0.05), [23, -10])
        self.assertEqual(tone_distance_uniform(23, 2), [23, -0.5])

    def test_source_rgb_order_and_lightmap_global_do_not_apply_normals_or_gamma(self):
        reciprocal = f32(1/255)
        self.assertEqual(color_vector(0x112233), [f32(c*reciprocal) for c in (0x33, 0x22, 0x11)])
        # At settled integer zone colors, the native encode-to-byte/decode
        # roundtrip leaves the RGB inputs unchanged. Queued blends differ.
        for byte in range(256):
            channel = f32(byte*reciprocal)
            encoded = int(f32(f32(channel*255)+0.5))
            self.assertEqual(encoded, byte)
            self.assertEqual(f32(encoded*reciprocal), channel)
        self.assertEqual(lightmap_global([1, 0, 0], [0, 2, 4], .5), [.5, .5, 1])
        self.assertEqual(lightmap_global([-1, 0, 0], [0, 0, 0], 2), [-2, 0, 0])
        for invalid in (True, -1, 1<<24, 1.0):
            with self.assertRaises(ValueError): color_vector(invalid)
        with self.assertRaises(ValueError): lightmap_global([1, 2], [1, 2, 3], 1)

    def test_source_signed_view_z_tone_is_evaluated_at_vertices_before_raster_interpolation(self):
        uniform = tone_distance_uniform(10, 2)
        near, far, light = [1, .5, .25], [.25, .1, .05], [2, 1, .5]
        self.assertEqual(vertex_color(-10, uniform, near, far, light), [2, .5, .125])
        self.assertEqual(vertex_color(-9, uniform, near, far, light), [2, .5, .125])
        half = vertex_color(-12, uniform, near, far, light)
        for actual, expected in zip(half, [2*(1+.25)/2, (.5+.1)/2, .5*(.25+.05)/2]):
            self.assertAlmostEqual(actual, expected, places=14)
        start = vertex_color(-10, uniform, [1]*3, [0]*3, [1]*3)
        end = vertex_color(-14, uniform, [1]*3, [0]*3, [1]*3)
        interpolated = [(a+b)/2 for a, b in zip(start, end)]
        self.assertEqual(interpolated, [.625]*3)
        self.assertNotEqual(interpolated, vertex_color(-12, uniform, [1]*3, [0]*3, [1]*3))
        with self.assertRaises(ValueError): vertex_color(math.nan, uniform, near, far, light)

    def test_layout_checks_native_offsets_and_expands_strings_as_arm64_pointers(self):
        wanted = {offset: (name, kind) for name, (offset, kind) in FIELDS.items()}
        columns, types, offset = ['syntheticString'], ['s'], 8
        while offset <= 0x158:
            name, kind = wanted.get(offset, (f'padding{offset}', 'u'))
            columns.append(name); types.append(kind); offset += 4
        table = {'columns': columns, 'physicalTypes': ''.join(types)}
        self.assertEqual(check_zone_layout(table)['checkedFields'], len(FIELDS))
        bad = {**table, 'physicalTypes': 'u'+table['physicalTypes'][1:]}
        with self.assertRaisesRegex(ValueError, 'offsets'): check_zone_layout(bad)
        with self.assertRaises(ValueError): check_zone_layout({**table, 'physicalTypes': 'x'+table['physicalTypes'][1:]})

    @unittest.skipUnless(NATIVE.is_file(), 'Original native evidence stays local')
    def test_native_zone_targets_got_writers_empty_hooks_and_uniform_names_are_pinned(self):
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes())
        result = verify_native(image)
        self.assertEqual((result['lightingRoutines'], result['zoneWriterRelocations']), (11, 6))
        self.assertFalse(result['appliedToRendering'])
        for changed in [*ROUTINES, *STRINGS, 0x1df7bc8, 0x1df7bd0, 0x1df7a60, 0x1df79e0, 0x1df7a84, 0x25092e8]:
            class Changed:
                elf = image.elf
                def read(self, address, size):
                    return bytes(size) if address == changed else image.read(address, size)
            with self.subTest(address=hex(changed)), self.assertRaises(ValueError): verify_native(Changed())
        for changed in GOT:
            class Relocations:
                def iter_relocations(self):
                    return [{**r.entry, 'r_addend': 0} if r['r_offset'] == changed else r
                            for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()]
            class ELF:
                def get_section_by_name(self, name): return Relocations()
            class Changed:
                elf = ELF()
                read = image.read
            with self.subTest(relocation=hex(changed)), self.assertRaises(ValueError): verify_native(Changed())

    @unittest.skipUnless((DEFAULT_SOURCE/'tables.bin').is_file(), 'Original scene evidence stays local')
    def test_current_tutorial_targets_preserve_skipped_write_and_distinct_character_model_multipliers(self):
        result = analyze_lighting()
        self.assertEqual(result['schema'], {'checkedFields': 12, 'runtimeStride': 0x164})
        base, overlay = result['zones']
        self.assertEqual((base['sourceZoneId'], overlay['sourceZoneId']), (194, 195))
        self.assertIsNone(base['tone']['distanceUniform'])
        self.assertEqual(overlay['tone']['distanceUniform'], [0, f32(-1/17)])
        self.assertEqual(overlay['tone']['gainNear'], color_vector(6195687))
        self.assertEqual(overlay['tone']['gainFar'], color_vector(11653355))
        self.assertEqual(overlay['intensities']['model_intensity_lightMap'], f32(1.33))
        self.assertEqual(overlay['intensities']['intensity_char_ambient'], f32(1.36))
        self.assertEqual(overlay['intensities']['intensity_char_diffuse'], f32(1.39))
        self.assertFalse(result['nativeActiveStateObserved'])
        self.assertFalse(result['appliedToRendering'])
        json.dumps(result, allow_nan=False)


if __name__ == '__main__': unittest.main()
