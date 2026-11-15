import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

// Run the real quest-page keyboard handler. No original assets/game state are
// fabricated here; these are only focus, modal and shortcut boundary checks.
const source=readFileSync(new URL('../deploy/quest_world.mjs',import.meta.url),'utf8');
const begin=source.indexOf("window.addEventListener('keydown',e=>{"),end=source.indexOf("\nwindow.addEventListener('keyup'",begin);
assert.ok(begin>=0&&end>begin);
function fixture(){
  const calls=[],keys=new Set();
  const ctx={connected:true,document:{activeElement:{tagName:'CANVAS'},querySelector:()=>null},
    skills:{isOpen:false,open(){calls.push('open');this.isOpen=true;},close(){calls.push('close');this.isOpen=false;}},
    blocked:()=>ctx.skills.isOpen,stop:()=>calls.push('stop'),moveKeys:new Set(['KeyW']),keys,send:v=>calls.push(v),
    window:{addEventListener:(type,fn)=>{assert.equal(type,'keydown');ctx.handler=fn;}}};
  vm.runInNewContext(source.slice(begin,end),ctx);
  const press=(code,extra={})=>{let prevented=false;ctx.handler({code,preventDefault(){prevented=true;},...extra});return prevented;};
  return {ctx,calls,keys,press};
}
test('K can close the original skills modal while movement is blocked, with no jump or movement leak',()=>{
  const h=fixture();assert.equal(h.press('KeyK'),true);assert.deepEqual(h.calls,['stop','open']);
  h.press('KeyW');h.press('Space');assert.equal(h.keys.size,0);assert.equal(h.calls.length,2);
  assert.equal(h.press('KeyK'),true);assert.deepEqual(h.calls,['stop','open','close']);
  h.press('KeyW');assert.equal(h.keys.has('KeyW'),true);
});
test('selection, text input, modifiers, repeats and disconnected sessions cannot open another character menu',()=>{
  for(const change of [h=>h.ctx.connected=false,h=>h.ctx.document.activeElement.tagName='INPUT',h=>h.ctx.document.querySelector=()=>({})]){
    const h=fixture();change(h);h.press('KeyK');assert.deepEqual(h.calls,[]);
  }
  for(const extra of [{repeat:true},{isComposing:true},{metaKey:true},{ctrlKey:true},{altKey:true}]){
    const h=fixture();h.press('KeyK',extra);assert.deepEqual(h.calls,[]);
  }
});
