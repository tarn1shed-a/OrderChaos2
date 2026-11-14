// Guarded entry bridge only; it does not replace map/lighting/environment data.
export const SKY_MANIFEST='/assets/source-tutorial-sky/manifest.json';
export function stageTutorialSkyEntry(source){
 const replace=(from,to)=>{if(source.split(from).length!==2)throw Error('Original sky entry anchor differs');source=source.replace(from,to);};
 if(source.includes('createTutorialSky'))throw Error('Original sky already attached');
 source="import {createTutorialSky} from '/source-tutorial-sky.js';\n"+source;
 replace("const viewport = $('viewport'), canvas = $('scene');", "const viewport = $('viewport'), canvas = $('scene');let tutorialSky=null;");
 const established='environment=createOriginalDefaultEnvironment(THREE,await json(assets.defaultEnvironment),bakedLighting,environment);';
 replace(established,established+"tutorialSky=await createTutorialSky(THREE,await json('/assets/source-tutorial-sky/manifest.json'),{json,text:async url=>{if(!url.startsWith('/assets/source-tutorial-sky/'))throw Error('Original sky shader scope differs');const r=await fetch(url);if(!r.ok)throw Error('Original sky shader unavailable');return r.text();},texture,scene,environment});");
 replace('hdrRenderer.render(scene,camera,zone);', 'tutorialSky?.update(camera,environment.state().pair);canvas.dataset.sourceTutorialSky=JSON.stringify(tutorialSky?.state());hdrRenderer.render(scene,camera,zone);');
 return source;
}

export function stageTutorialSkyPlan(plan,texts){
 if(!texts.has(SKY_MANIFEST))throw Error('Original sky manifest absent');
 const profile=JSON.parse(texts.get(SKY_MANIFEST));
 if(profile.format!=='oc2-source-tutorial-sky-candidate-v1'||profile.sourceMapId!==5)throw Error('Original sky plan input differs');
 const urls=[SKY_MANIFEST,...Object.values(profile.models).flatMap(m=>[m.model.url,m.texture.url]),...Object.values(profile.shaders).map(s=>s.url),'/source-tutorial-sky.js'];
 if(urls.some(url=>!plan.critical.includes(url)))throw Error('Original sky dependency missing from actual critical closure');
 return {...plan,scope:{...plan.scope,sourceTutorialSky:true,skyGPUQueue:'browser-adaptation',wholeMapAccepted:false}};
}
