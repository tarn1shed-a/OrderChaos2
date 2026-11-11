"""Connect one source palette mesh; keep existing map lights and other models."""
import json
from pathlib import Path
from tutorial_map_geometry import ROOT, local_output
from connect_map_geometry import replace_once
from scene_palette_model import FORMAT


def connect(runtime, export):
    runtime, export = map(local_output, (runtime, export))
    public = runtime/'prototype/public'
    if (runtime/'game-data/converted').is_symlink():
        raise ValueError('Detach local preview assets first')
    audit = json.loads((export/'audit.json').read_text())
    if audit.get('format') != FORMAT or audit.get('paletteInstances') != 1 or audit.get('lightsChanged') is not False or audit.get('lightmapConsumed') is not False:
        raise ValueError('Unverified original palette export')
    js = (public/'explore-map.js').read_text()
    js = replace_once(js, "json('/assets/source-map-mixed-walls/manifest.json')", "json('/assets/source-map-palette/manifest.json')")
    marker = "import {createContextControl} from './context-control.js';"
    js = replace_once(js, marker, "import{preparePaletteSource,createPaletteMaterial,preparePaletteModel,bindPaletteInstance}from './source-scene-palette.js?palette=1';\n"+marker)
    marker = "  await prepareDynamicWind(data,async url=>{const r=await fetch(url);if(!r.ok)throw Error('原摇动程序缺失');return r.text();});"
    js = replace_once(js, marker, marker+"\n  await preparePaletteSource(data,async url=>{const r=await fetch(url);if(!r.ok)throw Error('原锤座程序缺失');return r.text();});")
    js = replace_once(js, "&&!data.sourceZeroPlane&&data.sceneBakedLighting?.format!==BAKED_FORMAT", "&&!data.sourceZeroPlane&&data.sourcePalette?.format!=='oc2-source-scene-palette-v1'&&data.sceneBakedLighting?.format!==BAKED_FORMAT")
    js = replace_once(js, "&&data.sourceMixedWall?.format!=='oc2-source-mixed-wall-v1'", "&&data.sourcePalette?.format!=='oc2-source-scene-palette-v1'&&data.sourceMixedWall?.format!=='oc2-source-mixed-wall-v1'")
    js = replace_once(js, '  if(data.characterMaterials){', '  if(data.sourcePalette){materials=[await createPaletteMaterial(THREE,data,texture)];}else if(data.characterMaterials){')
    js = replace_once(js, '  prepareFlagModel(root,data);', '  prepareFlagModel(root,data);\n  preparePaletteModel(root,data);')
    js = replace_once(js, 'if(material.userData.sourceZeroPlane)continue;', 'if(material.userData.sourceZeroPlane||material.userData.sourcePalette)continue;')
    js = replace_once(js, 'else bindInstanceLightmap(THREE,model,inst,bakedLighting,bakedAtlases);', 'else if(!model.userData.sourcePalette)bindInstanceLightmap(THREE,model,inst,bakedLighting,bakedAtlases);')
    marker = '        bindMixedWallInstance(model,inst,canvas);'
    js = replace_once(js, marker, marker+'\n        bindPaletteInstance(THREE,model,inst,bakedLighting,origin,canvas);')
    html = replace_once((public/'explore-map.html').read_text(), '/explore-map.js?mixedWalls=1', '/explore-map.js?palette=1')
    outputs = {'prototype/public/explore-map.js': js.encode(), 'prototype/public/explore-map.html': html.encode(),
               'prototype/public/source-scene-palette.js': (ROOT/'tools/preview/source-scene-palette.js').read_bytes()}
    for p in export.iterdir():
        if not p.is_file() or p.suffix not in ('.json', '.png', '.glsl'):
            raise ValueError('Unexpected original palette output')
        name = 'game-data/converted/source-map-palette/'+p.name
        if (runtime/name).exists() and (runtime/name).read_bytes() != p.read_bytes():
            raise ValueError('Preserve existing palette output edits')
        outputs[name] = p.read_bytes()
    for name, content in outputs.items():
        p = runtime/name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
    return {'files': len(outputs), 'paletteInstances': 1, 'lightsChanged': False, 'originalGPUObserved': False}


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime', type=Path, required=True)
    p.add_argument('--export', type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(connect(args.runtime, args.export)))
