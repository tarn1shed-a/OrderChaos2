const $=id=>document.getElementById(id),professions={1:'战士',2:'法师',3:'游侠',4:'僧侣',5:'血骑士'};
let report=null,selected=null,loading=false;
const number=value=>Number.isFinite(value)?value.toLocaleString('zh-CN'):'—';
const date=value=>{if(!value)return '—';const d=new Date(value);return Number.isFinite(d.getTime())?d.toLocaleString('zh-CN',{hour12:false}):'—';};
async function api(path,body){const response=await fetch('/__admin/'+path,{method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),cache:'no-store'});const data=await response.json();if(!response.ok){if(response.status===401)showLogin();throw Error(data.error||'请求失败');}return data;}
function showLogin(){report=null;selected=null;$('dashboard').hidden=true;$('login-panel').hidden=false;$('logout').hidden=true;$('players').replaceChildren();$('detail-fields').replaceChildren();$('password').value='';}
function showDashboard(){$('dashboard').hidden=false;$('login-panel').hidden=true;$('logout').hidden=false;}
function detail(player){
 selected=player.id;$('detail').hidden=false;$('detail-title').textContent=player.name;
 const fields=[['角色 ID',player.id],['在线状态',player.online?'在线':'离线'],['职业',professions[player.profession]||'未知'],['等级 / 经验',number(player.level)+' / '+number(player.xp)],['生命',number(player.hp)+' / '+number(player.maxHp)],['金币 / 击杀',number(player.gold)+' / '+number(player.kills)],['房间 / 场景',player.online?player.room+' / '+player.scene:'—'],['本次进入',date(player.connectedAt)],['坐标',player.position?[player.position.x,player.position.height,player.position.y].map(v=>Number.isFinite(v)?v.toFixed(3):'—').join(', '):'—'],['背包物品总数',number(player.inventoryItems)],['装备',Object.entries(player.equipment).map(([slot,item])=>slot+': '+item).join('；')||'—'],['创建时间',date(player.createdAt)],['最近角色更新',date(player.updatedAt)]];
 $('detail-fields').replaceChildren(...fields.flatMap(([name,value])=>{const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=name;dd.textContent=value;return[dt,dd];}));
}
function render(){
 if(!report)return;$('online').textContent=number(report.online);$('total').textContent=number(report.total);$('updated').textContent=date(report.at);
 const search=$('search').value.trim().toLowerCase(),players=report.players.filter(p=>(!$('only-online').checked||p.online)&&[p.name,p.id,p.room||''].some(v=>v.toLowerCase().includes(search)));
 $('players').replaceChildren(...players.map(player=>{
  const row=document.createElement('tr'),cell=value=>{const td=document.createElement('td');td.textContent=value;row.append(td);return td;};
  const badge=document.createElement('span');badge.className='badge'+(player.online?' online':'');badge.textContent=player.online?'在线':'离线';cell('').append(badge);
  const name=cell(''),strong=document.createElement('span'),id=document.createElement('span');strong.className='name';strong.textContent=player.name;id.className='id';id.textContent=player.id.slice(0,8);name.append(strong,id);
  for(const value of [professions[player.profession]||'未知',number(player.level),number(player.xp),number(player.hp)+' / '+number(player.maxHp),number(player.gold),player.room||'—',date(player.connectedAt)])cell(value);
  const button=document.createElement('button');button.textContent='详情';button.addEventListener('click',()=>detail(player));cell('').append(button);return row;
 }));$('empty').hidden=players.length!==0;
 const player=report.players.find(p=>p.id===selected);if(player)detail(player);
}
async function refresh(){if(loading)return;loading=true;$('refresh').disabled=true;try{report=await api('players');showDashboard();$('message').textContent='';render();}catch(error){$('message').textContent=error.message;}finally{loading=false;$('refresh').disabled=false;}}
$('login').addEventListener('submit',async event=>{event.preventDefault();const button=event.submitter;button.disabled=true;try{await api('login',{password:$('password').value});$('password').value='';await refresh();}catch(error){$('message').textContent=error.message;}finally{button.disabled=false;}});
$('logout').addEventListener('click',async()=>{try{await api('logout',{});showLogin();$('message').textContent='已退出后台';}catch(error){$('message').textContent=error.message;}});
$('refresh').addEventListener('click',refresh);$('search').addEventListener('input',render);$('only-online').addEventListener('change',render);$('close-detail').addEventListener('click',()=>{selected=null;$('detail').hidden=true;});
setInterval(()=>{if(report&&!document.hidden)refresh();},5000);
try{const state=await api('session');if(!state.enabled){$('message').textContent='管理后台尚未启用';$('login-panel').hidden=true;}else if(state.authenticated)await refresh();}catch(error){$('message').textContent=error.message;}
