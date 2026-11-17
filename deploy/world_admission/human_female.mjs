// Thin compatibility only for the currently integrated own HumanF normal15.
// The generic factory remains closed by default and never enables creation.
import{WORLD_BODY_CONTRACTS}from'./contracts.mjs';
import{createSourceWorldPendingJoins}from'./pending.mjs';
import{observeSourceWorldFirstPose}from'./first_pose.mjs';
import{createCommonSourceWorldCommandGate}from'./gate.mjs';
export{guardQuestPorts}from'./gate.mjs';
const contract=WORLD_BODY_CONTRACTS['human-female'];
export const HUMAN_FEMALE_POLICY=contract.policy;
const resolveContract=record=>record?.sourceAvatar?.key==='human-female'?contract:null;
export function createHumanFemalePendingJoins({policy,...options}){
 if(Object.entries(HUMAN_FEMALE_POLICY).some(([k,v])=>policy?.[k]!==v))throw Error('Current pinned HumanF policy required');
 const pending=createSourceWorldPendingJoins({...options,resolveContract});
 return Object.freeze({...pending,
  // Retain only the existing HumanF creation callback, not new body authority.
  canCreate(selection,avatar){try{return!pending.inspect().disposed&&avatar.key==='human-female'&&options.registry.check(avatar,selection.profession).key==='human-female'&&options.readPreparedBody()?.ready===true;}catch{return false;}},
 });
}
export function observeHumanFemaleFirstPose(options){return observeSourceWorldFirstPose({...options,resolveContract,inputFactory:(context)=>options.inputFactory(context)});}
export function createSourceWorldCommandGate(options={}){const gate=createCommonSourceWorldCommandGate({...options,resolveContract});return Object.freeze({...gate,inspect:()=>({...gate.inspect(),sourceBody:'human-female'})});}
