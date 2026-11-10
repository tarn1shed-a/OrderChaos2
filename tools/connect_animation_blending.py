"""Connect source-backed normal state/blend CPU to the isolated shore preview."""
import json
from pathlib import Path
from tutorial_map_geometry import ROOT,local_output
from connect_map_geometry import replace_once
from animation_blending import FORMAT


def connect(runtime,export):
    runtime,export=map(local_output,(runtime,export));assets=runtime/'game-data/converted';public=runtime/'prototype/public'
    if assets.is_symlink():raise ValueError('Detach isolated art directory first')
    profile=json.loads((export/'profile.json').read_text())
    if profile.get('format')!=FORMAT:raise ValueError('Unknown original blending profile')
    js=replace_once((public/'explore-map.js').read_text(),"json('/assets/source-shore/manifest.json')","json('/assets/source-blending/manifest.json')")
    js=replace_once(js,"'./character-animation-shore.js?shore=1'","'./source-locomotion-blending.js?blend=1'")
    marker="a.label.dataset.motion=pose?.phase||'idle';"
    if js.count(marker)!=2:raise ValueError('Original preview actor bindings differ')
    js=js.replace(marker,marker+'a.label.dataset.sourceBlend=JSON.stringify(pose?.sourceBlend||null);')
    html=replace_once((public/'explore-map.html').read_text(),'/explore-map.js?shore=1','/explore-map.js?blend=1')
    native=replace_once((runtime/'prototype/game/native-window-collision.mjs').read_text(),
        'entity.locomotionPosture=result.locomotionPosture;','entity.sourceAnimation=result.sourceAnimation;entity.locomotionPosture=result.locomotionPosture;')
    cfg=json.loads((runtime/'prototype/native-physics.json').read_text());cfg['animationBlending']=str(export/'profile.json')
    outputs={'prototype/public/explore-map.js':js,'prototype/public/explore-map.html':html,
        'prototype/public/source-locomotion-blending.js':(ROOT/'tools/preview/source-locomotion-blending.js').read_text(),
        'prototype/game/native-window-collision.mjs':native,'prototype/native-physics.json':json.dumps(cfg,indent=2)+'\n'}
    for name in ['profile.json','manifest.json','elf-female.json']:
        raw=(export/name).read_text();p=assets/'source-blending'/name
        if p.exists()and p.read_text()!=raw:raise ValueError('Preserve existing source blend art')
        outputs['game-data/converted/source-blending/'+name]=raw
    for name,data in outputs.items():
        p=runtime/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(data)
    return {'files':len(outputs),'sourceNormalStateAndBlendCPU':True,'fullOriginalAnimationSystem':False}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--export',type=Path,required=True);a=p.parse_args();print(json.dumps(connect(a.runtime,a.export)))
