"""Versioned entry only; frozen v7 body/config/read lifecycle stay read-only."""
from pathlib import Path
import sys,hashlib,importlib.util
HERE=Path(__file__).resolve().parent
SOURCE_SHA='aeae2dfd87bcd70777f0a65e21967009813e4582e394f939ab07862e66c17965'

def reclaim_hf_idle(e,gather):
 # Called only after the unchanged release/disconnect and read invalidation.
 # Do not discard or recreate the original three Uc instances or their state.
 if any((e.humans,e.actors,e.species_actors,e.inputs.contexts,e.input_pressed,gather.entries,gather.reader.bindings)):return False
 if e.human_active:raise ValueError('HumanF idle pages require the native operation to finish')
 from source_guest_pages import reclaim_guest_pages
 for uc in (e.uc,e.human_pose[0].uc,e.bank.uc):reclaim_guest_pages(uc)
 return True

def start(config):
 previous=HERE/'worker_posture_v1.py'
 if hashlib.sha256(previous.read_bytes()).hexdigest()!=SOURCE_SHA:raise ValueError('Exact frozen same-engine posture worker required')
 spec=importlib.util.spec_from_file_location('_frozen_hf_posture_worker',previous);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
 cfg=__import__('json').loads(Path(config).read_text());root=Path(cfg['worker']).resolve().parents[2]
 sys.path[:0]=[str(HERE),str(root/'tools')]
 from female_air_null.source import source_method
 from runtime_v1 import RUNTIMES
 additions=[
  ("q=json.loads(line);op=q['operation'];d=q.get('data',{})","q=runtime_for(e).unwrap(json.loads(line));op=q['operation'];d=q.get('data',{})",1),
  ("if op=='init':r=info","if op=='initialize-native-runtime':r=runtime_for(e).initialize(d)\n            elif op=='native-runtime-audit':r=runtime_for(e).audit(d)\n            elif op=='init':r=info",1)]
 changed=[('from female_world_delivery.worker import own_load','from runtime_v1 import own_load,runtime_for',1),
  (' fn,digest=source_method(original.start,replacements,', ' replacements.extend('+repr(additions)+')\n fn,digest=source_method(original.start,replacements,',1),
  ("gather.invalidate(d['identity']);r=e.disconnect(d['identity'])","gather.invalidate(d['identity']);r=e.disconnect(d['identity']);reclaim_hf_idle(e,gather)",1),
  ("'attach':attach}","'attach':attach,'runtime_for':runtime_for,'reclaim_hf_idle':reclaim_hf_idle}",1)]
 fn,digest=source_method(old.start,changed,{'reclaim_hf_idle':reclaim_hf_idle})
 try:return fn(config)
 finally:
  for runtime in RUNTIMES.values():runtime.dispose()
  RUNTIMES.clear()
if __name__=='__main__':start(sys.argv[1])
