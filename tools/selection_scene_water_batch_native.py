"""Original water batch CPU stores and capability producer with explicit inputs.

No buffer/texture/GPU creation is returned as a fake native success. The batch
writer starts after allocation/map and stops before upload/unmap callbacks.
"""
from terrain_water import NativeWater
from source_physics import SourcePhysics


def capability(image,version,backend=4):
 from unicorn import UC_HOOK_CODE
 class Probe(SourcePhysics):
  KIND=0x30000900
  def hook(self,uc,a,n,d):
   if a==self.KIND:self.set('W0',backend)
   elif self.imports.get(a)=='strstr':
    text=self.cstr(self.get('X0'));needle=self.cstr(self.get('X1'));i=text.find(needle);self.set('X0',self.get('X0')+i if i>=0 else 0)
   elif self.imports.get(a)=='sscanf':self.set('W0',0) # Explicit vendor text does not match Adreno.
   else:return super().hook(uc,a,n,d)
   self.set('PC',self.get('X30'))
 p=Probe(image);p.uc.hook_add(UC_HOOK_CODE,p.hook,begin=p.KIND,end=p.KIND)
 driver,table,vendor,limits=p.alloc(0x2100),p.alloc(0x200),p.alloc(64),p.alloc(32)
 p.w(driver,'Q',table);p.w(table+0xc0,'Q',p.KIND);p.w(driver+0x900,'I',version);p.uc.mem_write(vendor,b'WebGL2 adapter\0');p.w(limits+0xb,'B',8)
 p.call(0x13b7ad0,{'X0':driver,'X1':vendor,'X2':limits},floats={'S0':0.})
 return {'versionInput':version,'backendInput':backend,'extensionsInput':'empty','vendorInput':'explicit WebGL2 adapter; not Android observation',
  'native13b7ad0Executed':True,'capabilityWord':p.r(driver+0x1b0,'Q')[0],
  'driver1b5Bit5':bool(p.r(driver+0x1b5,'B')[0]&0x20),'GPUObserved':False}


class NativeWaterBatch(NativeWater):
 def source_depth(self):
  e=self.e;e.set('SP',e.STACK);e.set('X20',self.tile)
  self.fragment(0x356fac,0x357024)
  densities=list(e.r(e.STACK+0x28,'64f'));levels=list(e.r(e.STACK+0x128,'64f'))
  expected=[c['waterHeight']if c['flags']&0x10000 else -100. for c in self.chunks]
  if densities!=[5.]*64 or levels!=expected:raise ValueError('Original water-stage inputs differ')
  out=e.alloc(16384);e.set('X19',out);self.fragment(0x357030,0x35724c)
  return bytes(e.uc.mem_read(out,16384)),{'original356facPreparationExecuted':True,'sourceDensity':5.,'sourceInactiveWaterSentinel':-100.}

 def buffers(self,common_rgb):
  e=self.e;wet=[c for c in self.chunks if c['flags']&0x10000];n=len(wet)
  if not n:raise ValueError('Original source water batch is empty')
  vertices=e.alloc(n*128);indices=e.alloc(n*12)
  e.w(0x2527834,'3f',*common_rgb);cfg=e.r(e.r(0x2528db0,'Q')[0]+0x270,'Q')[0]
  e.set('X8',vertices);e.set('X9',indices);e.set('X19',self.tile);e.set('X23',cfg)
  self.fragment(0x354878,0x354a08)
  if e.get('W22')!=n*4 or e.get('W24')!=n*6:raise ValueError('Original water batch counts differ')
  vb=bytes(e.uc.mem_read(vertices,n*128));ib=bytes(e.uc.mem_read(indices,n*12))
  import struct,hashlib
  result={'positions':[v for j in range(n*4)for v in struct.unpack_from('<3f',vb,j*32)],
   'uvs':[v for j in range(n*4)for v in struct.unpack_from('<2f',vb,j*32+12)],
   'colors':[v for j in range(n*4)for v in struct.unpack_from('<4B',vb,j*32+28)],
   'indices':list(struct.unpack('<'+str(n*6)+'H',ib)),
   'stride':32,'wetChunks':[c['chunk']for c in wet],'vertexBytesSHA256':hashlib.sha256(vb).hexdigest(),
   'indexBytesSHA256':hashlib.sha256(ib).hexdigest(),'native354878StoresExecuted':True,'GPUUploadExecuted':False}
  for j,c in enumerate(wet):
   cx,cz=c['chunk'];x,z=e.r(self.tile+8,'2i');h=c['waterHeight']
   expected=[x*64+cx*8,h,z*64+cz*8,x*64+cx*8+8,h,z*64+cz*8,x*64+cx*8,h,z*64+cz*8+8,x*64+cx*8+8,h,z*64+cz*8+8]
   if result['positions'][j*12:j*12+12]!=expected:raise ValueError('Original water batch does not match original source chunk coordinates')
   if result['indices'][j*6:j*6+6]!=[j*4,j*4+2,j*4+1,j*4+1,j*4+2,j*4+3]:raise ValueError('Original source water batch index order differs')
  return result
