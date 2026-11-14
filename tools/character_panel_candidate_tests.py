"""Pinned source drawings and negative read-only panel input checks.

No accounts, character saves or game servers are read. Browser checks are
separate; the JavaScript cases below exercise explicit protocol-shaped fixtures.
"""
import argparse
import hashlib
import io
import json
import shutil
import subprocess
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image
from character_panel_candidate_assets import ROOT,SOURCE_PINS
from hud_assets import document,sprite_frames
from optimized_abc import parse_abc,extract_abc,named_method
from resource_packs import DEFAULT_SOURCE,ResourceArchive,index,normalize_resource_name

PUBLIC=None
NODE=shutil.which('node')or'/Users/kevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'


class CharacterPanelCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.public=Path(PUBLIC).resolve();cls.package=cls.public.parent
        cls.profile=json.loads((cls.public/'assets/character-source/panels.json').read_text())
        cls.archives={};cls.locations={}
        for row in index():cls.locations.setdefault(normalize_resource_name(row['path']),[]).append(row['pack'])

    @classmethod
    def read(cls,path):
        copies=[]
        for pack in cls.locations[normalize_resource_name(path)]:
            if pack not in cls.archives:cls.archives[pack]=ResourceArchive(DEFAULT_SOURCE/pack)
            copies.append(cls.archives[pack].read(path))
        if any(copy!=copies[0]for copy in copies):raise ValueError('Ambiguous source image')
        return copies[0]

    def test_generated_bytes_match_manifest_and_reviewed_interface(self):
        checks=json.loads((self.package/'SHA256.json').read_text())
        self.assertEqual(set(checks),{str(p.relative_to(self.public))for p in self.public.rglob('*')if p.is_file()})
        for path,digest in checks.items():
            with self.subTest(path=path):self.assertEqual(hashlib.sha256((self.public/path).read_bytes()).hexdigest(),digest)
        pinned=json.loads((ROOT/'tools/local_mvp_runtime.json').read_text())['files']
        self.assertEqual(checks['source-ui-svg.js'],pinned['prototype/public/source-ui-svg.js'])
        for path,digest in SOURCE_PINS.items():
            self.assertEqual(hashlib.sha256(self.read(path)).hexdigest(),digest)
            self.assertEqual(self.profile['sources'][path]['sha256'],digest)

    def test_all_profession_icons_remain_original_bytes_and_lock_crop_is_exact(self):
        assets=self.profile['assets'];self.assertFalse(any('sourceImage'in row for row in self.profile['drawingBoundaries']))
        for path,asset in assets.items():
            target=self.public/asset['url'].lstrip('/');raw=target.read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),asset['sha256'])
            if asset.get('mode')=='same-exported-symbol-lossless-source-crop':
                self.assertEqual(asset['sourceSymbol'],'itempanellocked')
                atlas=Image.open(io.BytesIO(self.read(asset['sourceAtlas'])));expected=atlas.crop(asset['sourceRect'])
                self.assertEqual(Image.open(io.BytesIO(raw)).tobytes(),expected.tobytes())
                self.assertEqual(expected.size,(40,40))
            else:self.assertEqual(raw,self.read(path))
        for profession,catalog in self.profile['catalogs'].items():
            self.assertEqual((sum(s['kind']=='active'for s in catalog),sum(s['kind']=='passive'for s in catalog)),(9,5))
            self.assertTrue(all(s['profession']==int(profession)for s in catalog))
            self.assertTrue(all('learned'not in r for s in catalog for r in s['runes']))
        self.assertEqual([self.profile['catalogs'][str(p)][0]['skillId']for p in range(1,6)],[24,90,190,243,256])
        self.assertEqual(self.profile['skillDisplayCounts']['active'],9);self.assertEqual(self.profile['skillDisplayCounts']['runes'],27)
        self.assertEqual(self.profile['methods']['SkillSetting.onShow']['codeSHA256'],'e530aaf7ac6f7b5e44c2bfb73473f2b7775d4ed59fd9fa263e92863482f81256')

    def test_experience_parent_selects_original_last_frame_before_child_scale(self):
        raw=self.read('ui/Flash/AttributePage.swf');doc=document(raw,'ui/Flash/AttributePage.swf')
        abc=parse_abc(extract_abc(raw));method=named_method(abc,'AttributePage','SetAttributeValueExp')
        self.assertEqual(method['codeSHA256'],'a1871ececb03835c5e621a9ae2f96dd9edb1056e3a5d7dc747fbc9c8f936ef4f')
        calls=[i for i in method['instructions']if 290<=i['at']<358]
        self.assertEqual([i['args']for i in calls if i['op']=='callpropvoid'],[['gotoAndStop',1],['setMcToPercent',2]])
        self.assertEqual((len(sprite_frames(doc,70)),len(sprite_frames(doc,69))),(60,1))
        path='.CharacterAttrPanel.CharacterPanel.mc_content.Exp.valueBar'
        svg=ET.parse(self.public/'assets/character-source/AttributePage.svg').getroot()
        parent=next(n for n in svg.iter()if n.get('data-source-path')==path)
        self.assertEqual(parent.get('data-source-id'),'70');self.assertEqual(parent.get('data-source-selected-frame'),'60')
        self.assertEqual(self.profile['sidebarRuntime']['height'],565)
        self.assertEqual(self.profile['methods']['WindowStack.init']['codeSHA256'],'b8ceb7a0baaee980e37260b448f5fcf40842ad4b6dabed16aa787b01eb79a621')

    def run_js(self,code):
        module=(ROOT/'tools/preview/character-source-state.mjs').as_uri()
        script='import assert from "node:assert/strict";import fs from "node:fs";import{sourcePanelValues,sourceProfessionSkills,sourceXPFrame}from '+json.dumps(module)+';\nconst profile=JSON.parse(fs.readFileSync('+json.dumps(str(self.public/'assets/character-source/panels.json'))+',"utf8"));\n'+code
        result=subprocess.run([NODE,'--input-type=module','-e',script],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_role_and_protocol_fields_never_convert_demo_xp_or_cross_role_state(self):
        self.run_js('''
const role=Object.freeze({id:'explicit-fixture',profession:2,level:3,xp:150,hp:113,maxHp:140,stats:Object.freeze({armor:8})});
const source={roleId:role.id,attributes:{77:55,127:2,138:123,139:4567,145:4},learning:[]};const before=JSON.stringify(source);
assert.equal(sourcePanelValues(role).xp,null);assert.equal(sourcePanelValues(role).level,3);
assert.deepEqual([sourcePanelValues(role,null,{value:30,max:60}).xp,sourcePanelValues(role,null,{value:30,max:60}).upgradeXp],[30,60]);
assert.equal(sourcePanelValues(role,source).xp,4567);assert.equal(source.attributes[138],123);
assert.equal(sourcePanelValues(role,{...source,roleId:'other'}).xp,null);
assert.equal(sourcePanelValues(role,{...source,attributes:{...source.attributes,127:1}}).skillPoints,null);
assert.equal(sourcePanelValues(role,{roleId:role.id,attributes:{138:123,139:4567}}).xp,null);
assert.deepEqual(sourceXPFrame(.5,1),{frame:1,scale:.5});assert.deepEqual(sourceXPFrame(0,1),{frame:1,scale:.02});
assert.equal(sourceXPFrame(4,1).scale,1);assert.throws(()=>sourceXPFrame(NaN,1));assert.equal(JSON.stringify(source),before);assert.equal(role.xp,150);
''')

    def test_static_catalog_is_never_learning_or_equipment_and_profession_mismatch_is_rejected(self):
        self.run_js('''
const before=JSON.stringify(profile);const rows=sourceProfessionSkills(profile,2);assert.equal(rows.length,14);
assert(rows.every(s=>s.runes.every(r=>r.learned===null&&r.locked===null)));
const base=rows[0],source={roleId:'fixture',attributes:{77:1,127:2},learning:[[base.skillId,2],[999999,0],[24,0]]};
const selected=sourceProfessionSkills(profile,2,source,'fixture').find(s=>s.skillId===base.skillId);
assert.deepEqual(selected.runes.map(r=>r.learned),[false,false,true,false]);
assert.equal(sourceProfessionSkills(profile,2,{...source,learning:[]},'fixture')[0].runes[0].learned,false);
assert.equal(sourceProfessionSkills(profile,2,{...source,attributes:{77:1,127:1}},'fixture')[0].runes[0].learned,null);
assert.equal(sourceProfessionSkills(profile,2,source,'other')[0].runes[0].locked,null);
assert.deepEqual(sourceProfessionSkills(profile,6),[]);assert.deepEqual(sourceProfessionSkills(profile,'2'),[]);
assert.throws(()=>sourceProfessionSkills(profile,2,{roleId:'fixture',learning:[[90,4]]},'fixture'));
assert(rows.every(s=>!('equipped'in s)));assert.equal(JSON.stringify(profile),before);
''')


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--public',type=Path,required=True)
    args,remaining=cli.parse_known_args();PUBLIC=args.public
    unittest.main(argv=[__file__,*remaining])
