import hashlib
import struct
import tempfile
import unittest
from pathlib import Path

from control_assets import recover_controls, METHODS
from hud_assets import recover_hud_assets
from resource_packs import ResourceArchive, DEFAULT_SOURCE


class ControlAssetsTests(unittest.TestCase):
    @unittest.skipUnless(all((DEFAULT_SOURCE/p).is_file() for p in ['ui.bin','conf.bin','tables.bin','ui_icon_1.bin','ui_icon_2.bin']),
                         'Original game UI/skill files are local-only')
    def test_original_method_fingerprints_links_icons_and_geometry(self):
        archives={}
        def extract(path):
            pack=('conf.bin' if path.startswith('ui/Config/') else 'tables.bin' if path.startswith('tables/')
                  else 'ui_icon_2.bin' if '/interactive/' in path else 'ui_icon_1.bin' if '/icons/' in path else 'ui.bin')
            if pack not in archives:archives[pack]=ResourceArchive(DEFAULT_SOURCE/pack)
            return archives[pack].read(path)
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary);hud=recover_hud_assets(extract,output)
            p=recover_controls(extract,output,hud)
            self.assertEqual(hud['nativeControls']['format'],'oc2-original-mobile-controls-v2')
            self.assertEqual({k:v['codeSHA256'] for k,v in p['methods'].items()},METHODS)
            self.assertEqual(p['joystick']['stopArguments'],[-1000,False,False,0])
            self.assertEqual(p['icons']['sword']['sourceRuneId'],280)
            self.assertEqual(p['icons']['unarmed']['sourceRuneId'],16)
            self.assertFalse(p['attack']['nativeWeaponToSkillSelectionRecovered'])
            self.assertFalse(p['interaction']['nativeJumpPhysicsRecovered'])
            self.assertEqual(p['containers']['Joystick']['bodyCount'],1864)
            self.assertEqual(p['hitZones']['attack']['sourceShapeId'],2291)
            self.assertEqual(p['hitZones']['interaction']['sourceShapeId'],2282)
            self.assertIn('Q ',p['hitZones']['interaction']['pathPixels'])
            for key,icon in p['icons'].items():
                raw=(output/('control-'+key+'.png')).read_bytes()
                self.assertEqual(raw,extract(icon['sourcePath']))
                self.assertEqual(hashlib.sha256(raw).hexdigest(),icon['sourceSHA256'])
            self.assertAlmostEqual(p['iconPlacements']['attack']['boundsFraction'][0],15.2/138)
            self.assertAlmostEqual(p['iconPlacements']['interaction']['boundsFraction'][0],29.2/102)
            # A changed table cannot silently keep a previously selected icon.
            def changed(path):
                raw=extract(path)
                return raw.replace(b'skill/sword.png',b'skill/other.png') if path=='tables/skill_runes.tbl' else raw
            with self.assertRaisesRegex(ValueError,'proto/rune/icon'):recover_controls(changed,output,hud)
            def changed_constant(path):
                raw=extract(path)
                return raw.replace(struct.pack('<d',.33),struct.pack('<d',.34),1) if path.endswith('Joystick.swf') else raw
            with self.assertRaisesRegex(ValueError,'container changed'):recover_controls(changed_constant,output,hud)


if __name__=='__main__':unittest.main()
