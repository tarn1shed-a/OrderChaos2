"""Original sky frame and wrapper instructions with synthetic CPU receivers.

Callbacks that would propagate scene dirtiness or advance scene animation are
recorded, not executed. No original process, GPU or network is used.
"""
import struct

from scene_sky_frame import verify_native


class NativeSkyFrameProbe:
    BASE = 0x10000000

    def __init__(self, image):
        verify_native(image)
        from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
        from unicorn import arm64_const
        self.reg = arm64_const; self.uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        for at, size in [(0xa63000, 0x2000), (0x337000, 0x2000), (0x1364000, 0x1000), (0x34d000, 0x3000)]:
            self.uc.mem_map(at, size); self.uc.mem_write(at, image.read(at, size))
        for at, size in [(self.BASE, 0x10000), (0x20000000, 0x10000), (0x2528000, 0x1000), (0x1362000, 0x1000)]:
            self.uc.mem_map(at, size)
        self.uc.hook_add(UC_HOOK_CODE, self._hook, begin=0x1362320, end=0x1362320)
        for address in (self.BASE+0xf000, self.BASE+0xf004, self.BASE+0xf008, self.BASE+0xf00c):
            self.uc.hook_add(UC_HOOK_CODE, self._hook, begin=address, end=address)

    def write(self, at, fmt, *values): self.uc.mem_write(at, struct.pack('<'+fmt, *values))
    def read(self, at, fmt): return struct.unpack('<'+fmt, self.uc.mem_read(at, struct.calcsize('<'+fmt)))
    def set(self, name, value): self.uc.reg_write(getattr(self.reg, 'UC_ARM64_REG_'+name), value)
    def get(self, name): return self.uc.reg_read(getattr(self.reg, 'UC_ARM64_REG_'+name))

    def reset(self):
        self.uc.mem_write(self.BASE, bytes(0x10000)); self.uc.mem_write(0x20000000, bytes(0x10000))
        for i in range(31): self.set(f'X{i}', 0)
        for i in range(32): self.set(f'Q{i}', 0)
        self.set('SP', 0x20008000); self.set('X30', self.BASE+0xf00c)
        self.dirty = []; self.calls = []

    def _hook(self, uc, at, size, data):
        if at == self.BASE+0xf00c: uc.emu_stop(); return
        if at == 0x1362320:
            if self.get('W1') != 1 or self.get('W2') != 0: raise ValueError('Unexpected source dirty propagation arguments')
            self.dirty.append(self.get('X0')); self.set('PC', self.get('X30')); return
        target = {self.BASE+0xf000: 'primary+0x38', self.BASE+0xf004: 'sky+0x48', self.BASE+0xf008: 'scene+0xb8'}[at]
        if target == 'scene+0xb8':
            delta = struct.unpack('<f', struct.pack('<I', self.get('S0')))[0]
            self.calls.append({'target': target, 'deltaFloat': delta, 'argument1': self.get('W1')})
        else: self.calls.append({'target': target, 'deltaWord': self.get('W1')})
        self.set('PC', self.get('X30'))

    def follow(self, camera, main=None, hill=None, unloaded=()):
        self.reset(); world = self.BASE+0x1000; renderer = self.BASE+0x2000; scene = self.BASE+0x3000
        eye = self.BASE+0x4000; node_vtable = self.BASE+0xc000; wrapper_vtable = self.BASE+0xd000
        self.write(0x2528db0, 'Q', world); self.write(world+0x1c0, 'Q', renderer)
        self.write(renderer+0x18, 'Q', scene); self.write(scene+0x238, 'Q', eye)
        self.write(eye, 'Q', node_vtable); self.write(eye+8, 'I', 100); self.write(eye+0xa8, '3f', *camera)
        self.write(node_vtable+0x170, 'Q', 0x136400c); self.write(node_vtable+0x178, 'Q', 0x1364014)
        self.write(wrapper_vtable+0x18, 'Q', 0x3378c8)
        nodes = {}
        for name, offset, wrapper, node, old in [('main', 0x10, self.BASE+0x5000, self.BASE+0x6000, main),
                                               ('hill', 0x18, self.BASE+0x7000, self.BASE+0x8000, hill)]:
            if old is None: continue
            self.write(self.BASE+offset, 'Q', wrapper); self.write(wrapper, 'Q', wrapper_vtable)
            if name in unloaded: continue
            self.write(wrapper+8, 'Q', node); self.write(node, 'Q', node_vtable); self.write(node+0xa8, '3f', *old)
            nodes[name] = node
        self.set('X0', self.BASE)
        self.uc.emu_start(0xa63f40, self.BASE+0xf010, count=500)
        if self.get('PC') != self.BASE+0xf00c: raise ValueError('Sky frame probe exceeded bounds')
        return {'positions': {name: list(self.read(nodes[name]+0xa8, '3f')) if name in nodes else None for name in ('main', 'hill')},
                'dirtyNodes': [name for node in self.dirty for name, address in nodes.items() if node == address]}

    def schedule(self, delta, primary=True, sky=True):
        self.reset(); renderer = self.BASE; scene = self.BASE+0x1000
        self.write(renderer+0x18, 'Q', scene); self.write(scene, 'Q', self.BASE+0xa000)
        self.write(self.BASE+0xa0b8, 'Q', self.BASE+0xf008)
        for enabled, off, obj, table, callback in [(primary, 0x38, self.BASE+0x2000, self.BASE+0xb000, self.BASE+0xf000),
                                                 (sky, 0x48, self.BASE+0x3000, self.BASE+0xc000, self.BASE+0xf004)]:
            if enabled:
                self.write(renderer+off, 'Q', obj); self.write(obj, 'Q', table); self.write(table+0x18, 'Q', callback)
        self.set('X0', renderer); self.set('W1', delta)
        self.uc.emu_start(0x34df7c, 0x34dff0, count=80)
        if self.get('PC') != 0x34dff0: raise ValueError('Renderer prefix exceeded probe bounds')
        return self.calls
