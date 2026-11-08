import json
import random
import struct
import unittest
from pathlib import Path

from terrain_lighting import (ROUTINES, STRINGS, FORMAT, final_water_flags, loaded_chunk_flags,
    rgb565, terrain_effect, terrain_vertex, terrain_fragment, terrain_texture_encoding,
    lightmap_requests, recover_terrain_lighting, verify_native)
from scene_lighting import f32
from resource_packs import DEFAULT_SOURCE, index, normalize_resource_name, read_entry

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'
MAP = ROOT/'game-data/converted/maps/tutorial-preview.json'


class TerrainLightingTests(unittest.TestCase):
    def test_source_flags_are_postprocessed_and_water_comparison_includes_equality(self):
        self.assertEqual(loaded_chunk_flags(0x50001), 0x40001)
        self.assertEqual(loaded_chunk_flags(0x10001), 0x10001)
        for height, expected in [(0, 1), (132.35, 1), (132.35002, 0x10001)]:
            self.assertEqual(final_water_flags(0x10001, height, 132.35), expected)
        self.assertEqual(final_water_flags(3, -1, 0), 3)
        for v in [-1, 1 << 32, True, 1.0]:
            with self.assertRaises(ValueError): loaded_chunk_flags(v)
        with self.assertRaises(ValueError): final_water_flags(0, float('nan'), 0)

    def test_rgb565_expands_all_bits_and_keeps_opaque_alpha(self):
        for raw, expected in [(0, [0, 0, 0, 255]), (65535, [255]*4),
                              (0xf800, [255, 0, 0, 255]), (0x7e0, [0, 255, 0, 255]), (31, [0, 0, 255, 255])]:
            self.assertEqual(rgb565(raw), expected)
        for value in [-1, 65536, True]:
            with self.assertRaises(ValueError): rgb565(value)

    def test_exact_layer_names_and_world_fallback_are_distinct_from_object_atlases(self):
        self.assertEqual(lightmap_requests('tutorial', -43, 3), [
            'texture/lightmap/tutorial/layers/-043_0003.tga',
            'texture/terrain_lightmap_tutorial.tga', 'texture/terrain_lightmap.tga'])
        self.assertEqual(lightmap_requests('tutorial', -41, 2, 7)[0], 'texture/lightmap/tutorial/layers/phasing/-041_0002_7.tga')
        self.assertEqual(lightmap_requests('tutorial', -41, 2, enabled=False), ['texture/terrain_lightmap_tutorial.tga', 'texture/terrain_lightmap.tga'])
        for world, phase in [('../world', 0), ('tutorial', -1), ('tutorial', True)]:
            with self.assertRaises(ValueError): lightmap_requests(world, -41, 2, phase)

    def test_observed_pvrtc2bpp_container_requires_complete_native_mip_chain(self):
        sizes = sum(max(256 >> i, 16)*max(256 >> i, 8)//4 for i in range(9))
        raw = struct.pack('<13I', 52, 256, 256, 8, 0x8118, sizes, 2, 0, 0, 0, 1, 0x21525650, 1)+bytes(sizes)
        result = terrain_texture_encoding(raw)
        self.assertEqual((result['nativeFormat'], result['compressedGLFormat'], result['fileMipLevels']), (41, 0x8c03, 9))
        for changed in [raw[:-1], raw+b'0', raw[:12]+struct.pack('<I', 7)+raw[16:]]:
            with self.assertRaises(ValueError): terrain_texture_encoding(changed)

    def test_terrain_tone_offset_is_added_after_generic_light_and_no_clamp_or_directional_factor(self):
        vertex = terrain_vertex(-17, [0, -1/17], [1, .5, 0], [0, 0, 1], [.2, -.2, .4], [0, 0, 0])
        self.assertEqual(vertex['color'], [.5, .25, .5]); self.assertEqual(vertex['offset'], [.1, -.1, .2])
        self.assertEqual(terrain_fragment([1, 1, 1], [.5, .5, .5], vertex, [2, 2, 2]), [.6, .15, .7])
        self.assertEqual(terrain_fragment([2]*3, [1]*3, {'color': [1]*3, 'offset': [0]*3}, [2]*3), [4]*3)

    def test_changed_custom_effects_are_not_parsed_as_a_supported_shader(self):
        class Changed: b = b'not the verified CustomEffects'
        with self.assertRaisesRegex(ValueError, 'CustomEffects changed'): terrain_effect(Changed())

    @unittest.skipUnless(NATIVE.is_file(), 'Original native source stays local')
    def test_native_water_macro_rgb_and_normalized_color_paths_match_explicit_inputs(self):
        from analyze_native_resources import NativeImage
        from native_terrain_lighting_probe import NativeTerrainLightingProbe
        p = NativeTerrainLightingProbe(NativeImage(NATIVE.read_bytes())); rng = random.Random(305)
        for _ in range(100):
            flags = rng.randrange(1 << 20); height = f32(rng.uniform(-10, 200)); minimum = f32(rng.uniform(-10, 200))
            self.assertEqual(p.loaded_flags(flags), loaded_chunk_flags(flags))
            self.assertEqual(p.water_flags(flags, height, minimum), final_water_flags(flags, height, minimum))
            for blend in (False, True):
                initial = (0x807 if blend else 0x803) | ((flags >> 10) & 0x40)
                self.assertEqual(p.macros(flags, blend), [initial, initial & ~0x800])
            color = rng.randrange(65536); self.assertEqual(p.color(color), rgb565(color))
        self.assertEqual(p.color(65535), [255]*4); self.assertEqual(p.normalized(16), 1); self.assertEqual(p.normalized(0), 0)
        for height, minimum in [(1, 1), (1.0000001192092896, 1), (-1, -1), (-1, -.9999999403953552)]:
            self.assertEqual(p.water_flags(65536, height, minimum), final_water_flags(65536, height, minimum))

    @unittest.skipUnless(NATIVE.is_file(), 'Original native source stays local')
    def test_generic_and_model_lighting_are_distinct_original_uniform_vectors(self):
        from analyze_native_resources import NativeImage
        from native_terrain_lighting_probe import NativeTerrainLightingProbe
        p = NativeTerrainLightingProbe(NativeImage(NATIVE.read_bytes())); rng = random.Random(208)
        for _ in range(100):
            base = [f32(rng.uniform(-1, 2)) for _ in range(3)]
            values = [f32(rng.uniform(-2, 3)) for _ in range(3)]
            result = p.light_vectors(base, *values)
            for name, scale in zip(('common', 'generic', 'model'), values):
                self.assertEqual(result[name], [f32(v*scale) for v in base])

    @unittest.skipUnless(NATIVE.is_file(), 'Original native source stays local')
    def test_source_routines_color_semantics_pvrtc_table_and_names_are_pinned(self):
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes()); self.assertTrue(verify_native(image)['color0NormalizedByte'])
        for changed in [*ROUTINES, *STRINGS, 0x1f4fab7, 0x2499758, 0x1f3b90c+0x18*4, 0x1f3a670]:
            class Changed:
                elf = image.elf
                def read(self, address, size): return bytes(size) if address == changed else image.read(address, size)
            with self.subTest(address=hex(changed)), self.assertRaises(ValueError): verify_native(Changed())

    def source_profile(self, change=None):
        entries = {}
        for entry in index(DEFAULT_SOURCE): entries.setdefault(normalize_resource_name(entry['path']), []).append(entry)
        def extract(path):
            candidates = entries[normalize_resource_name(path)]; self.assertEqual(len(candidates), 1, path)
            raw = read_entry(candidates[0], DEFAULT_SOURCE); return change(path, raw) if change else raw
        terrain = json.loads(MAP.read_text())
        return recover_terrain_lighting(extract, lambda p: normalize_resource_name(p) in entries, terrain, lambda p:'/assets/textures/'+p+'.png')

    @unittest.skipUnless((DEFAULT_SOURCE/'tutorial.bin').is_file() and MAP.is_file(), 'Original terrain stays local')
    def test_actual9_tiles_use8_original_pages_and_unique_world_fallback_with_water_cleared(self):
        p = self.source_profile(); self.assertEqual(p['format'], FORMAT); self.assertEqual(len(p['tiles']), 9)
        self.assertEqual(sum(t['lightmap']['fallback'] for t in p['tiles']), 1)
        for row in p['tiles']:
            self.assertEqual(set(row['runtimeFlags']), {0})
            self.assertEqual(row['lightmap']['encoding'], 'ETC1')
            if row['lightmap']['fallback']:
                self.assertEqual(row['tile'], [-43, 3]); self.assertEqual(row['lightmap']['width'], 16)
                self.assertEqual(row['lightmap']['sourcePath'], 'texture/terrain_lightmap_tutorial.tga')
            else: self.assertEqual(row['lightmap']['width'], 128)
        for profile in p['effect']['profiles']:
            self.assertEqual(profile['techniques'][0]['vertex']['defines'], {'COLOR0': '', 'LIGHTMAP': ''})
            self.assertEqual(profile['techniques'][0]['state']['depthFunctionGL'], 0x201)

    @unittest.skipUnless((DEFAULT_SOURCE/'tutorial.bin').is_file() and MAP.is_file(), 'Original terrain stays local')
    def test_changed_shader_nonwhite_vertex_and_viable_water_reject_unsupported_render_branches(self):
        for kind in ('shader', 'color', 'water'):
            def change(path, data):
                if kind == 'shader' and path.endswith('.glsl'): return data+b'\n'
                if path.endswith('.trn'):
                    data = bytearray(data); version, = struct.unpack_from('<I', data, 4)
                    if kind == 'color': struct.pack_into('<H', data, 24+64*(16 if version == 9 else 24)+8450, 0)
                    if kind == 'water': struct.pack_into('<h', data, 28, 20000)
                return data
            with self.subTest(kind=kind), self.assertRaises(ValueError): self.source_profile(change)


if __name__ == '__main__': unittest.main()
