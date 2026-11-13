"""Execute original quest-zone containment, change dispatch and serialization.

Decoded source rows supply an explicit ordered table container. Positions and
socket flags are inspection inputs; no task state, live socket or save is used.
Entering a zone sends a trigger request, never a local objective completion.
"""
import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

from analyze_native_resources import NativeImage
from map_loading_evidence import Sources
from skill_attachments import decode_ftable
from source_physics import SourcePhysics
from tutorial_map_geometry import local_output
from tutorial_quest_request_probe import decoded_payload, fixture_integer, quest_schema

ROUTINES = {
    0xa071a4: (208,'66bbf3fe75743fc4bd30f2d400327d71925c85184889e4a30f2a35522f6a52dc'),
    0xa07274: (468,'d4a412e72c629f6c8f5b799ff87be87d33851d5a0785c20087aeeeb1d7578809'),
    0x3d60bc: (676,'22ca77e7ebbc84ca49aaf3e74952593c491b178a52e196ae678f0d2dd307a019'),
    0x1dcb628: (96,'df52b867b51bdc3a4327efc8646c41d5830be6e0cf6bd65a4ed412dd55d0ffde'),
    0x5a3528: (216,'6cc9ddbc9b7cdb2d5d7f8452a14c9e402fca94059d93a34c4fdc58853e9be621'),
    0x5a3600: (216,'f2b7d858fcc7febf53588dfeac5560f72357baac676b276c82772fa827de9189'),
    0x1d37868: (64,'78d549f1ad166acebd2e88ac257687c639a8a1a5fd2b8f877e942620d94c2a40'),
    0x1d379b8: (52,'185a4176d4ac59c128e4a7e6f55768eddfd27e0e5ca96a37a21eac48859fd062'),
    0x5ac05c: (204,'b30745adcaeae186809e811405582a405aa65203ef4b7d72b0e10db669e971a0'),
    0x1ab7a58: (144,'b9136404b77018ae18aa711398aa351351cffe609b31dde81e31a10c7ab81749'),
    0x1d37d58: (196,'dfee56dbcb04fa7338ca8f1e990bb7fa1c04e6283a799eb0c2d5dd577ec3f390'),
    0x1d37e1c: (176,'597a607b760d4922eb691d551175b068778aefbd1339f046809a47b700d864d5'),
}
ZONE_FIELDS = ('ID','map_id','x','y','z','radius','box_x','box_y','box_z','box_orientation')


def finite_f32(value):
    if type(value) not in (int,float):
        raise ValueError('Coordinates must be explicit finite float32 values')
    try:
        result, = struct.unpack('<f',struct.pack('<f',value))
    except (OverflowError,struct.error) as error:
        raise ValueError('Coordinates must fit finite float32') from error
    if not math.isfinite(result):
        raise ValueError('Coordinates must fit finite float32')
    return result


def zone_values(row):
    values = [row[name] for name in ZONE_FIELDS]
    for value,name in zip(values[:2],ZONE_FIELDS[:2]):
        fixture_integer(value,32,name)
    return values[:2]+[finite_f32(v) for v in values[2:]]


class QuestZoneProbe(SourcePhysics):
    TABLE_PROVIDER = 0xc99380
    SEND = 0x5802ec

    def __init__(self,image,rows,*,map_id=5):
        from unicorn import UC_HOOK_CODE
        for address,(size,digest) in ROUTINES.items():
            if hashlib.sha256(image.read(address,size)).hexdigest() != digest:
                raise ValueError('Original quest-zone routine differs')
        fixture_integer(map_id,32,'map_id')
        validated = [zone_values(row) for row in rows]
        if len({row[0] for row in validated}) != len(validated):
            raise ValueError('Duplicate source zone ID')
        super().__init__(image)
        self.schema = quest_schema(image); self.packets = []; self.serializations = 0
        self.hero = self.alloc(0x1800); self.root = self.alloc(0x400)
        self.table = self.alloc(0x100); self.network = self.alloc(0x100)
        self.socket = self.alloc(0x200)
        self.w(0x2528db0,'Q',self.root); self.w(self.root+0x278,'I',map_id)
        self.w(0x2528e30,'Q',self.network); self.w(self.network+8,'Q',self.socket)
        # A bounded socket-layout fixture stops before actual transport.
        self.w(self.socket+0x15c,'B',1); self.w(self.socket+0xd8,'Q',1)
        header = self.table+0x30; self.nodes = {}; ordered = sorted(validated)
        def tree(values,parent):
            if not values:
                return 0
            middle = len(values)//2; values_here = values[middle]
            node = self.alloc(0x50); self.nodes[values_here[0]] = node
            self.w(node,'I',1); self.w(node+8,'Q',parent)
            self.w(node+0x20,'I',values_here[0]); self.w(node+0x24,'II8f',*values_here)
            left = tree(values[:middle],node); right = tree(values[middle+1:],node)
            self.w(node+0x10,'2Q',left,right)
            return node
        root = tree(ordered,header)
        self.w(header,'I',0)
        self.w(header+8,'3Q',root,self.nodes[ordered[0][0]] if ordered else header,
               self.nodes[ordered[-1][0]] if ordered else header)
        for address in (self.TABLE_PROVIDER,self.SEND,0x5ac05c):
            self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=address,end=address)

    def hook(self,uc,address,size,data):
        if address == 0x5ac05c:
            self.serializations += 1
            return  # Observe; original byte-size, length prefix and serializer execute.
        if address == self.TABLE_PROVIDER:
            self.set('X0',self.table)
        elif address == self.SEND:
            packet = self.get('X1'); code = self.r(packet,'H')[0]
            stream = packet+8; length = self.r(stream+0x10,'Q')[0]
            begin,end,capacity = self.r(stream+0x18,'3Q')
            if code != 0x38 or not 4 <= length <= 1024 or not begin+length <= end <= capacity:
                raise ValueError('Unexpected original quest-zone packet framing')
            raw = bytes(uc.mem_read(begin,length)); declared = int.from_bytes(raw[:4],'little')
            if declared != length-4:
                raise ValueError('Original quest-zone length prefix differs')
            payload = raw[4:]
            self.packets.append({'id':code,'message':'C2GS_QuestZoneTrigger',
                                 'framedHex':raw.hex(),'hex':payload.hex(),
                                 'fields':decoded_payload(self.schema,'C2GS_QuestZoneTrigger',payload)})
            self.set('W0',1)
        elif self.imports.get(address) == '_ZNSt6vectorIhSaIhEE17_M_default_appendEm':
            # Host C++ vector storage only. Original application/protobuf code
            # determines the sizes and writes the length prefix and payload.
            vector = self.get('X0'); count = self.get('X1')
            begin,end,capacity = self.r(vector,'3Q')
            if count > 1024 or not begin <= end <= capacity:
                raise ValueError('Unbounded source quest-zone vector append')
            if end+count > capacity:
                replacement = self.alloc(end-begin+count)
                if end != begin:
                    uc.mem_write(replacement,bytes(uc.mem_read(begin,end-begin)))
                begin,end,capacity = replacement,replacement+end-begin,replacement+end-begin+count
            uc.mem_write(end,bytes(count)); self.w(vector,'3Q',begin,end+count,capacity)
        else:
            return super().hook(uc,address,size,data)
        self.set('PC',self.get('X30'))

    def contains(self,zone_id,position):
        fixture_integer(zone_id,32,'zone_id')
        position = self.checked_position(position)
        if zone_id not in self.nodes:
            raise ValueError('Unknown supplied source zone')
        self.w(self.hero+0x118,'3f',*position)
        return bool(self.call(0xa07274,{'X0':self.table,'X1':self.hero+0x118,
                                      'X2':self.nodes[zone_id]+0x24})&1)

    @staticmethod
    def checked_position(position):
        if not isinstance(position,(tuple,list)) or len(position) != 3:
            raise ValueError('Position must be three explicit finite floats')
        return [finite_f32(v) for v in position]

    def move_fixture(self,position,*,connected=True,suppressed=False,socket_present=True):
        position = self.checked_position(position)
        if any(type(flag) is not bool for flag in (connected,suppressed,socket_present)):
            raise ValueError('Socket flags must be explicit bool fixtures')
        before = self.r(self.hero+0x1508,'I')[0]
        self.w(self.hero+0x118,'3f',*position)
        self.w(self.socket+0x15c,'B',int(connected)); self.w(self.network+0x8b,'B',int(suppressed))
        self.w(self.socket+0xd8,'Q',int(socket_present))
        self.packets = []; self.serializations = 0
        self.call(0xa071a4,{'X0':self.hero})
        return {'positionFixture':list(position),'previousZone':before,
                'currentZone':self.r(self.hero+0x1508,'I')[0],
                'packets':list(self.packets),'originalSerializations':self.serializations,
                'socketFixture':{'connected':connected,'suppressed':suppressed,'socketPresent':socket_present},
                'objectiveCompletion':None,'liveServerOrSavesUsed':False}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--library',type=Path,required=True)
    cli.add_argument('--source',type=Path,required=True)
    cli.add_argument('--output',type=Path,required=True)
    args = cli.parse_args(); output = local_output(args.output)
    sources = Sources(args.source)
    table = decode_ftable(sources.read('tables/quests_zones.tbl'),'ID')
    engine = QuestZoneProbe(NativeImage(args.library.read_bytes()),table['rows'])
    selected = [341,252,644,253,256,1819,255,257,258]
    by_id = {row['ID']:row for row in table['rows']}
    cases = [engine.move_fixture([by_id[z][axis] for axis in ('x','y','z')]) for z in selected]
    cases += [engine.move_fixture([0,0,0]),engine.move_fixture([0,0,0])]
    report = {'format':'oc2-original-quest-zone-fixtures-v1','tableProof':table['verification'],
              'sourceRows':len(table['rows']),'cases':cases,'acceptedQuest':None,'completedQuest':None,
              'productionUpdated':False,'scope':'Original ordered-zone iteration, rotated-box test, state-change dispatch, protobuf construction and serialization; decoded source table container, positions, socket flags, allocation/libc and recording transport are host adapters.'}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'cases':len(cases),'packets':sum(len(r['packets']) for r in cases),
                      'acceptedQuest':None,'productionUpdated':False}))


if __name__ == '__main__':
    main()
