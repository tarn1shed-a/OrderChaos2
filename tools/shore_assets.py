"""Add the original run_normal track without replacing existing art/animations."""
import copy
import hashlib
import json
import tempfile
from pathlib import Path
from tutorial_map_geometry import ROOT,local_output


def player_clips(sources,old):
    from equipment_appearance import BASE_MODEL,ANIMATION
    from bdae_character import convert_character,aliases
    with tempfile.TemporaryDirectory()as d:
        body=Path(d)/'body.bdae';anim=Path(d)/'anim.bdae'
        body.write_bytes(sources.read(BASE_MODEL));anim.write_bytes(sources.read(ANIMATION))
        converted=convert_character(body,anim,body,extra_actions={'run_normal':'run_normal'})
    target=aliases(old['rig']['nodes']);remap={}
    for i,node in enumerate(converted['rig']['nodes']):
        if node['name']not in target:raise ValueError('Original run skeleton alias missing')
        j=target[node['name']]
        if any(node[k]!=old['rig']['nodes'][j][k]for k in ['position','quaternion','scale']):raise ValueError('Original run rest binding differs')
        remap[i]=j
    clips=[c for c in converted['clips']if c['name']=='run_normal']
    if len(clips)!=1 or any(c['name']=='run_normal'for c in old['clips']):raise ValueError('Unexpected original run clip set')
    for track in clips[0]['tracks']:track['node']=remap[track['node']]
    result=copy.deepcopy(old);result['clips'].extend(clips)
    result['shoreBinding']={'source':ANIMATION,'sha256':hashlib.sha256(sources.read(ANIMATION)).hexdigest(),
        'action':'run_normal','selection':'original a6906c normal movement request 0x20; dispatch/blend remain host interfaces'}
    return result


def export(runtime,output):
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE
    runtime,output=map(local_output,(runtime,output));assets=runtime/'game-data/converted'
    manifest=json.loads((assets/'source-swimming/manifest.json').read_text())
    old=json.loads((assets/manifest['player']['url'].removeprefix('/assets/')).read_text())
    player=player_clips(Sources(DEFAULT_SOURCE),old)
    manifest['player']['url']='/assets/source-shore/elf-female.json'
    output.mkdir(parents=True,exist_ok=True)
    for name,data in [('elf-female.json',player),('manifest.json',manifest)]:
        (output/name).write_text(json.dumps(data,separators=(',',':')))
    return {'originalRunClipAdded':True,'existingClipsPreserved':True}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(export(a.runtime,a.output)))
