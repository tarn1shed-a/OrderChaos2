"""Remove the verified extra wolf row inversion in the private map preview."""
import hashlib
from pathlib import Path
from tutorial_map_geometry import ROOT,local_output
from connect_map_geometry import replace_once

PINS={'explore-map.js':'a524d8052643bf3a706acb3e641860b3a003e1d96ea2435008ecd0950d5faf97',
      'explore-map.html':'dd34a4a2f1eb61b2b2ce74215bdec31ca2c2ef886b85bf12ffe1953abf11154c'}

def connect(runtime):
    public=local_output(runtime)/'prototype/public'
    old={n:(public/n).read_bytes()for n in PINS}
    if any(hashlib.sha256(old[n]).hexdigest()!=h for n,h in PINS.items()):
        raise ValueError('Preserve unexplained or already-connected map changes')
    helper=public/'source-wolf-texture.js'
    if helper.exists():raise ValueError('Preserve existing wolf helper')
    js="import{sourceWolfTexture}from'./source-wolf-texture.js';\n"+old['explore-map.js'].decode()
    js=replace_once(js,'let tex = data.sceneSampling ? sceneDiffuseTexture(THREE,cached,mat,index,data.sceneSampling) : cached;',
                   'let tex = data.sceneSampling ? sceneDiffuseTexture(THREE,cached,mat,index,data.sceneSampling) : sourceWolfTexture(THREE,entry,data,mat,cached);')
    html=replace_once(old['explore-map.html'].decode(),'explore-map.js?characterRows=1','explore-map.js?wolfRows=1')
    helper.write_bytes((ROOT/'tools/preview/source-wolf-texture.js').read_bytes())
    (public/'explore-map.js').write_text(js);(public/'explore-map.html').write_text(html)
    return {'files':3,'wolfRowFlip':False,'diffuseAddress':'Repeat','geometryOrUVChanged':False,'lightingChanged':False,'originalPixelsChanged':False}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True)
    print(connect(p.parse_args().runtime))
