"""Optional ElfMale33 ground-queue/original-composer worker, no air fallback."""
import json
import sys
from pathlib import Path


def load_elf_pose(engine,cfg,root):
    from source_human_pose_worker import read_input
    from player_choice_elf_pose import ElfCompositionProbe,ElfPoseTransport,bind_elf_mask
    from bdae_convert import BDAE
    from bdae_animation import BDAEAnimation
    from character_elf_male_binding import source_controller
    descriptor=cfg.get('sourceElfMaleComposition')
    if not isinstance(descriptor,dict)or set(descriptor)!={'bodyData','body','animation','mask','binding'} or \
      not cfg.get('sourceSpeciesProfiles')or not cfg.get('layerQueue'):
        raise ValueError('All pinned own elf male composition inputs required')
    inputs={name:read_input(root,item)for name,item in descriptor.items()}
    data,mask,binding=(json.loads(inputs[k][1])for k in('bodyData','mask','binding'))
    profile=engine.species_profiles.get('elf-male')
    if not profile or profile['dataSHA256']!=descriptor['bodyData']['sha256'] or \
      mask['bodyDataSHA256']!=descriptor['bodyData']['sha256'] or mask['sourceBodySHA256']!=descriptor['body']['sha256'] or \
      mask['sourceAnimationSHA256']!=descriptor['animation']['sha256'] or \
      binding['sourceMotion']!={k:profile[k]for k in('format','sha256','key','race','gender','sourceModelId')}:
        raise ValueError('Actual registered elf male queue and body must agree')
    bind_elf_mask(mask,data)
    body=BDAE(inputs['body'][0]);animation=BDAEAnimation(inputs['animation'][0])
    skin=source_controller(body,{'meshes':[data['meshes'][0]]},data['rig']['nodes'],0)
    vm=ElfCompositionProbe(engine.image,body,body,skin,0);vm.animation(animation)
    vm.elf_mask_file=inputs['mask'][0];vm.prepare_elf(data,mask);vm.remove_passive_observer();vm.prepare_batch();vm.bind_elf_profile(profile);vm.enable_temporary_recycling()
    transport=ElfPoseTransport(binding)
    vm.data={'rig':{'skins':tuple({'boneNames':tuple(s['boneNames'])}for s in data['rig']['skins'])}}
    engine.elf_pose=(vm,transport)
    return {'sourceElfMalePose':{'key':'elf-male','bindingId':transport.binding_id,'valueBytes':binding['valueBytes'],
            'sourceProperties':82,'originalCompositionCPU':True,'originalGPUExecuted':False}}


def elf_queue_type(base):
    class ElfQueue(base):
        def __init__(self,*args,**kwargs):
            self.elf_current_actor=False;self.elf_queue_trace=None
            super().__init__(*args,**kwargs)
            from unicorn import UC_HOOK_CODE
            for at in(0x330d0c,0x11962c0,0x3312c4,0xa50148):
                self.uc.hook_add(UC_HOOK_CODE,self.observe_elf_queue,begin=at,end=at)

        def observe_elf_queue(self,uc,at,size,data):
            if self.elf_queue_trace is not None:
                key=hex(at);self.elf_queue_trace[key]=self.elf_queue_trace.get(key,0)+1

        def display_tick(self,*args,**kwargs):
            if not self.elf_current_actor:return super().display_tick(*args,**kwargs)
            self.elf_queue_trace={}
            try:
                result=super().display_tick(*args,**kwargs)
                result['sourceElfMaleQueueTrace']=dict(self.elf_queue_trace)
                return result
            finally:self.elf_queue_trace=None

        def actor_tick(self,identity,*args,**kwargs):
            self.elf_current_actor=self.species_actors.get(identity)=='elf-male'
            try:
                result=super().actor_tick(identity,*args,**kwargs)
                if self.elf_current_actor:
                    vm,transport=self.elf_pose;packet=result.get('sourceAnimation')
                    trace=packet.get('sourceElfMaleQueueTrace',{})if isinstance(packet,dict)else{}
                    if not packet or packet.get('reason')not in(None,'distinct-track-bone-composition-not-recovered')or \
                      packet.get('nativeStateCPU')is not True or packet.get('nativeLayerQueueCPU')is not True or \
                      any(trace.get(at,0)<count for at,count in[('0x330d0c',1),('0x11962c0',2),('0x3312c4',2),('0xa50148',1)]):
                        raise ValueError('Original elf male ground queue is unavailable; air/direction guard retained: '+repr({'reason':packet.get('reason')if packet else None,'trace':trace,'posture':result.get('lastPosture'),'grounded':result.get('grounded'),'sourcePosture':packet.get('cachedWords')if packet else None}))
                    # The old scalar host omitted these flags when layers
                    # differ. This new consumer has observed the actual same
                    # original selector/clocks/blends/priority calls and now
                    # executes the complete own82-property composer below.
                    original={**packet,'nativeQueueCPU':True,'nativeTimedCompletionCPU':True,'nativeBlendCPU':True,'nativePriorityQueryCPU':True}
                    complete=vm.compose_bound_packet(original)
                    result['sourceElfMalePose']=transport.project(complete,identity)
                    result['sourceAnimation']={**original,'available':True,'distinctPoseCompositionRestored':True,
                        'originalElfMaleCompleteCompositionCPU':True}
                    result['sourceAnimation'].pop('reason',None)
                return result
            finally:self.elf_current_actor=False
    return ElfQueue


def start(config):
    import source_physics_worker
    from source_species_queue import SourceSpeciesQueue
    from source_species_worker import staged_worker_source,load_species_profiles,bind_source_reset,forget_source_actor
    source=staged_worker_source()
    before="engine_type=SourceSpeciesQueue if cfg.get('sourceSpeciesProfiles') else SourceLayerQueue"
    after="engine_type=SourceElfMalePoseQueue if cfg.get('sourceElfMaleComposition') else SourceSpeciesQueue if cfg.get('sourceSpeciesProfiles') else SourceLayerQueue"
    if source.count(before)!=1:raise ValueError('Reviewed optional species worker anchor differs')
    source=source.replace(before,after)
    before='    summary.update(load_species_profiles(engine,cfg,root))'
    if source.count(before)!=1:raise ValueError('Reviewed original species load anchor differs')
    source=source.replace(before,before+'\n    summary.update(load_elf_pose(engine,cfg,root))')
    namespace=dict(vars(source_physics_worker));namespace.update(SourceSpeciesQueue=SourceSpeciesQueue,
        SourceElfMalePoseQueue=elf_queue_type(SourceSpeciesQueue),load_species_profiles=load_species_profiles,
        bind_source_reset=bind_source_reset,forget_source_actor=forget_source_actor,load_elf_pose=load_elf_pose)
    exec(compile(source,__file__,'exec'),namespace);namespace['start'](config)


if __name__=='__main__':start(sys.argv[1])
