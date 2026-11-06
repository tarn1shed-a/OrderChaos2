import struct
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from beff_effects import decode_effect, EFFECT_SOURCES
from resource_packs import ResourceArchive, DEFAULT_SOURCE
from beff_particles import recover_materials


def sample(names=('fire.tga', '.'), duration=766):
    data = bytearray(52)
    struct.pack_into('<4sI', data, 0, b'beff', 9)
    struct.pack_into('<I', data, 24, duration)
    struct.pack_into('<I', data, 20, 1)
    struct.pack_into('<I', data, 48, len(names))
    for name in names:
        string = name.encode() + b'\0'
        string += b'\0' * (-len(string) % 4)
        data.extend(struct.pack('<I', len(string)))
        data.extend(string)
    data.extend(struct.pack('<3I',0,0,4)+b'e\0\0\0')  # node type, empty parent, padded name
    data.extend(struct.pack('<I',0))  # children
    emitter = [0]*20;emitter[7]=3;emitter[9:12]=[1,1,1]
    data.extend(struct.pack('<20i',*emitter));data.extend(struct.pack('<2I',0,0))
    def curve(kind, value):
        data.extend(struct.pack('<3I',1,0,0));data.extend(struct.pack('<'+kind,*value))
    for i in range(17): curve('i' if i==3 else '3f' if i==16 else 'f',[0,1,0] if i==16 else [0])
    particle = [0]*29;particle[3]=20
    data.extend(struct.pack('<29i',*particle));data.extend(struct.pack('<3i',0,1,1))
    for i in range(19): curve('i' if i<7 else 'f',[255 if i<7 else 1])
    data.extend(struct.pack('<I',0))
    return data


class EffectTests(unittest.TestCase):
    def test_recover_finite_and_unbounded_lifetime_and_safe_dependencies(self):
        result = decode_effect(sample())
        self.assertEqual(result['durationMs'], 766)
        self.assertFalse(result['loop'])
        self.assertEqual(result['textures'], ['texture/fire.tga'])
        self.assertEqual(len(result['sourceSHA256']), 64)
        self.assertEqual(result['verification']['bytesConsumed'],len(sample()))
        self.assertEqual(result['verification']['curves'],36)
        result = decode_effect(sample(duration=0xffffffff))
        self.assertIsNone(result['durationMs'])
        self.assertTrue(result['loop'])

    def test_reject_bad_version_extents_terminators_and_path_escape(self):
        broken = sample()
        struct.pack_into('<I', broken, 4, 10)
        with self.assertRaises(ValueError): decode_effect(broken)
        broken = sample()
        struct.pack_into('<I', broken, 52, 0xfffffff0)
        with self.assertRaises(ValueError): decode_effect(broken)
        broken = sample()
        broken[56:68] = b'no-terminatr'
        with self.assertRaises(ValueError): decode_effect(broken)
        for names in [('file.bdae', '.'), ('../fire.tga', '.'), ('fire\\bad.tga', '.'), ('a.tga',), ('a.tga', '.', '.')]:
            with self.subTest(names=names):
                with self.assertRaises(ValueError): decode_effect(sample(names))
        with self.assertRaises(ValueError): decode_effect(b'beff')
        with self.assertRaises(ValueError): decode_effect(sample()[:56])

    def test_reject_trailing_data_corrupt_particle_index_and_nonfinite_or_nonmonotonic_keys(self):
        original=sample();decoded=decode_effect(original)
        with self.assertRaisesRegex(ValueError,'Unconsumed'):decode_effect(original+b'\0'*4)
        for size in [len(original)-1,len(original)-80,len(original)-300]:
            with self.assertRaises(ValueError):decode_effect(original[:size])
        emitter=decoded['emitters'][0];particle=emitter['particle']
        bad=bytearray(original);struct.pack_into('<i',bad,particle['sourceOffset']+116,999)
        with self.assertRaisesRegex(ValueError,'index'):decode_effect(bad)
        bad=bytearray(original);struct.pack_into('<f',bad,emitter['curves']['outerX']['sourceOffset']+12,float('nan'))
        with self.assertRaisesRegex(ValueError,'Non-finite'):decode_effect(bad)
        bad=bytearray(original);struct.pack_into('<i',bad,emitter['curves']['outerX']['sourceOffset']+8,-1)
        with self.assertRaisesRegex(ValueError,'Non-monotonic'):decode_effect(bad)
        bad=bytearray(original);struct.pack_into('<I',bad,emitter['curves']['outerX']['sourceOffset'],0xffffffff)
        with self.assertRaisesRegex(ValueError,'count'):decode_effect(bad)
        at=emitter['curves']['outerX']['sourceOffset']
        bad=bytearray(original);bad[at+8:at+16]=bad[at+8:at+16]*2;struct.pack_into('<I',bad,at,2)
        with self.assertRaisesRegex(ValueError,'Non-monotonic'):decode_effect(bad)

    @unittest.skipUnless((DEFAULT_SOURCE / 'res.bin').is_file(), 'Original effect archive is local-only')
    def test_original_selected_dependencies_and_lifetimes(self):
        archive = ResourceArchive(DEFAULT_SOURCE / 'res.bin')
        expected = {
            'fireCast': (None, ['fire_015.tga', 'jpg_6755.tga', 'fx_sun.tga']),
            'fireMissile': (None, ['blur_a.tga', '2590977160622662525.tga', 'jpg_s_fire012e.tga']),
            'fireHit': (766, ['fx_stick.tga', 'fire03_xulie4x4.tga']),
            'frostHit': (633, ['ray045.tga', 'quan_02.tga', 'fx_iceblock01.tga', 'ice06.tga']),
        }
        textures = ResourceArchive(DEFAULT_SOURCE / 'res_t.bin')
        for key, (duration, dependencies) in expected.items():
            with self.subTest(effect=key):
                result = decode_effect(archive.read(EFFECT_SOURCES[key]))
                self.assertEqual(result['durationMs'], duration)
                self.assertEqual(result['textures'], ['texture/' + name for name in dependencies])
                for path in result['textures']:
                    self.assertGreater(len(textures.read(path)), 52)
                self.assertTrue(result['verification']['completePayload'])
                self.assertEqual(result['verification']['bytesConsumed'],len(archive.read(EFFECT_SOURCES[key])))

    @unittest.skipUnless((DEFAULT_SOURCE / 'res.bin').is_file(), 'Original effect archive is local-only')
    def test_original_emission_life_uv_shapes_and_material_ids(self):
        archive=ResourceArchive(DEFAULT_SOURCE/'res.bin')
        results={key:decode_effect(archive.read(path)) for key,path in EFFECT_SOURCES.items()}
        self.assertEqual([len(v['emitters']) for v in results.values()],[3,4,3,5])
        fire=results['fireHit']['emitters']
        self.assertEqual(fire[0]['particle']['lifeFrames'],20)
        self.assertEqual(fire[0]['durationFrames'],3)
        self.assertEqual(fire[0]['curves']['volumeHigh']['values'],[10])
        self.assertEqual(fire[1]['particle']['curves']['uvLeft']['values'][:4],[0,.25,.5,.75])
        self.assertEqual(fire[1]['particle']['curves']['uvTop']['values'][4],.25)
        frost=results['frostHit']['emitters']
        self.assertEqual([e['particle']['type'] for e in frost],[0,1,1,0,3])
        self.assertEqual([e['particle']['materialId'] for e in frost],[16,12,16,6,6])
        self.assertEqual(frost[4]['curves']['outerY']['values'],[10])
        with TemporaryDirectory() as directory:
            path=Path(directory)/'EfflibEffects.bdae';path.write_bytes(archive.read('EfflibEffects.bdae'))
            materials=recover_materials(path)
            self.assertEqual(materials[0]['blend'],'alpha')
            self.assertEqual(materials[6]['blend'],'additive')
            self.assertTrue(materials[12]['twoColor'])
            self.assertEqual(materials[16]['name'],'eff_unlit_textured_mix_2color_additive-fx')


if __name__ == '__main__':
    unittest.main()
