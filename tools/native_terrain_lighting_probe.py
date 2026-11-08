"""Bounded original terrain instructions with synthetic memory and CPU inputs.

No game process, network, GL driver, source assets or host native code is run.
Macro text allocation is stubbed; only the original numeric flag writes run.
Water cache cleanup and full AABB construction are outside these fragments.
"""
import struct

from terrain_lighting import verify_native


class NativeTerrainLightingProbe:
    BASE = 0x10000000

    def __init__(self, image):
        verify_native(image)
        from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
        from unicorn import arm64_const
        self.reg = arm64_const; self.uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        for address, size in [(0x350000, 0xa000), (0x550000, 0x2000), (0x34d000, 0x1000), (0x1411000, 0x1000)]:
            self.uc.mem_map(address, size); self.uc.mem_write(address, image.read(address, size))
        for address, size in [(self.BASE, 0x10000), (0x20000000, 0x10000),
                              (0x250a000, 0x1000), (0x2528000, 0x1000), (0x2527000, 0x1000)]:
            self.uc.mem_map(address, size)
        self.uc.hook_add(UC_HOOK_CODE, self._macro, begin=0x550db4, end=0x550db4)
        for address in (0x3599b0, 0x359a4c):
            self.uc.hook_add(UC_HOOK_CODE, lambda uc, a, size, data: uc.emu_stop(), begin=address, end=address)

    def write(self, at, fmt, *v): self.uc.mem_write(at, struct.pack('<'+fmt, *v))
    def read(self, at, fmt): return struct.unpack('<'+fmt, self.uc.mem_read(at, struct.calcsize('<'+fmt)))
    def set(self, name, value): self.uc.reg_write(getattr(self.reg, 'UC_ARM64_REG_'+name), value)
    def get(self, name): return self.uc.reg_read(getattr(self.reg, 'UC_ARM64_REG_'+name))
    def scalar(self, name, value): self.set(name, struct.unpack('<I', struct.pack('<f', value))[0])

    def reset(self):
        self.uc.mem_write(self.BASE, bytes(0x10000)); self.uc.mem_write(0x20000000, bytes(0x10000))
        for index in range(31): self.set(f'X{index}', 0)
        for index in range(32): self.set(f'Q{index}', 0)
        self.set('SP', 0x20008000); self.macro_flags = []

    def _macro(self, uc, address, size, data):
        self.macro_flags.append(self.get('W0'))
        self.set('PC', self.get('X30'))  # Do not execute the string formatter.

    def loaded_flags(self, flags):
        self.reset(); self.write(self.BASE+0x1000, 'I', flags)
        self.set('X26', self.BASE+0x1000); self.set('X23', self.BASE); self.set('X15', 0xa8)
        self.uc.emu_start(0x3592a4, 0x3592bc, count=32)
        return self.read(self.BASE+0x70, 'I')[0]

    def water_flags(self, flags, height, minimum):
        self.reset(); self.write(self.BASE+0x1000, 'Q', self.BASE)
        self.write(self.BASE+0x70, 'If', flags, height); self.write(self.BASE+0x3c, 'f', minimum)
        self.set('X28', self.BASE+0x1000)
        self.uc.emu_start(0x359968, 0x359a50, count=100)
        if self.get('PC') not in (0x3599b0, 0x359a4c): raise ValueError('Water probe exceeded fragment bounds')
        return self.read(self.BASE+0x70, 'I')[0]

    def macros(self, flags, blend_color=False):
        self.reset(); self.set('X19', self.BASE); self.write(self.BASE+0x70, 'I', flags)
        self.write(0x250aee4, 'B', int(blend_color))
        self.uc.emu_start(0x3509dc, 0x3509fc, count=200)
        if len(self.macro_flags) != 2: raise ValueError('Unexpected terrain macro calls')
        return self.macro_flags

    def color(self, rgb565):
        self.reset(); self.write(self.BASE+0x1000, 'H', rgb565)
        self.write(self.BASE+0x20, 'Q', self.BASE+0x2000)
        self.set('X19', self.BASE); self.set('X12', self.BASE+0x1000)
        self.uc.emu_start(0x359744, 0x359780, count=32)
        return list(self.read(self.BASE+0x2028, '4B'))

    def normalized(self, semantic):
        self.reset(); self.set('X22', semantic)
        self.uc.emu_start(0x1411b10, 0x1411b2c, count=16)
        return self.get('W3')

    def light_vectors(self, base, common, generic, model):
        self.reset()
        for i, value in enumerate(base): self.scalar(f'S{11+i}', value)
        self.write(0x20008014, '3f', model, generic, common)
        self.uc.emu_start(0x34d2fc, 0x34d36c, count=40)
        return {name: list(self.read(address, '3f')) for name, address in
                [('common', 0x2527834), ('generic', 0x2527840), ('model', 0x252784c)]}
