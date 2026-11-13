import unittest
from resource_packs import DEFAULT_SOURCE,ResourceArchive
from role_ui_evidence import evidence,PINS

@unittest.skipUnless((DEFAULT_SOURCE/'ui.bin').is_file(),'Original UI archives stay local')
class OriginalRoleUI(unittest.TestCase):
 def read(self,path):return ResourceArchive(DEFAULT_SOURCE/('conf.bin'if path.startswith('ui/Config/')else'ui.bin')).read(path)
 def test_tutorial_gate_and_actual_attribute_page_do_not_validate_the_prototype_sidebar(self):
  r=evidence(self.read);self.assertEqual(r['tutorialMenuEntranceHiddenOnMap'],5)
  self.assertEqual([v['name']for v in r['characterRoute']],['AttributePage','BaseInfo','IGMContainer'])
  self.assertFalse(r['originalHeadNameStyleKnown']);self.assertFalse(r['originalCharacterPageRendered']);self.assertFalse(r['replacementArtGenerated'])
 def test_changed_original_ui_is_rejected(self):
  with self.assertRaisesRegex(ValueError,'source changed'):evidence(lambda p:self.read(p)+(b'x'if p in PINS else b''))

if __name__=='__main__':unittest.main()
