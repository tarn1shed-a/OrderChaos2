"""Independent progression candidates and original request/XP instruction probes.

No runtime import, save access, XP award or learning-state synthesis. The source
wire/cache -> normalized learned-rune mapping is deliberately not supplied.
"""
import argparse
import json
import struct
from pathlib import Path

from character_progression_evidence import local_output, verify_native, wire_fields
from source_physics import SourcePhysics


def inspect_skill(catalog, skill_id, rune_index=0, *, learning_fixture=None):
    """Fail-closed inspection using an explicitly normalized learning fixture.

    This is a proposed boundary, not the missing original SMSG_SkillInit decoder
    or an assertion that a given character has learned any skill. An absent
    fixture stays unknown; an explicit empty fixture means no learned skills.
    """
    if type(skill_id) is not int or type(rune_index) is not int or rune_index not in range(4):
        raise ValueError('Expected original numeric skill ID and inscription index')
    rows = [r for r in catalog if r['skillId'] == skill_id]
    if not rows:
        return {'available':False, 'reason':'outside-profession-catalog'}
    if len(rows) != 1:
        raise ValueError('Ambiguous profession catalog')
    row = rows[0]
    rune = next((r for r in row['runes'] if r['index'] == rune_index),None)
    if rune is None:
        return {'available':False, 'reason':'absent-source-rune'}
    if learning_fixture is None:
        return {'available':False, 'reason':'learning-state-unknown', 'learned':None}
    if not isinstance(learning_fixture,dict):
        raise ValueError('Normalized learning fixture must be an explicit dict')
    for identifier,indices in learning_fixture.items():
        if type(identifier) is not int or not isinstance(indices,(list,tuple)) or any(type(i)is not int or i not in range(4) for i in indices) or len(set(indices)) != len(indices):
            raise ValueError('Invalid normalized learning fixture')
    indices = learning_fixture.get(skill_id,())
    if 0 not in indices:
        return {'available':False, 'reason':'base-not-learned', 'learned':False}
    if rune_index not in indices:
        return {'available':False, 'reason':'rune-not-learned', 'learned':False}
    # No claim about active slot, cast eligibility, point cost or server result.
    return {'available':True, 'reason':'explicit-learning-fixture', 'learned':True,
            'skillId':skill_id, 'runeIndex':rune_index, 'sourceRuneId':rune['sourceRuneId'],
            'kind':row['kind']}


class CharacterProgressionProbe(SourcePhysics):
    SEND = 0x567094
    SENT = SourcePhysics.EXIT + 0x900
    XP_STOP = 0x668814
    SERIALIZER = 0x1d50798
    TABLE_ROW = SourcePhysics.EXIT + 0xa00
    CATALOG_STOP = 0xa0fdbc
    COUNT_STOP = 0xa0f17c

    def __init__(self,image):
        from unicorn import UC_HOOK_CODE
        self.schema = verify_native(image)
        super().__init__(image)
        self.pending = None
        self.mode = None
        for address in (self.SEND,self.SENT,self.XP_STOP,self.TABLE_ROW,self.CATALOG_STOP,
                        self.COUNT_STOP,0xa996a0,0x5b57e8,0x1036690,0x10361b4,0x1036c70,0x53b5b8):
            self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=address,end=address)

    def hook(self,uc,address,size,data):
        if address == 0xa996a0 and self.mode in ('xp','catalog'):
            offset = self.get('X0') - self.properties
            if offset not in self.property_fixture:
                raise ValueError('Unexpected original property lookup')
            self.property_reads.append(offset)
            self.set('W0',self.property_fixture[offset] & 0xffffffff)
        elif address == self.TABLE_ROW and self.mode == 'catalog':
            row = self.xp_table_rows.get(self.get('W1'))
            self.slot_row_found = row is not None
            if row is not None:
                uc.mem_write(self.get('X2'),row)
            self.set('W0',int(row is not None))
        elif address == 0x5b57e8 and self.mode == 'catalog':
            # Explicit loaded proto-cache boundary; original attributes are
            # copied from the checked table, and a missing cache remains null.
            pointer = self.proto_cache.get(self.get('W0'),0)
            self.w(self.get('X8'),'2Q',pointer,0)
        elif address in (self.CATALOG_STOP,self.COUNT_STOP) and self.mode in ('catalog','counts'):
            self.set('PC',self.EXIT)
            return
        elif address == self.XP_STOP and self.mode == 'xp':
            self.xp_result = {'xp':self.r(self.STACK+0xc,'i')[0],
                              'upgradeXp':self.get('W21'), 'level':self.get('W0')}
            self.set('PC',self.EXIT)
            return
        elif address == 0x1036690 and self.mode == 'learn':
            # Explicit Flash numeric-value conversion boundary. Source callback
            # performs the count/type/finite checks before calling this helper.
            number = self.r(self.get('X0')+8,'d')[0]
            self.set('W0',int(number) & 0xffffffff)
        elif address == 0x10361b4 and self.mode == 'class':
            self.df('D0',self.r(self.get('X0')+8,'d')[0])
        elif address == 0x53b5b8 and self.mode == 'class':
            # Explicit absent 3D menu preview manager; original branch skips it.
            self.set('X0',0)
        elif address == 0x1036c70 and self.mode in ('learn','class'):
            self.callback_valid = bool(self.get('W1'))
        elif address == self.SEND and self.mode == 'learn':
            message = self.get('X2'); vtable = self.r(message,'Q')[0]
            if vtable != 0x24fc300 or self.r(vtable+0x58,'Q')[0] != self.SERIALIZER:
                raise ValueError('Unexpected original learning message/serializer')
            if self.pending is not None:
                raise ValueError('Nested original learning send')
            buffer = self.alloc(128)
            self.pending = (self.get('X30'),self.get('W1'),buffer)
            self.set('X0',message); self.set('X1',buffer)
            self.set('X30',self.SENT); self.set('PC',self.SERIALIZER)
            return
        elif address == self.SENT and self.mode == 'learn':
            return_address,code,buffer = self.pending
            length = self.get('X0')-buffer
            if not 0 <= length <= 128:
                raise ValueError('Unbounded original learning payload')
            raw = bytes(uc.mem_read(buffer,length))
            fields = list(wire_fields(raw)); schema = self.schema['CMSG_LearnSkill']['fields']
            by_number = {r['number']:r for r in schema}
            if any(w != 0 or n not in by_number for n,w,v in fields):
                raise ValueError('Unexpected original learning payload fields')
            values = {by_number[n]['name']:v for n,w,v in fields}
            self.packets.append({'id':code,'message':'CMSG_LearnSkill','hex':raw.hex(),'fields':values})
            self.pending = None
            self.set('W0',1); self.set('X30',return_address); self.set('PC',return_address)
            return
        else:
            return super().hook(uc,address,size,data)
        self.set('PC',self.get('X30'))

    def xp_display_slice(self, *, level, xp, upgrade_xp):
        """Execute 668778..668810 with explicit decoded property-return fixtures.

        These are not real actor properties, original XP-table results or a
        running Hero_GetHeroInfo. No table->threshold semantics are inferred.
        """
        if any(type(v)is not int or not 0<=v<=0x7fffffff for v in (level,xp,upgrade_xp)):
            raise ValueError('Signed nonnegative int32 property fixtures required')
        self.mode = 'xp'; self.property_reads = []
        self.properties = self.alloc(0x1000); actor = self.alloc(0x100)
        self.w(actor+0x18,'Q',self.properties)
        self.property_fixture = {0x268:level,0x450:xp,0x458:upgrade_xp,
                                 0x568:0,0x570:0,0x578:0,0x580:0,0x5e8:0,0x610:0}
        self.call(0x668778,{'X27':actor},limit=1000)
        return {**self.xp_result, 'propertyReads':[hex(n) for n in self.property_reads],
                'fixture':{'level':level,'xp':xp,'upgradeXp':upgrade_xp},
                'scope':'bounded original instruction slice; property getter returns are explicit fixtures'}

    def learn_request(self,skill_id,rune_index,*,argument_count=2,argument_type=2):
        if any(type(v)is not int or not 0<=v<=0xffffffff for v in (skill_id,rune_index,argument_count)) or type(argument_type)is not int or not 0<=argument_type<=255:
            raise ValueError('Unsigned request/layout fixtures required')
        self.mode = 'learn'; self.packets = []; self.callback_valid = None
        if self.pending is not None:
            raise ValueError('Unfinished original request')
        # Disable the optional source diagnostics branch, not game validation.
        debug = self.r(0x2506190,'Q')[0]
        self.w(debug,'B',0)
        vector = self.alloc(8); args = self.alloc(48); call = self.alloc(0x30)
        output = self.alloc(24)
        # Flash callback uses the high word as its starting argument index.
        # Numeric index 1 is the skill ID, and preceding index 0 is the rune.
        self.w(args,'B',argument_type); self.w(args+8,'d',float(rune_index))
        self.w(args+24,'B',argument_type); self.w(args+32,'d',float(skill_id))
        self.w(vector,'Q',args); self.w(call,'Q',output)
        self.w(call+0x18,'Q',vector); self.w(call+0x20,'2I',argument_count,1)
        self.w(0x2528e30,'Q',self.alloc(0x100))
        self.call(0x6a60e4,{'X0':call},limit=10000)
        return {'fixture':{'skillId':skill_id,'runeIndex':rune_index,
                           'argumentCount':argument_count,'argumentType':argument_type},
                'callbackValid':self.callback_valid,'packets':list(self.packets),
                'learningStateChanged':False,'liveServerOrSavesUsed':False,
                'scope':'original callback/constructor/array serializer; Flash-number and recording-transport interfaces'}

    def catalog(self,tables,*,profession,level,missing_proto_ids=()):
        """Execute source catalog construction/sorting/lock checks before UI sends.

        Read-only FTABLE contents populate explicit std::map nodes and loaded
        proto-cache fixtures. Source tree iteration executes without a hook.
        Actor property reads and generated-table virtual lookup are interfaces.
        The actor is fresh isolated memory, never a user character.
        """
        if type(profession)is not int or profession not in range(1,6) or type(level)is not int or not 1<=level<=0x7fffffff:
            raise ValueError('Explicit five-profession/level fixture required')
        self.mode = 'catalog'; self.property_reads = []; self.slot_row_found = False
        self.actor = self.alloc(0x1900); self.properties = self.alloc(0x1000)
        self.w(self.actor+0x18,'Q',self.properties)
        self.property_fixture = {0x268:level,0x3f8:profession}
        manager,unlock_table,xp_table,vt = [self.alloc(n) for n in (0x400,0x80,0x80,0x40)]
        self.w(0x2528dc8,'Q',manager)
        self.w(manager+0x220,'Q',unlock_table); self.w(manager+0x358,'Q',xp_table)
        self.w(xp_table,'Q',vt); self.w(vt+0x18,'Q',self.TABLE_ROW)
        xp = tables['player_xp']
        self.xp_table_rows = {r['level']:struct.pack('<'+''.join('i' if c=='i' else 'I' for c in xp['physicalTypes']),
                              *(r[c] for c in xp['columns'])) for r in xp['rows']}
        rows = sorted(tables['skill_unlock']['rows'],key=lambda r:r['id'])
        sentinel = unlock_table+0x30
        nodes = [self.alloc(0x48) for r in rows]
        def tree(lo,hi,parent):
            if lo>=hi:
                return 0
            mid=(lo+hi)//2; node=nodes[mid]
            self.w(node+8,'3Q',parent,tree(lo,mid,node),tree(mid+1,hi,node))
            row=rows[mid]
            self.w(node+0x20,'9I',row['id'],*(row[c] for c in tables['skill_unlock']['columns']))
            return node
        root=tree(0,len(rows),sentinel)
        self.w(sentinel+8,'3Q',root,nodes[0] if nodes else sentinel,nodes[-1] if nodes else sentinel)
        self.proto_cache={}
        for row in tables['skill_proto']['rows']:
            if row['skillId'] in missing_proto_ids:
                continue
            cached=self.alloc(0x30); proto=self.alloc(0x10)
            self.w(proto,'3I',row['skillId'],row['filter'],row['attributes'])
            self.w(cached+0x28,'Q',proto); self.proto_cache[row['skillId']]=cached
        self.call(0xa0f968,{'X0':self.actor},limit=100000)
        active_count=self.r(self.actor+0x1698,'I')[0]
        passive_count=self.r(self.actor+0x16d8,'I')[0]
        if active_count>9 or passive_count>5:
            raise ValueError('Original catalog capacity exceeded')
        active=[]
        for i in range(active_count):
            at=self.actor+0x1530+i*0x28
            active.append({'skillId':self.r(at+0x24,'I')[0],
                'learnedBytes':list(self.r(at,'4B')), 'locked':list(self.r(at+4,'4B')),
                'requiredLevels':list(self.r(at+0xd,'4B')),
                'requiredPoints':list(self.r(at+0x14,'4I'))})
        passive=[]
        for i in range(passive_count):
            at=self.actor+0x169c+i*0xc
            passive.append({'skillId':self.r(at+8,'I')[0], 'learnedByte':self.r(at,'B')[0],
                'locked':self.r(at+1,'B')[0], 'requiredLevel':self.r(at+2,'B')[0],
                'requiredPoints':self.r(at+4,'I')[0]})
        return {'fixture':{'profession':profession,'level':level,'missingProtoIds':list(missing_proto_ids)},
                'active':active,'passive':passive,
                'slots':list(self.r(self.actor+0x16e4,'2I')),'xpTableLookupFound':self.slot_row_found,
                'scope':'original catalog/lock/sort/slot instructions and tree iterator; fresh actor, source table containers and proto-cache interfaces; stopped before UI side effects',
                'liveServerOrSavesUsed':False}

    def learned_counts(self,active_flags):
        """Count original cached active/rune bytes; passive count is separate."""
        if not isinstance(active_flags,(list,tuple)) or len(active_flags)>9 or any(not isinstance(r,(list,tuple)) or len(r)!=4 or any(type(b)is not int or not 0<=b<=255 for b in r) for r in active_flags):
            raise ValueError('At most nine four-byte active learning fixtures required')
        self.mode='counts'; actor=self.alloc(0x1900)
        self.w(actor+0x1698,'I',len(active_flags))
        for i,row in enumerate(active_flags):
            self.w(actor+0x1530+i*0x28,'4B',*row)
        self.call(0xa0f0f8,{'X0':actor},limit=1000)
        return {'baseCount':self.r(actor+0x1718,'I')[0],
                'runeCount':self.r(actor+0x171c,'I')[0],
                'scope':'original byte-count instructions; explicit learning-cache fixture'}

    def creation_class(self,index,*,argument_count=1,argument_type=2):
        """Execute original menu index -> original player-class assignment."""
        if type(index)is not int or not -0x80000000<=index<=0x7fffffff or type(argument_count)is not int or not 0<=argument_count<=0xffffffff or type(argument_type)is not int or not 0<=argument_type<=255:
            raise ValueError('Explicit creation index/argument fixtures required')
        self.mode='class'; self.callback_valid=None
        menu=self.alloc(0x400); self.w(0x2528db0,'Q',menu)
        # A sentinel distinguishes an unmapped index from class zero.
        self.w(menu+0x2bc,'i',-99)
        output=self.alloc(24); argument=self.alloc(24); vector=self.alloc(8); call=self.alloc(0x30)
        self.w(argument,'B',argument_type);self.w(argument+8,'d',float(index))
        self.w(vector,'Q',argument);self.w(call,'Q',output)
        self.w(call+0x18,'Q',vector);self.w(call+0x20,'Q',argument_count)
        self.call(0x6fd340,{'X0':call},limit=1000)
        return {'fixture':{'index':index,'argumentCount':argument_count,'argumentType':argument_type},
                'callbackValid':self.callback_valid,'storedIndex':self.r(menu+0x2c0,'i')[0],
                'playerClass':self.r(menu+0x2bc,'i')[0],
                'scope':'original callback including jump table and class write; numeric Flash input and absent preview-manager interfaces; no creation request or save'}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--library',type=Path,required=True)
    cli.add_argument('--output',type=Path,required=True)
    cli.add_argument('--evidence',type=Path,help='Checked evidence.json for original catalog/slot execution')
    args = cli.parse_args()
    from analyze_native_resources import NativeImage
    probe = CharacterProgressionProbe(NativeImage(args.library.read_bytes()))
    report = {'xp':[probe.xp_display_slice(level=l,xp=123,upgrade_xp=4567) for l in (1,54,55,56)],
              'learn':[probe.learn_request(s,r) for s,r in ((90,0),(90,1),(24,0),(0xffffffff,99))],
              'badCount':probe.learn_request(90,0,argument_count=1),
              'badType':probe.learn_request(90,0,argument_type=5)}
    report['creationClasses']=[probe.creation_class(i)for i in range(5)]
    report['invalidCreationClasses']=[probe.creation_class(i)for i in (-1,5)]
    if args.evidence:
        tables=json.loads(args.evidence.read_text())['tables']
        report['catalogs']=[probe.catalog(tables,profession=p,level=1) for p in range(1,6)]
        report['mageLevel10']=probe.catalog(tables,profession=2,level=10)
        report['missingProto']=probe.catalog(tables,profession=2,level=10,missing_proto_ids=(94,))
        report['counts']=probe.learned_counts([(1,0,1,0),(0,1,0,1)])
    output = local_output(args.output)/'native-probe.json'
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'output':str(output),'serverOrSavesUsed':False}))


if __name__ == '__main__':
    main()
