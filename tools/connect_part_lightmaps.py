"""Connect verified source part order without replacing any source assets."""
import json
from pathlib import Path
from tutorial_map_geometry import ROOT,local_output
from connect_map_geometry import replace_once
from scene_part_lightmaps import FORMAT

def connect(runtime,export):
    runtime,export=map(local_output,(runtime,export));public=runtime/'prototype/public'
    if(runtime/'game-data/converted').is_symlink():raise ValueError('Detach local assets first')
    audit=json.loads((export/'audit.json').read_text())
    if audit.get('format')!=FORMAT or audit.get('changedInstances')!=17 or audit.get('lightingValuesChanged')is not False:raise ValueError('Unverified source part lighting export')
    js=(public/'explore-map.js').read_text()
    js=replace_once(js,"json('/assets/source-map-record-gaps/manifest.json')","json('/assets/source-map-part-lightmaps/manifest.json')")
    js=replace_once(js,'createBakedSceneMaterial,bindInstanceLightmap,prepareDynamicWind','createBakedSceneMaterial,prepareDynamicWind')
    marker="import {createContextControl} from './context-control.js';"
    js=replace_once(js,marker,"import{createPartLightmapContext}from './source-part-lightmaps.js?partLightmaps=1';\nlet partLightmaps;\nfunction bindInstanceLightmap(...args){return partLightmaps.bind(...args);}\n"+marker)
    js=replace_once(js,"    assets = await json('/assets/source-map-part-lightmaps/manifest.json');","    assets = await json('/assets/source-map-part-lightmaps/manifest.json');\n    partLightmaps=createPartLightmapContext(await json(assets.sourcePartLightmaps.url),canvas);")
    js=replace_once(js,'  prepareFlagModel(root,data);','  partLightmaps.prepare(root,entry,data);\n  prepareFlagModel(root,data);')
    html=replace_once((public/'explore-map.html').read_text(),'/explore-map.js?records=1','/explore-map.js?partLightmaps=1')
    outputs={'prototype/public/explore-map.js':js.encode(),'prototype/public/explore-map.html':html.encode(),
             'prototype/public/source-part-lightmaps.js':(ROOT/'tools/preview/source-part-lightmaps.js').read_bytes()}
    for name in ('manifest.json','policy.json','audit.json'):outputs['game-data/converted/source-map-part-lightmaps/'+name]=(export/name).read_bytes()
    for n,b in outputs.items():
        p=runtime/n
        if 'game-data/'in n and p.exists()and p.read_bytes()!=b:raise ValueError('Preserve existing source part output')
    for n,b in outputs.items():p=runtime/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
    return {'files':len(outputs),'changedInstances':17,'lightingValuesChanged':False}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--export',type=Path,required=True);a=p.parse_args();print(json.dumps(connect(a.runtime,a.export)))
