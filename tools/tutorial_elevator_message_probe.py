"""Original ObjectCreate parsing and StaticObject-to-motion-task candidate.

Raw packet values are explicit fixtures. No server message, has_physics admission,
automatic elevator cycle, existing save or production runtime is invented.
"""
import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

from native_combat import descriptor_fields
from tutorial_elevator_runtime_probe import ElevatorRuntimeProbe
from tutorial_map_geometry import local_output

DESCRIPTORS={
 'CxGS_Vec3':(0x2028fc8,44,'3448370d16d6eeb949ea17222bab1bd78db0d53f725bcea16fd35cf9ac7a89eb'),
 'GS2C_ObjectLocation':(0x2028ff7,134,'87bc09b6b7d768c845fe372493da6eed438b22a68bf97ac929e007c1f8782b70'),
 'GS2C_ObjectStaticObj':(0x2029120,558,'0879594cceac9c52685f4c636c1a9a87c3dec8dd19885a5a630e3bb4dddccf77'),
 'GS2C_ObjectCreate':(0x20297ec,361,'9b885cd9c85fe6ccc241c05531c773e0fda176de821eca3e351e4dda8c5b389f'),
}

def varint(value):
 if type(value)is not int or not 0<=value<1<<64:raise ValueError('Explicit unsigned packet integer required')
 out=bytearray()
 while value>127:out.append((value&127)|128);value>>=7
 out.append(value);return bytes(out)

def vector(v):
 if len(v)!=3 or not all(math.isfinite(x)for x in v):raise ValueError('Explicit finite vector required')
 return b''.join(varint((i+1)<<3|5)+struct.pack('<f',x)for i,x in enumerate(v))

def nested(number,raw):return varint(number<<3|2)+varint(len(raw))+raw

def packet_fixture(*,guid,map_id,position,direction,velocity,entry,display_id,spawn_id,model_idx,has_physics,scale,euler,minimum,maximum):
 """All active values are supplied; source table speed/delay are never read."""
 if type(has_physics)is not bool:raise ValueError('Explicit packet has_physics required')
 if not math.isfinite(minimum)or not math.isfinite(maximum):raise ValueError('Explicit finite packet limits required')
 loc=b'\x08'+varint(map_id)+nested(2,vector(position))+nested(3,vector(direction))+nested(4,vector(velocity))
 fields={1:entry,2:display_id,3:14,4:spawn_id,8:model_idx,9:int(has_physics)}
 static=b''.join(varint(i<<3)+varint(value)for i,value in fields.items())+nested(10,vector(scale))+nested(11,vector(euler))
 static+=varint(16<<3|5)+struct.pack('<f',minimum)+varint(17<<3|5)+struct.pack('<f',maximum)
 return b'\x08'+varint(guid)+nested(2,loc)+nested(7,static)


class ElevatorMessageProbe(ElevatorRuntimeProbe):
 def __init__(self,image):
  self.packet_mode=False;self.source_consumption=False;self.parsed=None;self.packet_parse_ok=None;self.boundaries=[]
  super().__init__(image)
  from unicorn import UC_HOOK_CODE
  for at in(0xa3f90c,0xa3700c,0xa38ad4,0xa5580c):self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=at,end=at)
  self.schema={}
  for name,(at,size,sha)in DESCRIPTORS.items():
   raw=image.read(at,size)
   if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('Original object descriptor differs')
   result=descriptor_fields(raw)
   if result['name']!=name:raise ValueError('Original object descriptor name differs')
   self.schema[name]=result

 def hook(self,uc,at,size,data):
  if self.packet_mode and at==0xa3f90c:self.packet_parse_ok=bool(self.get('W0'));return
  if self.packet_mode and at==0xa3700c:
   pointer=self.get('X1');self.parsed=self.alloc(0x60)
   self.uc.mem_write(self.parsed,bytes(self.uc.mem_read(pointer,0x60)));self.set('PC',self.EXIT);return
  if self.source_consumption and at==0xa38ad4:
   self.boundaries.append({'original':'0xa38ad4','scope':'interactive/UI cache boundary; not executed'})
   self.set('PC',self.get('X30'));return
  return super().hook(uc,at,size,data)

 def parse_packet(self,raw):
  if not isinstance(raw,bytes)or not 0<len(raw)<=16384:raise ValueError('Bounded raw original-schema packet required')
  stream=self.alloc(0x40);data=self.alloc(len(raw)+4);self.w(data,'I',len(raw));self.uc.mem_write(data+4,raw)
  self.w(stream+0x20,'2Q',data,data+len(raw)+4)
  self.packet_mode=True;self.parsed=None;self.packet_parse_ok=None
  try:self.call(0xa3f8b8,{'X1':stream},limit=300000)
  finally:self.packet_mode=False
  if not self.packet_parse_ok or self.parsed is None:raise ValueError('Original ObjectCreate parser rejected packet')
  p=self.parsed;flags=self.r(p+0x5c,'I')[0]
  if flags&0x88!=0x88:raise ValueError('Candidate requires explicit original location/static payloads')
  static=self.r(p+0x48,'Q')[0];location=self.r(p+0x28,'Q')[0]
  if not static or not location:raise ValueError('Original nested message absent')
  sf=self.r(static+0x80,'I')[0];lf=self.r(location+0x30,'I')[0]
  # Do not turn protobuf defaults into observed runtime scale, speed or state.
  required_static=(1<<0)|(1<<1)|(1<<2)|(1<<3)|(1<<7)|(1<<8)|(1<<9)|(1<<10)|(1<<15)|(1<<16)
  if sf&required_static!=required_static or lf&15!=15:raise ValueError('Candidate requires all motion/TRS fields explicitly present')
  def vec(a):
   q=self.r(a,'Q')[0]
   if not q:raise ValueError('Explicit original vector absent')
   return list(self.r(q+0x10,'3f'))
  self.packet={'guid':self.r(p+0x10,'Q')[0],'map':self.r(location+0x28,'i')[0],
    'entry':self.r(static+0x10,'i')[0],'displayId':self.r(static+0x14,'i')[0],
    'type':self.r(static+0x18,'i')[0],'spawnId':self.r(static+0x1c,'i')[0],
    'modelIndex':self.r(static+0x48,'i')[0],'hasPhysics':bool(self.r(static+0x5c,'B')[0]),
    'position':vec(location+0x10),'direction':vec(location+0x18),'velocity':vec(location+0x20),
    'scale':vec(static+0x40),'euler':vec(static+0x50),
    'minimum':self.r(static+0x60,'f')[0],'maximum':self.r(static+0x64,'f')[0],
    'nativeObjectCreateParsed':True,'nativeConstructorsExecuted':True,
    'staticPresenceBits':sf,'locationPresenceBits':lf,'bytesConsumed':self.r(stream+0x10,'Q')[0],
    'liveActivityObserved':False,'physicsAdmissionProven':False}
  return dict(self.packet)

 def consume_prepared_lift(self):
  """Run a551c8 through real task+48 and real position/scale setters.

  The actor/loaded PHY and registry are explicit prepared inputs. has_physics
  is retained as a packet field, not used to manufacture original admission.
  """
  if not self.lift or not self.parsed or self.packet['type']!=14:raise ValueError('Prepared original lift and parsed type14 required')
  actor=self.lift['actor']
  if self.packet['guid']!=self.r(actor+8,'Q')[0]:raise ValueError('Packet GUID differs from explicitly prepared actor')
  if not self.packet['minimum']<self.packet['maximum']:raise ValueError('Original movement branch requires minimum < maximum')
  self.boundaries=[];self.source_consumption=True
  try:end=self.fragment(0xa551c8,(0xa5580c,),{'X0':actor,'X1':self.parsed})
  finally:self.source_consumption=False
  return {'nativeStaticObjectConsumerExecuted':True,'end':hex(end),
   'position':list(self.r(actor+0x118,'3f')),'scale':list(self.r(actor+0x158,'3f')),
   'eulerStored':list(self.r(actor+0x164,'3f')),'minimum':self.r(actor+0xccc,'f')[0],
   'maximum':self.r(actor+0xcd0,'f')[0],'entry':self.r(actor+0xc90,'i')[0],
   'displayId':self.r(actor+0xc7c,'i')[0],'type':self.r(actor+0xc88,'i')[0],
   'taskGuid':self.r(self.lift['task']+8,'Q')[0],
   'taskPosition':list(self.r(self.lift['task']+0x10,'3f')),
   'taskVelocityPerMs':list(self.r(self.lift['task']+0x1c,'3f')),
   'boundaries':list(self.boundaries),'originalActorFactoryExecuted':False,
   'originalHasPhysicsAdmissionExecuted':False,'wholeOriginalFrameExecuted':False}


if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--library',type=Path,required=True);p.add_argument('--packet',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 from analyze_native_resources import NativeImage
 e=ElevatorMessageProbe(NativeImage(a.library.read_bytes()));r=e.parse_packet(a.packet.read_bytes())
 out=local_output(a.output);out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({'output':str(out),'sourceParse':True,'admissionOrActivityInvented':False}))
