"""Export the source PHY selection and placements for the explicit map window.

Complete original data stays local. No collision hulls are inferred from art.
"""
import argparse
import collections
import hashlib
import json
import struct
from pathlib import Path
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from scene_collision import decode_phy
from tutorial_map_geometry import ROOT,local_output


def phy_candidates(model):
    stem=model.rsplit('.',1)[0]
    if stem.endswith('_h'):stem=stem[:-2]
    return stem+'_s.phy',stem+'.phy'


def build(source,geometry,output):
    output=local_output(output);output.mkdir(parents=True,exist_ok=True)
    if (output/'collision.json').exists():raise ValueError('Preserve existing collision evidence; choose fresh output')
    sources=Sources(source);geometry=Path(geometry)
    selection_report=json.loads((geometry/'verified/selection.json').read_text())
    if selection_report['profile']!='APK_Default' or selection_report['settings']['ModelDetailLevel']!=0:
        raise ValueError('This collision export is bound to the verified APK Default branch')
    if any(i['admission']!='admittedBeforeTypeFactory' for i in selection_report['instances']):
        raise ValueError('A source instance fails original pre-creation admission')
    terrain=json.loads((geometry/'base/maps/tutorial-window.json').read_text())
    original=json.loads((geometry/'base/manifest.json').read_text())
    shapes={};instances=[];selection=[];flags=collections.Counter();raw_ids=set()
    for tile in terrain['sourceTiles']:
        x,z=tile['tile'];name=f'world/tutorial/items/{x:04d}_{z:04d}.itm'
        if not sources.candidates(name):continue
        raw=sources.read(name)
        for i in range(struct.unpack_from('<I',raw,16)[0]):
            at=24+i*76;ident=struct.unpack_from('<I',raw,at+4)[0]
            detail,phase=struct.unpack_from('<II',raw,at+56)
            if detail&3!=3 or phase!=0xffffffff:raise ValueError('New source collision admission branch needs tracing')
            raw_ids.add(ident);flags[detail&3]+=1
    for model in original['scenery']:
        small,normal=phy_candidates(model['model'])
        # Both original flag branches resolve the same path only when the
        # simplified candidate is absent. Do not guess a live global value.
        if sources.candidates(small):raise ValueError('Small PHY exists: actual mode/provider selection is required')
        raw=sources.read(normal);decoded=decode_phy(raw);shapes[normal]=decoded
        selection.append({'model':model['model'],'missingSimplified':small,'selected':normal,'sourceSHA256':decoded['sourceSHA256']})
        for item in model['instances']:
            if item['sourceType']!=2:raise ValueError('Inside-PHY branch needs separate tracing')
            instances.append({**item,'sourcePHY':normal})
    if {i['id']for i in instances}!=raw_ids:raise ValueError('Source instance coverage differs')
    if {i['id']for i in selection_report['instances']}!=raw_ids:raise ValueError('Native-verified selection coverage differs')
    # Keep the historical logical coordinate frame to preserve existing saves.
    # These are inspection bounds, not original world limits or spawn data.
    old=json.loads((geometry/'base/maps/tutorial-preview.json').read_text())
    profile={'format':'oc2-scene-collision-v2','sources':shapes,'instances':instances,
             'query':{'forwardMargin':struct.unpack('<f',struct.pack('<f',.05))[0],
                      'stepProbeCap':.5,'wallNormalYThreshold':.5,'stepProbeMultiplier':3.5},
             'coordinateFrame':{'min':old['bounds']['min'],'max':old['bounds']['max'],'width':1280,'height':1280},
             'sourceWindow':terrain['bounds'],'sourceMovement':'a878c0-grounded-only',
             'selection':selection,'settings':selection_report['settings'],'sourcesProof':sources.proofs,
             'gaps':['Actual actor state and complete airborne/water/landing branches are not restored.',
                     'Geometric ray/shape intersections remain a browser/server adapter, not the original collision virtual methods.',
                     'Six source trees have collision data but their original material is still unsupported.']}
    (output/'collision.json').write_text(json.dumps(profile,ensure_ascii=False,separators=(',',':')))
    report={'instances':len(instances),'sourceModels':len(shapes),'shapes':sum(len(v['shapes'])for v in shapes.values()),
            'simplifiedFilesPresent':0,'type15InsideInstances':0,'sourceDetailLow2':dict(flags),
            'originalCode':['a61030','a85cb0','a862a4','a878c0','a883a4','a8752c','363b9c','3394b4','90c610'],
            'lightingChanged':False,'automaticContinuation':'PAUSED','gaps':profile['gaps']}
    (output/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,default=DEFAULT_SOURCE)
    p.add_argument('--geometry',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(build(a.source,a.geometry,a.output),ensure_ascii=False))
