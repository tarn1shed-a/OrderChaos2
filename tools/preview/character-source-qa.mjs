// Local QA only: explicit transient roles, no saves, accounts, WebSocket or writes.
import{createCharacterSourcePanels}from'./character-source-panels.mjs';
const url=new URL(location.href),profession=Number(url.searchParams.get('profession')||2);
if(![1,2,3,4,5].includes(profession))throw Error('QA职业无效');
const names={1:'战士',2:'法师',3:'游侠',4:'僧侣',5:'血骑士'};
const role=Object.freeze({id:'qa-panel-'+profession,name:'隔离检查'+names[profession],profession,level:3,hp:113,maxHp:140,xp:150,stats:Object.freeze({armor:8}),equipment:Object.freeze({}),look:Object.freeze({})});
const panels=createCharacterSourcePanels();window.characterPanelCandidate=panels;
const source=url.searchParams.get('state')==='known-empty'?{roleId:role.id,attributes:{77:3,138:150,139:7455,145:2},learning:[]}:null;
panels.update(role,{source,trialProgress:{value:30,max:60}});
await(url.searchParams.get('pane')==='attributes'?panels.openAttributes():panels.openSkills());
window.addEventListener('keydown',e=>{if(e.code==='KeyC')panels.openAttributes();if(e.code==='KeyK')panels.openSkills();});
document.documentElement.dataset.qaFixture='isolated-transient-role';
