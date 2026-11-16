// Original Channelbar artwork projection. The caller supplies admitted source
// branch state and the window host; this view creates no clock or quest result.
const BASE='/assets/source-quest461-channel-v1/';
const MANIFEST_SHA='6f3f2ae104dc1eb5d659b30136a5137ef2d718a8e7833514490d3218e69e10b3';
const SVG_SHA='d37924ca9a76743fedae0226d1676c85834983b926d5a5a2a36c8e31b9ff8725';
const NS='http://www.w3.org/2000/svg';
let instances=0;
const sha=async raw=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',raw))].map(n=>n.toString(16).padStart(2,'0')).join('');
export async function createSourceChannelView(host,{load=fetch}={}){
 if(!host?.ownerDocument||typeof load!=='function'||!crypto.subtle)throw TypeError('Actual channel window host and verified loading required');
 const bytes=async url=>{const r=await load(url);if(!r.ok)throw Error('Original Channelbar artwork unavailable');return new Uint8Array(await r.arrayBuffer());};
 const manifestBytes=await bytes(BASE+'manifest.json');
 if(await sha(manifestBytes)!==MANIFEST_SHA)throw Error('Original Channelbar artwork manifest differs');
 const art=JSON.parse(new TextDecoder().decode(manifestBytes)),names=['bar','barFinish','barInterrupt'];
 if(art.format!=='oc2-original-channel-art-v1'||art.svg.sha256!==SVG_SHA||art.svg.url!==BASE+'channel.svg'||
  art.sourceRootPlacements.length!==3||names.some(n=>!art.clips[n]))throw Error('Original Channelbar drawing contract differs');
 const sourceSVG=await bytes(art.svg.url);
 if(await sha(sourceSVG)!==SVG_SHA)throw Error('Original Channelbar source frames differ');
 const parsed=new DOMParser().parseFromString(new TextDecoder().decode(sourceSVG),'image/svg+xml');
 if(parsed.querySelector('parsererror')||parsed.documentElement.namespaceURI!==NS||parsed.querySelector('script,foreignObject'))throw Error('Original Channelbar SVG unavailable');
 const svg=host.ownerDocument.importNode(parsed.documentElement,true);
 let disposed=false;
 try{
  const assets=Object.values(art.assets),images=[...svg.querySelectorAll('image')];
  if(!assets.length||images.some(i=>!assets.some(a=>a.url===i.getAttribute('href'))))throw Error('Original Channelbar image closure differs');
  const objects=new Map();
  const loaded=await Promise.allSettled(assets.map(async a=>{
   if(a.url!==BASE+a.sha256+'.png'||a.file!==a.sha256+'.png')throw Error('Original Channelbar atlas route differs');
   const raw=await bytes(a.url);if(raw.length!==a.bytes||await sha(raw)!==a.sha256)throw Error('Original Channelbar atlas bytes differ');
   // Reuse the existing img-src self/data CSP; do not broaden it for Blob URLs.
   const binary=[];for(let at=0;at<raw.length;at+=16384)binary.push(String.fromCharCode(...raw.subarray(at,at+16384)));
   const url='data:image/png;base64,'+btoa(binary.join(''));
   const image=new Image();image.src=url;await image.decode();
   if(image.naturalWidth!==a.size[0]||image.naturalHeight!==a.size[1])throw Error('Original Channelbar atlas dimensions differ');
   objects.set(a.url,url);
  }));
  const failed=loaded.find(value=>value.status==='rejected');if(failed)throw failed.reason;
  for(const image of images)image.setAttribute('href',objects.get(image.getAttribute('href')));
  // Instance-local SVG IDs permit two source windows without shared masks.
  const prefix='source-channel-'+(++instances)+'-',ids=new Map();
  for(const node of svg.querySelectorAll('[id]')){const id=node.id;if(ids.has(id))throw Error('Original Channelbar drawing ID repeats');ids.set(id,prefix+id);node.id=prefix+id;}
  for(const node of svg.querySelectorAll('*'))for(const attr of [...node.attributes]){
   const replaced=attr.value.replace(/url\(#([^)]*)\)/g,(_,id)=>{if(!ids.has(id))throw Error('Original Channelbar mask reference missing');return 'url(#'+ids.get(id)+')';});
   if(replaced!==attr.value)node.setAttribute(attr.name,replaced);
  }
  const uses=new Map();
  for(const row of art.sourceRootPlacements){
   if(!names.includes(row.name)||art.clips[row.name].sourceCharacterId!==row.characterId||
    row.colorTransform.multiply.some(n=>n!==256)||row.colorTransform.add.some(n=>n!==0))throw Error('Original root placement differs');
   const use=host.ownerDocument.createElementNS(NS,'use');use.setAttribute('transform','matrix('+row.matrixTwips.join(' ')+')');svg.append(use);uses.set(row.name,use);
  }
  // The original display list extends beyond the SWF stage header (344px bar
  // in a 340px movie). Do not crop those original children to that header.
  svg.setAttribute('overflow','visible');
  svg.setAttribute('role','img');svg.setAttribute('aria-label','施法进度');svg.setAttribute('display','none');host.append(svg);
  const render=state=>{
   if(disposed)throw Error('Source Channelbar view disposed');
   const pending=names.map(name=>{
    const value=state?.[name],clip=art.clips[name],frame=value?.currentFrame;
    if(value?.$clip!==name||value.totalFrames!==clip.frames.length||!Number.isInteger(frame)||frame<1||frame>clip.frames.length)
     throw Error('Actual source Channelbar movie state required');
    const id=clip.frames[frame-1];if(!ids.has(id))throw Error('Original source frame absent');
    return {use:uses.get(name),id:ids.get(id),visible:value.visible!==false};
   });
   for(const value of pending){value.use.setAttribute('href','#'+value.id);value.use.setAttribute('display',value.visible?'inline':'none');}
   svg.setAttribute('display',state.shown===true?'inline':'none');
   svg.setAttribute('data-source-channel-shown',state.shown===true?'1':'0');
  };
  return Object.freeze({render,
   sourceWindow:structuredClone(art.sourceWindow),
   dispose(){if(disposed)return;disposed=true;svg.remove();},
   scope:{sourceFrames:612,sourcePNGAtlases:assets.length,originalMasksRetained:true,
    viewportPlacementOwnedByCaller:true,clockOrActorOrQuestProduced:false,FlashGPUObserved:false}});
 }catch(error){svg.remove();throw error;}
}
