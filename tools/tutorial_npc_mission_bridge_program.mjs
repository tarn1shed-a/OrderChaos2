// Bounded interpreter for the pinned MissionDialog branch programs. Object,
// text measurement and callback storage are explicit host boundaries, not AVM2.
const PIN='1ca086266a17e5a12a46bcc6b5a37f1e3714dae6f66772f71256ea8161ca1236';
const METHODS={ShowQuestInfo:'bfedfd66896257e46f5d8765a1434c205417999b3c75b1e22402bc1ba77c8566',
  onOkClick:'8cbcd59a22e5ba5d68893f29d2415e34185b411d4bd417823adec682ce9dfce6',
  onCloseClick:'a93046ed840ee8063d15cecdf93308dadb4933212e4184339e06744a2f9c7acc',
  onEventQuestOpen:'e3323dbf8b2d776f22af9f2dfb082dd205cbb172937b7e68832509f5f115a788'};
const clone=v=>structuredClone(v),callbacks=new Set(['Hero_GetQuestInfoNPC','Player_GetString','Hero_SendAcceptQuestN','EventListCommon','Hero_SetQuestItemOp']);
export function createMissionProgramRuntime(program,info,event,windowContext){
  if(program?.format!=='oc2-original-mission-program-v1'||program.sourceSHA256!==PIN||
    Object.entries(METHODS).some(([k,v])=>program.methods?.[k]?.codeSHA256!==v))throw TypeError('Pinned original MissionDialog program required');
  if(!info||!event||!windowContext||!Number.isFinite(windowContext.currentWindowLevel)||
    ![windowContext.modelWindow0,windowContext.modelWindow1].every(v=>typeof v==='boolean'))throw TypeError('Actual source view/event/window-manager context required');
  const node=name=>({$node:name,x:0,y:0,width:1,height:1,textHeight:0,visible:false,enabled:false});
  const self={...program.constants,questId:info.questId,Status:info.Status,_statusFinished:0,_NumOfItemOp:0,
    _DisplayFlag:0,_summary_y:0,$node:'MissionDialog'};
  for(const name of ['btn_ok','btn_gray','txt_title','txt_summ','txt_sub_title','txt_detail','_RewardBoard','_watermark1','TutoBtn','_ScrollPanel','_detailBar','_ScrollContent'])self[name]=node(name);
  const actions=[];let shown=false,summary=false,steps=0;
  const get=(obj,key)=>{
    if(obj==null)throw Error('Missing original AS receiver '+key);
    if(obj===self&&callbacks.has(key))return {nativeCallback:key};
    if(Object.hasOwn(obj,key))return obj[key];
    if(obj.$node&&/^(Part[123]|Board|head|title|bounds|icon[0-9]+|txt[0-9]+|mcR[0-9]+|item(?:Op)?[0-9]+|m_icon|txt_reward)$/.test(key))return obj[key]=node(obj.$node+'.'+key);
    return undefined;
  };
  function call(obj,name,args){
    if(name==='call'&&obj?.nativeCallback){
      const native=obj.nativeCallback,values=args.slice(1);
      if(native==='Hero_GetQuestInfoNPC'){if(values[0]!==info.questId)throw Error('Original detail callback ID mismatch');Object.assign(values[1],clone(info));return undefined;}
      if(native==='Player_GetString'){
        if(!program.strings[values[0]])throw Error('Original general string unavailable '+values[0]);
        return program.strings[values[0]].text;
      }
      actions.push({nativeCallback:native,arguments:clone(values),networkSent:false,taskGranted:false});return undefined;
    }
    if(name==='getChildByName')return get(obj,args[0]);
    if(name==='setText'){obj.text=args[0];return;}
    if(name==='SetIcon'){obj.icon=args[0];return;}
    if(name==='numberWithCommas')return String(args[0]); // formatting is a named host boundary.
    if(name==='getCurWindowLevel')return windowContext.currentWindowLevel;
    if(name==='isModelWindowShow')return windowContext['modelWindow'+args[0]];
    if(name==='setShow'){shown=Boolean(args[0]);actions.push({presentation:'setShow',arguments:clone(args)});return;}
    if(name==='ShowQuestInfo')return execute('ShowQuestInfo');
    if(name==='RePosDetail'){summary=Boolean(args[0]);return;}
    if(['RePosReward','onCreate','trace','resetScroll','startScroll','InitBtnHandleByRange'].includes(name))return;
    throw Error('Unrestored original AS call '+name);
  }
  function execute(method,arg=null){
    const code=program.methods[method]?.instructions;if(!Array.isArray(code))throw Error('Original program absent '+method);
    const by=new Map(code.map((v,i)=>[v.at,i])),locals={0:self,1:arg},stack=[];let pc=0;
    const pop=()=>{if(!stack.length)throw Error('Original AS stack underflow');return stack.pop();};
    const jump=ins=>{if(!by.has(ins.targets[0]))throw Error('Original branch target missing');pc=by.get(ins.targets[0]);};
    while(pc<code.length){
      if(++steps>30000)throw Error('Bounded original AS instruction limit');
      const ins=code[pc++],a=ins.args,op=ins.op;
      if(op==='pushscope'||op==='pop')pop();
      else if(op==='label'||op==='coerce'){}
      else if(op==='coerce_s'){const v=pop();stack.push(v==null?null:String(v));}
      else if(op.startsWith('getlocal'))stack.push(locals[op==='getlocal'?a[0]:Number(op.slice(8))]);
      else if(op.startsWith('setlocal'))locals[op==='setlocal'?a[0]:Number(op.slice(8))]=pop();
      else if(op==='pushnull')stack.push(null);
      else if(op==='pushnan')stack.push(NaN);
      else if(op==='pushtrue'||op==='pushfalse')stack.push(op==='pushtrue');
      else if(op==='pushbyte'||op==='pushstring')stack.push(a[0]);
      else if(op==='dup')stack.push(stack.at(-1));
      else if(op==='getlex')stack.push(a[0]==='Common::ASDefines'?program.statuses:a[0]==='Common.Window::WindowManager'?{instants:{$manager:true}}:{asType:a[0]});
      else if(op==='findpropstrict')stack.push(self);
      else if(op==='getproperty'){const key=a[0]==='<runtime-name>'?pop():a[0];stack.push(get(pop(),key));}
      else if(op==='initproperty'||op==='setproperty'){const value=pop(),key=a[0]==='<runtime-name>'?pop():a[0],obj=pop();obj[key]=value;}
      else if(op==='constructprop'){if(a[0]!=='Object'||a[1]!==0)throw Error('Unrestored original constructor');pop();stack.push({});}
      else if(op==='astypelate'){
        const type=pop()?.asType,v=pop();stack.push(type==='Number'||type==='int'?typeof v==='number'?v:null:type==='Boolean'?typeof v==='boolean'?v:null:type==='String'?typeof v==='string'?v:null:v);
      }
      else if(op==='convert_d')stack.push(Number(pop()));
      else if(op==='convert_b')stack.push(Boolean(pop()));
      else if(op==='not')stack.push(!pop());
      else if(op==='increment')stack.push(Number(pop())+1);
      else if(op==='inclocal_i')locals[a[0]]=(Number(locals[a[0]])+1)|0;
      else if(['add','subtract','bitor','equals','greaterthan','lessthan'].includes(op)){
        const r=pop(),l=pop();stack.push(op==='add'?l+r:op==='subtract'?l-r:op==='bitor'?l|r:op==='equals'?l==r:op==='greaterthan'?l>r:l<r);
      }
      else if(op==='jump')jump(ins);
      else if(op==='iftrue'||op==='iffalse'){if(Boolean(pop())===(op==='iftrue'))jump(ins);}
      else if(['ifeq','ifne','iflt','ifnlt','ifngt'].includes(op)){
        const r=pop(),l=pop(),taken=op==='ifeq'?l==r:op==='ifne'?l!=r:op==='iflt'?l<r:op==='ifnlt'?!(l<r):!(l>r);if(taken)jump(ins);
      }
      else if(op==='callproperty'||op==='callpropvoid'){
        const args=stack.splice(stack.length-a[1],a[1]),obj=pop(),result=call(obj,a[0],args);if(op==='callproperty')stack.push(result);
      }
      else if(op==='returnvoid')return;
      else throw Error('Unrestored original MissionDialog opcode '+op);
    }
    throw Error('Original MissionDialog program did not return');
  }
  const state=()=>({shown,questId:self.questId,status:self.Status,statusFinished:self._statusFinished,
    title:self.txt_title.text,body:self.txt_detail.text,objective:self.txt_summ.text,showSummary:summary,
    okVisible:self.btn_ok.visible,grayVisible:self.btn_gray.visible,grayLabel:self.btn_gray.label,
    tutoVisible:self.TutoBtn.visible,watermark:self._watermark1.icon,displayFlag:self._DisplayFlag,
    numOptionalItems:self._NumOfItemOp,actions:clone(actions),steps,networkSent:false,taskGranted:false});
  return Object.freeze({open(){execute('onEventQuestOpen',event);return state();},
    ok(){execute('onOkClick');return state();},close(){execute('onCloseClick');return state();},inspect:state});
}
