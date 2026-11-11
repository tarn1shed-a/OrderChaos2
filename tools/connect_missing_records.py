"""Attach only the verified original empty-DAT/default-lightMap instances."""
import json
from pathlib import Path
from tutorial_map_geometry import ROOT, local_output
from connect_map_geometry import replace_once
from scene_missing_records import FORMAT


def connect(runtime, export):
    runtime, export = map(local_output, (runtime, export)); public = runtime/'prototype/public'
    if (runtime/'game-data/converted').is_symlink():raise ValueError('Detach local source assets first')
    audit = json.loads((export/'audit.json').read_text())
    if audit.get('format') != FORMAT or audit.get('instancesAdded') != 7 or audit.get('lightsChanged') is not False:
        raise ValueError('Unverified missing-record output')
    js = (public/'explore-map.js').read_text()
    js = replace_once(js,"json('/assets/source-map-palette/manifest.json')","json('/assets/source-map-record-gaps/manifest.json')")
    marker = "import {createContextControl} from './context-control.js';"
    js = replace_once(js,marker,"import{createMissingRecordContext}from './source-missing-records.js?records=1';\n"+marker)
    js = replace_once(js,'    const staticModels = new Map();',"    const missingRecords=await createMissingRecordContext(THREE,await json(assets.sourceMissingRecords.url),texture,bakedLighting,canvas);\n    const staticModels = new Map();")
    js = replace_once(js,'if(model.userData.sourceZeroPlane)bindZeroPlaneInstance(model,inst,canvas);else if(!model.userData.sourcePalette)bindInstanceLightmap(THREE,model,inst,bakedLighting,bakedAtlases);',
                      'if(missingRecords.bind(model,inst)){}else if(model.userData.sourceZeroPlane)bindZeroPlaneInstance(model,inst,canvas);else if(!model.userData.sourcePalette)bindInstanceLightmap(THREE,model,inst,bakedLighting,bakedAtlases);')
    html = replace_once((public/'explore-map.html').read_text(),'/explore-map.js?palette=1','/explore-map.js?records=1')
    outputs = {'prototype/public/explore-map.js':js.encode(),'prototype/public/explore-map.html':html.encode(),
               'prototype/public/source-missing-records.js':(ROOT/'tools/preview/source-missing-records.js').read_bytes()}
    for p in export.iterdir():
        if not p.is_file() or p.suffix not in ('.json','.png'):raise ValueError('Unexpected source-record output')
        name='game-data/converted/source-map-record-gaps/'+p.name
        if (runtime/name).exists() and (runtime/name).read_bytes()!=p.read_bytes():raise ValueError('Preserve existing record-gap data')
        outputs[name]=p.read_bytes()
    for n,b in outputs.items():
        p=runtime/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
    return {'files':len(outputs),'instancesAdded':7,'lightsChanged':False}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--export',type=Path,required=True)
    a=p.parse_args();print(json.dumps(connect(a.runtime,a.export)))
