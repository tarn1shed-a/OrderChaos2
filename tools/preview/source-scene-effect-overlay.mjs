// Deployment-only append layer. Reviewed entry and base bundle stay unchanged.
export const SCENE_EFFECT_MANIFEST='/assets/source-scene-effects/manifest.json';
const IMPORT="import {loadSourceSceneEffectRuntime} from '/source-scene-effect-runtime.js';\nlet sourceSceneEffects=null,sourceSceneEffectDiagnosticAt=-Infinity;\n";
export function stageSceneEffectsEntry(source){
 if(source.includes(IMPORT))throw Error('Scene effects overlay already applied');
 if(!source.includes('if(!sceneStages.present(windowChange))'))throw Error('Scene effects require the existing staged map');
 const replace=(from,to)=>{if(source.split(from).length!==2)throw Error('Scene effects anchor differs: '+from.slice(0,72));source=source.replace(from,to);};
 replace('    requestAnimationFrame(draw);sceneStages.start();',
  "    loadSourceSceneEffectRuntime(THREE,{json,texture,scene,camera,origin,archiveObjects}).then(value=>{sourceSceneEffects=value;canvas.dataset.sourceSceneEffects='ready';}).catch(error=>{canvas.dataset.sourceSceneEffects='failed';console.error(error);});\n    requestAnimationFrame(draw);sceneStages.start();");
 replace('  sourceWater?.update(now);',
  "  if(sourceSceneEffects){sourceSceneEffects.update(now,canvas.dataset.sourceArchiveWindow);if(now-sourceSceneEffectDiagnosticAt>=1000){sourceSceneEffectDiagnosticAt=now;canvas.dataset.sourceSceneEffects=JSON.stringify(sourceSceneEffects.inspect());}}\n  sourceWater?.update(now);");
 return IMPORT+source;
}

export function stageSceneEffectsPlan(plan,texts){
 if(!Array.isArray(plan?.critical)||!Array.isArray(plan?.background)||!texts.has(SCENE_EFFECT_MANIFEST))throw Error('Scene effects delivery plan missing');
 const manifest=JSON.parse(texts.get(SCENE_EFFECT_MANIFEST)),prefix='/assets/source-scene-effects/';
 const assets=[SCENE_EFFECT_MANIFEST,prefix+manifest.effect,prefix+manifest.placements,prefix+'playback.json',...Object.values(manifest.textures).map(r=>prefix+r.file)];
 if(assets.length!==7||assets.some(p=>!texts.has(p)&&p.endsWith('.json')))throw Error('Scene effects asset plan incomplete');
 const assetSet=new Set(assets),critical=plan.critical.filter(p=>!assetSet.has(p));
 return {...plan,critical,background:[...new Set([...plan.background,...assets])].filter(p=>!critical.includes(p)),
  scope:{...plan.scope,sourceSceneEffectPlacements:43,sceneEffectsBackground:true,wholeMapAccepted:false}};
}
