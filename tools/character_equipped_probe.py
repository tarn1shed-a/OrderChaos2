"""Bounded original skill-slot getters/updates on explicit fresh memory fixtures.

No saved/live character, network, production UI or storage is accessed.
"""
from pathlib import Path

from character_learning_state import CharacterLearningProbe,varint
from character_progression_evidence import wire_fields

ROOT=Path(__file__).resolve().parents[1]


def equipped_init_fixture(learned=(),equipped=(),*,page=0):
    if not isinstance(learned,(tuple,list))or not isinstance(equipped,(tuple,list))or len(learned)>256 or len(equipped)>256:
        raise ValueError('Bounded explicit original message groups required')
    payload=bytearray()
    for skill,rune in learned:payload+=b'\x0b\x10'+varint(skill)+b'\x18'+varint(rune)+b'\x0c'
    for skill,rune,slot in equipped:payload+=b'\x23\x28'+varint(skill)+b'\x30'+varint(rune)+b'\x38'+varint(slot)+b'\x24'
    return bytes(payload)+b'\x68'+varint(page)


class CharacterEquippedProbe(CharacterLearningProbe):
    TYPE=0x30000b00;INDEX=0x30000b04;GROUP=0x30000b08;UI_EVENT=0x30000b0c
    def __init__(self,image):
        self.equipped_mode=None
        super().__init__(image)
        from unicorn import UC_HOOK_CODE
        for address in [0x10361b4,0x1036c34,self.TYPE,self.INDEX,self.GROUP,self.UI_EVENT,
                        0x573f34,0x5bfb64,0xa100f0,0xa0f6b0,0xa1314c,0x648864,0x648338,
                        0x3de09c,0x39e034,0xa792c4,0x1de639c,0x1de9b88]:
            self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=address,end=address)

    def hook(self,uc,address,size,data):
        mode=self.equipped_mode
        if mode and address==0x10361b4:
            self.df('D0',self.r(self.get('X0')+8,'d')[0])
        elif mode and address==0x1036c34:
            self.returned=self.gd('D0');self.w(self.get('X0'),'B',2);self.w(self.get('X0')+8,'d',self.returned)
        elif mode and address in (self.TYPE,self.INDEX,self.GROUP):
            offset={self.TYPE:0x20,self.INDEX:0x24,self.GROUP:0x28}[address]
            self.set('W0',self.r(self.get('X0')+offset,'I')[0])
        elif mode and address==self.UI_EVENT:self.effects.append({'boundary':'UI event delivery'})
        elif mode and address==self.INIT_STOP:
            return # Continue beyond the frozen learning-only stop.
        elif mode and address==0x573f34:
            self.set('PC',self.EXIT);return # Stop before shortcut reconstruction.
        elif mode and address in (0x5bfb64,0xa100f0,0xa0f6b0):
            self.writes.append({'entry':hex(address),'skill':self.get('W1'),'slot':self.get('W2'),'flag':self.get('W3')})
            return # Execute the original writer, not a host replacement.
        elif mode and address==0xa1314c:
            self.effects.append({'boundary':'downstream recalculation excluded','entry':hex(address)})
        elif mode and address in (0x648864,0x648338):
            self.effects.append({'boundary':'presentation object construction','entry':hex(address),'slot':self.get('W1')})
            uc.mem_write(self.get('X0'),bytes(0x48))
        elif mode and address==0x3de09c:self.set('X0',self.ui_object)
        elif mode and address in (0x39e034,0x1de9b88):pass
        elif mode and address==0x1de639c:
            raw=self.cstr(self.get('X1'));at=self.alloc(24+len(raw)+1);self.w(at+16,'i',1);uc.mem_write(at+24,raw+b'\0');self.w(self.get('X0'),'Q',at+24)
        elif mode and address==0xa792c4:
            self.config_reads.append({'section':self.cstr(self.r(self.get('X1'),'Q')[0]).decode(),'key':self.cstr(self.r(self.get('X2'),'Q')[0]).decode(),'default':self.get('W3')})
            self.set('W0',self.num_skills)
        elif mode and address==self.SEND:
            message=self.get('X2');vtable=self.r(message,'Q')[0];serializer=self.r(vtable+0x58,'Q')[0]
            code=self.get('W1');name={0x47:'CMSG_EquipSkill',0xac:'CMSG_EquipPage'}.get(code)
            if not name:raise ValueError('Unexpected original equipped transport')
            buffer=self.alloc(512);self.pending=(self.get('X30'),code,buffer,name)
            self.set('X0',message);self.set('X1',buffer);self.set('X30',self.SENT);self.set('PC',serializer);return
        elif mode and address==self.SENT:
            back,code,buffer,name=self.pending;length=self.get('X0')-buffer
            if not 0<=length<=512:raise ValueError('Unbounded original equipped serializer')
            payload=bytes(uc.mem_read(buffer,length));fields={r['number']:r['name']for r in self.schema[name]['fields']}
            decoded={fields[n]:v for n,w,v in wire_fields(payload)if w==0}
            self.packets.append({'id':code,'message':name,'fields':decoded,'hex':payload.hex()});self.pending=None
            self.set('X30',back);self.set('W0',1);self.set('PC',back);return
        else:return super().hook(uc,address,size,data)
        self.set('PC',self.get('X30'))

    def setup(self,tables,*,profession=2,level=1,operation_bank=0,num_skills=6):
        if type(operation_bank)is not int or not 0<=operation_bank<5 or type(num_skills)is not int or not 0<=num_skills<=0xffffffff:
            raise ValueError('Explicit operation-manager selector/config-return fixtures required')
        self.catalog(tables,profession=profession,level=level)
        self.num_skills=num_skills;self.writes=[];self.effects=[];self.config_reads=[];self.ui_updates=[];self.returned=None
        registry=self.alloc(0x100);self.w(registry+0x68,'Q',self.actor);self.w(0x2528df8,'Q',registry)
        sentinel=self.actor+0x788;self.w(sentinel+0x10,'2Q',sentinel,sentinel)
        self.op_manager=self.alloc(0x40);self.w(self.op_manager+0x30,'I',operation_bank);self.w(0x2534df8,'Q',self.op_manager)
        self.banks=[]
        for i in range(5):
            pointer=self.alloc(0x200);self.banks.append(pointer);self.w(pointer,'Q',pointer);self.w(self.op_manager+8+8*i,'Q',pointer)
        self.ui_object=self.alloc(0x100);vt=self.alloc(0x100);self.w(self.ui_object,'Q',vt);self.w(vt+0x40,'Q',self.UI_EVENT)
        root=self.alloc(8);self.w(root,'Q',self.ui_object);self.w(0x2505658,'Q',root)
        self.w(0x2528e28,'Q',self.alloc(0x100))

    def state(self):
        return {'operationBanks':[list(self.r(p+0x34,'5i'))for p in self.banks],
                'actorSlots11To20':list(self.r(self.actor+0x16ec,'10I')),
                'skillPage':self.r(self.actor+0x17b4,'I')[0],
                'activeLearning':[list(self.r(self.actor+0x1530+i*0x28,'4B'))for i in range(self.r(self.actor+0x1698,'I')[0])],
                'selectedRunes':[self.r(self.actor+0x1530+i*0x28+0xc,'B')[0]for i in range(self.r(self.actor+0x1698,'I')[0])],
                'activeRows':[{'skillId':self.r(self.actor+0x1530+i*0x28+0x24,'I')[0],
                               'learningBytes':list(self.r(self.actor+0x1530+i*0x28,'4B')),
                               'selectedRune':self.r(self.actor+0x1530+i*0x28+0xc,'B')[0]}
                              for i in range(self.r(self.actor+0x1698,'I')[0])]}

    def receive_init_equipped(self,tables,learned=(),equipped=(),*,profession=2,level=1,page=0,operation_bank=0,num_skills=6):
        self.setup(tables,profession=profession,level=level,operation_bank=operation_bank,num_skills=num_skills)
        raw=equipped_init_fixture(learned,equipped,page=page);stream=self.message_stream(raw)
        self.in_message=True;self.message_kind='init';self.equipped_mode='init';self.applied=[];self.parser_result=None
        try:self.call(0x573b74,{'X1':stream},limit=300000)
        finally:self.equipped_mode=None;self.in_message=False
        return {'fixture':{'learned':learned,'equipped':equipped,'profession':profession,'level':level,'page':page,'operationBank':operation_bank,'NumOfSkillToShow':num_skills},
                'state':self.state(),'parserSucceeded':self.parser_result,'writes':self.writes,'configReads':self.config_reads,'presentationBoundaries':self.effects,
                'scope':'original protobuf parse/catalog/learning, operation-bank0 active slots and actor slots11..20; explicit loaded manager/config/presentation interfaces; stopped before shortcut restoration',
                'liveServerOrSavesUsed':False}

    def message_stream(self,raw):
        stream=self.alloc(0x40);data=self.alloc(len(raw)+4);self.w(data,'I',len(raw));self.uc.mem_write(data+4,raw)
        self.w(stream+0x20,'2Q',data,data+len(raw)+4);return stream

    def page_request(self,tables,page):
        self.setup(tables);self.equipped_mode='page-request';self.packets=[]
        try:self.call(0xa115ec,{'X0':self.actor,'W1':page,'W2':0},limit=10000)
        finally:self.equipped_mode=None
        return {'fixture':{'page':page},'packets':self.packets,'storedPage':self.r(self.actor+0x17b4,'I')[0],
                'scope':'original setter request branch and original protobuf array serializer; recording transport only','liveServerOrSavesUsed':False}

    def active_equip_request(self,tables,skill,slot):
        self.setup(tables);self.equipped_mode='equip-request';self.packets=[]
        if 1<=slot<=5:self.w(self.banks[0]+0x30+slot*4,'I',skill)
        try:self.call(0x5c01bc,{'X0':self.banks[0],'W1':slot,'W2':1,'W3':1,'W4':0},limit=20000)
        finally:self.equipped_mode=None
        return {'fixture':{'alreadyWrittenSlotSkill':skill,'slot':slot},'packets':self.packets,
                'scope':'original active-slot request core and protobuf array serializer; selected-slot cache supplied explicitly; action dispatch/service permission not executed','liveServerOrSavesUsed':False}

    def receive_equip(self,tables,skill,rune,slot,*,success=None,profession=2,level=1,operation_bank=0):
        self.setup(tables,profession=profession,level=level,operation_bank=operation_bank)
        raw=b'\x08'+varint(skill)+b'\x10'+varint(rune)+b'\x18'+varint(slot)
        if success is not None:raw+=b'\x20'+bytes([int(success)])
        self.in_message=True;self.message_kind='equip';self.equipped_mode='equip'
        try:self.call(0x578798,{'X1':self.message_stream(raw)},limit=100000)
        finally:self.equipped_mode=None;self.in_message=False
        return {'fixture':{'skill':skill,'rune':rune,'slot':slot,'success':success,'profession':profession,'operationBank':operation_bank},'state':self.state(),'writes':self.writes,
                'scope':'original 0xa8 parser and active/current-page or actor-slot writer; presentation/recalculation sinks explicit','liveServerOrSavesUsed':False}

    def get_slot(self,kind,index,*,entries=(),active_slots=None,operation_bank=0,argument_count=2,argument_type=2):
        """GetSkillIdByOpSlot callback with explicit op objects and page cache.

        Entry tuples are (kind,index,payload). For kind4 payload is native slot
        number; for kind5 it is a catalog-selection skill ID, not equipment.
        """
        self.equipped_mode='getter';self.effects=[];self.returned=None
        manager=self.alloc(0x40);array=self.alloc(max(8,len(entries)*8))
        for i,(entry_kind,entry_index,payload)in enumerate(entries):
            obj=self.alloc(0x40);vt=self.alloc(0x80);self.w(obj,'Q',vt);self.w(obj+0x20,'3I',entry_kind,entry_index,entry_kind)
            self.w(obj+(0x2c if entry_kind==4 else 0x30),'i',payload)
            for offset,target in [(0x10,self.TYPE),(0x18,self.INDEX),(0x60,self.GROUP)]:self.w(vt+offset,'Q',target)
            self.w(array+i*8,'Q',obj)
        self.w(manager,'2Q',array,array+len(entries)*8);self.w(0x25352b8,'Q',manager)
        if active_slots is not None:
            if len(active_slots)!=5:raise ValueError('Explicit five-slot page cache required')
            op=self.alloc(0x40);p=self.alloc(0x200);self.w(op+0x30,'I',operation_bank);self.w(op+8,'Q',p);self.w(p,'Q',p);self.w(p+0x34,'5i',*active_slots);self.w(0x2534df8,'Q',op)
        output=self.alloc(24);args=self.alloc(48);vector=self.alloc(8);call=self.alloc(0x30)
        self.w(args,'B',argument_type);self.w(args+8,'d',float(index));self.w(args+24,'B',argument_type);self.w(args+32,'d',float(kind))
        self.w(vector,'Q',args);self.w(call,'Q',output);self.w(call+0x18,'Q',vector);self.w(call+0x20,'2I',argument_count,1)
        try:self.call(0x6270ec,{'X0':call},limit=100000)
        finally:self.equipped_mode=None
        return {'fixture':{'kind':kind,'index':index,'entries':entries,'activeSlots':active_slots,'argumentCount':argument_count,'argumentType':argument_type},
                'returned':self.returned,'scope':'original AS callback validation, original OpSlot iteration and numeric ID/equipped-slot getter; explicit numeric-AS and virtual op-object interfaces','liveServerOrSavesUsed':False}
