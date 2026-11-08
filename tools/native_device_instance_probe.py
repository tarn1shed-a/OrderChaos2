"""Execute original device conditions, XML query fragments and instance gates.

Inputs and parsed-list layouts are fixtures. String/C-library and spec lookup
callbacks supply storage and explicit data. No original process, XML parser,
resource I/O, factory, renderer or gameplay implementation is supplied here.
"""
import struct, ctypes
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn import arm64_const as reg

class NativeDeviceInstanceProbe:
    BASE = 0x10000000
    EXIT = 0x300000f0

    def __init__(self, image):
        from device_instance_evidence import verify_native
        verify_native(image)
        self.uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        self.image = image
        for a, n in [(0xc58000, 0x5000), (0x4cb000, 0x1000), (0xa61000, 0x1000), (0x3bc000, 0x1000), (0x1eef000, 0x1000), (0x2044000, 0x1000), (0x1dfd000, 0x1000), (0x1f3d000, 0x1000)]:
            self.uc.mem_map(a, n)
            self.uc.mem_write(a, image.read(a, n))
        for a, n in [(self.BASE, 0x200000), (0x20000000, 0x10000), (0x2504000, 0x3000), (0x2528000, 0x1000), (self.EXIT & ~4095, 4096), (0x29e000, 0x2000), (0x2a0000, 0x2000), (0x1de5000, 0x5000)]:
            self.uc.mem_map(a, n)
        for a in [0x1de7400, 0x1de5f68, 0xc5b730, 0x1de9d0c, 0x1de9b88, 0x1de81c4, 0x29e3c0, 0x2a0840, 0x2a0c90, 0x2a0870, 0x4cb934, 0x4cbca0]:
            self.uc.hook_add(UC_HOOK_CODE, self.hook, begin=a, end=a)
        self.libc = ctypes.CDLL(None)
        self.libc.atoi.argtypes = [ctypes.c_char_p]
        self.libc.atoi.restype = ctypes.c_int
        self.libc.atof.argtypes = [ctypes.c_char_p]
        self.libc.atof.restype = ctypes.c_double
        # Strings end before the parsed level-list arena at +0x140000.
        # The admission probe's raw ITM input starts separately at +0x150000.
        self.cursor = self.BASE + 0x10000
        self.empty = self.s('')
        self.w(0x2504cc8, 'Q', self.empty - 24)
        self.w(0x2505ca0, 'Q', self.BASE + 0x2000)
        self.w(0x2506aa8, 'Q', 0x2528220)
        self.w(0x2528220, 'Q', self.BASE + 0x3000)
        self.w(0x2528db0, 'Q', self.BASE + 0x4000)
        self.w(self.BASE + 0x4000 + 0x1b8, 'Q', self.BASE + 0x5000)

    def set(self, k, v):
        self.uc.reg_write(getattr(reg, 'UC_ARM64_REG_' + k), v & (1 << 64) - 1)

    def get(self, k):
        return self.uc.reg_read(getattr(reg, 'UC_ARM64_REG_' + k))

    def w(self, a, f, *v):
        self.uc.mem_write(a, struct.pack('<' + f, *v))

    def r(self, a, f):
        return struct.unpack('<' + f, self.uc.mem_read(a, struct.calcsize('<' + f)))

    def c(self, a):
        b = bytearray()
        while len(b) < 4096:
            part = bytes(self.uc.mem_read(a, min(64, 4096 - (a & 4095))))
            a += len(part)
            if b'\x00' in part:
                return bytes(b) + part.split(b'\x00')[0]
            b.extend(part)
        raise ValueError('Unbounded C string fixture')

    def s(self, s):
        b = s.encode() if isinstance(s, str) else s
        a = self.cursor
        self.cursor = a + 24 + len(b) + 1 + 15 & ~15
        if self.cursor >= self.BASE + 0x140000:
            raise ValueError('String fixture arena exhausted')
        self.w(a, 'QQq', len(b), len(b), 1000000000)
        self.uc.mem_write(a + 24, b + b'\x00')
        return a + 24

    def hstr(self, a):
        return self.c(self.r(a, 'Q')[0])

    def registers(self):
        for i in range(31):
            self.set('X' + str(i), 0)
        self.set('SP', 0x20008000)
        self.set('X29', 0x20008000)
        self.set('X30', self.EXIT)

    def run(self, start, end=None):
        self.uc.emu_start(start, self.EXIT if end is None else end, count=40000)
        return self.get('PC')

    def hook(self, uc, a, n, d):
        if a == 0x4cbca0:
            if self.mode == 'query':
                uc.emu_stop()
                return
            raise ValueError('Unexpected query return')
        if a == 0x4cb934:
            if self.mode != 'gate':
                return
            model = self.c(self.get('X1')).decode()
            ident = self.get('W2')
            level = self.level_delegate(model, ident)
            self.set('W0', level)
        elif a == 0x1de7400:
            b = self.hstr(self.get('X0'))
            needle = self.c(self.get('X1'))[:self.get('X3')]
            pos = b.find(needle, self.get('X2'))
            self.set('X0', pos)
        elif a == 0x1de5f68:
            b = self.hstr(self.get('X1'))
            start = self.get('X2')
            length = self.get('X3')
            self.w(self.get('X0'), 'Q', self.s(b[start:] if length == (1 << 64) - 1 else b[start:start + length]))
        elif a == 0xc5b730:
            k = self.hstr(self.get('X1')).decode()
            kind, value = self.spec.get(k, (0, ''))
            if kind not in (0, 1, 2, 3, 4):
                raise ValueError('Uncovered property value type in explicit fixture')
            at = self.get('X8')
            uc.mem_write(at, bytes(32))
            self.w(at + 0x18, 'I', kind)
            self.w(at + 0x10, 'Q', self.empty)
            if kind == 1:
                self.w(at, 'B', int(value))
            elif kind == 2:
                self.w(at + 4, 'i', value)
            elif kind == 3:
                self.w(at + 8, 'd', value)
            elif kind == 4:
                self.w(at + 0x10, 'Q', self.s(value))
        elif a == 0x1de9d0c:
            self.w(self.get('X0'), 'Q', self.r(self.get('X1'), 'Q')[0])
        elif a == 0x1de9b88:
            pass
        elif a in [0x29e3c0, 0x1de81c4, 0x2a0840]:
            x = self.c(self.get('X0')) if a == 0x29e3c0 else self.hstr(self.get('X0')) if a == 0x1de81c4 else bytes(uc.mem_read(self.get('X0'), self.get('X2')))
            y = self.c(self.get('X1')) if a != 0x2a0840 else bytes(uc.mem_read(self.get('X1'), self.get('X2')))
            self.set('W0', (x > y) - (x < y))
        elif a == 0x2a0c90:
            self.set('W0', self.libc.atoi(self.c(self.get('X0'))) & 0xffffffff)
        elif a == 0x2a0870:
            self.set('D0', struct.unpack('<Q', struct.pack('<d', self.libc.atof(self.c(self.get('X0')))))[0])
        else:
            raise ValueError('Unexpected callback')
        self.set('PC', self.get('X30'))

    def condition(self, expr, spec):
        if not isinstance(expr, str) or len(expr.encode()) > 1024 or '\x00' in expr:
            raise ValueError('Bounded expression fixture required')
        self.registers()
        self.spec = spec
        self.mode = 'condition'
        self.w(self.BASE + 0x8000, 'Q', self.s(expr))
        self.set('X0', self.BASE + 0x9000)
        self.set('X1', self.BASE + 0x8000)
        pc = self.run(0xc5b854)
        if pc != self.EXIT:
            raise ValueError(hex(pc))
        return self.get('W0')

    def configure_levels(self, models, overrides):
        self.object = self.BASE + 0x5000
        self.node_cursor = self.BASE + 0x140000

        def allocate(n):
            at = self.node_cursor
            self.node_cursor += n
            if self.node_cursor > self.BASE + 0x150000:
                raise ValueError('Parsed level-list fixture exceeds reserved arena')
            return at

        def chain(head, rows):
            previous = head
            for payload in rows:
                node = allocate(32)
                self.w(previous, 'Q', node)
                self.w(node + 16, 'Q', payload)
                previous = node
            self.w(previous, 'Q', head)
        model_payloads = []
        for row in models:
            at = allocate(32)
            self.w(at, 'Qi', self.s(row['name']), row['level'])
            strings = []
            for value in row['exceptions']:
                holder = allocate(8)
                self.w(holder, 'Q', self.s(value))
                strings.append(holder)
            head = at + 16
            prev = head
            for holder in strings:
                node = allocate(32)
                self.w(prev, 'Q', node)
                self.w(node + 16, 'Q', self.r(holder, 'Q')[0])
                prev = node
            self.w(prev, 'Q', head)
            model_payloads.append(at)
        chain(self.object, model_payloads)
        payloads = []
        for row in overrides:
            at = allocate(16)
            self.w(at, 'Qi', self.s(row['id']), row['level'])
            payloads.append(at)
        chain(self.object + 16, payloads)

    def lookup(self, model, ident):
        if not 0 <= ident <= 0x7fffffff:
            raise ValueError('Audited positive signed-ID fixture range only')
        self.registers()
        self.mode = 'query'
        self.set('X21', self.object)
        self.set('X20', self.s(model))
        self.set('X28', self.empty - 24)
        number = str(ident if ident < 2 ** 31 else ident - 2 ** 32).encode()
        self.uc.mem_write(self.get('X29') - 0x78, number + b'\x00')
        pc = self.run(0x4cb980, 0x4cb9b8)
        if pc == 0x4cbca0:
            return self.get('W22')
        if pc != 0x4cb9b8:
            raise ValueError('Unknown ID query branch')
        self.w(self.get('SP') + 0x28, 'Q', self.s(str(ident)))
        pc = self.run(0x4cbb00, 0x4cbc14)
        if pc != 0x4cbc14:
            raise ValueError('Unknown model query branch')
        return self.get('W22')

    def load_itm(self, raw):
        if raw[:4] != b'AITM' or len(raw) > 0x80000:
            raise ValueError('ITM fixture outside bounds')
        self.uc.mem_write(self.BASE + 0x150000, raw)
        self.building = self.BASE + 0x1000
        count, models = struct.unpack_from('<2I', raw, 16)
        base = self.BASE + 0x150000
        self.record_count = count
        self.w(self.building + 0x40, 'Q', base + 24)
        self.w(self.building + 0x48, 'Q', base + 24 + count * 76 + 4)
        self.w(self.building + 0x50, 'I', models)
        self.w(base + 0x10, 'I', count)

    def admission(self, index, detail, layer, dynamic_ids=()):
        if not 0 <= index < self.record_count or not 0 <= detail <= 4 or (not 0 <= layer <= 5) or (len(dynamic_ids) > 100):
            raise ValueError('Instance-gate fixture outside audited bounds')
        self.registers()
        self.mode = 'gate'
        self.w(self.BASE + 0x2000, 'I', detail)
        self.w(self.BASE + 0x3000 + 0x54, 'I', layer)
        vec = self.BASE + 0x7000
        self.w(0x2528e10, 'Q', vec)
        self.w(vec + 0x10, '2Q', vec + 0x100, vec + 0x100 + len(dynamic_ids) * 4)
        for i, value in enumerate(dynamic_ids):
            self.w(vec + 0x100 + i * 4, 'I', value)
        self.set('X24', self.building)
        self.set('X22', index)
        self.set('X8', self.BASE + 0x150000)
        stop = []

        def end(uc, a, n, d):
            stop.append(a)
            uc.emu_stop()
        handles = [self.uc.hook_add(UC_HOOK_CODE, end, begin=a, end=a) for a in [0xa61a1c, 0xa61ef8, 0xa61acc]]
        try:
            pc = self.run(0xa619ac)
        finally:
            for h in handles:
                self.uc.hook_del(h)
        if not stop:
            raise ValueError('Admission fragment exceeded bound')
        return {0xa61acc: 'admittedBeforeTypeFactory', 0xa61a1c: 'dynamicIdRejected', 0xa61ef8: 'detailOrLevelRejected'}[pc]
