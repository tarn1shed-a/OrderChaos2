// Retire unverified prototype UI; this does not invent a replacement original UI.
// Original IGMEntrance.onShow hides the menu entrance on tutorial map 5.
export function retirePrototypeHTML(html){
  if(html.includes('id="retired-runtime-bindings"'))return html;
  const bindings=new Map();
  function remove(block){
    // Retain only empty compatibility nodes required by the reviewed runtime.
    // No old panel layout, explanatory copy, links or prototype artwork survives.
    for(const match of block.matchAll(/<([a-z][a-z0-9-]*)\b[^>]*\bid="([^"]+)"[^>]*>/gi)){
      const [opening,sourceTag,id]=match,tag=sourceTag==='aside'?'div':sourceTag;let content='';
      if(tag==='button'||id==='skill-hint')content='<span></span>';
      if(/^skill-(fireball|frost_blast|arcane_missile)$/.test(id))content='<span class="skill-art"><img class="skill-icon" alt=""></span><span class="skill-label"></span><span class="skill-status"></span>';
      const value=tag==='input'?(opening.match(/\bvalue="[^"]*"/)?.[0]||''):'';
      bindings.set(id,`<${tag} id="${id}"${value?' '+value:''}${['camp-panel','character-panel'].includes(id)?' hidden':''}>${content}${['input','img'].includes(tag)?'':`</${tag}>`}`);
    }
    return '';
  }
  html=html
    .replace(/<aside\b[^>]*\bid="camp-panel"[^>]*>[\s\S]*?<\/aside>/g,remove)
    .replace(/<button\b[^>]*\bid="(?:camp-toggle|field-lab-door)"[^>]*>[\s\S]*?<\/button>/g,remove)
    .replace(/<dialog\b[^>]*\bid="session-dialog"[^>]*>[\s\S]*?<\/dialog>/g,remove)
    .replace(/<div class="connection">[\s\S]*?<\/div>/g,remove)
    .replace(/<div class="scene-title">[\s\S]*?<\/div>/g,remove)
    .replace(/<span id="position">[\s\S]*?<\/span>/g,remove)
    .replace(/<footer class="site-footer">[\s\S]*?<\/footer>/g,remove)
    .replace(/<footer id="skill-book-note"[^>]*>[\s\S]*?<\/footer>/g,remove)
    .replace(/<div\b[^>]*>历史原型演示 · 原资源[\s\S]*?<\/div>/g,'')
    .replace(/<span class="desktop-shortcuts">[\s\S]*?<\/span>/g,'')
    .replace(/<p class="(?:equipment-preview-note|source-reference)">[\s\S]*?<\/p>/g,'')
    .replace('<span>原版技能资料</span>','').replace('<small>资料预览</small>','')
    .replace(/<small>查看面板时世界仍在运行[\s\S]*?<\/small>/g,'')
    .replace('物品和装备由本地服务器保存。','')
    .replace('正在读取本地转换后的地形与模型…','正在加载…')
    .replace(/<title>[\s\S]*?<\/title>/,'<title>混沌与秩序2</title>')
    .replace('<div id="labels"','<div hidden data-unrestored="original-world-name-renderer" id="labels"');
  if(bindings.size)html=html.replace('</body>',`<div id="retired-runtime-bindings" hidden inert aria-hidden="true">${[...bindings.values()].join('')}</div></body>`);
  return html.replace('</head>','<link rel="stylesheet" href="/__delivery/retired_ui.css"></head>');
}
export function retiredRoute(url){
  if(url.pathname!=='/explore.html'&&!(url.pathname==='/explore-map.html'&&url.searchParams.has('lab')))return null;
  const query=new URLSearchParams(url.search);query.delete('lab');query.delete('entry');
  if(!query.get('room')||query.get('room')==='DYNAMIC-01')query.set('room','RAILWAY-01');
  if(!query.has('sourceProfile'))query.set('sourceProfile','APK_Default');
  return '/explore-map.html?'+query;
}
