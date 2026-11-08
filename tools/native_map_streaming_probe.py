"""Run three bounded original ARM64 fragments with explicit synthetic inputs.

Only offset-table allocation is stubbed. No game process, scheduler, network,
asset loading, actual device configuration or residency state is reproduced.
"""
import struct


class NativeMapStreamingProbe:
    BASE = 0x10000000
    EXIT = 0x300000f0

    def __init__(self, image):
        from map_streaming_evidence import verify_native
        verify_native(image)
        from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
        from unicorn import arm64_const
        self.reg = arm64_const
        self.uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        for at, size in [(0x35b000, 0x1000), (0x366000, 0x1000)]:
            self.uc.mem_map(at, size)
            self.uc.mem_write(at, image.read(at, size))
        for at, size in [(self.BASE, 0x10000), (0x20000000, 0x10000),
                         (0x30000000, 0x1000), (0x29f000, 0x1000),
                         (0x2527000, 0x1000)]:
            self.uc.mem_map(at, size)
        self.uc.hook_add(UC_HOOK_CODE, self._allocation, begin=0x29fbb0, end=0x29fbb0)
        self.uc.hook_add(UC_HOOK_CODE, lambda uc, a, n, d: uc.emu_stop(),
                         begin=0x366e94, end=0x366e94)

    def set(self, name, value):
        self.uc.reg_write(getattr(self.reg, 'UC_ARM64_REG_'+name), value)

    def get(self, name):
        return self.uc.reg_read(getattr(self.reg, 'UC_ARM64_REG_'+name))

    def write(self, at, fmt, *values):
        self.uc.mem_write(at, struct.pack('<'+fmt, *values))

    def read(self, at, fmt):
        return struct.unpack('<'+fmt, self.uc.mem_read(at, struct.calcsize('<'+fmt)))

    def reset(self):
        for at, size in [(self.BASE, 0x10000), (0x20000000, 0x10000), (0x2527000, 0x1000)]:
            self.uc.mem_write(at, bytes(size))
        for i in range(31):
            self.set(f'X{i}', 0)
        self.set('SP', 0x20008000)
        self.set('X30', self.EXIT)
        self.allocations = []

    def _allocation(self, uc, at, size, data):
        requested = self.get('X0')
        if self.allocations or requested > 0xc000:
            raise ValueError('Probe allocation outside bounded fixture')
        self.allocations.append(requested)
        self.set('X0', self.BASE+0x1000)
        self.set('PC', self.get('X30'))

    def offsets(self, radius):
        if type(radius) is not int or not 0 <= radius <= 4:
            raise ValueError('Probe scope: explicit radii 0..4 only')
        self.reset()
        self.write(0x2527a70, 'i', radius)
        self.uc.emu_start(0x35b204, self.EXIT, count=20000)
        if self.get('PC') != self.EXIT:
            raise ValueError('Original offset generator exceeded instruction bound')
        count, = self.read(0x2527a88, 'I')
        pointer, = self.read(0x2527a80, 'Q')
        return {'inputRadius': radius, 'allocationBytes': self.allocations,
                'offsets': [list(self.read(pointer+i*8, '2i')) for i in range(count)]}

    def center(self, x, z, shifts=(3, 3)):
        if len(shifts) != 2 or any(type(v) is not int or not 0 <= v <= 8 for v in shifts):
            raise ValueError('Probe scope: bounded explicit shift inputs')
        self.reset()
        self.write(self.BASE+0x100, '3f', x, 0, z)
        self.write(self.BASE+0x4c, '2I', *shifts)
        self.set('X19', self.BASE)
        self.set('X1', self.BASE+0x100)
        self.set('W2', 1)
        self.uc.emu_start(0x366cc4, 0x366d14, count=40)
        if self.get('PC') != 0x366d14:
            raise ValueError('Original center fragment exceeded bounds')
        def signed(value):
            return value-(1 << 32) if value & (1 << 31) else value
        return [signed(self.get('W24')), signed(self.get('W25'))]

    def retain_distance_branch(self, center, tile, radius):
        """Distance branch only; phase/force/task status inputs are excluded."""
        if type(radius) is not int or not 0 <= radius <= 4:
            raise ValueError('Probe scope: explicit radii 0..4 only')
        self.reset()
        self.write(self.BASE+8, '2i', *tile)
        self.set('X9', self.BASE)
        self.set('W26', center[0] & 0xffffffff)
        self.set('W24', center[1] & 0xffffffff)
        self.set('W21', radius+1)
        self.uc.emu_start(0x366e5c, 0x366e84, count=30)
        pc = self.get('PC')
        if pc not in (0x366e84, 0x366e94):
            raise ValueError('Original retention fragment exceeded bounds')
        return {'branchAddress': hex(pc), 'distanceAllowsRetain': pc == 0x366e94}
