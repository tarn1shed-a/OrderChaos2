import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from resource_packs import ResourceArchive,DEFAULT_SOURCE
from login_ui_assets import recover_login_ui
from xml.etree import ElementTree as ET

@unittest.skipUnless((DEFAULT_SOURCE/'ui.bin').is_file(),'Original UI archives stay local')
class AttributePageTests(unittest.TestCase):
 def test_original_attribute_drawings_fields_and_parent_measurements(self):
  archives={}
  def read(path):
   pack='conf.bin'if path.startswith('ui/Config/')else'tables.bin'if path.startswith('tables/')else'ui.bin'
   if pack not in archives:archives[pack]=ResourceArchive(DEFAULT_SOURCE/pack)
   return archives[pack].read(path)
  with TemporaryDirectory()as folder:
   profile=recover_login_ui(read,folder,management=True,attributes=True);p=profile['attributePage']
   self.assertEqual(p['selectedTab'],2);self.assertEqual(p['animatedFrames']['.CharacterAttrPanel.CharacterPanel.mc_content.Hp.valueBar'],60)
   self.assertEqual(p['labels']['.CharacterAttrPanel.CharacterPanel.mc_content.Hp.title_name'],'生命值：')
   self.assertEqual(p['iconFrames']['.CharacterAttrPanel.CharacterPanel.mc_content.Hp.item_icon'],5)
   self.assertEqual(p['iconFrames']['.CharacterAttrPanel.CharacterPanel.mc_content.Armor.item_icon'],4)
   self.assertAlmostEqual(p['pageSize'][0],879.7466934204101);self.assertAlmostEqual(p['pageSize'][1],571.8526077270508)
   svg=(Path(folder)/'AttributePage.svg').read_text();self.assertIn('data-attribute-frame="60"',svg);self.assertIn('clipPath',svg);self.assertNotIn('foreignObject',svg)
   nodes={node.get('data-source-path'):node for node in ET.fromstring(svg).iter()if 'data-source-path'in node.attrib}
   for path in p['labels']:
    self.assertIn(path,nodes,path)
    self.assertTrue(any(child.get('data-entry-text')=='true'for child in nodes[path].iter()),path)
   self.assertEqual(p['labels']['.CombatScorePanel.CSAttrPanel._TotalCombatScore._TxtDesc'],'总战斗力')

if __name__=='__main__':unittest.main()
