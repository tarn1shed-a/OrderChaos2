"""Bounded original post-relocation direction and camera-yaw caller slices.

Decoded direction vectors, normal Hero host and loaded static scene are explicit
fixtures, not a received EnterMap or escape reply. No original special-queue/UI
branch is replaced with a success provider; those ranges are not executed.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
from tutorial_reentry_reset_probe import ROOT,DEFAULT_CONFIG,COURTYARD,ROOF,WATER,state,evidence_output


def load_engine(config):
    from analyze_native_resources import NativeImage,NATIVE_SHA256
    from native_phy_stream import NativePHYStreamMixin
    from source_layer_queue import SourceLayerQueue
    cfg=json.loads(Path(config).read_text());raw=Path(cfg['library']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=NATIVE_SHA256 or cfg['nativeSHA256']!=NATIVE_SHA256:
        raise ValueError('Original native identity differs')
    image=NativeImage(raw)
    class CallerProbe(NativePHYStreamMixin,SourceLayerQueue):
        def hook(self,uc,at,size,data):
            name=self.imports.get(at)
            if name in ('atan2','atan2f'):
                if name=='atan2':self.df('D0',math.atan2(self.gd('D0'),self.gd('D1')))
                else:self.sf('S0',math.atan2(self.gf('S0'),self.gf('S1')))
                self.set('PC',self.get('X30'));return
            return super().hook(uc,at,size,data)
    engine=CallerProbe(image);checked=set()
    def read(name):
        row=cfg['sourceFiles'][name];value=Path(row['path']).read_bytes()
        if hashlib.sha256(value).hexdigest()!=row['sha256']:raise ValueError('Original PHY differs: '+name)
        checked.add(name);return value
    terrain=json.loads(Path(cfg['terrain']).read_text());coll=json.loads(Path(cfg['collision']).read_text())
    light=json.loads(Path(cfg['terrainLighting']).read_text())
    loaded=engine.load_world(terrain,coll,read,{tuple(r['tile']):r['runtimeFlags']for r in light['tiles']})
    engine.load_water(json.loads(Path(cfg['swimming']).read_text()));engine.load_diving(json.loads(Path(cfg['diving']).read_text()))
    engine.load_shore();engine.load_animation_blending(json.loads(Path(cfg['animationBlending']).read_text()))
    engine.load_stop_queue(json.loads(Path(cfg['stopQueue']).read_text()));engine.load_layer_queue(json.loads(Path(cfg['layerQueue']).read_text()))
    rels={r['r_offset']:r['r_addend']for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
    for slot,entry in ((0x40,0xa2b7d8),(0x68,0xa0902c),(0x448,0xa0e3ac)):
        if rels.get(0x24228a8+slot)!=entry:raise ValueError('Original Hero caller virtual slot differs')
    return engine,image,{'nativeSHA256':NATIVE_SHA256,'sourceFilesChecked':len(checked),'loaded':loaded}


def view(engine,actor):
    a=actor['address'];c=actor['camera']
    return {**state(engine,actor),'headingDirection140':list(engine.r(a+0x140,'3f')),
        'pendingHeading174':list(engine.r(a+0x174,'3f')),'headingRadians188':list(engine.r(a+0x188,'2f')),
        'cameraYaw68':engine.r(c+0x68,'f')[0],'cameraPitch6c':engine.r(c+0x6c,'f')[0],
        'cameraDirty18c':engine.r(c+0x18c,'B')[0],'cameraByte2a9':engine.r(c+0x2a9,'B')[0]}


def analyze(config=DEFAULT_CONFIG):
    from unicorn import UC_HOOK_CODE
    engine,image,identity=load_engine(config);cases=[]
    for scenario,direction in [('fall-minus-z',[0,0,-1]),('dive-plus-x',[1,0,0]),('dive-diagonal',[3,0,4])]:
        name='reentry-caller-'+scenario;is_fall=scenario.startswith('fall');position=(ROOF if is_fall else WATER)[:]
        for i in range(261 if is_fall else 30):
            control=None if is_fall else{'forward':True,'pitchDelta':-40 if i==0 else 0,'yawDelta':-90 if i==0 else 0}
            frame=engine.actor_tick(name,position,[0,4.8]if is_fall else[4.8,0],50,False,control)
            position=frame['position']
        actor=engine.actors[name];a=actor['address'];vt=engine.r(a,'Q')[0]
        engine.w(vt+0x40,'Q',0xa2b7d8);engine.w(vt+0x68,'Q',0xa0902c)
        root=engine.r(0x2528db0,'Q')[0];engine.w(root+0x278,'I',5)
        before=view(engine,actor);point=engine.alloc(12);engine.w(point,'3f',*COURTYARD)
        engine.call(0x9037d4,{'X0':a,'X1':point,'X2':0,'X3':0});after_relocation=view(engine,actor)
        manager=engine.alloc(0x100);location=engine.alloc(0x50);vector=engine.alloc(0x28)
        engine.w(manager+0x68,'Q',a);engine.w(location+0x18,'Q',vector);engine.w(vector+0x10,'3f',*direction)
        # Exact original post-v448 caller: reads decoded direction, uses the
        # verified Hero virtual+40, and supplies W2=-1/W3=0 itself.
        entries=[]
        def direction_entry(uc,at,size,data):
            entries.append({'entry':hex(at),'modeW2':engine.get('W2'),'flagsW3':engine.get('W3'),
                'direction':list(engine.r(engine.get('X1'),'3f'))})
        hook=engine.uc.hook_add(UC_HOOK_CODE,direction_entry,begin=0xa2b7d8,end=0xa2b7d8)
        try:engine.fragment(0xa356d0,{0xa3571c},{'X19':manager,'X25':location})
        finally:engine.uc.hook_del(hook)
        after_direction=view(engine,actor)
        # Separately execute the later camera slice. The intervening e20/UI
        # branch is NOT executed; do not call these two slices a full frame.
        engine.fragment(0xa3574c,{0xa35814},{'X25':location,'X26':0x2528000})
        after_camera=view(engine,actor)
        cases.append({'scenario':scenario,'explicitDecodedDirection':direction,'lastPreparationFrame':frame,
            'before':before,'afterFullHeroRelocation':after_relocation,'afterDirectionCaller':after_direction,
            'afterCameraCaller':after_camera,'sourceCallerSlices':[['0xa356d0','0xa3571c'],['0xa3574c','0xa35814']],
            'actualDirectionConsumerEntries':entries,
            'interveningSpecialQueueAndUIExecuted':False,'realOriginalEnterMapReceived':False})
    pins=[]
    for at in (0xa2b7d8,0xa34f28):
        routine,_=image.routine(at);size=routine['size'];pins.append({'address':hex(at),'size':size,'sha256':hashlib.sha256(image.read(at,size)).hexdigest()})
    return {'format':'oc2-reentry-postrelocation-caller-v1','identity':identity,'cases':cases,'nativeRoutines':pins,
        'limits':['Decoded direction input and actor/container remain explicit fixtures, not original server fields observed at runtime.',
                  'Original virtual+40 and camera ranges execute; intervening special queue cleanup/UI/config branches do not.',
                  'atan2/atan2f use the standard libc ABI host binding; native branch and float stores remain original.',
                  'No support/spawn/escape rule follows from heading or camera math.'],
        'scope':{'originalServerEscapeDestinationKnown':False,'wholeEnterMapRestored':False,'cameraLifecycleFullyRestored':False,
                 'saveReadOrModified':False,'sharedRuntimeModified':False,'original127Changed':False,'published':False}}


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--config',type=Path,default=DEFAULT_CONFIG)
    cli.add_argument('--output',type=Path,required=True);args=cli.parse_args();output=evidence_output(args.output)
    report=analyze(args.config);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'output':str(output),'cases':len(report['cases']),'changedSaveOrRuntime':False}))
