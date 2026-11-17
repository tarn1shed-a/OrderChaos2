"""Original cold clock/RNG/controller inputs; standard-library dependencies only.

Caller supplies actual gettimeofday values and the verified libc-scope flag.
No new clock/RNG, actor, queue, VM, resource, equipment or ready signal is made.
"""
import hashlib
import struct

NATIVE='77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4'

def checked_timeval(value):
    if not isinstance(value,(list,tuple)) or len(value)!=2 or any(type(v)is not int for v in value) or not 0<=value[0]<=0x7fffffff or not 0<=value[1]<1000000:
        raise ValueError('Actual caller gettimeofday seconds/microseconds required')
    return tuple(value)

def checked_source(engine):
    if hashlib.sha256(engine.image.data).hexdigest()!=NATIVE:
        raise ValueError('Original verified native library required')

def _scope(engine,name):
    if name not in ('human_active','body_active') or not hasattr(engine,name) or type(getattr(engine,name))is not bool:
        raise ValueError('Explicit already-verified libc callback scope required')
    return getattr(engine,name)

def original_cold_clock_rng(engine,timevals,*,active_attribute):
    checked_source(engine)
    if not isinstance(timevals,(list,tuple)) or len(timevals)!=2:
        raise ValueError('Both actual original gettimeofday call inputs required')
    values=[checked_timeval(v)for v in timevals]
    if any(getattr(engine,n,{}) for n in ('humans','bindings','actors')):
        raise ValueError('Original cold initializer must precede every actor')
    previous=_scope(engine,active_attribute);setattr(engine,active_attribute,True)
    try:
        engine.set_timeval(values[0]);engine.original_fragment(0x39911c,0x39918c)
        engine.set_timeval(values[1]);engine.original_fragment(0x39918c,0x3991d0)
    finally:
        setattr(engine,active_attribute,previous)
    rng=bytes(engine.uc.mem_read(0x2528410,32));origin=bytes(engine.uc.mem_read(0x2528140,8))
    return {'rng':rng,'origin':origin,'receipt':{
        'format':'oc2-native-cold-clock-rng-v1','coldProducer':'39911c..3991d0 (original3990dc ctor)',
        'originalClockGetter':'3a9050','actualTimevals':[list(v)for v in values],
        'initialRNGSHA256':hashlib.sha256(rng).hexdigest(),'originalOriginMs':struct.unpack('<Q',origin)[0],
        'originalNativeSHA256':NATIVE,'sourceValuesFromOriginalProducer':True,
        'qaConfiguredRandomWordsAdmittedAsInitialState':False,'fullOriginalTimerFactoryOrAppClaimed':False}}

def original_clock_origin_only(engine,timeval,*,active_attribute):
    checked_source(engine);value=checked_timeval(timeval);previous=_scope(engine,active_attribute)
    before=bytes(engine.uc.mem_read(0x2528410,32));setattr(engine,active_attribute,True)
    try:
        engine.set_timeval(value);engine.original_fragment(0x3992d8,0x39931c)
    finally:
        setattr(engine,active_attribute,previous)
    if before!=bytes(engine.uc.mem_read(0x2528410,32)):
        raise ValueError('Original origin-only fragment unexpectedly changed RNG')
    return {'originalEntry':'3992d8..39931c','actualTimeval':list(value),
        'originalOriginMs':engine.r(0x2528140,'Q')[0],'originalRNGUnchanged':True}

def original_filter_cold(engine):
    checked_source(engine);target=0x2544581
    sections=[s for s in engine.image.elf.iter_sections()if s['sh_addr']<=target<s['sh_addr']+s['sh_size']]
    segments=[s for s in engine.image.elf.iter_segments()if s['p_type']=='PT_LOAD'and s['p_vaddr']<=target<s['p_vaddr']+s['p_memsz']]
    if len(sections)!=1 or sections[0]['sh_type']!='SHT_NOBITS' or len(segments)!=1 or target<segments[0]['p_vaddr']+segments[0]['p_filesz'] or engine.r(target,'B')[0]!=0:
        raise ValueError('Original ELF cold filter storage differs; no update was supplied')
    return {'value':0,'source':'ELF .bss SHT_NOBITS beyond PT_LOAD file data',
        'unknownUpdateAdmitted':False,'nativeFieldWrittenByHelper':False}

def original_setting_cold(engine):
    checked_source(engine)
    if any(getattr(engine,n,{}) for n in ('humans','bindings','actors')):
        raise ValueError('Original cold setting constructor must precede every actor')
    if engine.image.read(0x1dfecdc,4).hex()!='00007ac4':
        raise ValueError('Original setting sentinel changed')
    previous=engine.r(0x2528e18,'Q')[0];address=engine.alloc(0x40)
    engine.call(0x37ce68,{'X0':address})
    if engine.r(0x2528e18,'Q')[0]!=address or engine.r(address+0x34,'I')[0]!=0xc47a0000:
        raise ValueError('Original37ce68 controller publication differs')
    return {'address':address,'originalConstructor':'37ce68','word34':engine.r(address+0x34,'I')[0],
        'double8':engine.r(address+8,'d')[0],'oldSuppliedStorageReplaced':address!=previous,
        'unknownUpdateAdmitted':False,'fullWorldOrUIReadyClaimed':False}
