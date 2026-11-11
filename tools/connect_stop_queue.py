"""Connect the source-backed stop queue to an isolated blending preview."""
import json
from pathlib import Path
from tutorial_map_geometry import ROOT,local_output
from connect_map_geometry import replace_once
from stop_queue_assets import FORMAT


def connect(runtime,export):
    runtime,export=map(local_output,(runtime,export));assets=runtime/'game-data/converted';public=runtime/'prototype/public'
    if assets.is_symlink():raise ValueError('Detach isolated art directory first')
    profile=json.loads((export/'profile.json').read_text())
    if profile.get('format')!=FORMAT:raise ValueError('Unknown original stop-queue profile')
    js=replace_once((public/'explore-map.js').read_text(),"json('/assets/source-blending/manifest.json')","json('/assets/source-stop-queue/manifest.json')")
    js=replace_once(js,"'./source-locomotion-blending.js?blend=1'","'./source-locomotion-blending.js?stopQueue=1'")
    html=replace_once((public/'explore-map.html').read_text(),'/explore-map.js?blend=1','/explore-map.js?stopQueue=1')
    cfg=json.loads((runtime/'prototype/native-physics.json').read_text())
    if cfg.get('stopQueue'):raise ValueError('Preserve existing stop-queue binding')
    cfg['stopQueue']=str(export/'profile.json')
    outputs={'prototype/public/explore-map.js':js,'prototype/public/explore-map.html':html,'prototype/public/source-locomotion-blending.js':(ROOT/'tools/preview/source-locomotion-blending.js').read_text(),'prototype/native-physics.json':json.dumps(cfg,indent=2)+'\n'}
    for name in ['profile.json','manifest.json','elf-female.json']:
        text=(export/name).read_text();p=assets/'source-stop-queue'/name
        if p.exists()and p.read_text()!=text:raise ValueError('Preserve existing source stop art')
        outputs['game-data/converted/source-stop-queue/'+name]=text
    for name,text in outputs.items():
        p=runtime/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
    return {'files':len(outputs),'sourceQueueAndTimedCompletionCPU':True,'originalTwoChannelAnimation':False}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--export',type=Path,required=True);a=p.parse_args();print(json.dumps(connect(a.runtime,a.export)))
