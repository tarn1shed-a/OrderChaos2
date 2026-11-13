// Opt-in, connection-local timings. No credentials, coordinates, storage or new rules.
export function movementTrace(now=()=>performance.now()){
  const states=new WeakMap();
  return {
    input(ws,msg){
      if(msg.type!=='input')return;
      const seq=msg._timing;
      if(!Number.isSafeInteger(seq)||seq<1){states.delete(ws);return;}
      states.set(ws,{seq,received:now()});
    },
    accepted(ws){const s=states.get(ws);if(s)s.accepted=now();},
    before(ws){const s=states.get(ws);if(s&&s.started===undefined)s.started=now();},
    after(ws){const s=states.get(ws);if(s&&s.finished===undefined)s.finished=now();},
    reply(ws,data){
      const s=states.get(ws);
      if(data.type!=='state'||!s||s.accepted===undefined||s.finished===undefined)return data;
      const sent=now();states.delete(ws);
      return {...data,_timing:{seq:s.seq,handlerMs:s.accepted-s.received,queueMs:s.started-s.accepted,
        moveMs:s.finished-s.started,afterMoveMs:sent-s.finished,serverMs:sent-s.received}};
    }
  };
}
