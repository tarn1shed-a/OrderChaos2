// Original current-objective panel over real compatible per-character progress.
// No quest approval, native messages or automatic pathfinding are fabricated.
const PIN='760866b49cbd948764e93183c7ba5cc32605d408e91b7f052f52856837cdfe2c';
const METHOD='b510e0688ce1cb5e7371ba2ddd1bc495c8c673d247c3cf7f62a06055e41041d5';
const NS='http://www.w3.org/2000/svg';
export function trackedObjective(profile,state){
  if(profile?.format!=='oc2-original-ordinary-tracking-v1'||profile.sourceSHA256!==PIN||
    profile.method?.codeSHA256!==METHOD||profile.questId!==461||profile.steps?.length!==2)throw Error('Verified original objective profile required');
  if(!state)return null;
  if(state.origin!=='compatible-quest-layer'||!Array.isArray(state.quests)||!Array.isArray(state.completedQuestIds))throw Error('Actual compatible task state required');
  const rows=state.quests.filter(q=>q.id===profile.questId);
  if(rows.length>1||rows.length&&state.completedQuestIds.includes(profile.questId))throw Error('Contradictory current task state');
  const q=rows[0];if(!q)return null;
  const collect=profile.steps[0],finish=profile.steps[1];
  if(collect.sourceType!==2||collect.total!==4||finish.sourceType!==6||finish.total!==0||
    ![4,9].includes(q.status)||!Number.isInteger(q.current)||q.required!==collect.total||
    q.current<0||q.current>q.required||(q.status===9)!==(q.current===q.required))throw Error('Original objective progress differs');
  const step=q.status===9?finish:collect;
  if(typeof step.text!=='string'||!profile.assets[step.icon])throw Error('Original objective text/icon unavailable');
  return {...step,questId:q.id,current:q.status===9?0:q.current};
}

// Execute this pinned AS method, with text measurement/display objects as
// named browser boundaries. Only the original normal-quest branch is exposed.
export function formatTrackedObjective(profile,objective,metrics){
  if(profile.sourceSHA256!==PIN||profile.method?.codeSHA256!==METHOD)throw Error('Pinned original objective method required');
  if(!objective||![0,4].includes(objective.total)||![2,6].includes(objective.sourceType)||
    !Number.isInteger(objective.current)||objective.current<0||objective.current>objective.total)throw Error('Verified ordinary objective required');
  for(const k of ['width','y','counterWidth'])if(!Number.isFinite(metrics?.[k])||metrics[k]<0)throw Error('Original text metrics required');
  const nodes={stepText:{width:metrics.width,y:metrics.y},stepPercentNum:{width:metrics.counterWidth},
    stepicon:{},stepPercent:{},scrollText:{}};
  const self={...profile.constants,_language_id:profile.languages.LANG_SC,m_InitialTextWidth:metrics.width,m_InitialTextPosY:metrics.y};
  const item={children:nodes},locals={0:self,1:item,2:profile.constants.NORMAL_QUEST,
    3:objective.current,4:objective.total,5:objective.text,6:objective.icon,7:objective.pathFinding};
  const stack=[],code=profile.method.instructions,by=new Map(code.map((r,i)=>[r.at,i]));let pc=0,steps=0;
  const pop=()=>{if(!stack.length)throw Error('Original objective stack underflow');return stack.pop();};
  const jump=at=>{if(!by.has(at))throw Error('Original objective branch unavailable');pc=by.get(at);};
  while(pc<code.length){
    if(++steps>2000)throw Error('Original objective instruction bound');
    const r=code[pc++],op=r.op,a=r.args;
    if(op==='pushscope'||op==='pop')pop();
    else if(op==='coerce'||op==='label'){}
    else if(op.startsWith('getlocal'))stack.push(locals[op==='getlocal'?a[0]:Number(op.slice(8))]);
    else if(op.startsWith('setlocal'))locals[op==='setlocal'?a[0]:Number(op.slice(8))]=pop();
    else if(op==='kill')delete locals[a[0]];
    else if(op==='pushbyte'||op==='pushstring'||op==='pushdouble')stack.push(a[0]);
    else if(op==='pushtrue'||op==='pushfalse')stack.push(op==='pushtrue');
    else if(op==='findpropstrict')stack.push(self);
    else if(op==='getlex')stack.push(a[0]==='Common::ASDefines'?profile.languages:{asType:a[0]});
    else if(op==='astypelate'){pop();stack.push(pop());}
    else if(op==='getproperty'){const obj=pop();if(obj==null||!Object.hasOwn(obj,a[0]))throw Error('Original objective property unavailable '+a[0]);stack.push(obj[a[0]]);}
    else if(op==='setproperty'||op==='initproperty'){const v=pop(),obj=pop();if(!obj)throw Error('Original objective receiver absent');obj[a[0]]=v;}
    else if(op==='dup')stack.push(stack.at(-1));
    else if(op==='not')stack.push(!pop());
    else if(['add','subtract','multiply','divide','equals'].includes(op)){const b=pop(),v=pop();stack.push(op==='add'?v+b:op==='subtract'?v-b:op==='multiply'?v*b:op==='divide'?v/b:v==b);}
    else if(op==='jump')jump(r.targets[0]);
    else if(op==='iffalse'){if(!pop())jump(r.targets[0]);}
    else if(['ifnlt','ifnge','ifne','ifstrictne'].includes(op)){const b=pop(),v=pop();if(op==='ifnlt'?!(v<b):op==='ifnge'?!(v>=b):op==='ifne'?v!=b:v!==b)jump(r.targets[0]);}
    else if(op==='lookupswitch'){const index=pop();jump(r.targets[Number.isInteger(index)&&index>=0&&index<r.targets.length-1?index+1:0]);}
    else if(op==='callproperty'||op==='callpropvoid'){
      const args=stack.splice(stack.length-a[1],a[1]),obj=pop();let result;
      if(a[0]==='trace'){} // Original debug trace is not sent to the game UI/console.
      else if(a[0]==='getChildByName'){result=obj.children?.[args[0]];if(!result)throw Error('Original objective child absent');}
      else if(a[0]==='SetIcon')obj.icon=args[0];
      else if(a[0]==='setWidth')obj.width=args[0];
      else if(a[0]==='setText')obj.text=args[0];
      else if(a[0]==='http://adobe.com/AS3/2006/builtin::toString')result=String(obj);
      else throw Error('Unsupported original objective call '+a[0]);
      if(op==='callproperty')stack.push(result);
    }else if(op==='returnvoid')return structuredClone(nodes);
    else throw Error('Unsupported original objective opcode '+op);
  }
  throw Error('Original objective method did not return');
}

export async function createQuestTracking({profile,host=document.body}={}){
  trackedObjective(profile,null);
  const response=await fetch(profile.url);if(!response.ok)throw Error('Original objective drawing unavailable');
  const parsed=new DOMParser().parseFromString(await response.text(),'image/svg+xml');
  if(parsed.querySelector('parsererror,script,foreignObject'))throw Error('Invalid original objective drawing');
  const root=document.createElement('section');root.className='source-quest-tracking';root.hidden=true;root.setAttribute('aria-label','任务追踪');
  const svg=document.importNode(parsed.documentElement,true);root.append(svg);host.append(root);
  const style=document.createElement('style');style.textContent='.source-quest-tracking{position:fixed;inset:0;z-index:18;pointer-events:none;overflow:hidden}.source-quest-tracking[hidden]{display:none}.source-quest-tracking>svg{display:block;width:100%;height:100%;pointer-events:none}';document.head.append(style);
  const q=path=>svg.querySelector(`[data-source-path="${path}"]`),prefix='.m_CurQuestPanel.m_QuestItem0';
  const cfg=profile.window.config,[w,h]=profile.window.measuredSize;
  svg.querySelector('[data-quest-window]').setAttribute('transform',`translate(${Number(cfg.relativeposX)*(1136-w)+Number(cfg.offsetX)} ${Number(cfg.relativeposY)*(640-h)+Number(cfg.offsetY)}) scale(0.05)`);
  const item=q(prefix),textNode=q(prefix+'.stepText').querySelector('[data-entry-text]'),countNode=q(prefix+'.stepPercentNum').querySelector('[data-entry-text]');
  const textGroup=q(prefix+'.stepText'),textBounds=textNode.getAttribute('data-entry-bounds').split(' ').map(Number),countBounds=countNode.getAttribute('data-entry-bounds').split(' ').map(Number);
  const originalMatrix=textGroup.getAttribute('transform').slice(7,-1).split(/[ ,]+/).map(Number),itemMatrix=item.getAttribute('transform').slice(7,-1).split(/[ ,]+/).map(Number);
  // Source AS properties use pixels, while the extracted SVG uses twips.
  const metrics={width:textBounds[2]/20,y:originalMatrix[5]/20,counterWidth:countBounds[2]/20};
  const hide=path=>{const n=q(path);n?.setAttribute('display','none');n?.setAttribute('aria-hidden','true');};
  hide(prefix+'.scrollText');hide(prefix+'.stepPercent');
  let last=null,disposed=false;
  function update(state){
    if(disposed)return;
    let objective;
    try{objective=trackedObjective(profile,state);}catch(error){root.hidden=true;last=null;throw error;}
    if(!objective){root.hidden=true;last=null;return;}
    const formatted=formatTrackedObjective(profile,objective,metrics);
    textNode.textContent=formatted.stepText.text;countNode.textContent=formatted.stepPercentNum.text;
    q(prefix+'.stepPercentNum').setAttribute('display',formatted.stepPercentNum.visible?'inline':'none');
    q(prefix+'.stepPercentNum').setAttribute('aria-hidden',String(!formatted.stepPercentNum.visible));
    const m=[...originalMatrix];m[5]=formatted.stepText.y*20;textGroup.setAttribute('transform',`matrix(${m.join(' ')})`);
    // Original ordinary type is plain text, not the instant-quest percent bar.
    // Ellipsis uses the exact recovered text width; no new text box is drawn.
    textNode.setAttribute('data-source-width',String(formatted.stepText.width*20));
    const image=document.createElementNS(NS,'image');image.setAttribute('href',profile.assets[formatted.stepicon.icon].url);image.setAttribute('width','1920');image.setAttribute('height','1920');
    q(prefix+'.stepicon.ImageContains.image').replaceChildren(image);
    root.hidden=false;
    // Literal SetCurQuestPanel centering with browser text bounds as host metric.
    const low=q('.m_CurQuestPanel.m_LowShap'),b=low.getBBox(),lm=low.transform.baseVal.consolidate().matrix;
    const lowHeight=b.height*Math.hypot(lm.c,lm.d),itemHeight=item.getBBox().height;
    const next=[...itemMatrix];next[5]=lm.f+Math.max(0,(lowHeight-itemHeight)/2);item.setAttribute('transform',`matrix(${next.join(' ')})`);
    root.dataset.questId=String(objective.questId);root.dataset.current=String(objective.current);root.dataset.sourceType=String(objective.sourceType);last=state;
  }
  const resize=()=>{if(last)update(last);};window.addEventListener('resize',resize);
  document.fonts.ready.then(()=>{if(!disposed&&last)update(last);});
  return Object.freeze({update,clear:()=>update(null),dispose(){disposed=true;window.removeEventListener('resize',resize);root.remove();style.remove();}});
}
