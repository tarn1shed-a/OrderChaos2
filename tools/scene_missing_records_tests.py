"""Original empty records, cold texture order, preservation and replay checks."""
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from tutorial_map_geometry import ROOT
from scene_missing_records import export, IDS, DEFAULT_SHA

RAW=ROOT/'analysis/raw/map-record-gaps-20261112'
RUN=ROOT/'analysis/raw/showcase-20261110/running-preview'
EXP=RAW/'export'
NATIVE=ROOT/'analysis/raw/beff-native/library.so'


class Public(unittest.TestCase):
    def test_browser_adapter_syntax_and_unrelated_policy_refused(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node unavailable')
        p=ROOT/'tools/preview/source-missing-records.js'
        r=subprocess.run([node,'--check',str(p)],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
        code="import{validateMissingRecords as v}from '"+p.as_uri()+"';import assert from 'node:assert/strict';for(const p of [null,{}, {format:'other'}, {format:'oc2-source-missing-records-v1',slot:1}])assert.throws(()=>v(p));"
        subprocess.run([node,'--input-type=module','-e',code],check=True,capture_output=True)

    def test_source_native_dependencies_are_not_imported_for_public_reader(self):
        # Exporting needs native inputs; importing the public reader does not.
        import sys
        code="import sys;sys.path.insert(0,sys.argv[1]);import scene_missing_records;assert not {'unicorn','capstone','elftools'}&set(sys.modules)"
        r=subprocess.run([sys.executable,'-c',code,str(ROOT/'tools')],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)


@unittest.skipUnless(NATIVE.is_file() and (EXP/'policy.json').is_file(),'Original archives/native bytes stay local')
class Original(unittest.TestCase):
    def probe(self):
        from analyze_native_resources import NativeImage
        from native_missing_records import MissingRecordProbe
        return MissingRecordProbe(NativeImage(NATIVE.read_bytes()))

    def test_original_mount_order_is_first_present_update_not_largest_suffix(self):
        p=self.probe();packs=['res_t.bin',*[f'res_t_upd{i}.bin'for i in range(10,16)]]
        for containing,winner in [(['res_t.bin','res_t_upd10.bin'],'res_t_upd10.bin'),
                                  (['res_t.bin','res_t_upd15.bin'],'res_t_upd15.bin'),(['res_t.bin'],'res_t.bin')]:
            r=p.fresh_archives(packs,containing)
            self.assertEqual(r['order'],packs[1:]+packs[:1]);self.assertEqual(r['selected'],winner)
            self.assertEqual(r['attempts'],r['order'][:r['order'].index(winner)+1])
        r=p.fresh_archives(['res_t.bin','res_t_upd15.bin'],['res_t.bin'])
        self.assertEqual(r['order'],['res_t_upd15.bin','res_t.bin'])

    def test_seven_actual_source_lookups_return_empty_and_skip_replacement(self):
        from map_loading_evidence import Sources
        from resource_packs import DEFAULT_SOURCE
        s=Sources(DEFAULT_SOURCE);p=self.probe();policy=json.loads((EXP/'policy.json').read_text())
        for row in policy['instances']:
            r=p.no_record(s.read(row['recordPath']),row['id'])
            self.assertEqual(r['recordCount'],0);self.assertTrue(r['freshVectorsUnchanged']);self.assertTrue(r['noAtlasReplacement'])
            self.assertFalse(row['otherSlotApplied']);self.assertGreater(row['otherSlotRecords'],0)

    def test_selected_original_image_is_gray_130_not_white_or_base_200(self):
        from resource_packs import DEFAULT_SOURCE,read_entry
        from map_loading_evidence import Sources
        from texture_decode import decode
        from PIL import Image
        candidates=Sources(DEFAULT_SOURCE).candidates('texture/lightmap.tga');values={}
        for row in candidates:
            im=decode(read_entry(row,DEFAULT_SOURCE));values[row['pack']]=im.getpixel((0,0))
        self.assertEqual(values,{'res_t.bin':(200,200,200,255),'res_t_upd10.bin':(130,130,130,255)})
        im=Image.open(EXP/(DEFAULT_SHA+'.png')).convert('RGBA')
        self.assertEqual(im.getextrema(),((130,130),(130,130),(130,130),(255,255)))

    def test_all_existing_templates_and_lighting_preserved_only_seven_trs_added(self):
        old=json.loads((RUN/'game-data/converted/source-map-palette/manifest.json').read_text());new=json.loads((EXP/'manifest.json').read_text())
        self.assertEqual(new['sceneBakedLighting'],old['sceneBakedLighting']);self.assertEqual(new['textures'],old['textures'])
        self.assertEqual(len(new['scenery']),158);added=[]
        for a,b in zip(old['scenery'],new['scenery']):
            self.assertEqual({k:v for k,v in a.items()if k!='instances'},{k:v for k,v in b.items()if k!='instances'})
            self.assertEqual(b['instances'][:len(a['instances'])],a['instances']);added.extend(b['instances'][len(a['instances']):])
        self.assertEqual({r['id']for r in added},IDS);self.assertEqual(len(added),7)
        self.assertEqual(sum(len(r['instances'])for r in new['scenery']),1258)
        self.assertEqual(json.loads((EXP/'selection.json').read_text())['preview']['omitted'],[])
        for name,digest in json.loads((RAW/'before-assets.json').read_text()).items():
            self.assertEqual(hashlib.sha256((RUN/'game-data/converted'/name).read_bytes()).hexdigest(),digest,name)

    def test_rebuild_is_byte_identical(self):
        with tempfile.TemporaryDirectory(dir=RAW)as t:
            export(RUN,Path(t))
            self.assertEqual({p.name:p.read_bytes()for p in EXP.iterdir()},{p.name:p.read_bytes()for p in Path(t).iterdir()})

    def test_connector_replay_and_repeat_refusal(self):
        from connect_missing_records import connect
        with tempfile.TemporaryDirectory(dir=RAW)as t:
            p=Path(t);pub=p/'prototype/public';pub.mkdir(parents=True);(p/'game-data/converted').mkdir(parents=True)
            for n in ('explore-map.js','explore-map.html'):shutil.copyfile(RAW/('before-'+n),pub/n)
            self.assertEqual(connect(p,EXP)['files'],8)
            contents={str(f.relative_to(p)):f.read_bytes()for f in p.rglob('*')if f.is_file()}
            for n,b in contents.items():self.assertEqual((RUN/n).read_bytes(),b)
            with self.assertRaises(ValueError):connect(p,EXP)
            self.assertEqual(contents,{str(f.relative_to(p)):f.read_bytes()for f in p.rglob('*')if f.is_file()})


if __name__=='__main__':unittest.main()
