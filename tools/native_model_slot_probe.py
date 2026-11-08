"""Isolated original model-slot consumers; synthetic camera/config/load calls.

Only used with the local pinned ARM64 sample. No original host code or assets
are executed. Projected-area computation and render fade work are stubbed.
"""
import struct

from scene_model_slots import GLOBALS, bounds_parameters, distance_request, verify_native


class NativeModelSlotProbe:
    SELF = 0x10000000
    EXIT = 0x300000f0

    def __init__(self, image):
        verify_native(image)
        from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
        from unicorn import arm64_const
        self.reg = arm64_const; self.uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        for at, size in ((0x340000, 0x3000), (0x33f000, 0x1000), (0x1da9000, 0x1000),
                         (0x1df7000, 0x2000)):
            self.uc.mem_map(at, size); self.uc.mem_write(at, image.read(at, size))
        for at, size in ((0x10000000, 0x40000), (0x20000000, 0x10000), (0x30000000, 0x1000),
                         (0x29f000, 0x1000), (0x2a2000, 0x1000), (0x12e6000, 0x1000),
                         (0x2504000, 0x2000), (0x2509000, 0x2000), (0x2527000, 0x2000), (0x2532000, 0x1000)):
            self.uc.mem_map(at, size)
        self.write(0x25043f8, 'Q', 0x250a8a8); self.write(0x2505dd8, 'Q', 0x2532ef1)
        for at in (0x341aa0, 0x33f2fc, 0x340dc0, 0x29f0f0, 0x29f220, 0x2a2120,
                   0x12e668c, 0x30000000, 0x30000004, 0x30000008):
            if at not in (0x341aa0, 0x33f2fc, 0x340dc0): self.write(at, 'I', 0xd65f03c0)
            self.uc.hook_add(UC_HOOK_CODE, self._call, begin=at, end=at)

    def write(self, at, fmt, *values): self.uc.mem_write(at, struct.pack('<'+fmt, *values))
    def read(self, at, fmt): return struct.unpack('<'+fmt, self.uc.mem_read(at, struct.calcsize('<'+fmt)))
    def set(self, name, value): self.uc.reg_write(getattr(self.reg, 'UC_ARM64_REG_'+name), value)
    def get(self, name): return self.uc.reg_read(getattr(self.reg, 'UC_ARM64_REG_'+name))
    def float_reg(self, name, value): self.set(name, struct.unpack('<I', struct.pack('<f', value))[0])

    def cstring(self, at):
        result = bytearray()
        while len(result) < 1024:
            byte = self.uc.mem_read(at+len(result), 1)[0]
            if byte == 0: return bytes(result)
            result.append(byte)
        raise ValueError('Unexpected unterminated synthetic name')

    def _call(self, uc, at, size, data):
        if at == 0x341aa0:
            if not self.capture: return  # Run original slot/queue update.
            self.request = self.get('W1')
        elif at == 0x33f2fc: self.loads.append((self.get('W1'), self.get('W2')))
        elif at == 0x340dc0: self.applied += 1
        elif at == 0x29f0f0:
            if self.get('X0') != 24: raise ValueError('Unexpected queue allocation')
            self.set('X0', self.heap); self.heap += 32; self.allocations += 1
        elif at == 0x29f220: self.frees += 1
        elif at == 0x30000000: self.set('X0', 0x10008000)  # explicit virtual170 vector
        elif at == 0x30000004: self.set('X0', 0x10008020)  # explicit virtual288 vector
        elif at == 0x30000008: self.write(self.get('X8'), '6f', *([0]*6))  # synthetic box for injected metric
        elif at == 0x12e668c:
            if self.metric is None: raise ValueError('Projected-area producer needs explicit metric input')
            self.float_reg('S0', self.metric); self.metric_calls += 1
        elif at == 0x2a2120:
            haystack, needle = self.get('X0'), self.get('X1')
            index = self.cstring(haystack).find(self.cstring(needle))
            self.set('X0', haystack+index if index >= 0 else 0)
        else: raise ValueError('Unexpected synthetic native call')
        self.set('PC', self.get('X30'))

    def reset(self, inputs=None):
        values = inputs or {}
        self.uc.mem_write(0x10000000, bytes(0x40000)); self.uc.mem_write(0x20000000, bytes(0x10000))
        self.capture = True; self.request = None; self.loads = []; self.applied = 0
        self.allocations = self.frees = self.metric_calls = 0; self.heap = 0x10020000
        self.metric = values.get('projection_metric')
        for index in range(31): self.set(f'X{index}', 0)
        for index in range(32): self.set(f'Q{index}', 0)
        self.set('SP', 0x20008000); self.set('X30', self.EXIT); self.set('X0', self.SELF)
        self.write(0x2528220, 'Q', 0x10001000); self.write(0x2528db0, 'Q', 0x10002000)
        self.write(0x10001028, 'I', values.get('config28', 2))
        self.write(0x10001018, 'f', values.get('config18', 0))
        self.write(0x10001014, 'f', values.get('config14') or 0)
        self.write(0x10001059, 'B', values.get('direction_enabled', False))
        self.write(0x100021c0, 'Q', 0x10003000)
        self.write(0x10003030, 'Q', 0x10004000 if values.get('context_available', True) else 0)
        self.write(0x10004038, 'Q', 0x10005000); self.write(0x10005018, 'Q', 0x10006000)
        self.write(0x10006000, 'Q', 0x10007020); self.write(0x10006008, 'I', 100)
        self.write(0x10007190, 'Q', 0x30000000); self.write(0x100072a8, 'Q', 0x30000004)
        self.write(0x10008000, '3f', *(values.get('camera_second') or [0, 0, 0]))
        self.write(0x10008020, '3f', *(values.get('camera_first') or [0, 0, 1]))
        self.write(self.SELF, 'Q', 0x10009000); self.write(0x10009068, 'Q', 0x30000008)
        self.write(self.SELF+0x58, 'BB', values.get('current', 2), 2)
        self.write(self.SELF+0x150, 'f3ffff', values.get('radius', 0), *(values.get('center') or [0, 0, 0]),
                   values.get('scale160', 1), values.get('scale164', 1), values.get('override168', -1))
        self.write(0x1000a000, '3f', *(values.get('position') or [0, 0, 0]))
        self.write(0x250a8a8, 'B', values.get('override_enabled', False))
        self.write(0x2532ef1, 'B', values.get('projection_enabled', False))
        g = values.get('globals') or GLOBALS
        for at, key in ((0x25091c4, 'areaHysteresis'), (0x25091cc, 'innerBase'), (0x25091d0, 'innerHysteresis'),
                        (0x25091d4, 'innerScale'), (0x25091d8, 'outerBase'), (0x25091dc, 'outerHysteresis')):
            self.write(at, 'f', g[key])
        self.write(0x25091e4, 'i', g['minimumSlot'])
        self.write(0x2527810, 'QQ', 0x2527810, 0x2527810)

    def select(self, **inputs):
        distance_request(**inputs)  # input validation only; no returned oracle value is used
        self.reset(inputs); self.set('X1', 0x1000a000)
        self.uc.emu_start(0x341c60, self.EXIT, count=10000)
        if self.get('PC') != self.EXIT: raise ValueError('Native slot selector exceeded instruction bound')
        return self.request

    def manual(self, config, desired, current):
        self.reset({'config28': config, 'current': current}); self.set('W1', desired)
        self.uc.emu_start(0x341c2c, self.EXIT, count=100)
        return self.request

    def completion(self, requested, active, arrived, loaded_mask=0):
        self.reset({'current': requested}); self.set('X19', self.SELF); self.set('X23', arrived)
        self.write(self.SELF+0x59, 'B', active); self.write(self.SELF+0x5a, 'B', loaded_mask)
        self.write(0x2527820, 'B', 0)
        self.uc.emu_start(0x341a14, 0x341a5c, count=100)
        return self.request is not None, self.read(self.SELF+0x5a, 'B')[0]

    def bounds(self, box, name='', previous_scale164=1):
        bounds_parameters(box, name, previous_scale164)  # chosen-box validation only
        self.reset({'scale164': previous_scale164}); self.set('X19', self.SELF); self.set('X20', 0x1000a000)
        self.uc.mem_write(0x1000a000, name.encode()+b'\0')
        for index, value in enumerate(box): self.float_reg(f'S{index}', value)
        self.uc.emu_start(0x3411c0, 0x34127c, count=300)
        raw = self.read(self.SELF+0x150, '7f')
        return {'radius': raw[0], 'center': list(raw[1:4]), 'scale160': raw[4], 'scale164': raw[5]}

    def transition(self, requested, active, loaded, new_request, *, defer=False, mask_matches=False, queued=False, contains=False):
        self.reset(); self.capture = False; self.set('W1', new_request); self.set('W2', int(defer))
        self.write(self.SELF+0x58, 'BB', requested, active); self.write(self.SELF+0x5c, 'B', queued)
        self.write(self.SELF+0x10, 'I', 0xffffffff if mask_matches else 0); self.write(0x25277d0, 'I', 0)
        self.write(self.SELF+0x98, 'QQ', *[0x1000b000+index*256 if value else 0 for index, value in enumerate(loaded)])
        # Keep an unrelated queue member to verify real insertion/unlink links.
        nodes = [0x2527810, 0x10012000]+([0x10012020] if contains else [])
        self.write(0x10012010, 'Q', 0x1000d000)
        if contains: self.write(0x10012030, 'Q', self.SELF)
        for index, node in enumerate(nodes): self.write(node, 'QQ', nodes[(index+1) % len(nodes)], nodes[index-1])
        self.uc.emu_start(0x341aa0, self.EXIT, count=2000)
        if self.get('PC') != self.EXIT: raise ValueError('Native slot state exceeded instruction bound')
        owners = []; node, = self.read(0x2527810, 'Q')
        while node != 0x2527810:
            if len(owners) >= 10: raise ValueError('Bad original queue links')
            owner, = self.read(node+16, 'Q'); owners.append(owner); node, = self.read(node, 'Q')
        if 0x1000d000 not in owners: raise ValueError('Original queue lost unrelated member')
        req, act = self.read(self.SELF+0x58, 'BB'); pending, = self.read(self.SELF+0x5c, 'B')
        return {'requested': req, 'active': act, 'queued': bool(pending), 'contains': self.SELF in owners,
                'apply': bool(self.applied), 'allocate': bool(self.allocations), 'remove': bool(self.frees)}
