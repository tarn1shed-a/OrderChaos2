"""Original worker/notification/bounds consumers with explicit external results.

Resource acquisition, model construction, texture lookup, scene enumeration,
transform setters and render application are recorded/adapted boundaries. This
does not execute original VFS, asset construction, a scene or an Android process.
"""
from native_model_slot_probe import NativeModelSlotProbe
from unicorn import UC_HOOK_CODE


class NativeModelCompletionProbe(NativeModelSlotProbe):
    TASK = 0x10020000
    MODEL = 0x10018000

    def __init__(self, image):
        from model_completion_evidence import verify_native
        verify_native(image)
        super().__init__(image)
        self.uc.mem_map(0x2507000, 0x1000)
        for at, size in [(0x33c000, 0x2000), (0x337000, 0x2000),
                         (0x1362000, 0x1000), (0x1113000, 0x1000),
                         (0x1130000, 0x4000), (0x1dfe000, 0x1000)]:
            self.uc.mem_map(at, size)
            self.uc.mem_write(at, image.read(at, size))
        for at in (0x1181778, 0x111a45c, 0x11236b8, 0x143f178, 0x1362320,
                   0x1364464, 0x3d3634, 0x2a00b0, 0x30da84):
            page = at & ~4095
            # Parent already maps 2a2000, but not these synthetic call pages.
            if at != 0x1362320:
                self.uc.mem_map(page, 4096)
                self.uc.mem_write(at, bytes.fromhex('c0035fd6'))
            self.uc.hook_add(UC_HOOK_CODE, self.boundary, begin=at, end=at)
        for at in (0x30000020, 0x30000024, 0x30000028, 0x3000002c):
            self.uc.hook_add(UC_HOOK_CODE, self.boundary, begin=at, end=at)
        self.phase = ''

    def _call(self, uc, at, size, data):
        if at == 0x29f0f0 and self.phase == 'worker':
            if self.get('X0') != 16:
                raise ValueError('Uncovered original worker allocation')
            self.set('X0', self.SELF+0x29000)
            self.set('PC', self.get('X30'))
            return
        if at == 0x341aa0 and self.phase == 'callback':
            self.refreshes.append(self.get('W1'))
        super()._call(uc, at, size, data)

    def setup(self):
        self.reset()
        self.phase = ''
        self.refreshes, self.events = [], []
        self.write(0x2505c38, 'Q', self.SELF+0x30000)
        self.write(self.SELF+0x30000, 'Q', 0x1234)
        self.write(0x2507008, 'Q', self.SELF+0x30200)
        self.names_cursor = self.SELF+0x2a000

    def name(self, value):
        raw = value.encode()+b'\0'
        at = self.names_cursor
        self.names_cursor += len(raw)+16
        self.uc.mem_write(at, raw)
        return at

    def run_original(self, start, end=None):
        self.set('X30', self.EXIT)
        end = self.EXIT if end is None else end
        self.uc.emu_start(start, end, count=20000)
        if self.get('PC') != end:
            raise ValueError(f'Original model completion scope exceeded at {self.get("PC"):#x}')

    def model(self, at, box):
        self.write(at, 'Q', at+0x400)
        self.write(at+8, 'I', 100)
        self.write(at+0x400-0x20, 'q', 0)
        for slot in (0x158, 0x168, 0x178, 0x180):
            self.write(at+0x400+slot, 'Q', 0x30000024)
        self.write(at+0x400+0x80, 'Q', 0x30000028)
        self.write(at+0x200, '6f', *box)

    def boundary(self, uc, at, size, data):
        if at == 0x1181778:
            name = self.cstring(self.get('X1')).decode()
            self.events.append(['acquire', name])
            self.write(self.get('X8'), 'Q', self.SELF+0x23000 if name in self.available else 0)
        elif at == 0x111a45c:
            index = self.get('W2')
            self.events.append(['texture', index])
            self.write(self.get('X8'), 'Q', self.texture_pointers[index])
        elif at == 0x11236b8:
            self.events.append(['constructModel', self.get('W2')])
            self.write(self.get('X8'), 'Q', self.MODEL if self.return_model else 0)
        elif at == 0x143f178:
            self.events.append(['texturePrepareBoundary'])
        elif at == 0x3d3634:
            vector, begin, count = self.get('X0'), self.get('X1'), self.get('X2')
            if begin != self.SELF+0x22000 or count > 8:
                raise ValueError('Uncovered texture vector resize')
            self.uc.mem_write(begin, bytes(count*8))
            self.write(vector+8, 'Q', begin+count*8)
        elif at == 0x2a00b0:
            self.write(self.get('X0'), '2q', self.now_ms//1000, (self.now_ms % 1000)*1000)
            self.set('W0', 0)
        elif at == 0x1362320:
            self.events.append(['sceneUpdateBoundary'])
        elif at == 0x1364464:
            code, vector = self.get('W1'), self.get('X2')
            self.events.append(['sceneEnumerationBoundary', self.get('X0'), code])
            begin, count = self.SELF+0x1d000, len(self.node_boxes) if code == 0x6d656164 else 0
            self.write(vector, '3Q', begin, begin+count*8, begin+count*8)
        elif at == 0x30000020:
            ptr = self.get('X1')
            ident, index = self.read(ptr+8, 'Ii')
            self.packet = {'taskId': ident, 'selectedIndex': index,
                           'modelPresent': bool(self.read(ptr+0x10, 'Q')[0]),
                           'finishedByte': self.read(ptr+0x18, 'B')[0]}
        elif at == 0x30000024:
            self.events.append(['modelVirtualBoundary', self.get('X1'), self.get('W2')])
        elif at == 0x30000028:
            self.set('X0', self.get('X0')+0x200)
        elif at == 0x3000002c:
            self.set('W0', self.node_type)
        elif at == 0x30da84:
            pass  # Free the explicitly provided collection storage boundary.
        else:
            raise ValueError(hex(at))
        self.set('PC', self.get('X30'))

    def worker(self, names, available, *, return_model=True, textures=(), now_ms=1000):
        if not 1 <= len(names) <= 2 or any('ind_magic_shield001.bdae' in n for n in names):
            raise ValueError('Only scoped one/two candidate model tasks are supported')
        if len(textures) > 8:
            raise ValueError('Bounded texture fixtures required')
        self.setup()
        self.phase, self.available, self.return_model, self.now_ms = 'worker', set(available), return_model, now_ms
        self.write(self.TASK+0x40, '3Q', self.SELF+0x21000,
                   self.SELF+0x21000+len(names)*8, self.SELF+0x21000+len(names)*8)
        for i, value in enumerate(names):
            self.write(self.SELF+0x21000+i*8, 'Q', self.name(value))
        self.write(self.TASK+0x38, 'I', 0x5c)
        self.write(self.TASK+0x28, 'Q', self.SELF+0x31000)
        self.write(self.SELF+0x31300, 'Q', self.SELF+0x32000)
        self.write(self.TASK+0x58, 'i', -1)
        self.write(self.TASK+0x68, '3Q', *([self.SELF+0x22000]*2), self.SELF+0x22040)
        self.write(0x2505df0, 'Q', self.SELF+0x30008)
        self.write(self.SELF+0x30008, 'Q', self.SELF+0x30100)
        self.write(self.SELF+0x23000+8, 'I', 100)
        self.write(self.SELF+0x23000+0x48, 'Q', self.SELF+0x24000)
        self.write(self.SELF+0x24000+0x28, 'Q', self.SELF+0x25000)
        self.write(self.SELF+0x25000+0x94, 'I', len(textures))
        self.model(self.MODEL, [0, 0, 0, 1, 1, 1])
        self.texture_pointers = []
        for i, status in enumerate(textures):
            if status is None:
                self.texture_pointers.append(0)
                continue
            ptr = self.SELF+0x26000+i*0x200
            self.write(ptr+8, 'I', 100)
            self.write(ptr+0x28, 'Q', ptr+0x100)
            self.write(ptr+0x100+0x6a, 'b', -1 if status == 'skip' else 0)
            self.write(ptr+0x100+0x50, 'Q', int(status == 'ready'))
            self.texture_pointers.append(ptr)
        states = [0]
        for _ in range(16):
            self.set('X0', self.TASK)
            self.set('X1', self.SELF+0x2f000)
            self.run_original(0x33cfe4)
            state = self.read(self.TASK+0x14, 'I')[0]
            states.append(state)
            if self.read(self.SELF+0x2f000, 'B')[0] or self.read(self.TASK+0x88, 'Q')[0]:
                break
        return {'states': states, 'selectedIndex': self.read(self.TASK+0x58, 'i')[0],
                'finishedByte': self.read(self.SELF+0x2f000, 'B')[0],
                'modelPresent': bool(self.read(self.TASK+0x80, 'Q')[0]),
                'waitStamp': self.read(self.TASK+0x88, 'Q')[0], 'events': list(self.events)}

    def wait_gate(self, now_ms):
        """Original 80 ms polling predicate, not a reconstructed scheduler."""
        self.now_ms = now_ms
        self.set('X0', self.TASK)
        self.run_original(0x33cf0c)
        return bool(self.get('W0'))

    def notification(self, state, index, present):
        self.setup()
        self.write(self.TASK+0x10, '2I', 17, state)
        self.write(self.TASK+0x58, 'i', index)
        self.write(self.TASK+0x80, 'Q', self.MODEL if present else 0)
        self.model(self.MODEL, [0, 0, 0, 1, 1, 1])
        self.write(self.TASK+0x20, 'Q', self.SELF)
        self.write(self.SELF, 'Q', self.SELF+0x1000)
        self.write(self.SELF+0x1000+0xc0, 'Q', 0x30000020)
        self.set('X19', self.TASK)
        self.run_original(0x33cabc, 0x33cb98)
        return self.packet

    def consume(self, packet, mapping, *, requested=2, active=2, blocked=False,
                cache=-1, existing=(False, False), boxes=((0x18, [0, 0, 0, 2, 4, 6]),),
                root_box=(0, 0, 0, 1, 1, 1), model_name='model/test'):
        if len(mapping) not in (1, 2) or any(v not in (0, 1) for v in mapping):
            raise ValueError('Explicit candidate-to-slot mapping required')
        if len(boxes) > 4:
            raise ValueError('Bounded explicit child-node fixtures required')
        self.setup()
        self.phase, self.capture = 'callback', False
        self.write(self.SELF+0x58, '2B', requested, active)
        self.write(self.SELF+0x5d, 'B', blocked)
        self.write(self.SELF+0xa8, 'I', 17)
        self.write(self.SELF+0x160, 'f', cache)
        self.write(0x1000105b, 'B', 1)  # Explicitly skip the optional atlas lookup branch.
        self.write(self.SELF+0x60, 'Q', self.name(model_name))
        self.node_boxes = boxes
        for i, (flags, box) in enumerate(boxes):
            ptr = self.SELF+0x1d100+i*0x800
            self.model(ptr, box)
            self.write(ptr+0x130, 'I', flags)
            self.write(self.SELF+0x1d000+i*8, 'Q', ptr)
        self.model(self.MODEL, root_box)
        for i in range(2):
            ptr = self.SELF+0x17000+i*0x800
            self.model(ptr, root_box)
            self.write(self.SELF+0x98+i*8, 'Q', ptr if existing[i] else 0)
        for i, slot in enumerate(mapping):
            self.write(self.SELF+0xac+i, 'B', slot)
        payload = self.SELF+0x16000
        self.write(payload+8, 'IiQB', packet['taskId'], packet['selectedIndex'],
                   self.MODEL if packet['modelPresent'] else 0, packet['finishedByte'])
        self.set('X0', self.SELF)
        self.set('X1', payload)
        self.run_original(0x34138c)
        return {'taskId': self.read(self.SELF+0xa8, 'I')[0],
                'requested': self.read(self.SELF+0x58, 'B')[0],
                'active': self.read(self.SELF+0x59, 'B')[0],
                'completionMask': self.read(self.SELF+0x5a, 'B')[0],
                'slotsPresent': [bool(v) for v in self.read(self.SELF+0x98, '2Q')],
                'radiusCenterScale': list(self.read(self.SELF+0x150, '5f')),
                'refreshCalls': self.refreshes, 'renderApplyBoundaryCalls': self.applied,
                'events': self.events}

    def world_box(self, box, matrix):
        if len(box) != 6 or len(matrix) != 16:
            raise ValueError('Explicit local box and column-major matrix required')
        self.setup()
        self.model(self.MODEL, box)
        self.write(self.MODEL+0x400+0x78, 'Q', 0x30000028)
        self.write(self.MODEL+0x400+0x1b0, 'Q', 0x3000002c)
        self.node_type = 0x6d656164
        self.write(self.MODEL+0x28, '16f', *matrix)
        self.write(self.MODEL+0x130, 'I', 0x400)  # Dirty ordinary-bounds branch; bit11 clear.
        self.set('X0', self.MODEL)
        self.run_original(0x1133118)
        return list(self.read(self.MODEL+0xd0, '6f'))
