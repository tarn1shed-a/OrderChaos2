"""Quest request evidence gates; no live server, acceptance, reward or save."""
import unittest
from pathlib import Path

from tutorial_quest_request_probe import wire_fields

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'


class WireBoundaryTests(unittest.TestCase):
    def test_rejects_truncated_oversized_and_invalid_wire_input(self):
        for raw in (b'\x08\x80', b'\x08'+b'\xff'*9+b'\x02',
                    b'\x12\x02a', b'\x00', b'\x0d1234',
                    b'\x80\x80\x80\x80\x10\x00'):
            with self.subTest(raw=raw.hex()), self.assertRaises(ValueError):
                wire_fields(raw)
        with self.assertRaises(ValueError):
            wire_fields(bytearray(b'\x08\x01'))

    def test_uint64_and_length_span_are_kept_without_truncation(self):
        raw = b'\x08'+b'\xff'*9+b'\x01\x12\x03abc'
        fields = wire_fields(raw)
        self.assertEqual([row[:3] for row in fields],
                         [(1,0,0xffffffffffffffff),(2,2,b'abc')])
        self.assertEqual(raw[fields[1][3]:], b'abc')


@unittest.skipUnless(NATIVE.is_file(), 'Original APK native library remains private')
class OriginalRequestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        from tutorial_quest_request_probe import QuestRequestProbe
        cls.engine = QuestRequestProbe(NativeImage(NATIVE.read_bytes()))

    def test_original_query_and_complete_are_distinct_and_do_not_complete_cache(self):
        for status, code in ((5,0x2c),(6,0x2c),(7,0x2e),(8,0x2e),(9,0x2e)):
            with self.subTest(status=status):
                result = self.engine.click(status)
                self.assertEqual([p['id'] for p in result['packets']], [code])
                self.assertEqual(result['packets'][0]['hex'],
                                 '08a18695bb88cf959a1210ca01')
                self.assertEqual(result['cachedStatusAfter'], status)
                self.assertFalse(result['liveServerOrSavesUsed'])

    def test_missing_cache_invalid_as_value_and_nonrequest_states_send_nothing(self):
        for kwargs in ({'cached':False},{'argument_type':1},
                       {'argument_count':0},{'argument_count':2}):
            with self.subTest(kwargs=kwargs):
                result = self.engine.click(6, **kwargs)
                self.assertEqual(result['packets'], [])
                self.assertEqual(result['cachedStatusAfter'], 6)
        for status in (0,1,2,3,4,10,0xffffffff):
            self.assertEqual(self.engine.click(status)['packets'], [])

    def test_endless_type_sends_query_before_complete(self):
        result = self.engine.click(7,quest_type=10)
        self.assertEqual([p['id'] for p in result['packets']], [0x2c,0x2e])
        self.assertEqual(result['cachedStatusAfter'], 7)

    def test_reward_selection_serializes_original_id_and_ignores_invalid_indices(self):
        result = self.engine.click(9,reward_ids=(40001,40002),selected_reward=1)
        self.assertEqual(result['packets'][0]['fields']['selected_rewards'], [40002])
        self.assertTrue(result['packets'][0]['hex'].endswith('18c2b802'))
        for index in (-1,2,0x7fffffff):
            with self.subTest(index=index):
                result = self.engine.click(9,reward_ids=(40001,40002),selected_reward=index)
                self.assertNotIn('selected_rewards',result['packets'][0]['fields'])
        self.assertNotIn('selected_rewards',self.engine.click(9,selected_reward=0)['packets'][0]['fields'])

    def test_full_width_ids_are_not_python_or_transport_truncated(self):
        result = self.engine.click(6,guid=0xffffffffffffffff,quest_id=0xffffffff)
        self.assertEqual(result['packets'][0]['fields'],
                         {'guid':0xffffffffffffffff,'quest_id':0xffffffff})
        self.assertEqual(result['packets'][0]['hex'],
                         '08ffffffffffffffffff0110ffffffff0f')

    def test_bad_host_fixture_is_rejected_before_native_memory_changes(self):
        for kwargs in ({'status':-1},{'status':True},{'status':1.5},
                       {'guid':1<<64},{'quest_id':1<<32}, {'quest_type':-1},
                       {'argument_count':1<<32},{'argument_type':256},
                       {'selected_reward':1<<31},{'cached':1},
                       {'reward_ids':(1,-1)},{'reward_ids':'12'}):
            values = {'status':6,**kwargs}; cursor = self.engine.cursor
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.engine.click(**values)
            self.assertEqual(self.engine.cursor,cursor)

    def test_original_descriptor_preserves_required_fields_and_zone_enum(self):
        from tutorial_quest_request_probe import decoded_payload
        e = self.engine
        self.assertEqual(len(e.schema),26)
        zone = e.schema['C2GS_QuestZoneTrigger']
        self.assertEqual(zone['enums']['ZoneTrigger'],{'ENTER_ZONE':1,'EXIT_ZONE':2})
        self.assertEqual(zone['fields'][0]['defaultValue'],'ENTER_ZONE')
        self.assertEqual(e.schema_enums['QuestType']['ENDLESS_QUEST'],10)
        self.assertEqual(decoded_payload(e.schema,'C2GS_QuestQuery',b'\x08\x00'),{'guid':0})
        for name,raw in (('C2GS_QuestQuery',b'\x10\x01'),
                         ('C2GS_QuestComplete',b'\x08\x01'),
                         ('C2GS_QuestComplete',b'\x08\x01\x10\x01\x10\x02'),
                         ('C2GS_QuestQuery',b'\x08\x01\x10\x80\x80\x80\x80\x10')):
            with self.subTest(name=name,raw=raw.hex()), self.assertRaises(ValueError):
                decoded_payload(e.schema,name,raw)


if __name__ == '__main__':
    unittest.main()
