"""Optional original per-body ground queues and exact complete properties."""
import json
import sys

def load_body_poses(engine,cfg,root):
    from source_human_pose_worker import read_input
    from player_choice_body_pose import OwnBodyCompositionProbe,OwnBodyPoseTransport,bind_body_mask,IDENTITIES,FIELDS
    from bdae_convert import BDAE
    from bdae_animation import BDAEAnimation
    from character_elf_male_binding import source_controller
    descriptors=cfg.get('sourceBodyCompositions')
    if not isinstance(descriptors,dict)or not descriptors or set(descriptors)-set(IDENTITIES)or set(descriptors)!=set(engine.species_profiles)or not cfg.get('layerQueue'):
        raise ValueError('Exact own body composition/species set required')
    engine.body_poses={};info={}
    for key,descriptor in descriptors.items():
        if set(descriptor)!={'bodyData','body','animation','mask','binding'}:raise ValueError('All pinned body inputs required')
        inputs={name:read_input(root,item)for name,item in descriptor.items()}
        data,mask,binding=(json.loads(inputs[k][1])for k in('bodyData','mask','binding'));profile=engine.species_profiles[key]
        if profile['dataSHA256']!=descriptor['bodyData']['sha256']or mask['bodyDataSHA256']!=descriptor['bodyData']['sha256']or \
          mask['sourceBodySHA256']!=descriptor['body']['sha256']or mask['sourceAnimationSHA256']!=descriptor['animation']['sha256']or \
          binding['sourceMotion']!={k:profile[k]for k in('format','sha256','key','race','gender','sourceModelId')}:
            raise ValueError('Own actual body, queue and animation identity must agree')
        bind_body_mask(mask,data)
        body=BDAE(inputs['body'][0]);animation=BDAEAnimation(inputs['animation'][0])
        skin=source_controller(body,{'meshes':[data['meshes'][0]]},data['rig']['nodes'],0)
        vm=OwnBodyCompositionProbe(engine.image,body,body,skin,0);vm.animation(animation);vm.own_mask_file=inputs['mask'][0]
        vm.prepare_body(data,mask);vm.remove_passive_observer();vm.prepare_batch();vm.bind_body_profile(profile);vm.enable_temporary_recycling()
        transport=OwnBodyPoseTransport(binding);vm.data={'rig':{'skins':tuple({'boneNames':tuple(s['boneNames'])}for s in data['rig']['skins'])}}
        engine.body_poses[key]=(vm,transport)
        info[key]={'key':key,'bindingId':transport.binding_id,'valueBytes':binding['valueBytes'],'sourceProperties':binding['properties'],
            'sourceModelId':profile['sourceModelId'],'originalCompositionCPU':True,'originalGPUExecuted':False}
    return {FIELDS[key]:row for key,row in info.items()}

def body_queue_type(base):
    class BodyQueue(base):
        def __init__(self,*args,**kwargs):
            self.body_current_key=None;self.body_queue_trace=None;super().__init__(*args,**kwargs)
            from unicorn import UC_HOOK_CODE
            for at in(0x330d0c,0x11962c0,0x3312c4,0xa50148):self.uc.hook_add(UC_HOOK_CODE,self.observe_body_queue,begin=at,end=at)

        def observe_body_queue(self,uc,at,size,data):
            if self.body_queue_trace is not None:
                key=hex(at);self.body_queue_trace[key]=self.body_queue_trace.get(key,0)+1

        def display_tick(self,*args,**kwargs):
            if self.body_current_key is None:return super().display_tick(*args,**kwargs)
            self.body_queue_trace={}
            try:
                result=super().display_tick(*args,**kwargs);result['sourceBodyQueueTrace']=dict(self.body_queue_trace);return result
            finally:self.body_queue_trace=None

        def actor_tick(self,identity,*args,**kwargs):
            from player_choice_body_pose import FIELDS
            key=self.species_actors.get(identity);self.body_current_key=key if key in self.body_poses else None
            try:
                result=super().actor_tick(identity,*args,**kwargs)
                if self.body_current_key is not None:
                    vm,transport=self.body_poses[key];packet=result.get('sourceAnimation');trace=packet.get('sourceBodyQueueTrace',{})if isinstance(packet,dict)else{}
                    if not packet or packet.get('reason')not in(None,'distinct-track-bone-composition-not-recovered')or \
                      packet.get('nativeStateCPU')is not True or packet.get('nativeLayerQueueCPU')is not True or \
                      any(trace.get(at,0)<n for at,n in[('0x330d0c',1),('0x11962c0',2),('0x3312c4',2),('0xa50148',1)]):
                        raise ValueError('Original own body ground queue unavailable; air/direction guard retained: '+str(packet.get('reason')if packet else None))
                    original={**packet,'nativeQueueCPU':True,'nativeTimedCompletionCPU':True,'nativeBlendCPU':True,'nativePriorityQueryCPU':True}
                    full=vm.compose_bound_packet(original);result[FIELDS[key]]=transport.project(full,identity)
                    result['sourceAnimation']={**original,'available':True,'distinctPoseCompositionRestored':True,'originalOwnBodyCompleteCompositionCPU':True}
                    result['sourceAnimation'].pop('reason',None)
                return result
            finally:self.body_current_key=None
    return BodyQueue

def start(config):
    import source_physics_worker
    from source_species_queue import SourceSpeciesQueue
    from source_species_worker import staged_worker_source,load_species_profiles,bind_source_reset,forget_source_actor
    source=staged_worker_source();before="engine_type=SourceSpeciesQueue if cfg.get('sourceSpeciesProfiles') else SourceLayerQueue"
    if source.count(before)!=1:raise ValueError('Reviewed optional species worker anchor differs')
    source=source.replace(before,"engine_type=SourceOwnBodyPoseQueue if cfg.get('sourceBodyCompositions') else SourceSpeciesQueue if cfg.get('sourceSpeciesProfiles') else SourceLayerQueue")
    before='    summary.update(load_species_profiles(engine,cfg,root))'
    if source.count(before)!=1:raise ValueError('Reviewed species load anchor differs')
    source=source.replace(before,before+'\n    summary.update(load_body_poses(engine,cfg,root))')
    namespace=dict(vars(source_physics_worker));namespace.update(SourceSpeciesQueue=SourceSpeciesQueue,SourceOwnBodyPoseQueue=body_queue_type(SourceSpeciesQueue),
        load_species_profiles=load_species_profiles,bind_source_reset=bind_source_reset,forget_source_actor=forget_source_actor,load_body_poses=load_body_poses)
    exec(compile(source,__file__,'exec'),namespace);namespace['start'](config)

if __name__=='__main__':start(sys.argv[1])
