"""Append-only package checks on tiny fixtures, plus optional read-only assets."""
import contextlib
import hashlib
import io
import json
import tarfile
import tempfile
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import unstuck_delivery as delivery

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'analysis/raw/character-position-restore-20261114/unstuck-package-tests'
sha=lambda raw:hashlib.sha256(raw).hexdigest()


class PackageFixtureTests(unittest.TestCase):
    def setUp(self):
        RAW.mkdir(parents=True,exist_ok=True);self.temp=tempfile.TemporaryDirectory(prefix='fixture-',dir=RAW);self.root=Path(self.temp.name)
        self.candidate=self.root/'candidate';self.candidate.mkdir();self.base=self.root/'base.tar.gz'
        self.svg=b'<svg xmlns="http://www.w3.org/2000/svg"><image href="icon.png"/><path d="M0 0L1 1"/></svg>'
        self.png=b'\x89PNG\r\n\x1a\nexplicit-byte-fixture'
        (self.candidate/'setting.svg').write_bytes(self.svg);(self.candidate/'icon.png').write_bytes(self.png)
        self.disabled=self.root/'disabled.svg';self.disabled_bytes=b'<svg xmlns="http://www.w3.org/2000/svg"><path fill="black" opacity="0.30078125" d="M0 0L1 1"/></svg>';self.disabled.write_bytes(self.disabled_bytes)
        self.profile={'format':'oc2-original-unstuck-ui-v1','sourceStage':[1136,640],
            'drawings':{'settings-background':{'file':'setting.svg','viewBox':[0,0,880,560]}},
            'assets':{'ui/icons/userinterface/option_info.png':{'file':'icon.png'}},'strings':{},
            'fields':{'fixture':{'textStyle':{'initialHTML':'private authoring text','variable':'private-variable','fontHeight':22,'boundsPixels':[0,10,0,20]}}},
            'sourceTabs':{'order':['Setting','LanguageSetting','SettingScreen','SettingInfo']},'gearBounds':{},'layoutBoundary':{'finalChineseFlashTextHeightKnown':False},'windowPositionEquations':{},
            'methods':{'private':{'instructions':['not-for-runtime']}},'configs':['private'],'igmInitializer':['private'],'sourceProofs':{'native':'private'},'warnings':['private'],'limits':['private']}
        self.font=b'explicit-font-parser-boundary-fixture'
        self.write_profile();self.old={'runtime/entry.js':b'// explicit synthetic reviewed code\n','game-data/converted/previous.bin':b'\x00\xffold-bytes','game-data/converted/ui/chineseDisplay.woff':self.font};self.write_base()

    def tearDown(self):self.temp.cleanup()

    def write_profile(self):
        (self.candidate/'unstuck-ui.json').write_text(json.dumps(self.profile)+'\n')
        (self.candidate/'files.json').write_text(json.dumps([{'path':n,'sha256':sha(raw),'bytes':len(raw)}for n,raw in [('setting.svg',self.svg),('icon.png',self.png)]]))

    def write_base(self):
        self.manifest={'files':{name:{'sha256':sha(raw),'bytes':len(raw)}for name,raw in self.old.items()},'runtimeIdentity':{'files':{'runtime/entry.js':sha(self.old['runtime/entry.js'])}}}
        with tarfile.open(self.base,'w:gz')as archive:
            for name,raw in {**self.old,'bundle-manifest.json':json.dumps(self.manifest).encode()}.items():
                member=tarfile.TarInfo(name);member.mode=0o600;member.size=len(raw);archive.addfile(member,io.BytesIO(raw))

    @contextlib.contextmanager
    def configured(self):
        real_payload=delivery.payload
        fake_parent=types.ModuleType('fontTools');fake_parser=types.ModuleType('fontTools.ttLib')
        def font_fixture(stream):
            self.assertEqual(stream.read(),self.font)
            return {'head':types.SimpleNamespace(unitsPerEm=1000),'hhea':types.SimpleNamespace(ascent=1100,descent=-275,lineGap=0)}
        fake_parser.TTFont=font_fixture;fake_parent.ttLib=fake_parser
        with patch.dict(sys.modules,{'fontTools':fake_parent,'fontTools.ttLib':fake_parser}),patch.object(delivery,'BASE',self.base),patch.object(delivery,'BASE_SHA',delivery.file_sha(self.base)),patch.object(delivery,'DISABLED',self.disabled),patch.object(delivery,'DISABLED_SHA',sha(self.disabled_bytes)),patch.object(delivery,'PROFILE_SHA',sha((self.candidate/'unstuck-ui.json').read_bytes())),patch.object(delivery,'payload',lambda:real_payload(self.candidate)):
            yield real_payload

    def test_compact_metadata_strips_full_research_methods_and_text_authoring_fields(self):
        with self.configured()as payload:files=payload(self.candidate)
        profile=json.loads(files[delivery.PREFIX+'unstuck.json'])
        for name in ['methods','configs','igmInitializer','sourceProofs','warnings','limits']:self.assertNotIn(name,profile)
        self.assertEqual(profile['fields']['fixture']['textStyle'],{'fontHeight':22,'boundsPixels':[0,10,0,20]})
        self.assertFalse(profile['webBoundary']['originalFirstSpawn']);self.assertFalse(profile['webBoundary']['serverMovementCombatPolicyRecovered'])
        self.assertEqual(profile['browserFontMetrics']['Alegreya']['fontSHA256'],sha(self.font))
        self.assertEqual(profile['browserFontMetrics']['Alegreya']['family'],'EntryDisplay')

    def test_only_svg_bitmap_href_is_rebased_and_bitmap_bytes_remain_identical(self):
        before={p.name:sha(p.read_bytes())for p in self.candidate.iterdir()}
        with self.configured()as payload:files=payload(self.candidate)
        self.assertEqual(files[delivery.PREFIX+'icon.png'],self.png)
        self.assertEqual(files[delivery.PREFIX+'setting.svg'],self.svg.replace(b'href="icon.png"',b'href="/assets/source-unstuck/icon.png"'))
        self.assertEqual({p.name:sha(p.read_bytes())for p in self.candidate.iterdir()},before)

    def test_disabled_layer_is_the_only_extra_drawing_and_keeps_its_independent_digest(self):
        with self.configured()as payload:
            files=payload(self.candidate);metadata=json.loads(files[delivery.PREFIX+'unstuck.json'])
            self.assertEqual(set(files),{delivery.PREFIX+n for n in ['icon.png','setting.svg','source-unstuck-disabled.svg','unstuck.json']})
            self.assertEqual(files[delivery.PREFIX+'source-unstuck-disabled.svg'],self.disabled_bytes)
            self.assertEqual(set(metadata['drawings']),{'settings-background','breakaway-disabled'})
            self.assertEqual(metadata['drawings']['breakaway-disabled']['viewBox'],[-10,-15,300,130])
            self.assertNotIn('breakaway-disabled',json.loads((self.candidate/'unstuck-ui.json').read_text())['drawings'])
            self.disabled.write_bytes(self.disabled_bytes+b'tamper')
            with self.assertRaisesRegex(ValueError,'disabled drawing differs'):payload(self.candidate)

    def test_package_preserves_every_old_member_and_appends_manifest_entries(self):
        original=self.base.read_bytes();output=self.root/'appended.tar.gz'
        with self.configured():receipt=delivery.package(output)
        self.assertEqual(self.base.read_bytes(),original);self.assertEqual(receipt['originalPayloadsPreserved'],3);self.assertEqual(receipt['addedPayloads'],4);self.assertEqual(receipt['files'],7);self.assertFalse(receipt['localSavesImported'])
        with tarfile.open(output,'r:gz')as archive:
            for name,raw in self.old.items():self.assertEqual(archive.extractfile(name).read(),raw)
            manifest=json.load(archive.extractfile('bundle-manifest.json'));self.assertEqual(manifest['runtimeIdentity'],self.manifest['runtimeIdentity'])
            for name,row in self.manifest['files'].items():self.assertEqual(manifest['files'][name],row)
            self.assertTrue(all(name in self.old or name=='bundle-manifest.json'or name.startswith(delivery.PREFIX)for name in archive.getnames()))

    def test_collision_and_existing_outputs_fail_without_overwriting_any_payload(self):
        self.old[delivery.PREFIX+'setting.svg']=b'previous member';self.write_base();original=self.base.read_bytes();output=self.root/'collision.tar.gz'
        with self.configured():
            with self.assertRaisesRegex(ValueError,'replace'):delivery.package(output)
        self.assertFalse(output.exists());self.assertEqual(self.base.read_bytes(),original)
        output.write_bytes(b'preserve output')
        with self.configured():
            with self.assertRaisesRegex(ValueError,'Preserve'):delivery.package(output)
        self.assertEqual(output.read_bytes(),b'preserve output')

    def test_identity_guards_refuse_modified_source_or_assets(self):
        with self.configured():
            with patch.object(delivery,'BASE_SHA','0'*64):
                with self.assertRaisesRegex(ValueError,'runtime identity'):delivery.package(self.root/'bad-base.tar.gz')
            with patch.object(delivery,'PROFILE_SHA','0'*64):
                with self.assertRaisesRegex(ValueError,'profile identity'):delivery.payload()
            (self.candidate/'icon.png').write_bytes(self.png+b'tamper')
            with self.assertRaisesRegex(ValueError,'component differs'):delivery.payload()

    def test_outputs_and_members_cannot_escape_the_private_append_scope(self):
        with self.assertRaises(ValueError):delivery.private(ROOT/'docs/not-an-artifact.tar.gz')
        self.profile['drawings']['settings-background']['file']='../setting.svg';self.write_profile()
        with self.configured():
            with self.assertRaisesRegex(ValueError,'Unsafe'):delivery.payload()


@unittest.skipUnless((delivery.CANDIDATE/'unstuck-ui.json').is_file()and delivery.DISABLED.is_file(),'Original UI inputs remain private')
class OriginalPayloadReadOnlyTests(unittest.TestCase):
    def test_actual_original_assets_and_metadata_are_bounded_runtime_inputs(self):
        candidate=delivery.CANDIDATE;profile=json.loads((candidate/'unstuck-ui.json').read_text());names={r['file']for r in profile['drawings'].values()}|{r['file']for r in profile['assets'].values()}
        before={name:sha((candidate/name).read_bytes())for name in names|{'unstuck-ui.json','files.json'}}
        files=delivery.payload(candidate);metadata=json.loads(files[delivery.PREFIX+'unstuck.json'])
        for name in ['methods','configs','igmInitializer','sourceProofs','warnings','limits']:self.assertNotIn(name,metadata)
        for row in metadata['fields'].values():
            if row.get('textStyle'):
                self.assertNotIn('initialHTML',row['textStyle']);self.assertNotIn('variable',row['textStyle'])
        for name in names:
            raw=(candidate/name).read_bytes();expected=raw
            if name.endswith('.svg'):
                text=raw.decode()
                for image in profile['assets'].values():text=text.replace('href="'+image['file']+'"','href="/assets/source-unstuck/'+image['file']+'"')
                expected=text.encode()
            self.assertEqual(files[delivery.PREFIX+name],expected)
        self.assertEqual({name:sha((candidate/name).read_bytes())for name in before},before)
        self.assertTrue(all(n.startswith(delivery.PREFIX)and Path(n).suffix in ['.svg','.png','.json']for n in files))
        self.assertEqual(len(files),14)
        self.assertEqual(set(files),{delivery.PREFIX+n for n in names|{'unstuck.json','source-unstuck-disabled.svg'}})
        self.assertEqual(files[delivery.PREFIX+'source-unstuck-disabled.svg'],delivery.DISABLED.read_bytes())
        self.assertEqual(sha(files[delivery.PREFIX+'source-unstuck-disabled.svg']),delivery.DISABLED_SHA)
        from xml.etree import ElementTree as ET
        disabled=ET.fromstring(files[delivery.PREFIX+'source-unstuck-disabled.svg'])
        layer=next(n for n in disabled.iter()if n.get('data-source-path')=='_GroupBtn._Disable')
        self.assertEqual(layer.get('opacity'),str(77/256));self.assertEqual(layer.get('transform'),'matrix(1.073272705078125 0 0 0.9881744384765625 40 263)')
        self.assertTrue(any(n.get('fill')=='black'for n in layer.iter()))
        self.assertEqual(metadata['browserLayout']['sourceMapID'],5);self.assertEqual(metadata['browserLayout']['sourceMapType'],2);self.assertEqual(metadata['browserLayout']['battleFieldType'],4)
        from fontTools.ttLib import TTFont
        with tarfile.open(delivery.BASE,'r:gz')as archive:font_bytes=archive.extractfile('game-data/converted/ui/chineseDisplay.woff').read()
        font=TTFont(io.BytesIO(font_bytes));metric=metadata['browserFontMetrics']['Alegreya']
        self.assertEqual(metric['fontSHA256'],sha(font_bytes));self.assertEqual(metric['unitsPerEm'],font['head'].unitsPerEm)
        self.assertEqual((metric['ascent'],metric['descent'],metric['lineGap']),(font['hhea'].ascent,font['hhea'].descent,font['hhea'].lineGap))
        advance=22*(metric['ascent']-metric['descent']+metric['lineGap'])/metric['unitsPerEm']
        self.assertEqual(advance,30.25);self.assertEqual(advance-6,24.25)
        self.assertIn('browser adaptation',metric['boundary'])

    def test_real_base_is_pinned_and_keeps_reviewed_127_identities(self):
        if not delivery.BASE.is_file():self.skipTest('Append base archive remains private')
        self.assertEqual(delivery.file_sha(delivery.BASE),delivery.BASE_SHA)
        with tarfile.open(delivery.BASE,'r:gz')as archive:manifest=json.load(archive.extractfile('bundle-manifest.json'))
        self.assertEqual(len(manifest['runtimeIdentity']['files']),127)
        self.assertFalse(set(delivery.payload())&set(manifest['files']))


if __name__=='__main__':unittest.main()
