"""Bounded original default-display, part-input and feature-filename execution.

Table lookup/copy and C++ strings are host interfaces over verified source rows.
The model/part loader is a recording boundary, not successful GPU completion.
All actor inputs below are explicit fixtures; no activity message is fabricated.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from source_physics import SourcePhysics
from tutorial_npc_inventory import TABLES
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from skill_attachments import decode_ftable
from tutorial_map_geometry import local_output

PINS = {
    0x9dd5fc:(300,'b444c866432726c746aab60d0cded7632e55c27b271859e9878331751eb0e640'),
    0x9d40cc: (2940, 'dd24fc87627675410ec7097f02d21039428dfe45f00abebba5aa378e6bb3afff'),
    0x9d75e8: (472, 'e36e2d37b71b0ad1b2dad2f836519ba4baf8d9e3fa0e10e62cd3ccef95bee185'),
    0x9d88b0: (264, 'e95fe8ff31ef7e3825567438be0898446db9f846f2944be9d16e8346c27abfd3'),
    0x9e95a4: (932, '151817656e67e53564578fd14c0d63d98c57d6533324b49d627956cf0b180bff'),
}


class TutorialNPCProbe(SourcePhysics):
    LOOKUP = SourcePhysics.EXIT+0xe00

    def __init__(self, image, sources):
        for at, (size, sha) in PINS.items():
            if hashlib.sha256(image.read(at, size)).hexdigest() != sha:
                raise ValueError('Original NPC selection routine changed')
        super().__init__(image)
        from unicorn import UC_HOOK_CODE
        self.mode = None
        self.table_handles = {}
        self.table_by_handle = {}
        self.lookup_calls = []
        for at, name in {0xc992d0:'creature_appearance',0xc992d8: 'creaturedisplayinfo', 0xc992e8: 'creaturemodeldata',
                         0xc992e0: 'creaturedisplayinfoextra', 0xc99398: 'items',
                         0xc99280: 'creature_proto'}.items():
            key = 'entry' if name == 'items' else TABLES[name]
            parsed = decode_ftable(sources.read('tables/'+name+'.tbl'), key)
            handle, vt = self.alloc(32), self.alloc(32)
            self.w(handle, 'Q', vt)
            self.w(vt+0x18, 'Q', self.LOOKUP)
            self.table_handles[at] = handle
            self.table_by_handle[handle] = (name, parsed, {row[key]: row for row in parsed['rows']})
        for at in [*self.table_handles, self.LOOKUP, 0x9d4c48, 0x91661c, 0x335b50,0x9dd9b4]:
            self.uc.hook_add(UC_HOOK_CODE, self.hook, begin=at, end=at)

    def cpp_string(self, raw):
        at = self.alloc(24+len(raw)+1)
        self.w(at, '3Q', len(raw), len(raw), 1000)
        self.uc.mem_write(at+24, raw+b'\0')
        return at+24

    def pack_row(self, parsed, row):
        result = bytearray()
        for name, kind in zip(parsed['columns'], parsed['physicalTypes']):
            value = row[name]
            if kind == 's':
                result += struct.pack('<Q', self.cpp_string(value.encode()))
            else:
                result += struct.pack('<'+{'u':'I','k':'I','i':'i','f':'f','c':'B','h':'H'}[kind], value)
        return bytes(result)

    def hook(self, uc, at, size, data):
        if at in self.table_handles:
            self.set('X0', self.table_handles[at])
        elif at == self.LOOKUP:
            name, parsed, rows = self.table_by_handle[self.get('X0')]
            identifier = self.get('W1')
            self.lookup_calls.append({'table':name, 'id':identifier, 'found':identifier in rows})
            if identifier in rows:
                uc.mem_write(self.get('X2'), self.pack_row(parsed, rows[identifier]))
            self.set('W0', int(identifier in rows))
        elif at == 0x9d4c48 and self.mode == 'parts':
            value = self.get('X1')
            self.part_result = {'slots':list(self.r(value, '37I')),
                                'sourceColorAt9c':self.r(value+0x9c, 'I')[0],
                                'sourceColorAta0':self.r(value+0xa0, 'I')[0],
                                'modelId':self.get('W2')}
            self.set('PC', self.EXIT)
            return
        elif at == 0x91661c and self.mode == 'idle':
            self.default_display = self.r(self.get('X2'), 'I')[0]
            # The downstream model/part pipeline has a separate original-input
            # probe. This boundary never invents a model-loaded callback.
        elif at == 0x335b50 and self.mode == 'idle':
            self.idle_result = {'displayId':self.default_display,
                                'request':self.cstr(self.get('X1')).decode(),
                                'arg2':self.get('W2'), 'engineFlags':self.get('W3')}
            self.set('PC', self.EXIT)
            return
        elif at==0x9dd9b4 and self.mode=='entry':
            a=self.get('X0')
            self.entry_result={'keyAtF20':self.r(a+0xf20,'I')[0],
                               'appearanceKeyAtD2c':self.r(a+0xd2c,'I')[0],
                               'nameIdAtD30':self.r(a+0xd30,'I')[0],
                               'protoKeyAtDc8':self.r(a+0xdc8,'I')[0],
                               'defaultDisplayAtD40':self.r(a+0xd40,'I')[0],
                               'selectedDisplayAtD60':self.r(a+0xd60,'I')[0]}
            self.set('PC',self.EXIT);return
        elif at == 0x1de8970:
            raw = bytes(uc.mem_read(self.get('X1'), self.get('X2')))
            self.w(self.get('X0'), 'Q', self.cpp_string(raw))
        elif self.imports.get(at) in ('sprintf', 'snprintf'):
            bounded = self.imports[at] == 'snprintf'
            fmt_reg, arg_reg = (2, 3) if bounded else (1, 2)
            fmt = self.cstr(self.get('X'+str(fmt_reg)))
            if fmt == b'%s%s_%s_%s_%03d':
                args = [self.cstr(self.get('X'+str(arg_reg+i))).decode() for i in range(4)]
                n = self.get('W'+str(arg_reg+4))
                if n & 0x80000000: n -= 1<<32
                raw = (''.join(args[:2])+'_'+args[2]+'_'+args[3]+'_'+f'{n:03d}').encode()
            elif fmt == b'_%03d':
                n = self.get('W'+str(arg_reg))
                if n & 0x80000000: n -= 1<<32
                raw = ('_'+f'{n:03d}').encode()
            else:
                raise ValueError('Uncovered original NPC format')
            uc.mem_write(self.get('X0'), raw+b'\0')
            self.set('W0', len(raw))
        elif self.imports.get(at) == 'strncmp':
            n = self.get('X2')
            left, right = self.cstr(self.get('X0'))[:n], self.cstr(self.get('X1'))[:n]
            self.set('W0', ((left>right)-(left<right)) & 0xffffffff)
        else:
            return super().hook(uc, at, size, data)
        self.set('PC', self.get('X30'))

    def feature_path(self, feature, race, gender, face, value):
        output = self.alloc(512)
        length = self.call(0x9d88b0, {'W0':feature, 'W1':race, 'W2':gender,
                                    'W3':face & 0xffffffff, 'W4':value,
                                    'X5':output, 'W6':512})
        path = self.cstr(output).decode()
        if len(path.encode()) != length:
            raise ValueError('Original feature filename length differs')
        return path

    def model_race_gender(self, model_path):
        owner, holder, model, output = self.alloc(160), self.alloc(8), self.alloc(200), self.alloc(8)
        self.w(owner+0x40, 'Q', holder)
        self.w(holder, 'Q', model)
        self.w(model+0x90, 'Q', self.cpp_string(model_path.encode()))
        self.call(0x9d75e8, {'X0':owner, 'X1':output, 'X2':output+4})
        return list(self.r(output, '2i'))

    def parts(self, display_id):
        owner = self.alloc(256)
        self.mode, self.part_result, self.lookup_calls = 'parts', None, []
        self.call(0x9d40cc, {'X0':owner, 'W1':display_id, 'X4':self.cpp_string(b'idle')})
        self.mode = None
        if self.part_result is None:
            raise ValueError('Source part handoff was not reached')
        return {**self.part_result, 'tableLookups':list(self.lookup_calls),
                'actorOwnerSupplied':False, 'modelLoaderExecuted':False}

    def idle(self, entry, display_id):
        actor, model = self.alloc(0x2000), self.alloc(256)
        self.w(actor+0xd2c, 'I', entry)
        self.w(actor+0xd60, 'I', display_id)
        self.mode, self.idle_result, self.lookup_calls = 'idle', None, []
        self.call(0x9e95a4, {'X0':actor, 'X1':model})
        self.mode = None
        if self.idle_result is None:
            raise ValueError('Original default animation request was not reached')
        return {**self.idle_result, 'tableLookups':list(self.lookup_calls),
                'actorInputsAreFixtures':True, 'modelLoaderExecuted':False}

    def entry_selection(self,entry,display_override=0):
        actor,attrs=self.alloc(0x2000),self.alloc(0x1000)
        self.w(actor+0x18,'Q',attrs)
        self.call(0xa9995c,{'X0':attrs+0x280,'W1':display_override})
        self.mode,self.entry_result,self.lookup_calls='entry',None,[]
        result=self.call(0x9dd5fc,{'X0':actor,'W1':entry})
        self.mode=None
        return {'explicitAppearanceKey':entry,'explicitAttributeDisplayOverride':display_override,
                'result':self.entry_result,'originalReturnWhenNoHandoff':result if self.entry_result is None else None,
                'tableLookups':list(self.lookup_calls),'originalActivityMessageExecuted':False}


class TutorialNPCVisibilityProbe(SourcePhysics):
    """Execute source part-name mapping/replacement and two-channel counters.

    Original named model nodes are supplied as scene handles. Native scene
    lookup/attach/detach/property access remain explicit host boundaries.
    """
    ATTACH = SourcePhysics.EXIT+0xe40
    DETACH = ATTACH+4
    POSITION_GET = ATTACH+8
    POSITION_SET = ATTACH+12
    PINS = {
        0x32023c:(1056,'8db982e38b4ccbb9475332f780c1e21fcedb4069fa0e6cfe835420e4397d8ef0'),
        0x32165c:(3448,'6741a97b59840400b428dce5c3c18958df4cd9178ec384c10ab334e96dfcedb2'),
        0x321350:(780,'31eda5b3f2488ed5946f7089f46bf8da2f129c05a0094bc31d444b222a36f794'),
        0x9d64e8:(3892,'7c2f6212b83452dab73e3bfed09c33c937e65488867c98b75bc443c08d6c814b'),
    }

    def __init__(self, image):
        for at,(size,digest) in self.PINS.items():
            if hashlib.sha256(image.read(at,size)).hexdigest()!=digest:
                raise ValueError('Original NPC visibility routine changed')
        super().__init__(image)
        from unicorn import UC_HOOK_CODE
        self.names={};self.scene_events=[]
        for at in [0x1364108,0x320bdc,self.ATTACH,self.DETACH,self.POSITION_GET,self.POSITION_SET]:
            self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=at,end=at)
        self.model=self.alloc(0xe20)
        self.root=self.node('root')
        self.w(self.model+8,'Q',self.root)
        # Standard containers are provided empty; no resource callback is faked.
        for i in range(37):
            at=self.model+0x970+i*16;self.w(at,'2Q',at,at)

    def node(self,name,parent=0):
        at,vt=self.alloc(0x200),self.alloc(0x300)+32
        self.w(at,'Q',vt);self.w(at+8,'I',1000);self.w(vt-0x20,'q',0)
        for slot,callback in [(0xd0,self.ATTACH),(0x108,self.DETACH),
                              (0x170,self.POSITION_GET),(0x178,self.POSITION_SET)]:
            self.w(vt+slot,'Q',callback)
        self.w(at+0xe8,'Q',parent)
        self.names[at]=name
        return at

    def hook(self,uc,at,size,data):
        if at==0x1364108:
            name=self.cstr(self.get('X1')).decode()
            self.w(self.get('X8'),'Q',self.source_nodes.get(name,0))
        elif at==self.ATTACH:
            node=self.r(self.get('X1'),'Q')[0]
            self.w(node+0xe8,'Q',self.get('X0'))
            self.scene_events.append({'kind':'attach','name':self.names[node]})
        elif at==self.DETACH:
            node=self.get('X0');self.w(node+0xe8,'Q',0)
            self.scene_events.append({'kind':'detach','name':self.names[node]})
        elif at==self.POSITION_GET:self.set('X0',self.get('X0')+0x100)
        elif at==self.POSITION_SET:
            uc.mem_write(self.get('X0')+0x100,bytes(uc.mem_read(self.get('X1'),12)))
        elif at==0x320bdc:
            pass # Render/material refresh boundary; does not choose visibility.
        else:return super().hook(uc,at,size,data)
        self.set('PC',self.get('X30'))

    def fragment(self,start,end,regs=None,stack=()):
        from unicorn import UC_HOOK_CODE
        reached=[]
        def stop(uc,at,size,data):
            if at==end:reached.append(at);self.set('PC',self.EXIT)
        h=self.uc.hook_add(UC_HOOK_CODE,stop)
        try:self.call(start,regs,stack=stack)
        finally:self.uc.hook_del(h)
        if reached!=[end]:raise ValueError('Original fragment end absent')

    def bind_source_names(self,names):
        self.source_nodes={name:self.node(name,self.root) for name in names}
        self.fragment(0x3202ec,0x3203e8,{'X19':self.model})
        self.part_nodes={i:self.r(self.model+0xbf0+i*8,'Q')[0] for i in range(21)}
        return {i:self.names[node] for i,node in self.part_nodes.items() if node}

    def replace_feature(self,slot,name):
        node=self.node(name);holder=self.alloc(8);self.w(holder,'Q',node)
        self.fragment(0x32165c,0x321abc,{'X0':self.model,'W1':slot,'X2':holder})
        self.part_nodes[slot]=self.r(self.model+0xbf0+slot*8,'Q')[0]
        if self.part_nodes[slot]!=node:
            raise ValueError('Original feature replacement did not bind source slot')

    def apply_item_mask(self,flags0,flags1):
        values=[0]*35
        values[33]=flags0<<32;values[34]=flags1
        self.fragment(0x9d6d10,0x9d6d58,stack=values)
        mask=self.get('X9')
        self.call(0x321350,{'X0':self.model,'X1':0,'X2':mask})
        return mask

    def visibility(self):
        return {self.names[node]:bool(self.r(node+0xe8,'Q')[0])
                for node in [*self.source_nodes.values(),*self.part_nodes.values()] if node}


def recover(image, source=DEFAULT_SOURCE):
    sources = Sources(source)
    probe = TutorialNPCProbe(image, sources)
    entries=[probe.entry_selection(750),probe.entry_selection(750,742)]
    parts, idle = probe.parts(741), probe.idle(750,741)
    race_gender = probe.model_race_gender('model/npc/character/human/male/oc2_human_m_body_01.bdae')
    features = []
    face = parts['slots'][0]
    for kind, label in [(0,'Face'), (1,'Hair'), (2,'Beard')]:
        path = probe.feature_path(kind,*race_gender,face,parts['slots'][kind])
        features.append({'kind':kind, 'field':label, 'value':parts['slots'][kind],
                         'path':path, 'localCandidates':len(sources.candidates(path))})
        if sources.candidates(path): sources.read(path)
    return {'format':'oc2-tutorial-npc-native-selection-v1',
            'nativeSHA256':hashlib.sha256(image.data).hexdigest(),
            'entrySelectionFixtures':entries,
            'parts':parts, 'defaultIdle':idle, 'raceGender':race_gender, 'features':features,
            'sourceProofs':sources.proofs,
            'scope':'Original bounded default display/part producer and filename code over explicit verified-table fixtures; no live actor or successful resource callback.',
            'productionChanged':False, 'savesReadOrWritten':False}


if __name__ == '__main__':
    from analyze_native_resources import NativeImage
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--native', type=Path, default=Path(__file__).resolve().parents[1]/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so')
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    output = local_output(args.output)
    if output.exists(): cli.error('Choose new evidence output')
    report = recover(NativeImage(args.native.read_bytes()), args.source)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output':str(output),'features':len(report['features']),
                      'defaultRequest':report['defaultIdle']['request'],'productionChanged':False}))
