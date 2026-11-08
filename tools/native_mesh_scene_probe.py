"""Original mesh lookup to first buffer request, plus bounded scene consumers.

No GPU result or successful material update is supplied. Parent nodes and active
slots are explicit experiments; the live scene parent is not observed. The
attachment fragment is tested separately from its unresolved material condition.
"""
import hashlib

from unicorn import UC_HOOK_CODE
from native_bres_world_bounds_probe import NativeBresWorldBoundsProbe


class NativeMeshSceneProbe(NativeBresWorldBoundsProbe):
    def __init__(self, image):
        from mesh_scene_evidence import verify_native
        verify_native(image)
        self.real_lookup = False
        self.stop_material = False
        self.stage = 'lookup'
        self.boundary = None
        self.owner = None
        super().__init__(image)
        for at in (0x1130fd8, 0x1462ff8, 0x1502704, 0x150287c,
                   0x113e3e8, 0x34138c, 0x33f7b4, 0x1181630):
            self.uc.hook_add(UC_HOOK_CODE, self.observe, begin=at, end=at)

    def hook(self, uc, at, size, data):
        if at == 0x111b8c4 and self.real_lookup:
            return  # Remove the older lookup adapter; execute this original body.
        return super().hook(uc, at, size, data)

    def observe(self, uc, at, size, data):
        if at == 0x34138c:
            self.owner = self.get('X0')
        elif at == 0x1130fd8 and self.stage == 'lookup':
            self.boundary = {'kind': 'originalConstructorEntry',
                             'args': [self.get('X'+str(i)) for i in range(8)],
                             'vertexOptions': list(self.r(self.get('X4'), 'QI')),
                             'indexOptions': list(self.r(self.get('X5'), 'QI'))}
            uc.emu_stop()
        elif at == 0x1462ff8:
            desc = self.get('X1')
            kind, usage, count = self.r(desc, '3I')
            pointer = self.r(desc+16, 'Q')[0]
            raw = bytes(uc.mem_read(pointer, count))
            spans = [v for v in self.events if v[0] == 'originalStreamBytes'
                     and v[3] <= pointer and pointer+count <= v[3]+v[2]]
            if len(spans) != 1 or kind != 0 or self.get('X30') != 0x11315b4:
                raise ValueError('First source vertex request escaped the scoped constructor path')
            span, = spans
            offset = span[1]+pointer-span[3]
            if raw != self.source_slice(offset, count):
                raise ValueError('Vertex request bytes differ from original BRES source')
            self.boundary = {'kind': 'firstVertexBufferRequest', 'sourceOffset': offset,
                             'bytes': count, 'sha256': hashlib.sha256(raw).hexdigest(),
                             'requestKind': kind, 'usageLowWord': usage,
                             'originalBytesEqual': True, 'GPUResultSupplied': False}
            uc.emu_stop()
        elif at in (0x1502704, 0x150287c):
            self.set('PC', self.get('X30'))  # Lock/unlock environment only.
        elif at == 0x113e3e8:
            count, offset, dest = self.get('W1'), self.get('W2'), self.get('X3')
            uc.mem_write(dest, self.source_slice(offset, count))
            self.events.append(['originalStreamBytes', offset, count, dest])
            self.set('X0', count)
            self.set('PC', self.get('X30'))
        elif at == 0x33f7b4 and self.stop_material:
            self.boundary = {'kind': 'materialUpdateNotExecuted',
                             'slot': self.get('W1'), 'word2': self.get('W2'),
                             'word3': self.get('W3')}
            uc.emu_stop()
        elif at == 0x1181630 and self.real_lookup:
            self.boundary = {'kind': 'externalResourceNotExecuted'}
            uc.emu_stop()

    def local_geometry_ref(self, info):
        scene = info+0xe0+self.r(info+0xe0, 'i')[0]
        visited = set()
        def visit(at):
            if at in visited or len(visited) >= 64:
                raise ValueError('Invalid source node tree')
            visited.add(at)
            count, rel = self.r(at+0x50, 'Ii')
            for i in range(count):
                desc = at+0x54+rel+i*8
                kind, ref = self.r(desc, 'Ii')
                if kind == 3:
                    return desc+4+ref
            count, rel = self.r(at+0x48, 'Ii')
            for i in range(count):
                found = visit(at+0x4c+rel+i*96)
                if found:
                    return found
        count, rel = self.r(scene+0x10, 'Ii')
        for i in range(count):
            found = visit(scene+0x14+rel+i*96)
            if found:
                return found
        raise ValueError('No source geometry reference')

    def lookup(self, info, factory, switches=(False, False), ref=None):
        if factory not in (0x2416430, 0x244d308) or len(switches) != 2 or any(type(v) is not bool for v in switches):
            raise ValueError('Explicit pinned factory and two switch fixtures required')
        pair, resource, fac = self.alloc(32), self.alloc(0x80), self.alloc(32)
        self.w(pair, '2Q', resource, fac)
        self.w(resource+8, 'I', 100)
        self.w(resource+0x48, 'Q', self.r(self.ctx, 'Q')[0])
        self.w(fac, 'Q', factory)
        self.w(0x250aee6, 'B', int(switches[0]))
        self.w(0x25347a2, 'B', int(switches[1]))
        ref = self.local_geometry_ref(info) if ref is None else ref
        driver, output = self.alloc(256), self.alloc(8)
        self.real_lookup, self.stage, self.boundary = True, 'lookup', None
        self.regs()
        for key, value in dict(X0=pair, X1=driver, X2=ref, X3=0, X8=output).items():
            self.set(key, value)
        self.uc.emu_start(0x111b8c4, self.EXIT, count=200000)
        if self.boundary is None:
            if self.get('PC') != self.EXIT or self.r(output, 'Q')[0] != 0:
                raise ValueError('Uncovered original mesh lookup result')
            return {'kind': 'nullOriginalLookup'}
        return self.boundary

    def first_vertex_request(self):
        if self.get('PC') != 0x1130fd8:
            raise ValueError('Original constructor entry required; no fake mesh result')
        self.stage, self.boundary = 'buffer', None
        self.uc.emu_start(0x1130fd8, self.EXIT, count=200000)
        if not self.boundary or self.boundary['kind'] != 'firstVertexBufferRequest':
            raise ValueError('Did not reach original first vertex request')
        return self.boundary

    def make_parent_fixture(self):
        output = self.alloc(8)
        self.regs()
        self.set('X1', self.BASE+0x5000)
        self.set('X8', output)
        self.run(0x112b518)  # Actual transform constructor, not a handwritten tree.
        return self.r(output, 'Q')[0]

    def bind_parent_fragment(self, parent):
        param = self.alloc(0xa0)
        self.w(param+0x30, 'Q', parent)
        self.regs()
        self.set('X19', self.owner)
        self.set('X21', param)
        self.run(0x33ecac, 0x33ed28)

    def select_fixture(self, slot):
        if slot not in (0, 1, 2) or self.owner is None:
            raise ValueError('Explicit active slot and constructed owner required')
        self.w(self.owner+0x59, 'B', slot)
        self.stop_material, self.boundary = True, None
        self.regs()
        self.set('X0', self.owner)
        self.uc.emu_start(0x340dc0, self.EXIT, count=200000)
        if self.boundary is None and self.get('PC') != self.EXIT:
            raise ValueError('Uncovered scene-selection branch')
        return {'boundary': self.boundary, 'ownerVisibleByte': self.r(self.owner+0x14, 'B')[0],
                'slotWeights': list(self.r(self.owner+0xb0, '2I')),
                'slotPointers': list(self.r(self.owner+0x98, '2Q'))}

    def attach_fragment(self, root):
        """Test attachment itself; do NOT supply material success to its caller."""
        self.regs()
        self.set('X21', self.owner)
        self.set('X19', root)
        self.run(0x33e870, 0x33e904)

    def translation_fixture(self, parent, xyz):
        if len(xyz) != 3:
            raise ValueError('Explicit parent translation required')
        data = self.alloc(12)
        self.w(data, '3f', *xyz)
        self.regs()
        self.set('X0', parent)
        self.set('X1', data)
        self.run(0x1364014)
        self.refresh(parent)

    def visibility_fixture(self, parent, visible):
        if type(visible) is not bool:
            raise ValueError('Explicit parent visibility required')
        self.regs()
        self.set('X0', parent)
        self.set('W1', int(visible))
        self.run(0x1362e30)

    def refresh(self, root):
        self.regs()
        self.set('X0', root)
        self.set('W1', 1)
        self.run(0x1362320)

    def world_box(self, root):
        ref, output = self.alloc(8), self.alloc(24)
        self.w(ref, 'Q', root)
        self.regs()
        self.set('X0', ref)
        self.set('W1', 1)
        self.set('X8', output)
        self.run(0x337c98)
        return list(self.r(output, '6f'))
