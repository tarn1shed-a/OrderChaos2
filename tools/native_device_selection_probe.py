"""Original GPU selector/priority and update-order experiment with library adapters.

The proprietary branch bodies execute original instructions. Parsed JSON trees,
std::map/list/string storage, value access/copies and diagnostics are adapters.
Parameter writes stop at c4a6d4 and are recorded, not applied to a live client.
"""
from native_device_instance_probe import NativeDeviceInstanceProbe
from unicorn import UC_HOOK_CODE

class NativeDeviceSelectionProbe(NativeDeviceInstanceProbe):

    def __init__(self, image):
        super().__init__(image)
        for a, n in [(0xc48000, 0x3000), (0xc4e000, 0x1000), (0xc51000, 0x2000), (0x1da9000, 0x1000), (0x1987000, 0x4000), (0x1dcb000, 0x1000), (0x1eee000, 0x1000), (0x1fad000, 0x1000), (0x1f0c000, 0x1000), (0x1e03000, 0x1000), (0x1fec000, 0x1000)]:
            self.uc.mem_map(a, n)
            self.uc.mem_write(a, image.read(a, n))
        self.obj = self.BASE + 0x9000
        self.arena = self.BASE + 0x150000
        self.containers = {}
        self.maps = {}
        self.events = []
        self.NULL = self.json(None)
        self.w(0x2506ed8, 'Q', self.NULL)
        for a in [0xc4ee20, 0x1987b1c, 0x1988394, 0x19880bc, 0x1987e88, 0x1988170, 0x1988518, 0x1de639c, 0x1de73b8, 0x1de9e8c, 0x1de8b74, 0xc51988, 0xc524b8, 0x2a0c80, 0x29ec30, 0x2a12f0, 0x29f630, 0x2a0350, 0x29f0f0, 0x1da989c, 0x29fbb0, 0x29e010, 0x2a1e50, 0x2a0180, 0x1de8970, 0x1de6df8, 0x1989130, 0x1988ff0, 0xc4a6d4]:
            self.uc.hook_add(UC_HOOK_CODE, self.extra, begin=a, end=a)

    def alloc(self, n):
        a = self.arena
        self.arena = a + n + 15 & ~15
        if self.arena >= self.BASE + 0x1ff000:
            raise ValueError('JSON/storage fixture exhausted')
        self.uc.mem_write(a, bytes(n))
        return a

    def json(self, v):
        at = self.alloc(24)
        if isinstance(v, (dict, list)):
            isdict = isinstance(v, dict)
            items = sorted(v.items()) if isdict else list(enumerate(v))
            container = self.alloc(48)
            header = container + 8
            self.w(at, 'QH', container, 7 if isdict else 6)
            self.w(container + 0x28, 'Q', len(items))
            children = []
            for k, value in items:
                n = self.alloc(80)
                self.w(n + 0x20, 'QI', self.s(k) if isdict else 0, 1 if isdict else k)
                child = self.json(value)
                self.uc.mem_write(n + 0x30, bytes(self.uc.mem_read(child, 24)))
                children.append((k, n))

            def tree(nodes, parent):
                if not nodes:
                    return 0
                mid = len(nodes) // 2
                n = nodes[mid][1]
                self.w(n + 8, 'Q', parent)
                self.w(n + 16, '2Q', tree(nodes[:mid], n), tree(nodes[mid + 1:], n))
                return n
            root = tree(children, header)
            self.w(header, 'I', 0)
            self.w(container + 0x10, '3Q', root, children[0][1] if children else header, children[-1][1] if children else header)
            self.containers[container] = {k: n + 0x30 for k, n in children}
        elif v is None:
            self.w(at + 8, 'H', 0)
        elif isinstance(v, str):
            self.w(at, 'QH', self.s(v), 4)
        elif isinstance(v, bool):
            self.w(at, 'QH', int(v), 5)
        elif isinstance(v, int):
            self.w(at, 'qH', v, 1)
        elif isinstance(v, float):
            self.w(at, 'dH', v, 3)
        else:
            raise ValueError(type(v))
        return at

    def jstring(self, at):
        kind = self.r(at + 8, 'H')[0] & 255
        if kind == 4:
            return self.c(self.r(at, 'Q')[0])
        if kind == 1:
            return str(self.r(at, 'q')[0]).encode()
        raise ValueError('Uncovered JSON string conversion type ' + str(kind))

    def cell(self, base, key, kind):
        k = (base, key)
        if k not in self.maps:
            cell = self.alloc(24)
            if kind == 'string':
                self.w(cell, 'Q', self.empty)
            elif kind == 'list':
                self.w(cell, '2Q', cell, cell)
            self.maps[k] = (cell, kind)
        cell, actual = self.maps[k]
        if actual != kind:
            raise ValueError('Container adapter type mismatch')
        return cell

    def extra(self, uc, a, n, d):
        if a == 0xc4ee20:
            container = self.r(self.get('X0'), 'Q')[0]
            key = self.hstr(self.get('X1')).decode()
            self.set('X0', self.containers.get(container, {}).get(key, self.NULL))
        elif a == 0x1987b1c:
            uc.mem_write(self.get('X0'), bytes(24))
        elif a == 0x1988394:
            if self.r(self.get('X1') + 8, 'H')[0] != 0:
                raise ValueError('Only null equality is adapted')
            self.set('W0', int(self.r(self.get('X0') + 8, 'H')[0] == 0))
        elif a == 0x19880bc:
            pass
        elif a in [0x1989130, 0x1988ff0]:
            self.set('X0', self.containers[self.r(self.get('X0'), 'Q')[0]][self.get('W1')])
        elif a == 0xc4a6d4:
            value = self.get('X2')
            kind = self.r(value + 8, 'H')[0] & 255
            if kind not in (1, 3, 4, 5):
                raise ValueError('Uncovered JSON parameter type at recorded setter boundary')
            data = self.r(value, 'q')[0] if kind == 1 else self.r(value, 'd')[0] if kind == 3 else self.c(self.r(value, 'Q')[0]).decode() if kind == 4 else bool(self.r(value, 'Q')[0]) if kind == 5 else None
            self.events.append([self.hstr(self.get('X1')).decode(), data])
            self.set('W0', 1)
        elif a in [0x1987e88, 0x1988170]:
            uc.mem_write(self.get('X0'), bytes(uc.mem_read(self.get('X1'), 24)))
        elif a == 0x1988518:
            self.w(self.get('X8'), 'Q', self.s(self.jstring(self.get('X0'))))
        elif a == 0x1de6df8:
            self.w(self.get('X0'), 'Q', self.s(self.hstr(self.get('X0')) + self.hstr(self.get('X1'))))
        elif a == 0x1de8970:
            self.w(self.get('X0'), 'Q', self.s(self.c(self.get('X1'))[:self.get('X2')]))
        elif a == 0x1de639c:
            self.w(self.get('X0'), 'Q', self.s(self.c(self.get('X1'))))
        elif a in [0x1de73b8, 0x1de9e8c]:
            self.w(self.get('X0'), 'Q', self.r(self.get('X1'), 'Q')[0])
        elif a == 0x1de8b74:
            b = self.hstr(self.get('X0'))
            pos = self.get('X1')
            self.w(self.get('X0'), 'Q', self.s(b[:pos] + self.c(self.get('X2'))[:self.get('X3')] + b[pos:]))
            self.set('X0', self.get('X0'))
        elif a == 0xc51988:
            self.set('X0', self.BASE + 0xf000)
        elif a == 0xc524b8:
            pass
        elif a in [0x2a0c80, 0x2a0350, 0x29ec30, 0x2a12f0, 0x29f630]:
            kind = 'int' if a == 0x29ec30 else 'list' if a in [0x2a12f0, 0x29f630] else 'string'
            self.set('X0', self.cell(self.get('X0'), self.hstr(self.get('X1')).decode(), kind))
        elif a in [0x29f0f0, 0x29fbb0]:
            self.set('X0', self.alloc(self.get('X0')))
        elif a == 0x29e010:
            self.set('X0', len(self.c(self.get('X0'))))
        elif a == 0x2a1e50:
            uc.mem_write(self.get('X0'), bytes(uc.mem_read(self.get('X1'), self.get('X2'))))
        elif a == 0x2a0180:
            pass
        elif a == 0x1da989c:
            node, head = (self.get('X0'), self.get('X1'))
            last = self.r(head + 8, 'Q')[0]
            self.w(node, '2Q', head, last)
            self.w(last, 'Q', node)
            self.w(head + 8, 'Q', node)
        else:
            raise ValueError(hex(a))
        self.set('PC', self.get('X30'))

    def select(self, profile_data, spec, adjust=0):
        if not -10 <= adjust <= 10:
            raise ValueError('Bounded explicit GPU adjustment required')
        self.registers()
        self.spec = spec
        self.mode = 'selector'
        source = self.json({'GPU': profile_data})
        self.w(self.obj + 0x190, 'Q', self.BASE + 0x8000)
        cell = self.cell(self.obj + 0x128, 'GPU', 'int')
        self.w(cell, 'i', adjust)
        self.w(self.BASE + 0x8100, 'Q', self.s('GPU'))
        self.set('X0', self.obj)
        self.set('X1', source)
        self.set('X2', self.BASE + 0x8100)
        self.set('X8', self.BASE + 0x8200)
        self.uc.emu_start(0xc48524, self.EXIT, count=500000)
        if self.get('PC') != self.EXIT:
            raise ValueError('Selector instruction bound')
        return self.hstr(self.BASE + 0x8200).decode()

    def updates(self, profile_data, selected):
        self.events = []
        node = self.json(profile_data)
        self.w(self.obj + 0x198, 'Q', self.BASE + 0xe000)
        self.registers()
        self.set('X0', self.obj)
        self.set('X1', node)
        self.run_checked(0xc48ba8)
        self.registers()
        self.w(self.BASE + 0x8300, 'Q', self.s(selected))
        self.set('X0', self.obj)
        self.set('X1', node)
        self.set('X2', self.BASE + 0x8300)
        self.run_checked(0xc48e68)
        return self.events

    def layer_clamp(self, value):
        self.registers()
        self.w(self.obj + 0x54, 'I', value)
        self.set('X19', self.obj)
        self.run(0x3bc1e0, 0x3bc1f4)
        return self.r(self.obj + 0x54, 'I')[0]

    def run_checked(self, address):
        if self.run(address) != self.EXIT:
            raise ValueError('Original update-order fragment exceeded bound')
