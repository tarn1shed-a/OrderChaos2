"""Private append-only package and actual generated character-panel route checks."""
import argparse
import json
import subprocess
import tarfile
import unittest
from pathlib import Path

from character_panel_delivery import ROOT,BASE,BASE_SHA,CANDIDATE,CANDIDATE_MANIFEST_SHA,read_base,panel_payload,digest

NODE='/Users/kevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'
PACKAGE=None


@unittest.skipUnless(BASE.is_file()and(CANDIDATE/'SHA256.json').is_file(),'Private package/candidate stay local')
class CharacterPanelDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.base,cls.manifest=read_base();cls.delta,cls.dependencies=panel_payload(cls.base)

    def test_append_preserves_every_base_member_and_original_native_inputs(self):
        combined={**self.base,**self.delta}
        self.assertEqual(len(self.delta),104);self.assertEqual(len(combined),len(self.base)+104)
        for name,raw in self.base.items():self.assertEqual(combined[name],raw,name)
        for name,sha in self.manifest['runtimeIdentity']['files'].items():self.assertEqual(digest(combined[name]),sha)
        self.assertEqual(len(self.manifest['runtimeIdentity']['files']),127)
        self.assertEqual({p for p in self.delta if p.startswith('prototype/')},{'prototype/public/character-source-panels.mjs','prototype/public/character-source-state.mjs','prototype/public/character-source-panels.css'})
        self.assertFalse(any('qa' in n.lower()or n.endswith(('.sqlite','.db','.html'))or n.startswith('native-inputs/')for n in self.delta))
        self.assertTrue(all(n.startswith(('game-data/converted/character-source/','prototype/public/character-source-'))for n in self.delta))

    def test_runtime_references_resolve_without_copying_login_or_frame_dependencies(self):
        combined={**self.base,**self.delta};profile=json.loads(self.delta['game-data/converted/character-source/panels.json'])
        def references(value):
            if isinstance(value,str)and value.startswith('/assets/'):yield value
            elif isinstance(value,dict):
                for item in value.values():yield from references(item)
            elif isinstance(value,list):
                for item in value:yield from references(item)
        for url in references(profile):self.assertIn('game-data/converted/'+url.removeprefix('/assets/'),combined,url)
        for name in self.dependencies:self.assertIn(name,self.base);self.assertNotIn(name,self.delta)
        self.assertEqual(digest(self.delta['prototype/public/character-source-panels.mjs']),digest((ROOT/'tools/preview/character-source-panels.mjs').read_bytes()))
        self.assertNotIn('game-data/converted/source-entry/entry.json',self.delta)

    def test_actual_staged_entry_routes_keys_menus_close_and_read_only_role_updates(self):
        script=r'''
import assert from 'node:assert/strict';import{readFileSync}from'node:fs';import{spawnSync}from'node:child_process';import{pathToFileURL}from'node:url';
const root=process.argv[1];
const{stageEntry}=await import(pathToFileURL(root+'/deploy/stage_runtime.mjs'));
const{stageInsideEntry}=await import(pathToFileURL(root+'/tools/preview/map-runtime-inside-overlay.mjs'));
const{stageCharacterPanelsEntry,createCharacterPanelHandles}=await import(pathToFileURL(root+'/tools/preview/character-panel-runtime-overlay.mjs'));
const original=readFileSync(root+'/analysis/raw/showcase-20261110/running-preview/prototype/public/explore-map.js','utf8');
const before=stageInsideEntry(stageEntry(original,{entryUI:true})),source=stageCharacterPanelsEntry(before);
assert.throws(()=>stageCharacterPanelsEntry(source),/already applied/);
assert.throws(()=>stageCharacterPanelsEntry(stageEntry(original,{entryUI:true})),/four-inside/);
assert.throws(()=>stageCharacterPanelsEntry(stageInsideEntry(stageEntry(original))),/anchor differs/);
assert.throws(()=>stageCharacterPanelsEntry(before.replace('attributeUI=createAttributeUI','attributeUI=createChangedUI')),/anchor differs/);
assert.throws(()=>stageCharacterPanelsEntry(before+'\n'+"import { createSkillBook } from './skill-book.js';\n"),/anchor differs/);
assert(!source.includes('createAttributeUI'));assert(!source.includes('createSkillBook'));
assert.equal(source.split('attributeUI?.update(data)').length,2);assert.equal(source.split('attributeUI?.update(null)').length,2);
assert(source.includes("$('field-skills').addEventListener('click',()=>{questBook?.close();skillBook?.open();});"));
assert(source.includes('function inputBlocked(){return attributeUI?.isOpen||questBook?.isOpen||skillBook?.isOpen'));
assert(source.includes('function openSession(){characterPanels?.close();if(sourceEntry)sourceEntry.open();else legacySession();}'));
assert(source.includes("const xp=$('field-xp');return xp?{value:xp.value,max:xp.max}:null;"));
const preview=before.match(/preview:\(role,size\)=>renderAttributePreview\([^\n]*?(?=,beforeOpen:)/)?.[0];assert(preview&&source.includes(preview));
assert.equal((source.match(/\bsend\(/g)||[]).length,(before.match(/\bsend\(/g)||[]).length);
assert(source.includes("$('xp').value = xp % 60; $('xp-text').textContent = `${xp % 60} / 60（累计 ${xp}）`;"));
const syntax=spawnSync(process.execPath,['--check','--input-type=module'],{input:source,encoding:'utf8'});assert.equal(syntax.status,0,syntax.stderr);
let kind='attributes',opened=false,updates=[],calls=[];
const panels={get isOpen(){return opened;},inspect:()=>({kind}),openAttributes(){kind='attributes';opened=true;calls.push('attributes');},openSkills(){kind='skills';opened=true;calls.push('skills');},close(){opened=false;calls.push('close');},update(data,options){updates.push({data,options});}};
let reads=0;const progress=Object.freeze({value:30,max:60}),handles=createCharacterPanelHandles(panels,()=>{reads++;return progress;});
const role=Object.freeze({id:'explicit-fixture',profession:4,level:3,xp:150});handles.attributes.update(role);
assert.equal(updates[0].data,role);assert.equal(updates[0].options.source,null);assert.equal(updates[0].options.trialProgress,progress);assert.equal(role.xp,150);
handles.attributes.update(null);assert.equal(reads,1);assert.deepEqual(updates[1],{data:null,options:{source:null,trialProgress:null}});
handles.skills.open();assert(handles.skills.isOpen);assert(!handles.attributes.isOpen);handles.attributes.close();assert(!panels.isOpen);
// Execute the actual generated key handler with explicit DOM/event fixtures.
const keyStart=source.indexOf("window.addEventListener('keydown', e => {"),keyEnd=source.indexOf("window.addEventListener('keyup'",keyStart);assert(keyStart>=0&&keyEnd>keyStart);
let handler;const window={addEventListener(name,fn){assert.equal(name,'keydown');handler=fn;}},document={activeElement:{tagName:'CANVAS'}},session={open:false},quest={isOpen:false},hotbar={isEditing:false};
new Function('window','document','$','characterPanels','connected','questBook','hotbar','skillBook','attributeUI',source.slice(keyStart,keyEnd))(window,document,()=>session,panels,true,quest,hotbar,handles.skills,handles.attributes);
const event=(code,extra={})=>({code,repeat:false,isComposing:false,ctrlKey:false,metaKey:false,altKey:false,preventDefault(){this.prevented=true;},...extra});
calls=[];opened=false;handler(event('KeyC'));assert.deepEqual(calls,['attributes']);assert(handles.attributes.isOpen);
handler(event('KeyK'));assert.equal(calls.at(-1),'skills');assert(handles.skills.isOpen);
handler(event('KeyK'));assert.equal(calls.at(-1),'close');assert(!opened);
let n=calls.length;handler(event('KeyC',{repeat:true}));assert.equal(calls.length,n);
handler(event('KeyC',{ctrlKey:true}));assert.equal(calls.length,n);
document.activeElement.tagName='INPUT';handler(event('KeyK'));assert.equal(calls.length,n);document.activeElement.tagName='CANVAS';
quest.isOpen=true;handler(event('KeyC'));assert.equal(calls.length,n);quest.isOpen=false;
session.open=true;handler(event('KeyK'));assert.equal(calls.length,n);
console.log(JSON.stringify({syntax:true,guardedAnchors:true,previewUnchanged:true,existingRoleProgressOnly:true,actualGeneratedKeyHandler:true}));
'''
        result=subprocess.run([NODE,'--input-type=module','-e',script,str(ROOT)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);self.assertTrue(json.loads(result.stdout)['actualGeneratedKeyHandler'])

    def test_panel_art_moves_to_background_without_changing_inside_secondary_texture_critical(self):
        script=r'''
import assert from 'node:assert/strict';import{readFileSync}from'node:fs';import{pathToFileURL}from'node:url';
const root=process.argv[1],run=root+'/analysis/raw/showcase-20261110/running-preview',candidate=root+'/analysis/raw/map-specialist-20261114/inside-visible-candidate-v6';
const{stageCharacterPanelsPlan}=await import(pathToFileURL(root+'/tools/preview/character-panel-runtime-overlay.mjs'));
const{stageInsidePlan,INSIDE_MANIFEST,PREVIOUS_MANIFEST}=await import(pathToFileURL(root+'/tools/preview/map-runtime-inside-overlay.mjs'));
const{stagePlan}=await import(pathToFileURL(root+'/deploy/stage_plan.mjs'));
const moduleURLs=['/explore-map.js','/character-source-panels.mjs','/character-source-state.mjs','/source-ui-svg.js'];
const profile=JSON.parse(readFileSync(root+'/analysis/raw/character-progression-20261114/panel-candidate-final/public/assets/character-source/panels.json'));
const panelURLs=[...new Set(['/assets/character-source/panels.json',...Object.values(profile.windows).map(v=>v.url),...Object.values(profile.assets).map(v=>v.url)])];
assert.equal(panelURLs.length,101);
const scope=Object.freeze({entryTiles:3});
const noArt={critical:[...moduleURLs,'/assets/map.json'],background:['/assets/rest.png'],scope};assert.equal(stageCharacterPanelsPlan(noArt),noArt);
const duplicate={critical:[...moduleURLs,panelURLs[0],panelURLs[0],'/assets/source-secondary.png'],background:[panelURLs[0],'/assets/rest.png'],scope};
const changed=stageCharacterPanelsPlan(duplicate);assert.equal(changed.scope,scope);assert.deepEqual(changed.critical,[...moduleURLs,'/assets/source-secondary.png']);
assert.equal(changed.background.filter(v=>v===panelURLs[0]).length,1);assert.deepEqual(new Set([...changed.critical,...changed.background]),new Set([...duplicate.critical,...duplicate.background]));
assert.equal(stageCharacterPanelsPlan(changed),changed);
// Run the real four-inside planner over its pinned private source documents.
const full=JSON.parse(readFileSync(candidate+'/manifest.json')),texts=new Map([[INSIDE_MANIFEST,JSON.stringify(full)]]);
const read=url=>{if(texts.has(url))return JSON.parse(texts.get(url));const path=url.startsWith('/assets/source-tutorial-inside/')?candidate+'/'+url.split('/').at(-1):run+'/game-data/converted/'+url.slice(8);const raw=readFileSync(path,'utf8');texts.set(url,raw);return JSON.parse(raw);};
read(full.map.url);read(full.mapWindow.url);read(full.terrainWaterFloor.url);read(full.map.materials.url);read(full.terrainLighting.url);
for(const row of [full.player,...full.exhibits,...full.dynamicModels,...full.scenery])read(row.url);
const bounds=read(full.map.url).bounds,x=(-2682.6533203125-bounds.min[0])/(bounds.max[0]-bounds.min[0])*1280,z=(-64.11836242675781-bounds.min[2])/(bounds.max[2]-bounds.min[2])*1280;
texts.set('/__delivery/trial-world.js',`RESOURCE_WORLD = { ...WORLD, width: 1280, height: 1280, spawn: { x: ${x}, y: ${z} } }`);
let curated;
const closure=(entry,docs)=>{const manifest=JSON.parse(docs.get(INSIDE_MANIFEST)||docs.get(PREVIOUS_MANIFEST));if(manifest.scenery.length<full.scenery.length)curated=manifest;
 return [...new Set([...moduleURLs,INSIDE_MANIFEST,full.map.url,full.mapWindow.url,full.terrainWaterFloor.url,...panelURLs,...Object.values(manifest.textures)])];};
const originalPlan=await stageInsidePlan(stagePlan,texts,closure),beforeCritical=[...originalPlan.critical],beforeBackground=[...originalPlan.background];
const result=stageCharacterPanelsPlan(originalPlan);assert.equal(result.scope,originalPlan.scope);assert.equal(result.scope.insidePrimaryModels,4);assert.equal(result.scope.wholeMapAccepted,false);
assert.deepEqual(result.critical,originalPlan.critical.filter(v=>!v.startsWith('/assets/character-source/')));
assert.deepEqual(originalPlan.critical,beforeCritical);assert.deepEqual(originalPlan.background,beforeBackground);
assert.deepEqual(new Set([...result.critical,...result.background]),new Set([...originalPlan.critical,...originalPlan.background]));
assert.equal(new Set(result.background).size,result.background.length);
for(const url of moduleURLs)assert(result.critical.includes(url));for(const url of panelURLs){assert(!result.critical.includes(url));assert(result.background.includes(url));}
let secondary=0;for(const row of curated.scenery)for(const mat of read(row.url).sourceInsideMaterials?.materials||[]){if(mat.missingSamplers.length)continue;
 for(const name of ['texture2','texture2Mask']){const key=mat.samplers[name]?.texture;if(key){const url=full.textures[key];assert(originalPlan.critical.includes(url));assert(result.critical.includes(url));secondary++;}}}
assert(secondary>0);assert(result.critical.includes(full.map.url));assert(result.critical.includes(INSIDE_MANIFEST));
console.log(JSON.stringify({panelResources:panelURLs.length,secondaryCriticalPreserved:secondary,scopeUnchanged:true,allDependenciesRetained:true}));
'''
        result=subprocess.run([NODE,'--input-type=module','-e',script,str(ROOT)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        report=json.loads(result.stdout);self.assertEqual(report['panelResources'],101);self.assertGreater(report['secondaryCriticalPreserved'],0)

    def test_written_complete_archive_matches_all_payload_hashes_and_base_metadata(self):
        if not PACKAGE:self.skipTest('Pass --package to verify the written private complete bundle')
        receipt=json.loads(Path(str(PACKAGE)+'.receipt.json').read_text());self.assertEqual(receipt['sha256'],digest(Path(PACKAGE).read_bytes()))
        self.assertEqual(receipt['baseArchiveSHA256'],BASE_SHA);self.assertEqual(receipt['appendedFiles'],104)
        with tarfile.open(PACKAGE,'r:gz')as archive:
            members=archive.getmembers();names=[m.name for m in members]
            self.assertEqual(len(names),len(set(names)));self.assertEqual(len(names),len(self.base)+105)
            manifest=json.load(archive.extractfile('bundle-manifest.json'));expected={**self.base,**self.delta}
            for member in members:
                self.assertTrue(member.isfile());self.assertEqual(member.mode,0o600)
                if member.name=='bundle-manifest.json':continue
                raw=archive.extractfile(member).read();self.assertEqual(raw,expected[member.name])
                self.assertEqual(manifest['files'][member.name],{'bytes':len(raw),'sha256':digest(raw)})
        for key,value in self.manifest.items():
            if key!='files':self.assertEqual(manifest[key],value,key)
        self.assertEqual(manifest['characterIntegration']['candidateManifestSHA256'],CANDIDATE_MANIFEST_SHA)
        self.assertIsNone(manifest['characterIntegration']['realSourceState']);self.assertFalse(receipt['standaloneQAIncluded']);self.assertFalse(receipt['localSavesImported'])


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--package',type=Path)
    args,remaining=cli.parse_known_args();PACKAGE=args.package
    unittest.main(argv=[__file__,*remaining])
