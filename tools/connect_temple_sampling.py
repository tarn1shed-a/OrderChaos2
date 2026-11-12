"""Connect only the five verified temple models to original mip/sampler data."""
import json
from pathlib import Path
from tutorial_map_geometry import ROOT,local_output
from connect_map_geometry import replace_once
from temple_sampling import FORMAT

def connect(runtime,export):
    runtime,export=map(local_output,(runtime,export));public=runtime/'prototype/public'
    if(runtime/'game-data/converted').is_symlink():raise ValueError('Detach local original assets first')
    policy=json.loads((export/'policy.json').read_text())
    if policy.get('format')!=FORMAT or len(policy['models'])!=5 or len(policy['instances'])!=8 or policy['lightingChanged']is not False:raise ValueError('Unverified temple sampling export')
    js=(public/'explore-map.js').read_text();js=replace_once(js,"json('/assets/source-map-part-lightmaps/manifest.json')","json('/assets/source-temple-sampling/manifest.json')")
    marker="import {createContextControl} from './context-control.js';";js=replace_once(js,marker,"import{createTempleSampling}from './source-temple-sampling.js?templeSampling=1';\nlet templeSampling;\n"+marker)
    marker='    partLightmaps=createPartLightmapContext(await json(assets.sourcePartLightmaps.url),canvas);'
    js=replace_once(js,marker,marker+"\n    templeSampling=await createTempleSampling(THREE,renderer,canvas,await json(assets.sourceTempleSampling.url),async url=>{const r=await fetch(url);if(!r.ok)throw Error('原神殿 mip 文件缺失');return r.arrayBuffer();});")
    marker='  const data = await json(entry.url), group = new THREE.Group();';js=replace_once(js,marker,marker+'\n  templeSampling.validateModel(entry,data);')
    marker='    const tex = data.sceneSampling ? sceneDiffuseTexture(THREE,cached,mat,index,data.sceneSampling) : cached;';js=replace_once(js,marker,'    let tex = data.sceneSampling ? sceneDiffuseTexture(THREE,cached,mat,index,data.sceneSampling) : cached;\n    tex=templeSampling.diffuse(entry.model,mat.diffuse,tex);')
    marker='        bindDynamicWind(THREE,model,origin,windClock,canvas);';js=replace_once(js,marker,'        templeSampling.bindAtlases(model,inst,bakedAtlases);\n'+marker)
    html=replace_once((public/'explore-map.html').read_text(),'/explore-map.js?partLightmaps=1','/explore-map.js?templeSampling=1')
    outputs={'prototype/public/explore-map.js':js.encode(),'prototype/public/explore-map.html':html.encode(),'prototype/public/source-temple-sampling.js':(ROOT/'tools/preview/source-temple-sampling.js').read_bytes()}
    for p in export.iterdir():
        if not p.is_file()or p.suffix not in('.json','.rgba'):raise ValueError('Unexpected temple output')
        name='game-data/converted/source-temple-sampling/'+p.name
        if(runtime/name).exists()and(runtime/name).read_bytes()!=p.read_bytes():raise ValueError('Preserve existing temple data')
        outputs[name]=p.read_bytes()
    for n,b in outputs.items():p=runtime/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
    return{'files':len(outputs),'templeInstances':8,'lightingChanged':False}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--export',type=Path,required=True);a=p.parse_args();print(json.dumps(connect(a.runtime,a.export)))
