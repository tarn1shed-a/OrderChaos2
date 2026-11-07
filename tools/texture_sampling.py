"""Source texture format/default-state evidence, not an active quality preset."""
import hashlib,struct

ROUTINES={
 0x144cc44:(132,'0bc5e79bfe0732100f855d75d9d5f4e58e769735b0f8329be98e09c23804c554'),
 0x13d1614:(164,'ad7d4820c3eb26810c5f216fe474ad03ce34270c638e968812720d128ef5377c'),
 0x13d1424:(428,'33210b1cfa5fa87d15aeb55349f7bf1dcd46570db90831e0b8962ab9f24f89c9'),
 0x14527f8:(92,'875ceab1ba5f2e813ec26a4a0e15872941516c0d8dec95adb1a8f73a24e1df64'),
 0x1452690:(12,'aca0c5841bfc2b2fee7797acec04e61f3f4fadd8289757e24115c3d64746cf74'),
 0x146d4a8:(1864,'dd5b323f78dacc1a56a936de64b3f8ed7adf66e5de349d049ce1de66d3b6f133'),
}
FORMAT_ADDRESS=0x1f4e888
FORMAT_SHA256='201a81fbfcf22554099b644e37915ad28fafc2e43a76047b237b743e967b3f1b'

def verify_sampling(image):
 for at,(size,digest) in ROUTINES.items():
  if hashlib.sha256(image.read(at,size)).hexdigest()!=digest:raise ValueError('Texture sampling routine changed; retrace required')
 raw=image.read(FORMAT_ADDRESS,40)
 if hashlib.sha256(raw).hexdigest()!=FORMAT_SHA256:raise ValueError('Texture format descriptor changed; retrace required')
 if struct.unpack_from('<4I',raw,4)!=(255,65280,16711680,4278190080) or raw[21]!=4 or list(raw[28:32])!=[0,8,16,24]:raise ValueError('Unexpected mask format byte lanes')
 # The source name getter returns this relocated table, not a guessed name
 # based solely on the descriptor masks.
 slot=0x2498d88+22*8
 rels=[r for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations() if r['r_offset']==slot]
 if len(rels)!=1 or rels[0]['r_addend']!=0x1f4a5de or image.read(rels[0]['r_addend'],6)!=b'RGBA8\0':raise ValueError('Texture format source name changed')
 return mask_upload_profile()

def mask_upload_profile():
 return {'format':'oc2-source-mask-upload-v1','sourceFormatId':22,'sourceFormatName':'RGBA8','bytesPerPixel':4,
  'littleEndianComponentMasks':[255,65280,16711680,4278190080],'componentShifts':[0,8,16,24],
  'channelToByteLane':[0,1,2,3],'sourceDescriptor':hex(FORMAT_ADDRESS),'sourceDescriptorSHA256':FORMAT_SHA256,
  'sourceFormatNameTable':'0x2498d88','sourceFormatNameGetter':'0x1452690',
  'textureDefaults':{'sourceConstructor':'0x146d4a8','initialSamplerBits':'0x49120000',
   'minFilterWithoutMips':{'id':1,'name':'Linear'},'minFilterWithMips':{'id':3,'name':'Linear Mipmap Nearest'},
   'magFilter':{'id':1,'name':'Linear'},'powerOfTwoNonType3AddressMode':{'id':0,'name':'Repeat'},
   'filterNameTable':'0x24995b8','addressNameTable':'0x24995f0','appliedAsActiveQualityPreset':False},
  'limits':['RGBA8 raw-mask byte ordering is verified. These are constructor defaults, not proof of the active device quality or material-specific sampler overrides.',
   'Original mip chains, small/baked masks, material overrides and runtime filter selection still need separate evidence.']}
