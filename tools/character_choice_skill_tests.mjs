import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createCharacterChoiceSkills,CHARACTER_CHOICE_SKILL_DEPENDENCIES} from '../deploy/character_choice_skills.mjs';
import {sourceProfessionSkills} from './preview/character-source-state.mjs';
import {createPlayerChoiceRegistry} from '../deploy/player_choice_registry.mjs';

const root=fileURLToPath(new URL('..',import.meta.url)),tick=()=>new Promise(resolve=>setImmediate(resolve));
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return{promise,resolve,reject};};
const role=(profession,id='role-'+profession)=>({id,profession,name:'显式角色夹具',level:60,hotbar:null,sourceAvatar:{sourceModelId:1}});
class Button extends EventTarget{
 constructor(){super();this.hidden=false;this.disabled=false;this.values=new Map();this.style={setProperty:(k,v)=>this.values.set(k,v),removeProperty:k=>this.values.delete(k)};}
}
function harness(extra={}){
 let session={connected:true,character:role(2),epoch:1},panel;
 const button=new Button(),calls=[],errors=[];
 const loadPanels=async()=>({createCharacterSourcePanels(options){
  calls.push(['factory',Object.keys(options)]);
  let value=null,opened=false,ticket=0;
  panel={update(next,input){value=next;calls.push(['update',structuredClone(next),input]);},
   close(){ticket++;opened=false;calls.push(['close']);},get isOpen(){return opened;},
   async openSkills(){const own=++ticket;calls.push(['open',value?.profession]);options.beforeOpen();options.stop();
    await extra.mount?.();if(own===ticket){opened=true;calls.push(['shown',value?.profession]);}},
   inspect(){return{role:value};}};return panel;
 }});
 const helper=createCharacterChoiceSkills({readSession:()=>session,button,loadPanels:extra.loadPanels||loadPanels,
  loadStyle:extra.loadStyle||(()=>Promise.resolve()),onError:error=>errors.push(error.message)});
 return{helper,button,calls,errors,get panel(){return panel;},get session(){return session;},set session(v){session=v;},loadPanels};
}

test('five authenticated numeric professions use the same original window without source grants',async()=>{
 const h=harness();
 for(let profession=1;profession<=5;profession++){
  h.session={connected:true,character:role(profession),epoch:profession};assert.equal(h.helper.sync(),true);
  assert.equal(h.button.hidden,false);assert.equal(h.button.disabled,false);assert.equal(await h.helper.open(),true);
  assert.equal(h.panel.inspect().role.profession,profession);assert.equal(h.helper.isOpen,true);
  const update=h.calls.filter(c=>c[0]==='update'&&c[1]).at(-1);assert.deepEqual(update[2],{source:null,trialProgress:null});
  assert.deepEqual(update[1],h.session.character);assert.equal(h.helper.inspect().sourceLearningKnown,false);
 }
 assert.deepEqual(h.calls.filter(c=>c[0]==='shown').map(c=>c[1]),[1,2,3,4,5]);
 assert.deepEqual(h.calls.find(c=>c[0]==='factory')[1],['stop','beforeOpen','focusGame']);h.helper.dispose();
});

test('creation draft, disconnected identity, unknown epoch and string profession never open',async()=>{
 const h=harness();
 for(const session of [null,{connected:false,character:role(2),epoch:1},{connected:true,character:role('2'),epoch:1},
  {connected:true,character:role(0),epoch:1},{connected:true,character:role(6),epoch:1},{connected:true,character:role(2)},
  {connected:true,character:{profession:2,name:'创角草稿'},epoch:1}]){
  h.session=session;assert.equal(h.helper.sync(),false);assert.equal(await h.helper.open(),false);assert.equal(h.button.hidden,true);
 }
 assert.equal(h.calls.length,0);assert.throws(()=>createCharacterChoiceSkills());h.helper.dispose();
});

test('late module reply cannot show the previous class after a character switch',async()=>{
 const module=deferred(),h=harness({loadPanels:()=>module.promise});h.helper.sync();const first=h.helper.open();await tick();
 h.session={connected:true,character:role(3),epoch:2};h.helper.sync();const second=h.helper.open();
 module.resolve(await h.loadPanels());assert.equal(await first,false);assert.equal(await second,true);
 assert.deepEqual(h.calls.filter(c=>c[0]==='shown').map(c=>c[1]),[3]);assert.equal(h.panel.inspect().role.id,'role-3');h.helper.dispose();
});

test('pending original drawing mounts serialize and close invalidates the old request',async()=>{
 const drawing=deferred();let active=0,max=0,count=0;
 const h=harness({mount:async()=>{active++;max=Math.max(max,active);if(++count===1)await drawing.promise;active--;}});
 h.helper.sync();const first=h.helper.open();await tick();h.helper.close();
 h.session={connected:true,character:role(1),epoch:2};h.helper.sync();const second=h.helper.open();await tick();
 assert.equal(count,1);drawing.resolve();assert.equal(await first,false);assert.equal(await second,true);
 assert.equal(max,1);assert.deepEqual(h.calls.filter(c=>c[0]==='shown').map(c=>c[1]),[1]);h.helper.dispose();
});

test('entering selection clears old class and blocks late CSS/module replies until a new welcome sync',async()=>{
 const css=deferred(),h=harness({loadStyle:()=>css.promise});h.helper.sync();const opening=h.helper.open();await tick();
 h.helper.disconnect();assert.equal(h.helper.inspect().bound,null);assert.equal(h.button.hidden,true);
 css.resolve();assert.equal(await opening,false);assert.equal(await h.helper.open(),false);assert.equal(h.helper.isOpen,false);
 h.session={connected:true,character:role(5),epoch:2};h.helper.sync();assert.equal(await h.helper.open(),true);
 assert.deepEqual(h.calls.filter(c=>c[0]==='shown').map(c=>c[1]),[5]);h.helper.dispose();
});

test('a late view that reopens itself after disconnect is physically closed without another open request',async()=>{
 const drawing=deferred();let actualOpen=false,closed=0;
 const h=harness({loadPanels:async()=>({createCharacterSourcePanels:()=>({update(){},
  close(){actualOpen=false;closed++;},get isOpen(){return actualOpen;},
  async openSkills(){await drawing.promise;actualOpen=true;}})})});
 h.helper.sync();const opening=h.helper.open();await tick();h.helper.disconnect();const alreadyClosed=closed;
 drawing.resolve();assert.equal(await opening,false);assert.equal(actualOpen,false);assert.equal(closed,alreadyClosed+1);
 h.helper.dispose();
});

test('same UUID with a changed profession or epoch closes and clears the prior panel',async()=>{
 const h=harness();h.helper.sync();await h.helper.open();
 for(const change of [{character:role(4,'role-2'),epoch:1},{character:role(4,'role-2'),epoch:2}]){
  h.session={connected:true,...change};h.helper.sync();assert.equal(h.helper.isOpen,false);
  assert.equal(h.panel.inspect().role.profession,4);assert.equal(await h.helper.open(),true);
 }
 assert(h.calls.some(c=>c[0]==='update'&&c[1]===null));h.helper.dispose();
});

test('loading failures stay local to opening the menu, report once, and permit retry',async()=>{
 let count=0;const h=harness({loadStyle:async()=>{if(++count===1)throw Error('显式样式失败夹具');}});
 h.helper.sync();assert.equal(await h.helper.open(),false);assert.deepEqual(h.errors,['显式样式失败夹具']);
 assert.equal(h.helper.isOpen,false);assert.equal(h.button.hidden,false);assert.equal(await h.helper.open(),true);h.helper.dispose();
});

test('default CSS loader is lazy and its actual link error leaves normal session state untouched',async()=>{
 let link=null,removed=false,created=0,open=false;const session={connected:true,character:role(1),epoch:1},before=structuredClone(session),errors=[];
 const doc={createElement(tag){assert.equal(tag,'link');created++;return{remove(){removed=true;}};},head:{append(node){link=node;}}};
 const helper=createCharacterChoiceSkills({readSession:()=>session,document:doc,onError:e=>errors.push(e.message),
  loadPanels:async()=>({createCharacterSourcePanels:()=>({update(){},close(){open=false;},get isOpen(){return open;},async openSkills(){open=true;}})})});
 helper.sync();assert.equal(created,0);const opening=helper.open();await tick();
 assert.equal(link.rel,'stylesheet');assert.equal(link.href,'/character-source-panels.css');link.onerror();
 assert.equal(await opening,false);assert.equal(removed,true);assert.equal(open,false);assert.equal(errors.length,1);assert.deepEqual(session,before);helper.dispose();
});

test('existing menu toggles only skills, and disposal prevents later creation or events',async()=>{
 const h=harness();h.helper.sync();h.button.dispatchEvent(new Event('click'));await tick();assert.equal(h.helper.isOpen,true);
 h.button.dispatchEvent(new Event('click'));assert.equal(h.helper.isOpen,false);h.helper.dispose();
 const count=h.calls.length;h.button.dispatchEvent(new Event('click'));assert.equal(await h.helper.open(),false);assert.equal(h.helper.sync(),false);assert.equal(h.calls.length,count);
});

test('actual deployed class-index expression maps UI order to authenticated profession integers',()=>{
 const entry=readFileSync(resolve(root,'deploy/entry_ui.mjs'),'utf8'),expression=entry.match(/profession:(\[1,3,2,5,4\]\[draft\.cls\])/);
 assert(expression,'Original five-class create request expression changed');
 const selected=Function('draft','return '+expression[1]);assert.deepEqual([0,1,2,3,4].map(cls=>selected({cls})),[1,3,2,5,4]);
});

test('source projection keeps catalog, learned state and equipped state separate',()=>{
 const profile={catalogs:Object.fromEntries([1,2,3,4,5].map(p=>[p,[{skillId:p*100,kind:'active',runes:[{index:0,requirement:{needlevel:1}}]}]]))};
 for(let profession=1;profession<=5;profession++){
  const player=role(profession),rows=sourceProfessionSkills(profile,profession,null,player.id);
  assert.equal(rows[0].skillId,profession*100);assert.equal(rows[0].runes[0].learned,null);assert.equal(rows[0].runes[0].locked,null);
  const source={roleId:player.id,attributes:{77:60,127:profession},learning:[]};
  assert.equal(sourceProfessionSkills(profile,profession,source,player.id)[0].runes[0].learned,false);
  assert.equal(sourceProfessionSkills(profile,profession,{...source,roleId:'old-role'},player.id)[0].runes[0].learned,null);
  assert(!('equipped'in rows[0]));
 }
 assert(CHARACTER_CHOICE_SKILL_DEPENDENCIES.includes('/assets/character-source/panels.json'));
});

const registryFile=resolve(root,'analysis/raw/player-choice-recovery-20261115/registry-v1.json'),
 panelFile=resolve(root,'analysis/raw/character-progression-20261114/panel-candidate-final/public/assets/character-source/panels.json');
test('private original 45 choices feed their actual five catalogs, all learning and slots remain unknown',
 {skip:!existsSync(registryFile)||!existsSync(panelFile)},async()=>{
 const profile=JSON.parse(readFileSync(panelFile)),choices=JSON.parse(readFileSync(registryFile)),registry=createPlayerChoiceRegistry(choices),h=harness();let count=0;
 for(const body of choices.bodies)for(const choice of body.choices){
  const avatar=registry.draft({race:body.uiRace,gender:body.gender,profession:choice.profession});
  h.session={connected:true,character:{...role(choice.profession,'choice-'+count),sourceAvatar:avatar},epoch:++count};h.helper.sync();await h.helper.open();
  const actual=h.panel.inspect().role,rows=sourceProfessionSkills(profile,actual.profession,null,actual.id);
  assert.equal(actual.sourceAvatar.sourceModelId,body.sourceModelId);assert.equal(rows.length,14);
  assert.equal(rows.filter(r=>r.kind==='active').length,9);assert.equal(rows.filter(r=>r.kind==='passive').length,5);
  assert(rows.every(row=>row.runes.every(r=>r.learned===null&&r.locked===null)));
  assert.equal(h.helper.inspect().sourceEquipmentKnown,false);
 }
 assert.equal(count,45);h.helper.dispose();
});
