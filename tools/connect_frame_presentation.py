"""Repair paired actor/camera display timing in the ignored web preview.

This is a browser transport adaptation, not recovered original gameplay.
"""
import argparse
import hashlib
from pathlib import Path
from tutorial_map_geometry import ROOT, local_output
from connect_map_geometry import replace_once

PINS = {'explore-map.js':'bbbe7e6fbfbf45ffa281cb7f08410099285afb8c62ca14522f9d387f4d1f1c60',
        'explore-map.html':'890166e4e31864e62de8ee193f0acc5d83a0eeefd52e4e1c7f615193db0bdd70'}


def connect(runtime):
    public = local_output(runtime)/'prototype/public'
    old = {name:(public/name).read_bytes() for name in PINS}
    if any(hashlib.sha256(old[n]).hexdigest()!=h for n,h in PINS.items()):
        raise ValueError('Preview changed or presentation already connected; preserve it')
    if (public/'source-frame-presentation.js').exists(): raise ValueError('Preserve existing presentation helper')
    js = old['explore-map.js'].decode()
    marker = "const sourceCameraInput=createSourceCameraInput();"
    js = replace_once(js, marker, marker+"\nimport{createSourceFramePresentation}from'./source-frame-presentation.js';\nconst sourcePresentation=createSourceFramePresentation();")
    js = replace_once(js,"snapshot = msg.players;questBook?", "sourcePresentation.push(msg.players,msg.serverTime,performance.now());snapshot = msg.players;questBook?")
    js = replace_once(js,"connected = false; snapshot = [];", "sourcePresentation.reset();connected = false; snapshot = [];")
    marker = '  for(const [id,a] of avatars){\n    updateCharacterAnimation'
    js = replace_once(js,marker,'  const presented=sourcePresentation.sample(now);\n'+marker)
    marker = '    a.root.position.lerp(a.target,1-Math.exp(-dt*16));\n'
    js = replace_once(js,marker,"    const paired=presented.get(id);\n    if(paired)a.root.position.copy(entityPosition(paired));else a.root.position.lerp(a.target,1-Math.exp(-dt*16));\n")
    js = replace_once(js,'const nativeCamera=snapshot.find(p=>p.id===selfId)?.sourceCamera;',
                      'const nativeCamera=presented.get(selfId)?.sourceCamera||snapshot.find(p=>p.id===selfId)?.sourceCamera;')
    marker='canvas.dataset.sourceCameraControl=JSON.stringify(nativeCamera);'
    js=replace_once(js,marker,marker+"canvas.dataset.sourceFramePresentation=JSON.stringify(presented.get(selfId)?.presentation||null);")
    html = replace_once(old['explore-map.html'].decode(), 'explore-map.js?templeSampling=1', 'explore-map.js?pairedFrames=1')
    # All validation precedes the three writes; sources/assets/physics untouched.
    (public/'source-frame-presentation.js').write_bytes((ROOT/'tools/preview/source-frame-presentation.js').read_bytes())
    (public/'explore-map.js').write_text(js);(public/'explore-map.html').write_text(html)
    return {'files':3,'physicsChanged':False,'lightingChanged':False,'hostPresentationOnly':True}


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--runtime',type=Path,required=True)
    print(connect(cli.parse_args().runtime))
