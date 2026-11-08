import math
import random
import unittest
from pathlib import Path

from scene_sky import (FORMAT, MODEL, EFFECT, TEXTURE, ROUTINES, STRINGS, SOURCE_HASHES,
    analyze_sky, sky_effect, sky_material, sky_scale, sky_distance_uniform, sky_vertex, sky_fragment, verify_native)
from scene_lighting import f32
from resource_packs import DEFAULT_SOURCE, ResourceArchive

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'
HAS_SOURCE = NATIVE.is_file() and all((DEFAULT_SOURCE/p).is_file() for p in ('res.bin', 'res_t.bin', 'res_scene.bin'))


class SkyTests(unittest.TestCase):
    def test_scale_uses_maximum_absolute_coordinate_and_strict_float32_threshold(self):
        self.assertEqual(sky_scale([-900, 1, 3, 10, 8, 9]), .5)
        self.assertEqual(sky_scale([.1]*6), 1)
        self.assertEqual(sky_scale([0]*6), 1)
        self.assertEqual(sky_scale([-.10000000894069672, 0, 0, 0, 0, 0]), f32(450/f32(.10000000894069672)))
        for values in ([1]*5, [math.nan]*6, [math.inf]*6, [True]*6):
            with self.assertRaises(ValueError): sky_scale(values)

    def test_sky_distance_reciprocal_is_positive_and_clamped_before_upload(self):
        self.assertEqual(sky_distance_uniform(-7, 40), [-7, f32(1/40)])
        self.assertEqual(sky_distance_uniform(3, 0), [3, 10])
        self.assertEqual(sky_distance_uniform(3, -4), [3, 10])
        for half in (math.nan, math.inf, True):
            with self.assertRaises(ValueError): sky_distance_uniform(0, half)

    def test_sky_height_and_horizontal_depth_are_not_scene_negative_view_depth(self):
        factors = sky_vertex([3, 10, 4], [0, .2], [0, 123, .2], 0)
        self.assertEqual(factors, {'tone': .5, 'fog': .5})
        self.assertEqual(sky_vertex([3, 10, 4], [0, .2], [0, 123, .2], 7)['fog'], 1)
        self.assertEqual(sky_vertex([3, -2, 4], [0, .2], [0, 123, .2], 0)['tone'], .5**100)
        with self.assertRaises(ValueError): sky_vertex([0, math.nan, 1], [0, 1], [0, 1, 1], 7)

    def test_saturation_runs_after_tone_and_before_fog_and_preserves_alpha(self):
        result = sky_fragment([1, .5, .25, .4], [2, 1, 0], [0, 1, 2], {'tone': .5, 'fog': .5}, 1, [.1, .2, .3])
        gray = .2125+(.5*.7154)+(.25*.0721)
        self.assertEqual(result, [.1+(gray-.1)*.5, .2+(gray-.2)*.5, .3+(gray-.3)*.5, .4])
        self.assertEqual(sky_fragment([2]*4, [1]*3, [1]*3, {'tone': 1, 'fog': 1}, 0, [0]*3), [2]*4)

    def test_original_texture_spelling_and_source_hashes_are_explicit(self):
        self.assertEqual(TEXTURE, 'texture/tutorail_sky001.tga')
        self.assertEqual(len(SOURCE_HASHES), 5)
        self.assertEqual(len(SOURCE_HASHES[MODEL]), 64)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native source stays local')
    def test_native_scale_and_distance_numeric_fragments_match_explicit_inputs(self):
        from analyze_native_resources import NativeImage
        from native_sky_probe import NativeSkyProbe
        probe = NativeSkyProbe(NativeImage(NATIVE.read_bytes())); rng = random.Random(343)
        samples = [[0]*6, [.1]*6, [.10000000894069672]*6, [-.1]*6]
        samples += [[f32(rng.uniform(-1000, 1000)) for _ in range(6)] for _ in range(100)]
        for values in samples: self.assertEqual(probe.scale(values), sky_scale(values))
        for _ in range(100):
            near, half = [f32(rng.uniform(-50, 200)) for _ in range(2)]
            self.assertEqual(probe.distance(near, half), sky_distance_uniform(near, half))

    @unittest.skipUnless(NATIVE.is_file(), 'Original native source stays local')
    def test_constructor_and_parameter_cache_run_original_stores(self):
        from analyze_native_resources import NativeImage
        from native_sky_probe import NativeSkyProbe
        p = NativeSkyProbe(NativeImage(NATIVE.read_bytes()))
        self.assertEqual(p.constructor(), {'parameters': [40, 40, 1, 1, 1, 1, 1, 1, 0], 'fog': [8, 4]})
        rng = random.Random(3433)
        for _ in range(100):
            values = [f32(rng.uniform(-4, 8)) for _ in range(9)]
            self.assertEqual(p.cache(values[:2], values[2:5], values[5:8], values[8]), values)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native source stays local')
    def test_pinned_native_routines_constants_and_uniform_names_reject_changes(self):
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes()); self.assertEqual(verify_native(image)['rendererOwnerOffset'], 0x48)
        for changed in [*ROUTINES, *STRINGS, 0x1e62d40, 0x1df7a60, 0x1e62e80]:
            class Changed:
                elf = image.elf
                def read(self, at, size): return bytes(size) if at == changed else image.read(at, size)
            with self.subTest(address=hex(changed)), self.assertRaises(ValueError): verify_native(Changed())

    def source(self, mutate=None):
        from analyze_native_resources import NativeImage
        archives = {p: ResourceArchive(DEFAULT_SOURCE/p) for p in ('res.bin', 'res_t.bin', 'res_scene.bin')}
        def extract(name):
            pack = 'res_scene.bin' if name == MODEL else 'res_t.bin' if name == TEXTURE else 'res.bin'
            raw = archives[pack].read(name); return mutate(name, raw) if mutate else raw
        return analyze_sky(extract, NativeImage(NATIVE.read_bytes()))

    @unittest.skipUnless(HAS_SOURCE, 'Original sky resources stay local')
    def test_source_model_selects_solid_and_keeps_all_effect_profiles_and_distinct_defaults(self):
        report = self.source(); self.assertEqual(report['format'], FORMAT); self.assertFalse(report['appliedAsLiveState'])
        self.assertEqual(report['material']['technique'], {'valueWord0': 2, 'name': 'solid'})
        self.assertEqual(report['material']['fogIntensity'], 7)
        self.assertEqual((report['geometry']['meshes'], report['geometry']['vertices'], report['geometry']['triangles']), (1, 267, 528))
        self.assertEqual(report['geometry']['nodeBindings'][0]['reference'], '#sky001-mesh')
        self.assertEqual((report['texture']['width'], report['texture']['height'], report['texture']['fileMipLevels']), (1024, 1024, 11))
        for p in report['effect']['profiles']:
            self.assertEqual(p['defaults']['fog_intensity'], 8)
            self.assertEqual(set(p['defaults']['skyTexture']['request'].values()), {None})
            self.assertEqual([t['name'] for t in p['techniques']], ['tech0', 'blend', 'solid'])
            t = p['techniques'][2]; self.assertEqual(t['vertex']['defines'], {'HIDE_IN_FOG': '', 'SKY_COLOR_TONE': ''})
            for key in ('blendEnabled', 'cullEnabled', 'depthTestEnabled', 'depthWriteEnabled'): self.assertFalse(t['state'][key])

    @unittest.skipUnless(HAS_SOURCE, 'Original sky resources stay local')
    def test_every_source_input_is_pinned_before_reading(self):
        for changed in SOURCE_HASHES:
            with self.subTest(source=changed), self.assertRaisesRegex(ValueError, 'sky source changed'):
                self.source(lambda name, raw: raw+b'\n' if name == changed else raw)


if __name__ == '__main__': unittest.main()
