"""Attach verified floor/border data to the existing ignored map preview only."""
import argparse
import json
import shutil
from pathlib import Path
from tutorial_map_geometry import ROOT,local_output
from connect_map_geometry import replace_once


def connect(runtime,export):
    runtime,export=map(local_output,(runtime,export));public=runtime/'prototype/public';assets=runtime/'game-data/converted'
    if assets.is_symlink():raise ValueError('Preserve backup assets; detach the ignored preview first')
    js=(public/'explore-map.js').read_text()
    js=replace_once(js,"json('/assets/geometry-water/manifest.json')","json('/assets/geometry-water-floor/manifest.json')")
    js="import{createSourceWaterFloor}from'./source-water-floor.js?floor=1';\nlet sourceWaterFloor=null;\n"+js
    anchor='    canvas.dataset.sourceWater=JSON.stringify(sourceWater.state());'
    js=replace_once(js,anchor,anchor+"\n    sourceWaterFloor=await createSourceWaterFloor(THREE,await json(assets.terrainWaterFloor.url),renderTerrain,terrainMaterials,terrainLighting,origin,texture,async url=>{const r=await fetch(url);if(!r.ok)throw Error('原水下地表程序缺失');return r.text();},bakedLighting,environment);\n    for(const root of sourceWaterFloor.roots){scene.add(root);archiveObjects.push({root,tile:root.userData.sourceTile});}\n    canvas.dataset.sourceWaterFloor=JSON.stringify(sourceWaterFloor.state());")
    js=replace_once(js,'  sourceWater?.update(now);','  sourceWater?.update(now);\n  sourceWaterFloor?.update();')
    js=replace_once(js,'原游泳与水下流程仍待恢复。','水下地表和远景补色层已按原文件接入，原游泳仍待恢复。')
    html=replace_once((public/'explore-map.html').read_text(),'/explore-map.js?water=1','/explore-map.js?water-floor=1')
    for p in export.iterdir():
        if not p.is_file()or p.name=='audit.json':continue
        dest=assets/'geometry-water-floor'/p.name
        if dest.exists()and dest.read_bytes()!=p.read_bytes():raise ValueError('Preserve previous water-floor assets')
    for p in export.iterdir():
        if p.is_file()and p.name!='audit.json':
            dest=assets/'geometry-water-floor'/p.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    shutil.copyfile(ROOT/'tools/preview/source-water-floor.js',public/'source-water-floor.js')
    (public/'explore-map.js').write_text(js);(public/'explore-map.html').write_text(html)
    return json.loads((export/'audit.json').read_text())


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--export',type=Path,required=True)
    a=p.parse_args();print(json.dumps(connect(a.runtime,a.export)))
