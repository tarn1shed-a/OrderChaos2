// Only decoded art and embedded glyphs are loaded. Original SWF scripts never run.
export async function loadOriginalUI(profile) {
  if (profile.format !== 'oc2-original-ui-v16' || profile.gameplay?.format!=='oc2-native-gameplay-v7'||profile.controls?.format!=='oc2-original-controls-v1' || profile.fonts?.requiredTextStatus !== 'complete' ||
      !['chineseText','chineseDisplay'].every(key=>profile.fonts.faces?.[key]?.conversion==='lossless-full-sfnt-to-woff') ||
      profile.skillIcons?.format !== 'oc2-skill-icons-v1'||profile.hud?.format!=='oc2-original-hud-v1'||profile.hud?.nativeControls?.format!=='oc2-original-mobile-controls-v2'||
      profile.portraits?.format!=='oc2-character-portraits-v1'||profile.inventory?.format!=='oc2-original-inventory-v1'||
      profile.itemIcons?.format!=='oc2-item-icons-v1'||profile.skillUI?.format!=='oc2-original-skill-ui-v1') throw new Error('原版界面资源需要更新，请重新构建本地资源');
  if(profile.gameplay.interaction?.format!=='oc2-source-interaction-v1'||!profile.controls.icons.loot)throw new Error('原版交互资源需要更新');
  const imageKeys = ['buttonGreen','buttonGray','skillOrb','skillFrame','healthRing','experienceRing','healthFill','manaFill','panelBlue'];
  const localURL = url => {
    if (typeof url !== 'string' || !/^\/assets\/ui\/[A-Za-z0-9_-]+\.(png|woff)$/.test(url)) throw new Error('原版界面资源路径无效');
    return url;
  };
  // Load all images before switching the skin, so missing local assets fail visibly.
  await Promise.all(imageKeys.map(async key => {
    const url = localURL(profile.assets[key]?.url), image = new Image();
    image.src = url; await image.decode();
    document.documentElement.style.setProperty(`--oc2-${key}`, `url("${url}")`);
  }));
  await Promise.all(Object.entries(profile.hud.assets).map(async ([key,entry])=>{
    const url=localURL(entry.url),image=new Image();image.src=url;await image.decode();
    if(image.naturalWidth!==entry.width||image.naturalHeight!==entry.height)throw new Error('原状态栏图集尺寸不匹配');
    document.documentElement.style.setProperty(`--hud-${key}`,`url("${url}")`);
  }));
  await Promise.all([...Object.values(profile.controls.icons),...Object.values(profile.gameplay.icons)].map(async entry=>{
    const image=new Image();image.src=localURL(entry.url);await image.decode();
    if(image.naturalWidth!==entry.width||image.naturalHeight!==entry.height)throw new Error('原版操作图标尺寸不匹配');
  }));
  if(profile.gameplay.combat?.format!=='oc2-native-combat-v1')throw new Error('原版战斗资料版本不匹配');
  await Promise.all(Object.values(profile.gameplay.combat.auras).map(async aura=>{
    const image=new Image();image.src=localURL(aura.icon.url);await image.decode();
    if(image.naturalWidth!==96||image.naturalHeight!==96)throw new Error('原版状态图标尺寸不匹配');
  }));
  for(const [name,id] of [['attack','field-attack'],['interaction','field-interaction']]){
    const image=document.querySelector(`#${id} .control-icon`),bounds=profile.controls.iconPlacements[name].boundsFraction;
    Object.assign(image.style,{left:`${bounds[0]*100}%`,top:`${bounds[1]*100}%`,width:`${bounds[2]*100}%`,height:`${bounds[3]*100}%`});
    const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg'),defs=document.createElementNS(ns,'defs');
    svg.setAttribute('width','0');svg.setAttribute('height','0');svg.setAttribute('aria-hidden','true');svg.style.position='absolute';
    const clip=document.createElementNS(ns,'clipPath'),path=document.createElementNS(ns,'path'),hit=profile.controls.hitZones[name];
    clip.id=`native-hit-${name}`;clip.setAttribute('clipPathUnits','objectBoundingBox');
    path.setAttribute('d',hit.pathPixels);path.setAttribute('transform',`matrix(${hit.matrixFraction.join(' ')})`);
    clip.append(path);defs.append(clip);svg.append(defs);document.body.append(svg);
    document.querySelector(`#${id} .control-hit-area`).style.clipPath=`url(#${clip.id})`;
  }
  document.querySelector('#field-interaction .control-icon').src=profile.controls.icons.jump.url;
  await Promise.all(Object.entries(profile.inventory.assets).map(async ([key,entry])=>{
    const image=new Image();image.src=localURL(entry.url);await image.decode();
    if(image.naturalWidth!==entry.width||image.naturalHeight!==entry.height)throw new Error('原背包图集尺寸不匹配');
    document.documentElement.style.setProperty(`--inventory-${key}`,`url("${image.src}")`);
  }));
  await Promise.all([...Object.values(profile.skillUI.assets), ...profile.skillUI.skills.flatMap(skill=>[skill.base,...skill.runes].map(entry=>entry.icon))].map(async entry=>{
    const image=new Image();image.src=localURL(entry.url);await image.decode();
    if(image.naturalWidth!==entry.width||image.naturalHeight!==entry.height)throw new Error('原技能面板图标尺寸不匹配');
  }));
  await Promise.all(['trainingSword','trainingStaff','trainingGreatsword','linenArmor','travelerBoots','wolfPelt'].map(async key=>{
    const entry=profile.itemIcons.icons[key],image=new Image();image.src=localURL(entry?.url);await image.decode();
    if(image.naturalWidth!==96||image.naturalHeight!==96)throw new Error('原物品图标尺寸不匹配');
  }));
  await Promise.all(Object.entries(profile.fonts.faces).map(async ([key,entry]) => {
    const face = new FontFace(entry.family, `url("${localURL(entry.url)}") format("woff")`, {
      weight: String(entry.weight), unicodeRange: entry.unicodeRange,
    });
    await face.load(); document.fonts.add(face);
    if(key==='chineseText')document.documentElement.style.setProperty('--oc2-cjk-text',JSON.stringify(entry.family));
    if(key==='chineseDisplay')document.documentElement.style.setProperty('--oc2-cjk-display',JSON.stringify(entry.family));
  }));
  await Promise.all(['fireball','frost_blast','arcane_missile'].map(async key => {
    const entry=profile.skillIcons.icons[key],url=localURL(entry?.url);
    for(const id of [`field-${key}`,`skill-${key}`]){
      const element=document.querySelector(`#${id} .skill-icon`);
      if(!element)throw new Error('技能按钮缺少原图标容器');
      element.src=url;await element.decode();
      if(element.naturalWidth!==entry.width||element.naturalHeight!==entry.height)throw new Error('原技能图标尺寸不匹配');
      element.hidden=false;
    }
  }));
  document.body.classList.add('original-skin');
  document.body.dataset.ui = profile.format;
  document.body.dataset.chineseFont = 'original-full-source-fonts';
  document.body.dataset.fontFaces = String(Object.keys(profile.fonts.faces).length);
  document.body.dataset.skillIcons = 'fireball,frost_blast,arcane_missile';
  document.body.dataset.hud = profile.hud.format;
  return profile;
}
