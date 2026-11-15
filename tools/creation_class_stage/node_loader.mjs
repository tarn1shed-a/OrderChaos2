// Offline resolver only. No network, DOM, server or image substitution.
import {pathToFileURL} from 'node:url';
import {resolve as pathResolve} from 'node:path';
export async function resolve(specifier,context,next){
 if(specifier==='/source-scene-palette.js?palette=1')return {url:pathToFileURL(pathResolve('tools/preview/source-scene-palette.js')).href,format:'module',shortCircuit:true};
 return next(specifier,context);
}
