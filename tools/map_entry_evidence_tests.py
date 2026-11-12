"""Entry-height provenance, loading gates and multi-level original CPU checks."""
import json
import unittest
from pathlib import Path
from map_entry_evidence import descriptor_wire

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'analysis/raw/map-entry-floor-20261113'
RUN=ROOT/'analysis/raw/showcase-20261110/running-preview'

class DescriptorBounds(unittest.TestCase):
    def test_descriptor_rejects_truncation_groups_and_zero_field(self):
        for data in (b'\x80',b'\x0a\x04ab',b'\x00\x01',b'\x0b',b'\x80'*11):
            with self.subTest(data=data),self.assertRaises(ValueError):descriptor_wire(data)

    def test_descriptor_retains_repeated_messages_in_original_order(self):
        self.assertEqual(descriptor_wire(b'\x22\x01a\x22\x01b'),[(4,b'a'),(4,b'b')])

@unittest.skipUnless((RAW/'entry-audit.json').is_file(),'Original APK/map inputs and native evidence stay local')
class Original(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from map_entry_evidence import probe_runtime
        cls.report=probe_runtime(RUN)

    def test_original_setter_center_initial_support_and_sources_replay(self):
        self.assertEqual(self.report,json.loads((RAW/'entry-audit.json').read_text()))
        for case in self.report['cases']:
            e=case['entry']
            self.assertEqual(e['suppliedPosition'],e['currentPosition'])
            self.assertEqual(e['suppliedPosition'],e['pendingPosition'])
            self.assertEqual(e['suppliedPosition'],e['loadingCenter'])
            self.assertEqual(e['mapReloadFlag'],1)

    def test_same_xz_keeps_distinct_support_levels_and_does_not_select_highest(self):
        cases=self.report['cases']
        self.assertEqual([c['support']['pendingPosition'][1]for c in cases[:4]],
                         [132.34999084472656,132.34999084472656,172.3668975830078,172.3668975830078])
        for c in cases[:4]:self.assertTrue(c['support']['supportCached'])

    def test_inactive_stage_does_not_snap_and_explicit_pending_branch_retains_height(self):
        for c in self.report['cases'][4:6]:
            self.assertFalse(c['support']['supportCached'])
            self.assertEqual(c['entry']['pendingPosition'],c['support']['pendingPosition'])
        c=self.report['cases'][6]
        self.assertEqual(c['support']['pendingPosition'][1],196)
        self.assertEqual(c['support']['cachedSupport'],172.3668975830078)

    def test_original_entry_payload_identity_and_missing_map5_spawn_are_not_guessed(self):
        p=self.report['protocol'];s=self.report['sourceEntries']
        self.assertEqual(p['descriptorIndex'],14)
        self.assertEqual(p['messages'][1]['name'],'GS2C_EnterMap')
        self.assertEqual(p['messages'][1]['messageTypes']['location'],'.pb.GS2C_ObjectLocation')
        self.assertEqual(p['messages'][0]['messageTypes']['position'],'.pb.CxGS_Vec3')
        self.assertEqual(s['tutorialPlayerSpawnRows'],0)
        self.assertEqual(s['additionalTables']['area_trigger']['triggerIDs'],[399])
        self.assertFalse(p['actualServerPayloadAvailable'])
        self.assertFalse(s['triggerIsAnEntryPosition'])
        self.assertFalse(self.report['actualOriginalEntryKnown'])
        self.assertFalse(self.report['gameplayChanged'])

if __name__=='__main__':unittest.main()
