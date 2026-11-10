"""Export the checked normal-camera fallback branch and original look-at node.

This is a source profile, not evidence of live Android settings or GPU state.
"""
import hashlib
import json
import struct
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FORMAT='oc2-source-diving-camera-v1'


def recover(image,sources):
    from bdae_convert import BDAE
    from bdae_skin import read_nodes,compose,multiply
    from equipment_appearance import BASE_MODEL
    raw=sources.read(BASE_MODEL)
    with tempfile.TemporaryDirectory()as d:
        p=Path(d)/'body.bdae';p.write_bytes(raw);nodes=read_nodes(BDAE(p))
    world=[];offset=None
    for n in nodes:
        local=compose(n['position'],n['quaternion'],n['scale'])
        world.append(local if n['parent']<0 else multiply(world[n['parent']],local))
        if n['name']=='Dummy_Name-node':offset=world[-1][12:15]
    if offset is None:raise ValueError('Original camera target node absent')
    f=lambda a:struct.unpack('<f',image.read(a,4))[0]
    profile={'format':FORMAT,'nativeSHA256':hashlib.sha256(image.data).hexdigest(),
        'defaultPitch':355,'minPitch':f(0x1dfecc8),'maxPitch':f(0x1dfeccc),'radiansPerDegree':f(0x1df7ad0),
        'minDistance':f(0x1df7a60),'maxDistance':f(0x250b90c),'defaultDistance':580*f(0x1df7a94),
        'lookAtNode':'Dummy_Name','lookAtOffset':offset,'lookAtModel':BASE_MODEL,'lookAtModelSHA256':hashlib.sha256(raw).hexdigest(),
        'branch':'Original empty-configuration fallback, phone zoom maximum; not observed live Android configuration.',
        'bindings':['Static loaded world and host movement records; no original network/spawn/animation dispatcher.',
                    'Original camera CPU normal mode; no ride/combat target/cutscene or resource/GPU completion.',
                    'WebGL projection near plane and mouse/wheel input scaling remain explicit host inputs.']}
    if (profile['minPitch'],profile['maxPitch'],profile['maxDistance'])!=(280,420,12):raise ValueError('Original camera constants changed')
    return profile


def build(output):
    from tutorial_map_geometry import local_output
    from analyze_native_resources import NativeImage
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE
    p=local_output(output)
    if p.exists():raise ValueError('Preserve previous camera profiles; choose a fresh ignored directory')
    profile=recover(NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes()),Sources(DEFAULT_SOURCE))
    p.mkdir(parents=True);(p/'profile.json').write_text(json.dumps(profile,separators=(',',':')))
    return {'profile':str(p/'profile.json'),'lookAtNode':profile['lookAtNode'],'sourceFallback':True}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print(json.dumps(build(a.output)))
