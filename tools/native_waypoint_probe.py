"""Run the original cached waypoint lookup, with explicit host tree/libc fixtures.

This does not run the table loader, a path follower, server scripts or EnterMap.
No fixture flag or record ID is promoted to an observed Android runtime input.
"""
import hashlib
import struct
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn import arm64_const as reg

PINS = {
    # This constructor fragment is checked statically, not executed by the probe.
    0xc8b61c: (48, 'd3cf14c6bcc4b90e6d084774e9db8d204160cd1b9f5b998fb6880f6c82061a0e'),
    0xc99230: (8, '095bb56e13b6dfde16ade0b592279392884c282a7c7810cb58472b839de552de'),
    0xc9fa18: (196, '00d36608776cf2466981fcd247408453a0773e82cd7627bccdce9d95623b4cb6'),
}


class NativeWaypointProbe:
    BASE = 0x60000000
    EXIT = BASE + 0x1000
    DELEGATE = BASE + 0x2000
    TABLE = BASE + 0x3000
    MANAGER = BASE + 0x4000
    OUTPUT = BASE + 0x5000

    def __init__(self, image):
        for at, (size, digest) in PINS.items():
            if hashlib.sha256(image.read(at, size)).hexdigest() != digest:
                raise ValueError('Original waypoint lookup differs')
        rels = {r['r_offset']: r['r_addend'] for r in
                image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
        if rels.get(0x242a008+0x18) != 0xc9fa18:
            raise ValueError('Original waypoint lookup vtable differs')
        self.uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        for page in (0xc99000, 0xc9f000, 0x2a1000):
            self.uc.mem_map(page, 0x1000)
            self.uc.mem_write(page, image.read(page, 0x1000))
        self.uc.mem_map(self.BASE, 0x100000)
        self.calls = []
        self.uc.hook_add(UC_HOOK_CODE, self.hook)

    def write(self, at, fmt, *values):
        self.uc.mem_write(at, struct.pack('<'+fmt, *values))

    def hook(self, uc, at, size, data):
        if at == self.EXIT:
            uc.emu_stop()
        elif at == 0x2a1e50:  # Explicit libc memcpy adapter, not a recovered body.
            dst, src, count = [uc.reg_read(getattr(reg, 'UC_ARM64_REG_X'+str(i))) for i in range(3)]
            if count != 76:
                raise ValueError('Original record copy size differs')
            uc.mem_write(dst, bytes(uc.mem_read(src, count)))
            self.calls.append({'kind': 'memcpy-adapter', 'bytes': count})
            uc.reg_write(reg.UC_ARM64_REG_PC, uc.reg_read(reg.UC_ARM64_REG_X30))
        elif at == self.DELEGATE:
            self.calls.append({'kind': 'uncached-boundary-not-executed'})
            uc.reg_write(reg.UC_ARM64_REG_X0, 0)
            uc.reg_write(reg.UC_ARM64_REG_PC, uc.reg_read(reg.UC_ARM64_REG_X30))

    def call(self, at, args):
        for i, value in enumerate(args):
            self.uc.reg_write(getattr(reg, 'UC_ARM64_REG_X'+str(i)), value)
        self.uc.reg_write(reg.UC_ARM64_REG_SP, self.BASE+0xff000)
        self.uc.reg_write(reg.UC_ARM64_REG_X30, self.EXIT)
        self.uc.emu_start(at, self.EXIT+4, count=5000)
        if self.uc.reg_read(reg.UC_ARM64_REG_PC) != self.EXIT:
            raise ValueError('Original lookup did not return within probe bound')
        return self.uc.reg_read(reg.UC_ARM64_REG_X0)

    def records(self, rows):
        self.uc.mem_write(self.TABLE, bytes(0x100))
        self.write(self.MANAGER+0x38, 'Q', self.TABLE)
        self.write(self.TABLE+0xf0, 'B', 1)
        self.write(self.TABLE+0x50, 'Q', len(rows))
        nodes = []
        for index, (identifier, raw) in enumerate(sorted(rows.items())):
            if len(raw) != 76 or struct.unpack_from('<I', raw)[0] != identifier:
                raise ValueError('Explicit source record identity differs')
            node = self.BASE+0x10000+index*0x80
            self.uc.mem_write(node, bytes(0x80))
            self.write(node+0x20, 'I', identifier)
            self.uc.mem_write(node+0x24, raw)
            nodes.append(node)
        def tree(items):
            if not items:
                return 0
            middle = len(items)//2
            node = items[middle]
            self.write(node+0x10, '2Q', tree(items[:middle]), tree(items[middle+1:]))
            return node
        self.write(self.TABLE+0x38, 'Q', tree(nodes))
        vtable = self.BASE+0x6000
        self.write(self.TABLE, 'Q', vtable)
        self.write(vtable+0x58, 'Q', self.DELEGATE)
        self.calls = []

    def lookup(self, identifier, cached=True):
        self.write(self.TABLE+0xf0, 'B', int(cached))
        self.uc.mem_write(self.OUTPUT, bytes([0xa5])*76)
        self.calls = []
        table = self.call(0xc99230, [self.MANAGER])
        if table != self.TABLE:
            raise ValueError('Original manager accessor differs')
        found = self.call(0xc9fa18, [table, identifier, self.OUTPUT])
        return {'found': found, 'record': bytes(self.uc.mem_read(self.OUTPUT, 76)),
                'calls': list(self.calls)}
