// Original 0x719970 minute calculation. Browser key/clock are explicit host inputs,
// not a recovered original account preference or server destination policy.
export function sourceBreakAwayMinutes(nowSeconds,lastSeconds){
  if(!Number.isSafeInteger(nowSeconds)||nowSeconds<1800)throw Error('Invalid break-away clock');
  if(lastSeconds===null)return {minutes:0,initialValue:nowSeconds-1800};
  if(!Number.isSafeInteger(lastSeconds)||lastSeconds<0)throw Error('Invalid break-away preference');
  const elapsed=Math.max(0,nowSeconds-lastSeconds);
  return {minutes:Math.max(0,Math.trunc((1800-elapsed)/60)),initialValue:null};
}
export function browserBreakAwayClock({storage,now=()=>Math.trunc(Date.now()/1000),key='oc2.break-away.client.v1'}={}){
  let memory=null;
  function read(){
    try{const value=storage?.getItem(key);if(value!==null&&value!==undefined&&/^\d+$/.test(value)&&Number.isSafeInteger(Number(value)))memory=Number(value);}catch{}
    return memory;
  }
  function write(value){memory=value;try{storage?.setItem(key,String(value));}catch{}}
  return {
    remaining(){const result=sourceBreakAwayMinutes(now(),read());if(result.initialValue!==null)write(result.initialValue);return result.minutes;},
    returned(){write(now());},
  };
}
