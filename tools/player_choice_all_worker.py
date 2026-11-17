"""Compose only the nine already reviewed own-body ground worker interfaces."""
import sys

KEYS={'human-male','human-female','elf-male','elf-female','orc-male','orc-female','mendel-male','mendel-female','kartan'}

def load_all_poses(engine,cfg,root):
    import json
    from source_human_pose_worker import read_input
    from character_human_queue_fast_transport import FastPoseTransport
    from player_choice_body_pose import FIELDS
    if set(engine.species_profiles)!=KEYS:raise ValueError('Exact reviewed nine-body species set required')
    own=set(cfg.get('sourceBodyCompositions',{}))
    if own!=KEYS-{'human-male','human-female','elf-male','orc-male'}:raise ValueError('Exact remaining five original bodies required')
    fields={'human-male':'sourceHumanPose','human-female':'sourceFemalePose','elf-male':'sourceElfMalePose','orc-male':'sourceOrcMalePose',**FIELDS}
    descriptors={key:cfg[name]for key,name in [('human-male','sourceHumanComposition'),('human-female','sourceFemaleComposition'),('elf-male','sourceElfMaleComposition'),('orc-male','sourceOrcMaleComposition')]}
    descriptors.update(cfg['sourceBodyCompositions']);result={}
    for key,descriptor in descriptors.items():
        _,raw=read_input(root,descriptor['binding']);binding=json.loads(raw)
        if key=='human-male':transport=FastPoseTransport(binding);binding_id=transport.binding_id;size=1992
        else:binding_id=binding['bindingId'];size=binding['valueBytes']
        if binding['sourceMotion']!={k:engine.species_profiles[key][k]for k in ('format','sha256','key','race','gender','sourceModelId')}:raise ValueError('Declared own binding/model differs')
        result[fields[key]]={'key':key,'bindingId':binding_id,'valueBytes':size,'originalCompositionCPU':False,
          'originalGPUExecuted':False,'declaredBindingOnly':True,'loadBeforeActualOwnActorTick':True}
    engine.body_poses={};engine.choice_pose_loaded=set();engine.choice_pose_receipts={};engine.choice_pose_config=cfg;engine.choice_pose_root=root
    return result

def ensure_own_pose(engine,key,reason='actualActorTick'):
    import resource
    import time
    if key is None:return
    if key in engine.choice_pose_loaded:return{**engine.choice_pose_receipts[key],'alreadyPrepared':True}
    if key not in KEYS:raise ValueError('Unconfigured actual own body')
    started=time.perf_counter()
    from source_human_pose_worker import load_human_pose
    from player_choice_female_worker import load_female_pose
    from player_choice_elf_worker import load_elf_pose
    from player_choice_orc_worker import load_orc_pose
    from player_choice_body_worker import load_body_poses
    cfg,root=engine.choice_pose_config,engine.choice_pose_root
    loader={'human-male':load_human_pose,'human-female':load_female_pose,'elf-male':load_elf_pose,'orc-male':load_orc_pose}.get(key)
    if loader:metadata=loader(engine,cfg,root)
    else:
        # Narrow only the frozen loader's synchronous setup view. Its exact
        # private inputs and own masks are still validated without edits.
        profiles,previous=engine.species_profiles,engine.body_poses
        try:
            engine.species_profiles={key:profiles[key]}
            metadata=load_body_poses(engine,{**cfg,'sourceBodyCompositions':{key:cfg['sourceBodyCompositions'][key]}},root)
            loaded=engine.body_poses
        except BaseException:engine.body_poses=previous;raise
        finally:engine.species_profiles=profiles
        engine.body_poses={**previous,**loaded}
    engine.choice_pose_loaded.add(key)
    field,pose=next(iter(metadata.items()))
    receipt={'key':key,'ready':True,'poseField':field,'pose':pose,'milliseconds':(time.perf_counter()-started)*1000,
      'preparedBy':reason,'alreadyPrepared':False,'queueActorsCreatedOrAdvanced':False,
      'workerPeakResidentBytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin'else 1024)}
    engine.choice_pose_receipts[key]=receipt;return receipt

def resident_bytes():
    import os
    if sys.platform.startswith('linux'):
        from pathlib import Path
        return int(Path('/proc/self/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
    if sys.platform=='darwin':
        import subprocess
        value=subprocess.check_output(['/bin/ps','-o','rss=','-p',str(os.getpid())],text=True).strip()
        if not value.isdigit():raise ValueError('Current worker RSS unavailable')
        return int(value)*1024
    raise ValueError('Current resident-byte measurement unsupported')

def prepare_own_body(engine,data):
    if not isinstance(data,dict)or set(data)!={'species'}or data['species']not in KEYS:raise ValueError('Explicit configured body preparation required')
    receipt=ensure_own_pose(engine,data['species'],'explicitPrepareRPC');pose=receipt['pose']
    return{'key':receipt['key'],'ready':True,'pose':{'field':receipt['poseField'],'bindingId':pose['bindingId'],'valueBytes':pose['valueBytes']},
      'milliseconds':receipt['milliseconds'],'rssBytes':resident_bytes()}

def start(config):
    import source_physics_worker
    from source_species_queue import SourceSpeciesQueue
    from source_species_worker import staged_worker_source,load_species_profiles,bind_source_reset,forget_source_actor
    from source_human_pose_worker import human_pose_queue_type
    from player_choice_female_worker import female_queue_type
    from player_choice_elf_worker import elf_queue_type
    from player_choice_orc_worker import orc_queue_type
    from player_choice_body_worker import body_queue_type
    source=staged_worker_source()
    before="engine_type=SourceSpeciesQueue if cfg.get('sourceSpeciesProfiles') else SourceLayerQueue"
    if source.count(before)!=1:raise ValueError('Reviewed optional worker construction differs')
    source=source.replace(before,'engine_type=SourceAllPlayerChoiceQueue')
    before='    summary.update(load_species_profiles(engine,cfg,root))'
    if source.count(before)!=1:raise ValueError('Reviewed model-profile load differs')
    source=source.replace(before,before+'\n    summary.update(load_all_poses(engine,cfg,root))')
    before="            elif op=='ground':result=engine.ground(*data['point'])"
    if source.count(before)!=1:raise ValueError('Reviewed explicit worker RPC entry differs')
    source=source.replace(before,"            elif op=='prepareOwnBody':result=prepare_own_body(engine,data)\n"+before)
    base=body_queue_type(orc_queue_type(elf_queue_type(female_queue_type(human_pose_queue_type(SourceSpeciesQueue)))))
    class SourceAllPlayerChoiceQueue(base):
        def actor_tick(self,identity,*args,**kwargs):
            ensure_own_pose(self,self.species_actors.get(identity))
            return super().actor_tick(identity,*args,**kwargs)
    namespace=dict(vars(source_physics_worker));namespace.update(SourceSpeciesQueue=SourceSpeciesQueue,SourceAllPlayerChoiceQueue=SourceAllPlayerChoiceQueue,
      load_species_profiles=load_species_profiles,bind_source_reset=bind_source_reset,forget_source_actor=forget_source_actor,load_all_poses=load_all_poses,prepare_own_body=prepare_own_body)
    exec(compile(source,__file__,'exec'),namespace);namespace['start'](config)

if __name__=='__main__':start(sys.argv[1])
