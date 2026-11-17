"""Existing v7 serial worker plus one read-only op; config/body15 unmodified.

The trusted, byte-validated config still names its frozen original worker. That
path selects the already-installed source root; the process entry alone points
at this append. The old portal continues checking its complete resource pins.
"""
import sys,json,hashlib,inspect,textwrap
from pathlib import Path

ORIGINAL_WORKER_SHA='70a5e9560876a4fa742367c2089e4954548b500b96827706be487aed58eef101'
ORIGINAL_START_FILE_SHA='eae108b4eb89e1e972bba6d6214cc67885d782bc9951dec8eeaba44d8f7c7f89'
ACTIVE=[]
def start(config):
 cfg=json.loads(Path(config).read_text());old=Path(cfg['worker']).resolve()
 if hashlib.sha256(old.read_bytes()).hexdigest()!=ORIGINAL_WORKER_SHA:raise ValueError('Exact existing v7 worker bootstrap required')
 root=old.parents[2];base=root/'tools/player_choice_human_male_air_worker.py'
 if hashlib.sha256(base.read_bytes()).hexdigest()!=ORIGINAL_START_FILE_SHA:raise ValueError('Exact shared original serial start required')
 sys.path[:0]=[str(Path(__file__).resolve().parent),str(root/'tools')]
 from female_world_delivery.worker import own_load
 from female_air_null.source import source_method
 import player_choice_human_male_air_worker as original
 from lifetime_posture_v1 import GatherReadLifetimes
 def attach(e):
  life=GatherReadLifetimes(e);ACTIVE.append(life);return life
 replacements=[("'human-male'","'human-female'",3),("valueBytes':1992","valueBytes':1928",1),
  ('e,info=load(config)','e,info=load(config)\n    gather=attach(e)',1),
  ("r=e.fresh_actor(d['identity'],d['position'],d['profession'],d['equipment'])","r=e.fresh_actor(d['identity'],d['position'],d['profession'],d['equipment'])\n                gather.bound_after_reset(d['identity'])",1),
  ("elif op=='forget':r=e.disconnect(d['identity'])","elif op=='forget':\n                gather.invalidate(d['identity']);r=e.disconnect(d['identity'])",1),
  ("elif op=='input-state':r=e.inputs.inspect(d['identity'])","elif op=='gather-presentation-context':r=gather.read(d)\n            elif op=='input-state':r=e.inputs.inspect(d['identity'])",1)]
 fn,digest=source_method(original.start,replacements,{'load':own_load,'FIELD':'sourceFemalePose','attach':attach})
 try:return fn(config)
 finally:
  for life in ACTIVE:life.dispose()
  ACTIVE.clear()
if __name__=='__main__':start(sys.argv[1])
