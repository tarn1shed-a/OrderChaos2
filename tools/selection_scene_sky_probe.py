"""Original map7/region211 sky request and fresh-mode1 channel evidence.

The requested sky models are absent from the supplied archives. This exports
evidence, never a substituted dome/hill or a fabricated resource/GPU success.
"""
import argparse,hashlib,json,struct,zipfile
from pathlib import Path
from selection_scene_candidate import ROOT,local_output,CONFIGS
from selection_scene_environment_upstream_probe import UpstreamProbe
from tutorial_sky_candidate import CHANNELS,target_writes,source_sky_request,FIELDS
from scene_sky import sky_distance_uniform,verify_native as verify_sky
from scene_sky_frame import verify_native as verify_frame
from native_sky_frame_probe import NativeSkyFrameProbe
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from map_selection_evidence import DEFAULT_APK
from scene_lighting import ZONE_SHA256
from skill_attachments import decode_ftable

FORMAT='oc2-selection-region211-sky-evidence-v1'
EXPECTED={
 'main':'model/scene_whitepike_003/sky/whitepike_sky005.bdae',
 'hill':'model/scene_whitepike_003/sky/whitepike_skyhill005.bdae',
}

class SelectionSkyProbe(UpstreamProbe):
 def __init__(self,image):
  verify_sky(image);verify_frame(image);super().__init__(image)
  self.sky_request_active=False;self.requests=[]
  from unicorn import UC_HOOK_CODE
  for a in(0xa64d0c,0xa66de4):self.uc.hook_add(UC_HOOK_CODE,self.sky_boundary,begin=a,end=a)

 def sky_boundary(self,uc,a,n,d):
  if not self.sky_request_active:return
  self.requests.append({'consumer':hex(a),'kind':'main'if a==0xa64d0c else'hill',
   'rawPath':self.cstr(self.get('X1')).decode(),'modelCreationExecuted':False})
  # Request recording boundary only; the caller ignores return values. Do not
  # supply a fake resource pointer or a successful model-load return code.
  self.set('PC',self.get('X30'))

 def hook(self,uc,a,n,d):
  if self.imports.get(a)=='memcmp':
   n=self.get('X2');x=bytes(uc.mem_read(self.get('X0'),n));y=bytes(uc.mem_read(self.get('X1'),n))
   self.set('W0',int(x>y)-int(x<y));self.set('PC',self.get('X30'));return
  return super().hook(uc,a,n,d)

 def inspect(self,table,row):
  dispatch=self.startup_dispatch(1);catalog=self.catalog_and_queues(table,prior_target=False)
  start,end=self.r(self.manager+0x58,'2Q');region,=[self.r(p,'Q')[0]for p in range(start,end,8)if self.r(self.r(p,'Q')[0],'I')[0]==211]
  sky=self.alloc(0x80);self.requests=[];self.sky_request_active=True
  # Start at the source path-selection block with the actual catalog row.
  for i in range(31):self.set('X'+str(i),0)
  self.set('SP',self.STACK);self.set('X19',self.manager);self.set('X27',region);self.set('X21',sky)
  try:self.uc.emu_start(0x4c6438,0x4c6510,count=2000)
  finally:self.sky_request_active=False
  if self.get('PC')!=0x4c6510:raise ValueError('Original211 sky request block did not finish')
  requests=list(self.requests)
  before={k:list(self.r(self.env+offset,str(dim)+'f'))for k,(offset,dim)in CHANNELS.items()}
  # W20 at the setters is duration, not world mode. Execute the real producer
  # from the actual original dispatch state before entering the sky block.
  self.set('X23',self.outer);self.set('X25',self.STACK+0x108)
  self.uc.emu_start(0x4c6510,0x4c6544,count=40)
  duration,transition=self.get('W20'),self.get('W22')
  if duration!=0 or transition!=0:raise ValueError('Original selection mode1 duration is not immediate')
  for i in range(31):self.set('X'+str(i),0)
  for i in range(32):self.set('Q'+str(i),0)
  self.set('SP',self.STACK)
  for key,value in dict(X19=self.manager,X27=region,X25=self.STACK+0x108,W20=duration,W22=transition).items():self.set(key,value)
  self.sf('S8',1/255);self.uc.emu_start(0x4c6e04,0x4c730c,count=5000)
  if self.get('PC')!=0x4c730c:raise ValueError('Original211 immediate sky targets did not finish')
  result={k:list(self.r(self.env+offset,str(dim)+'f'))for k,(offset,dim)in CHANNELS.items()}
  if result!=target_writes(row,None):raise ValueError('Original211 sky targets differ: '+json.dumps({'actual':result,'source':target_writes(row,None)}))
  return {'dispatch':dispatch,'catalog':catalog,'originalRequestBlockExecuted':True,
   'requests':requests,'originalSkyTargetBlockExecuted':True,'worldMode':dispatch['worldModeAtFactoryBoundary'],
   'originalDurationProducerExecuted':True,'durationMs':duration,
   'initial':before,'current':result,'distanceUniform':sky_distance_uniform(*result['distance']),
   'freshStartOnly':True,'modelRequestBoundaryOnly':True,'GPUCreated':False}

def analyze(image):
 source=Sources(DEFAULT_SOURCE);raw=source.read('tables/zones.tbl')
 if hashlib.sha256(raw).hexdigest()!=ZONE_SHA256:raise ValueError('Original zone table differs')
 table=decode_ftable(raw,'ID');row,=[r for r in table['rows']if r['ID']==211]
 if row['map_id']!=7 or row['parent_ID']!=-1 or any(r['parent_ID']==211 for r in table['rows']):raise ValueError('Original211 selection hierarchy changed')
 offset=0;offsets={}
 for key,kind in zip(table['columns'],table['physicalTypes']):offsets[key]=(offset,'I'if kind=='u'else kind);offset+=8 if kind=='s'else 4
 if any(offsets[k]!=v for k,v in FIELDS.items()):raise ValueError('Original211 sky fields moved')
 expected={k:source_sky_request(row,None,hill=k=='hill')for k in EXPECTED}
 if expected!=EXPECTED:raise ValueError('Original211 sky references changed')
 native=SelectionSkyProbe(image).inspect(table,row)
 requests={r['kind']:r['rawPath'].replace('\\','/').lower()for r in native['requests']}
 if requests!=EXPECTED:raise ValueError('Original sky selection requested unexpected names')
 resources={};missing=[]
 with zipfile.ZipFile(DEFAULT_APK)as apk:
  apk_names=apk.namelist();options=json.loads(apk.read('assets/GameOptions.json'))
 from native_device_selection_probe import NativeDeviceSelectionProbe
 show_hill=dict(NativeDeviceSelectionProbe(image).updates(options['profiles']['GPU'],''))['ShowHillInSky']
 for key,path in EXPECTED.items():
  base=Path(path).name;exact=source.candidates(path)
  basename=[r for rs in source.lookup.values()for r in rs if Path(r['path'].replace('\\','/')).name.lower()==base]
  bundled=[n for n in apk_names if n.replace('\\','/').lower().endswith('/'+base)or n.lower()==base]
  resources[key]={'path':path,'archiveExactCandidates':exact,'archiveBasenameCandidates':basename,'apkCandidates':bundled}
  if not exact:missing.append(path)
 textures={}
 for path in('texture/whitepike_sky005.tga','texture/whitepike_sky005b.tga'):
  b=source.read(path);textures[path]={'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b),'sourceProof':source.proofs[path],
    'boundToRequestedModels':False,'reason':'Requested model material/sampler cannot be read while original models are absent'}
 from selection_scene_candidate import splash_configs
 configs=splash_configs(source);camera=configs[0]['cameraPosition']
 frame=NativeSkyFrameProbe(image).follow(camera,main=[0,0,0],hill=[1,2,3])
 return {'format':FORMAT,'mapId':7,'sourceRegion':211,'zoneSHA256':ZONE_SHA256,
  'zoneFields':{k:row[k]for k in['ID','parent_ID','map_id','skybox','skybox_hill',*FIELDS]},'native':native,
  'defaultShowHillInSky':show_hill,'resources':resources,'missingOriginalModels':missing,'nearbyTexturesOnly':textures,
  'conditionalCameraFollow':{'camera':camera,'originalWrapperConsumerExecuted':True,'receivers':'explicit loaded-node CPU controls only',
   'result':frame,'proofThatMissingModelsLoaded':False},
  'originalResourceIndexEntries':sum(len(rs)for rs in source.lookup.values()),
  'skyModelEntries':[{'pack':r['pack'],'path':r['path']}for rs in source.lookup.values()for r in rs if'sky'in r['path'].lower()and r['path'].lower().endswith('.bdae')],
  'sourceProofs':source.proofs,'runtimeReady':False,'previewChanged':False,'savesChanged':False,
  'limits':['Two requested original models are absent in all supplied.bin archives and the APK. No alias/model substitution is authorized or inferred from similar texture names.',
   'The source zone request block and sky target writers execute in the original normal selection mode1; model creation is an explicit recording boundary.',
   'Camera-follow CPU controls prove the original consumer if nodes are loaded, not that these missing resources exist or were rendered.',
   'No original model material/sampler/node bounds exist here to derive scale or select sky techniques. Existing tutorial models/parameters are not reused.',
   'Fresh-start sky targets do not reproduce played-world reentry/history, compiled reflection, draw queues or original GPU success.'],
  'requiredExternalMaterial':'Original client/update resource archive containing both exact requested BDAE files; their material references then determine any additional texture/effect dependencies.'}

if __name__=='__main__':
 from analyze_native_resources import NativeImage
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 out=local_output(a.output)
 if out.exists():raise ValueError('Use fresh sky evidence output')
 result=analyze(NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes()));out.parent.mkdir(parents=True,exist_ok=True)
 out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'missing':result['missingOriginalModels'],'mode':result['native']['worldMode'],'targets':result['native']['current'],'runtimeReady':False}))
