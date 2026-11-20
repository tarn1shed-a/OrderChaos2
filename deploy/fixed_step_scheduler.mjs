import {performance} from 'node:perf_hooks';

// This clock decides when to call a synchronous step. It is never passed to the
// game: the step keeps its original fixed dt and its existing source clock.
export function startFixedStepScheduler(step,periodMs,{now=()=>performance.now(),setTimer=setTimeout,clearTimer=clearTimeout}={}){
  if(typeof step!=='function'||!Number.isInteger(periodMs)||periodMs<1||periodMs>2147483647||
     [now,setTimer,clearTimer].some(fn=>typeof fn!=='function'))throw TypeError('Invalid fixed-step scheduler inputs');
  let active=true,timer=null,catchUp=false,lastObserved=-Infinity;
  const readTime=()=>{
    const value=now();
    if(!Number.isFinite(value)||value<lastObserved)throw Error('Fixed-step scheduler requires a monotonic clock');
    lastObserved=value;return value;
  };
  let deadline=readTime()+periodMs;
  const stats={startedSteps:0,completedSteps:0,catchUpSteps:0,rebases:0,earlyWakes:0,
    discardedScheduleDebtMs:0,lastStartedAtMs:null,lastCompletedAtMs:null,
    lastStepDurationMs:0,maxStepDurationMs:0,lastLatenessMs:0,maxLatenessMs:0,failed:false};
  function arm(){
    if(active)timer=setTimer(wake,Math.max(0,Math.ceil(deadline-readTime())));
  }
  function wake(){
    timer=null;if(!active)return;
    try{
      const started=readTime();
      // Timers may wake early; no game step is due until the actual deadline.
      if(started<deadline){stats.earlyWakes++;arm();return;}
      stats.startedSteps++;if(catchUp)stats.catchUpSteps++;
      stats.lastStartedAtMs=started;
      stats.lastLatenessMs=started-deadline;
      stats.maxLatenessMs=Math.max(stats.maxLatenessMs,stats.lastLatenessMs);
      step();
      const finished=readTime();
      stats.completedSteps++;stats.lastCompletedAtMs=finished;
      stats.lastStepDurationMs=finished-started;
      stats.maxStepDurationMs=Math.max(stats.maxStepDurationMs,stats.lastStepDurationMs);
      deadline+=periodMs;
      if(finished>=deadline){
        if(catchUp){
          // At most one extra overdue step, always on another timer turn. Drop
          // only scheduling debt after that. A short step resumes one period
          // from its real start; an overloaded step can run again immediately,
          // without an additional period's sleep. No simulated step is skipped.
          const next=Math.max(finished,started+periodMs);
          stats.discardedScheduleDebtMs+=next-deadline;stats.rebases++;
          deadline=next;catchUp=false;
        }else catchUp=true;
      }else catchUp=false;
      arm();
    }catch(error){
      active=false;stats.failed=true;
      if(timer!==null){clearTimer(timer);timer=null;}
      throw error; // The server step retains its existing storage/recovery path.
    }
  }
  try{arm();}catch(error){active=false;throw error;}
  return Object.freeze({
    stop(){if(!active)return;active=false;if(timer!==null){clearTimer(timer);timer=null;}},
    inspect(){return Object.freeze({...stats,active,pending:timer!==null,nextDeadlineMs:deadline,periodMs});},
  });
}

// Run only after the caller's original SHA guard and existing server stages.
// The original step body, 50ms argument and other timers remain byte-for-byte.
export function stageFixedStepServer(source){
  const replacements=[
    ['  const ticker = setInterval(() => {','  const ticker = startFixedStepScheduler(() => {'],
    ['clearInterval(ticker);','ticker.stop();'],
  ];
  for(const[from]of replacements)if(source.split(from).length!==2)throw Error('Fixed-step server anchor differs: '+from);
  if(source.includes('startFixedStepScheduler'))throw Error('Fixed-step server was already staged');
  for(const[from,to]of replacements)source=source.replace(from,to);
  return `import {startFixedStepScheduler} from ${JSON.stringify(import.meta.url)};\n`+source;
}
