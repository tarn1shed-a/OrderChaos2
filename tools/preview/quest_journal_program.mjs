// Bounded original branch interpreter for research controls, not a Flash/window
// implementation or a trusted receive capability. No network/UI/cache mutation.
const SOURCE='fb5f7211e4a9353ed025a30e6beb4863276437fd6adfb395ed93d340fba71c7a';
export async function createOriginalJournalControls(sourceJSON,{rows,selectedIndex=-1,isPUB,paramsStringCallback,abandonCallback=true}={}){
  if(typeof sourceJSON!=='string')throw TypeError('Pinned private original journal program required');
  if(!globalThis.crypto?.subtle)throw TypeError('WebCrypto SHA-256 required');
  const digest=await globalThis.crypto.subtle.digest('SHA-256',new TextEncoder().encode(sourceJSON));
  if(Array.from(new Uint8Array(digest),v=>v.toString(16).padStart(2,'0')).join('')!==SOURCE)throw TypeError('Pinned private original journal program required');
  if(!Array.isArray(rows)||rows.some(r=>!Number.isInteger(r.questId))||typeof isPUB!=='boolean'||typeof paramsStringCallback!=='boolean')throw TypeError('Explicit accepted-row, platform and parameter-string callback controls required');
  const program=JSON.parse(sourceJSON),params=program.msgboxParams,actions=[],priv='Common.Window:MsgboxParams::_params';
  const book={currSel:selectedIndex,_arrayQuestList:structuredClone(rows),Player_GetString:{port:'Player_GetString'},ShowMsg:{port:'ShowMsg'}};
  if(abandonCallback)book.Hero_AbandonQuest={port:'Hero_AbandonQuest'};
  const globals={...params.constants,'Common.Window::MsgboxParams':params.constants,Object:{className:'Object'},int:{className:'int'},'Common::ASDefines':{isPUB:{port:'isPUB'}}};
  let instructions=0;
  function get(obj,key){
    if(obj==null)throw Error('Missing original receiver '+key);
    if(obj.$params){const accessor=params.accessors.find(v=>v.name===key&&v.kind===2);if(accessor)return execute(accessor,obj,[]);}
    return obj[key];
  }
  function put(obj,key,value){
    if(obj==null)throw Error('Missing original write receiver');
    if(obj.$params){const accessor=params.accessors.find(v=>v.name===key&&v.kind===3);if(accessor){execute(accessor,obj,[value]);return;}}
    obj[key]=value;
  }
  function call(obj,key,args){
    if(key==='isPUB')return isPUB; // Explicit original platform input, not inferred.
    if(key==='call'&&obj?.port){
      const values=args.slice(1);
      if(obj.port==='Player_GetString'){
        const text=program.strings[values[0]];if(!text)throw Error('Missing original localized key');return text.text;
      }
      if(obj.port==='OnBtnClick'){
        actions.push({boundary:'MessageBox.OnBtnClick',arguments:structuredClone(values)});
        if(obj.forward)execute(program.methods['QuestListHero.MessageBoxYesNo'],book,values);
        return;
      }
      actions.push({boundary:obj.port,arguments:structuredClone(values),networkSent:false});return;
    }
    if(key==='PlaySound'){actions.push({boundary:'source-sound-port',arguments:structuredClone(args)});return;}
    if(key==='setShow'){obj.shown=Boolean(args[0]);actions.push({boundary:'source-window-show-port',arguments:structuredClone(args)});return;}
    if(key==='onCancelClick')return execute(program.methods['MessageBox.onCancelClick'],obj,args);
    throw Error('Unrestored original call '+key);
  }
  function execute(method,self,args){
    const code=method?.instructions;if(!Array.isArray(code))throw Error('Original method required');
    const by=new Map(code.map((v,i)=>[v.at,i])),locals={0:self},stack=[];args.forEach((v,i)=>locals[i+1]=v);let pc=0;
    const pop=()=>{if(!stack.length)throw Error('Original stack underflow');return stack.pop();};
    const jump=i=>{if(!by.has(i.targets[0]))throw Error('Original target absent');pc=by.get(i.targets[0]);};
    while(pc<code.length){
      if(++instructions>20000)throw Error('Original instruction bound');
      const i=code[pc++],a=i.args,op=i.op;
      if(op==='pushscope'||op==='pop')pop();
      else if(op==='coerce'||op==='label'){}
      else if(op==='coerce_s'){const v=pop();stack.push(v==null?null:String(v));}
      else if(op.startsWith('getlocal'))stack.push(locals[op==='getlocal'?a[0]:Number(op.slice(8))]);
      else if(op.startsWith('setlocal'))locals[op==='setlocal'?a[0]:Number(op.slice(8))]=pop();
      else if(op==='pushnull')stack.push(null);
      else if(op==='pushnan')stack.push(NaN);
      else if(op==='pushbyte'||op==='pushstring')stack.push(a[0]);
      else if(op==='pushtrue'||op==='pushfalse')stack.push(op==='pushtrue');
      else if(op==='convert_d')stack.push(Number(pop()));
      else if(op==='convert_b')stack.push(Boolean(pop()));
      else if(op==='astypelate'){
        const type=pop()?.className,value=pop();
        if(type!=='int'&&type!=='Object')throw Error('Unrestored original AS type');
        stack.push(type==='int'?(Number.isInteger(value)?value:null):(value&&typeof value==='object'?value:null));
      }
      else if(op==='getlex')stack.push(a[0]==='Common::GlobalFunc'?{instance:{$sound:true}}:globals[a[0]]);
      else if(op==='findpropstrict')stack.push(globals);
      else if(op==='getproperty'){const key=a[0]==='<runtime-name>'?pop():a[0];stack.push(get(pop(),key));}
      else if(op==='initproperty'||op==='setproperty'){const value=pop(),key=a[0]==='<runtime-name>'?pop():a[0];put(pop(),key,value);}
      else if(op==='constructsuper'){if(a[0]!==0)throw Error('Unrestored super inputs');pop();}
      else if(op==='constructprop'){
        if(a[1]!==0)throw Error('Unrestored constructor input');pop();
        if(a[0]==='Object')stack.push({});
        else if(a[0]==='Common.Window::MsgboxParams'){
          const value={$params:true};if(paramsStringCallback)value.Player_GetString={port:'Player_GetString'};
          execute(params.constructor,value,params.resolvedOptionalInputs);stack.push(value);
        }else throw Error('Unrestored constructor '+a[0]);
      }
      else if(op==='callproperty'||op==='callpropvoid'){
        const args=stack.splice(stack.length-a[1],a[1]),obj=pop(),value=call(obj,a[0],args);if(op==='callproperty')stack.push(value);
      }
      else if(op==='jump')jump(i);
      else if(op==='iftrue'||op==='iffalse'){if(Boolean(pop())===(op==='iftrue'))jump(i);}
      else if(op==='ifne'||op==='ifnge'){const r=pop(),l=pop();if(op==='ifne'?l!=r:!(l>=r))jump(i);}
      else if(op==='returnvoid')return;
      else if(op==='returnvalue')return pop();
      else throw Error('Unrestored original opcode '+op);
    }
    throw Error('Original method did not return');
  }
  const inspect=()=>({actions:structuredClone(actions),selectedIndex:book.currSel,instructions,networkSent:false,originalFlashExecuted:false});
  return Object.freeze({
    abandon(){execute(program.methods['QuestListHero.onAbandon'],book,[]);return inspect();},
    confirm(code){execute(program.methods['QuestListHero.MessageBoxYesNo'],book,[code]);return inspect();},
    select(index){if(!Number.isInteger(index)||index< -1||index>=rows.length)throw TypeError('Explicit selection index required');book.currSel=index;},
    messageButton(kind,{enableSound,fullScreenClose,forwardToBook=false}={}){
      if(!['onOkClick','onCancelClick','onFullScreenClick'].includes(kind)||typeof enableSound!=='boolean'||typeof fullScreenClose!=='boolean')throw TypeError('Explicit source MessageBox controls required');
      // Native ShowMsg -> GetMessageBoxInfo is NOT implemented by this port.
      const message={_msgParams:{EnableBtnSound:enableSound,FullScreenClose:fullScreenClose},OnBtnClick:{port:'OnBtnClick',forward:forwardToBook},shown:true};
      execute(program.methods['MessageBox.'+kind],message,[]);return {...inspect(),shown:message.shown,explicitCallbackBridge:forwardToBook};
    },inspect
  });
}
