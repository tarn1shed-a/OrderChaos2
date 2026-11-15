// Original MissionDialog drawings/branch program over the authorized compatible
// quest layer. These DTOs and actions are NOT original native messages.
export const QUEST_UI_ORIGIN='compatible-quest-layer';
const clone=v=>structuredClone(v),NS='http://www.w3.org/2000/svg';
const plain=v=>String(v).replace(/<[^>]*>/g,'');
const integer=(v,min=0)=>Number.isSafeInteger(v)&&v>=min;

export function validateQuestView(value){
  if(value?.origin!==QUEST_UI_ORIGIN||!integer(value.questId,1)||
    !(typeof value.revision==='string'||integer(value.revision))||
    ![1,2,4,5,6,8,9].includes(value.Status))throw TypeError('Compatible quest view/revision required');
  for(const name of ['Title','Detail','Objective','Incomplete','Completion'])
    if(typeof value[name]!=='string')throw TypeError('Missing source quest text '+name);
  if(typeof value.hasReward!=='boolean'||typeof value.HasCollectedTbItem!=='boolean'||
    typeof value.IsFailed!=='boolean'||typeof value.IsInTuto!=='boolean')throw TypeError('Explicit compatible quest flags required');
  if(value.IsInTuto)throw Error('Tutorial-specific controls are outside this ordinary-quest view');
  for(const name of ['NumGold','NumXp','NumFever','NumAdvExp','NumItem','NumItemOp','NumItemTb'])
    if(!integer(value[name]))throw TypeError('Missing compatible numeric field '+name);
  if(value.NumItemOp!==0)throw Error('Original optional-item selection is not attached');
  for(const [key,count]of [['fixedItems',value.NumItem],['returnItems',value.NumItemTb]]){
    if(!Array.isArray(value[key])||value[key].length!==count||count>4)throw TypeError('Item slot count differs '+key);
    for(const item of value[key]){
      if(!integer(item.id,1)||!integer(item.count,1)||typeof item.icon!=='string'||!item.icon||
        !integer(item.quality)||item.quality>7||item.isGem!==false||item.hasPromo!==false||item.restricted!==false)throw TypeError('Verified plain-item display required');
    }
  }
  return clone(value);
}

// All branch decisions run through the existing pinned, bounded original AS
// interpreter supplied by the host. It is not a native query provider/Flash VM.
export function createQuestController({query,action,program,programFactory,render,hide,onError=()=>{}}){
  if(![query,action,programFactory,render,hide,onError].every(v=>typeof v==='function'))throw TypeError('Quest controller providers required');
  let epoch=0,current=null,vm=null,disposed=false,pending=false;
  const inspect=()=>({visible:!!current,pending,questId:current?.questId??null,revision:current?.revision??null,
    stage:vm?.inspect().statusFinished===0&&(vm?.inspect().displayFlag&4)&&current?.NumItemTb>0?'return-items':'detail-or-rewards',
    compatibilityLayer:true,nativeMessage:false});
  const state=()=>({...vm.inspect(),info:clone(current),compatibilityLayer:true,nativeMessage:false});
  async function draw(token){if(disposed||token!==epoch)return false;await render(state(),pending);return !disposed&&token===epoch;}
  function reset(){epoch++;current=null;vm=null;pending=false;hide();}
  async function open(questId){
    if(disposed)throw Error('Quest UI disposed');const token=++epoch;current=null;vm=null;pending=false;hide();
    try{
      const info=validateQuestView(await query(questId));if(disposed||token!==epoch)return null;
      if(info.questId!==questId)throw Error('Quest query identity mismatch');
      current=info;vm=programFactory(program,info,{questId,isOpenedFromList:false,isAutoAccepted:false},
        {currentWindowLevel:0,modelWindow0:false,modelWindow1:false});
      vm.open();if(!await draw(token))return null;return inspect();
    }catch(error){if(disposed||token!==epoch)return null;reset();onError(error);throw error;}
  }
  async function pressOK(){
    if(disposed||pending||!current||!vm?.inspect().okVisible||vm.inspect().grayVisible)return null;
    const token=epoch,old=clone(current);pending=true;
    try{
      const fresh=validateQuestView(await query(old.questId));if(disposed||token!==epoch)return null;
      if(JSON.stringify(fresh)!==JSON.stringify(old)){
        pending=false;const refreshedEpoch=epoch+1;await open(old.questId);
        if(disposed||epoch!==refreshedEpoch)return null;return {sent:false,reason:'state-changed'};
      }
      const before=vm.inspect().actions.length,next=vm.ok();
      const requested=next.actions.slice(before).some(v=>v.nativeCallback==='Hero_SendAcceptQuestN');
      if(!requested){pending=false;if(!await draw(token))return null;return {sent:false,confirmation:true};}
      const type=[5,6].includes(old.Status)?'accept':[8,9].includes(old.Status)?'complete':null;
      if(!type)throw Error('This source state has no actionable command');
      const result=await action({type,questId:old.questId,revision:old.revision,origin:QUEST_UI_ORIGIN});
      if(disposed||token!==epoch)return null;
      if(result?.ok!==true)throw Error(result?.error||'Quest action rejected');
      reset();return {sent:true,type,result};
    }catch(error){
      if(disposed||token!==epoch)return null;
      pending=false;const recoveryEpoch=epoch+1;await open(old.questId).catch(()=>{});
      if(disposed||epoch!==recoveryEpoch)return null;onError(error);throw error;
    }finally{if(token===epoch)pending=false;}
  }
  async function close(){
    if(disposed||pending||!current)return false;const old=clone(current);vm?.close();reset();
    // Cancellation is a compatible UI intent, not the original EventListCommon.
    await action({type:'cancel',questId:old.questId,revision:old.revision,origin:QUEST_UI_ORIGIN});return true;
  }
  return Object.freeze({open,pressOK,close,inspect,
    // Session teardown is local invalidation, not a quest-cancel command.
    invalidate(){if(disposed)return false;reset();return true;},
    dispose(){if(disposed)return;reset();disposed=true;}});
}

// Literal original RePosReward program, source geometry in twips. No reward rule.
export function questRewardLayout(profile,flag){
  if(profile?.format!=='oc2-original-mission-optional-assets-v1'||!integer(flag)||flag>7)throw TypeError('Original reward profile required');
  const g=profile.geometry,height=k=>{const r=g[k];if(!r?.outerBoundsInvariantWithoutCooldown)throw Error('Original geometry incomplete');return r.localBounds[3]-r.localBounds[1];},y=k=>g[k].path.chain.at(-1).matrixTwips[5];
  const s={_DisplayFlag:flag,_y0:height('txt_reward')-profile.program.constants._Dist1*20,_y1:y('Part1'),_y2:y('Part2'),_y3:y('Part3'),
    _h1:height('txt_reward')+height('Part1'),_h2:y('Part3')+y('Part1')+height('Part1')-y('Part2'),_h3:y('Part3')+height('Part3'),
    _h4:y('Part2')+height('Part2'),_h11:height(''),_yBottom:y('')+height(''),
    _RewardBoard:{y:y(''),Board:{height:height('Board')*g.Board.path.chain.at(-1).matrixTwips[3]},Part1:{y:y('Part1'),visible:false},Part2:{y:y('Part2'),visible:false},Part3:{y:y('Part3'),visible:false}}};
  const code=profile.program.methods.RePosReward;
  if(code.codeSHA256!=='e901c4f3ac55ed114a78e04e318ac21f28368af41858edbffb0f2c9d598a981e')throw Error('Original reward layout program differs');
  const ins=code.instructions,by=new Map(ins.map((r,i)=>[r.at,i])),stack=[],locals={0:s,1:0};let pc=0,steps=0;
  while(pc<ins.length){
    if(++steps>500)throw Error('Bounded original reward layout');const r=ins[pc++],op=r.op,a=r.args;
    if(op==='getlocal0')stack.push(locals[0]);else if(op==='getlocal1')stack.push(locals[1]);else if(op==='pushscope')stack.pop();
    else if(op==='getproperty')stack.push(stack.pop()[a[0]]);else if(op==='pushbyte')stack.push(a[0]);else if(op==='pushtrue')stack.push(true);
    else if(op==='setproperty'||op==='initproperty'){const v=stack.pop();stack.pop()[a[0]]=v;}
    else if(op==='add'||op==='subtract'){const b=stack.pop(),v=stack.pop();stack.push(op==='add'?v+b:v-b);}
    else if(op==='ifne'){const b=stack.pop(),v=stack.pop();if(v!==b)pc=by.get(r.targets[0]);}
    else if(op==='jump')pc=by.get(r.targets[0]);else if(op==='returnvoid')return clone(s._RewardBoard);
    else throw Error('Unrestored reward-layout instruction '+op);
  }
  throw Error('Original reward layout did not return');
}

export async function createQuestUI({host=document.body,profile,optionalProfile,program,programFactory,query,action,
  assetBaseURL=location.href,optionalBaseURL=assetBaseURL,fontBaseURL='/assets/ui/',itemAssets={},qualityFrames={},onError=()=>{}}={}){
  if(!(host instanceof Element)||profile?.format!=='oc2-source-quest-ui-v1'||
    profile.windows?.MissionDialog?.sourceSHA256!=='1ca086266a17e5a12a46bcc6b5a37f1e3714dae6f66772f71256ea8161ca1236')throw TypeError('Original MissionDialog profile/host required');
  const spec=profile.windows.MissionDialog;
  const url=(path,base=assetBaseURL)=>new URL(path,base).href;
  async function svg(path,base){const r=await fetch(url(path,base));if(!r.ok)throw Error('Original drawing unavailable');
    const doc=new DOMParser().parseFromString(await r.text(),'image/svg+xml');if(doc.querySelector('parsererror,script,foreignObject'))throw Error('Invalid original SVG');return doc;}
  const drawing=await svg(spec.url,assetBaseURL),optional=optionalProfile?await svg(optionalProfile.rewardSVG.file,optionalBaseURL):null;
  const root=document.createElement('section');root.className='compatible-source-mission';root.hidden=true;root.setAttribute('aria-label','任务');host.append(root);
  const style=document.createElement('style');style.textContent=`
@font-face{font-family:EntryText;src:url('${url('chineseText.woff',url(fontBaseURL))}')}@font-face{font-family:EntryDisplay;src:url('${url('chineseDisplay.woff',url(fontBaseURL))}')}@font-face{font-family:EntryGothic;src:url('${url('leagueGothic.woff',url(fontBaseURL))}')}
.compatible-source-mission{position:fixed;inset:0;z-index:45;pointer-events:none;overflow:hidden}.compatible-source-mission[hidden]{display:none}.compatible-source-mission>svg{width:100%;height:100%;display:block;pointer-events:none}.compatible-source-mission [role=button]{cursor:pointer;pointer-events:auto}.compatible-source-mission [aria-disabled=true]{pointer-events:none}.compatible-source-mission-text{position:fixed;box-sizing:border-box;margin:0;padding:0;border:0;background:transparent;white-space:pre-wrap;overflow:auto;overflow-wrap:break-word;line-height:normal;scrollbar-width:none;pointer-events:auto}
`;document.head.append(style);
  let screen=null,texts=[],current=null,layoutBoard=null,disposed=false,controller;
  const q=path=>screen?.querySelector(`[data-source-path="${path}"]`);
  const visible=(path,value)=>{const el=q(path);if(el){el.setAttribute('display',value?'inline':'none');el.setAttribute('aria-hidden',String(!value));}};
  const moveY=(el,y)=>{const m=el.getAttribute('transform').slice(7,-1).split(/[ ,]+/).map(Number);m[5]=y;el.setAttribute('transform',`matrix(${m.join(' ')})`);};
  const clear=()=>{root.hidden=true;root.replaceChildren();screen=null;texts=[];current=null;layoutBoard=null;};
  function addText(path,value,optionalText=false){
    const group=q(path);if(!group)throw Error('Original text node unavailable '+path);
    const source=group.querySelector('[data-entry-text]'),meta=optionalText?optionalProfile.texts[Number(group.getAttribute('data-mission-text-index'))]:null;
    if(!source&&!meta)throw Error('Original text metrics unavailable '+path);
    const el=document.createElement('div');el.className='compatible-source-mission-text';el.dataset.questText=path;el.textContent=plain(value);
    let bounds,size;
    if(meta){const b=meta.style.boundsPixels;bounds=[b[0]*20,b[2]*20,(b[1]-b[0])*20,(b[3]-b[2])*20];size=meta.style.fontHeight*20;
      el.style.fontFamily=meta.font.includes('League')?'EntryGothic,EntryText':meta.font.includes('Alegreya')?'EntryDisplay':'EntryText';
      const [r,g,b0,a]=meta.style.colorRGBA;el.style.color=`rgb(${r},${g},${b0})`;el.style.opacity=a/255;el.style.textAlign=['left','right','center','left'][meta.style.align];
    }else{bounds=source.getAttribute('data-entry-bounds').split(' ').map(Number);size=Number(source.getAttribute('font-size'));
      el.style.fontFamily=source.getAttribute('font-family');el.style.color=source.getAttribute('fill');el.style.opacity=source.getAttribute('fill-opacity');el.style.textAlign=({start:'left',end:'right',middle:'center'})[source.getAttribute('text-anchor')]||'left';source.setAttribute('visibility','hidden');}
    root.append(el);texts.push({path,el,group,bounds,size});return el;
  }
  function placeText(field,height=null){const m=field.group.getScreenCTM();if(!m)return;const p=new DOMPoint(field.bounds[0],field.bounds[1]).matrixTransform(m),scale=Math.hypot(m.a,m.b);
    Object.assign(field.el.style,{left:p.x+'px',top:p.y+'px',width:field.bounds[2]*scale+'px',height:height===null?field.bounds[3]*scale+'px':height===false?'auto':height*scale+'px',fontSize:field.size*scale+'px'});return scale;}
  function layout(){
    if(!current||!screen)return;let panelY=spec.fields['MainWin.txt_summ'].matrixTwips[5];
    const summary=texts.find(t=>t.path==='.MainWin.txt_summ');
    if(current.showSummary&&summary){const scale=placeText(summary,false);if(!scale)return;
      const subtitle=q('.MainWin.txt_sub_title'),subtitleY=panelY+summary.el.getBoundingClientRect().height/scale;visible('.MainWin.txt_sub_title',true);moveY(subtitle,subtitleY);panelY=subtitleY+subtitle.getBBox().height;}
    moveY(q('.MainWin._ScrollPanel'),panelY);
    const rewardY=layoutBoard?.y??spec.fields['MainWin._RewardBoard'].matrixTwips[5],detailHeight=rewardY-panelY-profile.constants.detailInset*20;
    if(detailHeight<=0)throw Error('Original detail viewport exhausted');
    for(const text of texts)placeText(text,text.path.endsWith('txt_detail')?detailHeight:text===summary?false:null);
  }
  function icon(path,sourcePath,assetMap=optionalProfile?.assets,base=optionalBaseURL){
    const entry=assetMap?.[sourcePath];if(!entry)throw Error('Original icon unavailable '+sourcePath);
    const el=q(path+'.ImageContains.image');if(!el)throw Error('Original Icon child unavailable '+path);
    const image=document.createElementNS(NS,'image');image.setAttribute('href',url(entry.file??entry.url,base));image.setAttribute('width','1920');image.setAttribute('height','1920');el.replaceChildren(image);visible(path,true);
  }
  function item(path,value){
    const parent=q(path);if(!parent)throw Error('Original ItemSlot unavailable');
    if(value.quality!==0){const frame=qualityFrames[value.quality];if(!frame)throw Error('Original ItemSlot quality frame unavailable '+value.quality);
      const parsed=new DOMParser().parseFromString(frame,'image/svg+xml');if(parsed.querySelector('parsererror,script,foreignObject'))throw Error('Invalid original quality frame');q(path+'.quality').replaceChildren(...[...parsed.documentElement.children].map(n=>document.importNode(n,true)));}
    for(const name of ['SelectedMark','_GemIcon','Cooldown','FailEff','IsLocked','NewPromo','Disable'])visible(path+'.'+name,false);
    icon(path+'.DisplayIcon',value.icon,itemAssets,assetBaseURL);visible(path+'.Stack',value.count>1);if(value.count>1)addText(path+'.Stack',value.count,true);
  }
  async function render(state,pending){
    clear();if(disposed)return;current=state;screen=document.importNode(drawing.documentElement,true);root.append(screen);root.hidden=false;
    const cfg=spec.config,[w,h]=spec.measuredSize,x=Number(cfg.relativeposX)*(1136-w)+Number(cfg.offsetX),y=Number(cfg.relativeposY)*(640-h)+Number(cfg.offsetY);
    screen.querySelector('[data-quest-window]').setAttribute('transform',`translate(${x} ${y}) scale(0.05)`);
    for(const path of ['.MainWin._RewardBoard','.MainWin._GroupBtn.btn_gray','.MainWin._GroupBtn.TutoBtn','.MainWin._watermark1','.MainWin._detailBar','.MainWin.txt_summ','.MainWin.txt_sub_title'])visible(path,false);
    addText('.MainWin.txt_title',state.title);addText('.MainWin._ScrollPanel.mc_content.txt_detail',state.body);
    if(state.showSummary)addText('.MainWin.txt_summ',state.objective);
    layoutBoard=optionalProfile?questRewardLayout(optionalProfile,state.displayFlag):null;
    if(state.displayFlag){
      if(!optional||!optionalProfile)throw Error('Original reward/item drawing required');
      screen.querySelector('defs').append(...[...optional.querySelector('defs').children].map(n=>document.importNode(n,true)));
      const board=q('.MainWin._RewardBoard'),source=optional.querySelector('[data-source-path=".MainWin._RewardBoard"]');
      board.replaceChildren(...[...source.children].map(n=>document.importNode(n,true)));visible('.MainWin._RewardBoard',true);
      moveY(board,layoutBoard.y);
      for(const part of ['Part1','Part2','Part3']){visible('.MainWin._RewardBoard.'+part,layoutBoard[part].visible);moveY(q('.MainWin._RewardBoard.'+part),layoutBoard[part].y);}
      const backdrop=q('.MainWin._RewardBoard.Board'),bm=backdrop.getAttribute('transform').slice(7,-1).split(/[ ,]+/).map(Number),bounds=optionalProfile.geometry.Board.localBounds;
      bm[3]=layoutBoard.Board.height/(bounds[3]-bounds[1]);backdrop.setAttribute('transform',`matrix(${bm.join(' ')})`);
      const rows=layoutBoard.Part1.visible?optionalProfile.numericRewardSlots.filter(r=>state.info[r.field]>0):[];
      for(let i=0;i<4;i++){const prefix='.MainWin._RewardBoard.Part1.mcR'+i;visible(prefix,!!rows[i]);if(rows[i]){icon(prefix+'.icon0',rows[i].icon);addText(prefix+'.txt0',state.info[rows[i].field],true);}}
      const returning=!!(state.displayFlag&4)&&state.info.NumItemTb>0&&!state.statusFinished,items=returning?state.info.returnItems:state.info.fixedItems;
      for(let i=0;i<4;i++){visible('.MainWin._RewardBoard.Part2.item'+i,!returning&&!!items[i]);visible('.MainWin._RewardBoard.Part3.itemOp'+i,returning&&!!items[i]);
        if(items[i])item('.MainWin._RewardBoard.'+(returning?'Part3.itemOp':'Part2.item')+i,items[i]);}
      addText('.MainWin._RewardBoard.txt_reward',optionalProfile.program.strings[returning?'GENERAL_MISSIONDLG_04':'GENERAL_MISSIONDLG_01'].text,true);
    }
    if(state.watermark){if(!optionalProfile)throw Error('Original watermark required');icon('.MainWin._watermark1',state.watermark);}
    const btn=q('.MainWin._GroupBtn.btn_ok');visible('.MainWin._GroupBtn.btn_ok',state.okVisible&&!state.grayVisible);
    btn.setAttribute('role','button');btn.setAttribute('tabindex','0');btn.setAttribute('aria-label',profile.strings.GENERAL_OK.text);btn.setAttribute('aria-disabled',String(pending));
    btn.querySelector('[data-entry-text]').textContent=plain(profile.strings.GENERAL_OK.text);
    btn.addEventListener('click',()=>controller.pressOK().catch(onError));btn.addEventListener('keydown',e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();controller.pressOK().catch(onError);}});
    layout();await document.fonts.ready;layout();
  }
  controller=createQuestController({query,action,program,programFactory,render,hide:clear,onError});
  const key=e=>{if(e.key==='Escape'&&current){e.preventDefault();controller.close().catch(onError);}};
  window.addEventListener('keydown',key);window.addEventListener('resize',layout);
  return Object.freeze({...controller,dispose(){if(disposed)return;controller.dispose();disposed=true;root.remove();style.remove();window.removeEventListener('keydown',key);window.removeEventListener('resize',layout);}});
}
