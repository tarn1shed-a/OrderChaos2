"""Optional Female32 ground-queue/original-composer worker, no air fallback."""
import json
import sys
from pathlib import Path


def load_female_pose(engine,cfg,root):
    from source_human_pose_worker import read_input
    from player_choice_female_pose import FemaleCompositionProbe,FemalePoseTransport,bind_female_mask
    from bdae_convert import BDAE
    from bdae_animation import BDAEAnimation
    from character_elf_male_binding import source_controller
    descriptor=cfg.get('sourceFemaleComposition')
    if not isinstance(descriptor,dict)or set(descriptor)!={'bodyData','body','animation','mask','binding'} or \
      not cfg.get('sourceSpeciesProfiles')or not cfg.get('layerQueue'):
        raise ValueError('All pinned own female composition inputs required')
    from source_server_body_data import load_server_body_data,source_server_body_data_index,reuse_animation_reader
    server_index=source_server_body_data_index(root)
    shared_reader=getattr(getattr(engine,'bank',None),'reader',None)if server_index else None
    inputs={name:read_input(root,item)for name,item in descriptor.items()if name not in('bodyData','animation')}
    if shared_reader is None:
        inputs['animation']=read_input(root,descriptor['animation'])
        animation=BDAEAnimation(inputs['animation'][0])
    else:
        animation=reuse_animation_reader(root,descriptor['animation'],shared_reader)
    data=load_server_body_data(root,descriptor['bodyData'],descriptor['mask'],server_index)
    mask,binding=(json.loads(inputs[k][1])for k in('mask','binding'))
    profile=engine.species_profiles.get('human-female')
    if not profile or profile['dataSHA256']!=descriptor['bodyData']['sha256'] or \
      mask['bodyDataSHA256']!=descriptor['bodyData']['sha256'] or mask['sourceBodySHA256']!=descriptor['body']['sha256'] or \
      mask['sourceAnimationSHA256']!=descriptor['animation']['sha256'] or \
      binding['sourceMotion']!={k:profile[k]for k in('format','sha256','key','race','gender','sourceModelId')}:
        raise ValueError('Actual registered female queue and body must agree')
    bind_female_mask(mask,data)
    body=BDAE(inputs['body'][0])
    skin=source_controller(body,{'meshes':[data['meshes'][0]]},data['rig']['nodes'],0)
    vm=FemaleCompositionProbe(engine.image,body,body,skin,0);vm.animation(animation)
    vm.female_mask_file=inputs['mask'][0];vm.prepare_female(data,mask);vm.remove_passive_observer();vm.prepare_batch();vm.bind_female_profile(profile);vm.enable_temporary_recycling()
    transport=FemalePoseTransport(binding)
    vm.data={'rig':{'skins':tuple({'boneNames':tuple(s['boneNames'])}for s in data['rig']['skins'])}}
    engine.female_pose=(vm,transport)
    return {'sourceFemalePose':{'key':'human-female','bindingId':transport.binding_id,'valueBytes':binding['valueBytes'],
            'sourceProperties':131,'originalCompositionCPU':True,'originalGPUExecuted':False}}


def female_queue_type(base):
    class FemaleQueue(base):
        def __init__(self,*args,**kwargs):
            self.female_current_actor=False;self.female_queue_trace=None
            super().__init__(*args,**kwargs)
            from unicorn import UC_HOOK_CODE
            for at in(0x330d0c,0x11962c0,0x3312c4,0xa50148):
                self.uc.hook_add(UC_HOOK_CODE,self.observe_female_queue,begin=at,end=at)

        def observe_female_queue(self,uc,at,size,data):
            if self.female_queue_trace is not None:
                key=hex(at);self.female_queue_trace[key]=self.female_queue_trace.get(key,0)+1

        def display_tick(self,*args,**kwargs):
            if not self.female_current_actor:return super().display_tick(*args,**kwargs)
            self.female_queue_trace={}
            try:
                result=super().display_tick(*args,**kwargs)
                result['sourceFemaleQueueTrace']=dict(self.female_queue_trace)
                return result
            finally:self.female_queue_trace=None

        def actor_tick(self,identity,*args,**kwargs):
            self.female_current_actor=self.species_actors.get(identity)=='human-female'
            try:
                result=super().actor_tick(identity,*args,**kwargs)
                if self.female_current_actor:
                    vm,transport=self.female_pose;packet=result.get('sourceAnimation')
                    trace=packet.get('sourceFemaleQueueTrace',{})if isinstance(packet,dict)else{}
                    if not packet or packet.get('reason')not in(None,'distinct-track-bone-composition-not-recovered')or \
                      packet.get('nativeStateCPU')is not True or packet.get('nativeLayerQueueCPU')is not True or \
                      any(trace.get(at,0)<count for at,count in[('0x330d0c',1),('0x11962c0',2),('0x3312c4',2),('0xa50148',1)]):
                        raise ValueError('Original female ground queue is unavailable; air/direction guard retained: '+repr({'reason':packet.get('reason')if packet else None,'trace':trace,'posture':result.get('lastPosture'),'grounded':result.get('grounded'),'sourcePosture':packet.get('cachedWords')if packet else None}))
                    # The old scalar host omitted these flags when layers
                    # differ. This new consumer has observed the actual same
                    # original selector/clocks/blends/priority calls and now
                    # executes the complete own131-property composer below.
                    original={**packet,'nativeQueueCPU':True,'nativeTimedCompletionCPU':True,'nativeBlendCPU':True,'nativePriorityQueryCPU':True}
                    complete=vm.compose_bound_packet(original)
                    result['sourceFemalePose']=transport.project(complete,identity)
                    result['sourceAnimation']={**original,'available':True,'distinctPoseCompositionRestored':True,
                        'originalFemaleCompleteCompositionCPU':True}
                    result['sourceAnimation'].pop('reason',None)
                return result
            finally:self.female_current_actor=False
    return FemaleQueue


def start(config):
    import source_physics_worker
    from source_species_queue import SourceSpeciesQueue
    from source_species_worker import staged_worker_source,load_species_profiles,bind_source_reset,forget_source_actor
    source=staged_worker_source()
    before="engine_type=SourceSpeciesQueue if cfg.get('sourceSpeciesProfiles') else SourceLayerQueue"
    after="engine_type=SourceFemalePoseQueue if cfg.get('sourceFemaleComposition') else SourceSpeciesQueue if cfg.get('sourceSpeciesProfiles') else SourceLayerQueue"
    if source.count(before)!=1:raise ValueError('Reviewed optional species worker anchor differs')
    source=source.replace(before,after)
    before='    summary.update(load_species_profiles(engine,cfg,root))'
    if source.count(before)!=1:raise ValueError('Reviewed original species load anchor differs')
    source=source.replace(before,before+'\n    summary.update(load_female_pose(engine,cfg,root))')
    namespace=dict(vars(source_physics_worker));namespace.update(SourceSpeciesQueue=SourceSpeciesQueue,
        SourceFemalePoseQueue=female_queue_type(SourceSpeciesQueue),load_species_profiles=load_species_profiles,
        bind_source_reset=bind_source_reset,forget_source_actor=forget_source_actor,load_female_pose=load_female_pose)
    exec(compile(source,__file__,'exec'),namespace);namespace['start'](config)


if __name__=='__main__':start(sys.argv[1])
