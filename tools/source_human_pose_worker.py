"""Optional original human pose output over the reviewed physics worker.

Private configuration supplies pinned loaded resources; browser requests cannot
select paths, masks, animation policies, character defaults or shader inputs.
The legacy worker and its physics/queue results are preserved.
"""
import hashlib
import json
import sys
from pathlib import Path


def read_input(root, item):
    if not isinstance(item, dict) or set(item) != {'path', 'sha256'}:
        raise ValueError('Explicit pinned private pose input required')
    original = Path(item['path'])
    path = original.resolve()
    if original.is_symlink() or not path.is_relative_to(root/'analysis/raw'):
        raise ValueError('Original pose inputs must remain in the private runtime')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != item['sha256']:
        raise ValueError('Original pose input bytes differ')
    return path, raw


def load_human_pose(engine, cfg, root):
    descriptor = cfg.get('sourceHumanComposition')
    if descriptor is None:
        return {}
    if not cfg.get('layerQueue') or not cfg.get('sourceSpeciesProfiles'):
        raise ValueError('Original model queues must be explicitly configured')
    names = {'bodyData', 'body', 'animation', 'mask', 'queue', 'binding'}
    if not isinstance(descriptor, dict) or set(descriptor) != names:
        raise ValueError('Complete original human composition inputs required')
    inputs = {name: read_input(root, descriptor[name]) for name in names}
    data, mask, queue, binding = (json.loads(inputs[name][1]) for name in
                                  ('bodyData', 'mask', 'queue', 'binding'))
    paths = {name: row[0] for name, row in inputs.items()}
    inputs.clear()  # Digests were checked; do not retain duplicate source bytes.
    if (getattr(engine, 'human_pose', None) is not None or
            engine.species_profiles.get('human-male') != queue.get('species') or
            mask.get('bodyDataSHA256') != descriptor['bodyData']['sha256'] or
            mask.get('sourceBodySHA256') != descriptor['body']['sha256'] or
            mask.get('sourceAnimationSHA256') != descriptor['animation']['sha256']):
        raise ValueError('Actual registered human queue and loaded resources must agree')
    from character_human_queue_fast_transport import FastPoseTransport
    transport = FastPoseTransport(binding)
    if (binding['sourceBodyDataSHA256'] != descriptor['bodyData']['sha256'] or
            binding['sourceMaskSHA256'] != mask.get('sha256') or
            binding['sourceMotion'] != {k: queue['species'][k] for k in
                ('format', 'sha256', 'key', 'race', 'gender', 'sourceModelId')}):
        raise ValueError('Original pose binding differs from the loaded queue')
    from bdae_convert import BDAE
    from bdae_animation import BDAEAnimation
    from character_elf_male_binding import source_controller
    from character_human_queue_fast_probe import FastHumanCompositionProbe
    import character_human_queue_composition_probe as composition
    body, animation = BDAE(paths['body']), BDAEAnimation(paths['animation'])
    skin = source_controller(body, {'meshes': [data['meshes'][0]]}, data['rig']['nodes'], 0)
    vm = FastHumanCompositionProbe(engine.image, body, body, skin, 0)
    vm.animation(animation)
    # The frozen inspector still has a research-path constant. Bind it only
    # during this synchronous worker's setup, then restore it in all outcomes.
    old_mask = composition.MASK
    try:
        composition.MASK = paths['mask']
        vm.prepare_composition(data)
    finally:
        composition.MASK = old_mask
    # Full byte/canonical/body/mask validation and native target construction
    # have completed. The compositor only consults these names afterward.
    # Geometry and preconverted clip JSON are not a second runtime sampler.
    vm.data = {'rig': {'skins': tuple({'boneNames': tuple(s['boneNames'])}
                                     for s in data['rig']['skins'])}}
    vm.remove_passive_observer()
    vm.prepare_batch()
    vm.bind_profile(queue)
    vm.enable_temporary_recycling()
    engine.human_pose = (vm, transport)
    return {'sourceHumanPose': {'key': 'human-male', 'bindingId': transport.binding_id,
            'valueBytes': 1992, 'originalCompositionCPU': True,
            'bodyDataSHA256': descriptor['bodyData']['sha256'],
            'originalGPUExecuted': False}}


def human_pose_queue_type(base):
    class HumanPoseQueue(base):
        def actor_tick(self, identity, *args, **kwargs):
            human = self.species_actors.get(identity) == 'human-male'
            if human and getattr(self, 'human_pose', None) is None:
                raise ValueError('Original human composition is not configured')
            result = super().actor_tick(identity, *args, **kwargs)
            if human:
                vm, transport = self.human_pose
                # Consume this actor's actual original queue output. Never use
                # a saved QA pose, infer an action, or replace a failed result.
                result['sourceHumanPose'] = transport.project(
                    vm.compose_bound_packet(result.get('sourceAnimation')), identity)
            return result
    return HumanPoseQueue


def staged_human_worker_source():
    from source_species_worker import staged_worker_source
    source = staged_worker_source()
    replacements = [
        ('engine_type=SourceSpeciesQueue if cfg.get(\'sourceSpeciesProfiles\') else SourceLayerQueue',
         'engine_type=SourceHumanPoseQueue if cfg.get(\'sourceHumanComposition\') else SourceSpeciesQueue if cfg.get(\'sourceSpeciesProfiles\') else SourceLayerQueue'),
        ('    summary.update(load_species_profiles(engine,cfg,root))',
         '    summary.update(load_species_profiles(engine,cfg,root))\n    summary.update(load_human_pose(engine,cfg,root))'),
    ]
    for before, after in replacements:
        if source.count(before) != 1:
            raise ValueError('Reviewed model worker composition anchor differs')
        source = source.replace(before, after)
    return source


def start(config):
    import source_physics_worker
    from source_species_queue import SourceSpeciesQueue
    from source_species_worker import load_species_profiles, bind_source_reset, forget_source_actor
    namespace = dict(vars(source_physics_worker))
    namespace.update(SourceSpeciesQueue=SourceSpeciesQueue,
                     SourceHumanPoseQueue=human_pose_queue_type(SourceSpeciesQueue),
                     load_species_profiles=load_species_profiles,
                     bind_source_reset=bind_source_reset,
                     forget_source_actor=forget_source_actor,
                     load_human_pose=load_human_pose)
    exec(compile(staged_human_worker_source(), __file__, 'exec'), namespace)
    namespace['start'](config)


if __name__ == '__main__':
    start(sys.argv[1])
