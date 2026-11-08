"""Original visitor and root-list aggregation with synthetic callback results.

Node gates, bounds, frustum tests and render-controller submission are stubs.
No scene tree, real game process, GPU, host native code or network is used.
"""
import struct

from scene_sky_collection import verify_native


class NativeSkyCollectionProbe:
    BASE = 0x10000000

    def __init__(self, image):
        verify_native(image)
        from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
        from unicorn import arm64_const
        self.reg = arm64_const; self.uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        for at, size in [(0x1324000, 0x1000), (0x1341000, 0x1000), (0x12f1000, 0x1000)]:
            self.uc.mem_map(at, size); self.uc.mem_write(at, image.read(at, size))
        for at, size in [(self.BASE, 0x10000), (0x20000000, 0x10000), (0xa6f000, 0x1000), (0x1df7000, 0x1000)]:
            self.uc.mem_map(at, size)
        self.uc.mem_write(0x1df7000, image.read(0x1df7000, 0x1000))
        for at in [self.BASE+0xff00, 0xa6ff68, *[self.BASE+0xf000+off for off in (0, 0x20, 0x40, 0x60, 0x80, 0xa0)]]:
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
        self.gate_calls = 0; self.frustum_calls = 0; self.submitted = False; self.root_calls = []

    def _hook(self, uc, at, size, data):
        if at == self.BASE+0xff00: uc.emu_stop(); return
        if at == self.BASE+0xf000:
            if self.get('X0') != self.BASE+0x1000 or self.get('X1') != self.BASE+0x2000 or self.gate_calls >= 2:
                raise ValueError('Unexpected source node gate call')
            self.set('W0', self.gates[self.gate_calls]); self.gate_calls += 1
        elif at == self.BASE+0xf020:
            if self.get('X0') != self.BASE+0x1000: raise ValueError('Node mode receiver changed')
            self.set('W0', self.mode)
        elif at == self.BASE+0xf040:
            if self.get('X0') != self.BASE+0x3000: raise ValueError('Camera frustum receiver changed')
            self.set('X0', self.BASE+0x7000)
        elif at == self.BASE+0xf060:
            if self.get('X0') != self.BASE+0x1000 or self.get('X1') != self.BASE+0x2000 or not 0x20000000 <= self.get('X2') < 0x20010000:
                raise ValueError('Node bounds receiver/output changed')
            self.write(self.get('X2'), '6f', 0, 0, 0, 1, 1, 1)
        elif at == 0xa6ff68:
            if self.get('X0') != self.BASE+0x7000 or self.get('W1') != self.mode: raise ValueError('Frustum consumer arguments changed')
            self.frustum_calls += 1; self.set('W0', self.frustum_result)
        elif at == self.BASE+0xf080:
            if self.get('X0') != self.BASE+0x4000 or self.get('X1') != self.BASE+0x2000:
                raise ValueError('Render-controller submission receiver changed')
            self.submitted = True
        elif at == self.BASE+0xf0a0:
            reference = self.get('X2'); index = (reference-self.BASE-0x2000)//8
            if self.get('X0') != self.BASE or self.get('X1') != self.BASE+0x3000 or not 0 <= index < len(self.rows):
                raise ValueError('Root aggregation argument changed')
            self.root_calls.append(reference); self.write(self.BASE+0xc, '3I', *self.rows[index])
        self.set('PC', self.get('X30'))

    def visit(self, gates, mode, frustum_result=1, counts=(0, 0), fast=False, adapter=False):
        self.reset(); self.gates = gates; self.mode = mode; self.frustum_result = frustum_result
        self.write(self.BASE, 'Q', self.BASE+0x3000); self.write(self.BASE+8, '2I', *counts)
        self.write(self.BASE+0x1000, 'Q', self.BASE+0xa000)
        self.write(self.BASE+0x1120, 'Q', self.BASE+0x4000)
        for off, callback in [(0xa0, 0), (0x188, 0x20), (0x88, 0x60)]:
            self.write(self.BASE+0xa000+off, 'Q', self.BASE+0xf000+callback)
        self.write(self.BASE+0x3000, 'Q', self.BASE+0xb000)
        self.write(self.BASE+0xb2f8, 'Q', self.BASE+0xf040)
        self.write(self.BASE+0x4000, 'Q', self.BASE+0xc000)
        self.write(self.BASE+0xc020, 'Q', self.BASE+0xf080)
        self.write(self.BASE+0x5000, '2Q', self.BASE+0x1000, self.BASE+0x2000)
        self.write(self.BASE+0x6008, 'Q', self.BASE)
        if fast or adapter:
            self.set('X0', self.BASE+0x6000); self.set('X1', self.BASE+0x1000); self.set('X2', self.BASE+0x2000)
            start = 0x13246d8 if fast else 0x13412e4
        else:
            self.set('X0', self.BASE+0x5000); self.set('X1', self.BASE); start = 0x1324234
        self.uc.emu_start(start, self.BASE+0xff04, count=150)
        if self.get('PC') != self.BASE+0xff00: raise ValueError('Visitor probe exceeded bounds')
        return {'submitted': self.submitted, 'counts': list(self.read(self.BASE+8, '2I')),
                'gateCalls': self.gate_calls, 'frustumCalls': self.frustum_calls, 'returnWord': self.get('W0')}

    def aggregate(self, rows):
        if len(rows) > 64: raise ValueError('Probe root count exceeded')
        self.reset(); self.rows = rows
        self.write(self.BASE, 'Q', self.BASE+0xd000); self.write(self.BASE+0xd020, 'Q', self.BASE+0xf0a0)
        self.write(self.BASE+0x1000, '2Q', self.BASE+0x2000, self.BASE+0x2000+8*len(rows))
        self.set('X0', self.BASE); self.set('X1', self.BASE+0x3000); self.set('X2', self.BASE+0x1000)
        self.uc.emu_start(0x12f15b4, self.BASE+0xff04, count=1500)
        if self.get('PC') != self.BASE+0xff00: raise ValueError('Root aggregation probe exceeded bounds')
        return {'counts': list(self.read(self.BASE+0xc, '3I')), 'references': self.root_calls}
