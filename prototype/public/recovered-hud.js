import {mountSourceProgress} from './hud-progress.js';
import {SKILLS,skillById} from './skills.js';
import {castActive,castStageName} from './cast-pose.js';

const $=id=>document.getElementById(id);
const text=(id,value)=>{if($(id).textContent!==String(value))$(id).textContent=String(value);};

export function createRecoveredHUD(profile) {
  if(profile?.format!=='oc2-original-hud-v1'||profile.progress.healthGreen.sourceRole!=='self-health')throw new Error('原版状态栏资源不匹配');
  const hp=mountSourceProgress($('field-health-mask'),profile.progress.healthGreen,profile.assets);
  const xp=mountSourceProgress($('field-xp-fill'),profile.progress.experience,profile.assets);
  const cardXP=mountSourceProgress($('card-xp-track'),profile.progress.experience,profile.assets);
  const cooldowns={};
  for(const [id,definition]of [['field-attack','cooldownAttack'],['field-fireball','cooldownSkill'],['field-frost_blast','cooldownSkill']]){
    const element=document.createElement('span');element.className='hud-cooldown';element.setAttribute('aria-hidden','true');
    $(id).querySelector('.attack-art,.skill-art').append(element);
    cooldowns[id]=mountSourceProgress(element,profile.progress[definition],profile.assets);cooldowns[id].set(0);
  }
  // Source control placement is applied by mobile-hud after key settings mount.
  $('field-actions').dataset.layout='original-mobile-operation-panel';
  document.body.classList.add('recovered-hud');
  let portraits;
  function setPlayerPortrait(value){
    if(!portraits)portraits={};portraits.player=value;
    for(const id of ['field-portrait','character-portrait']){$(id).src=value.url;$(id).dataset.mode=value.mode;}
    if(portraits.targetWolf)$('scene').dataset.portraits=`${value.opaquePixels},${portraits.targetWolf.opaquePixels}`;
  }
  function character(data){
    const ratio=data.maxHp>0?Math.max(0,Math.min(1,data.hp/data.maxHp)):0;hp.set(ratio);
    const progress=Math.max(0,Number(data.xp)||0)%60;xp.set(progress/60);cardXP.set(progress/60);
    $('field-xp').value=progress;$('field-xp').max=60;
    text('field-xp-text',`经验 ${progress} / 60`);text('field-name',data.name);text('field-stats',`生命 ${data.hp}/${data.maxHp} · 金币 ${data.gold}`);
    $('field-xp-glow').style.left=`${progress/60*100}%`;$('field-xp-glow').hidden=progress===0;
    $('field-portrait').alt=`${data.name}的角色头像`;$('character-portrait').alt=$('field-portrait').alt;
    document.body.classList.toggle('hud-dead',data.hp<=0);
  }
  function combat({me,enemy,connected,now,attackCooldownMs=700}){
    document.body.classList.toggle('hud-playing',connected);$('field-experience').hidden=!connected;
    const casting=castActive(me?.cast);
    const dead=me&&me.hp<=0,revive=Math.max(0,Math.ceil(((me?.deadUntil||0)-now)/1000));
    text('field-state',dead?`倒地${revive?` · ${revive} 秒后恢复`:' · 等待恢复'}`:casting?`${skillById(me.cast.skillId)?.name||'技能'} · ${castStageName(me.cast.stage)||'施法中'}`:'');
    const attackAt=Math.max(me?.animation?.attackAt||0,me?.cast?.startedAt||0),attackRemaining=Math.max(0,attackAt+attackCooldownMs-now);
    cooldowns['field-attack'].set(attackRemaining/attackCooldownMs);
    $('field-attack').disabled=!connected||!enemy?.alive||!me||dead||casting||attackRemaining>0;
    $('attack').disabled=$('field-attack').disabled;
    for(const skill of Object.values(SKILLS)){
      const remaining=Math.max(0,Math.max(me?.skillReadyAt?.[skill.id]||0,me?.globalReadyAt||0)-now);
      cooldowns[`field-${skill.id}`].set(remaining/Math.max(1,skill.cooldownMs,skill.commonCD||0));
      $(`field-${skill.id}`).classList.toggle('casting',casting&&me.cast.skillId===skill.id);
    }
    $('target-hud').hidden=!connected||!enemy;
    if(enemy){
      text('hud-target-name',enemy.name);$('hud-target-hp').max=enemy.maxHp;$('hud-target-hp').value=enemy.hp;
      text('hud-target-health',`${enemy.hp} / ${enemy.maxHp}`);
      const respawn=Math.max(0,Math.ceil(((enemy.respawnAt||0)-now)/1000));
      const slow=Math.max(0,((enemy.slowUntil||0)-now)/1000);
      text('hud-target-state',!enemy.alive?`已击败${respawn?` · ${respawn} 秒后重生`:''}`:slow>0?`冰霜减速 · ${slow.toFixed(1)}s`:'战斗目标');
      $('target-hud').classList.toggle('dead',!enemy.alive);
    }
  }
  return {character,combat,setPortraits(value){
    portraits=value;
    setPlayerPortrait(value.player);
    $('target-portrait').src=value.targetWolf.url;$('target-portrait').dataset.mode=value.targetWolf.mode;
    $('scene').dataset.portraits=`${value.player.opaquePixels},${value.targetWolf.opaquePixels}`;
  },setPlayerPortrait,get playerPortrait(){return portraits?.player?.url;},clear(){
    document.body.classList.remove('hud-playing','hud-dead');$('target-hud').hidden=true;$('field-experience').hidden=true;
    for(const cooldown of Object.values(cooldowns))cooldown.set(0);
  }};
}
