"""Original GS2C_Error warning consumption and Map_GetMapInfo output fixtures.

This extends the frozen first BreakAway batch without editing its five files.
It never supplies original server results, moving/combat eligibility, real local
time keys, a destination or a live map. ARM64 parsing/dispatch/property assembly
execute; localization, initial string and AS property services are boundaries.
"""
import argparse
import hashlib
import json
from pathlib import Path
from original_unstuck_probe import UnstuckProbe
from tutorial_map_geometry import local_output

PINS={0x58c7f8:(2732,'b767e37a9642bdcdf29629984747d34e6691864ad4465a88a312ba0e2eaab790')}
DESCRIPTOR=(0x2028b85,62,'9efa389aeca6e72214c1d8c9ab49278d96e0e6ddc3e701141e0d657648f97411')

def source_map_type(source):
    from map_loading_evidence import Sources
    from skill_attachments import decode_ftable
    from optimized_abc import extract_named_abc,parse_abc
    s=Sources(source);row=next(r for r in decode_ftable(s.read('tables/map_info.tbl'),'map_id')['rows']if r['map_id']==5)
    raw=extract_named_abc(s.read('ui/Flash/mainUI.swf'),'Common/ASDefines')
    if hashlib.sha256(raw).hexdigest()!='e52412f677339cb3abb773e85a7eb0f6dae60af95ba93ff480dd1b2e94745889':raise ValueError('Original ASDefines block differs')
    a=parse_abc(raw);c=next(c for c in a['classes']if c['name']=='Common::ASDefines')
    constants={v['name']:a['ints'][v['value']]for v in c['staticTraits']if 'MAP_INFO_TYPE_'in v['name']and v.get('valueKind')==3}
    return {'sourceRow':row,'constants':constants,'proofs':s.proofs,'currentRuntimeMapTypeSupplied':False}

class UnstuckInputsProbe(UnstuckProbe):
    def __init__(self,image):
        from unicorn import UC_HOOK_CODE
        from native_combat import descriptor_fields
        for a,(n,h)in PINS.items():
            if hashlib.sha256(image.read(a,n)).hexdigest()!=h:raise ValueError('Original error consumer differs')
        a,n,h=DESCRIPTOR;raw=image.read(a,n)
        if hashlib.sha256(raw).hexdigest()!=h:raise ValueError('Original error descriptor differs')
        self.schema=descriptor_fields(raw)
        if self.schema['name']!='GS2C_Error':raise ValueError('Original message differs')
        super().__init__(image);self.mode=None;self.texts=[];self.parses=[];self.properties=[]
        for a in(0x1de639c,0x1ab7060,0xfc2b30,0xfc6148,0x103849c,0x1036890):self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=a,end=a)
        self.w(0x2528e08,'Q',self.alloc(0x6000))
    def hook(self,uc,a,n,d):
        if self.mode=='error'and a==0x1ab7060:
            self.parses.append({'source':hex(a),'bytes':self.get('W2'),'hex':bytes(uc.mem_read(self.get('X1'),self.get('W2'))).hex()});return
        if self.mode=='error'and a==0x1de639c:
            # Initial empty string allocation is outside the error decision.
            self.w(self.get('X0'),'Q',self.alloc(32));self.set('PC',self.get('X30'));return
        if self.mode=='error'and a==0x3ddd7c:self.texts.append(self.get('W0'));self.set('PC',self.EXIT);return
        if self.mode=='map'and a==0xfc2b30:self.w(self.get('X0'),'B',0)
        elif self.mode=='map'and a==0xfc6148:uc.mem_write(self.get('X0'),bytes(uc.mem_read(self.get('X2'),self.get('W1'))))
        elif self.mode=='map'and a==0x103849c:
            key=self.get('X1');value=self.get('X2')
            if self.r(key,'B')[0]==255:raise ValueError('Unexpected heap AS key fixture')
            if self.r(value,'B')[0]!=2:raise ValueError('Unexpected native AS value type')
            self.properties.append({'name':self.cstr(key+1).decode(),'type':2,'number':self.r(value+8,'d')[0]})
        elif self.mode=='map'and a==0x1036890:pass
        else:return super().hook(uc,a,n,d)
        self.set('PC',self.get('X30'))
    def error(self,code):
        if type(code)is not int or not 0<=code<=0x7fffffff:raise ValueError('Explicit nonnegative int32 err_code fixture required')
        self.mode='error';self.texts=[];self.parses=[]
        v=code;body=b'\x08'
        while v>127:body+=bytes([(v&127)|128]);v>>=7
        body+=bytes([v]);raw=len(body).to_bytes(4,'little')+body
        p=self.alloc(0x40);b=self.alloc(len(raw));self.uc.mem_write(b,raw);self.w(p+0x20,'2Q',b,b+len(raw))
        self.w(self.root+0x63,'B',1);self.w(self.root+0x68,'I',0x12345678);self.w(self.root+0x6c,'B',1)
        self.call(0x58c7f8,{'X1':p})
        return {'errCodeFixture':code,'actualOriginalParse':list(self.parses),'sourceTextLookupStop':list(self.texts),'context63':self.r(self.root+0x63,'B')[0],'context68':self.r(self.root+0x68,'I')[0],'context6c':self.r(self.root+0x6c,'B')[0],'movingOrCombatProducerSupplied':False,'originalServerReplySupplied':False,'warningTextLookupBoundaryOnly':True}
    def map_info(self,*,map_key,map_type,found=True):
        if type(map_key)is not int or not 0<=map_key<=0xffffffff or type(map_type)is not int or not 0<=map_type<=0xffffffff or type(found)is not bool:raise ValueError('Explicit uint32 map/table-type and bool row fixtures required')
        self.mode='map';self.properties=[];self.lookups=[];self.map_type=map_type;self.map_found=found
        self.w(self.root+0x278,'I',map_key);arg=self.alloc(24);self.w(arg,'B',5);vector=self.alloc(8);self.w(vector,'Q',arg);call=self.alloc(0x30);self.w(call+0x18,'Q',vector);self.w(call+0x20,'Q',1)
        self.call(0x6f0edc,{'X0':call})
        return {'mapKeyFixture':map_key,'tableTypeFixture':map_type,'rowFoundFixture':found,'nativeCallback':'0x6f0edc','mapLookups':list(self.lookups),'originalASProperties':list(self.properties),'tableReadBoundary':'Original source row type supplied at native map-row+8; table manager/row constructor are explicit boundaries.','currentRuntimeStateRecovered':False}

def run(image,source):
    e=UnstuckInputsProbe(image);m=source_map_type(source)
    return {'format':'oc2-original-unstuck-inputs-v1','schema':e.schema,'warning':e.error(0xa023),'control':e.error(0xa022),'mapSource':m,'map5ASProperty':e.map_info(map_key=5,map_type=m['sourceRow']['type']),'mapMissing':e.map_info(map_key=5,map_type=2,found=False),'timerBoundaryCases':[e.timer(now=100000,saved=v)for v in(None,98201,98200,100001,101800)],'limits':['Error codes are explicit test packets; no actual original server error is asserted.','0xa023 clears the pending context flag and requests4780, but does not reveal the server moving/combat eligibility algorithm.','Map5 static type2 plus actual callback emits mapType2 from a supplied source-row fixture; original activity and full table manager initialization remain unknown.','Original time arithmetic is measured only, not installed as a gameplay cooldown.'],'gameSaveOrTransportChanged':False}

if __name__=='__main__':
    from analyze_native_resources import NativeImage
    from resource_packs import DEFAULT_SOURCE
    c=argparse.ArgumentParser(description=__doc__);c.add_argument('--library',type=Path,required=True);c.add_argument('--source',type=Path,default=DEFAULT_SOURCE);c.add_argument('--output',type=Path,required=True);a=c.parse_args();o=local_output(a.output);o.parent.mkdir(parents=True,exist_ok=True);r=run(NativeImage(a.library.read_bytes()),a.source);o.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'output':str(o),'warning':r['warning']['sourceTextLookupStop'],'map5':r['map5ASProperty']['originalASProperties']}))
