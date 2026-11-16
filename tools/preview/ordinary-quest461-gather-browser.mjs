import {sampleTrack,mixProperty} from './source-property-math-v1.mjs';
import {composeWorldLayers} from './source-world-layer-compose-v1.mjs';
import {createSourceGatherController} from './source-gather-controller-v1.mjs';
export const GATHER_BROWSER_SOURCE_SHA256='0fe5482598667a28f459cce0bd4a533fb440102df6b983c317a7742a1a82dea8';
export const GATHER_BROWSER_BINDING_SHA256='c939575b7a4d7be63419a7d679df0ce5a08b174c1e2ebd1b2823b0a77fd582a3';
const BINDING='c03c5f0cd41117b7f88b32f41d6a9a299f5bf0e802a6ea307de22e92ad37a473',F=Math.fround;
const hash=async(b,c)=>Array.from(new Uint8Array(await c.subtle.digest('SHA-256',b)),v=>v.toString(16).padStart(2,'0')).join('');
const decoder=new TextDecoder('utf-8',{fatal:true}),clone=x=>structuredClone(x),name={1:'position',5:'quaternion',10:'scale'};
/** Pure browser source producer. Supplied bytes are original world Model2,
 * not Class; source context/RNG/event/time are explicit presentation inputs. */
export async function createGatherBrowserLibrary({sourceBytes,bindingBytes,crypto=globalThis.crypto}={}){
 if(!(sourceBytes instanceof Uint8Array)||!(bindingBytes instanceof Uint8Array)||!crypto?.subtle)throw Error('Exact source bytes and WebCrypto required');
 const sb=sourceBytes.slice(),bb=bindingBytes.slice();
 if(await hash(sb,crypto)!==GATHER_BROWSER_SOURCE_SHA256||await hash(bb,crypto)!==GATHER_BROWSER_BINDING_SHA256)throw Error('Frozen world Gather input SHA differs');
 const source=JSON.parse(decoder.decode(sb)),binding=JSON.parse(decoder.decode(bb));
 if(source.format!=='oc2-world-gather-presentation-source-v1'||source.worldNotClass!==true||source.sourceModelId!==2||source.bindingId!==BINDING||binding.bindingId!==BINDING||source.properties!==110||source.valueBytes!==1536||JSON.stringify(source.propertyOrder)!==JSON.stringify(binding.propertyOrder))throw Error('Exact own world body/mask binding required');
 const clips=new Map(source.clips.map(c=>[c.name,c]));let live=true;const sessions=new Set();
 function sampled(child){const clip=clips.get(child?.clip);if(!clip||!Number.isFinite(child.ageMs)||child.ageMs<0||child.ageMs>clip.sourceRangeMs[1]-clip.sourceRangeMs[0])throw Error('Own bounded original source clock required');return clip.tracks.map(t=>sampleTrack(t,F(clip.sourceRangeMs[0]+child.ageMs)));}
 function values(layers){
  const perLayer=layers.map(l=>{const current=sampled(l.current),previous=l.previous?sampled(l.previous):null;return current.map((v,i)=>previous?mixProperty(source.propertyOrder[i].sourceType,v,previous[i],l.weights):v);});
  return composeWorldLayers({layers:perLayer,propertyOrder:source.propertyOrder,propertyWeights:source.mask.weights,specialIndices:source.mask.specialIndices,specialParents:source.mask.specialParents,specialBlendWeights:source.mask.specialBlendWeights});
 }
 function packet(result,actorKey){const bytes=new Uint8Array(1536),view=new DataView(bytes.buffer);let at=0;for(const row of result)for(const value of row){if(!Number.isFinite(value)||F(value)!==value)throw Error('Complete original float32 output required');view.setFloat32(at,value,true);at+=4;}if(at!==1536)throw Error('Source property packet width differs');return{format:'oc2-source-body-native-pose-v1',key:'elf-female',actorKey,bindingId:BINDING,valueEncoding:'float32-le-base64',valueBytes:1536,values:btoa(String.fromCharCode(...bytes))};}
 return Object.freeze({
  createSession({sessionKey,actorKey,profession,randomWords,initialIdleVariant,sourceContext}={}){
   if(!live||typeof sessionKey!=='string'||!sessionKey||sessionKey.length>160||typeof actorKey!=='string'||!actorKey||actorKey.length>128||![1,2,3,4,5].includes(profession))throw Error('Explicit immutable source presentation session required');
   const controller=createSourceGatherController({ranges:source.ranges,randomWords,initialIdleVariant,sourceContext});let current=null,disposed=false,sequence=0;const scopes=new Set();
   const check=()=>{if(!live||disposed)throw Error('World Gather source session disposed');};
   const dispose=()=>{if(disposed)return;disposed=true;current=null;controller.dispose();sessions.delete(dispose);};sessions.add(dispose);
   function makeProducer(input){check();if(!input||input.actorKey!==actorKey||input.profession!==profession||typeof input.scope!=='string'||!input.scope||input.scope.length>160||scopes.has(input.scope)||current!==null)throw Error('Unique current source owner/scope required');
    const scope=input.scope;let started=false,released=false;
    function owned(){check();if(!started||released||current!==scope)throw Error('Source presentation capability expired');}
    return Object.freeze({
     begin(){check();if(started||current!==null)throw Error('Source presentation already started');const out=controller.begin({scope,actorKey,profession});started=true;current=scope;scopes.add(scope);return out;},
     frame(milliseconds,timeval){owned();const out=controller.frame(scope,milliseconds,timeval),result=values(out.sourceLayers);sequence++;return{...out,pose:packet(result,actorKey),sourcePropertyCount:110,translatedOriginalCPU:true,sourceSession:sessionKey,sourceSequence:sequence,resourceFactoryOrGPUProduced:false};},
     finish(kind){owned();return controller.finish(scope,kind);},
     release(){if(released)return{released:true};released=true;if(!started||current!==scope)return{released:true};controller.release(scope);current=null;return{released:true};}
    });
   }
   return Object.freeze({sessionKey,actorKey,profession,makeProducer,
    inspect(){check();return clone({sessionKey,actorKey,profession,sequence,...controller.inspect()});},
    dispose,
    // Read-only properties are useful for strict native comparison. This
    // projects the same live queue, never accepts externally supplied poses.
    properties(){check();const q=controller.inspect().queue,layers=q.map((l,i)=>({channel:i,current:l.current,previous:l.previous,weights:l.remainingMs?[F(1-Math.min(F(.99),F(l.remainingMs/l.durationMs))),Math.min(F(.99),F(l.remainingMs/l.durationMs))]:[1,0]}));return values(layers).map((value,i)=>({...source.propertyOrder[i],value}));}
   });
  },
  inspect(){return{format:source.format,key:'elf-female',sourceModelId:2,bindingId:BINDING,properties:110,valueBytes:1536,admittedClips:['idle','item_loading'],currentActorQualificationOrGPUCompleted:false};},
  dispose(){if(!live)return;live=false;for(const close of[...sessions])close();}
 });
}

/** Host receive capability. Only the caller holding this object can feed the
 * already authenticated, ordered room stream. JSON 'source' claims grant no
 * authority. This produces poses only; it never sends a game command. */
export function createGatherEventReceiver({session,sessionKey,actorKey,profession,initialSequence}={}){
 if(!session||session.sessionKey!==sessionKey||session.actorKey!==actorKey||session.profession!==profession||initialSequence!==0)throw Error('Current immutable presentation session required');
 let sequence=initialSequence,current=null,scope=null,closed=false;
 return Object.freeze({
  consume(event){
   if(closed)throw Error('Gather receive capability closed');
   if(!event||event.sessionKey!==sessionKey||event.actorKey!==actorKey||event.sequence!==sequence+1||!Number.isSafeInteger(event.sequence)||typeof event.scope!=='string'||!event.scope||!['begin','frame','success','interrupt','release'].includes(event.operation))throw Error('Current ordered source presentation event required');
   const keys=['sessionKey','actorKey','sequence','operation','scope',...(event.operation==='frame'?['milliseconds','timeval']:[])];
   if(Object.keys(event).length!==keys.length||!keys.every(k=>Object.hasOwn(event,k)))throw Error('Unknown presentation event fields refused');
   let result;
   if(event.operation==='begin'){
    if(current)throw Error('Presentation already active');
    const next=session.makeProducer({scope:event.scope,actorKey,profession});result=next.begin();current=next;scope=event.scope;
   }else{
    if(!current||event.scope!==scope)throw Error('Foreign or expired source presentation scope');
    if(event.operation==='frame')result=current.frame(event.milliseconds,event.timeval);
    else if(event.operation==='release'){result=current.release();current=null;scope=null;}
    else result=current.finish(event.operation);
   }
   sequence=event.sequence;return result;
  },
  inspect(){return{sessionKey,actorKey,profession,sequence,scope,closed};},
  dispose(){if(closed)return;closed=true;current=null;scope=null;session.dispose();}
 });
}
