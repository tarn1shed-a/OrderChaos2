"""Original BreakAway input checks; source-only fixtures remain private."""
import argparse
import unittest
from pathlib import Path
from original_unstuck_inputs_probe import PINS,DESCRIPTOR,UnstuckInputsProbe,source_map_type
from tutorial_map_geometry import local_output

ARGS=None
class PublicChecks(unittest.TestCase):
    def test_original_schema_pin_scope(self):
        self.assertEqual(DESCRIPTOR[:2],(0x2028b85,62));self.assertEqual(len(DESCRIPTOR[2]),64)
        self.assertEqual(PINS[0x58c7f8][0],2732);self.assertEqual(len(PINS[0x58c7f8][1]),64)
    def test_outputs_stay_private(self):
        with self.assertRaises(ValueError):local_output('docs/unstuck-original-error.json')
        self.assertTrue(local_output('analysis/raw/original-unstuck-inputs-test').is_absolute())

class NativeChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if ARGS.library is None:return
        from analyze_native_resources import NativeImage
        cls.e=UnstuckInputsProbe(NativeImage(ARGS.library.read_bytes()))
    def setUp(self):
        if ARGS.library is None:self.skipTest('Private original native sample; pass --library')
    def test_error_payload_parser_and_warning_dispatch(self):
        r=self.e.error(0xa023);self.assertEqual(r['actualOriginalParse'],[{'source':'0x1ab7060','bytes':4,'hex':'08a3c002'}]);self.assertEqual(r['sourceTextLookupStop'],[4780]);self.assertEqual((r['context63'],r['context68'],r['context6c']),(0,0xffffffff,0));self.assertFalse(r['movingOrCombatProducerSupplied'])
    def test_adjacent_error_preserves_pending_unstuck_flag(self):
        r=self.e.error(0xa022);self.assertEqual(r['sourceTextLookupStop'],[2034]);self.assertEqual(r['context6c'],1)
    def test_original_descriptor_field_names(self):
        self.assertEqual(self.e.schema['name'],'GS2C_Error')
        self.assertEqual([(x['name'],x['number'],x['type'])for x in self.e.schema['fields']],[('err_code',1,5),('req_lv',2,5),('str_id',3,5)])
    def test_map5_callback_emits_only_source_type(self):
        r=self.e.map_info(map_key=5,map_type=2);self.assertEqual(r['mapLookups'],[5]);self.assertEqual(r['originalASProperties'],[{'name':'mapType','type':2,'number':2.0}]);self.assertFalse(r['currentRuntimeStateRecovered'])
    def test_missing_map_does_not_get_a_default_type(self):
        r=self.e.map_info(map_key=5,map_type=2,found=False);self.assertEqual(r['originalASProperties'],[])
    def test_original_table_and_asdefines_agree(self):
        r=source_map_type(ARGS.source);self.assertEqual(r['sourceRow']['map_id'],5);self.assertEqual(r['sourceRow']['type'],2);self.assertEqual(r['sourceRow']['file'],'world/tutorial.wld');self.assertEqual(r['constants']['MAP_INFO_TYPE_BATTLE_FIELD'],4)
    def test_native_timer_threshold_future_and_input_validation(self):
        for key,want in((98201,0),(98200,0),(100001,30),(101800,30)):
            r=self.e.timer(now=100000,saved=key);self.assertEqual(r['asReturn'],want);self.assertEqual(len(r['keyValueBoundary']),1)
        with self.assertRaises(ValueError):self.e.error(True)
        with self.assertRaises(ValueError):self.e.map_info(map_key=5,map_type=2,found='yes')

if __name__=='__main__':
    from resource_packs import DEFAULT_SOURCE
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--library',type=Path);p.add_argument('--source',type=Path,default=DEFAULT_SOURCE);ARGS,rest=p.parse_known_args();unittest.main(argv=[__file__,*rest])
