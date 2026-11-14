"""Original CPU cross-species stop completion and interleaved actor isolation."""
import copy
import json
import unittest
from pathlib import Path
from species_world_profiles import ROOT, profile_digest, validate_profile

RAW = ROOT/'analysis/raw/species-world-router-20261115'
RUNTIME = ROOT/'analysis/raw/showcase-20261110/running-preview'


class PublicTests(unittest.TestCase):
    def test_missing_or_modified_loaded_track_inputs_are_rejected(self):
        for profile in ({}, {'format': 'oc2-source-species-motion-v1', 'sha256': '0'*64}):
            with self.assertRaisesRegex(ValueError, 'Unverified'):
                validate_profile(profile, 'source')


@unittest.skipUnless((RAW/'profiles-v1.json').is_file(), 'Original profiles remain private')
class OriginalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from source_species_queue import SourceSpeciesQueue
        from analyze_native_resources import NativeImage
        cfg = json.loads((RUNTIME/'prototype/native-physics.json').read_text())
        cls.engine = e = SourceSpeciesQueue(NativeImage(Path(cfg['library']).read_bytes()))
        e.load_world(json.loads(Path(cfg['terrain']).read_text()),
                     json.loads(Path(cfg['collision']).read_text()),
                     lambda name: Path(cfg['sourceFiles'][name]['path']).read_bytes(),
                     {tuple(r['tile']): r['runtimeFlags'] for r in json.loads(Path(cfg['terrainLighting']).read_text())['tiles']})
        for key, method in [('swimming', 'load_water'), ('diving', 'load_diving'),
                            ('animationBlending', 'load_animation_blending'),
                            ('stopQueue', 'load_stop_queue'), ('layerQueue', 'load_layer_queue')]:
            getattr(e, method)(json.loads(Path(cfg[key]).read_text()))
        cls.profiles = json.loads((RAW/'profiles-v1.json').read_text())
        for value in cls.profiles.values():
            e.register_species(value)

    def test_profiles_reproduce_original_model_ranges_and_flags(self):
        from species_world_profiles import recover
        from map_loading_evidence import Sources
        from resource_packs import DEFAULT_SOURCE
        for key, profile in self.profiles.items():
            self.assertEqual(recover(self.engine.image, Sources(DEFAULT_SOURCE), key), profile)
        self.assertEqual([p['ranges']['run_idle']['endMs']-p['ranges']['run_idle']['startMs']
                          for p in self.profiles.values()], [933, 933, 633])

    def test_interleaved_actors_finish_on_their_own_original_clock(self):
        e = self.engine
        keys = [*self.profiles, 'legacy-elf-female']
        names = {key: 'species-roundtrip-'+key for key in keys}
        positions = {key: [-2235.5, 108.55000305175781, 12] for key in keys}
        frames = {key: [] for key in keys}
        for key in self.profiles:
            e.bind_species(names[key], key)
        old_stop, old_layer = e.stop_profile, e.layer_profile
        for direction, count in [(1, 24), (0, 38), (1, 7), (0, 38)]:
            for _ in range(count):
                for key in keys:
                    result = e.actor_tick(names[key], positions[key], [direction*4.8, 0], 50,
                                          False, {'forward': bool(direction)})
                    positions[key] = result['position']
                    packet = result['sourceAnimation']
                    self.assertTrue(packet['available'])
                    self.assertTrue(packet['layerPoseAgreement'])
                    if key in self.profiles:
                        self.assertEqual(packet['sourceMotion']['sha256'], self.profiles[key]['sha256'])
                    else:
                        self.assertNotIn('sourceMotion', packet)
                    self.assertIs(e.stop_profile, old_stop)
                    self.assertIs(e.layer_profile, old_layer)
                    frames[key].append(copy.deepcopy(packet))
        completions = {}
        for key, values in frames.items():
            stopping = values[24:62]
            index = next(i for i, p in enumerate(stopping) if p['current']['clip'] == 'idle')
            completions[key] = {'firstIdleTick': index, 'lastStop': stopping[index-1]['current'],
                                'completionCount': stopping[index]['completionCount']}
            self.assertEqual(stopping[0]['current']['clip'], 'run_idle')
            self.assertEqual(stopping[index]['completionCount'], 1)
            self.assertEqual(values[62]['current']['clip'], 'run_normal_front')
        self.assertEqual(completions['human-male']['firstIdleTick'], completions['human-female']['firstIdleTick'])
        self.assertLess(completions['elf-male']['firstIdleTick'], completions['human-male']['firstIdleTick'])
        self.assertLess(completions['human-male']['firstIdleTick'], completions['legacy-elf-female']['firstIdleTick'])
        self.assertEqual(len({tuple(positions[k]) for k in keys}), 1)
        (RAW/'native-roundtrip-v1.json').write_text(json.dumps({
            'format': 'oc2-original-species-queue-roundtrip-v1', 'originalCPU': True,
            'actorCount': 4, 'framesPerActor': len(frames[key]), 'frames': frames,
            'completions': completions, 'finalPositions': positions,
            'hostBoundaries': ['explicit actor appearance/species', 'loaded scalar track views',
                               'horizontal input and transport cadence', 'no original server or GL claim'],
        }, indent=2)+'\n')

    def test_invalid_binding_and_profile_do_not_reinterpret_existing_actor(self):
        e = self.engine
        with self.assertRaisesRegex(ValueError, 'Explicit'):
            e.bind_species('invalid-model', 'not-a-species')
        e.bind_species('fixed-model', 'human-male')
        with self.assertRaisesRegex(ValueError, 'Cannot change'):
            e.bind_species('fixed-model', 'elf-male')
        bad = copy.deepcopy(self.profiles['human-male'])
        bad['ranges']['run_idle']['endMs'] += 300
        with self.assertRaisesRegex(ValueError, 'Unverified'):
            e.register_species(bad)
        self.assertEqual(e.species_actors['fixed-model'], 'human-male')

    def test_profile_globals_restore_after_native_failure(self):
        e = self.engine
        e.bind_species('explicit-native-failure', 'human-female')
        old_stop, old_layer = e.stop_profile, e.layer_profile
        with self.assertRaises((TypeError, ValueError)):
            e.actor_tick('explicit-native-failure', None)
        self.assertIs(e.stop_profile, old_stop)
        self.assertIs(e.layer_profile, old_layer)


if __name__ == '__main__':
    unittest.main()
