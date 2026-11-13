// Original drawings; centered login sizing is the user's explicit web layout preference.
// Existing web identities are a separate adapter.
const NS='http://www.w3.org/2000/svg';
export function savedEntryIdentities(storage){
  try{
    const saved=JSON.parse(storage.getItem('oc2.character-slots.v1')||'{}');
    if(!saved.characters||Array.isArray(saved.characters)||typeof saved.characters!=='object')return [];
    return Object.values(saved.characters).filter(v=>v&&typeof v.id==='string'&&typeof v.token==='string'&&/^[0-9a-f-]{36}$/.test(v.id)&&/^[0-9a-f]{64}$/.test(v.token)).slice(0,32).map(v=>({characterId:v.id,resumeToken:v.token}));
  }catch{return [];}
}
export function createSourceEntry({connect,legacy}){
  if(new URLSearchParams(location.search).get('entry')==='legacy')return null;
  const css=document.createElement('link');css.rel='stylesheet';css.href='/__delivery/entry_ui.css';document.head.append(css);
  const root=document.createElement('section');root.className='source-entry';root.hidden=true;root.setAttribute('aria-label','登录与角色选择');document.body.append(root);
  let manifest=null,screen=null,selected=null,roles=[],identities=[],isReady=false,busy=false,pendingError=null;
  const blocked=new Map();
  function hideRoot(){root.hidden=true;for(const[el,value]of blocked)el.inert=value;blocked.clear();}
  function fallback(){hideRoot();legacy();}
  const q=(path,scope=screen)=>scope?.querySelector(`[data-source-path="${path}"]`);
  const hide=(path,scope=screen)=>{const el=q(path,scope);if(el){el.setAttribute('display','none');el.setAttribute('aria-hidden','true');}};
  const label=(path,value,scope=screen)=>{const el=q(path,scope)?.querySelector('[data-entry-text]');if(el)el.textContent=String(value).replace(/<[^>]+>/g,'');};
  const word=key=>manifest.strings[key].text.replace(/<[^>]+>/g,'');
  const button=(el,name,fn,disabled=false)=>{
    if(!el)return;el.setAttribute('role','button');el.setAttribute('aria-label',name);el.setAttribute('tabindex',disabled?'-1':'0');el.setAttribute('aria-disabled',String(disabled));
    const activate=()=>{if(el.getAttribute('aria-disabled')!=='true')fn();};el.addEventListener('click',activate);el.addEventListener('keydown',e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();activate();}});
  };
  const image=(el,url)=>{if(!el||!url)return;const b=el.getBBox();if(!b.width||!b.height)return;el.replaceChildren();const img=document.createElementNS(NS,'image');for(const[k,v]of Object.entries({x:b.x,y:b.y,width:b.width,height:b.height,href:url,preserveAspectRatio:'xMidYMid meet'}))img.setAttribute(k,v);el.append(img);};
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
  function centerLogin(){
    const inverse=screen.getScreenCTM().inverse(),points=[];
    for(const el of [screen.querySelector('[data-entry-logo]'),...['._QuickLoginBtn','._GameCenterBtn','._FaceBookBtn'].map(path=>q(path))]){
      const b=el.getBBox(),matrix=inverse.multiply(el.getScreenCTM());
      for(const[x,y]of [[b.x,b.y],[b.x+b.width,b.y],[b.x,b.y+b.height],[b.x+b.width,b.y+b.height]])points.push(new DOMPoint(x,y).matrixTransform(matrix));
    }
    const x=Math.min(...points.map(p=>p.x)),y=Math.min(...points.map(p=>p.y)),w=Math.max(...points.map(p=>p.x))-x,h=Math.max(...points.map(p=>p.y))-y;
    // Fit the complete original artwork as one group; never stretch individual controls.
    screen.setAttribute('viewBox',`${x-12} ${y-12} ${w+24} ${h+24}`);
    screen.setAttribute('preserveAspectRatio','xMidYMid meet');
  }
  const loaded=fetch('/assets/source-entry/entry.json').then(r=>{if(!r.ok)throw Error('Original entry resources unavailable');return r.json();}).then(v=>{
    if(v.format!=='oc2-source-entry-ui-v1')throw Error('Original entry profile differs');manifest=v;return v;
  });
  async function show(name){
    await loaded;const profile=manifest.windows[name];const response=await fetch(profile.url);if(!response.ok)throw Error('Original entry drawing unavailable');
    const parsed=new DOMParser().parseFromString(await response.text(),'image/svg+xml');
    if(parsed.querySelector('parsererror,script,foreignObject'))throw Error('Invalid original entry drawing');
    screen=document.importNode(parsed.documentElement,true);screen.setAttribute('role','group');root.replaceChildren(screen);root.hidden=false;root.dataset.sourceScreen=name;
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
    centerLogin();
  }
  async function choose(){
    if(busy)return;busy=true;
    try{
      identities=savedEntryIdentities(localStorage);
      const response=await fetch('/__entry/characters',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({identities}),cache:'no-store'});
      if(!response.ok)throw Error('读取已有试玩角色失败');roles=(await response.json()).characters;
      await show('CharacterChooseCharacter');hide('._DeleteCharMC');hide('._RuneMC');hide('._FuncBtnMC');
      // Source InitPos anchors this panel to stageWidth minus its measured width.
      const panel=q('._CharacterMC');panel.setAttribute('transform',`translate(${(1136-panel.getBBox().width/20)*20} 0)`);
      for(const row of screen.querySelectorAll('[data-source-path^="._CharacterMC._CharacterList.item_"]')){
        if(!/^\._CharacterMC\._CharacterList\.item_(?:\d+|pre\d+|post\d+)$/.test(row.getAttribute('data-source-path')))continue;
        const match=row.getAttribute('data-source-path').match(/item_(\d+)$/),index=match?Number(match[1]):-1,role=roles[index];
        if(index<0||!role){row.setAttribute('display','none');row.setAttribute('aria-hidden','true');continue;}
        const prefix=row.getAttribute('data-source-path');hide(prefix+'._NewCharacter');hide(prefix+'._HighLight');
        label(prefix+'._ExistCharacter.txt_name',role.name);label(prefix+'._ExistCharacter.txt_level',word('GENERAL_MC_SELECT_LV')+role.level);
        for(const field of ['guild_name','ar_guild_name','ar_txt_level'])hide(prefix+'._ExistCharacter.'+field);
        const icon={1:'warrior',2:'mage',3:'ranger',4:'monk',5:'demonslayer'}[role.profession];image(q(prefix+'._ExistCharacter.DisplayIcon'),manifest.assets['ui/icons/userinterface/class_'+icon+'_0.5x.png']?.url);
        button(row,role.name,()=>select(role));
      }
      selected=roles[0]||null;select(selected);
      const play=q('._CharacterMC._StartBtn');label('._CharacterMC._StartBtn.mc_label.txt_label',word('GENERAL_MC_SELECT_BTN_PLAY'));
      button(play,word('GENERAL_MC_SELECT_BTN_PLAY'),()=>{
        const credentials=identities.find(v=>v.characterId===selected?.id);if(!isReady||!credentials)return;
        connect(selected.name,credentials,selected.profession);
      },!isReady||!selected);
      root.dataset.entryRoleCount=String(roles.length);
    }catch(error){root.dataset.entryError=error.message;fallback();}finally{busy=false;}
  }
  function select(role){
    selected=role;
    for(const el of screen.querySelectorAll('[data-source-path$="._ExistCharacter.SelectedEff"]')){
      const row=el.closest('[role=button]');el.setAttribute('display',row?.getAttribute('aria-label')===role?.name?'inline':'none');
    }
  }
  async function connectionError(message){
    await show('LoginMsgBox');hide('._DetailScrollPane');hide('._TxtTitle');hide('._VersionText');hide('.cnt._YesBtn');hide('.cnt._NoBtn');
    label('._MsgText',message);label('.cnt._OkBtn.mc_label.txt_label',word('GENERAL_OK'));button(q('.cnt._OkBtn'),word('GENERAL_OK'),login);
  }
  return {
    open(){const message=pendingError;pendingError=null;(message?connectionError(message):login()).catch(error=>{root.dataset.entryError=error.message;fallback();});},
    error(message){pendingError=String(message);},
    hide:hideRoot,
    ready(){isReady=true;const play=q('._CharacterMC._StartBtn');if(play&&selected){play.setAttribute('aria-disabled','false');play.setAttribute('tabindex','0');}}
  };
}
