// Loopback-only diagnostic: add the same per-request delay to both delivery versions.
import http from 'node:http';
import net from 'node:net';
import {writeFileSync,readFileSync} from 'node:fs';
const [port,targetPort,delay,path,holdBackground='0',mode='load']=process.argv.slice(2);
for(const value of [port,targetPort])if(!/^\d+$/.test(value||'')||Number(value)<1024||Number(value)>65535)throw Error('Explicit local ports required');
if(!/^\d+$/.test(delay||'')||Number(delay)>2000||!path?.includes('/analysis/raw/'))throw Error('Use a bounded delay and ignored report path');
if(!/^\d+$/.test(holdBackground)||Number(holdBackground)>60000)throw Error('Background hold must be bounded');
if(!['load','movement'].includes(mode))throw Error('Unknown loopback diagnostic mode');
let background=new Set(),unlockAt=0;
if(Number(holdBackground)){const index=await(await fetch(`http://127.0.0.1:${targetPort}/__delivery/index.json`)).json();background=new Set(index.plans['/explore-map.js'].background);}
const stats={startedAt:Date.now(),requests:0,bytes:0,statuses:{},lastPaths:[],runs:[]};
const observer=`(()=>{const check=()=>{const button=document.getElementById('join');if(!button||button.disabled)return;observer.disconnect();fetch('/__benchmark/ready',{method:'POST',body:JSON.stringify({navigationStart:performance.timeOrigin,readyMs:performance.now(),delivery:Object.fromEntries(Object.entries(document.documentElement.dataset).filter(([k])=>k.startsWith('delivery')))})});};const observer=new MutationObserver(check);observer.observe(document.documentElement,{subtree:true,attributes:true,attributeFilter:['disabled']});check();})();`;
const server=http.createServer((req,res)=>{
  const pathname=new URL(req.url,'http://localhost').pathname;
  if(pathname==='/__benchmark/observer.js'){res.writeHead(200,{'Content-Type':'text/javascript','Cache-Control':'no-store'});res.end(observer);return;}
  if(mode==='movement'&&pathname==='/__benchmark/movement.js'){res.writeHead(200,{'Content-Type':'text/javascript','Cache-Control':'no-store'});res.end(readFileSync(new URL('./movement_browser_observer.js',import.meta.url)));return;}
  if(mode==='movement'&&pathname==='/__benchmark/movement'&&req.method==='POST'){
    let body='';req.on('data',b=>{body+=b;if(body.length>65536)req.destroy();});req.on('end',()=>{try{stats.movement=JSON.parse(body);save();}catch{}res.writeHead(204);res.end();});return;
  }
  if(pathname==='/__benchmark/ready'&&req.method==='POST'){
    let body='';req.on('data',b=>{body+=b;if(body.length>4096)req.destroy();});req.on('end',()=>{try{const value=JSON.parse(body),run=stats.runs.at(-1);Object.assign(run,{...value,requests:stats.requests-run.requestStart,bytes:stats.bytes-run.byteStart,reportedAt:Date.now()});save();}catch{}res.writeHead(204);res.end();});return;
  }
  if(pathname.endsWith('.html')){unlockAt=Date.now()+Number(holdBackground);stats.runs.push({beganAt:Date.now(),requestStart:stats.requests,byteStart:stats.bytes});}
  stats.requests++;stats.lastPaths.push(new URL(req.url,'http://localhost').pathname);stats.lastPaths=stats.lastPaths.slice(-10);
  setTimeout(()=>{
    const upstream=http.request({hostname:'127.0.0.1',port:Number(targetPort),method:req.method,path:req.url,headers:req.headers},incoming=>{
      stats.statuses[incoming.statusCode]=(stats.statuses[incoming.statusCode]||0)+1;
      if((incoming.headers['content-type']||'').startsWith('text/html')&&incoming.statusCode===200){
        const chunks=[];incoming.on('data',b=>chunks.push(b));incoming.on('end',()=>{const body=Buffer.from(Buffer.concat(chunks).toString().replace('</head>','<script defer src="/__benchmark/observer.js"></script>'+(mode==='movement'?'<script defer src="/__benchmark/movement.js"></script>':'')+'</head>'));stats.bytes+=body.length;res.writeHead(200,{...incoming.headers,'content-length':body.length});res.end(body);});return;
      }
      res.writeHead(incoming.statusCode,incoming.headers);
      incoming.on('data',bytes=>{stats.bytes+=bytes.length;});incoming.pipe(res);
    });upstream.on('error',()=>{res.writeHead(502);res.end();});req.pipe(upstream);
  },Number(delay)+(background.has(pathname)?Math.max(0,unlockAt-Date.now()):0));
});
server.on('upgrade',(req,socket,head)=>{
  const upstream=net.connect(Number(targetPort),'127.0.0.1',()=>{
    const headers=req.rawHeaders.reduce((all,value,index)=>index%2===0?all+value+': '+req.rawHeaders[index+1]+'\r\n':all,'');
    upstream.write(`${req.method} ${req.url} HTTP/${req.httpVersion}\r\n${headers}\r\n`);if(head.length)upstream.write(head);socket.pipe(upstream).pipe(socket);
  });upstream.on('error',()=>socket.destroy());socket.on('error',()=>upstream.destroy());
});
const save=()=>writeFileSync(path,JSON.stringify({...stats,updatedAt:Date.now(),delayMs:Number(delay)},null,2));
const timer=setInterval(save,1000);timer.unref();
server.listen(Number(port),'127.0.0.1',()=>console.log(JSON.stringify({proxyPid:process.pid,port:Number(port),target:Number(targetPort),delayMs:Number(delay)})));
for(const signal of ['SIGTERM','SIGINT'])process.on(signal,()=>{save();server.close();process.exit(0);});
