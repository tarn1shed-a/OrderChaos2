"""Connect only the supported source archive subset in the ignored preview."""
import argparse
import json
import shutil
from pathlib import Path
from tutorial_map_geometry import ROOT,local_output
from connect_map_geometry import replace_once
from connect_native_physics import connect as connect_physics


def connect(runtime,geometry):
    runtime,geometry=map(local_output,(runtime,geometry));assets=runtime/'game-data/converted';p=runtime/'prototype';public=p/'public'
    if assets.is_symlink():raise ValueError('Detach asset directory from the backup first')
    audit=json.loads((geometry/'geometry-audit.json').read_text())
    for name in audit['addedAssetFiles']:
        if name in ('manifest.json','maps/terrain-materials.json','rendering/terrain-lighting.json'):continue
        dest=assets/name;dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists()and dest.read_bytes()!=(geometry/'base'/name).read_bytes():raise ValueError('Existing asset differs; preserve it: '+name)
        shutil.copyfile(geometry/'base'/name,dest)
    for src in(geometry/'verified').rglob('*'):
        if not src.is_file():continue
        dest=assets/'geometry-expanded'/src.relative_to(geometry/'verified')
        if dest.exists()and dest.read_bytes()!=src.read_bytes():raise ValueError('Existing expanded asset differs: '+str(dest))
    shutil.copytree(geometry/'verified',assets/'geometry-expanded',dirs_exist_ok=True)
    shutil.copyfile(ROOT/'tools/preview/source-archive-window.js',public/'source-archive-window.js')
    terrain=(public/'terrain-materials-window.js').read_text()
    terrain="import {validateSourceTileCoverage}from'./source-archive-window.js';\n"+terrain
    terrain=replace_once(terrain,"profile.tiles.length!==terrain.tileCount[0]*terrain.tileCount[1]","(terrain.sourceTiles?!validateSourceTileCoverage(terrain,profile):profile.tiles.length!==terrain.tileCount[0]*terrain.tileCount[1])")
    (public/'terrain-materials-expanded.js').write_text(terrain)
    js=(public/'explore-map.js').read_text()
    js="import {sourceArchiveWindow}from'./source-archive-window.js';\nimport {sourceTerrainSample}from'./source-height.js';\nlet archiveTerrain=null,archiveWindow=null;const archiveObjects=[];\n"+js
    js=replace_once(js,"from './terrain-materials-window.js?geometry=2'","from './terrain-materials-expanded.js?expansion=1'")
    js=replace_once(js,"json('/assets/geometry-map/manifest.json')","json('/assets/geometry-expanded/manifest.json')")
    js=replace_once(js,'function heightAt(x, z) {',
        "function heightAt(x, z) {\n  if(archiveTerrain){try{return sourceTerrainSample(archiveTerrain.sourceTiles,x,z).height;}catch(error){if(error instanceof RangeError)return NaN;throw error;}}")
    js=replace_once(js,'const renderTerrain=await json(assets.mapWindow.url);',
        'const renderTerrain=await json(assets.mapWindow.url);archiveTerrain=renderTerrain;\n    archiveWindow=sourceArchiveWindow(renderTerrain.sourceTiles.map(t=>t.tile),assets.mapWindow.originalRequestOffsets,assets.mapWindow.radius);')
    js=replace_once(js,'scene.add(...terrainMeshes);',
        "for(const root of terrainMeshes)archiveObjects.push({root,tile:root.userData.sourceTile});\n    scene.add(...terrainMeshes);")
    js=replace_once(js,'model.quaternion.fromArray(inst.quaternion); model.scale.fromArray(inst.scale); scene.add(model);',
        'model.quaternion.fromArray(inst.quaternion); model.scale.fromArray(inst.scale); scene.add(model);archiveObjects.push({root:model,tile:inst.tile});')
    js=replace_once(js,'const zone=environment.update(point.x+origin.x,point.z+origin.z,scene,Math.max(0,Math.floor(dt*1000)));',
        "const windowChange=archiveWindow?.update(point.x+origin.x,point.z+origin.z);\n  if(windowChange){for(const entry of archiveObjects)entry.root.visible=windowChange.resident.has(entry.tile.join(','));canvas.dataset.sourceArchiveWindow=JSON.stringify({center:windowChange.center,resident:[...windowChange.resident],scope:'original-offset-and-distance-branches;host-buffer-residency'});}\n  const zone=environment.update(point.x+origin.x,point.z+origin.z,scene,Math.max(0,Math.floor(dt*1000)));")
    js=js.replace('historical-frame-preserved-with-25-source-tile-bounds','historical-frame-preserved-with-explicit-archive-subset')
    start=js.index("    $('asset-detail').textContent = '");end=js.index(";",start)
    js=js[:start]+f"    $('asset-detail').textContent = '{audit['tileCount']}块有原贴图的地形、{audit['preview']['displayedInstances']}条已核对原摆放；其余材质、内部场景及水面仍有缺口。'"+js[end:]
    (public/'explore-map.js').write_text(js)
    html=(public/'explore-map.html').read_text().replace('/explore-map.js?geometry=4','/explore-map.js?expansion=1');(public/'explore-map.html').write_text(html)
    result=connect_physics(runtime,geometry,geometry/'physics')
    # The physics connector's default path is the old square export. Bind the
    # separately verified sparse atlas, preserving the old actor frame.
    cfg=json.loads((p/'native-physics.json').read_text());cfg['terrain']=str(geometry/'base/maps/expansion/tutorial-window.json')
    (p/'native-physics.json').write_text(json.dumps(cfg,indent=2)+'\n')
    return {**result,'tiles':audit['tileCount'],'displayedInstances':audit['preview']['displayedInstances'],'conditionalWindow':True}


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--runtime',type=Path,required=True);a.add_argument('--geometry',type=Path,required=True)
    x=a.parse_args();print(json.dumps(connect(x.runtime,x.geometry)))
