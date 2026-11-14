// Original drawings; centered entry sizing is the user's explicit web layout preference.
// Existing web identities are a separate adapter.
import {entryNameError} from './entry_name.mjs';
const NS='http://www.w3.org/2000/svg';
export function savedEntryIdentities(storage){
  try{
    const saved=JSON.parse(storage.getItem('oc2.character-slots.v1')||'{}');
    if(!saved.characters||Array.isArray(saved.characters)||typeof saved.characters!=='object')return [];
    return Object.values(saved.characters).filter(v=>v&&typeof v.id==='string'&&typeof v.token==='string'&&/^[0-9a-f-]{36}$/.test(v.id)&&/^[0-9a-f]{64}$/.test(v.token)).slice(0,32).map(v=>({characterId:v.id,resumeToken:v.token}));
  }catch{return [];}
}
export function createSourceEntry({connect,previewURL=null}){
  const css=document.createElement('link');css.rel='stylesheet';css.href='/__delivery/entry_ui.css';document.head.append(css);
  const root=document.createElement('section');root.className='source-entry';root.hidden=true;root.setAttribute('aria-label','登录与角色选择');document.body.append(root);
  let manifest=null,screen=null,selected=null,roles=[],identities=[],isReady=false,busy=false,pendingError=null,listOffset=0;
  let draft={race:0,gender:0,cls:0,name:''};
  let racePreview=null,previewPromise=null;
  function hidePreview(){racePreview?.hide();}
  function updateRacePreview(){
    if(!previewURL)return;
    const current={screen:root.dataset.sourceScreen,race:draft.race,gender:draft.gender};
    if(!previewPromise)previewPromise=import('./creation_preview.mjs').then(({createSourceCreationPreview})=>racePreview=createSourceCreationPreview(root,{profileURL:previewURL}));
    previewPromise.then(p=>{if(root.dataset.sourceScreen===current.screen&&draft.race===current.race&&draft.gender===current.gender&&!root.hidden)return p.show(current);}).catch(error=>{root.dataset.sourceCreationError=error.message;});
  }
  const blocked=new Map();
  function hideRoot(){racePreview?.dispose();racePreview=null;previewPromise=null;root.hidden=true;for(const[el,value]of blocked)el.inert=value;blocked.clear();}
  const api=async(path,data)=>{const r=await fetch('/__entry/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data),cache:'no-store'}),v=await r.json();if(!r.ok)throw Error(v.error||'请求失败');return v;};
  function remember(role,token){
    const saved=JSON.parse(localStorage.getItem('oc2.character-slots.v1')||'{"characters":{},"lastName":""}');
    saved.characters[role.name]={id:role.id,token};saved.lastName=role.name;
    localStorage.setItem('oc2.character-slots.v1',JSON.stringify(saved));
  }
  function forget(id){
    const saved=JSON.parse(localStorage.getItem('oc2.character-slots.v1')||'{"characters":{},"lastName":""}');
    for(const[name,value]of Object.entries(saved.characters))if(value.id===id){delete saved.characters[name];if(saved.lastName===name)saved.lastName='';}
    localStorage.setItem('oc2.character-slots.v1',JSON.stringify(saved));identities=identities.filter(v=>v.characterId!==id);
  }
  const q=(path,scope=screen)=>scope?.querySelector(`[data-source-path="${path}"]`);
  const hide=(path,scope=screen)=>{const el=q(path,scope);if(el){el.setAttribute('display','none');el.setAttribute('aria-hidden','true');}};
  const label=(path,value,scope=screen)=>{const el=q(path,scope)?.querySelector('[data-entry-text]');if(el)el.textContent=String(value).replace(/<[^>]+>/g,'');};
  const word=key=>manifest.strings[key].text.replace(/<[^>]+>/g,'');
  const button=(el,name,fn,disabled=false)=>{
    if(!el)return;el.setAttribute('role','button');el.setAttribute('aria-label',name);el.setAttribute('tabindex',disabled?'-1':'0');el.setAttribute('aria-disabled',String(disabled));
    const activate=()=>{if(el.getAttribute('aria-disabled')!=='true')Promise.resolve().then(fn).catch(error=>connectionError(error.message));};el.addEventListener('click',activate);el.addEventListener('keydown',e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();activate();}});
  };
  const image=(el,url)=>{if(!el||!url)return;const b=el.getBBox();if(!b.width||!b.height)return;el.replaceChildren();const img=document.createElementNS(NS,'image');for(const[k,v]of Object.entries({x:b.x,y:b.y,width:b.width,height:b.height,href:url,preserveAspectRatio:'xMidYMid meet'}))img.setAttribute(k,v);el.append(img);};
  const icon=name=>manifest.assets['ui/icons/userinterface/'+name+'_0.5x.png']?.url;
  const fieldLayouts=[];
  function layoutFields(){
    for(const {el,group,b,size}of fieldLayouts){
      const m=group.getScreenCTM();if(!m)continue;
      const p=new DOMPoint(b[0],b[1]).matrixTransform(m),end=new DOMPoint(b[0]+b[2],b[1]+b[3]).matrixTransform(m);
      // CSS pixel positions come only from the original text-field rectangle.
      Object.assign(el.style,{position:'absolute',left:p.x+'px',top:p.y+'px',width:Math.abs(end.x-p.x)+'px',height:Math.abs(end.y-p.y)+'px',fontSize:size*Math.hypot(m.a,m.b)+'px'});
    }
  }
  window.addEventListener('resize',layoutFields);
  function field(path,{name,value='',placeholder='',input=false}={}){
    const existing=fieldLayouts.find(v=>v.group===q(path));
    if(existing){if(input)existing.el.value=value;else existing.el.textContent=value;return existing.el;}
    const group=q(path),text=group.querySelector('[data-entry-text]'),b=text.getAttribute('data-entry-bounds').split(' ').map(Number);
    const el=document.createElement(input?'input':'div');
    el.setAttribute('aria-label',name||path);el.setAttribute('class','source-entry-field');el.setAttribute('data-align',text.getAttribute('text-anchor'));el.setAttribute('data-font-family',text.getAttribute('font-family'));
    if(input){el.value=value;el.placeholder=placeholder;el.autocomplete='off';el.spellcheck=false;}else el.textContent=value;
    el.style.position='absolute';text.setAttribute('visibility','hidden');root.append(el);
    fieldLayouts.push({el,group,b,size:Number(text.getAttribute('font-size'))});layoutFields();return el;
  }
  async function loginLogo(el,url){
    const bitmap=new Image();bitmap.src=url;await bitmap.decode();
    const b=el.getBBox(),m=screen.getScreenCTM().inverse().multiply(el.getScreenCTM());
    const p=new DOMPoint(b.x,b.y).matrixTransform(m),end=new DOMPoint(b.x+b.width,b.y+b.height).matrixTransform(m);
    const width=end.x-p.x,height=width*bitmap.naturalHeight/bitmap.naturalWidth;
    const img=document.createElementNS(NS,'image');
    for(const[k,v]of Object.entries({x:p.x,y:(p.y+end.y-height)/2,width,height,href:url,preserveAspectRatio:'xMidYMid meet','data-entry-logo':''}))img.setAttribute(k,v);
    // The SWF Picture placeholder has a nonuniform parent scale. Carry the
    // original bitmap in screen coordinates so that scale cannot flatten it.
    el.setAttribute('display','none');screen.append(img);
  }
  function artworkBounds(elements,inverse=screen.getScreenCTM().inverse()){
    const points=[];
    for(const el of elements){
      const b=el.getBBox(),matrix=inverse.multiply(el.getScreenCTM());
      for(const[x,y]of [[b.x,b.y],[b.x+b.width,b.y],[b.x,b.y+b.height],[b.x+b.width,b.y+b.height]])points.push(new DOMPoint(x,y).matrixTransform(matrix));
    }
    const x=Math.min(...points.map(p=>p.x)),y=Math.min(...points.map(p=>p.y));
    return {x,y,w:Math.max(...points.map(p=>p.x))-x,h:Math.max(...points.map(p=>p.y))-y};
  }
  function fitArtwork(elements){
    const {x,y,w,h}=artworkBounds(elements);
    // Fit the complete original artwork as one group; never stretch individual controls.
    screen.setAttribute('viewBox',`${x-12} ${y-12} ${w+24} ${h+24}`);
    screen.setAttribute('preserveAspectRatio','xMidYMid meet');layoutFields();
  }
  const loaded=fetch('/assets/source-entry/entry.json').then(r=>{if(!r.ok)throw Error('Original entry resources unavailable');return r.json();}).then(v=>{
    if(v.format!=='oc2-source-entry-ui-v1')throw Error('Original entry profile differs');manifest=v;return v;
  });
  async function show(name){
    hidePreview();
    await loaded;const profile=manifest.windows[name];const response=await fetch(profile.url);if(!response.ok)throw Error('Original entry drawing unavailable');
    const parsed=new DOMParser().parseFromString(await response.text(),'image/svg+xml');
    if(parsed.querySelector('parsererror,script,foreignObject'))throw Error('Invalid original entry drawing');
    fieldLayouts.length=0;screen=document.importNode(parsed.documentElement,true);screen.setAttribute('role','group');root.replaceChildren(screen);root.hidden=false;root.dataset.sourceScreen=name;
    for(const el of document.body.children)if(el!==root){if(!blocked.has(el))blocked.set(el,el.inert);el.inert=true;}
    const cfg=profile.config,[w,h]=profile.measuredSize||[0,0],x=Number(cfg.relativeposX)*(1136-w)+Number(cfg.offsetX),y=Number(cfg.relativeposY)*(640-h)+Number(cfg.offsetY);
    screen.querySelector('[data-entry-window]').setAttribute('transform',`translate(${x} ${y}) scale(0.05)`);
  }
  async function login(){
    await show('QuickLogin');hide('.m_Title');hide('.m_Line');hide('._GoogleBtn'); // original ASDefines.isPUB() returns false in this package
    hide('.2380.ImageContains'); // Picture constructor hides its unassigned authoring placeholder
    hide('._QuickLogin');hide('._QuickLoginText'); // native auto-login preference is unavailable; no invented saved setting
    hide('._VersionText');hide('.m_Version'); // native account/runtime version response is not a web version
    for(const[path,key]of [['._QuickLoginBtn.title','GENERAL_QUICK_LOGIN'],['._FaceBookBtn.title','GENERAL_LOGIN_FACEBOOK_BTN'],['._GameCenterBtn.title','GENERAL_LOGIN_GAMECENTER_BTN']])label(path,word(key));
    await loginLogo(q('.m_Picture._Picture'),manifest.logo);
    for(const[name,key]of [['_FaceBookBtn','facebook'],['_GameCenterBtn','gamecenter']]){
      image(q('.'+name+'.icon'),manifest.assets['ui/icons/userinterface/'+key+'_0.5x.png']?.url);
      button(q('.'+name),word(name==='_FaceBookBtn'?'GENERAL_LOGIN_FACEBOOK_BTN':'GENERAL_LOGIN_GAMECENTER_BTN')+'（原账号登录不可用）',()=>{},true);
    }
    button(q('._QuickLoginBtn'),word('GENERAL_QUICK_LOGIN'),choose);
    fitArtwork([screen.querySelector('[data-entry-logo]'),...['._QuickLoginBtn','._GameCenterBtn','._FaceBookBtn'].map(path=>q(path))]);
  }
  async function choose(){
    if(busy)return;busy=true;
    try{
      identities=[...new Map([...savedEntryIdentities(localStorage),...identities].map(v=>[v.characterId,v])).values()];
      roles=(await api('characters',{identities})).characters;
      selected=roles.find(v=>v.id===selected?.id)||roles[0]||null;
      await renderChoose();
    }finally{busy=false;}
  }
  async function renderChoose(){
    await show('CharacterChooseCharacter');hide('._DeleteCharMC');hide('._FuncBtnMC');
    const panel=q('._CharacterMC');panel.setAttribute('transform',`translate(${(1136-panel.getBBox().width/20)*20} 0)`);
    // The preview has no recovered account slot/price response. One original
    // creation action is exposed, without claiming purchased/open slot counts.
    const entries=[...roles,{create:true}];listOffset=Math.max(0,Math.min(listOffset,Math.max(0,entries.length-5)));
    for(const row of screen.querySelectorAll('[data-source-path^="._CharacterMC._CharacterList.item_"]')){
      const path=row.getAttribute('data-source-path');if(!/^\._CharacterMC\._CharacterList\.item_(?:\d+|pre\d+|post\d+)$/.test(path))continue;
      const match=path.match(/item_(\d+)$/),entry=match?entries[Number(match[1])+listOffset]:null;
      if(!entry){row.setAttribute('display','none');row.setAttribute('aria-hidden','true');continue;}
      hide(path+'._HighLight');
      if(entry.create){
        hide(path+'._ExistCharacter');hide(path+'._NewCharacter.IsLockedForSkill');hide(path+'._NewCharacter.SelectedEff');
        image(q(path+'._NewCharacter.DisplayIcon'),icon('icon_characteradd'));label(path+'._NewCharacter.txt_name',word('GENERAL_MC_SELECT_CREATE'));
        button(row,word('GENERAL_MC_SELECT_CREATE'),()=>{draft={race:0,gender:0,cls:0,name:''};return race();});
      }else{
        hide(path+'._NewCharacter');label(path+'._ExistCharacter.txt_name',entry.name);label(path+'._ExistCharacter.txt_level',word('GENERAL_MC_SELECT_LV')+entry.level);
        for(const key of ['guild_name','ar_guild_name','ar_txt_level'])hide(path+'._ExistCharacter.'+key);
        image(q(path+'._ExistCharacter.DisplayIcon'),icon('class_'+({1:'warrior',2:'mage',3:'ranger',4:'monk',5:'demonslayer'}[entry.profession])));
        button(row,entry.name,()=>select(entry));
      }
    }
    const rune=q('._RuneMC');rune.setAttribute('transform','translate(200 200)');
    for(const child of rune.children)if(!['._RuneMC._DeleteBtn','._RuneMC._DeleteText'].includes(child.getAttribute('data-source-path'))){child.setAttribute('display','none');child.setAttribute('aria-hidden','true');}
    image(q('._RuneMC._DeleteBtn.DisplayIcon'),icon('icon_deleteplayer'));
    label('._RuneMC._DeleteText',word('GENERAL_ROLESELECT_REMOVE_WINDOW_TITLE'));
    if(selected)button(q('._RuneMC._DeleteBtn'),word('GENERAL_ROLESELECT_REMOVE_WINDOW_TITLE'),deleteRole);else hide('._RuneMC');
    select(selected);
    const play=q('._CharacterMC._StartBtn');label('._CharacterMC._StartBtn.mc_label.txt_label',word('GENERAL_MC_SELECT_BTN_PLAY'));
    button(play,word('GENERAL_MC_SELECT_BTN_PLAY'),()=>{
      const credentials=identities.find(v=>v.characterId===selected?.id);if(!isReady||!credentials)return;
      startSelected(selected,credentials).catch(error=>connectionError(error.message));
    },!isReady||!selected);
    root.dataset.entryRoleCount=String(roles.length);
    screen.addEventListener('wheel',event=>{event.preventDefault();const next=Math.max(0,Math.min(listOffset+Math.sign(event.deltaY),Math.max(0,entries.length-5)));if(next!==listOffset){listOffset=next;renderChoose().catch(error=>connectionError(error.message));}},{passive:false});
  }
  async function startSelected(role,credentials){
    if(busy)return;busy=true;
    try{
      const url=new URL(location.href);
      if(url.searchParams.get('trialEntry')==='cinematic7'){
        await api('return',{...credentials,anchor:'cinematic7'});
        // One explicitly selected role, once; normal reload/reconnect restores saves.
        url.searchParams.delete('trialEntry');history.replaceState(null,'',url);
      }
      connect(role.name,credentials,role.profession);
    }finally{busy=false;}
  }
  async function deleteRole(){
    const role=selected,credentials=identities.find(v=>v.characterId===role?.id);if(!credentials)return;
    const proof=await api('delete-challenge',credentials);
    await show('CharacterChooseCharacter');root.dataset.sourceScreen='CharacterDelete';
    const window=screen.querySelector('[data-entry-window]').firstElementChild;
    for(const child of window.children)if(child.getAttribute('data-source-path')!=='._DeleteCharMC'){child.setAttribute('display','none');child.setAttribute('aria-hidden','true');}
    const modal=q('._DeleteCharMC');modal.setAttribute('transform','translate(0 0)');
    label('._DeleteCharMC._Title',word('GENERAL_ROLESELECT_REMOVE_WINDOW_TITLE'));
    label('._DeleteCharMC._CharInfo',role.name+' ('+word('GENERAL_MC_SELECT_LV')+role.level+')');
    label('._DeleteCharMC._RandCode',proof.code);label('._DeleteCharMC._RandCodeTitle',word('GENERAL_ROLESELECT_REMOVE_WINDOW_CODE'));label('._DeleteCharMC._InputErrorText','');
    const input=field('._DeleteCharMC._RandCodeInput.TextEditBox',{name:word('GENERAL_ROLESELECT_REMOVE_WINDOW_CODE'),input:true,placeholder:word('GENERAL_ROLESELECT_REMOVE_WINDOW_TEXTBOX')});input.maxLength=4;input.inputMode='numeric';
    label('._DeleteCharMC._CancelBtn.mc_label.txt_label',word('GENERAL_CANCEL'));label('._DeleteCharMC._OkBtn.mc_label.txt_label',word('GENERAL_OK'));
    button(q('._DeleteCharMC._CancelBtn'),word('GENERAL_CANCEL'),choose);
    let submitting=false;
    button(q('._DeleteCharMC._OkBtn'),word('GENERAL_OK'),async()=>{
      if(submitting)return;
      if(input.value!==proof.code){label('._DeleteCharMC._InputErrorText',word(input.value?'GENERAL_ROLESELECT_REMOVE_WINDOW_INCORRECT1':'GENERAL_ROLESELECT_REMOVE_WINDOW_INCORRECT2'));return;}
      submitting=true;
      try{await api('delete',{...credentials,challenge:proof.challenge,code:input.value});forget(role.id);selected=null;listOffset=0;await choose();}
      finally{submitting=false;}
    });
    fitArtwork([modal]);input.focus();
  }
  function select(role){
    selected=role;
    for(const el of screen.querySelectorAll('[data-source-path$="._ExistCharacter.SelectedEff"]')){
      const row=el.closest('[role=button]');el.setAttribute('display',row?.getAttribute('aria-label')===role?.name?'inline':'none');
    }
  }
  function navigation(back,next){
    for(const[path,key,fn]of [['._BackMC._BackBtn','GENERAL_CH_SELEC_22',back],['._NextMC._NextBtn','GENERAL_CH_SELEC_21',next]]){
      if(q(path)){label(path+'.mc_label.txt_label',word(key));button(q(path),word(key),fn);}
    }
    hide('._BackMC._BackBtnHL');hide('._NextMC._NextBtnHL');
  }
  const raceNames=['human','mender','elf','orc','kartan'],classNames=['warrior','ranger','mage','demonslayer','monk'];
  const raceTitles=['01','02','03','04','14'],classTitles=['05','06','07','08','15'];
  function creationPositions(kind){
    const size=path=>artworkBounds([q(path)]),move=(path,x,y)=>{const el=q(path),m=el.transform.baseVal.consolidate().matrix;el.setAttribute('transform',`matrix(${m.a} ${m.b} ${m.c} ${m.d} ${x*20} ${y*20})`);};
    // Exact InitPos assignments in Window_ChooseRace / Window_ChooseClass.
    const list='._'+kind+'List',desc='._'+kind+'DescMC',next=size('._NextMC');
    move(desc,100,100);move(list,1136-size(list).w-100,10);move('._BackMC',10,10);move('._NextMC',1136-next.w-10,640-next.h-10);
    if(kind==='Race'){const male=size('._MaleBtn'),female=size('._FemaleBtn');move('._MaleBtn',120,640-male.h-100);move('._FemaleBtn',150+male.w,640-female.h-100);}
  }
  async function race(){
    await show('CharacterChooseRace');creationPositions('Race');navigation(choose,profession);
    const update=()=>{
      for(let i=0;i<5;i++){const path='._RaceList.Item_'+i;q(path+'.SelectedEff').setAttribute('display',i===draft.race?'inline':'none');}
      label('._RaceDescMC._Title',word('GENERAL_CH_SELEC_'+raceTitles[draft.race]));
      image(q('._RaceDescMC._Icon'),icon('race_'+raceNames[draft.race]));
      field('._RaceDescMC._Detail.mc_content.text',{name:'种族说明',value:word('GENERAL_CH_SELEC_'+(16+draft.race))});
      for(const[which,value]of [['Male',0],['Female',1]]){
        q('._'+which+'Btn').setAttribute('display',draft.race===4?'none':'inline');q('._'+which+'Btn.SelectedEff').setAttribute('display',draft.gender===value?'inline':'none');
      }
      updateRacePreview();
    };
    for(let i=0;i<5;i++){const path='._RaceList.Item_'+i;hide(path+'.IsLockedForSkill');image(q(path+'.DisplayIcon'),icon('race_'+raceNames[i]));button(q(path),word('GENERAL_CH_SELEC_'+raceTitles[i]),()=>{draft.race=i;if(i===4)draft.gender=0;update();});}
    for(const[which,value]of [['Male',0],['Female',1]]){hide('._'+which+'Btn.IsLockedForSkill');image(q('._'+which+'Btn.DisplayIcon'),icon(which.toLowerCase()));button(q('._'+which+'Btn'),word('GENERAL_CH_SELEC_'+(value?23:24)),()=>{draft.gender=value;update();});}
    // Original txt_select_class -> ScrollPane -> UIComponent constructor
    // hides its mc_bounds authoring rectangle (code SHA 24e6fc6e…279df6).
    hide('._RaceDescMC._Detail.mc_bounds');hide('._RaceDescMC._ScrollBar');update();
  }
  async function profession(){
    await show('CharacterChooseClass');creationPositions('Class');navigation(race,appearance);
    const update=()=>{
      for(let i=0;i<5;i++)q('._ClassList.Item_'+i+'.SelectedEff').setAttribute('display',i===draft.cls?'inline':'none');
      label('._ClassDescMC._Title',word('GENERAL_CH_SELEC_'+classTitles[draft.cls]));image(q('._ClassDescMC._Icon'),icon('class_'+classNames[draft.cls]));
      const key='GENERAL_CH_SELEC_'+String(9+draft.cls).padStart(2,'0');field('._ClassDescMC._Detail.mc_content.text',{name:'职业说明',value:word(key)});
    };
    for(let i=0;i<5;i++){const path='._ClassList.Item_'+i;hide(path+'.IsLockedForSkill');image(q(path+'.DisplayIcon'),icon('class_'+classNames[i]));button(q(path),word('GENERAL_CH_SELEC_'+classTitles[i]),()=>{draft.cls=i;update();});}
    // The authored radar frame is not the selected class's recovered data.
    hide('._ClassDescMC._Pic');hide('._ClassDescMC._ScrollBar');update();
  }
  async function appearance(){
    await show('CharacterChoosePart');navigation(profession,()=>{});
    const panel=q('._PartMC'),sourceWidth=panel.getBBox().width/20;
    panel.setAttribute('transform',`translate(${(1136-sourceWidth)*20} 0)`);q('._BackMC').setAttribute('transform','translate(200 200)');
    hide('._RandomBtn');hide('._PartMC._InputNameMC._RandomNameBtn');hide('._PartMC._PartListMC');
    root.dataset.unrestored='original-name-server-approval,appearance-controls,selection-3d,village-config';
    const input=field('._PartMC._InputNameMC._InputName.TextEditBox',{name:word('GENERAL_CH_SELEC_36'),value:draft.name,input:true,placeholder:word('GENERAL_CH_SELEC_36')});input.maxLength=16;
    input.addEventListener('input',()=>{draft.name=input.value;});
    label('._PartMC._CreateBtn.mc_label.txt_label',word('GENERAL_CH_SELEC_43'));
    let submitting=false;
    button(q('._PartMC._CreateBtn'),word('GENERAL_CH_SELEC_43'),async()=>{
      if(submitting)return;draft.name=input.value.replace(/ +$/,'');const error=entryNameError(draft.name);
      if(error)return connectionError(manifest.strings[error]?.text||'名字包含不可用字符',appearance);
      if(roles.some(v=>v.name===draft.name))return connectionError('本设备已有同名角色，请返回选角或更换名字。',appearance);
      submitting=true;
      try{
        const result=await api('create',{name:draft.name,race:draft.race,gender:draft.gender,profession:[1,3,2,5,4][draft.cls]});
        identities.push({characterId:result.character.id,resumeToken:result.resumeToken});selected=result.character;
        remember(result.character,result.resumeToken);listOffset=Math.max(0,roles.length-3);await choose();
      }catch(error){await connectionError(manifest.strings[error.message]?.text||error.message,appearance);}
      finally{submitting=false;}
    });
  }
  async function connectionError(message,back=choose){
    await show('LoginMsgBox');hide('._DetailScrollPane');hide('._TxtTitle');hide('._VersionText');hide('.cnt._YesBtn');hide('.cnt._NoBtn');
    field('._MsgText',{name:'提示',value:message});label('.cnt._OkBtn.mc_label.txt_label',word('GENERAL_OK'));button(q('.cnt._OkBtn'),word('GENERAL_OK'),back);
    fitArtwork([screen.querySelector('[data-entry-window]')]);
  }
  return {
    open(){const message=pendingError;pendingError=null;(message?connectionError(message):login()).catch(error=>{root.dataset.entryError=error.message;root.hidden=false;root.textContent='原界面资源加载失败，请刷新重试。';root.setAttribute('role','alert');});},
    error(message){pendingError=String(message);},
    hide:hideRoot,
    ready(){isReady=true;const play=q('._CharacterMC._StartBtn');if(play&&selected){play.setAttribute('aria-disabled','false');play.setAttribute('tabindex','0');}}
  };
}
