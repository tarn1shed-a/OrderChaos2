// Loopback QA only. Observes real input/DOM/frame timing; never creates input or sockets.
(()=>{
  const samples=[],gaps=[],waits=[],keys=new Set(['KeyW','KeyA','KeyS','KeyD','ArrowUp','ArrowDown','ArrowLeft','ArrowRight']);
  let pending=null,lastFrame=null,waitingAt=null;
  const position=()=>[...(document.getElementById('position')?.textContent||'').matchAll(/-?\d+(?:\.\d+)?/g)].map(v=>Number(v[0]));
  let previous=[];
  window.addEventListener('keydown',event=>{if(!event.repeat&&keys.has(event.code)&&!document.getElementById('session-dialog')?.open){let yaw=0;try{yaw=JSON.parse(document.getElementById('scene').dataset.sourceCameraControl).yaw*Math.PI/180;}catch{}const side=['KeyD','ArrowRight'].includes(event.code)?1:['KeyA','ArrowLeft'].includes(event.code)?-1:0,back=['KeyS','ArrowDown'].includes(event.code)?1:['KeyW','ArrowUp'].includes(event.code)?-1:0;pending={at:performance.now(),direction:[side*Math.cos(yaw)+back*Math.sin(yaw),-side*Math.sin(yaw)+back*Math.cos(yaw)],code:event.code};previous=position();}});
  const changes=new MutationObserver(()=>{
    const scene=document.getElementById('scene');
    const current=position();
    if(pending&&current.length===2&&previous.length===2&&current.reduce((sum,v,i)=>sum+(v-previous[i])*pending.direction[i],0)>.03&&scene?.dataset.loadingPresentation==='complete-window'){samples.push({code:pending.code,milliseconds:performance.now()-pending.at,stage:scene.dataset.loadingStage});pending=null;}
    previous=current;
  });
  changes.observe(document.documentElement,{subtree:true,childList:true,characterData:true});
  const stats=values=>{const a=[...values].sort((x,y)=>x-y);return{n:a.length,median:a[Math.floor(a.length*.5)]||0,p95:a[Math.floor(a.length*.95)]||0,max:a.at(-1)||0};};
  function frame(now){
    const scene=document.getElementById('scene'),active=!document.getElementById('session-dialog')?.open&&scene?.dataset.sourceArchiveWindow;
    if(active){if(lastFrame!==null)gaps.push(now-lastFrame);if(gaps.length>6000)gaps.shift();lastFrame=now;
      if(scene.dataset.loadingPresentation==='waiting-for-complete-window')waitingAt??=now;else if(waitingAt!==null){waits.push(now-waitingAt);waitingAt=null;}
    }else lastFrame=null;
    requestAnimationFrame(frame);
  }requestAnimationFrame(frame);
  setInterval(()=>{
    const scene=document.getElementById('scene'),report={inputToPosition:samples,frameGaps:stats(gaps),completedWindowWaitsMs:waits,waitingNowMs:waitingAt===null?0:performance.now()-waitingAt,
      loading:Object.fromEntries(Object.entries(scene?.dataset||{}).filter(([k])=>k.startsWith('loading')||k==='sourceArchiveWindow'))};
    document.documentElement.dataset.qaMovement=JSON.stringify(report);
    fetch('/__benchmark/movement',{method:'POST',body:JSON.stringify(report)}).catch(()=>{});
  },1000);
})();
