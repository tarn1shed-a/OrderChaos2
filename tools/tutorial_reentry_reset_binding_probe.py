"""Execute the reviewed web binding with explicit recording RPC providers.

Only the two fixed, SHA-pinned source files are opened. No worker, socket,
account, character storage or runtime source is created or modified here.
"""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REVIEWED=ROOT/'analysis/raw/showcase-20261110/running-preview'
NODE=shutil.which('node')or'/Users/kevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'
FILES=('prototype/game/native-window-collision.mjs','prototype/public/source-shore-motion.js')

SCRIPT=r'''
import assert from'node:assert/strict';import vm from'node:vm';
const input=JSON.parse(await new Promise(resolve=>{let s='';process.stdin.on('data',v=>s+=v);process.stdin.on('end',()=>resolve(s));}));
const source=input.files[0],air=input.files[1],begin='function bind(',end='export function loadNativeWindowCollision(';
assert.equal(source.split(begin).length,2);assert.equal(source.split(end).length,2);
const code=air.replaceAll('export function ','function ')+'\n'+source.slice(source.indexOf(begin),source.indexOf(end));
const calls=[],rpc={request(operation,data){calls.push({operation,data:structuredClone(data)});
  if(operation==='reset')return true;
  if(operation==='restore-height')return{height:data.point[1]};
  if(operation==='sample'||operation==='ground')return{height:135.72999572753906};
  if(operation==='tick')return{position:data.position,grounded:true,velocityY:0,swimming:false,submerged:false,waterState:0,lastPosture:0x20,
    camera:{nativeCPU:true,position:data.position,target:data.position},sourceAnimation:{available:false,reason:'explicit-recording-rpc'}};
  throw Error('Unexpected fixture RPC '+operation);}};
const info={frame:{min:[0,0,0],max:[1,1,1],width:1,height:1},bounds:{min:[-3000,0,-1000],max:[-1000,200,1000]},instanceIds:[],sourceCameraCPU:true,nativeSHA256:input.nativeSHA256};
const context=vm.createContext({RESOURCE_WORLD:{speed:4.8},randomUUID:()=> 'explicit-fixture-scope',Date,Math,WeakMap,WeakSet,rpc,info,scope:'same-reviewed-bind'});
vm.runInContext(code+'\nthis.binding=bind(rpc,info,scope);',context,{timeout:1000});
const binding=context.binding,target={x:-2594,y:-64,worldY:135.72999572753906},old={id:'same-fixture-id',...target};
binding.move(old,{x:0,y:0},.05);assert.deepEqual(calls.map(r=>r.operation),['reset','tick']);calls.length=0;
binding.jumpPressed(old,true);binding.cameraInput(old,{yawDelta:19,pitchDelta:-8,distanceScale:1,near:.1});
binding.restoreHeight(old,target.worldY);binding.move(old,{x:0,y:0},.05);
const sameObjectRestore=structuredClone(calls);calls.length=0;
assert.deepEqual(sameObjectRestore.map(r=>r.operation),['restore-height','reset','tick']);
assert.equal(sameObjectRestore.at(-1).data.jump,true);assert.equal(sameObjectRestore.at(-1).data.control.yawDelta,19);
// A reconnect-created object has the same character ID but a new object identity.
// Old pending state remains tied to the released object, never copied to this one.
binding.jumpPressed(old,false);binding.jumpPressed(old,true);binding.cameraInput(old,{yawDelta:31,pitchDelta:-12,distanceScale:1,near:.1});
const fresh={id:'same-fixture-id',...target};binding.move(fresh,{x:0,y:0},.05);
const newObject=structuredClone(calls);calls.length=0;
assert.deepEqual(newObject.map(r=>r.operation),['reset','tick']);
assert.equal(newObject[0].data.identity,sameObjectRestore[1].data.identity);
assert.equal(newObject[1].data.jump,false);assert.deepEqual(newObject[1].data.control,{forward:false});
binding.move(fresh,{x:0,y:0},.05);const secondMove=structuredClone(calls);
assert.deepEqual(secondMove.map(r=>r.operation),['tick']);
console.log(JSON.stringify({sameObjectRestore,newObject,secondMove,
  scope:'literal reviewed JS bind; RPC/info/world are explicit recording fixtures; no CPU/browser/socket execution',
  inspectedSave:false,changedRuntime:false}));
'''


def binding_cases():
    manifest=json.loads((ROOT/'tools/local_mvp_runtime.json').read_text())['files'];sources=[];pins=[]
    for relative in FILES:
        raw=(REVIEWED/relative).read_bytes();digest=hashlib.sha256(raw).hexdigest()
        if digest!=manifest[relative]:raise ValueError('Reviewed web binding source differs: '+relative)
        sources.append(raw.decode());pins.append({'path':relative,'sha256':digest})
    result=subprocess.run([NODE,'--input-type=module','-e',SCRIPT],input=json.dumps({'files':sources,
        'nativeSHA256':'77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4'}),
        capture_output=True,text=True,cwd=ROOT,timeout=10)
    if result.returncode:raise ValueError('Reviewed binding fixture failed: '+result.stderr[-1800:])
    return {'files':pins,**json.loads(result.stdout)}


if __name__=='__main__':print(json.dumps(binding_cases(),ensure_ascii=False,indent=2))
