// Connection metadata for the protected operator page only, never role saves.
import {isIP} from 'node:net';
const clean=value=>typeof value==='string'?value.replace(/[\x00-\x1f\x7f]/g,'').slice(0,512):'';
function address(value){const raw=clean(value).trim(),ip=raw.startsWith('::ffff:')?raw.slice(7):raw;return isIP(ip)?ip:null;}
export function readConnectionInfo(request={},{trustRailway=false}={}){
 const peer=address(request.socket?.remoteAddress),forwarded=trustRailway?address(request.headers?.['x-real-ip']):null;
 const userAgent=clean(request.headers?.['user-agent']);
 const browser=/Edg\//.test(userAgent)?'Edge':/OPR\//.test(userAgent)?'Opera':/Firefox\//.test(userAgent)?'Firefox':/Chrome\//.test(userAgent)?'Chrome':/Safari\//.test(userAgent)?'Safari':null;
 const platform=/Android/.test(userAgent)?'Android':/iPhone|iPad|iPod/.test(userAgent)?'iOS':/Windows/.test(userAgent)?'Windows':/Macintosh|Mac OS X/.test(userAgent)?'macOS':/Linux/.test(userAgent)?'Linux':null;
 return {ip:forwarded||peer,ipSource:forwarded?'railway-x-real-ip':peer?'socket':null,userAgent:userAgent||null,browser,platform};
}
export function noteConnectionPong(ws,now=Date.now()){
 if(Number.isFinite(ws.entryPingAt)&&now>=ws.entryPingAt&&now-ws.entryPingAt<=60000)ws.entryRttMs=now-ws.entryPingAt;
}
