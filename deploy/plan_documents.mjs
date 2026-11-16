// Startup-only dependency readers. Copying or aliasing the planning Map must
// not keep every original model's JSON string resident alongside parsed maps.
import {readFileSync}from'node:fs';
export function planDocument(path){
 const read=()=>readFileSync(path,'utf8');
 return Object.freeze({
  [Symbol.toPrimitive]:read,
  toString:read,
  match:pattern=>read().match(pattern),
  matchAll:pattern=>read().matchAll(pattern),
 });
}
