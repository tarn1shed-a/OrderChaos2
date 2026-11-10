"""Connect checked shore motion only to the existing ignored diving preview."""
import json
from pathlib import Path
from tutorial_map_geometry import ROOT,local_output
from connect_map_geometry import replace_once


def connect(runtime,export):
    runtime,export=map(local_output,(runtime,export));public=runtime/'prototype/public';assets=runtime/'game-data/converted'
    if assets.is_symlink():raise ValueError('Detach isolated art directory first')
    js=replace_once((public/'explore-map.js').read_text(),"json('/assets/source-swimming/manifest.json')","json('/assets/source-shore/manifest.json')")
    js=replace_once(js,"'./character-animation-swimming.js?swim=1'","'./character-animation-shore.js?shore=1'")
    js=replace_once(js,'a.label.dataset.submerged=String(p.submerged===true);','a.label.dataset.sourcePosture=String(p.sourcePosture??\'\');a.label.dataset.sourceLocomotion=String(p.locomotionPosture??\'\');a.label.dataset.submerged=String(p.submerged===true);')
    html=replace_once((public/'explore-map.html').read_text(),'/explore-map.js?diving=1','/explore-map.js?shore=1')
    native=(runtime/'prototype/game/native-window-collision.mjs').read_text()
    native="import{sourceAirborne}from'../public/source-shore-motion.js';\n"+native
    native=replace_once(native,'entity.sourcePosture=result.lastPosture;','entity.locomotionPosture=result.locomotionPosture;entity.sourcePosture=result.lastPosture;')
    native=replace_once(native,'else if(!result.grounded){','else if(sourceAirborne(result)){')
    native=replace_once(native,'}else if(entity.jump&&entity.jump.landedAt===null){','}else if(entity.jump&&result.grounded&&entity.jump.landedAt===null){')
    native=replace_once(native,'    if(entity.jump&&now>=entity.jump.endsAt)entity.jump=null;',
        '    if(!result.grounded&&!sourceAirborne(result))entity.jump=null;\n    if(entity.jump&&now>=entity.jump.endsAt)entity.jump=null;')
    animation=(ROOT/'tools/preview/source-shore-animation.js').read_text()
    cfg=json.loads((runtime/'prototype/native-physics.json').read_text());cfg['shoreTransitions']=True
    outputs={'prototype/public/explore-map.js':js,'prototype/public/explore-map.html':html,
        'prototype/public/character-animation-shore.js':animation,
        'prototype/public/source-shore-motion.js':(ROOT/'tools/preview/source-shore-motion.js').read_text(),
        'prototype/game/native-window-collision.mjs':native,'prototype/native-physics.json':json.dumps(cfg,indent=2)+'\n'}
    for name in ['manifest.json','elf-female.json']:
        raw=(export/name).read_text();p=assets/'source-shore'/name
        if p.exists()and p.read_text()!=raw:raise ValueError('Preserve existing source-shore art')
        outputs['game-data/converted/source-shore/'+name]=raw
    for name,data in outputs.items():
        p=runtime/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(data)
    return {'files':len(outputs),'originalLocomotionDecisions':True,'originalAnimationDispatcher':False}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--export',type=Path,required=True);a=p.parse_args();print(json.dumps(connect(a.runtime,a.export)))
