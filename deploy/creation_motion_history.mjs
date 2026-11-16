// Session-owned carrier of the observed original globals. Unknown Race callbacks
// are not synthesized from an HTTP completion, UI click, or profession number.
export function createCreationMotionHistory({counter,selected}){
 if(!Number.isInteger(counter)||counter<0||counter>2147483647||!Number.isInteger(selected)||selected<0||selected>6)throw Error('Explicit cold-session source globals required');
 let values={counter,selected},known=true;
 const body=i=>i&&Number.isInteger(i.race)&&i.race>=0&&i.race<5&&[0,1].includes(i.gender)&&!(i.race===4&&i.gender!==0);
 return Object.freeze({
  enterRace(identity,{sourceQueueEnabled=false}={}){
   if(!body(identity))throw Error('Explicit source Race identity required');
   if(typeof sourceQueueEnabled!=='boolean')throw Error('Explicit Race source-carrier capability required');
   // 542da4 stage0 writes selected only. It does not resolve an unknown counter.
   values.selected=identity.race===0&&identity.gender===0?6:0;
   // The Race wrapper's generic selection callback is not carried by the
   // finite preview yet. Even without a click its next source tick is unknown.
   if(!sourceQueueEnabled)known=false;
  },
  raceInput(before,after){
   if(!body(before)||!body(after))throw Error('Explicit original Character_Race input required');
   if(before.race!==after.race||before.gender!==after.gender)known=false;
  },
  unresolvedClassCarrier(){known=false;},
  unresolvedCarrier(){known=false;},
  raceFrame(frame){this.classFrame(frame);},
  classFrame(frame){
   if(!frame||!Number.isInteger(frame.counter)||frame.counter<0||frame.counter>2147483647||!Number.isInteger(frame.selected)||frame.selected<0||frame.selected>6)throw Error('Observed source Class frame required');
   values={counter:frame.counter,selected:frame.selected};known=true;
  },
  read(){return known?{...values}:null;},
 });
}
