// Race-preview resources are requested by the recovered race page only. They
// must not become a new first-entry gate or compete with map streaming warmup.
export function creationPreviewPlan(plan,files){
 const owned=url=>url==='/__delivery/creation_preview.mjs'||
  ['/assets/source-creation-','/assets/source-selection-'].some(prefix=>url.startsWith(prefix))||
  ['/source-selection-scene.js','/selection_scene_inside_material.js','/selection_scene_stones_material.js',
   '/selection_scene_flowers_material.js','/selection_scene_grass_material.js','/selection_scene_waterfalls_material.js',
   '/selection_scene_water_material.js','/selection_scene_water_surface.js','/selection_scene_water_floor.js',
   '/source-creation-stage.mjs','/character_creation_preview_proposal.mjs'].includes(url);
 const set=new Set(files.filter(owned));
 return {...plan,critical:plan.critical.filter(url=>!set.has(url)),background:plan.background.filter(url=>!set.has(url)),
  scope:{...plan.scope,sourceCreationPreview:'on-demand-original-race-panel',creationPreviewChangesPlayableRaces:false}};
}
