// Explicit QA identities only. Receipts and raw results must stay in ignored paths.
import {readFileSync,writeFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
const require=createRequire(new URL('../analysis/raw/showcase-20261110/running-preview/prototype/package.json',import.meta.url));
const WebSocket=require('ws');
const [url,receipt,output,countText='2']=process.argv.slice(2),count=Number(countText);
assert(url&&receipt&&output&&[1,2].includes(count));
const identities=JSON.parse(readFileSync(receipt,'utf8')).peers.slice(0,count),peers=[];
const pause=ms=>new Promise(ok=>setTimeout(ok,ms));
async function until(check,label){for(let i=0;i<200;i++){if(check())return;await pause(20);}throw Error('Timing timeout: '+label);}
const samples=[];
try{
  for(const saved of identities){
    const socket=new WebSocket(url.replace(/^http/,'ws')+'/ws',{origin:url});
    const p={socket,state:null,welcome:null,pending:null};peers.push(p);
    socket.on('error',()=>{});
    socket.on('message',raw=>{
      const at=performance.now(),msg=JSON.parse(raw);if(msg.type==='error')throw Error(msg.message);
      if(msg.type==='welcome')p.welcome=msg;
      if(msg.type==='state'){
        p.state=msg;
        if(p.pending&&msg._timing?.seq===p.pending.seq){
          const timing=msg._timing,total=at-p.pending.at;
          samples.push({connections:count,sentToStateMs:total,...timing,networkAndEventLoopMs:total-timing.serverMs});p.pending=null;
        }
      }
    });
    await new Promise((ok,fail)=>{socket.once('open',ok);socket.once('error',fail);});
    socket.send(JSON.stringify({type:'join',scene:'resources',mapWindow:'tutorial',room:'TIMING-QA-01',name:saved.name,...saved.identity}));
    await until(()=>p.welcome&&p.state,'join');assert(p.welcome.restored,'Use existing owned QA role');
  }
  await until(()=>peers.every(p=>p.state.players.length===count),'peers');
  const p=peers[0];
  for(let i=1;i<=12;i++){
    await pause(130+i*7);p.pending={seq:i,at:performance.now()};
    p.socket.send(JSON.stringify({type:'input',x:i%2?1:-1,y:0,_timing:i}));
    await until(()=>p.pending===null,'correlated state');
    p.socket.send(JSON.stringify({type:'input',x:0,y:0}));await pause(150);
  }
  const stats=key=>{const a=samples.map(s=>s[key]).sort((a,b)=>a-b);return{n:a.length,min:a[0],median:a[Math.floor(a.length/2)],max:a.at(-1)};};
  const report={format:'oc2-movement-timing-v1',connections:count,samples,summary:Object.fromEntries(['sentToStateMs','handlerMs','queueMs','moveMs','afterMoveMs','serverMs','networkAndEventLoopMs'].map(k=>[k,stats(k)]))};
  writeFileSync(output,JSON.stringify(report,null,2),{mode:0o600,flag:'wx'});console.log(JSON.stringify(report.summary));
}finally{for(const p of peers)p.socket.close();await pause(250);for(const p of peers)p.socket.terminate();}
