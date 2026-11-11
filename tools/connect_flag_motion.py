"""Connect only checked original flag motion to the existing local map page."""
import json
from pathlib import Path
from tutorial_map_geometry import ROOT,local_output
from connect_map_geometry import replace_once
from scene_flag_motion import FORMAT


def connect(runtime,export):
    runtime,export=map(local_output,(runtime,export));public=runtime/'prototype/public'
    if(runtime/'game-data/converted').is_symlink():raise ValueError('Detach local preview assets first')
    audit=json.loads((export/'audit.json').read_text())
    if audit.get('format')!=FORMAT or audit.get('flagInstances')!=17 or audit.get('lightsChanged')is not False or audit.get('originalGPUObserved')is not False:raise ValueError('Unverified flag export')
    js=(public/'explore-map.js').read_text()
    js=replace_once(js,"json('/assets/source-map-zero-planes/manifest.json')","json('/assets/source-map-flags/manifest.json')")
    marker="import {createContextControl} from './context-control.js';"
    js=replace_once(js,marker,"import{prepareFlagModel,bindFlagInstance,updateFlags}from './source-flag-motion.js?flagMotion=1';\nconst sourceFlags=[];\n"+marker)
    marker="  guardSceneOrientation(root,()=>{canvas.dataset.sceneCullDraw='positive-transform-checked';});"
    js=replace_once(js,marker,'  prepareFlagModel(root,data);\n'+marker)
    marker='        bindDynamicWind(THREE,model,origin,windClock,canvas);'
    js=replace_once(js,marker,marker+'\n        bindFlagInstance(model,inst,canvas,sourceFlags,performance.now());')
    js=replace_once(js,'function draw(now) {','function draw(now) {\n  updateFlags(sourceFlags,now,canvas);')
    html=replace_once((public/'explore-map.html').read_text(),'/explore-map.js?zeroPlanes=1','/explore-map.js?flagMotion=1')
    outputs={'prototype/public/explore-map.js':js.encode(),'prototype/public/explore-map.html':html.encode()}
    for name in('source-flag-motion.js','flag-motion-math.js'):outputs['prototype/public/'+name]=(ROOT/'tools/preview'/name).read_bytes()
    for p in export.iterdir():
        if not p.is_file()or p.suffix not in('.json','.png'):raise ValueError('Unexpected local flag export')
        name='game-data/converted/source-map-flags/'+p.name
        if(runtime/name).exists()and(runtime/name).read_bytes()!=p.read_bytes():raise ValueError('Preserve existing flag output edits')
        outputs[name]=p.read_bytes()
    for name,b in outputs.items():p=runtime/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
    return {'files':len(outputs),'flagInstances':17,'lightsChanged':False,'hostCPUDeformation':True,'originalGPUObserved':False}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--export',type=Path,required=True);a=p.parse_args();print(json.dumps(connect(a.runtime,a.export)))
