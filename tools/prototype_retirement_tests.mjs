import {test}from'node:test';import assert from'node:assert/strict';
import{retirePrototypeHTML,retiredRoute}from'../deploy/retire_prototype.mjs';
import{readFileSync}from'node:fs';import{entryServer}from'../deploy/entry_manage.mjs';
test('retired lab links redirect to the current source-entry flow and preserve invitations and explicit position reset',()=>{
 for(const path of ['/explore.html?room=DYNAMIC-01&lab=collision','/explore-map.html?lab=collision&room=DYNAMIC-01'])assert.equal(retiredRoute(new URL(path,'https://game.invalid')),'/explore-map.html?room=RAILWAY-01&sourceProfile=APK_Default');
 const out=retiredRoute(new URL('https://game.invalid/explore.html?room=FRIENDS-01&trialEntry=cinematic7&lab=collision'));
 assert(out.includes('room=FRIENDS-01'));assert(out.includes('trialEntry=cinematic7'));assert(!out.includes('lab='));
 assert.equal(retiredRoute(new URL('https://game.invalid/explore-map.html?room=RAILWAY-01')),null);
});
test('production HTML removes the test link and hides unverified sidebar and head cards without making substitute art',()=>{
 const old='<button id="camp-toggle">营地</button><aside id="camp-panel" hidden><p><a href="/explore.html?room=DYNAMIC-01&amp;lab=collision">进入动态碰撞验证场</a>（本地试验摆放）</p><div id="character-panel">old binding</div></aside><div id="labels"></div><canvas id="scene"></canvas>';
 const html=retirePrototypeHTML(old);assert(!html.includes('lab=collision'));assert(!html.includes('进入动态碰撞'));assert(html.includes('<button hidden aria-hidden="true" id="camp-toggle"'));
 assert(html.includes('<aside id="camp-panel" inert'));assert(html.includes('data-unrestored="original-world-name-renderer"'));assert(html.includes('id="character-panel"'));assert(html.includes('<canvas id="scene"></canvas>'));
 assert.equal(retirePrototypeHTML(html),html);
});
test('cached prototype lab clients are rejected before any account/save access',t=>{
 let source;try{source=readFileSync(new URL('../analysis/raw/showcase-20261110/running-preview/prototype/server.mjs',import.meta.url),'utf8');}catch{t.skip('Private reviewed runtime stays local');return;}
 const code=entryServer(source,'file:///trace.mjs');assert(code.indexOf('if(msg.lab!==undefined)return reject')<code.indexOf('store.resolveCharacter('));
 assert(code.includes('ws.motion.restoreHeight(ws.player,position.groundY)'));
});
