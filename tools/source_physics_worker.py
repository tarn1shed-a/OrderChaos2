"""Private stdin/stdout bridge to original static-scene ARM64 physics.

The configuration is local server state, never a browser-provided path or code.
"""
import json
import hashlib
import sys
from pathlib import Path
from source_physics import SourcePhysics
from analyze_native_resources import NativeImage,NATIVE_SHA256
from map_loading_evidence import Sources


def start(config):
    p=Path(config).resolve();root=Path(__file__).resolve().parents[1]
    if not p.is_relative_to(root/'analysis/raw'):raise ValueError('Native physics configuration must stay in the ignored inspection runtime')
    cfg=json.loads(p.read_text())
    if cfg['nativeSHA256']!=NATIVE_SHA256:raise ValueError('Physics configuration identifies another original build')
    image=NativeImage(Path(cfg['library']).read_bytes())
    if cfg.get('layerQueue'):
        if not all(cfg.get(k)for k in ['stopQueue','animationBlending','diving','shoreTransitions']):raise ValueError('Layer queue requires verified stop/blend/shore/diving inputs')
        from source_layer_queue import SourceLayerQueue
        engine_type=SourceLayerQueue
    elif cfg.get('stopQueue'):
        if not all(cfg.get(k)for k in ['animationBlending','diving','shoreTransitions']):raise ValueError('Stop queue requires original blending/shore/diving inputs')
        from source_stop_queue import SourceStopQueue
        engine_type=SourceStopQueue
    elif cfg.get('animationBlending'):
        if not cfg.get('diving')or not cfg.get('shoreTransitions'):raise ValueError('Animation binding requires original shore/diving inputs')
        from source_animation_blending import SourceAnimationBlending
        engine_type=SourceAnimationBlending
    elif cfg.get('shoreTransitions'):
        if not cfg.get('diving'):raise ValueError('Shore binding requires original diving inputs')
        from source_shore import SourceShore
        engine_type=SourceShore
    elif cfg.get('diving'):
        from source_diving import SourceDiving
        engine_type=SourceDiving
    elif cfg.get('swimming'):
        from source_swimming import SourceSwimming
        engine_type=SourceSwimming
    else:engine_type=SourcePhysics
    if cfg.get('nativeArchiveStream'):
        from native_phy_stream import NativePHYStreamMixin
        engine_type=type('SourceArchiveStreamPhysics',(NativePHYStreamMixin,engine_type),{})
    engine=engine_type(image)
    terrain=json.loads(Path(cfg['terrain']).read_text());profile=json.loads(Path(cfg['collision']).read_text())
    lights=json.loads(Path(cfg['terrainLighting']).read_text());flags={tuple(r['tile']):r['runtimeFlags']for r in lights['tiles']}
    if cfg.get('sourceFiles'):
        def read_source(name):
            item=cfg['sourceFiles'][name];raw=Path(item['path']).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=item['sha256']:raise ValueError('Private PHY digest differs: '+name)
            return raw
    else:read_source=Sources(Path(cfg['source'])).read
    summary=engine.load_world(terrain,profile,read_source,flags)
    if cfg.get('swimming'):summary.update(engine.load_water(json.loads(Path(cfg['swimming']).read_text())))
    if cfg.get('diving'):summary.update(engine.load_diving(json.loads(Path(cfg['diving']).read_text())))
    if cfg.get('shoreTransitions'):summary.update(engine.load_shore())
    if cfg.get('animationBlending'):summary.update(engine.load_animation_blending(json.loads(Path(cfg['animationBlending']).read_text())))
    if cfg.get('stopQueue'):summary.update(engine.load_stop_queue(json.loads(Path(cfg['stopQueue']).read_text())))
    if cfg.get('layerQueue'):summary.update(engine.load_layer_queue(json.loads(Path(cfg['layerQueue']).read_text())))
    for line in sys.stdin:
        try:
            q=json.loads(line);op=q['operation'];data=q.get('data',{})
            if op=='init':result={**summary,'nativeSHA256':cfg['nativeSHA256'],'sourceNative':True,'bounds':terrain['bounds'],'frame':profile['coordinateFrame']}
            elif op=='ground':result=engine.ground(*data['point'])
            elif op=='sample':result=engine.sample(*data['point'])
            elif op=='reset':
                identity=data['identity'];position=data['position']
                if identity in engine.actors:del engine.actors[identity]
                engine.actor(identity,position);result=True
            elif op=='tick':
                args=[data['identity'],data['position'],data['velocity'],data['milliseconds'],data['jump']]
                result=engine.actor_tick(*args,control=data.get('control'))if cfg.get('diving')else engine.actor_tick(*args)
            elif op=='restore-height'and cfg.get('diving'):result=engine.restore_height(data['point'])
            elif op=='ray':result=engine.ray(data['from'],data['to'],data.get('capsule',False))
            elif op=='forget':engine.actors.pop(data['identity'],None);result=True
            else:raise ValueError('Unsupported physics bridge operation')
            print(json.dumps({'result':result},allow_nan=False,separators=(',',':')),flush=True)
        except Exception as e:
            # Fail the current request explicitly; never switch to prototype physics.
            print(json.dumps({'error':str(e)},ensure_ascii=False),flush=True)


if __name__=='__main__':start(sys.argv[1])
