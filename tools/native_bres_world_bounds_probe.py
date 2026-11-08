"""Execute original BRES fixups, removable buffers, scene tree and world bounds.

Byte streams, allocators/strings, locks/thread environment and mesh-resource
lookup storage are adapters. Geometry bbox bytes, source node assembly, TRS,
flags, matrices, callback and bounds consumers execute original instructions.
A detached fresh model is not an observed Android process or rendered frame.
"""
import struct
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_MEM_INVALID, UC_HOOK_MEM_WRITE
from unicorn import arm64_const as R


class NativeBresWorldBoundsProbe:
    BASE = 0x10000000
    EXIT = 0x300000f0

    def __init__(self, im):
        from bres_world_bounds_evidence import verify_native
        verify_native(im)
        self.im = im
        self.uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        for s in im.elf.iter_segments():
            if s['p_type'] != 'PT_LOAD':
                continue
            start = s['p_vaddr'] & ~0xfff
            end = (s['p_vaddr'] + s['p_memsz'] + 0xfff) & ~0xfff
            self.uc.mem_map(start, end - start)
            self.uc.mem_write(s['p_vaddr'], s.data())
        for rel in im.elf.get_section_by_name('.rela.dyn').iter_relocations():
            if rel['r_info_type'] == 0x403:
                self.w(rel['r_offset'], 'Q', rel['r_addend'])
        for a, n in [(self.BASE, 0x2000000), (0x20000000, 0x10000), (0x30000000, 0x1000)]:
            self.uc.mem_map(a, n)
        for a in [0x29f0f0, 0x29fbb0, 0x3c0fbc, 0x11dcc20, 0x2a1030, 0x29f220, 0x2a0180, 0x30da84, 0x2a1e50, 0x29f5b0, 0x30000100, 0x30000104, 0x30000108, self.EXIT, 0x29e010, 0x29e3c0, 0x2a2120, 0x29eaf0, 0x1de8970, 0x1de9b88, 0x1502ff4, 0x1503330, 0x1502cf0, 0x1502fc0, 0x1561f2c, 0x1561f34, 0x14f40b4, 0x14f3e5c, 0x111b8c4, 0x11ddd2c, 0x138aaa8, 0x11dcc44]:
            self.uc.hook_add(UC_HOOK_CODE, self.hook, begin=a, end=a)
        self.uc.hook_add(UC_HOOK_MEM_INVALID, self.bad)
        self.uc.hook_add(UC_HOOK_MEM_WRITE, self.flag_write, begin=self.BASE, end=self.BASE+0x2000000-1)
        self.heap = self.BASE + 0x10000
        self.events = []
        self.nodes = {}
        self.flag_writes = []
        self.prepared = []

    def set(self, n, v):
        self.uc.reg_write(getattr(R, 'UC_ARM64_REG_' + n), v & ((1 << 64) - 1))

    def get(self, n):
        return self.uc.reg_read(getattr(R, 'UC_ARM64_REG_' + n))

    def w(self, a, f, *v):
        self.uc.mem_write(a, struct.pack('<' + f, *v))

    def r(self, a, f):
        return struct.unpack('<' + f, self.uc.mem_read(a, struct.calcsize('<' + f)))

    def alloc(self, n):
        if n < 0 or n > 0x200000:
            raise ValueError('alloc ' + str(n))
        p = self.heap
        self.heap = (p + n + 0x3f) & ~0x3f
        if self.heap >= self.BASE+0x1ff0000:
            raise ValueError('Bounded research arena exhausted')
        self.uc.mem_write(p, bytes(n))
        caller = self.get('X30')-4
        if caller in (0x112b538, 0x112b660, 0x112ba8c):
            self.nodes[p] = caller
        return p

    def bad(self, uc, k, a, n, v, d):
        raise ValueError(f'Uncovered native memory access at PC {self.get("PC"):#x}, address {a:#x}')

    def flag_write(self, uc, access, address, size, value, data):
        if size == 4 and address-0x130 in self.nodes:
            self.flag_writes.append({'node': address-0x130, 'pc': self.get('PC'),
                                     'before': self.r(address, 'I')[0], 'after': value})

    def source_slice(self, offset, size):
        if offset < 0 or size < 0 or offset+size > len(self.raw):
            raise ValueError('Native read escapes the original source bytes')
        return self.raw[offset:offset+size]

    def c(self, a):
        b = bytearray()
        for i in range(0x1000):
            v = bytes(self.uc.mem_read(a + i, 1))
            if v == b'\x00':
                return bytes(b)
            b.extend(v)
        raise ValueError('long string')

    def hook(self, uc, a, n, d):
        if a == self.EXIT:
            uc.emu_stop()
            return
        if a in [0x29f0f0, 0x29fbb0, 0x3c0fbc, 0x11dcc20, 0x2a1030]:
            self.set('X0', self.alloc(self.get('X0')))
        elif a in [0x29f220, 0x2a0180, 0x30da84, 0x11dcc44]:
            pass
        elif a in [0x2a1e50, 0x29f5b0]:
            uc.mem_write(self.get('X0'), bytes(uc.mem_read(self.get('X1'), self.get('X2'))))
        elif a == 0x30000100:
            count = self.get('W2')
            offset = self.cursor
            self.cursor += count
            uc.mem_write(self.get('X1'), self.source_slice(offset, count))
            self.set('W0', count)
            self.events.append(['read', offset, count])
        elif a == 0x30000104:
            if self.get('W2') != 0:
                raise ValueError('whence')
            self.cursor = self.get('X1')
            self.source_slice(self.cursor, 0)
            self.events.append(['seek', self.cursor])
        elif a == 0x30000108:
            count, offset, dest = (self.get('W1'), self.get('W2'), self.get('X3'))
            uc.mem_write(dest, self.source_slice(offset, count))
            self.events.append(['bufferRead', offset, count])
        elif a == 0x29e010:
            self.set('X0', len(self.c(self.get('X0'))))
        elif a == 0x29e3c0:
            x, y = (self.c(self.get('X0')), self.c(self.get('X1')))
            self.set('W0', (x > y) - (x < y))
        elif a == 0x2a2120:
            pos = self.c(self.get('X0')).find(self.c(self.get('X1')))
            self.set('X0', self.get('X0') + pos if pos >= 0 else 0)
        elif a == 0x29eaf0:
            uc.mem_write(self.get('X0'), bytes([self.get('W1') & 0xff]) * self.get('X2'))
        elif a == 0x1de8970:
            n = self.get('X2')
            v = bytes(uc.mem_read(self.get('X1'), n))
            s = self.alloc(n + 0x19)
            self.w(s, 'QQi', n, n, 0x64)
            uc.mem_write(s + 0x18, v + b'\x00')
            self.w(self.get('X0'), 'Q', s + 0x18)
        elif a in [0x1de9b88, 0x1502ff4, 0x1503330, 0x1502cf0, 0x1502fc0, 0x1561f2c, 0x1561f34]:
            pass
        elif a in [0x14f40b4, 0x14f3e5c]:
            self.set('X0', self.BASE + 0x9000)
        elif a == 0x11ddd2c:
            n = self.r(self.get('X0'), 'I')[0]
            obj = self.alloc(n + 0x18)
            self.w(obj + 0x10, 'I', 0x64)
            uc.mem_write(obj + 0x18, bytes(uc.mem_read(self.get('X1'), n)))
            self.set('X0', obj)
        elif a == 0x138aaa8:
            vec = self.get('X0')
            begin, end, cap = self.r(vec, '3Q')
            old = bytes(uc.mem_read(begin, end - begin)) if begin else b''
            new = self.alloc(len(old) + 0x40)
            uc.mem_write(new, old + bytes(uc.mem_read(self.get('X1'), 8)))
            self.w(vec, '3Q', new, new + len(old) + 8, new + len(old) + 0x40)
        elif a == 0x111b8c4:
            ref = self.get('X2')
            name = self.c(self.r(ref + 8, 'Q')[0]).decode()
            self.events.append(['meshLookupAdapter', name])
            self.w(self.get('X8'), 'Q', self.meshes[name.removeprefix('#')])
        else:
            raise ValueError(hex(a))
        self.set('PC', self.get('X30'))

    def regs(self):
        for i in range(0x1f):
            self.set('X' + str(i), 0)
        for i in range(0x20):
            self.set('Q' + str(i), 0)
        self.set('SP', 0x20008000)
        self.set('X30', self.EXIT)

    def run(self, a, end=None):
        self.uc.emu_start(a, end or self.EXIT, count=0x30d40)
        if self.get('PC') != (end or self.EXIT):
            raise ValueError('scope ' + hex(self.get('PC')))

    def load(self, raw, string_pool=False):
        """Original stream reader/fixups; supplied stream bytes and pool mode."""
        if (not isinstance(raw, bytes) or len(raw) < 64 or raw[:8] != b'BRES\xfe\xff\0\0'
                or struct.unpack_from('<I', raw, 8)[0] != 64
                or struct.unpack_from('<I', raw, 12)[0] != len(raw)):
            raise ValueError('Expected a complete scoped inner BRES image')
        if type(string_pool) is not bool:
            raise ValueError('Explicit string-pool branch required')
        dependency = struct.unpack_from('<I', raw, 0x30)[0]
        if dependency+4 > len(raw) or struct.unpack_from('<I', raw, dependency)[0] >= 2:
            raise ValueError('External BRES dependency prefetch is outside this experiment')
        self.raw = raw
        self.cursor = 0
        self.ctx = self.BASE
        self.uc.mem_write(self.ctx, bytes(0x90))
        stream = self.BASE + 0x1000
        vt = self.BASE + 0x2000
        self.w(stream, 'Q', vt)
        self.w(vt + 0x18, 'Q', 0x30000100)
        self.w(vt + 0x20, 'Q', 0x30000104)
        self.w(0x25dd608, 'B', int(string_pool))
        self.regs()
        self.set('X0', self.ctx)
        self.set('X1', stream)
        self.run(0x148daa8)
        return {'main': self.r(self.ctx, 'Q')[0], 'info': self.r(self.r(self.ctx, 'Q')[0] + 0x28, 'Q')[0], 'successByte': self.r(self.ctx + 8, 'B')[0]}

    def prepare(self, wrapper):
        count = self.r(wrapper+4, 'h')[0]
        offset = self.r(wrapper+8, 'Q')[0]
        size, compressed = self.r(wrapper+0x10, '2I')
        if not 1 <= count <= 16 or size < count*8 or compressed:
            raise ValueError('Only scoped uncompressed removable buffers are executed')
        self.source_slice(offset, size)
        reader = self.BASE + 0x3000
        vt = self.BASE + 0x4000
        self.w(reader, 'Q', vt)
        self.w(vt + 0x10, 'Q', 0x30000108)
        self.regs()
        self.set('X0', wrapper)
        self.set('X1', reader)
        self.set('W2', 0)
        self.run(0x117c40c)
        body = self.get('X0')
        expected = self.source_slice(offset+count*8+0x60, 24)
        copied = bytes(self.uc.mem_read(body+0x60, 24))
        if copied != expected:
            raise ValueError('Original prepared bbox bytes differ from source span')
        self.prepared.append({'prefixCount': count, 'sourceBufferOffset': offset,
                              'sourceBoxOffset': offset+count*8+0x60,
                              'preparedBoxOffset': 0x60, 'bboxBytesEqual': True,
                              'localBox': list(self.r(body+0x60, '6f'))})
        return body

    def scene(self, info, factory=0x244d308):
        """Execute the original scene/node assembler; mesh graphics work is adapted."""
        if factory not in (0x244d308, 0x2416430):
            raise ValueError('Only the two pinned source factories are in scope')
        self.meshes = {}
        c, rel = self.r(info + 0xb4, 'Ii')
        tab = info + 0xb8 + rel
        for i in range(c):
            rec = tab + i * 0x18
            wr = rec + 0x14 + self.r(rec + 0x14, 'i')[0]
            body = self.prepare(wr)
            mesh = self.alloc(0x100)
            self.w(mesh, 'Q', 0x244e410)
            self.w(mesh + 8, 'I', 0x64)
            self.regs()
            self.set('X27', body)
            self.set('X26', mesh)
            self.run(0x1131ae0, 0x1131afc)
            name = self.c(self.r(rec, 'Q')[0]).decode()
            self.meshes[name] = mesh
        pair = self.BASE + 0x5000
        res = self.BASE + 0x6000
        fac = self.BASE + 0x7000
        self.w(pair, '2Q', res, fac)
        self.w(res + 8, 'I', 0x64)
        self.w(res + 0x48, 'Q', self.r(self.ctx, 'Q')[0])
        self.w(fac, 'Q', factory)
        self.regs()
        self.set('X1', pair)
        self.set('X8', self.BASE + 0xa000)
        self.run(0x112ba70)
        root = self.r(self.BASE + 0xa000, 'Q')[0]
        cnt, rel = self.r(info + 0xdc, 'Ii')
        scene = info + 0xe0 + rel
        if cnt != 1:
            raise ValueError('scene count')
        self.regs()
        self.set('X0', pair)
        self.set('X1', self.BASE + 0x8000)
        self.set('X2', scene)
        self.set('X3', self.BASE + 0xa000)
        self.set('X8', self.BASE + 0xa008)
        self.run(0x112330c)
        return root

    def itm_transform(self, raw_record, tile, config_words):
        if len(raw_record) != 76 or len(tile) != 2 or len(config_words) != 12:
            raise ValueError('Original ITM record, coordinates and WLD words required')
        rec = self.alloc(len(raw_record))
        self.uc.mem_write(rec, bytes(raw_record))
        world = self.alloc(0x100)
        context = self.alloc(0x30)
        self.uc.mem_write(world+0x84, config_words)
        self.w(context + 0x10, '2i', *tile)
        self.regs()
        self.set('X19', world)
        self.set('X24', context)
        self.set('X22', 0)
        self.set('X23', rec)
        self.run(0xa61bdc, 0xa61c70)
        return self.r(self.get('SP') + 0x38, '10f')

    def finish(self, root, trs, name='model/test.bdae', slot=0):
        """Original fresh-owner callback, with actual reconstructed source nodes."""
        if len(trs) != 10 or slot not in (0, 1):
            raise ValueError('Explicit source TRS and source slot required')
        obj = self.alloc(0x180)
        self.regs()
        self.set('X0', obj)
        self.run(0x33db74)
        s = self.alloc(len(name) + 1)
        self.uc.mem_write(s, name.encode() + b'\x00')
        self.w(obj + 0x60, 'Q', s)
        self.w(obj + 0x68, '10f', *trs)
        self.w(obj + 0xac, 'B', slot)
        config = self.alloc(0x100)
        self.w(config + 0x5b, 'B', 1)
        self.w(0x2528220, 'Q', config)
        packet = self.alloc(0x30)
        self.w(packet + 8, 'IiQB', 0x11, 0, root, 1)
        self.regs()
        self.set('X0', obj)
        self.set('X1', packet)
        self.run(0x34138c)
        # Ask the original aggregator for its box as well as the parameters
        # already produced by the full callback. No Python box union is used.
        ref, output = self.alloc(8), self.alloc(24)
        self.w(ref, 'Q', root)
        self.regs()
        self.set('X0', ref)
        self.set('W1', 1)
        self.set('X8', output)
        self.run(0x337c98)
        return {'rootFlags': hex(self.r(root + 0x130, 'I')[0]),
                'rootMatrix': list(self.r(root + 0x28, '16f')),
                'ownerBoundsParams': list(self.r(obj + 0x150, '5f')),
                'worldBox': list(self.r(output, '6f'))}

    def tree(self, node, seen=None):
        seen = set() if seen is None else seen
        if node in seen or len(seen) >= 64:
            raise ValueError('Unbounded reconstructed source tree')
        seen.add(node)
        nameptr = self.r(node + 0x20, 'Q')[0]
        out = [{'nativeProbeAddress': node, 'name': self.c(nameptr).decode() if nameptr else '', 'vptr': hex(self.r(node, 'Q')[0]), 'flags': hex(self.r(node + 0x130, 'I')[0]), 'matrix': list(self.r(node + 0x28, '16f')), 'cachedWorldBox': list(self.r(node + 0xd0, '6f'))}]
        head = node + 0xf0
        child = self.r(head, 'Q')[0]
        while child != head:
            out.extend(self.tree(child - 8, seen))
            child = self.r(child, 'Q')[0]
        return out
