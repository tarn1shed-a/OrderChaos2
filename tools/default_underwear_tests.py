"""Original empty underwear slots and bounded browser visibility recovery."""
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from tutorial_map_geometry import ROOT

RAW=ROOT/'analysis/raw/underwear-selection-20261113'
RUN=ROOT/'analysis/raw/showcase-20261110/running-preview'
NATIVE=ROOT/'analysis/raw/beff-native/library.so'
NODE=shutil.which('node')or str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node')

class Public(unittest.TestCase):
    def test_default_selection_keeps_body_and_refuses_to_remove_body_as_foundation(self):
        if not Path(NODE).is_file():self.skipTest('Node required')
        code="import assert from'node:assert/strict';import{sourceDefaultBaseMeshes,BODY_MODEL,BODY_SHA256}from'"+(ROOT/'tools/preview/source-default-underwear.js').as_uri()+"';"+r'''
const appearance={baseModelPath:BODY_MODEL,provenance:{sources:{[BODY_MODEL]:{sha256:BODY_SHA256}}},
 baseMeshIndices:Array.from({length:16},(_,i)=>i),bodyPartMeshIndices:Object.fromEntries(Array.from({length:14},(_,i)=>['part'+i,i])),
 foundationMeshIndices:[14,15],foundationPaths:['model/item/armor/8_underwear/oc2_elf_f_underwear_bra.bdae','model/item/armor/8_underwear/oc2_elf_f_underwear_briefs.bdae']};
const before=JSON.stringify(appearance);
assert.deepEqual(sourceDefaultBaseMeshes(appearance),Array.from({length:14},(_,i)=>i));
assert.equal(JSON.stringify(appearance),before);
for(const mutate of [a=>a.foundationMeshIndices=[7,15],a=>a.foundationMeshIndices=[14,14],a=>a.provenance.sources[BODY_MODEL].sha256='other',a=>a.foundationPaths.reverse(),a=>a.baseMeshIndices.push(20)]){
 const bad=structuredClone(appearance);mutate(bad);assert.throws(()=>sourceDefaultBaseMeshes(bad));
}
'''
        r=subprocess.run([NODE,'--input-type=module','-e',code],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)

    def test_connector_refuses_project_root(self):
        from connect_default_underwear import connect
        with self.assertRaises(ValueError):connect(ROOT)

@unittest.skipUnless(NATIVE.is_file()and(RAW/'before-character-equipment.js').is_file(),'Original clothing inputs stay local')
class Original(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        from native_default_underwear import NativeDefaultUnderwear
        cls.probe=NativeDefaultUnderwear(NativeImage(NATIVE.read_bytes()))

    def test_original_zero_stores_37_slot_loop_and_actual_clear_preserve_body(self):
        p=self.probe
        self.assertEqual(p.zero_stores()['attachmentSlotValues'],[0,0])
        calls=p.slot_loop()['calls'];self.assertEqual(len(calls),37)
        self.assertEqual(calls[7:9],[{'slot':7,'value':0},{'slot':8,'value':0}])
        self.assertEqual(p.clear_defaults()['bodyPartsPreserved'],14)
        result=p.clear_defaults(True);self.assertEqual(result['bodyPartsPreserved'],14)
        self.assertEqual(result['sceneRequests'],4)

    def test_original_two_counter_channels_and_removal_restore_body(self):
        self.assertTrue(self.probe.part_counters()['removeRestoresBody'])

    def test_original_texture_replacement_is_slot_scoped_and_empty_is_noop(self):
        from map_loading_evidence import Sources
        from resource_packs import DEFAULT_SOURCE
        source=Sources(DEFAULT_SOURCE);p=self.probe
        self.assertEqual(p.texture_override('')['requests'],[])
        for kind,(sampler,stem)in enumerate([('texture','oc2_elf_f_underwear_briefs_01_d'),('normalMap','oc2_elf_f_underwear_briefs_n'),('maskMap','oc2_elf_f_underwear_briefs_s')]):
            result=p.texture_override(stem,13,kind)
            request=result['requests'][0];self.assertEqual(request['sampler'],sampler)
            self.assertEqual(request['path'],'texture/'+stem+'.tga')
            self.assertTrue(source.read(request['path']))
            self.assertFalse(result['nativeSetterExecuted'])
        self.assertEqual(p.texture_override('oc2_elf_f_underwear_briefs_01_d',8,0,False)['requests'],[])

    def test_all_original_body_geometry_and_seven_sampler_images_are_preserved(self):
        from map_loading_evidence import Sources
        from resource_packs import DEFAULT_SOURCE
        from bdae_convert import BDAE
        from character_orientation import audit
        source=Sources(DEFAULT_SOURCE);path='model/npc/character/elf/female/oc2_elf_f_body_01.bdae'
        data=json.loads((RUN/'game-data/converted/source-layers/elf-female.json').read_text())
        with tempfile.TemporaryDirectory()as d:
            p=Path(d)/'body.bdae';p.write_bytes(source.read(path));original=BDAE(p).parse()
            self.assertEqual(len(original['meshes']),14)
            for i,mesh in enumerate(original['meshes']):
                for key in('positions','uvs','indices','normals'):
                    self.assertEqual(mesh.get(key),data['meshes'][i].get(key),(i,key))
        self.assertEqual(len(audit(RUN)['textures']),7)

    def test_browser_equipment_roundtrip_and_connector_are_exact(self):
        from connect_default_underwear import connect
        with tempfile.TemporaryDirectory(dir=RAW)as d:
            p=Path(d);public=p/'prototype/public';public.mkdir(parents=True)
            shutil.copyfile(RAW/'before-character-equipment.js',public/'character-equipment.js')
            self.assertEqual(connect(p)['files'],2)
            before={f.name:f.read_bytes()for f in public.iterdir()}
            for n,b in before.items():self.assertEqual(b,(RUN/'prototype/public'/n).read_bytes())
            with self.assertRaises(ValueError):connect(p)
            self.assertEqual(before,{f.name:f.read_bytes()for f in public.iterdir()})
        code="import assert from'node:assert/strict';import{readFile}from'node:fs/promises';import{validateEquipmentAppearance,applyEquipmentMeshes}from'"+(RUN/'prototype/public/character-equipment.js').as_uri()+"';const data=JSON.parse(await readFile(new URL('"+(RUN/'game-data/converted/source-layers/elf-female.json').as_uri()+"'),'utf8'));"+r'''
const ap=validateEquipmentAppearance(data),before=JSON.stringify(data),objects=data.meshes.map(()=>({visible:false}));
const bare=applyEquipmentMeshes(objects,ap,{});
assert.deepEqual(bare.visibleMeshIndices,[0,1,2,3,4,5,6,7,8,9,10,11,12,13,22]);
const dressed=applyEquipmentMeshes(objects,ap,{chest:'linenArmor',feet:'travelerBoots'});
for(const i of [19,20,21])assert(dressed.visibleMeshIndices.includes(i));
for(const i of [14,15])assert(!dressed.visibleMeshIndices.includes(i));
assert.deepEqual(applyEquipmentMeshes(objects,ap,{}),bare);
for(const hair of ['hair1','hair2','hair3']){
 const result=applyEquipmentMeshes(objects,ap,{}, {hair});
 const selected=new Set(ap.hair.styles[hair].meshIndices);
 for(const style of Object.values(ap.hair.styles))for(const i of style.meshIndices)
  assert.equal(result.visibleMeshIndices.includes(i),selected.has(i));
 for(const i of [14,15])assert(!result.visibleMeshIndices.includes(i));
}
assert.equal(JSON.stringify(data),before);
'''
        r=subprocess.run([NODE,'--input-type=module','-e',code],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)

    def test_all_original_assets_and_main_save_are_unchanged(self):
        for n,h in json.loads((RAW/'before-assets.json').read_text()).items():
            self.assertEqual(hashlib.sha256((RUN/'game-data/converted'/n).read_bytes()).hexdigest(),h,n)
        self.assertEqual((ROOT/'runtime/characters.json').read_bytes(),(RAW/'before-main-private.json').read_bytes())

if __name__=='__main__':unittest.main()
