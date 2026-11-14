"""Pinned source attribute parsing/writing with explicit protocol fixtures."""
import copy
import unittest
from pathlib import Path

from character_attribute_updates import CharacterAttributeProbe,FIELDS,audit_level_message,full_fixture,int32,source_attribute_view,update_fixture,varint

ROOT=Path(__file__).resolve().parents[1]
LIBRARY=ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'
GUID=0x120a00000001


class AttributeBoundaryTests(unittest.TestCase):
    def test_source_projection_does_not_convert_local_total_xp_or_invent_unknowns(self):
        self.assertFalse(source_attribute_view()['known'])
        self.assertTrue(all(v is None for v in source_attribute_view()['fields'].values()))
        snapshot={77:3,138:150,139:7455,145:2};before=copy.deepcopy(snapshot)
        view=source_attribute_view(snapshot)
        self.assertEqual(view['fields'],{'level':3,'profession':None,'xp':150,'upgradeXp':7455,'skillPoints':2})
        self.assertEqual(snapshot,before)
        for local in ({'level':3,'xp':150},{77:True},{138:1<<31},[77,138]):
            with self.assertRaises(ValueError):source_attribute_view(local)

    def test_fixture_scalar_ranges_and_mask_input_refuse_invalid_data(self):
        self.assertEqual(int32(-1),b'\xff'*9+b'\x01')
        self.assertEqual(varint(0x80000000),b'\x80\x80\x80\x80\x08')
        for value in (-1,True,1<<64,'1'):
            with self.assertRaises(ValueError):varint(value)
        for changes in ({-1:1},{512:1},{True:1},{'77':1},{77:1<<31}):
            with self.assertRaises(ValueError):update_fixture(GUID,changes)
        for values in ([0]*513,[True],{'77':1}):
            with self.assertRaises(ValueError):full_fixture(GUID,values)

    def test_explicit_empty_and_bit_count_are_preserved_without_source_inference(self):
        # Empty nested message still has its required bit_count=0; it does not
        # mean the actor's level/xp should be zeroed.
        self.assertEqual(update_fixture(1,{}).hex(),'080112020800')
        self.assertNotEqual(update_fixture(GUID,{138:1},bit_count=1),
                            update_fixture(GUID,{138:1},bit_count=5))
        self.assertEqual(full_fixture(1,[]).hex(),'08012a00')


@unittest.skipUnless(LIBRARY.exists(),'Original ARM64 library stays local')
class OriginalAttributeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.image=NativeImage(LIBRARY.read_bytes());cls.probe=CharacterAttributeProbe(cls.image)

    def test_original_parse_mask_indices_and_integer_getter_chain(self):
        changes={77:2,138:17,139:4802,145:1}
        result=self.probe.receive(update_fixture(GUID,changes))
        self.assertTrue(result['parserSucceeded']);self.assertTrue(result['coreReached'])
        self.assertEqual(result['after'],{'level':2,'profession':2,'xp':17,'upgradeXp':4802,'skillPoints':1})
        self.assertEqual(result['sourceWrites'],[{'index':i,'rawValue':changes[i]}for i in sorted(changes)])
        self.assertEqual(result['sourceXPDisplay'],{'level':2,'xp':17,'upgradeXp':4802})
        self.assertEqual(result['coreFlagsBeforePresentation'],{
            'levelChanged':True,'skillPointsChanged':True,'gaugesDirtyRequested':True})

    def test_original_full_values_are_sequential_and_zero_type_comes_from_guid(self):
        values=[0]*146;values[0]=777777;values[77]=3;values[127]=2;values[138]=150;values[139]=12345;values[145]=7
        result=self.probe.receive(full_fixture(GUID,values),kind='full')
        self.assertTrue(result['parserSucceeded']);self.assertTrue(result['coreReached'])
        self.assertEqual(result['actorTypeField'],0x120a)
        self.assertNotIn(0,[r['index']for r in result['sourceWrites']])
        self.assertEqual(result['after'],{'level':3,'profession':2,'xp':150,'upgradeXp':12345,'skillPoints':7})
        self.assertEqual(result['sourceXPDisplay'],{'level':3,'xp':150,'upgradeXp':12345})
        self.assertFalse(result['fullActorFactoryExecuted'])

    def test_original_incoming_xp_does_not_locally_change_level_or_threshold(self):
        result=self.probe.receive(update_fixture(GUID,{138:99999}))
        self.assertEqual(result['after']['level'],1)
        self.assertEqual(result['after']['xp'],99999)
        self.assertEqual(result['after']['upgradeXp'],2403)
        self.assertFalse(result['coreFlagsBeforePresentation']['levelChanged'])
        changed=self.probe.receive(update_fixture(GUID,{139:12345}))
        self.assertEqual(changed['sourceXPDisplay'],{'xp':0,'upgradeXp':12345,'level':1})
        at55=self.probe.receive(update_fixture(GUID,{77:55,138:123,139:4567}))
        self.assertEqual(at55['after']['xp'],123)
        self.assertEqual(at55['sourceXPDisplay'],{'xp':4567,'upgradeXp':4567,'level':55})

    def test_original_guid_filter_bit_count_zero_and_equal_value(self):
        wrong=self.probe.receive(update_fixture(GUID+1,{138:99}))
        self.assertTrue(wrong['parserSucceeded']);self.assertFalse(wrong['coreReached'])
        self.assertEqual(wrong['after'],wrong['before']);self.assertEqual(wrong['sourceWrites'],[])
        for bit_count in (0,1,4):
            result=self.probe.receive(update_fixture(GUID,{138:99},bit_count=bit_count))
            self.assertEqual(result['after']['xp'],0)
        result=self.probe.receive(update_fixture(GUID,{138:99},bit_count=5))
        self.assertEqual(result['after']['xp'],99)
        same=self.probe.receive(update_fixture(GUID,{138:0,139:2403}))
        self.assertEqual(same['sourceWrites'],[])
        self.assertFalse(same['coreFlagsBeforePresentation']['levelChanged'])
        signed=self.probe.receive(update_fixture(GUID,{138:-1}))
        self.assertEqual(signed['after']['xp'],-1)
        self.assertEqual(signed['sourceXPDisplay']['xp'],-1)

    def test_original_protocols_and_bounded_level_notification_audit(self):
        schema=self.probe.schema
        self.assertEqual([r['name']for r in schema['GS2C_PlayerLevelUp']['fields']],['guid','level','skill_point'])
        self.assertNotIn('xp',[r['name']for r in schema['GS2C_PlayerLevelUp']['fields']])
        self.assertEqual([r['name']for r in schema['GS2C_ObjectValueUpdate']['fields']],['bit_count','bit_masks','values'])
        audit=audit_level_message(self.image)
        self.assertEqual(audit['directBranches'],[])
        self.assertTrue(audit['vtableAddressSequences'])
        self.assertTrue(all(int(r['fdeStart'],16)>=0x1b00000 for r in audit['vtableAddressSequences']))
        # This static negative result intentionally supplies no fabricated
        # message ID or assertion that an indirect runtime consumer is absent.
        self.assertIn('not established',audit['conclusion'])


if __name__=='__main__':unittest.main()
