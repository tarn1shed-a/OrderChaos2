// Bounded original component instructions with explicit geometry/event ports.
// No Flash movie, DOM, timer, task state, native renderer or input admission.
export const JOURNAL_WIDGET_PROGRAM_SHA256='4b4c88e6cc7edcc7aaee351dbb01533c4e7f9e2f83fbc17821c7990407492171';
const finite=(v,name)=>{if(!Number.isFinite(v))throw TypeError('Explicit finite '+name+' required');return v;};
const leaf=k=>String(k).split('::').at(-1),copy=v=>structuredClone(v);
function rectangle(v,name){for(const k of ['left','right','top','bottom'])finite(v?.[k],name+'.'+k);if(v.right<v.left||v.bottom<v.top)throw TypeError('Ordered '+name+' required');return copy(v);}
export async function createOriginalJournalWidgets(sourceJSON){
  if(typeof sourceJSON!=='string'||!globalThis.crypto?.subtle)throw TypeError('Pinned source and WebCrypto required');
  const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(sourceJSON));
  if([...new Uint8Array(digest)].map(v=>v.toString(16).padStart(2,'0')).join('')!==JOURNAL_WIDGET_PROGRAM_SHA256)throw TypeError('Original widget program differs');
  const p=JSON.parse(sourceJSON);
  function runtime(){
    const trace=[];let steps=0;
    const globals={Array:{$type:'Array'},'flash.display::MovieClip':{$type:'MovieClip'},Math,
      'gluic.events::ButtonEvent':{$type:'ButtonEvent',PRESS:'PRESS',RELEASE:'RELEASE'},
      'gluic.components.ui::isBeingAltered':false};
    const movie=v=>!!v&&v.$movie===true;
    function get(o,key){
      if(o==null)throw TypeError('Missing source property receiver '+key);if(o===globals)return o[key];key=leaf(key);
      if((o.$class==='ScrollBar'||o.$class==='ScrollBarNew')&&key==='value')return run('ScrollBar','value',o,[],2);
      if(o.$class==='ScrollBarNew'&&key==='yScroll')return run('ScrollBar','yScroll',o,[],2);
      return o[key];
    }
    function put(o,key,v){
      if(o==null)throw TypeError('Missing source write receiver');key=leaf(key);
      if((o.$class==='ScrollBar'||o.$class==='ScrollBarNew')&&key==='value'){run('ScrollBar','value',o,[v],3);return;}
      o[key]=v;
      if(['height','width','visible','x','y','enabled'].includes(key))trace.push({port:'property-write',node:o.$name??o.$class,field:key,value:v});
    }
    function call(o,key,args){
      key=leaf(key);if(o==null)throw TypeError('Missing source call receiver '+key);
      if(o===Math&&key==='round')return Math.round(args[0]);
      if(o===globals&&key==='MovieClip')return movie(args[0])?args[0]:null;
      if(key==='push'&&Array.isArray(o))return o.push(...args);
      if(key==='getChildByName')return o.children?.[args[0]]??null;
      if(key==='getBounds'){
        if(args[0]!==o.$boundsReference)throw TypeError('Unprovided getBounds reference space');return copy(o.$bounds);
      }
      if(key==='getContentBounds')return copy(o.$contentBounds);
      if(key==='dispatchEvent'){trace.push({port:'original-event-dispatch-not-delivered',node:o.$name,event:args[0]});return;}
      if(key==='trace'){trace.push({port:'source-trace',arguments:args});return;}
      if(key==='change'){trace.push({port:'original-change-not-delivered',arguments:args});return;}
      if(key==='setBoundsRect'){trace.push({port:'original-setBoundsRect-awaiting-host-measurement'});return;}
      if(o.$class==='DeferredBar'&&key==='InitBtnHandleByRange'){o.requestedRange=args[0];trace.push({port:'original-bar-init-awaiting-host-measurements',range:args[0]});return;}
      let cl=o.$class;
      if(cl==='ScrollBarNew'&&!p.methods[cl+'.'+key+'#1'])cl='ScrollBar';
      if(cl&&p.methods[cl+'.'+key+'#1'])return run(cl,key,o,args);
      throw TypeError('Unprovided source call '+key);
    }
    function run(cl,name,self,args=[],kind=1){
      const m=name==='<constructor>'?p.classes[cl].constructor:p.methods[cl+'.'+name+'#'+kind];
      if(!m)throw TypeError('Original method absent');
      const code=m.instructions,by=new Map(code.map((v,i)=>[v.at,i])),locals={0:self},stack=[];let pc=0;
      args.forEach((v,i)=>locals[i+1]=v);
      const pop=()=>{if(!stack.length)throw TypeError('Original stack underflow');return stack.pop();};
      function scope(key){return Object.hasOwn(globals,key)?globals:self;}
      const jump=i=>{if(!by.has(i.targets[0]))throw TypeError('Original branch absent');pc=by.get(i.targets[0]);};
      while(pc<code.length){
        if(++steps>30000)throw TypeError('Original widget instruction bound');
        const i=code[pc++],op=i.op,a=i.args;
        if(op==='pushscope'||op==='pop')pop();
        else if(['coerce','label'].includes(op)){}
        else if(op.startsWith('getlocal'))stack.push(locals[op==='getlocal'?a[0]:Number(op.slice(8))]);
        else if(op.startsWith('setlocal'))locals[op==='setlocal'?a[0]:Number(op.slice(8))]=pop();
        else if(op==='kill')delete locals[a[0]];
        else if(op==='pushnull')stack.push(null);
        else if(op==='pushnan')stack.push(NaN);
        else if(['pushbyte','pushshort','pushdouble','pushstring'].includes(op))stack.push(a[0]);
        else if(op==='pushtrue'||op==='pushfalse')stack.push(op==='pushtrue');
        else if(op==='dup')stack.push(stack.at(-1));
        else if(op==='convert_d')stack.push(Number(pop()));
        else if(op==='convert_b')stack.push(Boolean(pop()));
        else if(op==='not')stack.push(!pop());
        else if(op==='increment'||op==='decrement')stack.push(Number(pop())+(op==='increment'?1:-1));
        else if(op==='coerce_s'){const v=pop();stack.push(v==null?null:String(v));}
        else if(op==='getlex')stack.push(get(scope(a[0]),a[0]));
        else if(op==='findpropstrict'||op==='findproperty')stack.push(scope(a[0]));
        else if(op==='getproperty'){const key=a[0]==='<runtime-name>'?pop():a[0];stack.push(get(pop(),key));}
        else if(op==='initproperty'||op==='setproperty'){const v=pop(),key=a[0]==='<runtime-name>'?pop():a[0];put(pop(),key,v);}
        else if(op==='istypelate'||op==='astypelate'){
          const type=pop()?.$type,v=pop();if(type!=='MovieClip')throw TypeError('Unprovided source cast');stack.push(op==='istypelate'?movie(v):movie(v)?v:null);
        }
        else if(['add','subtract','multiply','divide','greaterthan','greaterequals','lessthan'].includes(op)){
          const r=pop(),l=pop();stack.push(op==='add'?l+r:op==='subtract'?l-r:op==='multiply'?l*r:op==='divide'?l/r:op==='greaterthan'?l>r:op==='greaterequals'?l>=r:l<r);
        }
        else if(op==='jump')jump(i);
        else if(op==='iftrue'||op==='iffalse'){if(Boolean(pop())===(op==='iftrue'))jump(i);}
        else if(['ifne','iflt','ifnlt','ifngt'].includes(op)){const r=pop(),l=pop();if(op==='ifne'?l!==r:op==='iflt'?l<r:op==='ifnlt'?!(l<r):!(l>r))jump(i);}
        else if(op==='constructsuper'){if(a[0]!==0)throw TypeError('Unknown original super input');pop();trace.push({port:'MovieClip-super-not-executed'});}
        else if(op==='constructprop'){
          const args=stack.splice(stack.length-a[1],a[1]);pop();
          if(a[0]==='Array')stack.push([]);
          else if(a[0]==='gluic.events::ButtonEvent')stack.push({type:args[0],bubbles:args[1],cancelable:args[2],data:args[3]});
          else throw TypeError('Unprovided source constructor');
        }
        else if(op==='callproperty'||op==='callpropvoid'){
          const args=stack.splice(stack.length-a[1],a[1]),value=call(pop(),a[0],args);if(op==='callproperty')stack.push(value);
        }
        else if(op==='returnvoid')return;
        else if(op==='returnvalue')return pop();
        else throw TypeError('Unprovided original opcode '+op);
      }
      throw TypeError('Original widget did not return');
    }
    return{run,trace,globals,get steps(){return steps;}};
  }
  function pager(measure,{pages,currentPage=pages>0?0:-1,horizontal=true}={}){
    finite(measure?.widthBak,'pre-initialization PageIndicator.width');
    if(!Number.isInteger(pages)||pages<0||pages>10||!Number.isInteger(currentPage)||typeof horizontal!=='boolean'||measure.indicators?.length!==10)throw TypeError('Bounded original page/ten-child inputs required');
    const rt=runtime(),self={$class:'PageIndicator',$movie:true,width:measure.widthBak,children:{},...p.classes.PageIndicator.constants};
    for(let i=0;i<10;i++){const m=measure.indicators[i];if(m.name!=='mc_Indi'+i||m.selectionChild!=='SelState')throw TypeError('Exact original page aliases required');
      if(finite(m.width,'page width')<=0)throw TypeError('Positive original page width required');finite(m.x,'authored page x');
      self.children[m.name]={$movie:true,$name:m.name,width:m.width,x:m.x,children:{SelState:{$movie:true,$name:m.name+'.SelState'}}};}
    rt.run('PageIndicator','<constructor>',self);rt.run('PageIndicator','InitPageNum',self,[pages,horizontal]);rt.run('PageIndicator','SetCurrPageNum',self,[currentPage]);
    return{pages:self._PageNum,currentPage:self._CurrPage,realWidth:self._Width,widthBak:self._WidthBak,
      indicators:Object.values(self.children).map(n=>({name:n.$name,x:n.x,visible:n.visible,selected:n.children.SelState.visible??null})),trace:rt.trace,sourceInstructions:rt.steps,originalFlash:false};
  }
  function handleByRange({slotWidth,slotHeight,vertical},range){
    if(finite(slotWidth,'slot width')<=0||finite(slotHeight,'slot height')<=0||typeof vertical!=='boolean'||finite(range,'overflow')<0)throw TypeError('Positive source slot and nonnegative overflow required');
    const rt=runtime(),self={$class:'ScrollBarNew',_yScroll:vertical,slot:{width:slotWidth,height:slotHeight},btn_handle:{$name:'mc_btn_handle'}};
    rt.run('ScrollBarNew','InitBtnHandleByRange',self,[range]);
    return{handleHeight:self.btn_handle.height??null,handleWidth:self.btn_handle.width??null,valueStep:self._ValueStep,enabledAfter:self.enabled,trace:rt.trace,sourceInstructions:rt.steps};
  }
  function barValue({slotWidth,slotHeight,slotBounds,handleBounds,handleX,handleY},value,{isBeingAltered}={}){
    finite(slotWidth,'selected slot width');finite(slotHeight,'selected slot height');finite(handleX,'handle x');finite(handleY,'handle y');finite(value,'source ratio');
    if(typeof isBeingAltered!=='boolean')throw TypeError('Explicit original isBeingAltered input required');
    const sr=rectangle(slotBounds,'selected slot getBounds(bar)'),hr=rectangle(handleBounds,'selected handle getBounds(bar)'),rt=runtime();
    const self={$class:'ScrollBar',_coordsRef:null,slot:{$movie:true,$name:'mc_slot',width:slotWidth,height:slotHeight,$bounds:sr},btn_handle:{$movie:true,$name:'mc_btn_handle',x:handleX,y:handleY,$bounds:hr}};
    self._coordsRef=self;self.slot.$boundsReference=self;self.btn_handle.$boundsReference=self;
    rt.globals['gluic.components.ui::isBeingAltered']=isBeingAltered;
    rt.run('ScrollBar','getBoundsAndMoveItAllAround',self);
    if(self._maxPos<=self._minPos)throw TypeError('Degenerate original bar range cannot publish a finite ratio');
    rt.run('ScrollBar','value',self,[value],3);const ratio=rt.run('ScrollBar','value',self,[],2);
    return{vertical:self._yScroll,min:self._minPos,max:self._maxPos,handleX:self.btn_handle.x,handleY:self.btn_handle.y,actualRatio:ratio,
      trace:rt.trace,sourceInstructions:rt.steps,referenceSpace:'bar-local; original constructor coordsRef=self',fullMovieMeasurement:false};
  }
  function contentY({contentY,contentTop,contentHeight,boundsTop,boundsHeight},ratio){
    for(const [k,v]of Object.entries({contentY,contentTop,contentHeight,boundsTop,boundsHeight,ratio}))finite(v,k);
    const rt=runtime(),self={content:{y:contentY},_boundsRect:{top:boundsTop,height:boundsHeight},$contentBounds:{top:contentTop,height:contentHeight}};
    rt.run('ScrollPane','positionRatioY',self,[ratio],3);
    return{y:self.content.y,sourceInstructions:rt.steps,clampedBySource:false,measurementPort:'getContentBounds in current pane coordinates'};
  }
  function bodyLayout({expanded,summary,detail,textHeight,maskHeight1,maskHeight2,previousStepBarVisible,previousBodyBarVisible}){
    if(typeof expanded!=='boolean'||typeof previousStepBarVisible!=='boolean'||typeof previousBodyBarVisible!=='boolean'||typeof summary!=='string'||typeof detail!=='string')throw TypeError('Explicit source body state required');
    finite(textHeight,'textHeight for the resulting HTML text');finite(maskHeight1,'MaskHeight1');finite(maskHeight2,'MaskHeight2');
    if(textHeight<0||maskHeight1<=0||maskHeight2<maskHeight1)throw TypeError('Original body measurements required');
    const rt=runtime(),self={$class:'QuestListHero',strSummary:summary,strDetail:detail,_MaskHeight1:maskHeight1,_MaskHeight2:maskHeight2,
      _IsScroll3Visible:previousStepBarVisible,m_Scroll3:{visible:previousStepBarVisible},m_Scroll2:{$class:'DeferredBar',visible:previousBodyBarVisible},
      panel_content:{$name:'panel_content',bounds:{}},txt_detail:{textHeight},mc_panelContent:{},m_ScrollPanel2:{},mc_textFoldMark:{},mc_textStretchMark:{},mc_textHZ:{},mc_textHZDown:{}};
    for(const [name,node]of Object.entries(self))if(node&&typeof node==='object')node.$name=name;
    rt.run('QuestListHero',expanded?'stretchText':'foldText',self);
    return{expanded:self.isTextStretched,htmlText:self.txt_detail.htmlText,textFieldHeight:self.txt_detail.height,maskHeight:self.panel_content.bounds.height,
      contentY:self.mc_panelContent.y,barVisible:self.m_Scroll2.visible,barRequestedRange:self.m_Scroll2.requestedRange??null,
      barRequestedDisplayHeight:self.m_Scroll2.height??null,barRequestedValue:self.m_Scroll2.value??null,stepBarVisible:self.m_Scroll3.visible,
      trace:rt.trace,sourceInstructions:rt.steps,textHeightMeasuredByCaller:true,originalFlash:false};
  }
  return Object.freeze({pager,handleByRange,barValue,contentY,bodyLayout,authoredMeasurements:copy(p.authoredMeasurements),
    aliases:copy(p.aliases),limits:copy(p.limits)});
}
