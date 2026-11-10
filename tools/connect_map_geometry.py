"""Connect source map geometry in a separate ignored inspection page only."""
import argparse
import json
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def replace_once(text,old,new):
    if text.count(old)!=1:raise ValueError('Viewer differs from the inspected geometry entry; refusing a guessed edit')
    return text.replace(old,new)


def connect(runtime,geometry):
    runtime,geometry=Path(runtime).resolve(),Path(geometry).resolve()
    if any(not p.is_relative_to((ROOT/'analysis/raw').resolve())for p in (runtime,geometry)):
        raise ValueError('Only ignored inspection outputs may be changed')
    public=runtime/'prototype/public';assets=runtime/'game-data/converted'
    if assets.is_symlink():raise ValueError('Detach preview assets from backup before connecting')
    audit=json.loads((geometry/'geometry-audit.json').read_text())
    for name in audit['addedAssetFiles']:
        if name in ('manifest.json','maps/terrain-materials.json','rendering/terrain-lighting.json'):continue
        target=assets/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(geometry/'base'/name,target)
    shutil.copytree(geometry/'verified',assets/'geometry-map',dirs_exist_ok=True)
    shutil.copyfile(ROOT/'tools/preview/source-map-geometry.js',public/'source-map-geometry.js')
    terrain=(public/'terrain-materials.js').read_text()
    terrain=replace_once(terrain,"from './terrain-lighting.js'","from './terrain-lighting-window.js?geometry=2'")
    terrain="import {sourceTileVertex,sourceLayerColor as originalLayerColor} from './source-map-geometry.js?geometry=2';\n"+terrain
    begin=terrain.index('export function sourceLayerColor(');end=terrain.index('export function tileGeometry(',begin)
    terrain=terrain[:begin]+'export const sourceLayerColor=originalLayerColor;\n'+terrain[end:]
    terrain=replace_once(terrain,'const positions=[],normals=[],uv=[],maskUV=[],indices=[],groups=new Map();',
        "const positions=[],normals=[],uv=[],maskUV=[],colors=[],indices=[],groups=new Map();\n  const nativeTile=terrain.sourceTiles?.find(t=>t.tile[0]===tx&&t.tile[1]===tz);")
    old='const i=((tz-oz)*64+z)*w+(tx-ox)*64+x,p=terrain.positions.slice(i*3,i*3+3),n=terrain.normals.slice(i*3,i*3+3),coords=sourceUV(x,z);'
    new="const i=((tz-oz)*64+z)*w+(tx-ox)*64+x,source=nativeTile?sourceTileVertex(nativeTile,x,z):null;\n    const p=source?source.position:terrain.positions.slice(i*3,i*3+3),n=source?source.normal:terrain.normals.slice(i*3,i*3+3),coords=sourceUV(x,z);\n    colors.push(...(source?.color||[255,255,255,255]));"
    terrain=replace_once(terrain,old,new)
    terrain=replace_once(terrain,"geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));",
        "geometry.setAttribute('terrainSourceColor',new THREE.Uint8BufferAttribute(colors,4,true));\n  geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));")
    terrain=replace_once(terrain,'for(const chunk of tile.chunks){','for(const chunk of tile.chunks){\n    if(chunk.sourceWaterPending===true)continue;')
    terrain=replace_once(terrain,"if(!terrain.sourceVertexColorSummary?.white16)throw new Error('此地形的原顶点颜色尚未接入');",
        "if(!terrain.sourceVertexColorSummary?.white16&&!terrain.sourceTiles)throw new Error('原地形顶点颜色缺失');")
    (public/'terrain-materials-window.js').write_text(terrain)
    lighting=(public/'terrain-lighting.js').read_text()
    lighting="import {sourceLayerShader} from './source-map-geometry.js?geometry=2';\n"+lighting
    lighting=replace_once(lighting,"profile.vertexColor?.source!=='RGB565'||!finite(profile.vertexColor.current,4)||profile.vertexColor.current.some(v=>v!==255)||",
        "profile.vertexColor?.source!=='RGB565'||(profile.vertexColor.mode!=='per-source-tile'&&(!finite(profile.vertexColor.current,4)||profile.vertexColor.current.some(v=>v!==255)))||")
    lighting=replace_once(lighting,"row.runtimeFlags.some(v=>!Number.isSafeInteger(v)||v<0||v>0xffffffff||(v&0x10000))||\n      row.waterClearedByTileMinimumBound!==true||",
        "row.runtimeFlags.some((v,i)=>!Number.isSafeInteger(v)||v<0||v>0xffffffff||Boolean(v&0x10000)!==Boolean(source.chunks[i].sourceWaterPending))||\n      (row.waterClearedByTileMinimumBound!==true&&c.sourceGeometryWindow!==true)||")
    lighting=replace_once(lighting,'attribute vec2 terrainMaskUV;','attribute vec2 terrainMaskUV;\nattribute vec4 terrainSourceColor;')
    lighting=replace_once(lighting,'toneGain=mix(sourceToneFar,sourceToneNear,tone);','toneGain=mix(sourceToneFar,sourceToneNear,tone)*terrainSourceColor.rgb;')
    lighting=replace_once(lighting,"||layers[0]<0||textures.length!==5", "||layers.every(v=>v<0)||textures.length!==5")
    start=lighting.index("  let mix='vec4 weights=");end=lighting.index('  const material=',start)
    lighting=lighting[:start]+'  const mix=sourceLayerShader(layers);\n'+lighting[end:]
    (public/'terrain-lighting-window.js').write_text(lighting)
    js=(public/'explore-default.js').read_text()
    js=replace_once(js,"from './terrain-materials.js'","from './terrain-materials-window.js?geometry=2'")
    js=replace_once(js,"assets = await json(sourceProfile?`/assets/verified/${sourceProfile}/manifest.json`:'/assets/manifest.json');",
                    "assets = await json('/assets/geometry-map/manifest.json');")
    js=replace_once(js,'terrainMeshes=await createSourceTerrain(THREE,terrainData,terrainMaterials,origin,texture,',
        "const renderTerrain=await json(assets.mapWindow.url);\n    canvas.dataset.sourceGeometryWindow=JSON.stringify({tiles:renderTerrain.sourceTiles.length,vertexColors:renderTerrain.sourceVertexColorSummary.unique16,actorCoordinateFrame:'historical-nine-tile-frame-preserved',pendingWaterChunks:terrainMaterials.tiles.flatMap(t=>t.chunks).filter(c=>c.sourceWaterPending).length});\n    terrainMeshes=await createSourceTerrain(THREE,renderTerrain,terrainMaterials,origin,texture,")
    js=replace_once(js,'obj.matrix.fromArray(mesh.sourceNodeTransform.matrix);obj.matrix.decompose(obj.position,obj.quaternion,obj.scale);',
        'obj.matrix.fromArray(mesh.sourceNodeTransform.matrix);obj.matrixAutoUpdate=false;obj.matrixWorldNeedsUpdate=true;')
    js=js.replace("document.title='原 APK 默认配置 · 材质与光照核对';","document.title='原新手地图 · 地形与模型核对';")
    (public/'explore-map.js').write_text(js)
    html=replace_once((public/'explore-default.html').read_text(),'/explore-default.js?audit=5','/explore-map.js?geometry=2')
    html=html.replace('真实新手地图 3×3 地块；可换装玩家精灵、狼与熊；接入 39 个原作场景摆放。已恢复场景节点与静态PHY碰撞；地表混合材质及完整物理引擎尚未恢复。',
        '原地形展示范围 5×5 地块，接入 211 条原摆放。六棵针叶树的材质及部分水面待恢复；移动与碰撞仍使用历史九块测试范围。')
    (public/'explore-map.html').write_text(html)
    return {'tiles':audit['tileCount'],'modelsParsed':audit['modelCount'],
            'instancesDisplayed':audit['preview']['displayedInstances'],'pendingWaterChunks':audit['pendingWaterChunks'],
            'lightingSettingsChanged':False,'newServer':False}


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--runtime',type=Path,required=True);cli.add_argument('--geometry',type=Path,required=True)
    args=cli.parse_args();print(json.dumps(connect(args.runtime,args.geometry)))
