"""Connect the checked forward-dive/camera CPU branch to an isolated swimming preview."""
import json
from pathlib import Path
from tutorial_map_geometry import ROOT,local_output
from connect_map_geometry import replace_once


def connect(runtime,export):
    runtime,export=map(local_output,(runtime,export))
    assets=runtime/'game-data/converted'
    if assets.is_symlink():raise ValueError('Detach isolated assets before connecting')
    profile=json.loads((export/'profile.json').read_text())
    if profile.get('format')!='oc2-source-diving-camera-v1':raise ValueError('Unknown source camera profile')
    public=runtime/'prototype/public';js=(public/'explore-map.js').read_text()
    js="import{createSourceCameraInput,applySourceCamera}from'./source-diving-controls.js';\nconst sourceCameraInput=createSourceCameraInput();\n"+js
    js=replace_once(js,"if (pointer.button === 2 || e.pointerType === 'touch') { azimuth -= dx * .006; elevation = THREE.MathUtils.clamp(elevation + dy * .005, .18, 1.35); pointer.x = e.clientX; pointer.y = e.clientY; }",
        "if (pointer.button === 0 || pointer.button === 2 || e.pointerType === 'touch') { sourceCameraInput.rotate(dx,dy); pointer.x = e.clientX; pointer.y = e.clientY; }")
    js=replace_once(js,"distance = THREE.MathUtils.clamp(distance * Math.exp(e.deltaY * .001), 4, 160);","sourceCameraInput.zoom(e.deltaY);")
    js=replace_once(js,"send({type:'input',x,y});","send({type:'input',x,y,...sourceCameraInput.packet(back<0&&Math.abs(right)<1e-6,camera.near)});")
    camera_start="  camera.position.copy(focus).add(new THREE.Vector3(Math.sin(azimuth)*Math.cos(elevation)*distance,Math.sin(elevation)*distance,Math.cos(azimuth)*Math.cos(elevation)*distance));camera.lookAt(focus);"
    camera_end="  if(camera.position.y<surface+1.5){camera.position.y=surface+1.5;camera.lookAt(focus);}"
    js=replace_once(js,camera_start,"  const nativeCamera=snapshot.find(p=>p.id===selfId)?.sourceCamera;\n  if(nativeCamera){applySourceCamera(THREE,camera,origin,nativeCamera);azimuth=nativeCamera.yaw*Math.PI/180;canvas.dataset.sourceCameraControl=JSON.stringify(nativeCamera);}else{\n"+camera_start)
    js=replace_once(js,camera_end,camera_end+"\n  }")
    js=replace_once(js,"a.label.dataset.swimming=String(p.swimming===true);","a.label.dataset.submerged=String(p.submerged===true);a.label.dataset.swimming=String(p.swimming===true);")
    js=replace_once(js,'水下地表与普通水域游动已接入；潜水和完整原相机仍待核对。','原前游潜水与普通相机CPU已接入；完整触控、动画分派和水下角色材质仍待核对。')
    html=replace_once((public/'explore-map.html').read_text(),'/explore-map.js?swimming=1','/explore-map.js?diving=1')
    native=(runtime/'prototype/game/native-window-collision.mjs').read_text()
    native=replace_once(native,"jump:control.request&&!entity.swimming}","jump:control.request&&!entity.swimming,...(info.sourceCameraCPU?{control:{...(control.camera||{}),forward:input.sourceForward===true}}:{})}")
    native=replace_once(native,"control.request=false;pending.set(entity,control);","control.request=false;delete control.camera;pending.set(entity,control);")
    native=replace_once(native,'entity.sourcePosture=result.lastPosture;',"entity.submerged=result.submerged===true;if(result.camera)entity.sourceCamera=result.camera;entity.sourcePosture=result.lastPosture;")
    native=replace_once(native,'    if(!result.grounded){','    if(entity.swimming){entity.jump=null;}else if(!result.grounded){')
    native=replace_once(native,'return {sourceNative:true,world,point,',"return {sourceNative:true,sourceCameraCPU:info.sourceCameraCPU===true,world,point,\n    restoreHeight:(entity,height)=>{const p=point(entity.x,entity.y);entity.worldY=rpc.request('restore-height',{point:[p.x,height,p.z]}).height;initialized.delete(entity);},\n    cameraInput:(entity,value)=>{if(!info.sourceCameraCPU)return;const keys=['yawDelta','pitchDelta','distanceScale','near'];if(!value||typeof value!=='object'||keys.some(k=>!Number.isFinite(value[k]))||Object.keys(value).length!==4||Math.abs(value.yawDelta)>1000||Math.abs(value.pitchDelta)>1000||value.distanceScale<.01||value.distanceScale>100||value.near<=0||value.near>1)throw Error('无效镜头输入');const state=pending.get(entity)||{pressed:false,request:false},old=state.camera||{yawDelta:0,pitchDelta:0,distanceScale:1},next={yawDelta:old.yawDelta+value.yawDelta,pitchDelta:old.pitchDelta+value.pitchDelta,distanceScale:old.distanceScale*value.distanceScale,near:value.near};if(Math.abs(next.yawDelta)>1000||Math.abs(next.pitchDelta)>1000||next.distanceScale<.01||next.distanceScale>100)throw Error('镜头输入累计超限');state.camera=next;pending.set(entity,state);},")
    server=(runtime/'prototype/server.mjs').read_text()
    server=replace_once(server,'const p=ws.motion.point(ws.player.x,ws.player.y);ws.player.worldY=ws.motion.support(p.x,p.z,position.groundY+ws.motion.step);',
        'if(ws.motion.sourceCameraCPU)ws.motion.restoreHeight(ws.player,position.groundY);else{const p=ws.motion.point(ws.player.x,ws.player.y);ws.player.worldY=ws.motion.support(p.x,p.z,position.groundY+ws.motion.step);}')
    server=replace_once(server,'ws.input = { x: msg.x, y: msg.y }; ws.inputAt = Date.now();',
        "if(msg.sourceForward!==undefined&&typeof msg.sourceForward!=='boolean')return reject(ws,'无效前游输入');if(msg.sourceCamera!==undefined){try{ws.motion?.cameraInput?.(ws.player,msg.sourceCamera);}catch{return reject(ws,'无效镜头输入');}}ws.input = { x: msg.x, y: msg.y,sourceForward:msg.sourceForward===true }; ws.inputAt = Date.now();")
    store=replace_once((runtime/'prototype/game/character-store.mjs').read_text(),'player.grounded&&Number.isFinite(player.worldY)','(player.grounded||player.swimming===true)&&Number.isFinite(player.worldY)')
    cfg=json.loads((runtime/'prototype/native-physics.json').read_text());cfg['diving']=str(export/'profile.json')
    outputs={'prototype/public/explore-map.js':js,'prototype/public/explore-map.html':html,
        'prototype/public/source-diving-controls.js':(ROOT/'tools/preview/source-diving-controls.js').read_text(),
        'prototype/game/native-window-collision.mjs':native,'prototype/server.mjs':server,'prototype/game/character-store.mjs':store,
        'prototype/native-physics.json':json.dumps(cfg,indent=2)+'\n',
        'game-data/converted/source-diving-controls/profile.json':json.dumps(profile,separators=(',',':'))}
    for name,data in outputs.items():
        p=runtime/name
        if name.startswith('game-data/')and p.exists()and p.read_text()!=data:raise ValueError('Preserve existing camera profile')
    for name,data in outputs.items():
        p=runtime/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(data)
    return {'sourceForwardDive':True,'sourceCameraCPU':True,'fullOriginalTouchAndAnimation':False,'files':len(outputs)}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--export',type=Path,required=True);a=p.parse_args()
    print(json.dumps(connect(a.runtime,a.export)))
