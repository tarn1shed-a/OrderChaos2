"""Connect source dynamic vegetation to the isolated preview, without light edits."""
import json
from pathlib import Path
from tutorial_map_geometry import ROOT,local_output
from connect_map_geometry import replace_once
from scene_dynamic_wind import FORMAT


def connect(runtime,export):
    runtime,export=map(local_output,(runtime,export));assets=runtime/'game-data/converted';public=runtime/'prototype/public'
    if assets.is_symlink():raise ValueError('Detach isolated art first')
    audit=json.loads((export/'audit.json').read_text())
    if audit.get('format')!=FORMAT or audit.get('lightsChanged')is not False or len(audit.get('added',[]))!=1:raise ValueError('Unknown source dynamic branch')
    alpha=replace_once((public/'scene-alpha.js').read_text(),"  'ut_lightmap_shake_gray_trans.bdae':'discard-less-equal',","  'ut_lightmap_shake_gray_trans.bdae':'discard-less-equal',\n  'ut_lightmap_shake_trans.bdae':'discard-less-equal',")
    cull=replace_once((public/'scene-culling.js').read_text()," 'ut_lightmap_shake_gray_trans.bdae':false,"," 'ut_lightmap_shake_gray_trans.bdae':false,\n 'ut_lightmap_shake_trans.bdae':false,")
    js=replace_once((public/'explore-map.js').read_text(),"json('/assets/source-map-zero-wind/manifest.json')","json('/assets/source-map-dynamic-wind/manifest.json')")
    js=replace_once(js,"import {createBakedSceneMaterial,bindInstanceLightmap} from './source-wind-identity.js?sourceWind=1';","import {createBakedSceneMaterial,bindInstanceLightmap,prepareDynamicWind,bindDynamicWind,createWindClock} from './source-dynamic-wind.js?dynamicWind=1';\nconst windClock=createWindClock(Math.floor(performance.now()*1000));")
    js=replace_once(js,"  if (data.colors?.length) g.setAttribute('color', new THREE.Float32BufferAttribute(data.colors, 3));","  if (data.sourceUV2?.length) g.setAttribute('TexCoord2',new THREE.Float32BufferAttribute(data.sourceUV2,2));\n  if (data.colors?.length) g.setAttribute('color', new THREE.Float32BufferAttribute(data.colors, 3));")
    js=replace_once(js,"  let materials;","  await prepareDynamicWind(data,async url=>{const r=await fetch(url);if(!r.ok)throw Error('原摇动程序缺失');return r.text();});\n  let materials;")
    marker="        // Scene meshes use original local-space transforms, not the avatar centering wrapper."
    js=replace_once(js,marker,"        bindDynamicWind(THREE,model,origin,windClock,canvas);\n"+marker)
    js=replace_once(js,'function draw(now) {','function draw(now) {\n  windClock.update(Math.floor(now*1000));')
    html=replace_once((public/'explore-map.html').read_text(),'/explore-map.js?sourceWind=1','/explore-map.js?dynamicWind=1')
    outputs={'prototype/public/explore-map.js':js.encode(),'prototype/public/explore-map.html':html.encode(),'prototype/public/scene-alpha.js':alpha.encode(),'prototype/public/scene-culling.js':cull.encode(),'prototype/public/source-dynamic-wind.js':(ROOT/'tools/preview/source-dynamic-wind.js').read_bytes()}
    for p in export.iterdir():
        if not p.is_file()or p.suffix not in('.json','.png','.glsl'):raise ValueError('Unexpected dynamic asset entry')
        n='game-data/converted/source-map-dynamic-wind/'+p.name
        if(runtime/n).exists()and(runtime/n).read_bytes()!=p.read_bytes():raise ValueError('Preserve existing dynamic asset edits')
        outputs[n]=p.read_bytes()
    for n,b in outputs.items():p=runtime/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
    return {'files':len(outputs),'addedInstances':1,'lightsChanged':False}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--export',type=Path,required=True);a=p.parse_args();print(json.dumps(connect(a.runtime,a.export)))
