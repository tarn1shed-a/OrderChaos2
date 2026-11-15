"""Exact ratio-zero solid DefineMorphShape start, not an interpolating player.

Adobe SWF19 pp145/148/150 (zero based PDF146/149/151):
https://open-flash.github.io/mirrors/swf-spec-19.pdf
Only the original solid-fill/round-line subset used by this UI is accepted.
"""
import struct
from ui_assets import Bits
from swf_ui_graphics import shape

def morph_start(kind,raw,*,ratio):
 if kind!=46 or ratio!=0:raise ValueError('Only source DefineMorphShape ratio zero is recovered')
 if not isinstance(raw,(bytes,bytearray)) or len(raw)<10:raise ValueError('Truncated morph record')
 try:
  bits=Bits(raw,2);start=bits.rect();rect_end=bits.pos();end=bits.rect();offset_at=bits.pos()
 except IndexError as error:raise ValueError('Truncated morph bounds') from error
 if offset_at+4>len(raw):raise ValueError('Truncated morph offset')
 offset=struct.unpack_from('<I',raw,offset_at)[0];at=offset_at+4;end_edges=at+offset
 if not at<end_edges<len(raw):raise ValueError('Morph EndEdges offset outside record')
 def take(n):
  nonlocal at
  if at+n>end_edges:raise ValueError('Truncated morph styles')
  value=raw[at:at+n];at+=n;return value
 def count():
  value=take(1)[0]
  if value==255:raise ValueError('Extended morph style count not recovered')
  if value>16:raise ValueError('Morph styles outside recovered UI span')
  return value
 fills=[]
 for _ in range(count()):
  if take(1)!=b'\0':raise ValueError('Only source solid morph fills are recovered')
  color=take(4);take(4);fills.append(b'\0'+color)
 lines=[]
 for _ in range(count()):
  width=take(2);take(2);color=take(4);take(4);lines.append(width+color)
 if at>=end_edges:raise ValueError('Source start edges unavailable')
 # Shape3 uses the same RGBA shape records. Preserve source rect and edges;
 # only split the original interleaved start/end style records at ratio zero.
 static=(raw[:rect_end]+bytes([len(fills)])+b''.join(fills)+bytes([len(lines)])+
         b''.join(lines)+raw[at:end_edges])
 result=shape(32,static,extended=True)
 if result['boundsTwips']!=start:raise ValueError('Morph start bounds changed')
 result['sourceMorph']={'kind':kind,'ratio':ratio,'startBounds':start,'endBounds':end,
   'startEdgesSpan':[at,end_edges],'endEdgesSpan':[end_edges,len(raw)],'interpolated':False}
 return result
