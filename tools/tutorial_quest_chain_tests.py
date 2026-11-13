"""Source/CPU gates for the tutorial audit; passing is not a playable quest."""
import unittest
from pathlib import Path

from tutorial_quest_chain import link_objectives

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'
SOURCE = ROOT / 'game-data/com.gameloft.android.ANMP.GloftO2HM/files'


class JoinTests(unittest.TestCase):
    def test_step_order_and_two_part_join_prevent_the_tutorial_misordering(self):
        objectives = [{'id': 10, 'quest_id': 202, 'obj_idx': 2, 'step': 3},
                      {'id': 99, 'quest_id': 202, 'obj_idx': 9, 'step': 2}]
        logic = [{'quest_id': 202, 'obj_idx': 9, 'zone': 1},
                 {'quest_id': 500, 'obj_idx': 2, 'zone': 2}]
        result = link_objectives(202, objectives, logic, [{'ID': 1}, {'ID': 2}])
        self.assertEqual([r['objective']['obj_idx'] for r in result], [9, 2])
        self.assertEqual(result[1]['targets'], [])

    def test_missing_zone_and_orphan_logic_are_not_synthesised(self):
        objective = [{'quest_id': 202, 'obj_idx': 1, 'step': 1}]
        with self.assertRaisesRegex(ValueError, 'absent zone'):
            link_objectives(202, objective, [{'quest_id': 202, 'obj_idx': 1, 'zone': 8}], [])
        with self.assertRaisesRegex(ValueError, 'Orphan'):
            link_objectives(202, objective, [{'quest_id': 202, 'obj_idx': 2, 'zone': 0}], [])

    def test_duplicate_objectives_are_an_error_not_an_arbitrary_choice(self):
        row = {'quest_id': 202, 'obj_idx': 1, 'step': 1}
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            link_objectives(202, [row, row], [], [])


@unittest.skipUnless(NATIVE.is_file() and (SOURCE / 'tables.bin').is_file(),
                     'Original APK/data remain private')
class SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        from map_loading_evidence import Sources
        from native_inside_collision_probe import InsidePhysicsProbe
        from tutorial_quest_chain import audit
        cls.source = Sources(SOURCE)
        cls.chain = audit(SOURCE)
        cls.engine = InsidePhysicsProbe(NativeImage(NATIVE.read_bytes()))

    def test_tutorial_has_ten_steps_but_no_proved_finish_predicate(self):
        c = self.chain
        self.assertEqual([r['objective']['obj_idx'] for r in c['steps']],
                         [1, 9, 2, 3, 4, 5, 10, 6, 7, 8])
        self.assertEqual(c['quest']['FinishGiverID'], 0)
        self.assertEqual(c['quest']['AutoShowFinish'], 1)
        self.assertIsNone(c['completionPredicate'])
        self.assertIsNone(c['acceptedQuest'])
        self.assertFalse(c['routeVerified'])

    def test_source_elevator_and_manual_spawns_prevent_static_only_certification(self):
        elevator, = self.chain['elevatorSpawns']
        self.assertEqual([elevator['id'], elevator['Entry']], [739, 209])
        self.assertAlmostEqual(elevator['elevator_star_y'] - elevator['elevator_over_y'],
                               32.96, places=3)
        hammer, = [r for r in self.chain['objectSpawns'] if r['Entry'] == 190]
        self.assertEqual(hammer['manual_spawn'], 1)
        self.assertEqual(self.chain['npcInteractions'], [])

    def test_native_inside_branch_keeps_normal_chain_when_extra_file_is_absent(self):
        for model, count in [('god_underground_palace01', 70),
                             ('god_underground_palace02', 24),
                             ('god_temple01_inside01', 20)]:
            path = 'model/scene_generator_temple_000/' + model
            for quality in (False, True):
                with self.subTest(model=model, simplified=quality):
                    result = self.engine.select(path + '.bdae', self.source, simplified=quality)
                    self.assertEqual(result['originalReturn'], 1)
                    self.assertEqual(result['shapeCount'], count)
                    self.assertEqual(result['readRequests'], [path + '.phy', path + '_inside.phy'])
                    self.assertTrue(result['normalChainUnchanged'])
                    if quality:
                        self.assertIn(path + '_inside_s.phy', result['presenceProbes'])

    def test_original_stream_retains_eleven_records_without_repairing_the_file(self):
        from scene_collision import decode_phy
        path = 'model/scene_generator_temple_000/god_underground_palace02_02.bdae'
        raw = self.source.read(path.replace('.bdae', '.phy'))
        self.assertEqual(len(raw), 4484)
        # The generic decoder remains strict; only executed source evidence
        # authorises the EOF prefix, not a changed header or fabricated shape.
        with self.assertRaisesRegex(ValueError, 'Truncated PHY'):
            decode_phy(raw)
        for quality in (False, True):
            result = self.engine.select(path, self.source, simplified=quality)
            self.assertEqual(result['originalReturn'], 1)
            self.assertEqual(result['shapeCount'], 11)
            self.assertTrue(result['normalChainUnchanged'])
            report = result['nativeStream']
            self.assertEqual(report['sourceSHA256'],
                             '13ad30bb3a43dc87a7c0419419135f6579e82379ee4032df670b00a40a8492f5')
            self.assertEqual([report['declaredShapeCount'],report['retainedShapeCount'],
                              report['bytesConsumed'],report['descriptorError']], [12,11,4484,1])
        self.assertEqual(self.source.read(path.replace('.bdae', '.phy')), raw)

    def test_native_eof_does_not_authorise_an_incomplete_shape(self):
        raw = self.source.read('model/scene_generator_temple_000/god_underground_palace02_02.phy')
        with self.assertRaisesRegex(ValueError, 'Truncated PHY|Trailing PHY'):
            self.engine.read_phy(raw[:-1], 'partial-record-negative.phy')

    def test_original_getter_returns_the_prefix_despite_descriptor_error(self):
        from unicorn import UC_HOOK_CODE
        from analyze_native_resources import NativeImage
        from native_phy_stream import NativePHYStreamPhysics

        class GetterProbe(NativePHYStreamPhysics):
            PROVIDE = 0x30000810
            def hook(self, uc, address, size, data):
                if address == self.PROVIDE:
                    self.set('X0', self.stream)
                elif address == 0xa8674c:
                    self.descriptors.append(self.get('X0'))
                    return  # Observe the real reader without replacing it.
                elif self.imports.get(address) in ('pthread_mutex_lock','pthread_mutex_unlock'):
                    self.set('W0', 0)  # Single-thread inspection, not a live cache.
                else:
                    return super().hook(uc,address,size,data)
                self.set('PC', self.get('X30'))

        e = GetterProbe(NativeImage(NATIVE.read_bytes())); e.descriptors = []
        for address in (e.PROVIDE, 0xa8674c):
            e.uc.hook_add(UC_HOOK_CODE,e.hook,begin=address,end=address)
        name = 'model/scene_generator_temple_000/god_underground_palace02_02.phy'
        raw = self.source.read(name); stream, filename = e.memory_stream(raw,name)
        e.uc.mem_write(e.filename,name.encode()+b'\0')
        e.w(e.stream,'Q',0x2425a70)
        # Host provider owns one reference; the getter must release only its own.
        e.w(e.stream+8,'I',2); e.w(e.stream+0x10,'Q',stream)
        e.w(e.stream+0x18,'Q',len(raw)); e.w(e.stream+0x20,'Q',filename)
        provider=e.alloc(0x20); vtable=e.alloc(0x20)
        e.w(provider,'Q',vtable); e.w(vtable+0x18,'Q',e.PROVIDE)
        for address in range(0x25451f8,0x2545230,8):
            e.w(address,'Q',provider if address==0x25451f8 else 0)
        pointer=e.call(0xa862a4,{'X0':filename}); count=0
        while pointer:
            count+=1; self.assertLessEqual(count,12)
            pointer=e.r(pointer+8,'Q')[0]
        self.assertEqual(count,11)
        self.assertEqual([e.r(p,'B')[0] for p in e.descriptors],[1])
        self.assertEqual(e.r(e.stream+8,'I')[0],1)

    def test_original_stream_short_read_and_eof_leave_unread_destination_bytes_unchanged(self):
        e = self.engine
        stream, _ = e.memory_stream(b'ABCD', 'stream-boundary-fixture')
        target = e.alloc(8)
        read = e.r(e.r(stream, 'Q')[0] + 0x18, 'Q')[0]
        e.w(stream + 0x30, 'Q', 2); e.uc.mem_write(target, b'12345678')
        self.assertEqual(e.call(read, {'X0':stream,'X1':target,'W2':4}), 2)
        self.assertEqual(bytes(e.uc.mem_read(target,8)), b'CD345678')
        self.assertEqual(e.r(stream + 0x30, 'Q')[0], 4)
        self.assertEqual(e.call(read, {'X0':stream,'X1':target,'W2':4}), 0)
        self.assertEqual(bytes(e.uc.mem_read(target,8)), b'CD345678')


if __name__ == '__main__':
    unittest.main()
