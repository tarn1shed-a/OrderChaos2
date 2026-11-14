"""Execute original skill-init parsing and cache writes on isolated fixtures.

This follows the frozen first progression batch. No file-backed role, network
session, real server learning state or persistent state is accessed.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from character_progression_evidence import local_output
from character_skill_progression import CharacterProgressionProbe

ROUTINES = {
    0x573b74:(1224,'8925b017d001940cba60bcf40fe00d526f95097293f3744b1af1650d895203e6'),
    0xa0ef3c:(252,'a7701a46c9a780e6e2d0a9a0d978096e34954254997a18a5253a199821729435'),
    0x1d43ba0:(84,'6fa3b7d4a061192d9f935f228b3d8c3f378d7e459883ebd3632e8ce1ee131a0f'),
    0x1ab7060:(660,'1551ba9b53a6ca7b563e1cc989bbdfef7199706317299b635edc5f2899a4281f'),
    0x1d42018:(68,'0d64069efcd008cdc004a86811e92f125a4820a9a40d6a20a0cc2433afd397de'),
    0x1d42110:(52,'30a6c1f5fa10c872f45bac4a792f2cd9b21dba8af882fe37ceec6bde3094146e'),
    0xa115ec:(100,'62492e2eda9110befb03c447aee4cdc8f3ea6fff861545645074a98e8bd51064'),
    0x5780fc:(1692,'47bdfc483b963e1430123dc9ff3afd25395bf0774ca7c57dcbabd832ff510bf3'),
    0x572370:(6148,'f27287413ce4e4fd6cd8d72f9e8aceb5ed7d7983d2059f6cab416af6fbc4714a'),
}


def varint(value):
    if type(value)is not int or not 0<=value<=0xffffffff:
        raise ValueError('Expected explicit uint32 fixture')
    out=bytearray()
    while value>127:
        out.append((value&127)|128);value>>=7
    out.append(value)
    return bytes(out)


def skill_init_fixture(records,skill_page=0):
    """Build the descriptor's explicit group fixture, not a live server packet."""
    if not isinstance(records,(tuple,list)) or len(records)>256:
        raise ValueError('Bounded learning-record fixture required')
    payload=bytearray()
    for row in records:
        if not isinstance(row,(tuple,list)) or len(row)!=2:
            raise ValueError('Expected (skill_proto_id,skill_rune) fixture')
        skill,index=row
        payload+=b'\x0b\x10'+varint(skill)+b'\x18'+varint(index)+b'\x0c'
    payload+=b'\x68'+varint(skill_page)
    return bytes(payload)


def project_learning_records(catalog,records=None):
    """Pure candidate projection; an absent incoming snapshot remains unknown.

    Records are (skill_proto_id, skill_rune index), as verified by the source
    init consumer. This neither learns anything on a server nor gates casting.
    Invalid rune ranges/passive variants are refused at this proposed boundary,
    because the native writer trusts incoming indices and has no range check.
    """
    if records is None:
        return {'known':False,'skills':None,'ignoredSkillIds':[]}
    if not isinstance(records,(tuple,list)) or len(records)>256:
        raise ValueError('Bounded explicit incoming-learning records required')
    indexed={row['skillId']:row for row in catalog}
    if len(indexed)!=len(catalog):raise ValueError('Duplicate profession catalog skill')
    learned={identifier:set() for identifier in indexed}; ignored=[]
    for row in records:
        if not isinstance(row,(tuple,list)) or len(row)!=2:
            raise ValueError('Expected source skill/rune record')
        identifier,index=row
        if type(identifier)is not int or not 0<=identifier<=0xffffffff or type(index)is not int or index not in range(4):
            raise ValueError('Invalid source skill/rune identifier')
        entry=indexed.get(identifier)
        if entry is None:
            ignored.append(identifier);continue
        if entry['kind']=='passive'and index!=0:
            raise ValueError('Unverified passive inscription record')
        if index not in [r['index']for r in entry['runes']]:
            raise ValueError('Absent source inscription')
        learned[identifier].add(index)
    return {'known':True,'skills':{identifier:sorted(indices)for identifier,indices in learned.items()},
            'ignoredSkillIds':ignored,
            'scope':'source incoming-learning projection; no unlock, equipped-slot, cast or point-spend inference'}


class CharacterLearningProbe(CharacterProgressionProbe):
    INIT_STOP=0x573c54
    def __init__(self,image):
        for address,(size,digest) in ROUTINES.items():
            if hashlib.sha256(image.read(address,size)).hexdigest()!=digest:
                raise ValueError('Original learning consumer differs; retrace required')
        self.in_message=False;self.message_kind=None
        super().__init__(image)
        from unicorn import UC_HOOK_CODE
        for address in (self.INIT_STOP,0x573bd4,0xa0ef3c,0x62f5b0,0x578160,0x57819c,0x5781f8):
            self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=address,end=address)

    def hook(self,uc,address,size,data):
        if self.in_message and address == self.CATALOG_STOP:
            # The original catalog core is finished. Skip only its UI refresh
            # tail and execute its own stack/register epilogue back to caller.
            self.set('PC',0xa0ffec)
        elif self.in_message and address == self.COUNT_STOP:
            self.set('PC',0xa0f1dc)
        elif self.in_message and address == self.INIT_STOP:
            # Equip/shortcut application follows; it is not part of this probe.
            self.set('PC',self.EXIT)
        elif self.in_message and self.message_kind=='receipt'and address in (0x57819c,0x5781f8):
            # Success has completed the cache write, or the failure path skipped
            # it. Presentation, displayed-point math and continuation are out.
            self.set('PC',self.EXIT)
        elif self.in_message and address == 0x573bd4:
            self.parser_result=bool(self.get('W0'))
        elif self.in_message and address == 0x578160:
            self.parser_result=bool(self.get('W0'))
        elif self.in_message and address == 0xa0ef3c:
            self.applied.append({'skillId':self.get('W1'),'runeIndex':self.get('W2'),
                                 'value':self.get('W3')&1})
        elif address == 0x62f5b0:
            if not self.in_message:raise ValueError('Unexpected skill UI update boundary')
            self.ui_updates.append({'kind':self.get('W1'),'index':self.get('W2')})
            self.set('PC',self.get('X30'))
        else:
            super().hook(uc,address,size,data)

    def receive_init(self,tables,records,*,profession=2,level=1,skill_page=0):
        raw=skill_init_fixture(records,skill_page)
        self.catalog(tables,profession=profession,level=level)
        registry=self.alloc(0x100);self.w(registry+0x68,'Q',self.actor)
        self.w(0x2528df8,'Q',registry)
        stream=self.alloc(0x40);data=self.alloc(len(raw)+4)
        self.w(data,'I',len(raw));self.uc.mem_write(data+4,raw)
        self.w(stream+0x10,'Q',0);self.w(stream+0x20,'2Q',data,data+len(raw)+4)
        self.in_message=True;self.message_kind='init';self.applied=[];self.ui_updates=[];self.parser_result=None
        self.mode='catalog'
        try:
            self.call(0x573b74,{'X1':stream},limit=200000)
        finally:
            self.in_message=False
        active=[];passive=[]
        for i in range(self.r(self.actor+0x1698,'I')[0]):
            at=self.actor+0x1530+i*0x28
            active.append({'skillId':self.r(at+0x24,'I')[0],'learningBytes':list(self.r(at,'4B')),
                           'locked':list(self.r(at+4,'4B'))})
        for i in range(self.r(self.actor+0x16d8,'I')[0]):
            at=self.actor+0x169c+i*0xc
            passive.append({'skillId':self.r(at+8,'I')[0],'learningByte':self.r(at,'B')[0]})
        return {'fixture':{'records':records,'profession':profession,'level':level,'skillPage':skill_page},
                'parserSucceeded':self.parser_result,'appliedInputs':list(self.applied),
                'active':active,'passive':passive,'skillPage':self.r(self.actor+0x17b4,'I')[0],
                'counts':list(self.r(self.actor+0x1718,'2I')),
                'streamBytesConsumed':self.r(stream+0x10,'Q')[0],
                'scope':'original protobuf parse, group copy, catalog/lock setup, per-rune cache writes and counts; explicit actor/table fixtures; UI events and equip/shortcut continuation excluded',
                'liveServerOrSavesUsed':False}

    def receive_receipt(self,tables,skill_id,rune_index,*,success=None,initial=(),profession=2,level=1):
        if success is not None and type(success)is not bool:
            raise ValueError('Explicit optional bool success fixture required')
        self.receive_init(tables,list(initial),profession=profession,level=level)
        raw=b'\x08'+varint(skill_id)+b'\x10'+varint(rune_index)
        if success is not None:raw+=b'\x18'+bytes([int(success)])
        stream=self.alloc(0x40);data=self.alloc(len(raw)+4)
        self.w(data,'I',len(raw));self.uc.mem_write(data+4,raw)
        self.w(stream+0x10,'Q',0);self.w(stream+0x20,'2Q',data,data+len(raw)+4)
        before=bytes(self.uc.mem_read(self.actor+0x1530,0x1ac))
        self.in_message=True;self.message_kind='receipt';self.applied=[];self.ui_updates=[];self.parser_result=None
        try:
            self.call(0x5780fc,{'X1':stream},limit=200000)
        finally:
            self.in_message=False
        after=bytes(self.uc.mem_read(self.actor+0x1530,0x1ac));learned={}
        for i in range(self.r(self.actor+0x1698,'I')[0]):
            at=self.actor+0x1530+i*0x28
            learned[self.r(at+0x24,'I')[0]]=[n for n,b in enumerate(self.r(at,'4B'))if b]
        for i in range(self.r(self.actor+0x16d8,'I')[0]):
            at=self.actor+0x169c+i*0xc
            learned[self.r(at+8,'I')[0]]=[0]if self.r(at,'B')[0]else []
        return {'fixture':{'skillId':skill_id,'runeIndex':rune_index,'success':success,
                           'initial':initial,'profession':profession,'level':level},
                'parserSucceeded':self.parser_result,'appliedInputs':list(self.applied),
                'cacheChanged':before!=after,'learnedRuneIndices':learned,
                'scope':'original response parse and success-guarded cache write; stopped before presentation/point-display continuation; explicit actor/source-state fixtures',
                'liveServerOrSavesUsed':False}


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--library',type=Path,required=True)
    cli.add_argument('--evidence',type=Path,required=True)
    cli.add_argument('--output',type=Path,required=True)
    args=cli.parse_args()
    from analyze_native_resources import NativeImage
    probe=CharacterLearningProbe(NativeImage(args.library.read_bytes()))
    tables=json.loads(args.evidence.read_text())['tables']
    report={'empty':probe.receive_init(tables,[]),
            'mage':probe.receive_init(tables,[(90,0),(90,2),(94,0),(404,0)],skill_page=2),
            'crossProfession':probe.receive_init(tables,[(24,0),(90,0)],profession=1),
            'runeWithoutBase':probe.receive_init(tables,[(90,2)]),
            'unknown':probe.receive_init(tables,[(0xffffffff,0)])}
    report['receipts']=[probe.receive_receipt(tables,90,1,success=s,initial=[(90,0)])for s in (None,False,True)]
    report['registration']={'init':{'messageId':0x4b,'handler':'0x573b74','registration':'0x5723b4..0x5723c4'},
                            'receipt':{'messageId':0xa7,'handler':'0x5780fc','registration':'0x573610..0x573620'},
                            'scope':'pinned original registration instructions; not a live transport'}
    out=local_output(args.output)/'learning-init-probe.json'
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'output':str(out),'serverOrSavesUsed':False}))


if __name__=='__main__':
    main()
