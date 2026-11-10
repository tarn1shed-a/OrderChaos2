"""Expand the inspection preview using supported original archive content only.

Missing art is not replaced. Unknown inside/malformed-collision tiles remain
unavailable to walking in this inspection, not invented original barriers.
"""
import argparse
import json
from pathlib import Path
from tutorial_map_geometry import ROOT,local_output,build
from resource_packs import DEFAULT_SOURCE
from map_loading_evidence import Sources
from tutorial_walk_collision import phy_candidates
from scene_collision import decode_phy
from terrain_lighting import lightmap_requests,terrain_texture_encoding


def supported_tiles(source,atlas):
    sources=Sources(source);inventory=json.loads((Path(atlas)/'inventory.json').read_text())
    ready=[];gaps=[]
    for row in inventory['tileFiles']:
        data=json.loads((Path(atlas)/row['geometry']).read_text())
        try:
            if data['missingReferencedTextures']:raise ValueError('Missing terrain texture: '+','.join(data['missingReferencedTextures']))
            # All exported slots need actual files; do not assign a default PNG.
            for name in data['material']['textures']:
                if not sources.candidates(name):raise ValueError('Missing terrain texture slot: '+name)
            x,z=row['tile'];candidates=[p for p in lightmap_requests('tutorial',x,z)if sources.candidates(p)]
            if not candidates:raise ValueError('Original terrain lightmap absent')
            encoding=terrain_texture_encoding(sources.read(candidates[0]))
            if encoding['encoding']!='ETC1':raise ValueError('Unrecovered terrain lightmap encoding')
            ready.append(row['tile'])
        except ValueError as error:gaps.append({'tile':row['tile'],'reason':str(error)})
    return ready,gaps


def collision(source,geometry,output):
    output=local_output(output);output.mkdir(parents=True,exist_ok=True)
    if(output/'collision.json').exists():raise ValueError('Existing collision evidence preserved')
    s=Sources(source);manifest=json.loads((geometry/'base/manifest.json').read_text())
    terrain=json.loads((geometry/'base'/manifest['mapWindow']['url'].removeprefix('/assets/')).read_text())
    selection=json.loads((geometry/'verified/selection.json').read_text())
    old=json.loads((ROOT/'analysis/raw/walk-collision-20261111/final-export/collision.json').read_text())
    shapes={};instances=[];choices=[];no_files=[];gaps=[];unavailable=set()
    for r in selection['instances']:
        if r['admission']!='admittedBeforeTypeFactory':continue
        if r['sourceType']==15:
            unavailable.add(tuple(r['tile']));gaps.append({'id':r['id'],'tile':r['tile'],'reason':'inside factory/collision not restored'})
    names=sorted({r['model']for r in selection['instances']if r['sourceType']==2 and r['admission']=='admittedBeforeTypeFactory'})
    for name in names:
        rows=[r for r in selection['instances']if r['model']==name and r['sourceType']==2 and r['admission']=='admittedBeforeTypeFactory']
        small,normal=phy_candidates(name)
        try:
            if s.candidates(small):raise ValueError('Simplified PHY exists; active mode unresolved')
            if not s.candidates(normal):
                # a862a4 returns null when all supplied local providers miss.
                # Do not derive a collider from the displayed geometry.
                no_files.append({'model':name,'normal':normal,'simplified':small,'ids':[r['id']for r in rows],
                    'scope':'original null-provider branch under this explicit local archive set'})
                continue
            raw=s.read(normal);shape=decode_phy(raw);shapes[normal]=shape
            choices.append({'model':name,'selected':normal,'missingSimplified':small,'sourceSHA256':shape['sourceSHA256']})
            instances.extend({**r,'sourcePHY':normal}for r in rows)
        except ValueError as error:
            for r in rows:unavailable.add(tuple(r['tile']))
            gaps.append({'model':name,'ids':[r['id']for r in rows],'reason':str(error)})
    result={'format':'oc2-source-static-atlas-collision-v1','coordinateFrame':old['coordinateFrame'],
            'instances':instances,'sources':shapes,'selection':choices,'nullProviderFiles':no_files,
            'inspectionUnavailableTiles':[list(t)for t in sorted(unavailable)],'gaps':gaps,
            'sourceWindow':terrain['bounds'],'scope':'Explicit local static archive; source geometry/native queries. Not observed Android residency or original server.'}
    (output/'collision.json').write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')))
    return {'sourceModels':len(shapes),'instances':len(instances),'sourceShapes':sum(len(v['shapes'])for v in shapes.values()),
            'nullProviderModels':len(no_files),'inspectionUnavailableTiles':len(unavailable),'gaps':gaps}


def expand(source,atlas,legacy,output):
    from analyze_native_resources import NativeImage
    output=local_output(output);coordinates,gaps=supported_tiles(source,atlas)
    audit=build(NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes()),source,legacy,output,
                coordinates=coordinates,namespace='expansion')
    audit['archiveTileGaps']=gaps
    audit['collision']=collision(source,output,output/'physics')
    (output/'geometry-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
    return {'tiles':audit['tileCount'],'staticSourceInstances':audit['instanceCount'],
            'displayedInstances':audit['preview']['displayedInstances'],'omittedInstances':len(audit['preview']['omitted']),
            'physics':{k:v for k,v in audit['collision'].items()if k!='gaps'}}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--legacy',type=Path,required=True)
    p.add_argument('--atlas',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(expand(DEFAULT_SOURCE,a.atlas,a.legacy,a.output),ensure_ascii=False))
