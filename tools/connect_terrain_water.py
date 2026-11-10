"""Connect source water to the existing ignored 251-tile inspection page."""
import argparse
import json
import shutil
from pathlib import Path
from tutorial_map_geometry import ROOT,local_output
from connect_map_geometry import replace_once


def connect(runtime,water):
    runtime,water=map(local_output,(runtime,water));assets=runtime/'game-data/converted';p=runtime/'prototype';public=p/'public'
    if assets.is_symlink():raise ValueError('Detach preview assets from backup before connecting')
    audit=json.loads((water/'water-audit.json').read_text());js=(public/'explore-map.js').read_text()
    js=replace_once(js,"json('/assets/geometry-missing-terrain/manifest.json')","json('/assets/geometry-water/manifest.json')")
    js="import{createSourceWater}from'./source-terrain-water.js?water=1';\nlet sourceWater=null;\n"+js
    js=replace_once(js,'scene.add(...terrainMeshes);canvas.dataset.terrainMaterials=terrainMaterials.format;',
        "scene.add(...terrainMeshes);\n    sourceWater=await createSourceWater(THREE,await json(assets.terrainWater.url),origin,texture,async url=>{const r=await fetch(url);if(!r.ok)throw Error('原水面程序缺失');return r.text();},bakedLighting,environment);\n    for(const root of sourceWater.roots){scene.add(root);archiveObjects.push({root,tile:root.userData.sourceTile});}\n    canvas.dataset.sourceWater=JSON.stringify(sourceWater.state());\n    canvas.dataset.terrainMaterials=terrainMaterials.format;")
    js=replace_once(js,'  hdrRenderer.render(scene,camera,zone);',
        '  sourceWater?.update(now);\n  hdrRenderer.render(scene,camera,zone);')
    begin=js.index("    $('asset-detail').textContent = '");end=js.index(';',begin)
    js=js[:begin]+f"    $('asset-detail').textContent = '251块原地形资料；{audit['waterChunks']}个原水面区块接入明确的原着色分支，原游泳与水下流程仍待恢复。'"+js[end:]
    for source in water.iterdir():
        if not source.is_file()or source.name=='water-audit.json':continue
        dest=assets/'geometry-water'/source.name
        if dest.exists()and dest.read_bytes()!=source.read_bytes():raise ValueError('Preserve existing water assets: '+str(dest))
    for source in water.iterdir():
        if source.is_file()and source.name!='water-audit.json':
            dest=assets/'geometry-water'/source.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
    shutil.copyfile(ROOT/'tools/preview/source-terrain-water.js',public/'source-terrain-water.js')
    cfg=json.loads((p/'native-physics.json').read_text());cfg['terrainLighting']=str(water/'terrain-lighting.json')
    (p/'native-physics.json').write_text(json.dumps(cfg,indent=2)+'\n');(public/'explore-map.js').write_text(js)
    html=replace_once((public/'explore-map.html').read_text(),'/explore-map.js?terrain-missing=1','/explore-map.js?water=1')
    (public/'explore-map.html').write_text(html)
    return {k:v for k,v in audit.items()if k not in ['nativeProofs','sources']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--water',type=Path,required=True)
    x=p.parse_args();print(json.dumps(connect(x.runtime,x.water)))
