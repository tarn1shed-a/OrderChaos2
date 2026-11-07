import tempfile,unittest
from pathlib import Path
from resource_packs import ResourceArchive,DEFAULT_SOURCE,index
from native_quest import recover_quest_data,verify_quest_native,PROTOCOL
from quest_assets import recover_quest_ui,METHODS
ROOT=Path(__file__).resolve().parents[1]
class QuestAssetsTests(unittest.TestCase):
 def test_changed_native_descriptor_requires_retrace(self):
  class Changed:
   def read(self,a,n):return bytes(n)
  with self.assertRaisesRegex(ValueError,'retrace'):verify_quest_native(Changed())
 @unittest.skipUnless((ROOT/'analysis/raw/beff-native/library.so').is_file(),'Original library stays local')
 def test_native_runtime_object_flags_and_quest_fields_are_separate_from_spawn_state(self):
  from analyze_native_resources import NativeImage
  p=verify_quest_native(NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes()))
  self.assertEqual(set(p),set(PROTOCOL));fields={f['name']:f for f in p['GS2C_ObjectStaticObj']['fields']}
  self.assertEqual(fields['can_loot']['number'],14);self.assertEqual(fields['quest_status']['number'],12);self.assertEqual(fields['interactives']['label'],3)
  self.assertEqual({f['name']:f['number'] for f in p['GS2C_QuestInfo']['fields']}['status'],2)
 @unittest.skipUnless((DEFAULT_SOURCE/'ui.bin').is_file(),'Original quest UI stays local')
 def test_source_layout_methods_chinese_quest_links_and_art(self):
  rows=index(DEFAULT_SOURCE);archives={}
  def extract(path):
   matches=[r for r in rows if r['path']==path and r['pack'] in ['ui.bin','tables.bin','conf.bin','ui_icon_2.bin']]
   self.assertEqual(len(matches),1,path);pack=matches[0]['pack']
   if pack not in archives:archives[pack]=ResourceArchive(DEFAULT_SOURCE/pack)
   return archives[pack].read(path)
  data=recover_quest_data(extract);self.assertFalse(data['serverScriptsRecovered'])
  self.assertEqual({r['id']:r['title'] for r in data['catalog']},{572:'阴谋败露',632:'苹果苹果红酒'})
  self.assertEqual(len(data['objects']),3);self.assertEqual(next(q for q in data['catalog'] if q['id']==632)['sourceObjects'],[621])
  with tempfile.TemporaryDirectory() as temp:
   p=recover_quest_ui(extract,temp,data);self.assertEqual({k:v['codeSHA256'] for k,v in p['methods'].items()},METHODS)
   fields=p['layouts']['book']['fields'];self.assertAlmostEqual(fields['panel_list.item_1']['matrixPixels'][5]-fields['panel_list.item_0']['matrixPixels'][5],63.8)
   self.assertEqual(p['assets']['unfinished']['sourcePath'],'ui/icons/head_obj/quest_unfinished.png');self.assertTrue((Path(temp)/'ui/quest-unfinished.png').is_file());self.assertFalse(p['provenance']['swfScriptExecution'])
if __name__=='__main__':unittest.main()
