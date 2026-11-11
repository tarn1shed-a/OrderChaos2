"""Resolve the selected original model's layer flags and CPU scope locally."""
import hashlib
import json
from pathlib import Path
from tutorial_map_geometry import ROOT,local_output
from stop_queue_assets import recover as stop_profile

FORMAT='oc2-source-layer-queue-v1'


def model_flags(vm,flags):
    actor=vm.alloc(0x1200)
    vm.original_fragment(0x9e96e8,0x9e9704,{'X19':actor},stack=(0,)*60+(flags<<32,))
    a,b=vm.get('W21'),vm.get('W24')
    vm.original_fragment(0x9e9798,0x9e97b0,{'W21':a,'W24':b,'X29':vm.STACK+0xd0})
    return vm.get('W3')


def recover(image,sources):
    from equipment_appearance import BASE_MODEL,ANIMATION
    from bdae_animation import BDAEAnimation
    import tempfile
    from skill_attachments import decode_ftable
    from source_stop_queue import SourceStopQueue
    vm=SourceStopQueue(image);raw=sources.read('tables/creaturemodeldata.tbl');table=decode_ftable(raw,'ID')
    rows=[{'ID':r['ID'],'Flags':r['Flags'],'engineFlags':model_flags(vm,r['Flags'])}for r in table['rows']if r['ModelPath']==BASE_MODEL]
    if not rows or {r['engineFlags']for r in rows}!={3}:raise ValueError('Original selected model layer mode unresolved')
    with tempfile.TemporaryDirectory()as td:
        p=Path(td)/'original.bdae';p.write_bytes(sources.read(ANIMATION));clip_names=sorted({r['name']for r in BDAEAnimation(p).ranges()})
    routines={}
    for a in [0x9e95a4,0xc89394,0xc992e8,0xa50148,0x331a28,0x331cf8,0x330940,0x32d0c8,0x32c9dc]:
        info,_=image.routine(a);routines[hex(a)]={**info,'sha256':hashlib.sha256(image.read(int(info['start'],16),info['size'])).hexdigest()}
    return {'format':FORMAT,'nativeSHA256':hashlib.sha256(image.data).hexdigest(),'modelPath':BASE_MODEL,'modelRows':rows,'modelTableSHA256':hashlib.sha256(raw).hexdigest(),'sourceClipNames':clip_names,'nativeModelRowLayout':image.read(0x1ef11ee,19).split(b'\0')[0].decode(),'engineFlags':3,'channels':2,'routines':routines,'stopRange':stop_profile(image,sources)['ranges']['run_idle'],'scope':'two original CPU queues/clocks/priority query; publish only agreeing poses; distinct-track bone composition/model/GPU/complete actor deque absent'}


def export(runtime,output):
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE
    from analyze_native_resources import NativeImage
    runtime,output=map(local_output,(runtime,output));cfg=json.loads((runtime/'prototype/native-physics.json').read_text());assets=runtime/'game-data/converted'
    profile=recover(NativeImage(Path(cfg['library']).read_bytes()),Sources(DEFAULT_SOURCE));manifest=json.loads((assets/'source-stop-queue/manifest.json').read_text());player=json.loads((assets/'source-stop-queue/elf-female.json').read_text())
    manifest['player']['url']='/assets/source-layers/elf-female.json';player['sourceLayerQueueBinding']={'format':FORMAT,'engineFlags':profile['engineFlags'],'distinctPoseCompositionRestored':False}
    output.mkdir(parents=True,exist_ok=True)
    for name,value in [('profile.json',profile),('manifest.json',manifest),('elf-female.json',player)]:
        (output/name).write_text(json.dumps(value,separators=(',',':')))
    return {'files':3,'modelRows':len(profile['modelRows']),'sourceChannels':2,'distinctPoseCompositionRestored':False}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(export(a.runtime,a.output)))
