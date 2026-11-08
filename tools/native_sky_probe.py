"""Execute bounded sky numeric fragments in isolated synthetic ARM64 memory.

No game process, graphics calls, archive loading or native host code executes.
The upstream model bounds and environment samples are explicit probe inputs.
"""
import struct

from scene_sky import verify_native


class NativeSkyProbe:
    BASE = 0x10000000

    def __init__(self, image):
        verify_native(image)
        from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM
        from unicorn import arm64_const
        self.reg = arm64_const; self.uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        for at, size in [(0xa63000, 0x4000), (0x4c0000, 0x1000),
                         (0x1e62000, 0x1000), (0x1df7000, 0x1000)]:
            self.uc.mem_map(at, size); self.uc.mem_write(at, image.read(at, size))
        for at, size in [(self.BASE, 0x10000), (0x20000000, 0x10000),
                         (0x2504000, 0x1000), (0x2528000, 0x1000)]: self.uc.mem_map(at, size)

    def write(self, at, fmt, *values): self.uc.mem_write(at, struct.pack('<'+fmt, *values))
    def read(self, at, fmt): return struct.unpack('<'+fmt, self.uc.mem_read(at, struct.calcsize('<'+fmt)))
    def set(self, name, value): self.uc.reg_write(getattr(self.reg, 'UC_ARM64_REG_'+name), value)
    def get(self, name): return self.uc.reg_read(getattr(self.reg, 'UC_ARM64_REG_'+name))
    def scalar(self, name, value): self.set(name, struct.unpack('<I', struct.pack('<f', value))[0])
    def floating(self, name): return struct.unpack('<f', struct.pack('<I', self.get(name)))[0]

    def reset(self):
        self.uc.mem_write(self.BASE, bytes(0x10000)); self.uc.mem_write(0x20000000, bytes(0x10000))
        for i in range(31): self.set(f'X{i}', 0)
        for i in range(32): self.set(f'Q{i}', 0)
        self.set('SP', 0x20008000); self.set('X29', 0x20009000)

    def constructor(self):
        self.reset(); self.set('X19', self.BASE)
        self.uc.emu_start(0xa63818, 0xa63864, count=32)
        return {'parameters': list(self.read(self.BASE+0x30, '9f')),
                'fog': list(self.read(self.BASE+0x68, '2f'))}

    def scale(self, coordinates):
        self.reset(); self.set('X19', self.BASE)
        self.write(0x20009000-0x80, '6f', *coordinates)
        self.write(self.BASE+0x10, 'Q', self.BASE+0x2000)
        self.write(self.BASE+0x2000, 'Q', self.BASE+0x3000)
        self.write(0x2528db0, 'Q', self.BASE+0x4000)
        self.write(self.BASE+0x41c0, 'Q', self.BASE+0x5000)
        self.write(self.BASE+0x5018, 'Q', self.BASE+0x6000)
        self.uc.emu_start(0xa64de8, 0xa64eb4, count=80)
        return self.floating('S8')

    def distance(self, near, half):
        self.reset(); self.write(0x20008018, '2f', near, half)
        self.set('X21', 0x2528000)  # Source page register established by the caller.
        self.scalar('S8', 1); self.scalar('S9', .1)
        self.uc.emu_start(0x4c0588, 0x4c05b0, count=20)
        return list(self.read(0x20008018, '2f'))

    def cache(self, distance, near, far, saturation):
        self.reset(); self.set('X0', self.BASE)
        for name, at, values in [('X1', 0x10001000, distance), ('X2', 0x10002000, near),
                                 ('X3', 0x10003000, far), ('X4', 0x10004000, [saturation])]:
            self.set(name, at); self.write(at, 'f'*len(values), *values)
        self.uc.emu_start(0xa65f4c, 0xa65fac, count=32)
        return list(self.read(self.BASE+0x30, '9f'))
