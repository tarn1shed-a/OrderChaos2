// One pinned metadata join for delivery preparation and server assembly.
// It imports only the frozen contract data, never a native worker or a model.
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {createPinnedResourceReader} from './source_resource_reader.mjs';
import {buildSourceContentCatalog} from './source_content_catalog.mjs';

export const SOURCE_CONTENT_CATALOG_URL='/__delivery/source-content-catalog.json';
const hash=b=>createHash('sha256').update(b).digest('hex');
const json=bytes=>JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));
export function readSourceContentDeclaration(root){
  const data=JSON.parse(readFileSync(resolve(root,'tools/source_world_python.json'),'utf8'));
  if(data.format!=='oc2-source-world-python-closure-v1'||data.content?.format!=='oc2-source-world-content-v1')throw Error('Reviewed source content declaration required');
  return data;
}
export async function loadSourceContentCatalog({root,runtime,delivery,files,reader,declaration=readSourceContentDeclaration(root)}){
  reader??=createPinnedResourceReader({roots:[runtime,delivery,resolve(root,'deploy')]});
  const privateBytes=pin=>{
    if(!pin||Object.keys(pin).sort().join(',')!=='bytes,path,sha256'||typeof pin.path!=='string'||
      !pin.path||/[\\:?#%\x00-\x1f\x7f]/.test(pin.path)||pin.path.split('/').some(p=>!p||p==='.'||p==='..'))throw Error('Exact runtime-relative content plan required');
    return reader.readBytes({path:resolve(runtime,pin.path),bytes:pin.bytes,sha256:pin.sha256});
  };
  const plans=Object.fromEntries(Object.entries(declaration.content.plans).map(([name,pin])=>[name,json(privateBytes(pin))]));
  const latestPlan=json(privateBytes(declaration.plans.latestWorld));
  // This older shared browser closure is referenced by SHA in latestWorld;
  // its byte count comes from the already verified private bundle manifest.
  const actorPath='native-inputs/world-latest-v1/browser-import-plan.json';
  const bundle=JSON.parse(readFileSync(resolve(runtime,'bundle-manifest.json'),'utf8'));
  const actorPin=bundle.files?.[actorPath];
  if(!actorPin||actorPin.sha256!==latestPlan.browserImportPlanSHA256)throw Error('Original actor import closure differs');
  const actorImportPlan=json(privateBytes({path:actorPath,sha256:actorPin.sha256,bytes:actorPin.bytes}));
  function publicBytes(pin){
    const actual=files[pin.url];
    if(!actual||actual.bytes!==pin.bytes||actual.sha256!==pin.sha256)throw Error('Content delivery identity differs: '+pin.url);
    return reader.readBytes({path:resolve(actual.path),bytes:pin.bytes,sha256:pin.sha256});
  }
  const registryProfile=json(publicBytes(declaration.content.registry));
  for(const module of declaration.content.browserModules)publicBytes(module);
  const contractPath='prototype/game/world-admission-latest-v1/contracts.mjs';
  const contractPin=latestPlan.newPayloadFiles?.[contractPath];
  if(!contractPin||Object.keys(contractPin).sort().join(',')!=='bytes,sha256')throw Error('Exact original common contract data pin required');
  reader.verify({path:resolve(runtime,contractPath),bytes:contractPin.bytes,sha256:contractPin.sha256});
  const contracts=await import(pathToFileURL(resolve(runtime,contractPath)));
  const catalog=buildSourceContentCatalog({declaration,registryProfile,latestPlan,actorImportPlan,
    normalContracts:contracts.getNormalContract,gatherContracts:contracts.getGatherContract,
    additionalPlans:plans,publicResources:files});
  const projectionBytes=Buffer.from(JSON.stringify(catalog.browserProjection));
  const projectionPin={url:SOURCE_CONTENT_CATALOG_URL,bytes:projectionBytes.length,sha256:hash(projectionBytes)};
  return {catalog,declaration,latestPlan,plans,reader,projectionBytes,projectionPin};
}
