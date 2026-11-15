"""Original task artwork/mask checks; full source drawings remain private."""
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from xml.etree import ElementTree as ET

from swf_morph_start import morph_start

PUBLIC='--public-only' in sys.argv or os.environ.get('PUBLIC_ONLY')=='1'
if '--public-only' in sys.argv:sys.argv.remove('--public-only')
ROOT=Path(__file__).resolve().parents[1]
NS={'s':'http://www.w3.org/2000/svg'}


class UnsupportedMorph(unittest.TestCase):
 def test_nonzero_progress_never_becomes_a_zero_frame(self):
  for kind,ratio in [(46,1),(46,65535),(84,0),(32,0)]:
   with self.assertRaises(ValueError):morph_start(kind,b'',ratio=ratio)
 def test_missing_bounds_are_not_accepted(self):
  for raw in [b'',b'\0',b'\0'*9,b'\0\0\xff'+b'\0'*8]:
   with self.assertRaises(ValueError):morph_start(46,raw,ratio=0)


@unittest.skipIf(PUBLIC,'Private original source excluded')
class SourceArtwork(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  from map_loading_evidence import Sources
  from resource_packs import DEFAULT_SOURCE
  from hud_assets import document
  from ui_assets import Bits,tags
  cls.source=DEFAULT_SOURCE
  try:
   s=Sources(DEFAULT_SOURCE);raw=s.read('ui/Flash/library.swf')
  except (FileNotFoundError,KeyError):raise unittest.SkipTest('Original source unavailable')
  cls.s=s;cls.library=document(raw,'ui/Flash/library.swf',False)
  h=Bits(raw,8);h.rect();matches=[]
  for k,a,n in tags(raw,h.pos()+4,len(raw)):
   if k==46 and struct.unpack_from('<H',raw,a)[0]==486:matches.append(raw[a:a+n])
  if len(matches)!=1:raise ValueError('Specific original cooldown morph changed')
  cls.morph=matches[0]
  from quest_journal_art import recover
  cls.temp=tempfile.TemporaryDirectory(prefix='journal-art-test-',dir=ROOT/'analysis/raw')
  cls.out=Path(cls.temp.name)/'export';cls.art=recover(DEFAULT_SOURCE,cls.out)
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 def test_cooldown_zero_keeps_the_actual_bottom_strip(self):
  v=morph_start(46,self.morph,ratio=0)
  self.assertEqual(v['boundsTwips'],[0,1699,1730,1830])
  self.assertEqual(v['fills'][0]['paint'],{'kind':'solid','color':[0,0,0,255]})
  self.assertEqual(v['fills'][0]['path'],'M 1699 1730 L 0 1730 L 0 1830 L 1699 1830 L 1699 1730 Z')
  self.assertEqual(v['sourceMorph']['startEdgesSpan'],[43,59])
  self.assertFalse(v['sourceMorph']['interpolated'])
 def test_bad_end_edges_offset_is_rejected(self):
  from ui_assets import Bits
  b=Bits(self.morph,2);b.rect();b.rect();at=b.pos()
  bad=bytearray(self.morph);struct.pack_into('<I',bad,at,len(bad))
  with self.assertRaisesRegex(ValueError,'offset outside'):morph_start(46,bytes(bad),ratio=0)
 def test_non_solid_morph_style_is_not_replaced(self):
  from ui_assets import Bits
  b=Bits(self.morph,2);b.rect();b.rect();at=b.pos()+4
  bad=bytearray(self.morph);bad[at+1]=16
  with self.assertRaisesRegex(ValueError,'solid'):morph_start(46,bytes(bad),ratio=0)
 def test_all_bitmap_files_are_unchanged_source_bytes(self):
  self.assertEqual(len(self.art['assets']),17)
  for path,v in self.art['assets'].items():
   raw=(self.out/v['file']).read_bytes()
   self.assertEqual(hashlib.sha256(raw).hexdigest(),v['sha256'])
   if path!='ui/icons/item/gold_coin.png':self.assertEqual(raw,self.s.read(path))
   else:self.assertEqual(self.art['nativeResourceSelections'][path]['pack'],'ui_icons_upd14.bin')
 def test_no_filled_resource_gaps(self):
  self.assertEqual(self.art['gaps'],[])
  self.assertEqual(set(self.art['windows']),{'QuestListHero','MessageBox'})
  for window in self.art['windows'].values():
   raw=(self.out/window['file']).read_bytes();root=ET.fromstring(raw)
   self.assertEqual(hashlib.sha256(raw).hexdigest(),window['sha256'])
   self.assertFalse(root.findall('.//*[@data-unrestored]'))
 def test_source_mask_geometries_are_kept(self):
  root=ET.parse(self.out/'QuestListHero.svg').getroot()
  clips=root.findall('.//s:clipPath',NS)
  self.assertGreater(len(clips),0)
  self.assertTrue(all(c.findall('s:path',NS)for c in clips))
  # The original morph serves as a clip, so its resolved geometry is moved
  # into defs; a visible replacement cooldown group would be incorrect.
  original=morph_start(46,self.morph,ratio=0)['fills'][0]['path']
  self.assertGreater(sum(p.get('d')==original for c in clips for p in c),0)
  self.assertEqual(root.findall('.//*[@data-source-morph-ratio="0"]'),[])
 def test_authored_track_and_disabled_frames_are_distinct(self):
  from hud_assets import document,named_path,resolve,sprite_frames
  d=document(self.s.read('ui/Flash/QuestListHero.swf'),'ui/Flash/QuestListHero.swf')
  l=self.library
  for name,v in self.art['stateDrawings'].items():
   root=ET.parse(self.out/v['file']).getroot();node=root.find('.//*[@data-state-root]')
   self.assertEqual(int(node.get('data-source-frame')),v['frame'])
   self.assertFalse(v['appliedToRuntime'])
  variant=self.art['stateDrawings']['active-disabled']
  p=named_path(d,99,'m_btnSetActive',l)
  self.assertEqual(variant['placement'],p)
  self.assertNotEqual(sprite_frames(l,p['leafCharacterId'])[0],sprite_frames(l,p['leafCharacterId'])[10])
 def test_export_does_not_include_a_task_or_saved_character(self):
  self.assertNotIn('accepted',self.art);self.assertNotIn('ActionIdItemTb0',json.dumps(self.art))
  self.assertTrue(all(p.startswith(('ui/','tables/String_'))for p in self.art['sources']))


if __name__=='__main__':unittest.main()
