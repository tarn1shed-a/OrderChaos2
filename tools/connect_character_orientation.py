"""Remove an extra browser row inversion from character sampler bindings."""
import hashlib
from pathlib import Path
from tutorial_map_geometry import ROOT, local_output
from connect_map_geometry import replace_once

PINS={'explore-map.js':'c7d25e06c1226c342e74ac4c010c175e5c6710e9161c74737633a0af61d20d91',
      'explore-map.html':'c13a367fd2840db16024ab7cbe7fba47ed0c5ad0549c794759dd7752579f8d53'}

def connect(runtime):
    public=local_output(runtime)/'prototype/public'
    old={n:(public/n).read_bytes()for n in PINS}
    if any(hashlib.sha256(old[n]).hexdigest()!=h for n,h in PINS.items()):raise ValueError('Preserve unexplained or already-connected character entry')
    if(public/'source-character-textures.js').exists():raise ValueError('Preserve existing texture helper')
    js=old['explore-map.js'].decode()
    js="import{sourceCharacterTexture}from'./source-character-textures.js';\n"+js
    js=replace_once(js,'const tex=await texture(url,THREE.NoColorSpace);textures.set(url,tex);',
                    'const tex=sourceCharacterTexture(THREE,await texture(url,THREE.NoColorSpace));textures.set(url,tex);')
    html=replace_once(old['explore-map.html'].decode(),'explore-map.js?pairedFrames=1','explore-map.js?characterRows=1')
    (public/'source-character-textures.js').write_bytes((ROOT/'tools/preview/source-character-textures.js').read_bytes())
    (public/'explore-map.js').write_text(js);(public/'explore-map.html').write_text(html)
    return {'files':3,'originalPixelsChanged':False,'lightingChanged':False,'geometryOrUVChanged':False}

if __name__=='__main__':
    import argparse
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--runtime',type=Path,required=True)
    print(connect(cli.parse_args().runtime))
