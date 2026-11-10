"""Recover normal source state/action entries and original blend inputs locally."""
import hashlib
import json
import struct
from pathlib import Path
from tutorial_map_geometry import ROOT,local_output

FORMAT='oc2-source-locomotion-blending-v1'
TABLE='tables/c_animationdata.tbl'


def action_map(image):
    from source_physics import SourcePhysics
    from unicorn import UC_HOOK_CODE
    class MapVM(SourcePhysics):
        def hook(self,uc,a,n,data):
            if self.imports.get(a)=='_ZNSt3mapIiSt4pairIiiESt4lessIiESaIS0_IKiS1_EEEixEOi':
                if self.get('X0')!=0x25444d0:raise ValueError('Original state map owner differs')
                key=self.r(self.get('X1'),'i')[0]
                if key not in self.cells:self.cells[key]=self.alloc(8)
                self.set('X0',self.cells[key]);self.set('PC',self.get('X30'));return
            if a==0xa4bf68:self.set('PC',self.EXIT);return
            return super().hook(uc,a,n,data)
    e=MapVM(image);e.cells={};e.uc.hook_add(UC_HOOK_CODE,e.hook,begin=0xa4bf68,end=0xa4bf68)
    e.call(0xa4adb0,{})
    # All values were written by the original initializer; the map storage is
    # an explicit host interface. Stop before its unrelated string-map phase.
    return {key:list(e.r(cell,'2i'))for key,cell in e.cells.items()}


def recover(image,sources):
    from skill_attachments import decode_ftable
    raw=sources.read(TABLE);table=decode_ftable(raw,'anim_id');rows={r['anim_id']:r for r in table['rows']}
    mapping=action_map(image);keys=[m|p for m in (2,5)for p in (8,0x18,0x20,0x50)]
    selected={str(k):mapping[k]for k in keys};ids={v for pair in selected.values()for v in pair if v>0}
    routines={}
    for address in [0xa4adb0,0xa51f20,0xa52ec0,0xa528bc,0xa3cf28,0xa4d6c8,0xa4e034,0x32ee00,0x330d0c,0x9e95a4]:
        info,_=image.routine(address);routines[hex(address)]={'bytes':info['size'],'sha256':hashlib.sha256(image.read(address,info['size'])).hexdigest()}
    return {'format':FORMAT,'nativeSHA256':hashlib.sha256(image.data).hexdigest(),'sourceTable':TABLE,
        'sourceTableSHA256':hashlib.sha256(raw).hexdigest(),'nativeRowLayout':image.read(0x1e190df,9).split(b'\0')[0].decode(),
        'actions':{str(i):rows[i]for i in sorted(ids)},'stateActions':selected,'routines':routines,
        'blendOldWeightCap':struct.unpack('<f',image.read(0x1df79ec,4))[0],
        'blendActiveEpsilon':struct.unpack('<f',image.read(0x1df79e8,4))[0],
        'scope':'normal supplied actor; original state CPU and scalar blend CPU; full model/animation loading and primary-queue playback absent'}


def export(runtime,output):
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE
    from analyze_native_resources import NativeImage
    from equipment_appearance import BASE_MODEL,ANIMATION
    from bdae_character import convert_character,aliases
    import tempfile,copy
    runtime,output=map(local_output,(runtime,output));assets=runtime/'game-data/converted';sources=Sources(DEFAULT_SOURCE)
    cfg=json.loads((runtime/'prototype/native-physics.json').read_text());profile=recover(NativeImage(Path(cfg['library']).read_bytes()),sources)
    manifest=json.loads((assets/'source-shore/manifest.json').read_text());old=json.loads((assets/manifest['player']['url'].removeprefix('/assets/')).read_text())
    names=['run_normal_front','run_idle']
    with tempfile.TemporaryDirectory()as td:
        body=Path(td)/'body.bdae';anim=Path(td)/'animations.bdae';body.write_bytes(sources.read(BASE_MODEL));anim.write_bytes(sources.read(ANIMATION))
        converted=convert_character(body,anim,body,extra_actions={n:n for n in names})
    target=aliases(old['rig']['nodes']);remap={}
    for i,node in enumerate(converted['rig']['nodes']):
        if node['name']not in target:raise ValueError('Original blend skeleton node missing')
        j=target[node['name']]
        if any(node[k]!=old['rig']['nodes'][j][k]for k in ('position','quaternion','scale')):raise ValueError('Original blend rest binding differs')
        remap[i]=j
    clips=[c for c in converted['clips']if c['name']in names]
    if len(clips)!=2 or any(c['name']in names for c in old['clips']):raise ValueError('Original blend clip set differs')
    player=copy.deepcopy(old)
    for c in clips:
        for track in c['tracks']:track['node']=remap[track['node']]
    player['clips'].extend(clips);player['sourceBlendBinding']={'source':ANIMATION,'sha256':hashlib.sha256(sources.read(ANIMATION)).hexdigest(),'actions':names,'primaryRunIdleQueueRestored':False}
    manifest['player']['url']='/assets/source-blending/elf-female.json'
    output.mkdir(parents=True,exist_ok=True)
    for n,v in [('profile.json',profile),('manifest.json',manifest),('elf-female.json',player)]:
        (output/n).write_text(json.dumps(v,separators=(',',':')))
    return {'originalActionMapEntries':len(profile['stateActions']),'addedOriginalClips':names,'primaryQueueRestored':False}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(export(a.runtime,a.output)))
