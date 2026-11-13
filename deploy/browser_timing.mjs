// Read-only rendering measurements; enabled only by ?timing=1. Never predicts motion.
export function createBrowserTiming(canvas){
  if(new URLSearchParams(location.search).get('timing')!=='1')return null;
  let seq=0,identity=null,latest=null,pending=null,lastFrame=null,published=0;
  const sent=new Map(),samples=[],frames=[];
  const keys=new Set(['KeyW','KeyA','KeyS','KeyD','ArrowUp','ArrowDown','ArrowLeft','ArrowRight']);
  const moved=(a,b)=>a&&b&&Math.hypot(a.x-b.x,a.y-b.y)>.001;
  window.addEventListener('keydown',e=>{
    if(e.repeat||!keys.has(e.code)||document.getElementById('session-dialog')?.open||!latest)return;
    pending={at:performance.now(),baseline:{x:latest.x,y:latest.y},key:e.code};
  },true);
  return {
    input(data){
      if(data.type!=='input')return data;
      const id=++seq,at=performance.now();sent.set(id,{at,pending});
      if(pending&&!pending.firstSent)pending.firstSent=at;
      if(sent.size>120)sent.delete(sent.keys().next().value);
      return {...data,_timing:id};
    },
    receive(msg){
      if(msg.type==='welcome')identity=msg.id;
      if(msg.type!=='state')return;
      latest=msg.players?.find(p=>p.id===identity)||null;
      const stamp=sent.get(msg._timing?.seq);sent.delete(msg._timing?.seq);
      if(!stamp||!stamp.pending||stamp.pending!==pending||pending.reply||!moved(latest,pending.baseline))return;
      pending.reply={at:performance.now(),sentAt:stamp.at,timing:msg._timing};
    },
    rendered(paired){
      const now=performance.now();if(lastFrame!==null)frames.push(now-lastFrame);lastFrame=now;if(frames.length>600)frames.shift();
      if(pending?.reply&&moved(paired,pending.baseline)){
        const r=pending.reply;
        samples.push({key:pending.key,inputToSendMs:pending.firstSent-pending.at,
          supersededInputMs:r.sentAt-pending.firstSent,sentToStateMs:r.at-r.sentAt,...r.timing,networkAndEventLoopMs:r.at-r.sentAt-r.timing.serverMs,
          firstStateToRenderMs:now-r.at,inputToRenderMs:now-pending.at});
        if(samples.length>32)samples.shift();pending=null;published=0;
      }
      if(now-published<1000)return;published=now;
      const ordered=[...frames].sort((a,b)=>a-b);
      canvas.dataset.movementTiming=JSON.stringify({samples,frames:{n:frames.length,median:ordered[Math.floor(ordered.length*.5)]||0,p95:ordered[Math.floor(ordered.length*.95)]||0}});
    }
  };
}
