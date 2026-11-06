// Only decoded art and embedded glyphs are loaded. Original SWF scripts never run.
export async function loadOriginalUI(profile) {
  if (profile.format !== 'oc2-original-ui-v2' || profile.fonts?.requiredTextStatus !== 'complete' ||
      !['chineseText','chineseDisplay'].every(key=>profile.fonts.faces?.[key]?.conversion==='lossless-full-sfnt-to-woff') ||
      profile.skillIcons?.format !== 'oc2-skill-icons-v1') throw new Error('原版中文字体与技能图标资源需要更新，请重新构建本地资源');
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
  await Promise.all(Object.entries(profile.fonts.faces).map(async ([key,entry]) => {
    const face = new FontFace(entry.family, `url("${localURL(entry.url)}") format("woff")`, {
      weight: String(entry.weight), unicodeRange: entry.unicodeRange,
    });
    await face.load(); document.fonts.add(face);
    if(key==='chineseText')document.documentElement.style.setProperty('--oc2-cjk-text',JSON.stringify(entry.family));
    if(key==='chineseDisplay')document.documentElement.style.setProperty('--oc2-cjk-display',JSON.stringify(entry.family));
  }));
  await Promise.all(['fireball','frost_blast'].map(async key => {
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
  document.body.dataset.skillIcons = 'fireball,frost_blast';
}
