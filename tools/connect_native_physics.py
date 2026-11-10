"""Bind the original-ELF worker to the ignored map preview; no new listener."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path
from tutorial_map_geometry import ROOT,local_output
from resource_packs import DEFAULT_SOURCE
from connect_map_geometry import replace_once


def connect(runtime,geometry,collision):
    runtime,geometry,collision=map(local_output,(runtime,geometry,collision));p=runtime/'prototype'
    # Originals are server-private, outside the assets/public HTTP roots.
    from map_loading_evidence import Sources
    source=Sources(DEFAULT_SOURCE);private=runtime/'native-inputs';private.mkdir(exist_ok=True)
    library=private/'library.so';shutil.copyfile(ROOT/'analysis/raw/beff-native/library.so',library)
    source_files={}
    for name,item in json.loads((collision/'collision.json').read_text())['sources'].items():
        raw=source.read(name);digest=hashlib.sha256(raw).hexdigest()
        if digest!=item['sourceSHA256']:raise ValueError('Original PHY differs from collision evidence')
        target=private/(digest+'.phy');target.write_bytes(raw);source_files[name]={'path':str(target),'sha256':digest}
    cfg={'python':str(ROOT/'.venv/bin/python'),'worker':str(ROOT/'tools/source_physics_worker.py'),
         'config':str(p/'native-physics.json'),'library':str(library),'sourceFiles':source_files,
         'nativeSHA256':'77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4',
         'terrain':str(geometry/'base/maps/tutorial-window.json'),'collision':str(collision/'collision.json'),
         'terrainLighting':str(geometry/'verified/terrain-lighting.json'),'source':str(DEFAULT_SOURCE)}
    (p/'native-physics.json').write_text(json.dumps(cfg,indent=2)+'\n')
    for name in ['native-window-collision.mjs','native-physics-thread.mjs']:shutil.copyfile(ROOT/'tools/preview'/name,p/'game'/name)
    server=(p/'server.mjs').read_text()
    if "from'./game/native-window-collision.mjs'"not in server:
        server=replace_once(server,"import {loadSourceWindowCollision}from'./game/source-window-collision.mjs';",
            "import {loadNativeWindowCollision as loadSourceWindowCollision}from'./game/native-window-collision.mjs';")
        server=replace_once(server,"if(ws.world.sourceCollisionWindow)return notice(ws,'这个原地图预览尚未恢复腾空与落地');",
            "if(ws.motion?.sourceNative){ws.motion.jumpPressed(ws.player,msg.pressed);return;}")
        server=replace_once(server,"for(const ws of room.values())updateJump(ws,clock());",
            "for(const ws of room.values())if(!ws.motion?.sourceNative)updateJump(ws,clock());")
        server=replace_once(server,'await new Promise(resolve => server.close(resolve));',
            'await new Promise(resolve => server.close(resolve));\n          await mapWindowMotion?.close?.();')
        (p/'server.mjs').write_text(server)
    js=(p/'public/explore-map.js').read_text()
    js=js.replace('original-grounded-branch;host-intersections;airborne-incomplete','original-ARM64-static-physics;host-input-and-animation-binding')
    js=js.replace('原地形25块、原摆放211条；217条实例的原静态碰撞资料已接入。普通行走分支已核对，完整物理和水面仍待恢复。',
        '25块原地形、211条可显示原摆放；原静态碰撞及普通跳跃、下落、落地在隔离环境执行原指令。水面及原动画调度仍待恢复。')
    (p/'public/explore-map.js').write_text(js)
    html=(p/'public/explore-map.html').read_text().replace('/explore-map.js?geometry=3','/explore-map.js?geometry=4')
    html=html.replace('普通行走和原静态碰撞已扩到25块；水面、腾空与完整落地流程仍待恢复。',
        '25块原地图已接原静态碰撞及普通跳跃、下落、落地计算；水面和完整动作调度仍待恢复。')
    (p/'public/explore-map.html').write_text(html)
    return {'originalStaticQueries':True,'originalJumpFallLandingInstructions':True,'newListener':False,'lightingChanged':False,'automaticContinuation':'PAUSED'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--geometry',type=Path,required=True);p.add_argument('--collision',type=Path,required=True)
    a=p.parse_args();print(json.dumps(connect(a.runtime,a.geometry,a.collision)))
