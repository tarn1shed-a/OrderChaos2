"""Connect the bounded source walk/collision branch only to explore-map rooms."""
import argparse
import json
import shutil
from pathlib import Path
from connect_map_geometry import replace_once
from tutorial_map_geometry import ROOT,local_output


def connect(runtime,evidence):
    runtime,evidence=local_output(runtime),local_output(evidence)
    p=runtime/'prototype';assets=runtime/'game-data/converted'
    if assets.is_symlink():raise ValueError('Detach inspection assets from backups first')
    if not (evidence/'collision.json').is_file():raise ValueError('Source collision export missing')
    shutil.copyfile(evidence/'collision.json',assets/'maps/window-collision.json')
    for name in ['source-height.js','source-walk.js']:shutil.copyfile(ROOT/'tools/preview'/name,p/'public'/name)
    shutil.copyfile(ROOT/'tools/preview/source-window-collision.mjs',p/'game/source-window-collision.mjs')
    world=(p/'public/world.js').read_text()
    old='return x >= r && y >= r && x <= world.width - r && y <= world.height - r &&'
    new='return x >= (world.bounds?.minX??0)+r && y >= (world.bounds?.minY??0)+r && x <= (world.bounds?.maxX??world.width)-r && y <= (world.bounds?.maxY??world.height)-r &&'
    if old in world:(p/'public/world.js').write_text(replace_once(world,old,new))
    server=(p/'server.mjs').read_text()
    if 'mapWindowMotion'not in server:
        server="import {loadSourceWindowCollision}from'./game/source-window-collision.mjs';\n"+server
        server=replace_once(server,'motion=loadCollision(), navigation=loadNavigation()',
                           'motion=loadCollision(), mapWindowMotion=loadSourceWindowCollision(), navigation=loadNavigation()')
        server=replace_once(server,"const world = scene === 'resources' ? RESOURCE_WORLD : WORLD;",
            "const sourceWindow=scene==='resources'&&msg.mapWindow==='tutorial';\n        if(msg.mapWindow!==undefined&&!sourceWindow)return reject(ws,'未知地图范围');\n        if(sourceWindow&&!mapWindowMotion)return reject(ws,'原地图碰撞资料未就绪');\n        const selectedMotion=sourceWindow?mapWindowMotion:motion;\n        const world = sourceWindow?mapWindowMotion.world:scene === 'resources' ? RESOURCE_WORLD : WORLD;")
        server=replace_once(server,"`resources:${lab?'lab:':''}${roomId}`","`resources:${sourceWindow?'source-map:':lab?'lab:':''}${roomId}`")
        server=replace_once(server,'notice,gameplay,motion,navigation,contextualLoot,ai,casting,lab',
            'notice,gameplay,motion:selectedMotion,navigation:sourceWindow?null:navigation,contextualLoot,ai:sourceWindow?false:ai,casting,lab')
        (p/'server.mjs').write_text(server)
    server=(p/'server.mjs').read_text()
    if '这个原地图预览尚未恢复腾空与落地'not in server:
        server=replace_once(server,"if(typeof msg.pressed!=='boolean')return reject(ws,'无效跳跃输入');",
            "if(typeof msg.pressed!=='boolean')return reject(ws,'无效跳跃输入');\n        if(ws.world.sourceCollisionWindow)return notice(ws,'这个原地图预览尚未恢复腾空与落地');")
        (p/'server.mjs').write_text(server)
    js=(p/'public/explore-map.js').read_text()
    if "mapWindow:'tutorial'"not in js:
        js=replace_once(js,"scene: 'resources', name, room,","scene: 'resources', mapWindow:'tutorial', name, room,")
        js=replace_once(js,"canvas.dataset.sourceGeometryWindow=JSON.stringify({tiles:","canvas.dataset.sourceWalk='original-grounded-branch;host-intersections;airborne-incomplete';\n    canvas.dataset.sourceGeometryWindow=JSON.stringify({tiles:")
        js=replace_once(js,"actorCoordinateFrame:'historical-nine-tile-frame-preserved'","actorCoordinateFrame:'historical-frame-preserved-with-25-source-tile-bounds'")
        # Read-only diagnostic attributes do not create a new game interface.
        js=replace_once(js,"a.label.dataset.grounded=String(p.grounded??true);",
            "a.label.dataset.grounded=String(p.grounded??true);a.label.dataset.logicalX=String(p.x);a.label.dataset.logicalY=String(p.y);")
        (p/'public/explore-map.js').write_text(js)
    js=(p/'public/explore-map.js').read_text()
    if "$('asset-detail').textContent = assets.summary;"in js:
        js=replace_once(js,"$('asset-detail').textContent = assets.summary;",
            "$('asset-detail').textContent = '原地形25块、原摆放211条；217条实例的原静态碰撞资料已接入。普通行走分支已核对，完整物理和水面仍待恢复。';")
        (p/'public/explore-map.js').write_text(js)
    html=(p/'public/explore-map.html').read_text().replace('/explore-map.js?geometry=2','/explore-map.js?geometry=3')
    html=html.replace('移动与碰撞仍使用历史九块测试范围。','普通行走和原静态碰撞已扩到25块；水面、腾空与完整落地流程仍待恢复。')
    (p/'public/explore-map.html').write_text(html)
    return {'sourceWindowOnly':True,'originalSaveFramePreserved':True,'lightingChanged':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True)
    a=p.parse_args();print(json.dumps(connect(a.runtime,a.evidence)))
