"""Source-backed effect loading/association and honest material creation boundaries."""
import unittest
from pathlib import Path

from effect_material_evidence import analyze, verify_native
from resource_packs import DEFAULT_SOURCE

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'


@unittest.skipUnless(NATIVE.is_file() and (DEFAULT_SOURCE/'tutorial.bin').is_file(),
                     'Original native/model/effect inputs stay private')
class EffectMaterialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.image = NativeImage(NATIVE.read_bytes())
        cls.result = analyze(cls.image, DEFAULT_SOURCE)

    def test_original_resource_linker_and_effect_bytes_fail_closed(self):
        image = self.image
        self.assertFalse(verify_native(image)['compiledEffectOrGPUResultSupplied'])
        for changed in (0x117ec68, 0x117f010, 0x1180360, 0x1118004,
                        0x1127250, 0x13baac8, 0x1180d90, 0x1f2f44c):
            class Changed:
                elf = image.elf
                def read(self, at, size):
                    raw = image.read(at, size)
                    return bytes([raw[0] ^ 1])+raw[1:] if at == changed else raw
            with self.subTest(address=hex(changed)), self.assertRaises(ValueError):
                verify_native(Changed())

    def test_original_resource_constructor_reads_real_bres_without_compiled_effect(self):
        for model in self.result['models']:
            for row in [model['resourceRead'], *model['effectResourceReads'].values()]:
                self.assertEqual(row['sourceReadByte'], 1)
                self.assertTrue(row['originalStreamEvents'])
                self.assertTrue(row['info'])
                self.assertFalse(row['VFSOpenExecuted'])
                self.assertFalse(row['compiledEffectCreated'])

    def test_seven_materials_get_real_source_effect_definitions_by_original_lookup(self):
        checked = 0
        for model in self.result['models']:
            for row in model['associations']:
                definition = model['materials'][row['localIndex']]
                binding = row['sourceAssociation']
                self.assertTrue(binding['after'])
                self.assertEqual(binding['effectName'], definition['effectName'][1:])
                request = row['dependencyFragment']
                if request['kind'] == 'dependencyRequestNotExecuted':
                    self.assertEqual(request['file'], definition['effectPath'])
                    self.assertTrue(binding['originalLookupAndStoreExecuted'])
                    self.assertEqual(binding['before'], 0)
                else:
                    self.assertTrue(binding['originalDuplicateReuseExecuted'])
                self.assertFalse(binding['compiledEffectCreated'])
                checked += 1
        self.assertEqual(checked, 7)

    def test_smithy_materials_share_source_effect_without_becoming_one_material(self):
        model = next(r for r in self.result['models'] if r['model'].endswith('hum_archi_smithy001_03.bdae'))
        a, b = model['associations']
        self.assertEqual((a['localIndex'], b['localIndex']), (0, 1))
        self.assertNotEqual(a['material'], b['material'])
        self.assertEqual(a['sourceAssociation']['after'], b['sourceAssociation']['after'])

    def test_both_factories_preserve_linked_definition_until_first_device_read(self):
        checked = 0
        for model in self.result['models']:
            for row in model['associations']:
                for result in row['creationFrontiers']:
                    self.assertEqual(result['sourceEffectDefinition'], row['sourceAssociation']['after'])
                    self.assertEqual(result['stoppedAt'], '0x1127290')
                    self.assertEqual(result['kind'], 'firstDeviceDereferenceNotExecuted')
                    self.assertFalse(result['compiledEffectResultSupplied'])
                    self.assertEqual(result['name'], row['sourceAssociation']['effectName'])
                    self.assertIn('0x1127250', result['trace'])
                    checked += 1
        self.assertEqual(checked, 14)

    def test_null_definition_reaches_original_missing_effect_diagnostic(self):
        for model in self.result['models']:
            row = model['missingDefinitionBranch']
            self.assertEqual(row['format'], 'MISSING EFFECT BDAE in %s')
            self.assertEqual(row['sourceFile'], model['model'])
            self.assertTrue(row['fallbackEffectNotExecuted'])

    def test_three_source_effects_have_verified_shader_files_without_active_profile_guess(self):
        self.assertEqual(len(self.result['effects']), 3)
        shaders = set()
        for name, effect in self.result['effects'].items():
            self.assertEqual(effect['name'], name[:-5]+'-fx')
            for profile in effect['profiles']:
                self.assertFalse(profile['activeDeviceSelectionObserved'])
                self.assertEqual(profile['modifierDescriptorWords'], [0]*8)
                technique, = profile['techniques']
                self.assertEqual(technique['name'], 'tech0')
                source_pass, = technique['passes']
                for stage, shader in source_pass.items():
                    self.assertEqual(len(shader['sourceCandidates']), 1)
                    self.assertEqual(shader['entry'], 'main' if profile['sourceField'] == 32
                                     else ('VS' if stage == 'vertex' else 'FS'))
                    shaders.add(shader['file'])
        self.assertEqual(shaders, {'lt_pal_normal_vs.glsl', 'lt_pal_normal_fs.glsl',
                                  'ut_common_vs.glsl', 'ut_common_fs.glsl'})

    def test_twelve_source_associations_are_not_reported_as_completed_live_updates(self):
        self.assertEqual(len(self.result['instances']), 12)
        self.assertEqual(len({r['id'] for r in self.result['instances']}), 12)
        self.assertTrue(all(r['partAssociations'] and not r['runtimeMaterialUpdateObserved']
                            for r in self.result['instances']))
        for key in ('VFSArchiveOpenExecuted', 'completeDependencyLoaderExecuted',
                    'deviceMethodExecuted', 'compiledEffectResultSupplied', 'completeMaterialCreated',
                    'runtimePartRebindExecuted', 'renderedFrameObserved'):
            self.assertFalse(self.result['scope'][key])
        self.assertFalse(self.result['appliedToGame'])


if __name__ == '__main__':
    unittest.main()
