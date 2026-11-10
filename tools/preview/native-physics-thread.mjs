// Transport adapter only; all geometric/physical decisions are in the original ELF.
import {parentPort,workerData}from'node:worker_threads';
import {spawn}from'node:child_process';
import {createInterface}from'node:readline';
const child=spawn(workerData.python,[workerData.worker,workerData.config],{stdio:['pipe','pipe','pipe']});
let current=null,failure=null,stderr='';
function finish(value){if(!current)return;const {shared}=current,flag=new Int32Array(shared,0,2),bytes=new Uint8Array(shared,8),data=new TextEncoder().encode(JSON.stringify(value));
  if(data.length>bytes.length)throw Error('Native physics response exceeded transport capacity');bytes.set(data);Atomics.store(flag,1,data.length);Atomics.store(flag,0,1);Atomics.notify(flag,0);current=null;}
child.stderr.on('data',b=>{stderr=(stderr+b.toString()).slice(-4000);});
child.on('error',e=>{failure=e.message;finish({error:failure});});
child.on('exit',code=>{failure=`Original physics worker exited (${code}): ${stderr}`;finish({error:failure});});
createInterface({input:child.stdout}).on('line',line=>{try{finish(JSON.parse(line));}catch(e){finish({error:e.message});}});
parentPort.on('message',message=>{if(message.close){child.kill('SIGTERM');process.exit(0);}
  if(current)throw Error('Native physics transport has an outstanding request');current=message;
  if(failure)return finish({error:failure});child.stdin.write(JSON.stringify({operation:message.operation,data:message.data})+'\n');});
