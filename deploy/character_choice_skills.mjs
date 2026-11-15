// Read-only routing to the existing original SkillSetting/SkillPassive drawings.
// Session identity is supplied by authenticated welcome, never creation draft.
// No learned/equipped state, shortcuts, requests, storage or progression rules.
export const CHARACTER_CHOICE_SKILL_DEPENDENCIES=Object.freeze([
 '/character-source-panels.mjs','/character-source-state.mjs','/source-ui-svg.js',
 '/character-source-panels.css','/assets/character-source/panels.json',
]);

function sourcePanelStyle(doc){
 return new Promise((resolve,reject)=>{
  const link=doc.createElement('link');link.rel='stylesheet';link.href='/character-source-panels.css';
  const timer=setTimeout(()=>finish(Error('原技能窗口样式载入超时')),10000);
  function finish(error){clearTimeout(timer);link.onload=link.onerror=null;if(error){link.remove();reject(error);}else resolve();}
  link.onload=()=>finish();link.onerror=()=>finish(Error('原技能窗口样式不可用'));doc.head.append(link);
 });
}

export function createCharacterChoiceSkills({readSession,stop=()=>{},beforeOpen=()=>{},focusGame=()=>{},onError=()=>{},
 button=null,document:doc=globalThis.document,
 loadPanels=()=>import('/character-source-panels.mjs'),loadStyle=()=>sourcePanelStyle(doc)}={}){
 if(typeof readSession!=='function')throw Error('Authenticated character session reader required');
 let bound=null,panels=null,loading=null,style=null,revision=0,disposed=false,queue=Promise.resolve();
 const valid=session=>Boolean(session?.connected&&typeof session.character?.id==='string'&&session.character.id.length&&
  Number.isSafeInteger(session.character.profession)&&session.character.profession>=1&&session.character.profession<=5&&
  ((Number.isSafeInteger(session.epoch)&&session.epoch>=0)||(typeof session.epoch==='string'&&session.epoch.length)));
 const same=(a,b)=>Boolean(a&&b&&a.id===b.character.id&&a.profession===b.character.profession&&a.epoch===b.epoch);
 const current=()=>{const session=readSession();return valid(session)&&same(bound,session)?session:null;};
 function menu(enabled){if(!button)return;button.hidden=!enabled;button.disabled=!enabled;
  if(enabled)button.style.removeProperty('display');else button.style.setProperty('display','none');}
 function close(){revision++;panels?.close();}
 function disconnect(){close();bound=null;panels?.update(null,{source:null,trialProgress:null});menu(false);}
 function sync(){
  if(disposed)return false;const session=readSession();
  if(!valid(session)){disconnect();return false;}
  if(!same(bound,session)){close();panels?.update(null,{source:null,trialProgress:null});}
  bound={id:session.character.id,profession:session.character.profession,epoch:session.epoch};
  panels?.update(structuredClone(session.character),{source:null,trialProgress:null});menu(true);return true;
 }
 async function ensure(){
  if(!loading)loading=loadPanels().then(module=>{
   if(typeof module.createCharacterSourcePanels!=='function')throw Error('原技能窗口模块无效');
   if(!disposed)panels=module.createCharacterSourcePanels({
    stop:()=>{if(current())stop();},
    beforeOpen:()=>{if(current())beforeOpen();else panels?.close();},focusGame,
   });return panels;
  }).catch(error=>{loading=null;throw error;});
  if(!style)style=Promise.resolve().then(loadStyle).catch(error=>{style=null;throw error;});
  await Promise.all([loading,style]);return panels;
 }
 function open(){
  if(disposed||!current())return Promise.resolve(false);
  stop();
  const ticket=++revision;
  // Frozen source panels share mutable mount state. Serialize mounts so an old
  // asynchronous drawing response cannot overwrite a later character's page.
  const run=async()=>{
   try{
    if(disposed||ticket!==revision||!current())return false;
    const view=await ensure();
    if(disposed||ticket!==revision||!current())return false;
    view.update(structuredClone(current().character),{source:null,trialProgress:null});
    await view.openSkills();
    if(disposed||ticket!==revision||!current()){view.close();return false;}
    return true;
   }catch(error){if(!disposed&&ticket===revision&&current()){panels?.close();onError(error);}return false;}
  };
  const result=queue.then(run);queue=result.then(()=>{},()=>{});return result;
 }
 const click=()=>{if(panels?.isOpen)close();else void open();};button?.addEventListener('click',click);menu(false);
 return {sync,open,close,disconnect,
  get isOpen(){return Boolean(!disposed&&current()&&panels?.isOpen);},
  dispose(){if(disposed)return;disconnect();disposed=true;button?.removeEventListener('click',click);},
  inspect(){return{bound:bound?{...bound}:null,isOpen:this.isOpen,sourceLearningKnown:false,sourceEquipmentKnown:false};},
 };
}
