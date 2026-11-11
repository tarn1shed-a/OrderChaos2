"""Attach verified source trees to the isolated map preview; no light edits."""
import hashlib,json
from pathlib import Path
from tutorial_map_geometry import ROOT,local_output
from connect_map_geometry import replace_once
from scene_tree_recovery import FORMAT


def connect(runtime,export):
    runtime,export=map(local_output,(runtime,export));public=runtime/'prototype/public';assets=runtime/'game-data/converted'
    if assets.is_symlink():raise ValueError('Detach isolated source assets first')
    audit=json.loads((export/'audit.json').read_text())
    if audit.get('format')!=FORMAT or audit.get('lightsChanged')is not False:raise ValueError('Unknown original tree evidence')
    if hashlib.sha256((public/'scene-sampling.js').read_bytes()).hexdigest()!='7c16306b5c980e45cf322232d4e669ee2a9ea417bcb990bc49e6812ecfe272bc':raise ValueError('Preserve existing scene sampler changes')
    js=replace_once((public/'explore-map.js').read_text(),"json('/assets/source-layers/manifest.json')","json('/assets/source-map-trees/manifest.json')")
    js=replace_once(js,"data.sceneSampling?.format!=='oc2-scene-sampling-v1'","!['oc2-scene-sampling-v1','oc2-scene-sampling-v2'].includes(data.sceneSampling?.format)")
    js=replace_once(js,"from './scene-sampling.js'","from './scene-sampling.js?sourceTrees=1'")
    html=replace_once((public/'explore-map.html').read_text(),'/explore-map.js?layers=1','/explore-map.js?sourceTrees=1')
    outputs={'prototype/public/explore-map.js':js.encode(),'prototype/public/explore-map.html':html.encode(),'prototype/public/scene-sampling.js':(ROOT/'tools/preview/scene-sampling.js').read_bytes()}
    for p in export.iterdir():
        if not p.is_file()or p.suffix not in('.json','.png'):raise ValueError('Unexpected source tree export')
        name='game-data/converted/source-map-trees/'+p.name
        if(runtime/name).exists()and(runtime/name).read_bytes()!=p.read_bytes():raise ValueError('Preserve existing tree data')
        outputs[name]=p.read_bytes()
    for name,raw in outputs.items():
        p=runtime/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    return {'files':len(outputs),'addedInstances':len(audit['added']),'lightsChanged':False}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--export',type=Path,required=True);a=p.parse_args();print(json.dumps(connect(a.runtime,a.export)))
