"""Read original228/240 event records; do not execute their script names.

Only the generated record reader and original bounded string-stream consumer
execute. Loaded-file seek/read and COW string allocation are named interfaces.
"""
import hashlib
import json
import struct
from pathlib import Path
from source_physics import SourcePhysics

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'analysis/raw/tutorial-skill-script-refs-20261115'
SO=ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'
TABLE_SHA='c94f012b101f0b42d2adc392f9a0cf41f187b67085a948b6d78f4c09eb922e46'


class SkillEventRecordProbe(SourcePhysics):
    SEEK=SourcePhysics.EXIT+0xdc0
    FILE_READ=SourcePhysics.EXIT+0xdc4
    def __init__(self,image,table):
        super().__init__(image);self.table_bytes=table;self.position=0;self.interfaces=[]
        from unicorn import UC_HOOK_CODE
        for at in(self.SEEK,self.FILE_READ,0x1de8e34):
            self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=at,end=at)

    def hook(self,uc,at,size,data):
        if at==0x1de8e34:
            n=self.get('W1')
            if not 0<n<=128 or self.get('W2')!=0:raise ValueError('Bounded source string allocation required')
            storage=self.alloc(24+n+1);self.w(storage,'3Q',n,n,0xffffffffffffffff)
            self.w(self.get('X0'),'Q',storage+24)
            self.interfaces.append({'kind':'COW-string-resize-allocation','sourceCall':'0xe88224','length':n,'libstdcxxBodyExecuted':False})
        elif at==self.SEEK:
            if self.get('W2')!=0 or self.get('W1')>len(self.table_bytes):raise ValueError('Only source absolute table seek admitted')
            self.position=self.get('W1');self.interfaces.append({'kind':'loaded-file-seek','offset':self.position})
            self.set('W0',1)
        elif at==self.FILE_READ:
            n=self.get('W2');raw=self.table_bytes[self.position:self.position+n]
            if len(raw)!=n:raise ValueError('Original string read outside complete original table')
            self.uc.mem_write(self.get('X1'),raw);self.position+=n
            self.interfaces.append({'kind':'loaded-file-read','bytes':n});self.set('W0',n)
        else:return super().hook(uc,at,size,data)
        self.set('PC',self.get('X30'))

    def read_record(self,index,expected):
        _,count,cols,ids_at,types_at,rows_at,stride,strings_at,_=struct.unpack_from('<9I',self.table_bytes,8)
        if not 0<=index<count:raise ValueError('Original table row index required')
        native_table=self.alloc(0x200);file=self.alloc(0x30);vt=self.alloc(0x30)
        self.w(file,'Q',vt);self.w(vt+0x20,'Q',self.SEEK);self.w(vt+0x18,'Q',self.FILE_READ)
        self.w(native_table+0x88,'Q',file);self.w(native_table+0xc4,'I',len(self.table_bytes))
        raw=self.table_bytes[rows_at+stride*index:rows_at+stride*(index+1)]
        stream=self.alloc(0x30);value=self.alloc(len(raw));self.uc.mem_write(value,raw)
        self.w(stream+0x18,'2Q',value,value+len(raw));destination=self.alloc(44)
        self.interfaces=[];result=self.call(0xd08cfc,{'X0':native_table,'X1':stream,'X2':destination},limit=10000)
        source_name=self.cstr(self.r(destination+0xc,'Q')[0]).decode()
        decoded={'ID':self.r(destination,'I')[0],'triggerType':self.r(destination+4,'I')[0],
            'targetType':self.r(destination+8,'I')[0],'scriptFunc':source_name,
            'areaType':self.r(destination+0x14,'I')[0],'areaRadius':self.r(destination+0x18,'f')[0],
            'areaAngle':self.r(destination+0x1c,'f')[0],'delayTime':self.r(destination+0x20,'I')[0],
            'parentSkillId':self.r(destination+0x24,'I')[0],'runeId':self.r(destination+0x28,'I')[0]}
        assert decoded==expected and result==1 and self.r(stream+8,'Q')[0]==stride
        return {'rowIndex':index,'rowBytes':stride,'nativeOutputBytes':44,'return':result,
            'decoded':decoded,'scriptStringMemoryOffset':12,'originalReader':'0xd08cfc',
            'originalStringReader':'0xe881dc','interfaces':list(self.interfaces),
            'originalFileLoaderExecuted':False,'scriptLookupOrExecutionObserved':False}


def run():
    from analyze_native_resources import NativeImage
    from resource_packs import ResourceArchive,DEFAULT_SOURCE
    from skill_attachments import decode_ftable
    raw=ResourceArchive(Path(DEFAULT_SOURCE)/'tables.bin').read('tables/skill_event.tbl')
    if hashlib.sha256(raw).hexdigest()!=TABLE_SHA:raise ValueError('Original event table changed')
    parsed=decode_ftable(raw,'ID');p=SkillEventRecordProbe(NativeImage(SO.read_bytes()),raw)
    rows=[p.read_record(i,row)for i,row in enumerate(parsed['rows'])if row['parentSkillId']in(228,240)]
    assert[(r['decoded']['ID'],r['decoded']['scriptFunc'])for r in rows]==[(291,'Skill228_OnSkillHit'),(317,'Skill240_OnSkillHit')]
    return {'format':'oc2-original-skill-script-record-consumer-v1','nativeSHA256':hashlib.sha256(SO.read_bytes()).hexdigest(),
        'tableSHA256':TABLE_SHA,'sourcePhysicalTypes':parsed['physicalTypes'],'sourceRows':parsed['verification']['rows'],
        'records':rows,'scriptNamesInterpretedOrResolved':False,'serverScriptBodiesRecovered':False,
        'checks':3,'savesTouched':False,'sharedOrProductionChanged':False}


if __name__=='__main__':
    RAW.mkdir(parents=True,exist_ok=True);target=RAW/'record-cpu-v1.json'
    if target.exists():raise ValueError('Preserve original record evidence')
    r=run();target.write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps({'records':len(r['records']),'checks':r['checks'],'scriptExecution':False}))
