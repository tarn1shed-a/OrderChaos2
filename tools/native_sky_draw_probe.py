"""Original scene append/pass dispatch with synthetic memory and callbacks.

Only bounded allocations are simulated. Mutex and pass callbacks are logged;
their bodies and all GL/driver operations are deliberately not executed.
"""
import struct

from scene_sky_draw import verify_native


class NativeSkyDrawProbe:
    BASE = 0x10000000

    def __init__(self, image):
        verify_native(image)
        from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
        from unicorn import arm64_const
        self.reg = arm64_const; self.uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        for at, size in [(0x12f7000, 0x1000), (0x12f9000, 0x1000), (0x1364000, 0x1000)]:
            self.uc.mem_map(at, size); self.uc.mem_write(at, image.read(at, size))
        for at, size in [(self.BASE, 0x10000), (0x20000000, 0x10000), (0x3c0000, 0x1000)]: self.uc.mem_map(at, size)
        for at in [0x3c0fbc, 0x3c0fe8, 0x13649e4, 0x13649f4, self.BASE+0xff00,
                   *[self.BASE+0xf000+s for s in (0x88, 0x98, 0x60, 0x58, 0x90, 0xb0, 0xa0)]]:
            self.uc.hook_add(UC_HOOK_CODE, self._hook, begin=at, end=at)

    def write(self, at, fmt, *values): self.uc.mem_write(at, struct.pack('<'+fmt, *values))
    def read(self, at, fmt): return struct.unpack('<'+fmt, self.uc.mem_read(at, struct.calcsize('<'+fmt)))
    def set(self, name, value): self.uc.reg_write(getattr(self.reg, 'UC_ARM64_REG_'+name), value)
    def get(self, name): return self.uc.reg_read(getattr(self.reg, 'UC_ARM64_REG_'+name))

    def reset(self):
        self.uc.mem_write(self.BASE, bytes(0x10000)); self.uc.mem_write(0x20000000, bytes(0x10000))
        for i in range(31): self.set(f'X{i}', 0)
        for i in range(32): self.set(f'Q{i}', 0)
        self.set('SP', 0x20008000); self.set('X30', self.BASE+0xff00)
        self.events = []; self.allocations = []; self.frees = []

    def _hook(self, uc, at, size, data):
        if at == self.BASE+0xff00: uc.emu_stop(); return
        if at == 0x3c0fbc:
            size = self.get('X0')
            if size > 0x8000 or self.get('W1') != 0 or self.allocations: raise ValueError('Out-of-scope probe allocation')
            self.allocations.append(size); self.set('X0', self.BASE+0x6000)
        elif at == 0x3c0fe8: self.frees.append(self.get('X0'))
        elif at in (0x13649e4, 0x13649f4):
            self.events.append({'boundary': 'enter' if at == 0x13649e4 else 'leave'})
        else:
            slot = at-self.BASE-0xf000
            if self.get('X0') != self.BASE: raise ValueError('Pass callback receiver changed')
            event = {'slot': slot}
            if slot in (0x88, 0xa0): event['driver'] = self.get('X1')
            if slot == 0xa0: event['bit'] = self.get('W2')
            if slot == 0x60: event['node'] = self.get('X1')
            if slot == 0x58:
                event['referenceAddress'] = self.get('X1'); event['node'] = self.read(self.get('X1'), 'Q')[0]
            self.events.append(event)
        self.set('PC', self.get('X30'))

    def append(self, nodes, capacity, node):
        if not len(nodes) <= capacity <= 256: raise ValueError('Probe only accepts bounded explicit container states')
        self.reset(); begin = self.BASE+0x2000 if capacity else 0
        self.write(self.BASE+0x10, '3Q', begin, begin+8*len(nodes), begin+8*capacity)
        if nodes: self.write(begin, 'Q'*len(nodes), *nodes)
        self.set('X0', self.BASE); self.set('X1', node)
        self.uc.emu_start(0x12f9ea8, self.BASE+0xff04, count=1000)
        if self.get('PC') != self.BASE+0xff00: raise ValueError('Scene append probe exceeded bounds')
        begin, end, limit = self.read(self.BASE+0x10, '3Q'); count = (end-begin)//8
        return {'nodes': list(self.read(begin, 'Q'*count)), 'capacity': (limit-begin)//8,
                'allocated': bool(self.allocations), 'allocationBytes': self.allocations, 'freedOld': bool(self.frees)}

    def scene_pass(self, mode, skip_word=0, clear_word=1, node=0x12345678):
        if mode not in ('direct', 'reference'): raise ValueError('Unknown pass mode')
        self.reset(); table = self.BASE+0x9000; driver = self.BASE+0x4000
        self.write(self.BASE, 'Q', table); self.write(self.BASE+0x40, 'Q', driver)
        self.write(self.BASE+8, 'Q', 0x87654321)
        for slot in (0x88, 0x98, 0x60, 0x58, 0x90, 0xb0, 0xa0):
            self.write(table+slot, 'Q', self.BASE+0xf000+slot)
        self.set('X0', self.BASE); self.set('W2', skip_word); self.set('W3', clear_word)
        if mode == 'direct': self.set('X1', node)
        else:
            self.write(self.BASE+0x3000, 'Q', node); self.set('X1', self.BASE+0x3000)
        self.uc.emu_start(0x12f78b8 if mode == 'direct' else 0x12f797c, self.BASE+0xff04, count=150)
        if self.get('PC') != self.BASE+0xff00: raise ValueError('Scene pass probe exceeded bounds')
        return {'events': self.events, 'finalPassWord': self.read(self.BASE+0x26c, 'I')[0]}
