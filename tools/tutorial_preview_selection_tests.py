"""Source-backed checks for conditional tutorial asset selection."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from tutorial_preview_selection import (ROOT, DEFAULT_APK, DEFAULT_SOURCE,
    MaskProbe, mask_baseline, resolve, export_preview, verify_mask)

LEGACY = ROOT/'backups/prototype-withdrawal-20261108-224729/converted-preview'
NATIVE = ROOT/'analysis/raw/beff-native/library.so'


@unittest.skipUnless(NATIVE.is_file() and DEFAULT_APK.is_file() and LEGACY.is_dir(),
                     'Private original inputs and archived viewer assets are required')
class OriginalSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.image = NativeImage(NATIVE.read_bytes())
        cls.reports = {}
        for profile in ('GPU_6','GPU_1','GPU_0M'):
            cls.reports[profile] = resolve(cls.image,DEFAULT_SOURCE,DEFAULT_APK,profile,LEGACY)

    def test_original_mask_filename_branches(self):
        probe = MaskProbe(self.image)
        for x,z in [(-41,2),(0,-5)]:
            for phase in (0,3):
                for level in (0,1,3):
                    for small in (False,True):
                        for channel in range(4):
                            stem = f'{x:04d}_{z:04d}_{channel+level*4}'
                            if phase: stem += f'_{phase}'
                            if small: stem += '_l'
                            expected = 'world/tutorial/layers/'+('phasing/'if phase else '')+stem+'.msk'
                            self.assertEqual(probe.request(x,z,channel,level,phase,small),expected)

    def test_config_write_identity_is_checked(self):
        original = self.image.read
        class Changed:
            elf = self.image.elf
            def read(self,address,size):
                raw = original(address,size)
                return bytes([raw[0]^1])+raw[1:] if address==0x3bcb18 else raw
        with self.assertRaisesRegex(ValueError,'mask selection changed'):
            verify_mask(Changed())

    def test_mask_invariant_rejects_different_downloaded_config(self):
        config = {'profiles':{'MEM':{'defaults':[{'Default':[['UseSmallTerrainMask',False]]}],
                                    'overrides':{'MEM_0':{'UseSmallTerrainMask':True}}}}}
        with self.assertRaisesRegex(ValueError,'invariant'):
            mask_baseline(config)

    def test_source_masks_and_slot_are_kept_separate(self):
        high,_ = self.reports['GPU_6'];low,_ = self.reports['GPU_1']
        self.assertEqual(high['phase'],0)
        self.assertFalse(high['mask']['value'])
        self.assertEqual([n for t in high['tiles']for n in t['maskPresent']],
                         ['world/tutorial/layers/-041_0002_1.msk'])
        self.assertEqual(high['tiles'],low['tiles'])
        self.assertEqual(len(high['instances']),39)
        self.assertTrue(all(r['modelSlot']==0 for r in high['instances']))
        self.assertTrue(all(r['modelSlot']==1 for r in low['instances']))
        # A real low model exists for the tree. Other missing _l candidates
        # must retain slot 1 even when their geometry uses the base filename.
        tree = next(r for r in low['instances']if 'small_tree006' in r['model'])
        self.assertTrue(tree['requestedModel'].endswith('_l.bdae'))
        self.assertTrue(any(r['requestedModel']==r['model']and r['modelSlot']==1 for r in low['instances']))
        self.assertFalse(high['actualDeviceObserved'])

    def test_original_atlas_page_difference_is_not_merged(self):
        high,_ = self.reports['GPU_6'];low,_ = self.reports['GPU_1']
        one = {r['id']:r for r in high['instances']};two = {r['id']:r for r in low['instances']}
        # Same building and geometry can reference a different original atlas.
        changed = [i for i in one if one[i]['bindings']and two[i]['bindings']and
                   one[i]['bindings'][0]['atlas']!=two[i]['bindings'][0]['atlas']]
        self.assertGreater(len(changed),0)
        self.assertTrue(all('_l' in two[i]['recordPath'] for i in changed))

    def test_missing_slot1_records_are_not_borrowed_from_slot0(self):
        report,sources = self.reports['GPU_1']
        with tempfile.TemporaryDirectory()as temp:
            result = export_preview(copy.deepcopy(report),sources,LEGACY,Path(temp))
            self.assertEqual(result['displayedInstances'],35)
            missing = {r['id']for r in result['omitted']if 'lightmap' in r['reason']}
            self.assertEqual(missing,{935785592,269862216,935792072})
            manifest = json.loads((Path(temp)/'manifest.json').read_text())
            self.assertFalse(manifest['sourceSelection']['actualDeviceObserved'])

    def test_no_replacement_for_unimplemented_lightmap_disabled_branch(self):
        report,sources = self.reports['GPU_0M']
        self.assertFalse(report['settings']['ShowModelLightMap'])
        self.assertFalse(report['settings']['ShowTerrainLightMap'])
        with tempfile.TemporaryDirectory()as temp:
            with self.assertRaisesRegex(ValueError,'no substitute'):
                export_preview(report,sources,LEGACY,Path(temp))

    def test_unknown_profile_is_not_guessed(self):
        with self.assertRaisesRegex(ValueError,'explicit original GPU profile'):
            resolve(self.image,DEFAULT_SOURCE,DEFAULT_APK,'auto',LEGACY)


class PublicBoundaryTests(unittest.TestCase):
    def test_small_mask_override_prevents_invariant_export(self):
        data={'profiles':{'MEM':{'defaults':[{'Default':[['UseSmallTerrainMask',False]]}],
                                'overrides':{'saved':{'UseSmallTerrainMask':True}}}}}
        with self.assertRaisesRegex(ValueError,'invariant'):
            mask_baseline(data)

    def test_missing_mask_declaration_is_not_synthesized(self):
        with self.assertRaisesRegex(ValueError,'invariant'):
            mask_baseline({'profiles':{'MEM':{'defaults':[],'overrides':{}}}})

    def test_connector_rejects_live_repository(self):
        from connect_tutorial_preview import connect
        with self.assertRaisesRegex(ValueError,'ignored local preview'):
            connect(ROOT,ROOT/'analysis/raw')


if __name__=='__main__':
    unittest.main()
