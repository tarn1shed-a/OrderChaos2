import hashlib,json,tempfile,unittest
from pathlib import Path
from resource_packs import ResourceArchive,DEFAULT_SOURCE
from login_ui_assets import recover_login_ui,PINS
from hud_assets import document
from swf_ui_graphics import shape

@unittest.skipUnless((DEFAULT_SOURCE/'ui.bin').exists(),'Original UI archives stay local')
class OriginalEntryTests(unittest.TestCase):
 def setUp(self):self.archives={}
 def read(self,path):
  pack='conf.bin'if path.startswith('ui/Config/')else'tables.bin'if path.startswith('tables/')else'ui.bin'
  if pack not in self.archives:self.archives[pack]=ResourceArchive(DEFAULT_SOURCE/pack)
  return self.archives[pack].read(path)
 def test_drawings_paths_localization_and_exact_artwork(self):
  with tempfile.TemporaryDirectory()as td:
   r=recover_login_ui(self.read,td);self.assertEqual(r['stage'],[1136,640]);self.assertFalse(r['methods']['ASDefines.isPUB']['constantReturn'])
   self.assertEqual(r['methods']['WindowManager.resetUI']['codeSHA256'],'09e6cd50d37111dd0ea42b6c9e51cccea9a521ac28dc39d04f891e4812b84544')
   self.assertEqual(r['windows']['CharacterChooseCharacter']['sourceRoot'],35);self.assertEqual(r['strings']['GENERAL_MC_SELECT_BTN_PLAY']['text'],'开始')
   for path,a in r['assets'].items():self.assertEqual((Path(td)/a['url'].rsplit('/',1)[-1]).read_bytes(),self.read(path))
   svg=(Path(td)/'CharacterChooseCharacter.svg').read_text();self.assertIn('item_4._ExistCharacter.SelectedEff',svg);self.assertIn('clipPath',svg);self.assertNotIn('<script',svg)
   from xml.etree import ElementTree as E
   clips=E.fromstring(svg).findall('.//{http://www.w3.org/2000/svg}clipPath');self.assertTrue(clips)
   self.assertTrue(all(list(c)and all(v.tag.endswith('}path')for v in c)for c in clips))
 def test_changed_source_is_rejected_before_restoration(self):
  path='ui/Flash/QuickLogin.swf'
  with tempfile.TemporaryDirectory()as td:
   with self.assertRaisesRegex(ValueError,'source changed'):recover_login_ui(lambda p:self.read(p)+(b'x'if p==path else b''),td)
 def test_extended_styles_do_not_change_legacy_reader_contract(self):
  lib=document(self.read('ui/Flash/library.swf'),'library',False)
  for cid in [2189,2190,1543,1690,1523,1735]:
   record=lib['records'][cid]
   with self.assertRaises(ValueError):shape(*record)
   result=shape(*record,extended=True);self.assertTrue(result['fills']);self.assertTrue(all(v['path']for v in result['fills']))
if __name__=='__main__':unittest.main()
