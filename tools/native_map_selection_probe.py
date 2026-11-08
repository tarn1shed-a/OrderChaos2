"""Bounded execution of original mask/phase fragments with explicit fixtures.

The constant initializer's std::map operator[] is a storage stub. Lookup trees
are synthetic layouts populated from captured constants or original source rows.
Neither the profile selector nor the full game/map loader is executed.
"""
import struct


class NativeMapSelectionProbe:
    BASE = 0x10000000
    EXIT = 0x300000f0

    def __init__(self, image):
        from map_selection_evidence import verify_native
        verify_native(image)
        from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
        from unicorn import arm64_const
        self.reg = arm64_const
        self.uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        for at in (0x352000, 0x357000, 0x367000, 0x58a000, 0xc99000):
            self.uc.mem_map(at, 0x1000)
            self.uc.mem_write(at, image.read(at, 0x1000))
        self.fixture_ranges = [(self.BASE, 0x40000), (0x20000000, 0x10000),
                               (0x2528000, 0x1000)]
        for at, size in self.fixture_ranges+[(0x30000000, 0x1000), (0x2a0000, 0x1000)]:
            self.uc.mem_map(at, size)
        self.uc.hook_add(UC_HOOK_CODE, self._collect_slot, begin=0x2a0890, end=0x2a0890)

    def set(self, name, value):
        self.uc.reg_write(getattr(self.reg, 'UC_ARM64_REG_'+name), value)

    def get(self, name):
        return self.uc.reg_read(getattr(self.reg, 'UC_ARM64_REG_'+name))

    def write(self, at, fmt, *values):
        self.uc.mem_write(at, struct.pack('<'+fmt, *values))

    def read(self, at, fmt):
        return struct.unpack('<'+fmt, self.uc.mem_read(at, struct.calcsize('<'+fmt)))

    def reset(self):
        for at, size in self.fixture_ranges:
            self.uc.mem_write(at, bytes(size))
        for i in range(31):
            self.set(f'X{i}', 0)
        self.set('SP', 0x20008000)
        self.set('X30', self.EXIT)
        self.slots = []

    def run(self, start, end):
        self.uc.emu_start(start, end, count=30000)
        if self.get('PC') != end:
            raise ValueError('Original selection fragment exceeded instruction bound')

    def _collect_slot(self, uc, at, size, data):
        if self.get('X0') != 0x2528570 or len(self.slots) >= 20:
            raise ValueError('Initializer map collector outside audited scope')
        key, = self.read(self.get('X1'), 'Q')
        address = self.BASE+len(self.slots)*8
        self.slots.append((key, address))
        self.set('X0', address)
        self.set('PC', self.get('X30'))

    def mask_constants(self):
        self.reset()
        self.run(0x357b2c, self.EXIT)
        def signed16(v):
            return v-65536 if v & 32768 else v
        return [{'key': key, 'mapId': key >> 48, 'phase': (key >> 32) & 65535,
                 'tile': [signed16((key >> 16) & 65535), signed16(key & 65535)],
                 'mask': self.read(at, 'I')[0]} for key, at in self.slots]

    def mask_lookup(self, constants, map_id, x, z, phase):
        if len(constants) > 20:
            raise ValueError('Only captured initializer-sized mask tables are audited')
        self.reset()
        ordered = sorted(constants, key=lambda row: row['key'])
        node_base = self.BASE+0x4000
        for i, row in enumerate(ordered):
            node = node_base+i*0x40
            self.write(node+0x18, 'Q', node+0x40 if i+1 < len(ordered) else 0)
            self.write(node+0x20, 'QI', row['key'], row['mask'])
        self.write(0x2528580, 'Q', node_base if ordered else 0)
        self.write(0x2528db0, 'Q', self.BASE+0x2000)
        self.write(self.BASE+0x2278, 'I', map_id)
        self.set('X19', self.BASE+0x1000)
        self.set('W21', x & 0xffffffff)
        self.set('W20', z & 0xffffffff)
        self.set('W22', phase)
        self.run(0x3520e0, 0x35217c)
        return self.read(self.BASE+0x1014, 'I')[0]

    def phase_select(self, rows, map_id, x, z, active_ids):
        if len(rows) > 100 or len(active_ids) > 31 or any(not 1 <= i <= 31 for i in active_ids):
            raise ValueError('Phase fixture outside recovered bit/record bounds')
        self.reset()
        manager, table, context = self.BASE+0x1000, self.BASE+0x2000, self.BASE+0x3000
        self.write(0x2528dc8, 'Q', manager)
        self.write(0x2528db0, 'Q', context)
        self.write(context+0x278, 'I', map_id)
        self.write(manager+0x70, 'Q', table)
        ordered = sorted(rows, key=lambda row: row['id'])
        node_base = self.BASE+0x4000
        self.write(table+0x38, 'Q', node_base if ordered else 0)
        for i, row in enumerate(ordered):
            if len(row['tiles']) > 100:
                raise ValueError('Source phase tile count outside record')
            node = node_base+i*0x400
            self.write(node+0x18, 'Q', node+0x400 if i+1 < len(ordered) else 0)
            self.write(node+0x20, 'I', row['id'])
            self.write(node+0x30, 'I', row['mapId'])
            self.write(node+0x38, 'I', len(row['tiles']))
            for j, tile in enumerate(row['tiles']):
                self.write(node+0x3c+j*8, '2i', *tile)
        vector = self.BASE+0x30000
        for i, phase in enumerate(active_ids):
            self.write(vector+i*4, 'I', phase)
        if not active_ids:
            # Original empty-list branch begins earlier than the table loop.
            self.set('X27', vector)
            start = 0x367124
        else:
            start = 0x367134
        self.set('X21', vector)
        self.set('W28', len(active_ids))
        self.set('X20', 0x2528000)
        self.set('W22', x & 0xffffffff)
        self.set('W23', z & 0xffffffff)
        self.run(start, 0x36720c if active_ids else 0x367218)
        return self.get('W3')

    def input_phase_word(self, word, available_bytes=4):
        """Execute the original bounded u32 reader/store, without naming its packet."""
        if not 0 <= available_bytes <= 4:
            raise ValueError('Only the single-word input fragment is audited')
        self.reset()
        buffer, payload, holder, player = [self.BASE+i*0x2000 for i in range(4)]
        self.write(payload, 'I', word)
        self.write(buffer+0x20, '2Q', payload, payload+available_bytes)
        self.write(0x2528df8, 'Q', holder)
        self.write(holder+0x68, 'Q', player)
        self.set('X1', buffer)
        self.run(0x58ae2c, self.EXIT)
        return {'playerPhaseWord': self.read(player+0x14e0, 'I')[0],
                'bufferCursor': self.read(buffer+0x10, 'Q')[0]}
