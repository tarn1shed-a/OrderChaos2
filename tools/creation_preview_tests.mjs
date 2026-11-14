import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync,existsSync} from 'node:fs';
import {stageEntry} from '../deploy/stage_runtime.mjs';
import {creationPreviewPlan} from '../deploy/creation_plan.mjs';
const source=readFileSync(new URL('../deploy/creation_preview.mjs',import.meta.url),'utf8');
// Only the manifest admission guard is evaluated here. Rendering and switching
// are checked in the actual recovered SVG UI/browser, not a pretend GPU.
const context={};vm.createContext(context);
vm.runInContext(source.replace(/^import[^\n]*\n/gm,'').replaceAll('export ','')+';this.validate=validateCreationDelivery;',context);
const validate=context.validate;
const profile={format:'oc2-source-creation-preview-delivery-v1',mapId:7,sourceSelectionRegion:211,freshStartOnly:true,wholeCreationRestored:false,createsPlayableRole:false,stages:['CharacterChooseRace'],
 stage:'/assets/source-creation-stage/stage.json',environment:'/assets/source-creation-stage/environment.json',scene:'/assets/source-selection-scene/manifest.json',inside:'/assets/source-selection-inside/overlay.json',stones:'/assets/source-selection-stones/overlay.json',
 previews:{'0:0':{baseURL:'/assets/source-creation-human-male/'},'0:1':{baseURL:'/assets/source-creation-human-female/'}}};
test('race-preview admission rejects unavailable stages, models, worlds and external resource redirects',()=>{
 assert.equal(validate(profile),profile);
 for(const change of [null,{}, {...profile,mapId:5},{...profile,createsPlayableRole:true},{...profile,stages:['CharacterChoosePart']},{...profile,wholeCreationRestored:true},
  {...profile,scene:'https://external.invalid/model.json'},{...profile,stage:'/assets/source-creation-stage/../other.json'},{...profile,previews:{...profile.previews,'2:0':profile.previews['0:0']}}])assert.throws(()=>validate(change));
});
test('preview host has no character mutation endpoint and keeps unsupported role stages outside admission',()=>{
 assert(!source.includes('WebSocket'));assert(!source.includes("method:'POST'"));assert(!source.includes('localStorage'));
 assert(source.includes("screen!=='CharacterChooseRace'"));
 const css=readFileSync(new URL('../deploy/entry_ui.css',import.meta.url),'utf8');assert(css.includes('object-fit:contain'));assert(css.includes('pointer-events:none'));
});
test('race-only preparation does not become a map-entry gate or prefetch unrelated character textures',()=>{
 const original={critical:['/explore-map.js','/assets/source-creation-stage/manifest.json','/assets/source-selection-scene/manifest.json','/__delivery/entry_ui.mjs'],background:['/assets/source-temple-sampling/far.png','/assets/source-creation-human-female/assets/body.png'],scope:{unchanged:true}};
 const before=JSON.stringify(original),actual=creationPreviewPlan(original,[...original.critical,...original.background]);
 assert.deepEqual(actual.critical,['/explore-map.js','/__delivery/entry_ui.mjs']);assert.deepEqual(actual.background,['/assets/source-temple-sampling/far.png']);assert.equal(JSON.stringify(original),before);
 assert.equal(actual.scope.unchanged,true);assert.equal(actual.scope.creationPreviewChangesPlayableRaces,false);
});
test('preview routing is opt-in and leaves the existing entry, world and saves unchanged otherwise',t=>{
 const path=new URL('../analysis/raw/showcase-20261110/running-preview/prototype/public/explore-map.js',import.meta.url);
 if(!existsSync(path)){t.skip('Private reviewed source absent');return;}
 const original=readFileSync(path,'utf8'),old=stageEntry(original,{entryUI:true}),next=stageEntry(original,{entryUI:true,creationPreview:true});
 const addition="previewURL:'/assets/source-creation-stage/manifest.json',";
 assert.equal(next.replace(addition,''),old);assert.throws(()=>stageEntry(original,{creationPreview:true}));
});
