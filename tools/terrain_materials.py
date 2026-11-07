"""Bounded ATIL material/UV and raw mask recovery from the verified ARM64 reader.

Only source albedo is restored here. Native lighting, quality selection, water,
texture residency and batching are separate unfinished branches.
"""
import hashlib,json,math,struct
from pathlib import Path
from PIL import Image
from terrain_convert import string_table
from texture_sampling import ROUTINES as SAMPLING_ROUTINES,verify_sampling,mask_upload_profile

ROUTINES={
 0x354de4:(520,'71716ca4b6447af3e77b8d3d814682fc52043097514bd4123d85cf6a36772ad1'),
 0x358e08:(3272,'df1512b24d644ac3fa7f198f358c78b548d11c77b04e21fe560ca92d2d7e2227'),
 0x354fec:(384,'6a09f57257e209159ca291ad6f58677a1697eb1a822a8316385c20e80a54a350'),
 0x359ad0:(660,'3d2990aa71c0d9a0f29fbec070c8e8e4c373372a8499da3c04c9e0fce436bf7e'),
 0x355644:(1012,'d7801a24f22881346fb7e7cd3ffafbf05317d14f691417f11777449b9ccb7b8b'),
 0x355f28:(1204,'19aa377c20fb1189305326bbec4c5924c7b3cb5b0641b6aba4417d8c071535b4'),
 0x3509c4:(1108,'eb10b0d37fdb2153569863e3c40f77e703f5f394c65b6d847fae99b45a3d63e3'),
 0x146f58c:(240,'9382b1b3101fa6cc9b235c3d51e9a49eb36ad14d4e2482a484b57e17acec1942'),
}
ROUTINES.update(SAMPLING_ROUTINES)
SHADERS={'TerrainFP.glsl':'194acb5b7c438aad84a1abcc98ae89448a431a75f54b7408c686421454844504',
 'TerrainVP.glsl':'68ba120d664ceda3aece0249263d53e5bc85ea0bff419ae41ccec3d237442936'}

def verify_native(image):
 for address,(size,digest) in ROUTINES.items():
  if hashlib.sha256(image.read(address,size)).hexdigest()!=digest:raise ValueError('Terrain native routine changed; retrace required')
 verify_sampling(image)
 # 358e08 generates local vertex UV0 = (x,z)*0.125, UV1 = (x,z)/64.
 return {hex(a):{'bytes':n,'sha256':h} for a,(n,h) in ROUTINES.items()}

def tile_materials(raw):
 if len(raw)<24 or raw[:4]!=b'ATIL':raise ValueError('Invalid material tile header')
 version,x,z=struct.unpack_from('<3i',raw,4)
 if version not in (9,10):raise ValueError('Unsupported material tile version')
 stride=16 if version==9 else 24;heights=24+64*stride;end=(heights+29575+3)&~3
 if end+4>len(raw):raise ValueError('Truncated material tile')
 textures=string_table(raw,end);chunks=[]
 for i in range(64):
  at=24+i*stride;indices=list(struct.unpack_from('<5h',raw,at+6))
  if any(v < -1 or v>=len(textures) for v in indices):raise ValueError('Terrain texture index outside source table')
  chunks.append({'chunk':[i%8,i//8],'flags':struct.unpack_from('<I',raw,at)[0],'indices':indices})
 return {'tile':[x,z],'version':version,'recordStride':stride,'textures':textures,'chunks':chunks}

def mask_channels(channels):
 if len(channels)!=4:raise ValueError('Expected four source mask channels')
 present=[c for c in channels if c is not None]
 if not present:return None,[[0]*4 for _ in range(64)]
 count=len(present[0]);side=math.isqrt(count)
 if count!=side*side or side<8 or side>1024 or side&(side-1) or any(len(c)!=count for c in present):raise ValueError('Invalid source mask dimensions')
 rgba=bytearray(count*4);classes=[[0]*4 for _ in range(64)];step=side//8
 for channel,data in enumerate(channels):
  if data is None:continue
  rgba[channel::4]=data
  for z in range(8):
   for x in range(8):
    # Native scans the upper five bits. Values 0..7 prune a layer;
    # an all-248..255 chunk prunes every layer underneath it.
    values=[v&248 for row in range(z*step,(z+1)*step) for v in data[row*side+x*step:row*side+(x+1)*step]]
    classes[z*8+x][channel]=0 if not any(values) else 1 if all(v==248 for v in values) else 2
 return Image.frombytes('RGBA',(side,side),bytes(rgba)),classes

def effective_indices(indices,classes):
 if len(indices)!=5 or len(classes)!=4 or any(v not in (0,1,2) for v in classes):raise ValueError('Invalid source layer classification')
 result=list(indices)
 for channel in range(3,-1,-1):
  if classes[channel]==0:result[channel+1]=-1
  elif classes[channel]==1:
   result[:channel+1]=[-1]*(channel+1);break
 return result

def recover_materials(extract,exists,output,terrain,texture):
 loaded={}
 def load(path):
  value=extract(path);raw=bytes(value) if isinstance(value,(bytes,bytearray)) else Path(value).read_bytes()
  loaded[path]={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()};return raw
 for path,digest in SHADERS.items():
  if hashlib.sha256(load(path)).hexdigest()!=digest:raise ValueError('Terrain shader changed; retrace required')
 out=Path(output)/'maps';out.mkdir(parents=True,exist_ok=True);tiles=[]
 for source in terrain['sourceTextures']:
  x,z=source['tile'];stem=f'{x:04d}_{z:04d}';path=f'world/{terrain["world"]}/terrain/{stem}.trn'
  tile=tile_materials(load(path))
  if tile['tile']!=source['tile'] or tile['textures']!=source['textures']:raise ValueError('Material/geometry tile mismatch')
  names=[f'world/{terrain["world"]}/layers/{stem}_{i}.msk' for i in range(4)]
  channels=[load(p) if exists(p) else None for p in names];image,classes=mask_channels(channels)
  tile['mask']=None
  if image:
   filename=f'terrain-mask-{stem}.png';image.save(out/filename)
   tile['mask']={'url':'/assets/maps/'+filename,'width':image.width,'height':image.height,'channels':[p if c is not None else None for p,c in zip(names,channels)],'flipY':False}
  for c,values in zip(tile['chunks'],classes):c.update(maskClasses=values,effectiveIndices=effective_indices(c['indices'],values))
  tile['textures']=[{'sourcePath':p,'url':texture(p)} for p in tile['textures']]
  if any(t['url'] is None for t in tile['textures']):raise ValueError('Original terrain texture missing')
  tiles.append(tile)
 fallback=texture('texture/tiles/textures/default.tga')
 if not fallback:raise ValueError('Original terrain fallback missing')
 profile={'format':'oc2-terrain-materials-v1','world':terrain['world'],'tiles':tiles,'fallback':fallback,
  'coordinates':{'tileSize':64,'chunksPerSide':8,'chunkSize':8,'uv0UnitsPerRepeat':8,'uv1UnitsPerRepeat':64,'sourceVertexStride':44,'maskAddressMode':{'value':2,'name':'Clamp to Edge','nativeNameTable':'0x24995f0'}},
  'sources':loaded,'maskUpload':mask_upload_profile(),'nativeRoutines':{hex(a):{'bytes':n,'sha256':h} for a,(n,h) in ROUTINES.items()},
  'limits':['Source layer indices, UVs, raw masks, upper-five-bit mask pruning and sequential encoded-space mixing are recovered.',
   'Full-resolution non-phasing RGBA mask lanes are verified. This region still has only a green source file; baked/small-mask selection, active texture filtering/mipmap quality and native batching remain pending.',
   'This restores albedo inputs only. Existing browser Standard lighting and the color-space bridge remain web adaptations; native terrain lighting/lightmaps, water, holes and quality branches are not restored.']}
 (out/'terrain-materials.json').write_text(json.dumps(profile,ensure_ascii=False,indent=2));return profile
