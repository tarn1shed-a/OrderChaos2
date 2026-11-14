"""Host routing of original queue CPU to each explicit actor's own track views.

The original state, request, priority, timer and completion code is inherited
unchanged. The supplied loaded-track metadata is per actor instead of global.
No actor is silently assigned a species, default appearance or server identity.
"""
import copy
from source_layer_queue import SourceLayerQueue
from species_world_profiles import validate_profile


class SourceSpeciesQueue(SourceLayerQueue):
    def __init__(self, image):
        super().__init__(image)
        self.species_profiles = {}
        self.species_actors = {}

    def register_species(self, profile):
        validate_profile(profile, self.image_hash())
        key = profile['key']
        if key in self.species_profiles:
            raise ValueError('Species profile already registered')
        self.species_profiles[key] = copy.deepcopy(profile)

    def bind_species(self, identity, key):
        if not isinstance(identity, str) or not identity or key not in self.species_profiles:
            raise ValueError('Explicit actor identity and verified species required')
        if identity in self.actors or identity in self.species_actors:
            raise ValueError('Cannot change an existing actor species or reinterpret its queue')
        self.species_actors[identity] = key

    def actor_tick(self, identity, *args, **kwargs):
        key = self.species_actors.get(identity)
        if key is None:
            return super().actor_tick(identity, *args, **kwargs)
        source = self.species_profiles[key]
        old_stop, old_layer = self.stop_profile, self.layer_profile
        # The VM is synchronous. Restore globals even on a native failure so
        # an interleaved legacy/other-species actor cannot inherit this clock.
        self.stop_profile = {**old_stop, 'ranges': source['ranges']}
        self.layer_profile = {**old_layer, 'sourceClipNames': source['sourceClipNames'],
                              'engineFlags': source['engineFlags']}
        try:
            result = super().actor_tick(identity, *args, **kwargs)
            packet = result.get('sourceAnimation')
            if packet is not None:
                packet['sourceMotion'] = {k: source[k] for k in
                    ('format', 'sha256', 'key', 'race', 'gender', 'sourceModelId')}
            return result
        finally:
            self.stop_profile, self.layer_profile = old_stop, old_layer
