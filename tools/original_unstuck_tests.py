"""Bounded source-only BreakAway checks; private fixtures are explicit opt-in."""
import argparse
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from original_unstuck_probe import ROUTINES,UnstuckProbe
from tutorial_map_geometry import local_output

ARGS=None
class PublicChecks(unittest.TestCase):
    def test_pinned_native_scope(self):
        self.assertEqual(set(ROUTINES),{0x7197e4,0x719970,0x5a4540,0x7984d0,0x48b858})
        self.assertTrue(all(n>0 and len(h)==64 and int(h,16)>=0 for n,h in ROUTINES.values()))
    def test_private_output_boundary(self):
        with self.assertRaises(ValueError):local_output('docs/unstuck-source.svg')
        self.assertTrue(local_output('analysis/raw/original-unstuck-test').is_absolute())

class OriginalChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if ARGS.library is None:return
        from analyze_native_resources import NativeImage
        cls.image=NativeImage(ARGS.library.read_bytes());cls.e=UnstuckProbe(cls.image)
    def setUp(self):
        if ARGS.library is None:self.skipTest('Original native image is private; pass --library')
    def test_ordinary_has_no_confirmation_or_destination(self):
        for key,kind in((5,2),(6,0)):
            r=self.e.click(map_key=key,map_type=kind)
            self.assertEqual(r['confirmations'],[]);self.assertEqual(r['packets'],[{'opcode':644,'payloadHex':'','bytes':0,'transportExecuted':False}]);self.assertEqual(r['context6c'],1)
            self.assertFalse(r['destinationProduced'])
        self.assertEqual(self.e.click(map_key=5,map_type=2)['mapLookups'],[])
        r=self.e.click(map_key=6,map_type=2,map_found=False);self.assertEqual(r['confirmations'],[]);self.assertEqual(r['packets'][0]['opcode'],644)
    def test_original_dungeon_confirmation(self):
        r=self.e.click(map_key=6,map_type=2)
        self.assertEqual(r['packets'],[]);self.assertEqual(r['context6c'],0)
        self.assertEqual(r['confirmations'],[{'textId':2207,'constructorFlag':1,'callback':'0x7984d0','secondaryTextId':237}])
        self.assertEqual(len(self.e.confirm(0)['packets']),1);self.assertEqual(self.e.confirm(1)['packets'],[])
    def test_transport_gates_and_validation(self):
        for args in({'connected':False},{'suppressed':True}):
            r=self.e.click(**args);self.assertEqual(r['packets'],[]);self.assertEqual(r['context6c'],1)
        with self.assertRaises(ValueError):self.e.click(connected='yes')
    def test_original_timer_arithmetic_and_missing_key(self):
        r=self.e.timer(now=100000,saved=None);self.assertEqual(r['asReturn'],0)
        self.assertEqual(r['keyValueBoundary'][-1],{'write':'break_away','value':'98200'})
        for saved,want in((100000,30),(99999,29),(99940,29),(98200,0),(98199,0)):
            r=self.e.timer(now=100000,saved=saved);self.assertEqual(r['asReturn'],want)
            self.assertFalse(any('write'in x for x in r['keyValueBoundary']))
    def test_deferred_original_map_path_time_writer(self):
        a=self.e.map_path_time(False);b=self.e.map_path_time(True)
        self.assertEqual(a['keyValueBoundary'],[]);self.assertEqual(b['keyValueBoundary'],[{'write':'break_away','value':'100000'}]);self.assertEqual(b['context6cAfter'],0)
    def test_source_drawings_and_manifest(self):
        if ARGS.candidate is None:self.skipTest('Original UI candidate is private; pass --candidate')
        from xml.etree import ElementTree as ET
        files=json.loads((ARGS.candidate/'files.json').read_text())
        for row in files:
            raw=(ARGS.candidate/row['path']).read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256']);self.assertEqual(len(raw),row['bytes'])
        svgs=list(ARGS.candidate.glob('*.svg'));self.assertEqual(len(svgs),6)
        for p in svgs:ET.parse(p)
    def test_original_navigation_text_and_measurement_boundary(self):
        if ARGS.candidate is None:self.skipTest('Original UI candidate is private; pass --candidate')
        j=json.loads((ARGS.candidate/'unstuck-ui.json').read_text())
        self.assertEqual(j['strings']['GENERAL_SET_INFO_BTN_BREAK']['text'],'脱离卡死')
        self.assertFalse(j['layoutBoundary']['finalChineseFlashTextHeightKnown'])
        self.assertEqual(j['sourceTabs']['informationIndex'],3);self.assertFalse(j['sourceTabs']['textLabelPresentInOnItemSet'])
        s=j['fields']['ui/Flash/SettingInfo.swf:m_HelpPanel.mc_content.m_BreakAway._Detail']['textStyle']
        self.assertEqual(s['fontHeight'],22);self.assertTrue(s['wordWrap']);self.assertTrue(s['multiline']);self.assertEqual(s['colorRGBA'],[255]*4)
        self.assertEqual(j['gearBounds']['componentGraphicPixelsWithoutNotification'],[10,6,50,46])

if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--library',type=Path);cli.add_argument('--candidate',type=Path);ARGS,remaining=cli.parse_known_args();unittest.main(argv=[__file__,*remaining])
