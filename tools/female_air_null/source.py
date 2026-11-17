"""Own Female32 source-null boundary and common original Hero air consumer.

No missing track is added. A null loaded-track interface is supplied only after
the original constructor/lookup has returned null for this exact own bank.
"""
import copy,hashlib,inspect,json,sys,textwrap,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/creation_playback')]
AREA=ROOT/'analysis/raw/female-world-null-20261116'
BASE=ROOT/'analysis/raw/female-world-idle-family-20261116/candidate-v1'
def source_method(method,replacements,scope):
 text=textwrap.dedent(inspect.getsource(method))
 for a,b,count in replacements:
  if text.count(a)!=count:raise ValueError('Exact shared method anchor changed '+method.__name__)
  text=text.replace(a,b)
 space={**method.__globals__,**scope};exec(compile(text,__file__,'exec'),space)
 return space[method.__name__],hashlib.sha256(text.encode()).hexdigest()

def own_type():
 from character_human_queue_probe import HumanQueue
 from player_choice_human_male_air_worker import HumanMaleAir
 from player_choice_elf_female_input_contract_probe import SourceJumpInputMixin,SourceJumpInputContexts
 from native_phy_stream import NativePHYStreamMixin
 from source_layer_queue import SourceLayerQueue
 class FemaleBase(HumanQueue):pass
 format='oc2-female-original-air-null-queue-v1'
 methods={}
 FemaleBase.__init__,methods['init']=source_method(HumanQueue.__init__,[(".get('sourceModelId')!=1",".get('sourceModelId')!=32",1),('super().__init__','super(HumanQueue,self).__init__',1)],{'FORMAT':format})
 FemaleBase.bind_human,methods['bind']=source_method(HumanQueue.bind_human,[("'human-male'","'human-female'",2)],{})
 class FemaleAir(SourceJumpInputMixin,NativePHYStreamMixin,FemaleBase):
  def __init__(self,image,profile,reader,context,bank):
   self.bank=bank;self.reader=reader;self.missing_receipts=[];self.selector_trace=[];self.current_null=False
   if bank.query('jumplandrun')is not None:raise ValueError('Own source null lookup required')
   bank.uc.emu_start(0x32e4b4,0x32e4bc);self.null_duration=bank.get('W0')
   if self.null_duration!=0xffffffff:raise ValueError('Original duration null tail changed')
   self.maps={};self.storage_calls=[];self.jump_input_audit=False;self.jump_input_storage_active=False;self.jump_free_nodes=[];self.jump_as_input=None
   context=copy.deepcopy(context);flag=context.pop('source_filter_byte')
   if flag not in(0,1):raise ValueError('Explicit original filtering field required')
   FemaleBase.__init__(self,image,profile,**context)
   self.w(0x2544581,'B',flag);self.bindings=self.humans;self.phy_read_reports=[];self.inputs=SourceJumpInputContexts(self);self.input_pressed={};self.native_notifications=[];self.water_trace=[]
   from unicorn import UC_HOOK_CODE
   for at in(0x90e26c,0x90e3b8,0x90e50c,0x90e63c):self.uc.hook_add(UC_HOOK_CODE,self.observe,begin=at,end=at)
   for at in(0x32e4cc,0x32f160,0x32f168,0x32f3f8,0x32f5a4,0x32f5b0):self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=at,end=at)
  def original_missing(self,name):
   if name!='jumplandrun':return False
   if self.bank.query(name)is not None:raise ValueError('Exact own null source prefix changed')
   return True
  def hook(self,uc,pc,size,data):
   if pc==0xa3cf28 and getattr(self,'human_active',False)and self.native_state:
    self.native_notifications.append({'actor':self.r(self.get('X0')+8,'Q')[0],'manager':self.get('X0'),'state':self.get('W1'),'caller':hex(self.get('X30')-4)});return
   if getattr(self,'human_active',False)and pc==0x331cbc:
    name=self.cstr(self.get('X2')).decode()
    if self.original_missing(name):
     # The separate bank VM executed this exact original null-return tail.
     self.metadata_queries.append({'sourceClip':name,'nativeLookupNull':True,'durationMs':-1,'sourceEntry':'0x32e4b4..0x32e4bc','fullResourceLoaderExecuted':False})
     self.set('W0',self.null_duration);self.set('PC',self.get('X30'));return
    if name not in self.profile['ranges']:
     found=self.bank.query(name)
     if found is None:
      self.metadata_queries.append({'sourceClip':name,'nativeLookupNull':True,'durationMs':-1,'durationOnlyNotPlaybackAdmission':True,'sourceEntry':'0x32e4b4..0x32e4bc'});self.set('W0',self.null_duration);self.set('PC',self.get('X30'));return
     start,end=found['nativeClockMs'];self.metadata_queries.append({'sourceClip':name,'durationMs':int(end-start),'ownNativeRange':found,'durationOnlyNotPlaybackAdmission':True});self.set('W0',int(end-start));self.set('PC',self.get('X30'));return
   if self.layers_native and self.queue_selection:
    if pc==0x32f14c:
     name=bytes(uc.mem_read(self.get('SP')+0x60,64)).split(b'\0')[0].decode()
     if self.original_missing(name):
      self.current_null=True;channel=self.get('W20');engine=self.get('X19');self.null_before=bytes(uc.mem_read(engine+0x38+channel*0x58,0x58));self.selector_trace.append({'at':hex(pc),'channel':channel,'name':name,'currentRecordBefore':self.null_before.hex(),'channelFlagBefore':self.r(engine+0x10+channel*4,'B')[0]});return
    if self.current_null and pc==0x32e4cc:
     name=self.cstr(self.get('X2')).decode()
     if not self.original_missing(name):raise ValueError('Null route cannot supply another resource')
     self.w(self.get('X8'),'Q',0);self.missing_receipts.append({'name':name,'channel':self.get('W1'),'actualOriginalBankLookupNull':True,'boundary':'0x32e4cc output storage','fullResourceConstructorExecuted':False,'resourceSuccessSupplied':False});self.set('PC',self.get('X30'));return
    if self.current_null and pc in(0x32f160,0x32f168,0x32f3f8,0x32f5a4,0x32f5b0):
     row={'at':hex(pc),'channel':self.get('W20'),'nativeX26':self.get('X26')}
     if pc==0x32f5b0:
      after=bytes(uc.mem_read(self.get('X19')+0x38+self.get('W20')*0x58,0x58));row.update(currentRecordAfter=after.hex(),currentRecordPreserved=after==self.null_before,channelFlagAfter=self.r(self.get('X28'),'B')[0])
     self.selector_trace.append(row)
     if pc==0x32f5b0:self.current_null=False
     return
   return super().hook(uc,pc,size,data)
 FemaleAir.observe=HumanMaleAir.observe
 FemaleAir.scope,methods['scope']=source_method(HumanMaleAir.scope,[('super().scope(identity,fn)','HumanQueue.scope(self,identity,fn)',1)],{'HumanQueue':HumanQueue})
 for name in('fresh_actor','water_state','press_event','active_timer','physics_frame','tick_own','disconnect'):
  method=getattr(HumanMaleAir,name);text=textwrap.dedent(inspect.getsource(method));count=text.count("'human-male'");changes=[]
  if count:changes.append(("'human-male'","'human-female'",count))
  if name=='fresh_actor':changes.append(("'sourceModelId':1","'sourceModelId':32",1))
  function,digest=source_method(method,changes,{'FIELD':'sourceFemalePose'});setattr(FemaleAir,name,function);methods[name]=digest
 FemaleAir.enqueue_requests,methods['enqueue_requests']=source_method(HumanQueue.enqueue_requests,[("if request['name']not in self.profile['ranges']:raise ValueError('Unadmitted own human track')","if request['name']not in self.profile['ranges']and not self.original_missing(request['name']):raise ValueError('Unadmitted own Female32 track')",1)],{})
 FemaleAir.select_queue,methods['select_queue']=source_method(SourceLayerQueue.select_queue,[("if name not in self.stop_profile['ranges']:raise ValueError('Original layer track absent')","if self.original_missing(name):continue\n            if name not in self.stop_profile['ranges']:raise ValueError('Original layer track absent')",1)],{})
 return FemaleAir,format,methods

def load(config=None,qa_evidence=False):
 started=time.perf_counter()
 from analyze_native_resources import NativeImage
 from bdae_animation import BDAEAnimation
 from index_body_banks import bank_probe_type
 from character_human_queue_probe import profile_hash
 from player_choice_female_worker import load_female_pose
 cfg=json.loads(Path(config or BASE/'native-physics.json').read_text());image=NativeImage(Path(cfg['library']).read_bytes());reader=BDAEAnimation(cfg['sourceFemaleComposition']['animation']['path']);bank=bank_probe_type()(image);bank.build(reader)
 if config is not None:
  from species_world_profiles import profile_digest
  from player_choice_female_pose import binding_id
  original=json.loads((BASE/'native-physics.json').read_text());expected=copy.deepcopy(original);meta=cfg.get('sourceOwnNullBoundary',{})
  if set(meta)!={'sourceFormat','missingPlaybackName','onlyAddedOwnRequest','oldIdleCandidateSHA256'}or meta.get('sourceFormat')!='oc2-female-original-air-null-v1'or meta.get('oldIdleCandidateSHA256')!=hashlib.sha256((BASE/'native-physics.json').read_bytes()).hexdigest()or meta.get('missingPlaybackName')!='jumplandrun'or meta.get('onlyAddedOwnRequest',{}).get('name')!='jump_start_01':raise ValueError('Exact frozen own idle baseline and observed variant required')
  expected['sourceSpeciesProfiles']=cfg['sourceSpeciesProfiles'];expected['sourceFemaleComposition']['binding']=cfg['sourceFemaleComposition']['binding'];expected['config']=cfg['config'];expected['worker']=cfg['worker'];expected['sourceOwnNullBoundary']=meta
  if cfg!=expected:raise ValueError('Unexplained changes outside own variant/null boundary')
  own=json.loads(Path(original['sourceSpeciesProfiles']['path']).read_text());r,=[r for r in reader.ranges()if r['name']=='jump_start_01'];own['human-female']['ranges']['jump_start_01']=r;own['human-female']['sha256']=profile_digest(own['human-female'])
  if own!=json.loads(Path(cfg['sourceSpeciesProfiles']['path']).read_text()):raise ValueError('Only the actual own jump-start variant may be appended')
  b=json.loads(Path(original['sourceFemaleComposition']['binding']['path']).read_text());b['sourceMotion']={k:own['human-female'][k]for k in('format','sha256','key','race','gender','sourceModelId')};b['bindingId']=binding_id(b)
  if b!=json.loads(Path(cfg['sourceFemaleComposition']['binding']['path']).read_text()):raise ValueError('Own131 rig/property/mask must remain unchanged')
 species=json.loads(Path(cfg['sourceSpeciesProfiles']['path']).read_text())['human-female'];p=copy.deepcopy(json.loads((ROOT/'analysis/raw/character-human-queue-20261115/profile-v2-private.json').read_text()));kind,format,methods=own_type();p.update(format=format,species=species);p['stop']['ranges']=species['ranges'];p['layer']['sourceClipNames']=species['sourceClipNames'];p['layer']['engineFlags']=species['engineFlags'];p['sha256']=profile_hash(p)
 context=json.loads((ROOT/'analysis/raw/player-choice-human-male-air-20261116/candidate-v4/native-physics.world.json').read_text())['sourceRuntimeInputs']
 e=kind(image,p,reader,context,bank)
 terrain=json.loads(Path(cfg['terrain']).read_text());collision=json.loads(Path(cfg['collision']).read_text());lights=json.loads(Path(cfg['terrainLighting']).read_text())
 def source_file(n):
  r=cfg['sourceFiles'][n];b=Path(r['path']).read_bytes()
  if hashlib.sha256(b).hexdigest()!=r['sha256']:raise ValueError('Pinned original PHY differs')
  return b
 for r in[cfg['sourceSpeciesProfiles'],*cfg['sourceFemaleComposition'].values()]:
  if hashlib.sha256(Path(r['path']).read_bytes()).hexdigest()!=r['sha256']:raise ValueError('Own source metadata digest differs')
 summary=e.load_world(terrain,collision,source_file,{tuple(r['tile']):r['runtimeFlags']for r in lights['tiles']});summary.update(e.load_water(json.loads(Path(cfg['swimming']).read_text())));summary.update(e.load_diving(json.loads(Path(cfg['diving']).read_text())))
 summary.update(load_female_pose(e,cfg,ROOT));e.human_pose=e.female_pose;e.qa_original_pose_evidence=qa_evidence;e.preparation_milliseconds=(time.perf_counter()-started)*1000
 summary.update(bounds=terrain['bounds'],frame=collision['coordinateFrame'],sourceNative=True,nativeSHA256=cfg['nativeSHA256'],sourceSpeciesKeys=['human-female'],entryMode='web-owned-event',wholeHeroOrGPUExecuted=False)
 return e,cfg,summary,methods
