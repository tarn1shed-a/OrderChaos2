// Deployment-only append layer. Reviewed entry and base bundle stay unchanged.
export const FIRE10_MANIFEST='/assets/source-scene-fire10/manifest.json';
const IMPORT="import {loadSourceSceneFire10Runtime} from '/source-scene-effect-fire10-runtime.js';\nlet sourceSceneFire10=null,sourceSceneFire10DiagnosticAt=-Infinity;\n";
export function stageFire10Entry(source){
 if(source.includes(IMPORT))throw Error('Scene effects overlay already applied');
 if(!source.includes('if(!sceneStages.present(windowChange))'))throw Error('Scene effects require the existing staged map');
 const replace=(from,to)=>{if(source.split(from).length!==2)throw Error('Scene effects anchor differs: '+from.slice(0,72));source=source.replace(from,to);};
 replace('    requestAnimationFrame(draw);sceneStages.start();',
  "    loadSourceSceneFire10Runtime(THREE,{json,texture,scene,camera,origin,archiveObjects}).then(value=>{sourceSceneFire10=value;canvas.dataset.sourceSceneFire10='ready';}).catch(error=>{canvas.dataset.sourceSceneFire10='failed';console.error(error);});\n    requestAnimationFrame(draw);sceneStages.start();");
 replace('  sourceWater?.update(now);',
  "  if(sourceSceneFire10){sourceSceneFire10.update(now,canvas.dataset.sourceArchiveWindow);if(now-sourceSceneFire10DiagnosticAt>=1000){sourceSceneFire10DiagnosticAt=now;canvas.dataset.sourceSceneFire10=JSON.stringify(sourceSceneFire10.inspect());}}\n  sourceWater?.update(now);");
 return IMPORT+source;
}

export function stageFire10Plan(plan,texts){
 if(!Array.isArray(plan?.critical)||!Array.isArray(plan?.background)||!texts.has(FIRE10_MANIFEST))throw Error('Scene effects delivery plan missing');
 const manifest=JSON.parse(texts.get(FIRE10_MANIFEST)),prefix='/assets/source-scene-fire10/';
 const assets=[FIRE10_MANIFEST,prefix+manifest.effect,prefix+manifest.placements,prefix+'playback.json',...Object.values(manifest.textures).map(r=>prefix+r.file)];
 if(assets.length!==6||assets.some(p=>!texts.has(p)&&p.endsWith('.json')))throw Error('Scene effects asset plan incomplete');
 const assetSet=new Set(assets),critical=plan.critical.filter(p=>!assetSet.has(p));
 return {...plan,critical,background:[...new Set([...plan.background,...assets])].filter(p=>!critical.includes(p)),
  scope:{...plan.scope,sourceFire10Placements:10,sceneEffectsBackground:true,wholeMapAccepted:false}};
}
