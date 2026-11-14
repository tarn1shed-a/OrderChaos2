// Apply after the source character-panel overlay. Reviewed 127 files stay intact.
const IMPORT="import {createCharacterHotbar} from '/__delivery/character_hotbar.mjs';\n";
export function stageCharacterHotbarEntry(source){
 if(source.includes(IMPORT))throw Error('Character hotbar overlay already applied');
 if(!source.includes("import {createCharacterSourcePanels} from '/character-source-panels.mjs';"))throw Error('Character hotbar requires source character panels');
 const replace=(from,to)=>{if(source.split(from).length!==2)throw Error('Character hotbar anchor differs: '+from.slice(0,96));source=source.replace(from,to);};
 replace('let hotbar, mobileHUD, joystick, jumpControl, attackControl,controlProfile, gameplayProfile;',
  "let hotbar, mobileHUD, joystick, jumpControl, attackControl,controlProfile, gameplayProfile;\nconst characterHotbar=createCharacterHotbar({createHotbarUI,createMobileHUD,readCharacter:()=>connected?character:null});");
 replace("    hotbar=createHotbarUI({root:$('field-actions')", "    hotbar=characterHotbar.createHotbar({root:$('field-actions')");
 replace('    mobileHUD=createMobileHUD(uiProfile.hud);','    mobileHUD=characterHotbar.createMobile(uiProfile.hud);');
 replace('function useSkill(id) {\n','function useSkill(id) {\n  if(!characterHotbar.canUse(id))return;\n');
 replace("      button.dataset.readyAt=String(me?.skillReadyAt?.[skill.id]||0);\n    }\n  }\n}",
  "      button.dataset.readyAt=String(me?.skillReadyAt?.[skill.id]||0);\n    }\n  }\n  characterHotbar.apply();\n}");
 return IMPORT+source;
}
