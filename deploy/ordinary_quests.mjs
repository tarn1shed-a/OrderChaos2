// Compatible execution of explicitly exported original ordinary-quest data.
// This is new server code, not a recovered original server or script VM.
import {readFileSync,writeFileSync,mkdirSync,renameSync,unlinkSync,openSync,closeSync,fsyncSync,existsSync} from 'node:fs';
import {dirname} from 'node:path';
import {randomUUID} from 'node:crypto';

const FORMAT='oc2-compatible-ordinary-quests-v1';
const STATE='oc2-compatible-quest-ledger-v1';
const uint=x=>Number.isSafeInteger(x)&&x>=0&&x<=1_000_000_000;
const positive=x=>uint(x)&&x>0;
const object=x=>x!==null&&typeof x==='object'&&!Array.isArray(x);
const copy=x=>structuredClone(x);
const key=x=>String(x);
function requireValue(ok,message){if(!ok)throw Error(message);}
function unique(rows,label){const result=new Map();for(const row of rows){requireValue(!result.has(row.id),'重复'+label);result.set(row.id,row);}return result;}

export function checkOrdinaryQuestProfile(profile){
  profile=copy(profile);
  requireValue(profile?.format===FORMAT&&profile.originalServerRecovered===false,'普通任务执行资料格式不符');
  requireValue(positive(profile.mapId)&&Array.isArray(profile.quests)&&profile.quests.length>0,'缺少原地图或任务');
  requireValue(Array.isArray(profile.actors)&&Array.isArray(profile.objects),'缺少原对象资料');
  const quests=unique(profile.quests,'任务'),actors=unique(profile.actors,'人物'),objects=unique(profile.objects,'采集对象');
  for(const actor of [...actors.values(),...objects.values()]){
    requireValue(typeof actor.id==='string'&&/^[a-z]+:[0-9]+$/.test(actor.id)&&positive(actor.entry),'对象身份无效');
    requireValue(actor.mapId===profile.mapId&&Array.isArray(actor.position)&&actor.position.length===3&&actor.position.every(Number.isFinite),'对象原位置无效');
    requireValue(Number.isFinite(actor.range)&&actor.range>0&&actor.range<=10,'交互距离尚未核对');
  }
  for(const quest of quests.values()){
    requireValue(positive(quest.id)&&quest.sourceScript===''&&uint(quest.minLevel),'普通任务资料无效');
    requireValue(['title','detail','objectiveText','incomplete','completion'].every(k=>typeof quest[k]==='string'),'原任务文字不完整');
    requireValue([quest.startActor,quest.finishActor].every(id=>actors.has(id)),'原交接人物缺失');
    requireValue(Array.isArray(quest.prerequisites)&&quest.prerequisites.every(positive)&&Array.isArray(quest.removeQuests)&&quest.removeQuests.every(positive),'前置任务资料无效');
    const o=quest.collect;
    requireValue(object(o)&&positive(o.itemId)&&positive(o.count)&&o.sourceType===2&&positive(o.sourceIndex),'仅支持已核对的原收集目标');
    requireValue(Array.isArray(o.objectIds)&&o.objectIds.length>=o.count&&new Set(o.objectIds).size===o.objectIds.length&&o.objectIds.every(id=>objects.has(id)),'原采集摆放不完整');
    requireValue(quest.finishSourceType===6&&quest.takeBackAll===true,'原交谈或交回资料尚未支持');
    requireValue(object(quest.reward)&&['money','xp','favor'].every(k=>uint(quest.reward[k]))&&Array.isArray(quest.reward.items),'原奖励资料无效');
    for(const item of quest.reward.items)requireValue(positive(item.id)&&positive(item.count)&&item.guaranteed===true,'未支持的奖励选择');
  }
  return {profile:copy(profile),quests,actors,objects};
}

function emptyRole(){return {revision:0,quests:{},items:{},rewards:{xp:0,money:0,favor:0,items:{}}};}
export function checkQuestRole(value,quests){
  requireValue(object(value)&&uint(value.revision)&&object(value.quests)&&object(value.items)&&object(value.rewards),'任务存档结构无效');
  if(value.position!==undefined)requireValue(object(value.position)&&['x','y','groundY'].every(k=>Number.isFinite(value.position[k])),'任务地图位置无效');
  requireValue(['xp','money','favor'].every(k=>uint(value.rewards[k]))&&object(value.rewards.items),'奖励存档无效');
  for(const items of [value.items,value.rewards.items])for(const [id,count]of Object.entries(items))requireValue(/^[1-9][0-9]*$/.test(id)&&positive(Number(id))&&uint(count),'物品存档无效');
  for(const [id,state]of Object.entries(value.quests)){
    const quest=quests.get(Number(id));requireValue(key(Number(id))===id,'任务编号格式无效');
    requireValue(quest&&object(state)&&['accepted','ready','completed'].includes(state.phase)&&Array.isArray(state.collected),'未知任务存档');
    requireValue(new Set(state.collected).size===state.collected.length&&state.collected.length<=quest.collect.count&&state.collected.every(x=>quest.collect.objectIds.includes(x)),'采集进度无效');
    requireValue(state.phase==='accepted'?state.collected.length<quest.collect.count:state.collected.length===quest.collect.count,'任务目标和状态不一致');
    requireValue(Number.isSafeInteger(state.acceptedAt)&&state.acceptedAt>=0,'接取时间无效');
    if(state.phase==='completed')requireValue(Number.isSafeInteger(state.completedAt)&&state.completedAt>=state.acceptedAt,'提交时间无效');
  }
  // Persisted totals are derived again, so corrupt state cannot silently grant
  // money/items or turn an uncompleted quest into a paid completion.
  const expected={xp:0,money:0,favor:0,items:{}};
  const carried={};
  for(const [id,state]of Object.entries(value.quests)){
    const quest=quests.get(Number(id));
    if(state.phase==='completed'){
      for(const name of ['xp','money','favor'])expected[name]+=quest.reward[name];
      for(const item of quest.reward.items)expected.items[key(item.id)]=(expected.items[key(item.id)]||0)+item.count;
    }else if(state.collected.length)carried[key(quest.collect.itemId)]=(carried[key(quest.collect.itemId)]||0)+state.collected.length;
  }
  for(const name of ['xp','money','favor'])requireValue(expected[name]===value.rewards[name],'奖励总计与完成记录不一致');
  const equal=(a,b)=>Object.keys(a).length===Object.keys(b).length&&Object.keys(a).every(k=>a[k]===b[k]);
  requireValue(equal(expected.items,value.rewards.items)&&equal(carried,value.items),'物品总计与任务记录不一致');
  return value;
}

export class OrdinaryQuestLedger{
  constructor(profile,{saveFile=null,clock=Date.now,write=null}={}){
    Object.assign(this,checkOrdinaryQuestProfile(profile));this.saveFile=saveFile;this.clock=clock;this.write=write;this.roles={};this.dirty=false;
    if(saveFile&&existsSync(saveFile)){
      const stored=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(readFileSync(saveFile)));
      requireValue(stored.format===STATE&&object(stored.roles),'任务存档格式不符，原文件保留');
      for(const [id,role]of Object.entries(stored.roles)){
        requireValue(/^[0-9a-f-]{36}$/.test(id),'任务存档角色无效');checkQuestRole(role,this.quests);
      }
      this.roles=stored.roles;
    }
  }
  role(id){requireValue(typeof id==='string'&&/^[0-9a-f-]{36}$/.test(id),'角色身份无效');return this.roles[id]||emptyRole();}
  position(id){return copy(this.role(id).position);}
  savePosition(id,player){
    if(!(player.grounded||player.swimming)||!['x','y','worldY'].every(k=>Number.isFinite(player[k])))return;
    const position={x:player.x,y:player.y,groundY:player.worldY},before=this.role(id);
    if(JSON.stringify(before.position)===JSON.stringify(position))return;
    this.roles={...this.roles,[id]:{...before,position}};this.dirty=true;
  }
  flush(){if(this.dirty){this.persist(this.roles);this.dirty=false;}}
  persist(next){
    const raw=JSON.stringify({format:STATE,roles:next},null,2)+'\n';
    if(this.write){this.write(raw);return;}
    if(!this.saveFile)return;
    mkdirSync(dirname(this.saveFile),{recursive:true,mode:0o700});const temp=this.saveFile+'.'+randomUUID()+'.tmp';
    try{
      writeFileSync(temp,raw,{flag:'wx',mode:0o600});const fd=openSync(temp,'r');try{fsyncSync(fd);}finally{closeSync(fd);}
      renameSync(temp,this.saveFile);
      // The task state and its rewards have one commit point, separate from
      // legacy character files. No two-file "complete then grant" window.
    }catch(error){try{unlinkSync(temp);}catch{}throw Error('任务存档写入失败，进度和奖励未提交：'+error.message);}
  }
  proximity(context,actor){
    requireValue(context.mapId===actor.mapId,'请在原任务所在地图操作');
    requireValue(Array.isArray(context.position)&&context.position.length===3&&context.position.every(Number.isFinite),'服务端角色位置未就绪');
    requireValue(Math.hypot(...context.position.map((v,i)=>v-actor.position[i]))<=actor.range,'距离太远，请靠近后再操作');
    requireValue(context.alive===true&&!context.inspector,'当前角色不能交互');
  }
  quest(id){const result=this.quests.get(id);requireValue(result,'此任务尚未接入');return result;}
  eligible(context,quest,role){
    requireValue(uint(context.level)&&context.level>=quest.minLevel,'角色等级不足');
    requireValue(quest.prerequisites.every(id=>role.quests[key(id)]?.phase==='completed'),'尚未完成原前置任务');
    // RemoveQuests is not silently translated into deletion of legacy quests.
    // The currently supported branch has none of these records active.
    requireValue(!quest.removeQuests.some(id=>role.quests[key(id)]&&role.quests[key(id)].phase!=='completed'),'存在尚未处理的原互斥任务');
  }
  query(context,id){
    const quest=this.quest(id),role=this.role(context.characterId),state=role.quests[key(id)];
    requireValue(context.mapId===this.profile.mapId,'请先进入原任务地图');this.eligible(context,quest,role);
    const status=!state?6:state.phase==='accepted'?4:state.phase==='ready'?9:0;
    return {origin:'compatible-quest-layer',questId:id,revision:role.revision,Status:status,
      Title:quest.title,Detail:quest.detail,Objective:quest.objectiveText,Incomplete:quest.incomplete,Completion:quest.completion,
      phase:state?.phase||'available',hasReward:true,HasCollectedTbItem:state?.phase==='ready',IsFailed:false,IsInTuto:false,
      NumGold:quest.reward.money,NumXp:quest.reward.xp,NumFever:quest.reward.favor,NumAdvExp:0,
      NumItem:quest.reward.items.length,NumItemOp:0,NumItemTb:state?.phase==='ready'?1:0,
      rewards:copy(quest.reward.items),fixedItems:copy(quest.reward.items),returnItems:state?.phase==='ready'?[{...this.profile.items?.[key(quest.collect.itemId)],id:quest.collect.itemId,count:quest.collect.count}]:[],
      progress:{current:state?.collected.length||0,required:quest.collect.count,text:quest.collect.text},rewarded:state?.phase==='completed'};
  }
  snapshot(characterId){
    const role=this.role(characterId);
    return {origin:'compatible-quest-layer',mapId:this.profile.mapId,revision:role.revision,
      quests:[...this.quests.values()].flatMap(q=>{
        const state=role.quests[key(q.id)];if(!state||state.phase==='completed')return [];
        return [{id:q.id,title:q.title,status:state.phase==='ready'?9:4,objective:q.collect.text,current:state.collected.length,required:q.collect.count}];
      }),collectedObjectIds:[...new Set(Object.values(role.quests).flatMap(s=>s.phase==='completed'?[]:s.collected))],
      completedQuestIds:Object.entries(role.quests).flatMap(([id,s])=>s.phase==='completed'?[Number(id)]:[]),
      inventory:copy(role.items),rewards:copy(role.rewards)};
  }
  validateCollect(context,command){
    requireValue(object(command)&&command.type==='collect'&&positive(command.questId)&&uint(command.revision),'任务请求无效');
    const quest=this.quest(command.questId),role=this.role(context.characterId),state=role.quests[key(quest.id)];
    requireValue(command.revision===role.revision,'任务状态已更新，请重新打开');
    this.eligible(context,quest,role);
    requireValue(state?.phase==='accepted','请先接取任务或交回已收集物品');
    requireValue(quest.collect.objectIds.includes(command.objectId),'此对象不属于当前目标');
    this.proximity(context,this.objects.get(command.objectId));
    requireValue(!state.collected.includes(command.objectId),'此处已经收集过');
    return {quest,object:this.objects.get(command.objectId)};
  }
  act(context,command){
    requireValue(object(command)&&positive(command.questId)&&uint(command.revision),'任务请求无效');
    requireValue(['accept','collect','complete','abandon'].includes(command.type),'任务操作尚未支持');
    const quest=this.quest(command.questId),before=this.role(context.characterId);
    requireValue(command.revision===before.revision,'任务状态已更新，请重新打开');
    this.eligible(context,quest,before);const role=copy(before),id=key(quest.id),state=role.quests[id];
    if(command.type==='accept'){
      this.proximity(context,this.actors.get(quest.startActor));requireValue(!state,'任务已经接取或完成');
      role.quests[id]={phase:'accepted',collected:[],acceptedAt:this.clock()};
    }else if(command.type==='collect'){
      this.validateCollect(context,command);
      state.collected.push(command.objectId);role.items[key(quest.collect.itemId)]=(role.items[key(quest.collect.itemId)]||0)+1;
      if(state.collected.length===quest.collect.count)state.phase='ready';
    }else if(command.type==='complete'){
      this.proximity(context,this.actors.get(quest.finishActor));requireValue(state?.phase==='ready','任务尚未完成或已经交付');
      requireValue(role.items[key(quest.collect.itemId)]>=quest.collect.count,'交回物品不足');
      delete role.items[key(quest.collect.itemId)];state.phase='completed';state.completedAt=this.clock();
      for(const name of ['xp','money','favor']){role.rewards[name]+=quest.reward[name];requireValue(uint(role.rewards[name]),'奖励总量超出范围');}
      for(const item of quest.reward.items){const k=key(item.id);role.rewards.items[k]=(role.rewards.items[k]||0)+item.count;requireValue(uint(role.rewards.items[k]),'奖励物品超出范围');}
    }else{
      requireValue(state&&state.phase!=='completed','没有可放弃的任务');
      requireValue(context.mapId===this.profile.mapId&&context.alive===true&&!context.inspector,'当前角色不能放弃任务');
      delete role.items[key(quest.collect.itemId)];delete role.quests[id];
    }
    role.revision++;checkQuestRole(role,this.quests);
    const next={...this.roles,[context.characterId]:role};this.persist(next);this.roles=next;this.dirty=false;
    return this.snapshot(context.characterId);
  }
}
