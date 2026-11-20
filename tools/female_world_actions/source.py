"""Data-only own Female32 range expansion; frozen Hero/null consumer reused."""
import copy,hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/creation_playback')]
from female_air_null.source import own_type,source_method
AREA=ROOT/'analysis/raw/female-world-actions-20261116'
BASE=ROOT/'analysis/raw/female-world-null-20261116/candidate-v1/native-physics.json'
BASE_SHA='e0715fc5dfb69d26050d8fa85e4efbc452191a6ce0c15048f2bfdf713afb6b7e'
NAMES=('shuffle_right','combat_unarmed_ready')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def validate(cfg):
 from bdae_animation import BDAEAnimation
 from species_world_profiles import profile_digest
 from player_choice_female_pose import binding_id
 if sha(BASE)!=BASE_SHA:raise ValueError('Frozen own13 baseline changed')
 original=json.loads(BASE.read_text());expected=copy.deepcopy(original)
 meta=cfg.get('sourceFemaleActionsAppend')
 if not isinstance(meta,dict)or set(meta)!={'baselineSHA256','names'}or meta['baselineSHA256']!=sha(BASE)or tuple(meta['names'])!=NAMES:raise ValueError('Exact scoped Female32 action expansion required')
 for k in('sourceSpeciesProfiles','config','worker','sourceFemaleActionsAppend'):expected[k]=cfg[k]
 expected['sourceFemaleComposition']['binding']=cfg['sourceFemaleComposition']['binding']
 if cfg!=expected:raise ValueError('Unexplained change outside own action metadata')
 reader=BDAEAnimation(original['sourceFemaleComposition']['animation']['path'])
 collection=json.loads(Path(original['sourceSpeciesProfiles']['path']).read_text());sp=collection['human-female']
 for n in NAMES:
  row,=[r for r in reader.ranges()if r['name']==n]
  if n in sp['ranges']:raise ValueError('Only previously unadmitted own requests may be appended')
  sp['ranges'][n]=row
 sp['sha256']=profile_digest(sp)
 if collection!=json.loads(Path(cfg['sourceSpeciesProfiles']['path']).read_text()):raise ValueError('Source names/ranges differ beyond proven own requests')
 b=json.loads(Path(original['sourceFemaleComposition']['binding']['path']).read_text());b['sourceMotion']={k:sp[k]for k in('format','sha256','key','race','gender','sourceModelId')};b['bindingId']=binding_id(b)
 if b!=json.loads(Path(cfg['sourceFemaleComposition']['binding']['path']).read_text()):raise ValueError('Own rig/order/mask changed')
 for r in[cfg['sourceSpeciesProfiles'],*cfg['sourceFemaleComposition'].values()]:
  if sha(r['path'])!=r['sha256']:raise ValueError('Pinned own input differs')
 return sp,reader

def load(config,qa_evidence=False):
 from analyze_native_resources import NativeImage,NATIVE_SHA256
 from index_body_banks import bank_probe_type
 from character_human_queue_probe import profile_hash
 from player_choice_female_worker import load_female_pose
 path=Path(config).resolve()
 if not path.is_relative_to(ROOT/'analysis/raw'):raise ValueError('Private ignored own configuration required')
 started=time.perf_counter();cfg=json.loads(path.read_text());species,reader=validate(cfg)
 image=NativeImage.from_file(ROOT,{'path':cfg['library'],'sha256':NATIVE_SHA256});bank=bank_probe_type()(image);bank.build(reader)
 p=copy.deepcopy(json.loads((ROOT/'analysis/raw/character-human-queue-20261115/profile-v2-private.json').read_text()))
 kind,format,methods=own_type();p.update(format=format,species=species);p['stop']['ranges']=species['ranges'];p['layer']['sourceClipNames']=species['sourceClipNames'];p['layer']['engineFlags']=species['engineFlags'];p['sha256']=profile_hash(p)
 context=json.loads((ROOT/'analysis/raw/player-choice-human-male-air-20261116/candidate-v4/native-physics.world.json').read_text())['sourceRuntimeInputs']
 e=kind(image,p,reader,context,bank)
 terrain,collision,lights=(json.loads(Path(cfg[k]).read_text())for k in('terrain','collision','terrainLighting'))
 def source_file(n):
  r=cfg['sourceFiles'][n]
  if sha(r['path'])!=r['sha256']:raise ValueError('Pinned original PHY differs')
  return Path(r['path']).read_bytes()
 summary=e.load_world(terrain,collision,source_file,{tuple(r['tile']):r['runtimeFlags']for r in lights['tiles']})
 summary.update(e.load_water(json.loads(Path(cfg['swimming']).read_text())));summary.update(e.load_diving(json.loads(Path(cfg['diving']).read_text())))
 summary.update(load_female_pose(e,cfg,ROOT));e.human_pose=e.female_pose;e.qa_original_pose_evidence=qa_evidence;e.preparation_milliseconds=(time.perf_counter()-started)*1000
 summary.update(bounds=terrain['bounds'],frame=collision['coordinateFrame'],sourceNative=True,nativeSHA256=cfg['nativeSHA256'],sourceSpeciesKeys=['human-female'],entryMode='web-owned-event',wholeHeroOrGPUExecuted=False)
 return e,cfg,summary,methods
