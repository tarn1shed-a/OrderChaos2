// Creation-preview resources are requested by the recovered creation pages. They
// must not become a new first-entry gate or compete with map streaming warmup.
export const isCreationPreviewResource=url=>url==='/__delivery/creation_preview.mjs'||url==='/__delivery/creation_stages.mjs'||url==='/__delivery/creation_stages_profile.mjs'||url==='/__delivery/creation_geometry.mjs'||url==='/__delivery/creation_motion.mjs'||url==='/__delivery/creation_motion_history.mjs'||url.startsWith('/__delivery/creation_control/')||url.startsWith('/__delivery/creation_batch/')||url.startsWith('/__delivery/creation_class_stage/')||
  ['/assets/source-creation-','/assets/source-selection-'].some(prefix=>url.startsWith(prefix))||
  ['/source-selection-scene.js','/selection_scene_inside_material.js','/selection_scene_stones_material.js',
   '/selection_scene_flowers_material.js','/selection_scene_grass_material.js','/selection_scene_waterfalls_material.js',
   '/selection_scene_water_material.js','/selection_scene_water_surface.js','/selection_scene_water_floor.js',
   '/source-creation-stage.mjs','/character_creation_preview_proposal.mjs','/character_creation_race_preview_v1.mjs',
   '/character_creation_race_preview_v2.mjs','/creation_elf_source_ready.mjs'].includes(url);
export function creationPreviewPlan(plan,files){
 const set=new Set(files.filter(isCreationPreviewResource));
 return {...plan,critical:plan.critical.filter(url=>!set.has(url)),background:plan.background.filter(url=>!set.has(url)),
  scope:{...plan.scope,sourceCreationPreview:'on-demand-original-race-panel',creationPreviewChangesPlayableRaces:false}};
}
