"""Recover original stop-queue timing/CPU fingerprints; export locally only."""
import hashlib
import json
import tempfile
from pathlib import Path
from tutorial_map_geometry import ROOT,local_output

FORMAT='oc2-source-stop-queue-v1'


def recover(image,sources):
    from bdae_animation import BDAEAnimation
    from equipment_appearance import ANIMATION
    from animation_blending import recover as original_actions
    raw=sources.read(ANIMATION)
    with tempfile.TemporaryDirectory()as td:
        p=Path(td)/'original.bdae';p.write_bytes(raw)
        rows={r['name']:r for r in BDAEAnimation(p).ranges()}
    actions=original_actions(image,sources);names={v['anim_name']for v in actions['actions'].values()}
    routines={}
    for a in [0xa4d6c8,0xa4e034,0xa50434,0xa4d638,0xa2db2c,0xa2e108,0x32b518,0x32d58c,0x32e9dc,0x32ee00,0x330d0c,0x32b210,0x32b24c,0x32d978,0x32d9e0,0x11962c0,0x1189f04,0x1196824]:
        info,_=image.routine(a);routines[hex(a)]={**info,'sha256':hashlib.sha256(image.read(int(info['start'],16),info['size'])).hexdigest()}
    return {'format':FORMAT,'nativeSHA256':hashlib.sha256(image.data).hexdigest(),'sourceAnimation':ANIMATION,'sourceAnimationSHA256':hashlib.sha256(raw).hexdigest(),'sourceTableSHA256':actions['sourceTableSHA256'],'ranges':{n:rows[n]for n in sorted(names)},'routines':routines,'scope':'explicit one-channel loaded-track inspection; original request/queue/clock/finish CPU; resource/model/GPU/audio markers and two-channel actor arbitration absent'}


def export(runtime,output):
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE
    from analyze_native_resources import NativeImage
    import copy
    runtime,output=map(local_output,(runtime,output));cfg=json.loads((runtime/'prototype/native-physics.json').read_text());assets=runtime/'game-data/converted'
    profile=recover(NativeImage(Path(cfg['library']).read_bytes()),Sources(DEFAULT_SOURCE))
    manifest=json.loads((assets/'source-blending/manifest.json').read_text());player=json.loads((assets/'source-blending/elf-female.json').read_text())
    if not any(c['name']=='run_idle'for c in player['clips']):raise ValueError('Original stop track absent')
    player=copy.deepcopy(player);player['sourceStopQueueBinding']={'format':FORMAT,'originalTwoChannelAnimation':False};manifest['player']['url']='/assets/source-stop-queue/elf-female.json'
    output.mkdir(parents=True,exist_ok=True)
    for name,v in [('profile.json',profile),('manifest.json',manifest),('elf-female.json',player)]:
        (output/name).write_text(json.dumps(v,separators=(',',':')))
    return {'files':3,'originalStopRangeMs':profile['ranges']['run_idle']['endMs']-profile['ranges']['run_idle']['startMs'],'originalFullAnimationSystem':False}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(export(a.runtime,a.output)))
