import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {createCharacterHotbar,mageTrialEligible,CONNECTED_MAGE_SPELLS} from '../deploy/character_hotbar.mjs';
import {stageCharacterHotbarEntry} from './preview/character-hotbar-overlay.mjs';
import {stageCharacterPanelsEntry} from './preview/character-panel-runtime-overlay.mjs';
import {stageInsideEntry} from './preview/map-runtime-inside-overlay.mjs';
import {stageEntry} from '../deploy/stage_runtime.mjs';

const ROOT=fileURLToPath(new URL('../',import.meta.url)),RUNTIME=ROOT+'analysis/raw/showcase-20261110/running-preview/';
const {defaultHotbar,swapHotbarSlots,rebindHotbarSlot}=await import(new URL('../analysis/raw/showcase-20261110/running-preview/prototype/public/hotbar-settings.js',import.meta.url));
const {createHotbarUI}=await import(new URL('../analysis/raw/showcase-20261110/running-preview/prototype/public/hotbar-ui.js',import.meta.url));
let passed=0;
function test(name,fn){fn();passed++;console.log('ok '+name);}

// Explicit DOM fixture, never the user's browser, storage or saved characters.
class Style{
 values=new Map();getPropertyValue(k){return this.values.get(k)?.value||'';}getPropertyPriority(k){return this.values.get(k)?.priority||'';}
 setProperty(k,value,priority=''){this.values.set(k,{value,priority});}removeProperty(k){this.values.delete(k);}
}
class Element{
 constructor(tag='div',id='',className=''){this.tagName=tag.toUpperCase();this.id=id;this.children=[];this.parentElement=null;this.attrs=new Map();this.events=new Map();this.style=new Style();this.hidden=false;this.disabled=false;this.inert=false;this.tabIndex=0;this.textContent='';this.dataset={};this.classes=new Set(className.split(' ').filter(Boolean));
  this.classList={add:(...s)=>s.forEach(v=>this.classes.add(v)),remove:(...s)=>s.forEach(v=>this.classes.delete(v)),toggle:(s,v)=>{const on=v===undefined?!this.classes.has(s):v;on?this.classes.add(s):this.classes.delete(s);return on;},contains:s=>this.classes.has(s)};}
 set className(v){this.classes=new Set(v.split(' ').filter(Boolean));}get className(){return [...this.classes].join(' ');}
 append(...nodes){for(const node of nodes){node.remove();node.parentElement=this;this.children.push(node);}}prepend(node){node.remove();node.parentElement=this;this.children.unshift(node);}
 remove(){if(this.parentElement){this.parentElement.children=this.parentElement.children.filter(n=>n!==this);this.parentElement=null;}}
 replaceChildren(...nodes){for(const n of this.children)n.parentElement=null;this.children=[];this.append(...nodes);}
 setAttribute(k,v){this.attrs.set(k,String(v));}getAttribute(k){return this.attrs.get(k)??null;}removeAttribute(k){this.attrs.delete(k);}
 matches(selector){return selector.startsWith('.')?this.classes.has(selector.slice(1)):selector.startsWith('#')?this.id===selector.slice(1):this.tagName.toLowerCase()===selector;}
 closest(selector){for(let n=this;n;n=n.parentElement)if(n.matches(selector))return n;return null;}
 contains(node){for(let n=node;n;n=n.parentElement)if(n===this)return true;return false;}
 querySelectorAll(selector){return this.children.flatMap(n=>[...(n.matches(selector)?[n]:[]),...n.querySelectorAll(selector)]);}querySelector(selector){return this.querySelectorAll(selector)[0]??null;}
 addEventListener(type,fn,capture=false){if(!this.events.has(type))this.events.set(type,[]);this.events.get(type).push({fn,capture});}focus(){}
}
function fixture(){
 const nodes=new Map(),body=new Element('body'),listeners=new Map(),windowListeners=new Map();
 const add=(id,tag='div',cls='',parent=body)=>{const n=new Element(tag,id,cls);if(id)nodes.set(id,n);parent.append(n);return n;};
 const root=add('field-actions'),slots=Array.from({length:10},(_,i)=>{const n=add('slot-'+i,'div','hotbar-slot',root);n.dataset.slot=String(i);add('key-'+i,'kbd','slot-key',n);return n;});
 CONNECTED_MAGE_SPELLS.forEach((id,i)=>{for(const prefix of ['field-','skill-']){const button=add(prefix+id,'button','',prefix==='field-'?slots[i]:body);add('icon-'+prefix+id,'img','skill-icon',button);}});
 const attack=add('field-attack','button','',root),jump=add('field-interaction','button','',root);attack.style.left='native-attack';jump.style.left='native-jump';
 const panel=add('hotbar-editor');panel.hidden=true;
 for(const id of ['hotbar-close','hotbar-reset','hotbar-retry'])add(id,'button','',panel);
 add('hotbar-bindings','div','',panel);add('hotbar-status','p','',panel);add('hotbar-settings','button');add('skill-hint','p');
 const doc={body,getElementById:id=>nodes.get(id)||null,createElement:tag=>new Element(tag),addEventListener(type,fn,capture){if(!listeners.has(type))listeners.set(type,[]);listeners.get(type).push({fn,capture});}};
 let storageReads=0,storageWrites=0,sends=[],role=null,changes=0;
 const win={addEventListener(type,fn,capture){if(!windowListeners.has(type))windowListeners.set(type,[]);windowListeners.get(type).push({fn,capture});},localStorage:{getItem(){storageReads++;return null;},setItem(){storageWrites++;}}};
 globalThis.document=doc;globalThis.window=win;
 const nativeLayout=()=>{let empty=4;for(const slot of slots){const id=CONNECTED_MAGE_SPELLS.find(id=>slot.querySelector('#field-'+id));const index=id?CONNECTED_MAGE_SPELLS.indexOf(id)+1:empty++;slot.hidden=index>4;slot.dataset.nativeSlot=String(index);}};
 const adapter=createCharacterHotbar({createHotbarUI,createMobileHUD:()=>{nativeLayout();return{layout:nativeLayout,scale:.8};},readCharacter:()=>role,document:doc});
 const hotbar=adapter.createHotbar({root,panel,toggle:nodes.get('hotbar-settings'),closeButton:nodes.get('hotbar-close'),rows:nodes.get('hotbar-bindings'),status:nodes.get('hotbar-status'),reset:nodes.get('hotbar-reset'),retryButton:nodes.get('hotbar-retry'),send:value=>{sends.push(value);},fixedLayout:true,onChange:()=>{changes++;}});
 const mobile=adapter.createMobile({});
 function dispatch(node,type='click'){
  const event={target:node,defaultPrevented:false,stopped:false,preventDefault(){this.defaultPrevented=true;},stopImmediatePropagation(){this.stopped=true;},stopPropagation(){this.stopped=true;}};
  for(const {fn}of listeners.get(type)||[]){fn(event);if(event.stopped)return event;}
  for(const {fn}of node.events.get(type)||[]){fn(event);if(event.stopped)return event;}return event;
 }
 return {doc,root,slots,nodes,adapter,hotbar,mobile,dispatch,setRole(next){role=next;},get role(){return role;},get sends(){return sends;},get storageReads(){return storageReads;},get storageWrites(){return storageWrites;},get changes(){return changes;}};
}
function role(profession,id='fixture-'+profession,settings=defaultHotbar()){return Object.freeze({id,profession,hotbar:settings,level:3,xp:150});}
const hidden=n=>n.style.getPropertyValue('display')==='none'&&n.style.getPropertyPriority('display')==='important';
function assertBlocked(f){
 for(const id of CONNECTED_MAGE_SPELLS){const field=f.nodes.get('field-'+id),legacy=f.nodes.get('skill-'+id);assert(hidden(field));assert(hidden(field.closest('.hotbar-slot')));assert(field.disabled&&field.inert&&field.tabIndex===-1);assert(hidden(legacy));assert.equal(f.adapter.canUse(id),false);}
 assert(f.nodes.get('hotbar-settings').disabled);assert(f.nodes.get('hotbar-editor').hidden);assert(!f.hotbar.isEditing);
 assert(!hidden(f.nodes.get('field-attack')));assert(!hidden(f.nodes.get('field-interaction')));assert.equal(f.nodes.get('field-attack').style.left,'native-attack');assert.equal(f.nodes.get('field-interaction').style.left,'native-jump');
}

test('all five professions and no role obey existing mage-only transport eligibility',()=>{
 for(const profession of [null,1,2,3,4,5]){const f=fixture();const data=profession?role(profession):null;f.setRole(data);if(data)f.hotbar.setCharacter(data);
  assert.equal(mageTrialEligible(data),profession===2);if(profession!==2){assertBlocked(f);assert.equal(f.sends.length,0);assert.equal(f.storageReads,0);assert.equal(f.storageWrites,0);}else{for(const id of CONNECTED_MAGE_SPELLS)assert(f.adapter.canUse(id));}}
 for(const bad of [{id:'x',profession:'2'},{profession:2},{id:'',profession:2}])assert.equal(mageTrialEligible(bad),false);
});
test('role swaps, progress and native layout cannot restore another professions three spells',()=>{
 const f=fixture();let mage=role(2);f.setRole(mage);f.hotbar.setCharacter(mage);f.dispatch(f.nodes.get('hotbar-settings'));assert(f.hotbar.isEditing);
 for(const p of [3,1,5,4]){const other=role(p);f.setRole(other);f.hotbar.syncCharacter(other);f.hotbar.setCharacter(other);assertBlocked(f);
  for(const slot of f.slots)slot.hidden=false;for(const id of CONNECTED_MAGE_SPELLS)f.nodes.get('field-'+id).disabled=false;
  f.mobile.layout();f.hotbar.syncCharacter(other);f.adapter.apply();assertBlocked(f);
  assert.equal(f.hotbar.skillForEvent({code:'Digit1',shiftKey:false}),null);assert.equal(f.sends.length,0);assert.equal(f.storageWrites,0);
 }
 f.setRole(mage);f.hotbar.setCharacter(mage);f.mobile.layout();assert.equal(f.mobile.scale,.8);
 for(const id of CONNECTED_MAGE_SPELLS){assert(!hidden(f.nodes.get('field-'+id)));assert(!hidden(f.nodes.get('field-'+id).closest('.hotbar-slot')));}
 f.hotbar.disconnect();assertBlocked(f);f.setRole(null);f.mobile.layout();assertBlocked(f);
});
test('mage saved ordering and custom keys are preserved without filtering or writes',()=>{
 let settings=swapHotbarSlots(defaultHotbar(),0,7);settings=rebindHotbarSlot(settings,7,{code:'KeyZ',shift:true}).settings;
 const original=JSON.stringify(settings),f=fixture(),mage=role(2,'saved-mage',settings);f.setRole(mage);f.hotbar.setCharacter(mage);f.mobile.layout();
 assert.equal(JSON.stringify(settings),original);assert.equal(f.hotbar.keyForSkill('fireball'),'Shift+Z');assert.equal(f.hotbar.skillForEvent({code:'KeyZ',shiftKey:true}),'fireball');
 assert.equal(f.nodes.get('field-fireball').closest('.hotbar-slot').dataset.slot,'7');assert.equal(f.nodes.get('field-fireball').closest('.hotbar-slot').dataset.nativeSlot,'1');
 const ranger=role(3);f.setRole(ranger);f.hotbar.setCharacter(ranger);f.hotbar.receiveResult({requestId:1,ok:true,hotbar:settings});assertBlocked(f);assert.equal(f.sends.length,0);assert.equal(f.storageWrites,0);
 f.setRole(mage);f.hotbar.setCharacter(mage);assert.equal(f.hotbar.keyForSkill('fireball'),'Shift+Z');assert.equal(JSON.stringify(settings),original);
});
test('nonmage null config never initializes legacy storage or permits stale editor actions',()=>{
 const f=fixture(),ranger=role(3,'empty-ranger',null);f.setRole(ranger);f.hotbar.setCharacter(ranger);
 for(const id of ['hotbar-settings','hotbar-reset','hotbar-retry','field-fireball','skill-frost_blast']){const event=f.dispatch(f.nodes.get(id));assert(event.defaultPrevented&&event.stopped);}
 assertBlocked(f);assert.equal(f.sends.length,0);assert.equal(f.storageReads,0);assert.equal(f.storageWrites,0);assert.equal(ranger.hotbar,null);
});

const original=readFileSync(RUNTIME+'prototype/public/explore-map.js','utf8');
const before=stageCharacterPanelsEntry(stageInsideEntry(stageEntry(original,{entryUI:true})));
const staged=stageCharacterHotbarEntry(before);
test('actual staged overlay has unique anchors and preserves original attack, jump and sends',()=>{
 assert.throws(()=>stageCharacterHotbarEntry(staged),/already applied/);
 assert.throws(()=>stageCharacterHotbarEntry(stageInsideEntry(stageEntry(original,{entryUI:true}))),/requires source character panels/);
 assert.throws(()=>stageCharacterHotbarEntry(before.replace('function useSkill(id) {','function useChangedSkill(id) {')),/anchor differs/);
 assert.throws(()=>stageCharacterHotbarEntry(before+'\nfunction useSkill(id) {\n'),/anchor differs/);
 assert(staged.includes('mobileHUD=characterHotbar.createMobile(uiProfile.hud)'));assert(staged.includes('hotbar=characterHotbar.createHotbar('));
 assert(staged.includes('characterHotbar.apply();\n}'));assert.equal((staged.match(/\bsend\(/g)||[]).length,(before.match(/\bsend\(/g)||[]).length);
 const attack=before.slice(before.indexOf('function attack(pressed=false)'),before.indexOf('function useSkill(id)'));
 assert(staged.includes(attack));assert(staged.includes("jumpControl=createContextControl($('field-interaction')"));
 const syntax=spawnSync(process.execPath,['--check','--input-type=module'],{input:staged,encoding:'utf8'});assert.equal(syntax.status,0,syntax.stderr);
});
test('actual generated useSkill rejects wrong profession and stale-role direct calls before sending',()=>{
 const start=staged.indexOf('function useSkill(id)'),end=staged.indexOf('function updateSkills()',start),body=staged.slice(start,end);
 for(const profession of [null,1,2,3,4,5]){const f=fixture(),data=profession?role(profession):null;f.setRole(data);if(data)f.hotbar.setCharacter(data);const sent=[];
  const args=['characterHotbar','questBook','skillBook','hotbar','skillById','snapshot','selfId','serverOffset','castActive','connected','nextSkillRequestAt','chosenMonster','send','canvas','target'];
  const fn=new Function(...args,'return '+body)(f.adapter,null,null,f.hotbar,id=>({id}),[{id:'self',hp:100,controls:{}}],'self',0,()=>false,true,0,()=>({id:'wolf'}),v=>sent.push(v),{focus(){}},null);
  fn('fireball');assert.equal(sent.length,profession===2?1:0);if(profession===2)assert.deepEqual(sent[0],{type:'skill',skillId:'fireball',targetId:'wolf'});
 }
});
test('actual generated keyboard path cannot resolve nonmage saved keys',()=>{
 const start=staged.indexOf("window.addEventListener('keydown', e => {"),end=staged.indexOf("window.addEventListener('keyup'",start),body=staged.slice(start,end);
 for(const profession of [1,2,3,4,5]){const f=fixture(),data=role(profession);f.setRole(data);f.hotbar.setCharacter(data);let handler,calls=[];
  const captureWindow={addEventListener(type,fn){assert.equal(type,'keydown');handler=fn;}},doc={activeElement:{tagName:'CANVAS'}};
  new Function('window','document','$','characterPanels','connected','questBook','skillBook','hotbar','attributeUI','inventoryUI','useSkill','codes',body)(captureWindow,doc,id=>id==='camp-panel'?{hidden:true}:{open:false},null,true,null,null,f.hotbar,null,null,id=>calls.push(id),new Set());
  handler({code:'Digit1',shiftKey:false,preventDefault(){}});assert.deepEqual(calls,profession===2?['fireball']:[]);
 }
});
console.log(JSON.stringify({passed,originalRuntimeChanged:false,storageUsed:'explicit in-memory spy only',realRolesUsed:false}));
