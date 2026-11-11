"""Connect checked non-lightmapped, all-zero-alpha placements to local preview."""
import json
from pathlib import Path
from tutorial_map_geometry import ROOT,local_output
from connect_map_geometry import replace_once
from scene_zero_planes import FORMAT


def connect(runtime,export):
    runtime,export=map(local_output,(runtime,export));public=runtime/'prototype/public'
    if(runtime/'game-data/converted').is_symlink():raise ValueError('Detach isolated art first')
    audit=json.loads((export/'audit.json').read_text())
    if audit.get('format')!=FORMAT or audit.get('lightsChanged')is not False or audit.get('zeroAlphaInstances')!=31:raise ValueError('Unknown source plane export')
    js=(public/'explore-map.js').read_text();js=replace_once(js,"json('/assets/source-map-dynamic-wind/manifest.json')","json('/assets/source-map-zero-planes/manifest.json')")
    js=replace_once(js,"import {createContextControl} from './context-control.js';","import {createZeroPlaneMaterial,bindZeroPlaneInstance,ZERO_PLANE_FORMAT}from './source-zero-planes.js?zeroPlanes=1';\nimport {createContextControl} from './context-control.js';")
    js=replace_once(js,"if(assets.scenery?.includes(entry)&&data.sceneBakedLighting?.format!==BAKED_FORMAT)","if(assets.scenery?.includes(entry)&&!data.sourceZeroPlane&&data.sceneBakedLighting?.format!==BAKED_FORMAT)")
    js=replace_once(js,"data.sceneBakedLighting?THREE.NoColorSpace:THREE.SRGBColorSpace","(data.sceneBakedLighting||data.sourceZeroPlane)?THREE.NoColorSpace:THREE.SRGBColorSpace")
    marker='    if(data.sceneBakedLighting){\n      tex.flipY=false;tex.needsUpdate=true;'
    js=replace_once(js,marker,"    if(data.sourceZeroPlane){tex.flipY=false;tex.needsUpdate=true;return applySceneCulling(THREE,createZeroPlaneMaterial(THREE,tex,mat,index,data),mat,index,data.sceneCulling);}\n"+marker)
    marker='  guardSceneOrientation(root,()=>{canvas.dataset.sceneCullDraw=\'positive-transform-checked\';});'
    js=replace_once(js,marker,"  if(data.sourceZeroPlane)root.userData.sourceZeroPlane={format:ZERO_PLANE_FORMAT};\n"+marker)
    js=replace_once(js,'        bindInstanceLightmap(THREE,model,inst,bakedLighting,bakedAtlases);','        if(model.userData.sourceZeroPlane)bindZeroPlaneInstance(model,inst,canvas);else bindInstanceLightmap(THREE,model,inst,bakedLighting,bakedAtlases);')
    js=replace_once(js,"          material.onBeforeCompile=()=>{canvas.dataset.sceneBakedShader=", "          if(material.userData.sourceZeroPlane)continue;\n          material.onBeforeCompile=()=>{canvas.dataset.sceneBakedShader=")
    marker="    canvas.dataset.sceneSampling='oc2-scene-sampling-v1';"
    js=replace_once(js,marker,"    canvas.dataset.sourceZeroPlaneInstances=String(assets.scenery.filter(m=>m.model==='model/scene/plane.bdae').reduce((n,m)=>n+m.instances.length,0));\n"+marker)
    cull=replace_once((public/'scene-culling.js').read_text()," 'ut_lightmap_shake_trans.bdae':false,"," 'ut_lightmap_shake_trans.bdae':false,\n 'ut_trans.bdae':false,")
    html=replace_once((public/'explore-map.html').read_text(),'/explore-map.js?dynamicWind=1','/explore-map.js?zeroPlanes=1')
    outputs={'prototype/public/explore-map.js':js.encode(),'prototype/public/explore-map.html':html.encode(),'prototype/public/scene-culling.js':cull.encode(),'prototype/public/source-zero-planes.js':(ROOT/'tools/preview/source-zero-planes.js').read_bytes()}
    for p in export.iterdir():
        if not p.is_file()or p.suffix not in('.json','.png'):raise ValueError('Unexpected plane export')
        n='game-data/converted/source-map-zero-planes/'+p.name
        if(runtime/n).exists()and(runtime/n).read_bytes()!=p.read_bytes():raise ValueError('Preserve existing plane asset edits')
        outputs[n]=p.read_bytes()
    for n,b in outputs.items():p=runtime/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
    return {'files':len(outputs),'sourcePlaneInstances':31,'newVisiblePixelsExpected':False,'lightsChanged':False}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--export',type=Path,required=True);a=p.parse_args();print(json.dumps(connect(a.runtime,a.export)))
