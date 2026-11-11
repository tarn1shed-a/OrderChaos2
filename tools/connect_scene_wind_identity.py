"""Attach only verified original zero-speed vegetation; preserve other inputs."""
import hashlib,json
from pathlib import Path
from tutorial_map_geometry import ROOT,local_output
from connect_map_geometry import replace_once
from scene_wind_identity import FORMAT


def connect(runtime,export):
    runtime,export=map(local_output,(runtime,export));assets=runtime/'game-data/converted';public=runtime/'prototype/public'
    if assets.is_symlink():raise ValueError('Detach isolated art first')
    audit=json.loads((export/'audit.json').read_text())
    if audit.get('format')!=FORMAT or audit.get('lightsChanged')is not False:raise ValueError('Unknown source zero-wind branch')
    alpha=(public/'scene-alpha.js').read_text();cull=(public/'scene-culling.js').read_text()
    alpha=replace_once(alpha,"  'ut_lightmap_gray_trans.bdae':'discard-less-equal',","  'ut_lightmap_gray_trans.bdae':'discard-less-equal',\n  'ut_lightmap_shake_gray_trans.bdae':'discard-less-equal',")
    cull=replace_once(cull," 'ut_lightmap_gray_trans.bdae':false,"," 'ut_lightmap_gray_trans.bdae':false,\n 'ut_lightmap_shake_gray_trans.bdae':false,")
    js=replace_once((public/'explore-map.js').read_text(),"json('/assets/source-map-gray/manifest.json')","json('/assets/source-map-zero-wind/manifest.json')")
    js=replace_once(js,"from './source-gray-materials.js?sourceGray=1'","from './source-wind-identity.js?sourceWind=1'")
    html=replace_once((public/'explore-map.html').read_text(),'/explore-map.js?sourceGray=1','/explore-map.js?sourceWind=1')
    outputs={'prototype/public/explore-map.js':js.encode(),'prototype/public/explore-map.html':html.encode(),'prototype/public/scene-alpha.js':alpha.encode(),'prototype/public/scene-culling.js':cull.encode(),'prototype/public/source-wind-identity.js':(ROOT/'tools/preview/source-wind-identity.js').read_bytes()}
    for p in export.iterdir():
        if not p.is_file()or p.suffix not in('.json','.png'):raise ValueError('Unexpected wind asset entry')
        n='game-data/converted/source-map-zero-wind/'+p.name
        if(runtime/n).exists()and(runtime/n).read_bytes()!=p.read_bytes():raise ValueError('Preserve existing zero-wind asset')
        outputs[n]=p.read_bytes()
    for n,b in outputs.items():
        p=runtime/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
    return {'files':len(outputs),'addedInstances':len(audit['added']),'lightsChanged':False}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--export',type=Path,required=True);a=p.parse_args();print(json.dumps(connect(a.runtime,a.export)))
