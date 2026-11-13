// Retire unverified prototype UI; this does not invent a replacement original UI.
// Original IGMEntrance.onShow hides the menu entrance on tutorial map 5.
export function retirePrototypeHTML(html){
  return html
    .replace(/<p><a href="\/explore\.html\?room=DYNAMIC-01(?:&amp;|&)lab=collision">[\s\S]*?<\/p>/g,'')
    .replace('<aside id="camp-panel" hidden','<aside id="camp-panel" inert data-retired-prototype="true" hidden')
    .replace('<button id="camp-toggle"','<button hidden aria-hidden="true" id="camp-toggle"')
    .replace('<div id="labels"','<div hidden data-unrestored="original-world-name-renderer" id="labels"');
}
export function retiredRoute(url){
  if(url.pathname!=='/explore.html'&&!(url.pathname==='/explore-map.html'&&url.searchParams.has('lab')))return null;
  const query=new URLSearchParams(url.search);query.delete('lab');query.delete('entry');
  if(!query.get('room')||query.get('room')==='DYNAMIC-01')query.set('room','RAILWAY-01');
  if(!query.has('sourceProfile'))query.set('sourceProfile','APK_Default');
  return '/explore-map.html?'+query;
}
