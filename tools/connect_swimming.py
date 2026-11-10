"""Connect verified surface swimming and camera water parameters locally only."""
import argparse
import json
import shutil
from pathlib import Path
from tutorial_map_geometry import ROOT,local_output
from connect_map_geometry import replace_once


def connect(runtime,export):
    runtime,export=map(local_output,(runtime,export));public=runtime/'prototype/public';assets=runtime/'game-data/converted'
    if assets.is_symlink():raise ValueError('Detach the isolated art directory first')
    js=(public/'explore-map.js').read_text();js=replace_once(js,"json('/assets/geometry-water-floor/manifest.json')","json('/assets/source-swimming/manifest.json')")
    js="import{sourceCameraWater,cameraWaterLight}from'./source-swimming-camera.js?swim=1';\nlet sourceSwimmingProfile=null;\n"+js
    js=replace_once(js,"'./character-animation.js'","'./character-animation-swimming.js?swim=1'")
    js=replace_once(js,"from'./source-terrain-water.js?water=1'","from'./source-terrain-water-swimming.js?swim=1'")
    js=replace_once(js,"from'./source-water-floor.js?floor=1'","from'./source-water-floor-swimming.js?swim=1'")
    js=replace_once(js,'    canvas.dataset.sourceWaterFloor=JSON.stringify(sourceWaterFloor.state());',
        '    canvas.dataset.sourceWaterFloor=JSON.stringify(sourceWaterFloor.state());\n    sourceSwimmingProfile=await json(assets.sourceSwimming.url);')
    js=replace_once(js,'  sourceWaterFloor?.update();',"  sourceWaterFloor?.update();\n  if(sourceSwimmingProfile){const state=sourceCameraWater(sourceSwimmingProfile.tiles,[camera.position.x+origin.x,camera.position.y+origin.y,camera.position.z+origin.z]),common=cameraWaterLight(bakedLighting,environment);sourceWater.setCamera(state,common);sourceWaterFloor.setCamera(state,common);canvas.dataset.sourceCameraWater=JSON.stringify(state);canvas.dataset.sourceWaterTechnique=sourceWater.state().technique;}")
    js=replace_once(js,'水下地表和远景补色层已按原文件接入，原游泳仍待恢复。','水下地表与普通水域游动已接入；潜水和完整原相机仍待核对。')
    js=replace_once(js,"a.label.dataset.worldY=String(p.worldY??'');","a.label.dataset.swimming=String(p.swimming===true);a.label.dataset.waterState=String(p.waterState??0);a.label.dataset.worldY=String(p.worldY??'');")
    animation=(ROOT/'tools/preview/source-swim-animation.js').read_text()
    water=(public/'source-terrain-water.js').read_text()
    water=replace_once(water,'  const choice=profile?.selection;',"  const under=profile?.swimmingEffects?.Terrain_Water;if(!under||under.some(p=>p.equationGL!==0x8006||JSON.stringify(p.factorsGL)!=='[1,770]'||p.sameAlphaFactors!==true))throw Error('原水下混合状态尚未核对');\n  const choice=profile?.selection;")
    water=replace_once(water,'  const started=performance.now();let elapsed=0;',"  const power=await sampler(profile.swimmingPowerTable,false);\n  for(const m of materials)Object.assign(m.uniforms,{global_powerTable:{value:power},global_camera_water_color:{value:new THREE.Vector3()},under_water_color:{value:new THREE.Vector3()},waterFactor:{value:0}});\n  const started=performance.now();let elapsed=0;")
    water=replace_once(water,'return {roots,update(now){',"return {roots,setCamera(state,common){for(const m of materials){const active=Boolean(m.defines?.UNDER_WATER);if(active!==state.underwater){m.defines=state.underwater?{UNDER_WATER:1}:{};m.blendSrc=m.blendSrcAlpha=state.underwater?THREE.OneFactor:THREE.SrcAlphaFactor;m.blendDst=m.blendDstAlpha=state.underwater?THREE.SrcAlphaFactor:THREE.OneMinusSrcAlphaFactor;m.needsUpdate=true;}m.uniforms.global_camera_water_color.value.fromArray(state.attenuation.map((v,i)=>Math.fround(v*common[i])));m.uniforms.under_water_color.value.fromArray(state.color.map((v,i)=>Math.fround(v*common[i])));m.uniforms.waterFactor.value=state.factor;}},update(now){")
    water=replace_once(water,"effect:31,technique:'default',","effect:31,technique:materials.some(m=>m.defines?.UNDER_WATER)?'under_water':'default',")
    water=replace_once(water,'swimmingRestored:false','surfaceSwimmingRestored:true,fullSwimmingRestored:false')
    floor=(public/'source-water-floor.js').read_text()
    floor=replace_once(floor,'return{roots,update(){',"return{roots,setCamera(state,common){for(const m of materials){m.uniforms.global_camera_water_depth.value=state.depth;m.uniforms.global_camera_water_depth_vs.value=state.depth;m.uniforms.global_camera_water_color.value.fromArray(state.attenuation.map((v,i)=>Math.fround(v*common[i])));}for(const r of roots)for(const m of r.children)if(m.renderOrder===-1)m.visible=!state.underwater;},update(){")
    floor=replace_once(floor,'swimmingRestored:false','surfaceSwimmingRestored:true,fullSwimmingRestored:false')
    # Extend the same source-water profile by reference, preserving its old namespace.
    manifest=json.loads((export/'manifest.json').read_text());swimming=json.loads((export/'swimming.json').read_text())
    waterprofile=json.loads((assets/manifest['terrainWater']['url'].removeprefix('/assets/')).read_text());waterprofile['swimmingPowerTable']=swimming['powerTable'];waterprofile['swimmingEffects']=swimming['effects']
    manifest['terrainWater']['url']='/assets/source-swimming/terrain-water.json'
    profilefiles={p.name:p.read_bytes()for p in export.iterdir()if p.is_file()}
    profilefiles['manifest.json']=json.dumps(manifest,separators=(',',':')).encode();profilefiles['terrain-water.json']=json.dumps(waterprofile,separators=(',',':')).encode()
    for name,data in profilefiles.items():
        dest=assets/'source-swimming'/name
        if dest.exists()and dest.read_bytes()!=data:raise ValueError('Preserve previous swimming assets')
    native=(runtime/'prototype/game/native-window-collision.mjs').read_text()
    native=replace_once(native,'entity.sourcePosture=result.lastPosture;entity.sourceVelocityY=result.velocityY;',
        'entity.sourcePosture=result.lastPosture;entity.sourceVelocityY=result.velocityY;entity.swimming=result.swimming===true;entity.waterState=result.waterState;entity.waterHeight=result.waterHeight;')
    native=replace_once(native,'jump:control.request','jump:control.request&&!entity.swimming')
    html=replace_once((public/'explore-map.html').read_text(),'/explore-map.js?water-floor=1','/explore-map.js?swimming=1')
    cfg=json.loads((runtime/'prototype/native-physics.json').read_text());cfg['swimming']=str(export/'water-native-metadata.json')
    for name,data in profilefiles.items():
        dest=assets/'source-swimming'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    for name,data in [('explore-map.js',js),('character-animation-swimming.js',animation),('source-terrain-water-swimming.js',water),('source-water-floor-swimming.js',floor)]:
        (public/name).write_text(data)
    shutil.copyfile(ROOT/'tools/preview/source-swimming-camera.js',public/'source-swimming-camera.js')
    (runtime/'prototype/game/native-window-collision.mjs').write_text(native)
    (runtime/'prototype/native-physics.json').write_text(json.dumps(cfg,indent=2)+'\n')
    (public/'explore-map.html').write_text(html)
    return {'swimming':True,'originalNormalWaterCPU':True,'fullOriginalCameraRig':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--export',type=Path,required=True);a=p.parse_args();print(json.dumps(connect(a.runtime,a.export)))
