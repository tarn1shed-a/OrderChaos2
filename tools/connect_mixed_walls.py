"""Connect only the two checked original mixed-wall placements to local preview."""
import json
from pathlib import Path
from tutorial_map_geometry import ROOT, local_output
from connect_map_geometry import replace_once
from scene_mixed_walls import FORMAT


def connect(runtime, export):
    runtime, export = map(local_output, (runtime, export))
    public = runtime/'prototype/public'
    if (runtime/'game-data/converted').is_symlink():
        raise ValueError('Detach local preview assets first')
    audit = json.loads((export/'audit.json').read_text())
    if (audit.get('format') != FORMAT or audit.get('mixedWallInstances') != 2 or
            audit.get('lightsChanged') is not False or audit.get('originalGPUObserved') is not False):
        raise ValueError('Unverified original mixed-wall export')
    js = (public/'explore-map.js').read_text()
    js = replace_once(js, "json('/assets/source-map-flags/manifest.json')", "json('/assets/source-map-mixed-walls/manifest.json')")
    marker = "import {createContextControl} from './context-control.js';"
    js = replace_once(js, marker, "import{createMixedWallMaterial,bindMixedWallInstance}from './source-mixed-walls.js?mixedWalls=1';\n"+marker)
    js = replace_once(js, "&&data.sceneAlpha?.format!=='oc2-scene-alpha-v1'", "&&data.sourceMixedWall?.format!=='oc2-source-mixed-wall-v1'&&data.sceneAlpha?.format!=='oc2-scene-alpha-v1'")
    marker = '      return applySceneCulling(THREE,createBakedSceneMaterial(THREE,tex,mat,index,data,bakedLighting),mat,index,data.sceneCulling);'
    js = replace_once(js, marker, '      if(data.sourceMixedWall)return createMixedWallMaterial(THREE,tex,mat,index,data,bakedLighting);\n'+marker)
    marker = '        bindFlagInstance(model,inst,canvas,sourceFlags,performance.now());'
    js = replace_once(js, marker, marker+'\n        bindMixedWallInstance(model,inst,canvas);')
    html = replace_once((public/'explore-map.html').read_text(), '/explore-map.js?flagMotion=1', '/explore-map.js?mixedWalls=1')
    outputs = {'prototype/public/explore-map.js': js.encode(), 'prototype/public/explore-map.html': html.encode(),
               'prototype/public/source-mixed-walls.js': (ROOT/'tools/preview/source-mixed-walls.js').read_bytes()}
    for p in export.iterdir():
        if not p.is_file() or p.suffix not in ('.json', '.png'):
            raise ValueError('Unexpected local mixed-wall output')
        name = 'game-data/converted/source-map-mixed-walls/'+p.name
        if (runtime/name).exists() and (runtime/name).read_bytes() != p.read_bytes():
            raise ValueError('Preserve existing mixed-wall output edits')
        outputs[name] = p.read_bytes()
    for name, content in outputs.items():
        p = runtime/name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
    return {'files': len(outputs), 'mixedWallInstances': 2, 'lightsChanged': False, 'originalGPUObserved': False}


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime', type=Path, required=True)
    p.add_argument('--export', type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(connect(args.runtime, args.export)))
