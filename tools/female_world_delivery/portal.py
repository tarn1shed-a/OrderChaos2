"""Relocate immutable Female32 inputs; do not alter source queue/math/identity."""
import copy,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
RUNTIME=ROOT/'analysis/raw/portable/running-preview'
CONFIG='native-inputs/player-human-female-actions-v1/native-physics.json'
FROZEN_CONFIG_SHA='723e0d6c98fa016cff0c239da4878a60bc74dfcfd695cafcbf97997c2802b9c6'
QUEUE_SHA='b62bcd1c1c46ac196b481a5cfd6b8fbaee27041eaa04afb155796200b6219397'
CONTEXT_SHA='317cba770f748c92800be2d1cb2a39209e7a32f4debc7a7f789c27545a9db489'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def inside(value):
 p=(RUNTIME/value).resolve()
 if not isinstance(value,str)or value.startswith('/')or'..'in Path(value).parts or not p.is_relative_to(RUNTIME):raise ValueError('Fixed private relative resource path required')
 return p
def projected(recipe,plan,python):
 paths={r['original']:str(inside(r['target']))for r in plan['resources']}
 def remap(v):
  if isinstance(v,str):return paths.get(v,v)
  if isinstance(v,list):return[remap(x)for x in v]
  if isinstance(v,dict):return{k:remap(x)for k,x in v.items()}
  return v
 out=remap(recipe);out.update(config=str(inside(CONFIG)),python=python,worker=str(ROOT/'tools/female_world_delivery/worker.py'))
 out['sourceFemalePortable']={'format':'oc2-female-actions-portable-v1','projection':plan['projectionTarget'],'baselineQueue':paths[plan['baselineQueueOriginal']],'runtimeContext':copy.deepcopy(plan['runtimeContext'])}
 return out
def validate(cfg):
 from source_immutable_inputs import source_pages_enabled
 source_pages=source_pages_enabled()
 from bdae_animation import BDAEAnimation
 meta=cfg.get('sourceFemalePortable')
 if not isinstance(meta,dict)or meta.get('format')!='oc2-female-actions-portable-v1':raise ValueError('Explicit own portable recipe required')
 plan=json.loads(inside(meta['projection']).read_text());recipe_path=inside(plan['recipeTarget'])
 if plan.get('format')!='oc2-female-actions-path-projection-v1'or sha(recipe_path)!=FROZEN_CONFIG_SHA:raise ValueError('Frozen Female15 recipe differs')
 recipe=json.loads(recipe_path.read_text());expected=projected(recipe,plan,cfg['python'])
 if cfg!=expected:raise ValueError('Runtime differs beyond explicit source path projection')
 if sha(meta['baselineQueue'])!=QUEUE_SHA or hashlib.sha256(json.dumps(meta['runtimeContext'],sort_keys=True,separators=(',',':')).encode()).hexdigest()!=CONTEXT_SHA:raise ValueError('Frozen original queue or explicit constructor context changed')
 seen=set()
 for r in plan['resources']:
  if source_pages:
   from source_immutable_inputs import verify_source
   if r['original']in seen:raise ValueError('Original bytes or source path mapping differs')
   verify_source(ROOT,{'path':str(inside(r['target'])),'sha256':r['sha256']})
  elif r['original']in seen or sha(inside(r['target']))!=r['sha256']:raise ValueError('Original bytes or source path mapping differs')
  seen.add(r['original'])
 species=json.loads(Path(cfg['sourceSpeciesProfiles']['path']).read_text())['human-female']
 if species['sha256']!='c5c940718e49f560ed7160209687b1417d6231cf5ec479a723bc89c1b42763d1':raise ValueError('Own15 motion identity changed')
 if source_pages:
  from source_immutable_inputs import open_source
  path,raw=open_source(ROOT,cfg['sourceFemaleComposition']['animation'])
  return species,BDAEAnimation(path,source_buffer=raw)
 return species,BDAEAnimation(cfg['sourceFemaleComposition']['animation']['path'])
def load(path,qa_evidence=False):
 from female_world_actions import source
 # Only two fixed file-provider reads change; original code and values do not.
 fn,digest=source.source_method(source.load,[
  ("(ROOT/'analysis/raw/character-human-queue-20261115/profile-v2-private.json').read_text()","Path(cfg['sourceFemalePortable']['baselineQueue']).read_text()",1),
  ("json.loads((ROOT/'analysis/raw/player-choice-human-male-air-20261116/candidate-v4/native-physics.world.json').read_text())['sourceRuntimeInputs']","copy.deepcopy(cfg['sourceFemalePortable']['runtimeContext'])",1),
 ],{'validate':validate})
 e,cfg,info,methods=fn(path,qa_evidence=qa_evidence)
 methods['explicitPortableProviderLoad']=digest
 return e,cfg,info,methods
