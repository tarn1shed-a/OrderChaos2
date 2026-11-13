"""Original quest-zone CPU checks; trigger packets do not complete objectives."""
import math
import unittest
from pathlib import Path

from tutorial_quest_zone_probe import QuestZoneProbe, finite_f32

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'
SOURCE = ROOT / 'game-data/com.gameloft.android.ANMP.GloftO2HM/files'


class HostBoundaryTests(unittest.TestCase):
    def test_unrepresentable_and_nonfinite_positions_are_rejected(self):
        for position in ([0,0], [0,0,float('nan')], [0,float('inf'),0],
                         [0,0,1e100], [0,0,10**1000], [0,0,True], '000'):
            with self.subTest(position_type=type(position)), self.assertRaises(ValueError):
                QuestZoneProbe.checked_position(position)
        self.assertEqual(finite_f32(0.1),0.10000000149011612)


@unittest.skipUnless(NATIVE.is_file() and (SOURCE/'tables.bin').is_file(),
                     'Original APK/data remain private')
class OriginalZoneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        from map_loading_evidence import Sources
        from skill_attachments import decode_ftable
        cls.image = NativeImage(NATIVE.read_bytes())
        cls.rows = decode_ftable(Sources(SOURCE).read('tables/quests_zones.tbl'),'ID')['rows']
        cls.by_id = {r['ID']:r for r in cls.rows}
        cls.engine = QuestZoneProbe(cls.image,cls.rows)

    def new_engine(self,rows=None,**kwargs):
        return QuestZoneProbe(self.image,self.rows if rows is None else rows,**kwargs)

    def at(self,zone_id):
        return [self.by_id[zone_id][axis] for axis in ('x','y','z')]

    def test_source_anchor_is_horizontal_centre_and_vertical_bottom_all_faces_inclusive(self):
        e = self.engine; row = self.by_id[341]; anchor = self.at(341)
        self.assertTrue(e.contains(341,anchor))
        for axis,half in ((0,row['box_x']/2),(2,row['box_z']/2)):
            for sign in (-1,1):
                point = list(anchor); point[axis] += half*sign
                self.assertTrue(e.contains(341,point))
                point[axis] += .01*sign
                self.assertFalse(e.contains(341,point))
        top = list(anchor); top[1] += row['box_y']
        self.assertTrue(e.contains(341,top))
        top[1] += .01
        self.assertFalse(e.contains(341,top))
        below = list(anchor); below[1] -= .01
        self.assertFalse(e.contains(341,below))

    def test_radius_is_not_used_in_original_client_box_test(self):
        row = self.by_id[644]
        self.assertEqual(row['radius'],5)
        self.assertEqual(row['box_x'],5)
        position = self.at(644); position[0] += 3
        self.assertFalse(self.engine.contains(644,position))

    def test_original_rotation_rotates_horizontal_box_axes(self):
        row = {'ID':1,'map_id':5,'x':0.,'y':10.,'z':0.,'radius':100.,
               'box_x':2.,'box_y':4.,'box_z':6.,'box_orientation':math.pi/2}
        e = self.new_engine([row])
        self.assertTrue(e.contains(1,[2.9,10,0]))
        self.assertFalse(e.contains(1,[3.1,10,0]))
        self.assertTrue(e.contains(1,[0,10,.9]))
        self.assertFalse(e.contains(1,[0,10,1.1]))
        self.assertFalse(e.contains(1,[0,9.99,0]))
        self.assertTrue(e.contains(1,[0,14,0]))

    def test_overlapping_source_target_644_does_not_emit_an_extra_enter(self):
        e = self.new_engine()
        first = e.move_fixture(self.at(252))
        self.assertEqual(first['currentZone'],252)
        result = e.move_fixture(self.at(644))
        self.assertTrue(e.contains(644,self.at(644)))
        self.assertEqual(result['currentZone'],252)
        self.assertEqual(result['packets'],[])
        self.assertEqual(result['originalSerializations'],0)
        outside_252 = self.at(644); outside_252[0] -= 1
        result = e.move_fixture(outside_252)
        self.assertEqual(result['currentZone'],644)
        self.assertEqual([p['fields'] for p in result['packets']],
                         [{'type':2,'zone_id':252},{'type':1,'zone_id':644}])

    def test_change_sends_exit_before_enter_with_original_length_prefixed_protobuf(self):
        e = self.new_engine()
        first = e.move_fixture(self.at(341))
        self.assertEqual(first['packets'][0]['framedHex'],'05000000080110d502')
        second = e.move_fixture(self.at(253))
        self.assertEqual([p['id'] for p in second['packets']],[0x38,0x38])
        self.assertEqual([p['fields'] for p in second['packets']],
                         [{'type':2,'zone_id':341},{'type':1,'zone_id':253}])
        self.assertEqual(second['originalSerializations'],2)
        leave = e.move_fixture([0,0,0])
        self.assertEqual(leave['currentZone'],0)
        self.assertEqual([p['fields'] for p in leave['packets']],[{'type':2,'zone_id':253}])
        self.assertEqual(e.move_fixture([0,0,0])['packets'],[])
        self.assertIsNone(leave['objectiveCompletion'])

    def test_original_socket_gates_suppress_send_but_do_not_undo_zone_cache(self):
        for kwargs in ({'connected':False},{'suppressed':True},{'socket_present':False}):
            with self.subTest(kwargs=kwargs):
                e = self.new_engine()
                result = e.move_fixture(self.at(341),**kwargs)
                self.assertEqual(result['currentZone'],341)
                self.assertEqual(result['packets'],[])
                self.assertEqual(result['originalSerializations'],1)
                self.assertEqual(e.move_fixture(self.at(341))['packets'],[])

    def test_map_filter_and_empty_table_do_not_manufacture_zones(self):
        e = self.new_engine([self.by_id[341]],map_id=1)
        self.assertEqual(e.move_fixture(self.at(341))['currentZone'],0)
        e = self.new_engine([])
        self.assertEqual(e.move_fixture(self.at(341))['packets'],[])

    def test_invalid_host_inputs_do_not_change_zone_cache(self):
        e = self.new_engine(); e.move_fixture(self.at(341))
        cursor = e.cursor
        for position,kwargs in (([0,0,float('nan')],{}),([0,0,0],{'connected':1})):
            with self.assertRaises(ValueError):
                e.move_fixture(position,**kwargs)
            self.assertEqual(e.r(e.hero+0x1508,'I')[0],341)
            self.assertEqual(e.cursor,cursor)


if __name__ == '__main__':
    unittest.main()
