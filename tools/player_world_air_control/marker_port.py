"""Original per-track marker reader bound to the existing scalar time control.

The scalar loaded-track view is explicit. No model/GPU/cache success is claimed.
Original BRES fixups, marker object construction, callback setters, interval
selection, actor marker consumer and selected-record refcounts remain native.
"""
import struct
from player_world_air_control.bres_port import SameVMBresPort


def prepare_bank(engine,animation):
    from unicorn import UC_HOOK_CODE
    port=SameVMBresPort(engine);engine.bank_port=port
    handles=[engine.uc.hook_add(UC_HOOK_CODE,engine.hook,begin=at,end=at)for at in port.POINTS]
    engine.original_bank_io_active=True
    try:loaded=port.load(animation.b)
    finally:
        engine.original_bank_io_active=False
        for handle in handles:engine.uc.hook_del(handle)
    if loaded['successByte']!=1:raise ValueError('Original own BRES marker byte load failed')
    info=loaded['info'];relative=engine.r(info+0x48,'i')[0]
    engine.own_marker_source=info+0x48+relative if relative else 0
    engine.own_marker_load={'nativeReader':'148daa8','main':loaded['main'],'info':info,'markerSource':engine.own_marker_source,'modelOrGPUReady':False,'byteReads':port.events}
    engine.marker_bindings=[];engine.marker_events=[]
    for at in (0x9188dc,):engine.uc.hook_add(UC_HOOK_CODE,engine.hook,begin=at,end=at)


def publish_selected(engine,uc):
    sp=engine.get('SP');channel=engine.get('W20');record=bytes(uc.mem_read(sp+0x60,0x58));name=record[:64].split(b'\0')[0].decode()
    provider=struct.unpack_from('<Q',record,0x50)[0]
    if provider:
        vt,_,fn,actor,deleter=engine.r(provider,'5Q')
        if vt!=0x240db50 or fn!=0x9188dc or actor!=engine.active_human['actor']['address'] or deleter!=0:
            raise ValueError('Unknown original actor marker provider')
    if (channel,name)not in engine.prepared:raise ValueError('Own scalar track not prepared')
    engine.publishing[channel]=engine.prepared[channel,name]
    engine.set('PC',0x32f16c)


def bind_marker(engine,q,selected,channel):
    provider=struct.unpack_from('<Q',selected,0x50)[0]
    callback=engine.r(0x240db30+channel*8,'Q')[0]if provider else 0
    if callback not in (0,0x32b290,0x32b2e0):raise ValueError('Original channel marker callback differs')
    carrier=engine.alloc(0x90)
    engine.original_fragment(0x118a468,0x118a4fc,{'X19':carrier,'X20':engine.own_marker_source})
    marker=engine.r(carrier+0x30,'Q')[0];control=q['control']
    engine.call(0x11968cc,{'X0':control,'X1':callback,'X2':q['engine']if callback else 0})
    engine.call(0x1361c30,{'X0':marker,'X1':callback,'X2':q['engine']if callback else 0})
    engine.call(0x1196850,{'X0':control,'X1':marker})
    if engine.r(control+0x48,'Q')[0]!=marker or engine.r(marker+0x48,'Q')[0]!=engine.own_marker_source:raise ValueError('Original marker/time control binding differs')
    q['current']['markerPort']=True
    engine.marker_bindings.append({'channel':channel,'clip':selected[:64].split(b'\0')[0].decode(),'provider':provider,'marker':marker,'control':control,'callback':callback,'context':q['engine']if callback else 0,'source':engine.own_marker_source,'originalConstructorsAndSetters':True})
