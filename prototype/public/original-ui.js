// Only decoded art and embedded glyphs are loaded. Original SWF scripts never run.
export async function loadOriginalUI(profile) {
  if (profile.format !== 'oc2-original-ui-v1') throw new Error('原版界面资源版本不匹配');
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
  await Promise.all(Object.values(profile.fonts.faces).map(async entry => {
    const face = new FontFace(entry.family, `url("${localURL(entry.url)}") format("woff")`, {
      weight: String(entry.weight), unicodeRange: entry.unicodeRange,
    });
    await face.load(); document.fonts.add(face);
  }));
  document.body.classList.add('original-skin');
  document.body.dataset.ui = profile.format;
  document.body.dataset.chineseFont = 'system-fallback';
}
