"""Sky release integration: public plan guards and private append/replay receipt."""
import hashlib
import json
import shutil
import subprocess
import tarfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT/'analysis/raw/tutorial-sky-release-20261115'


class Public(unittest.TestCase):
    def node(self, body):
        node = shutil.which('node') or str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node')
        if not Path(node).is_file(): self.skipTest('Node absent')
        script = '''
import assert from 'node:assert/strict';
import {stageTutorialSkyPlan,SKY_MANIFEST} from './tools/preview/source-tutorial-sky-overlay.mjs';
const profile={format:'oc2-source-tutorial-sky-candidate-v1',sourceMapId:5,models:{main:{model:{url:'/assets/source-tutorial-sky/main.json'},texture:{url:'/assets/source-tutorial-sky/main.png'}},hill:{model:{url:'/assets/source-tutorial-sky/hill.json'},texture:{url:'/assets/source-tutorial-sky/hill.png'}}},shaders:{vertex:{url:'/assets/source-tutorial-sky/sky_box_vs.glsl'},fragment:{url:'/assets/source-tutorial-sky/sky_box_fs.glsl'}}};
const all=[SKY_MANIFEST,...Object.values(profile.models).flatMap(v=>[v.model.url,v.texture.url]),...Object.values(profile.shaders).map(v=>v.url),'/source-tutorial-sky.js'];
const texts=new Map([[SKY_MANIFEST,JSON.stringify(profile)]]),plan={critical:[...all],background:['/assets/existing-background.json'],scope:{existing:true,wholeMapAccepted:true}};
''' + body
        done = subprocess.run([node, '--input-type=module', '-e', script], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_real_plan_bridge_preserves_background_and_marks_whole_map_unaccepted(self):
        self.node('const out=stageTutorialSkyPlan(plan,texts);assert.deepEqual(out.background,plan.background);assert.deepEqual(out.critical,plan.critical);assert.equal(out.scope.existing,true);assert.equal(out.scope.sourceTutorialSky,true);assert.equal(out.scope.wholeMapAccepted,false);assert.equal(out.scope.skyGPUQueue,"browser-adaptation");assert.equal(plan.scope.wholeMapAccepted,true);')

    def test_each_of_eight_missing_critical_resources_is_rejected(self):
        self.node('assert.equal(all.length,8);for(const missing of all)assert.throws(()=>stageTutorialSkyPlan({...plan,critical:all.filter(v=>v!==missing)},texts));')

    def test_missing_or_wrong_original_map_manifest_is_rejected(self):
        self.node('assert.throws(()=>stageTutorialSkyPlan(plan,new Map()));for(const altered of [{...profile,format:"other"},{...profile,sourceMapId:1}])assert.throws(()=>stageTutorialSkyPlan(plan,new Map([[SKY_MANIFEST,JSON.stringify(altered)]])));')


@unittest.skipUnless((RELEASE/'receipt.json').is_file() and (RELEASE/'prepare-receipt.json').is_file(), 'Private sky release replay absent')
class PrivateRelease(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipt = json.loads((RELEASE/'receipt.json').read_text())
        cls.prepared = json.loads((RELEASE/'prepare-receipt.json').read_text())

    def test_actual_delta_payload_matches_full_manifest_and_has_no_save_or_host_replacement(self):
        r = self.receipt
        p = Path(r['delta']['path'])
        with p.open('rb') as f: self.assertEqual(hashlib.file_digest(f, 'sha256').hexdigest(), r['delta']['sha256'])
        with tarfile.open(r['current']['path']) as previous:
            online = json.load(previous.extractfile('bundle-manifest.json'))
        with tarfile.open(p) as t:
            rows = t.getmembers(); names = {m.name for m in rows}
            manifest = json.load(t.extractfile('bundle-manifest.json'))
            base = json.load(t.extractfile('bundle-base.json'))
            self.assertEqual(base['baseArchiveSHA256'], r['base']['sha256'])
            payload = names-{'bundle-manifest.json', 'bundle-base.json'}
            self.assertEqual(len(payload), 42); self.assertEqual(len(manifest['files']), 2899)
            self.assertEqual(len(manifest['runtimeIdentity']['files']), 127)
            self.assertEqual(len(manifest['pythonFiles']), 53)
            for name in payload:
                raw = t.extractfile(name).read()
                self.assertEqual(manifest['files'][name], {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
                self.assertFalse('characters.json' in name or name.startswith(('runtime/', 'native-inputs/')))
                if name.startswith('tools/'):
                    # Two scene-effect JS overlays already belong to the
                    # online 34-file extension. They are not new Python hosts.
                    self.assertEqual(online['files'].get(name), manifest['files'][name])

    def test_actual_bootstrap_receipt_preserves_all_previous_online_payloads(self):
        r = self.receipt
        self.assertEqual(r['originalOnlinePayloadsPreserved'], 2891)
        self.assertEqual(r['currentAndBaseMetadataReplacements'], [])
        self.assertTrue(r['actualBootstrapExtractVerified']); self.assertTrue(r['allReconstructedPayloadBytesVerified'])
        self.assertFalse(r['userSaveReadOrWritten']); self.assertFalse(r['dockerStarted'])
        runtime = Path(r['runtime'])
        full = json.loads((runtime/'bundle-manifest.json').read_text())
        with tarfile.open(r['current']['path']) as t:
            old = json.load(t.extractfile('bundle-manifest.json'))
        self.assertEqual(old['runtimeIdentity'], full['runtimeIdentity']); self.assertEqual(old['pythonFiles'], full['pythonFiles'])
        self.assertTrue(all(full['files'].get(k) == v for k, v in old['files'].items()))
        self.assertEqual(len(set(full['files'])-set(old['files'])), 8)

    def test_actual_formal_prepare_keeps_inspector_and_changes_only_the_map_entry(self):
        r = self.prepared
        self.assertEqual(r['prepareSourceSHA256'], hashlib.sha256((ROOT/'deploy/prepare_delivery.mjs').read_bytes()).hexdigest())
        self.assertEqual(r['publicChanged'], ['/explore-map.js']); self.assertEqual(len(r['publicAdded']), 8)
        self.assertEqual(r['existingOtherPublicFilesIdentical'], 2742)
        self.assertEqual(r['baseline']['background'], r['candidate']['background'])
        self.assertEqual(r['candidate']['critical']-r['baseline']['critical'], 8)
        self.assertTrue(r['allSkyCritical']); self.assertTrue(r['inspectorKept']); self.assertTrue(r['qaObserverAbsent'])
        self.assertTrue(r['originalManifestRestored']); self.assertFalse(r['serverStarted']); self.assertFalse(r['userSaveReadOrWritten'])
        self.assertFalse(r['candidate']['scope']['wholeMapAccepted'])


if __name__ == '__main__': unittest.main()
