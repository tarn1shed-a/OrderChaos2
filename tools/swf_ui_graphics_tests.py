import struct,unittest
from character_portraits_tests import rect
from swf_ui_graphics import paths,shape,text_style

class SourceGraphicsTests(unittest.TestCase):
 def test_fill_contours_join_by_endpoint_keep_curves_and_multiple_islands(self):
  edges=[((0,0),None,(10,0)),((10,10),None,(0,0)),((10,0),(12,5),(10,10)),((20,0),None,(20,0))]
  self.assertEqual(paths(edges,True),'M 0 0 L 10 0 Q 12 5 10 10 L 0 0 Z M 20 0 L 20 0 Z')
  with self.assertRaisesRegex(ValueError,'Open'):paths(edges[:1],True)
  self.assertEqual(paths(edges[:1],False),'M 0 0 L 10 0')
 def test_rgba_shape_reads_paints_and_rejects_unknown_or_unbounded_styles(self):
  prefix=struct.pack('<H',1)+rect([0,100,0,100])
  # One solid fill, no strokes, one fill bit, zero line bits, end record.
  raw=prefix+b'\x01\x00\x01\x02\x03\x04\x00\x10\x00'
  self.assertEqual(shape(32,raw)['fills'],[])
  for bad in [raw[:-1],raw+b'\x00',prefix+b'\x11',prefix+b'\x01\x13',prefix+b'\x01\x00\x01']:
   with self.assertRaises(ValueError):shape(32,bad)
  with self.assertRaises(ValueError):shape(22,raw)
 def test_shape4_reserved_flags_and_mid_shape_styles_fail_closed(self):
  prefix=struct.pack('<H',1)+rect([0,100,0,100])
  with self.assertRaisesRegex(ValueError,'flags'):shape(83,prefix+rect([0,100,0,100])+b'\x08')
  # Empty style arrays, zero style bits, StyleChangeRecord StateNewStyles=1.
  with self.assertRaisesRegex(ValueError,'Mid-shape'):shape(32,prefix+b'\x00\x00\x00\x40')
 def test_edittext_requires_full_supported_style_extent(self):
  prefix=struct.pack('<H',7)+rect([-40,1000,-40,1000])
  raw=prefix+b'\x85\x20'+struct.pack('<HH',6,760)+bytes([255]*4)+bytes([0])+struct.pack('<HHHh',0,0,0,40)+b'\0<p></p>\0'
  s=text_style(37,raw);self.assertEqual(s['fontHeight'],38);self.assertEqual(s['leadingPixels'],2);self.assertFalse(s['border'])
  with self.assertRaises(ValueError):text_style(37,raw+b'\0')
  with self.assertRaises(ValueError):text_style(32,raw)

if __name__=='__main__':unittest.main()
