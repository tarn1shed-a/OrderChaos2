// Deployment-only routes for the frozen, read-only original character panels.
// Applied after stageEntry({entryUI:true}) and stageInsideEntry. No store/cast rules.
export const CHARACTER_PANEL_MANIFEST='/assets/character-source/panels.json';
const IMPORT="import {createCharacterSourcePanels} from '/character-source-panels.mjs';\n";

// Emitted verbatim into the staged entry. Also runnable with explicit fixtures.
export function createCharacterPanelHandles(panels,readTrialProgress){
 const close=()=>panels.close();
 return {
  attributes:{open:()=>panels.openAttributes(),close,
   get isOpen(){return panels.isOpen&&panels.inspect().kind==='attributes';},
   update(data){panels.update(data,{source:null,trialProgress:data?readTrialProgress():null});}},
  skills:{open:()=>panels.openSkills(),close,
   get isOpen(){return panels.isOpen&&panels.inspect().kind==='skills';}}
 };
}

export function stageCharacterPanelsEntry(source){
 if(source.includes(IMPORT))throw Error('Character panel overlay already applied');
 if(!source.includes("import {prepareInsideSource,createInsideSceneMaterial,prepareInsideGeometry,prepareInsideRoot,bindInsideInstance} from '/source-inside-models.js';"))throw Error('Character panels require the four-inside staged entry');
 const replace=(from,to)=>{if(source.split(from).length!==2)throw Error('Character panel anchor differs: '+from.slice(0,96));source=source.replace(from,to);};
 replace("import {createAttributeUI} from '/__delivery/attribute_ui.mjs';\n",IMPORT);
 replace("import { createSkillBook } from './skill-book.js';\n",'');
 replace('let attributeUI,sourcePreviewResources;','let attributeUI,sourcePreviewResources,characterPanels;');
 // Keep the existing source model/camera/light callback and pixel-ratio values.
 replace('attributeUI=createAttributeUI({stop,focusGame:', 'characterPanels=createCharacterSourcePanels({stop,focusGame:');
 replace('beforeOpen:()=>{questBook?.close();skillBook?.close();inventoryUI?.close();hotbar?.close();setCampPanel(false);pointer=null;}});',
  'beforeOpen:()=>{questBook?.close();inventoryUI?.close();hotbar?.close();setCampPanel(false);pointer=null;}});\n    const characterPanelHandles=createCharacterPanelHandles(characterPanels,()=>{const xp=$(\'field-xp\');return xp?{value:xp.value,max:xp.max}:null;});\n    attributeUI=characterPanelHandles.attributes;skillBook=characterPanelHandles.skills;');
 replace("attributeStyle.href='/__delivery/attribute_ui.css'","attributeStyle.href='/character-source-panels.css'");
 replace("    skillBook=createSkillBook(uiProfile,{stop,focusGame:()=>canvas.focus({preventScroll:true}),beforeOpen:()=>{questBook?.close();hotbar?.close();inventoryUI?.close();setCampPanel(false);pointer=null;}});",'');
 // Existing attributeUI.update, close/reset paths, HUD/menu routes and both
 // isOpen input gates now consume the shared read-only panel handles.
 replace('function openSession(){if(sourceEntry)sourceEntry.open();else legacySession();}',
  'function openSession(){characterPanels?.close();if(sourceEntry)sourceEntry.open();else legacySession();}');
 replace("window.addEventListener('keydown', e => {\n  if(questBook?.isOpen||skillBook?.isOpen||hotbar?.isEditing||$('session-dialog').open||e.isComposing||e.ctrlKey||e.metaKey||e.altKey||['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName))return;",
  "window.addEventListener('keydown', e => {\n  if(characterPanels&&connected&&(e.code==='KeyC'||e.code==='KeyK')&&!questBook?.isOpen&&!hotbar?.isEditing&&!$('session-dialog').open&&!e.isComposing&&!e.ctrlKey&&!e.metaKey&&!e.altKey&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName)){\n    e.preventDefault();if(!e.repeat){const pane=e.code==='KeyC'?'attributes':'skills';if(characterPanels.isOpen&&characterPanels.inspect().kind===pane)characterPanels.close();else if(pane==='attributes')characterPanels.openAttributes();else characterPanels.openSkills();}return;\n  }\n  if(questBook?.isOpen||skillBook?.isOpen||hotbar?.isEditing||$('session-dialog').open||e.isComposing||e.ctrlKey||e.metaKey||e.altKey||['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName))return;");
 replace("if(e.code==='KeyC'){e.preventDefault();if(!e.repeat){if(attributeUI?.isOpen)attributeUI.close();else attributeUI?.open();}return;}\n  ",'');
 return createCharacterPanelHandles.toString()+'\n'+source;
}

// Original panel art remains available for background prefetch/on-demand open.
// Keep all module imports and the existing map/texture critical schedule intact.
export function stageCharacterPanelsPlan(plan){
 if(!Array.isArray(plan?.critical)||!Array.isArray(plan?.background))throw Error('Character panel staged plan differs');
 const panel=url=>typeof url==='string'&&url.startsWith('/assets/character-source/');
 const moved=plan.critical.filter(panel);if(!moved.length)return plan;
 return {...plan,critical:plan.critical.filter(url=>!panel(url)),background:[...new Set([...plan.background,...moved])]};
}
