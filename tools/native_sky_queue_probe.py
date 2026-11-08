"""Original technique resolver and bounded queue3/8 insertion instructions.

Explicit material/driver/technique states and node getter results are fixtures.
The original 40-byte distance branch stops at its frontier, before insertion.
No original process, GPU, queue sorting or resource loading is executed.
"""
from native_sky_mesh_probe import NativeSkyMeshProbe
from scene_sky_queue import verify_native, technique_selection, queue_route, word


class NativeSkyQueueProbe:
    BASE = NativeSkyMeshProbe.BASE

    def __init__(self, image):
        verify_native(image)
        self.p = NativeSkyMeshProbe(image)
        from unicorn import UC_HOOK_CODE
        for at in [0x13ed140, 0x1503508, 0x1503598, 0x3c0fbc, 0x3c0fe8, 0x12f3acc,
                   *[self.BASE+0x1f200+x for x in (0, 0x20, 0x40, 0x60)]]:
            self.p.uc.hook_add(UC_HOOK_CODE, self._hook, begin=at, end=at)

    def reset(self):
        self.p.uc.mem_write(self.BASE, bytes(0x20000)); self.p.uc.mem_write(0x20000000, bytes(0x10000))
        self.p.registers(); self.locks = []; self.selectors = 0; self.allocations = []; self.frees = []
        self.getters = []; self.frontier = False

    def _hook(self, uc, at, size, data):
        p, b = self.p, self.BASE
        if at == 0x13ed140:
            if p.get('X0') != b+0x4000 or p.get('X1') != b+0x3000:
                raise ValueError('Technique selector arguments changed')
            self.selectors += 1; return
        if at in (0x1503508, 0x1503598):
            if p.get('X0') != b+0x7048: raise ValueError('Technique manager mutex receiver changed')
            self.locks.append(at)
        elif at == 0x3c0fbc:
            amount = p.get('X0')
            if not 0 < amount <= 4096 or p.get('W1') != 0 or self.allocations:
                raise ValueError('Queue allocation outside bounded fixture')
            self.allocations.append(amount); p.set('X0', b+0x11000)
        elif at == 0x3c0fe8:
            if p.get('X0') != b+0x6000: raise ValueError('Unexpected old queue buffer release')
            self.frees.append(p.get('X0'))
        elif at == 0x12f3acc:
            self.frontier = True; uc.emu_stop(); return
        else:
            if p.get('X0') != b+0x2000: raise ValueError('Queue node getter receiver changed')
            slot = at-b-0x1f200; self.getters.append(slot)
            if slot == 0: p.set('W0', self.node_priority)
            elif slot == 0x20:
                if p.get('X1') != self.part: raise ValueError('Queue part getter argument changed')
                p.set('W0', self.tag)
            elif slot == 0x40: p.set('W0', self.node210)
            elif slot == 0x60: p.set('W0', self.node200)
            else: raise ValueError('Unknown queue node getter')
        p.set('PC', p.get('X30'))

    def technique_fixture(self, base, variation, packed, profile, stride, remap):
        expected = technique_selection(base, variation, packed, profile, stride, remap)
        p, b = self.p, self.BASE
        p.write(b+0x4008, 'Q', b+0x5000); p.write(b+0x4010, 'B', base); p.write(b+0x4018, 'B', variation)
        p.write(b+0x5018, 'H', 0); p.write(b+0x501c, 'H', packed)
        p.write(b+0x32f8, 'Q', b+0x7000); p.write(b+0x3320, 'I', profile)
        p.write(b+0x7028, 'Q', b+0x8000); p.write(b+0x70a0, 'I', stride)
        p.write(b+0x8000, 'Q', b+0x8100); p.write(b+0x8120, 'Q', b+0x8200 if remap is not None else 0)
        if remap is not None: p.uc.mem_write(b+0x8200, remap)
        return expected

    def select(self, base, variation, packed, profile, stride, remap):
        self.reset(); self.technique_fixture(base, variation, packed, profile, stride, remap)
        self.p.set('X0', self.BASE+0x4000); self.p.set('X1', self.BASE+0x3000)
        self.p.uc.emu_start(0x13ed140, self.BASE+0x1ff04, count=150)
        if self.p.get('PC') != self.BASE+0x1ff00: raise ValueError('Technique probe exceeded bounds')
        result = self.p.get('W0')
        return {'returnWord': result, 'queueIndex': result & 0xff, 'lockCalls': len(self.locks)}

    def insert(self, code, material=False, technique_flags=0, pass_byte_e2=0, scene_byte_2a8=0,
               node_word_210=0, node_word_200=0, old=(), capacity=0, part=1, context_word=0,
               priority=0x7fffffff, node_priority=7, tag=9, lookup=(0, 0, 0, 0xffffffff, 0, None)):
        route = queue_route(code, material, technique_flags, pass_byte_e2, scene_byte_2a8, node_word_210, node_word_200)
        word(part, 64); word(context_word, 64); word(priority, 32); word(node_priority, 32); word(tag, 32)
        if type(capacity) is not int or not len(old) <= capacity <= 16:
            raise ValueError('Invalid bounded queue container')
        if not route['completed'] and old: raise ValueError('Distance frontier only supports an empty fixture')
        self.reset(); self.technique_fixture(*lookup)
        p, b = self.p, self.BASE
        self.part, self.node_priority, self.tag = part, node_priority, tag
        self.node210, self.node200 = node_word_210, node_word_200
        p.write(b+0x38, 'Q', b+0x3000); p.write(b+0x2a8, 'B', scene_byte_2a8)
        p.write(b+0x2000, 'Q', b+0xa000)
        for slot, callback in [(0x1e8, 0), (0x58, 0x20), (0x210, 0x40), (0x200, 0x60)]:
            p.write(b+0xa000+slot, 'Q', b+0x1f200+callback)
        p.write(b+0x5030, 'Q', b+0xb000)
        for i in range(256): p.write(b+0xb008+24*i, 'Q', b+0xd000)
        p.write(b+0xd006, 'B', technique_flags); p.write(b+0xd020, 'Q', b+0xe000)
        p.write(b+0xe0e2, 'B', pass_byte_e2)
        p.write(b+0x4f00, 'Q', b+0x4000 if material else 0)
        offset, size = route['queueOffset'], route['recordBytes']
        fmt = '2Q' if code == 8 else '3Q2I'
        if offset is not None and route['completed']:
            begin = b+0x6000 if capacity else 0
            p.write(b+offset, '3Q', begin, begin+len(old)*size, begin+capacity*size)
            for i, row in enumerate(old): p.write(begin+i*size, fmt, *row)
        p.set('X0', b); p.set('X1', b+0x2000); p.set('X2', context_word); p.set('X3', b+0x4f00)
        p.set('X4', part); p.set('W5', code); p.set('W7', priority)
        p.uc.emu_start(0x12f368c, b+0x1ff04, count=3000)
        if not self.frontier and p.get('PC') != b+0x1ff00: raise ValueError('Queue insertion exceeded bounds')
        records, actual_capacity = [], capacity
        if offset is not None and route['completed']:
            begin, end, limit = p.read(b+offset, '3Q'); actual_capacity = (limit-begin)//size
            records = [list(p.read(at, fmt)) for at in range(begin, end, size)]
        return {'completed': not self.frontier, 'records': records, 'capacity': actual_capacity,
                'returnWord': None if self.frontier else p.get('W0'), 'selectorCalls': self.selectors,
                'lockCalls': len(self.locks), 'allocationBytes': self.allocations, 'freedOld': bool(self.frees),
                'queueOffset': offset}
