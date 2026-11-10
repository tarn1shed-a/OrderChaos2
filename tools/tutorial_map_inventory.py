"""Archive-wide source geometry inventory; no replacement art or runtime policy.

This is a local evidence export, not a claim that every archived tile is active,
walkable, displayed, or resident at once in the original client.
"""
import argparse
import collections
import hashlib
import json
import tempfile
from pathlib import Path
from bdae_convert import BDAE
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from scene_collision import apply_scene_transforms,decode_phy
from terrain_convert import read_instances
from terrain_materials import tile_materials,mask_channels,effective_indices
from tutorial_map_geometry import ROOT,local_output,source_coordinates,raw_tile


def inventory(source,output):
    output=local_output(output)
    if output.exists():raise ValueError('Preserve existing evidence; choose a fresh directory')
    output.mkdir(parents=True);s=Sources(source);tiles=[];instances=[];gaps=[];models=[]
    def save(name,value):
        p=output/name;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False))
    with tempfile.TemporaryDirectory(prefix='oc2-tutorial-atlas-')as temp:
        p=Path(temp)/'original.bdae'
        for x,z in source_coordinates(s):
            stem=f'{x:04d}_{z:04d}';name=f'world/tutorial/terrain/{stem}.trn';raw=s.read(name)
            tile=raw_tile(raw,x,z);m=tile_materials(raw)
            masks=[f'world/tutorial/layers/{stem}_{i}.msk'for i in range(4)]
            _,classes=mask_channels([s.read(n)if s.candidates(n)else None for n in masks])
            used={i for chunk,c in zip(m['chunks'],classes)for i in effective_indices(chunk['indices'],c)if i>=0}
            missing=[n for i,n in enumerate(m['textures'])if i in used and not s.candidates(n)]
            if missing:gaps.append({'tile':[x,z],'missingReferencedTerrainTextures':missing,
                                    'scope':'absent from indexed download packs; not replaced'})
            save('terrain/'+stem+'.json',{**tile,'source':name,'material':m,
                 'maskFiles':[n for n in masks if s.candidates(n)],'missingReferencedTextures':missing})
            tiles.append({'tile':[x,z],'source':name,'geometry':'terrain/'+stem+'.json','textures':m['textures']})
            itm=f'world/tutorial/items/{stem}.itm'
            if s.candidates(itm):p.write_bytes(s.read(itm));instances+=read_instances(p)
        for name in sorted({i['model']for i in instances}):
            entry={'source':name,'types':sorted({i['sourceType']for i in instances if i['model']==name})}
            try:
                raw=s.read(name)
                if name.endswith('.bdae'):
                    p.write_bytes(raw);reader=BDAE(p);data=apply_scene_transforms(reader,reader.parse())
                    dest='models/'+hashlib.sha256(raw).hexdigest()+'.json';save(dest,data)
                    entry.update(geometry=dest,meshes=len(data['meshes']),
                        vertices=sum(m['vertexCount']for m in data['meshes']),
                        triangles=sum(m['triangleCount']for m in data['meshes']),
                        scope='original mesh and node data only; material/runtime factory still separate')
                else:entry['scope']='source effect reference; not treated as a static BDAE mesh'
                phy=name.removesuffix('.bdae')+'.phy'
                if name.endswith('.bdae')and s.candidates(phy):
                    shape=decode_phy(s.read(phy));dest='collision/'+hashlib.sha256(s.read(phy)).hexdigest()+'.json'
                    save(dest,shape);entry['availablePHY']={'source':phy,'decoded':dest,
                        'scope':'file availability, not final type/mode-selected collision'}
            except ValueError as error:
                entry['gap']=str(error);gaps.append({'model':name,'gap':str(error)})
            models.append(entry)
    save('instances.json',instances)
    # Run original pre-creation selection separately. It does not complete the
    # type8 effect or type15 inside factory merely by returning admission.
    save('selection-input/terrain.json',{'tileOrigin':[min(t['tile'][0]for t in tiles),min(t['tile'][1]for t in tiles)],
         'tileCount':[max(t['tile'][0]for t in tiles)-min(t['tile'][0]for t in tiles)+1,
                      max(t['tile'][1]for t in tiles)-min(t['tile'][1]for t in tiles)+1],
         'sourceTextures':[{'tile':t['tile'],'textures':t['textures']}for t in tiles],
         'sourceTiles':[{k:v for k,v in json.loads((output/t['geometry']).read_text()).items()
                         if k in ('tile','heights','normals','colors')}for t in tiles]})
    save('selection-input/manifest.json',{'map':{'url':'/assets/terrain.json'}})
    from analyze_native_resources import NativeImage
    from tutorial_preview_selection import resolve
    from map_selection_evidence import DEFAULT_APK
    report,_=resolve(NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes()),
                     source,DEFAULT_APK,'APK_Default',output/'selection-input')
    save('selection.json',report)
    summary={'tiles':len(tiles),'instances':len(instances),'references':len(models),
        'BDAEReferences':sum(n['source'].endswith('.bdae')for n in models),
        'decodedBDAE':sum('geometry'in n for n in models),
        'types':dict(collections.Counter(i['sourceType']for i in instances)),
        'selection':dict(collections.Counter(i['admission']for i in report['instances'])),
        'missingTerrainTextureTiles':sum('missingReferencedTerrainTextures'in g for g in gaps),
        'gaps':gaps,'tileFiles':tiles,'modelFiles':models,'sources':s.proofs,
        'displayChanged':False,'lightingChanged':False,'automaticContinuation':'PAUSED',
        'scope':'all actual archived TRN/ITM data; no filled cells, substituted resources, spawn or live residency claim'}
    save('inventory.json',summary)
    return {k:summary[k]for k in ('tiles','instances','references','BDAEReferences','decodedBDAE','types','selection','missingTerrainTextureTiles')}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,default=DEFAULT_SOURCE)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print(json.dumps(inventory(a.source,a.output)))
