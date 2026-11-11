"""Original CPU/browser equivalence and refusal checks for source flag motion."""
import hashlib,json,shutil,subprocess,tempfile,unittest
from pathlib import Path
from tutorial_map_geometry import ROOT
from scene_flag_motion import export,flag_geometry
from scene_flags_evidence import MODELS

RAW=ROOT/'analysis/raw/flag-motion-20261112';RUN=ROOT/'analysis/raw/showcase-20261110/running-preview'
NATIVE=ROOT/'analysis/raw/beff-native/library.so';EXP=RAW/'export'
NODE="import assert from'node:assert/strict';import{readFileSync}from'node:fs';const api=await import(process.argv[1]);"

class Public(unittest.TestCase):
    def node(self,body,*args):
        node=shutil.which('node')
        if not node:self.skipTest('Node unavailable')
        r=subprocess.run([node,'--input-type=module','-e',NODE+body,(ROOT/'tools/preview/flag-motion-math.js').as_uri(),*map(str,args)],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
    def test_no_missing_skin_or_loop_fallback(self):
        self.node("for(const x of[null,{}, {format:api.FLAG_FORMAT,normalizationApplied:true}])assert.throws(()=>api.validateFlag(x));")
    def test_clock_keeps_exact_end_and_rejects_invalid_delta(self):
        self.node("const c=api.createFlagClock();assert.equal(c.tick(4000),4000);assert.equal(c.tick(1),1);for(const n of[-1,NaN,Infinity])assert.throws(()=>c.tick(n));")
    def test_unknown_model_cannot_become_a_type3_identity_mesh(self):
        class Wrong:
            b=b''
        with self.assertRaisesRegex(ValueError,'Unverified'):flag_geometry(Wrong(),{})

@unittest.skipUnless(NATIVE.is_file()and(EXP/'audit.json').is_file(),'Original models, native image and local export stay local')
class Original(unittest.TestCase):
    node=Public.node
    def models(self):
        return[(EXP/(ids[0]+'.json'))for ids in MODELS.values()]
    def test_native_sampling_palette_and_weighted_vertices(self):
        self.node(r'''
for(const file of process.argv.slice(2)){
 const data=JSON.parse(readFileSync(file)),p=api.validateFlag(data.sourceFlagMotion);let maxPalette=0,maxVertex=0;
 for(const c of p.nativeCases){
  const actual=api.paletteAt(p,c.timeMs);maxPalette=Math.max(maxPalette,...actual.map((v,i)=>Math.abs(v-c.boneMatrices[i])));
  for(const ch of c.channels){const x=p.channels.find(v=>v.sourceIndex===ch.sourceIndex);assert.deepEqual(api.sourceSample(x,c.timeMs),ch.value);}
 }
 assert(maxPalette<3e-6,`${file} palette ${maxPalette}`);
 for(const c of p.nativeVertexCases){const actual=api.deform(p,data.meshes[0].positions,api.paletteAt(p,c.timeMs));maxVertex=Math.max(maxVertex,...actual.map((v,i)=>Math.abs(v-c.positions[i])));}
 assert(maxVertex<1e-5,`${file} vertex ${maxVertex}`);
 const clock=api.createFlagClock();for(const c of p.nativeTicks)assert.equal(clock.tick(c.dt),c.timeMs);
}
''',*self.models())
    def test_native_bone_lookup_and_literal_weights_are_not_rebased(self):
        from bdae_convert import BDAE
        from scene_flags_evidence import literal_nodes,controller_evidence
        for file,path in zip(self.models(),MODELS):
            data=json.loads(file.read_text());p=data['sourceFlagMotion'];b=BDAE(ROOT/'analysis/raw/map-flags-20261112'/Path(path).name);skin=controller_evidence(b,b.parse(),literal_nodes(b))
            self.assertEqual(p['weights'],skin['literalWeights2']);self.assertEqual(p['indices'],skin['literalIndices4']);self.assertFalse(p['additionalBindShapeApplied']);self.assertTrue(p['nativeBoneLookupVerified'])
            self.assertEqual([x['inverseBindMatrix']for x in p['bones']],[x['inverseBindMatrix']for x in skin['bones']]);self.assertEqual(p['nodes'],literal_nodes(b));self.assertIn(p['sourceChannelCount'],[21,27]);self.assertEqual(p['selectedPropertyCount'],p['sourceChannelCount']);self.assertTrue(p['sourceCompatibilityBootstrap'])
    def test_corrupt_loop_or_bone_reference_is_rejected(self):
        self.node(r'''
const p=JSON.parse(readFileSync(process.argv[2])).sourceFlagMotion;
for(const edit of[x=>x.clock.loop=false,x=>x.bones[0].node=-1,x=>x.weights[0][0]=NaN,x=>x.channels[0].timesMs[0]=1,x=>x.additionalBindShapeApplied=true]){const c=structuredClone(p);edit(c);assert.throws(()=>api.validateFlag(c));}
''',self.models()[0])
    def test_only_17_source_placements_and_existing_lighting(self):
        old=json.loads((RUN/'game-data/converted/source-map-zero-planes/manifest.json').read_text());new=json.loads((EXP/'manifest.json').read_text());audit=json.loads((EXP/'audit.json').read_text())
        self.assertEqual(new['scenery'][:154],old['scenery']);self.assertEqual(len(new['scenery']),156);self.assertEqual(sum(len(x['instances'])for x in new['scenery']),1248);self.assertEqual(len(audit['added']),17);self.assertEqual(audit['omittedInstances'],10);self.assertFalse(audit['lightsChanged'])
        before=json.loads((RUN/'game-data/converted'/old['sceneBakedLighting']['url'].removeprefix('/assets/')).read_text());after=json.loads((EXP/'baked-lighting.json').read_text());self.assertEqual(after['instances'][:1200],before['instances']);self.assertEqual(len(after['instances']),1217)
        for key in before.keys()-{'instances','atlases'}:self.assertEqual(before[key],after[key])
        for name,digest in json.loads((RAW/'before-assets.json').read_text()).items():self.assertEqual(hashlib.sha256((RUN/'game-data/converted'/name).read_bytes()).hexdigest(),digest)
    def test_rebuild_is_byte_identical_and_does_not_change_live_preview(self):
        with tempfile.TemporaryDirectory(dir=RAW)as tmp:
            export(RUN,Path(tmp))
            expected={p.name:p.read_bytes()for p in EXP.iterdir()};actual={p.name:p.read_bytes()for p in Path(tmp).iterdir()};self.assertEqual(actual,expected)
    def test_connector_replay_and_repeat_refusal(self):
        from connect_flag_motion import connect
        with tempfile.TemporaryDirectory(dir=RAW)as tmp:
            d=Path(tmp);(d/'game-data/converted').mkdir(parents=True);pub=d/'prototype/public';pub.mkdir(parents=True)
            for n in('explore-map.js','explore-map.html'):shutil.copyfile(RAW/('before-'+n),pub/n)
            self.assertEqual(connect(d,EXP)['files'],15)
            files={str(p.relative_to(d)):p.read_bytes()for p in d.rglob('*')if p.is_file()}
            # Entry points may gain a later, separately checked material branch.
            # Pin this connector's historical output instead of requiring the
            # live preview to stay frozen at the flag-only stage forever.
            entrypoints={'prototype/public/explore-map.js':'2c5d78058b5b46c3641aa38fe4b3b3ad223770d2b14ad59b6cc8eea8bbf653ab',
                         'prototype/public/explore-map.html':'45d64e70840ffbf04efa57ab410361f674f245b83554b3c3cd8ad84d42c570d8'}
            for n,b in files.items():
                if n in entrypoints:self.assertEqual(hashlib.sha256(b).hexdigest(),entrypoints[n])
                else:self.assertEqual(b,(RUN/n).read_bytes())
            with self.assertRaises(ValueError):connect(d,EXP)
            self.assertEqual(files,{str(p.relative_to(d)):p.read_bytes()for p in d.rglob('*')if p.is_file()})

if __name__=='__main__':unittest.main()
