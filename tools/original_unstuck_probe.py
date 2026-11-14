"""Execute the original BreakAway branches on explicit isolated input fixtures.

No Android process, network, game save, cooldown or destination is implemented.
Table/UI/clock/key-value services are recorded boundaries. The actual ARM64
callback, confirmation callback, packet construction and timer arithmetic run.
"""
import argparse
import hashlib
import json
from pathlib import Path
from source_physics import SourcePhysics
from tutorial_map_geometry import local_output

ROUTINES={
 0x7197e4:(396,'59babe041b8acef29c13ddfe12c8af1eace0ce0e284fa63cb2cadce7e5043569'),
 0x719970:(268,'6177683ca1a33d731d4b58194ad55e1c0c632f7b9e8f712b058797821d0ccf52'),
 0x5a4540:(288,'9c835ab2fae1214404ae8d4c864109748454f513fb08df85e458cea79e3a267e'),
 0x7984d0:(128,'d1f94fd58d3abadaa1ec491f06348c8ad0f9e31b94ddfee4ebcad356246a49c8'),
 0x48b858:(204,'ac427f9c73af9fafaa3fbe8f2754b41114dda0e12a98bf460e3a925a2540d182'),
}

class UnstuckProbe(SourcePhysics):
    TABLE=SourcePhysics.EXIT+0x1000
    UI=TABLE+4
    def __init__(self,image):
        from unicorn import UC_HOOK_CODE
        for a,(n,h)in ROUTINES.items():
            if hashlib.sha256(image.read(a,n)).hexdigest()!=h:raise ValueError('BreakAway source routine differs')
        super().__init__(image)
        self.uc.mem_map(self.TABLE&~4095,4096)
        self.root=self.alloc(0x800);self.net=self.alloc(0x300);self.sock=self.alloc(0x200);self.registry=self.alloc(0x100)
        self.w(0x2528db0,'Q',self.root);self.w(0x2528e30,'Q',self.net);self.w(0x2528df8,'Q',self.registry)
        self.w(self.net+8,'Q',self.sock);self.w(self.sock+0x15c,'B',1);self.w(self.sock+0xd8,'Q',1)
        self.table=self.alloc(0x40);tv=self.alloc(0x40);self.w(self.table,'Q',tv);self.w(tv+0x18,'Q',self.TABLE)
        self.ui=self.alloc(0x20);uv=self.alloc(0x100);self.w(self.ui,'Q',uv)
        self.w(uv+0x40,'Q',self.UI);self.w(uv+0x88,'Q',self.UI)
        self.w(0x2505c38,'Q',self.alloc(8))
        hooks=[self.TABLE,self.UI,0xc99270,0xc88aa8,0x3ddd7c,0x607a60,0x5dc9d4,0x6075bc,0x5dcbc4,
               0x3de09c,0x5033cc,0x64b928,0x39e034,0x406388,0x5802ec,0x3bb4b8,
               0x3f7c48,0xa79e38,0xa79a34,0xa7aaf4,0x1036c34,0x5a09f8,0xa35958]
        for a in hooks:self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=a,end=a)
        self.packets=[];self.confirmations=[];self.events=[];self.lookups=[];self.kv=[]
        self.map_type=0;self.map_found=True;self.now=100000;self.saved=None;self.answer=None;self.last_string=None

    def hook(self,uc,a,n,d):
        if a==0xa35958:self.set('PC',self.EXIT);return
        if a==0xc99270:self.set('X0',self.table)
        elif a==0xc88aa8:uc.mem_write(self.get('X0'),bytes(0xd0)) # map-row constructor boundary, no original row supplied
        elif a==self.TABLE:
            self.lookups.append(self.get('W1'));self.w(self.get('X2')+8,'I',self.map_type);self.set('W0',int(self.map_found))
        elif a==0x3ddd7c:
            self.last_string=self.get('W0');p=self.alloc(32);uc.mem_write(p,f'string-id-{self.last_string}'.encode()+b'\0');self.set('X0',p)
        elif a==0x607a60:self.confirmations.append({'textId':self.last_string,'constructorFlag':self.get('W2')})
        elif a==0x5dc9d4:self.confirmations[-1]['callback']=hex(self.r(self.get('X1')+8,'Q')[0])
        elif a==0x5dcbc4:self.confirmations[-1]['secondaryTextId']=self.last_string
        elif a==0x3de09c:self.set('X0',self.ui)
        elif a==0x64b928:self.events.append({'source':hex(a),'event':self.cstr(self.get('X1')).decode()})
        elif a==0x5802ec:
            p=self.get('X1');b,e=self.r(p+0x20,'2Q')
            if e<b or e-b>1024:raise ValueError('Unexpected original packet buffer')
            self.packets.append({'opcode':self.r(p,'H')[0],'payloadHex':bytes(uc.mem_read(b,e-b)).hex(),'bytes':e-b,'transportExecuted':False})
        elif a==0x3bb4b8:self.events.append({'source':hex(a),'text':self.cstr(self.get('X1')).decode()})
        elif a==0x3f7c48:self.set('X0',self.now)
        elif a==0xa79e38:
            key=self.cstr(self.get('X0')).decode();self.kv.append({'read':key,'fixture':self.saved})
            if self.saved is not None:uc.mem_write(self.get('X1'),str(self.saved).encode()+b'\0')
            self.set('W0',int(self.saved is not None))
        elif a==0xa79a34:self.kv.append({'write':self.cstr(self.get('X0')).decode(),'value':self.cstr(self.get('X1')).decode()})
        elif a==0x1036c34:self.answer=self.gd('D0')
        elif a==0x5a09f8:self.set('W0',0) # explicit unsynchronized clock fixture
        elif self.imports.get(a)=='time':self.set('X0',self.now)
        elif self.imports.get(a)=='atoll':self.set('X0',int(self.cstr(self.get('X0')))&((1<<64)-1))
        elif self.imports.get(a)=='sprintf':
            if self.cstr(self.get('X1'))!=b'%lld':raise ValueError('Unexpected timer format')
            v=self.get('X2');v=v-(1<<64)if v>>63 else v;raw=str(v).encode();uc.mem_write(self.get('X0'),raw+b'\0');self.set('W0',len(raw))
        elif a in(self.UI,0x6075bc,0x5033cc,0x39e034,0x406388,0xa7aaf4)or self.imports.get(a)=='_ZNSt8_Rb_treeISsSt4pairIKSsmESt10_Select1stIS2_ESt4lessISsESaIS2_EE8_M_eraseEPSt13_Rb_tree_nodeIS2_E':pass
        else:return super().hook(uc,a,n,d)
        self.set('PC',self.get('X30'))

    def click(self,*,map_key=5,map_type=0,map_found=True,connected=True,suppressed=False):
        if any(type(v)is not bool for v in(map_found,connected,suppressed)):raise ValueError('Explicit boolean fixtures required')
        if type(map_key)is not int or not 0<=map_key<=0xffffffff:raise ValueError('Explicit uint32 map key required')
        self.map_type=map_type;self.map_found=map_found;self.packets=[];self.confirmations=[];self.events=[];self.lookups=[]
        self.w(self.root+0x278,'I',map_key);self.w(self.root+0x6c,'B',0);self.w(self.sock+0x15c,'B',int(connected));self.w(self.net+0x8b,'B',int(suppressed))
        self.call(0x7197e4)
        return {'fixture':{'mapKey':map_key,'mapType':map_type,'mapFound':map_found,'connected':connected,'suppressed':suppressed},'packets':list(self.packets),'confirmations':list(self.confirmations),'mapLookups':list(self.lookups),'context6c':self.r(self.root+0x6c,'B')[0],'events':list(self.events),'destinationProduced':False}

    def confirm(self,result):
        if type(result)is not int or not 0<=result<=0xffffffff:raise ValueError('Explicit uint32 confirmation result required')
        self.packets=[];p=self.alloc(4);self.w(p,'I',result);self.call(0x7984d0,{'X0':p})
        return {'resultFixture':result,'packets':list(self.packets),'destinationProduced':False}

    def timer(self,*,now,saved):
        if type(now)is not int or(saved is not None and type(saved)is not int):raise ValueError('Explicit integer clock/key fixture required')
        self.now=now;self.saved=saved;self.kv=[];self.answer=None;call=self.alloc(0x30);self.w(call,'Q',self.alloc(24))
        self.call(0x719970,{'X0':call});return {'nowFixture':now,'savedFixture':saved,'asReturn':self.answer,'keyValueBoundary':list(self.kv),'realStorageTouched':False}

    def map_path_time(self,flag):
        if type(flag)is not bool:raise ValueError('Explicit context flag fixture required')
        self.kv=[];self.w(self.root+0x6c,'B',int(flag));self.call(0xa35938,{'X26':0x2528000})
        return {'flagFixture':flag,'keyValueBoundary':list(self.kv),'context6cAfter':self.r(self.root+0x6c,'B')[0],'mapPathPrefixOnly':True,'realStorageTouched':False,'clockSynchronizedFixture':False}

def run(image):
    e=UnstuckProbe(image)
    return {'format':'oc2-original-breakaway-fixtures-v1','ordinaryMap5':e.click(),'ordinaryOther':e.click(map_key=6,map_type=0),'unknownMapRow':e.click(map_key=6,map_type=2,map_found=False),
        'soloDungeon':e.click(map_key=6,map_type=2),'confirmZero':e.confirm(0),'confirmNonzero':e.confirm(1),
        'disconnected':e.click(connected=False),'suppressed':e.click(suppressed=True),
        'timerCases':[e.timer(now=100000,saved=v)for v in(None,100000,99999,99940,98200,98199)],
        'mapPathTimeWriter':[e.map_path_time(False),e.map_path_time(True)],
        'limits':['Input clock/map rows/socket state and UI services are explicit fixtures, not original activity.',
                  'Opcode 0x284 is the actual empty-payload request constructed by BreakAway. No original symbolic packet name or destination is inferred.',
                  'The localized combat/movement warning is text evidence only; its actual eligibility producer is not yet proven.',
                  'No transport, server result, save, destination or cooldown policy is implemented.']}

def main():
    from analyze_native_resources import NativeImage
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--library',type=Path,required=True);cli.add_argument('--output',type=Path,required=True);a=cli.parse_args();o=local_output(a.output);o.parent.mkdir(parents=True,exist_ok=True);r=run(NativeImage(a.library.read_bytes()));o.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'output':str(o),'ordinaryPackets':r['ordinaryMap5']['packets'],'soloConfirm':r['soloDungeon']['confirmations']}))
if __name__=='__main__':main()
