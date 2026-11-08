"""Original root attachment/context propagation and static classifier16.

Synthetic stable trees use original concrete virtual tables. Only mutex bodies
are intercepted during attachment. Resource loading, reparenting and gate
transitions are not executed. Static submission retains explicit query/queue
fixtures but executes the original classifier with full uint64 context words.
"""
from native_sky_mesh_probe import NativeSkyMeshProbe
from scene_sky_material import verify_native, classification_word


class NativeSkyMaterialProbe(NativeSkyMeshProbe):
    LOCKS = (0x1502ff4, 0x1503330, 0x1502cf0, 0x1502fc0)

    def __init__(self, image):
        verify_native(image)
        super().__init__(image)
        from unicorn import UC_HOOK_CODE
        for at in (*self.LOCKS, 0x119700c):
            self.uc.hook_add(UC_HOOK_CODE, self._hook, begin=at, end=at)

    def _hook(self, uc, at, size, data):
        if at in self.LOCKS:
            if self.get('X0') != 0x25dd058: raise ValueError('Root binding mutex receiver changed')
            self.lock_calls.append(at); self.set('PC', self.get('X30')); return
        if at == 0x119700c:
            if self.get('X0') != self.BASE+0x4000: raise ValueError('Static classification receiver changed')
            if (self.get('W1') != 0 or self.get('X2') != self.BASE+0x5000 or
                    self.get('W3') != self.part or self.get('W4') != classification_word(self.context_word)):
                raise ValueError('Static classification ABI changed')
            self.static_calls += 1
            return  # Execute the two original instructions, including mov W0,16.
        super()._hook(uc, at, size, data)

    def static_submit(self, part_count, flags=0, context_word=0):
        from scene_sky_material import static_submissions
        static_submissions(part_count, flags); classification_word(context_word)
        self.construct(); self.registers(); self.classifications = [16]*part_count
        self.context_word = context_word; self.submissions = []; self.cleanup = []
        self.delegate_calls = 0; self.static_calls = 0
        self.write(self.BASE+0x130, 'I', flags | 0x18)
        self.write(self.BASE+0x118, 'Q', self.BASE+0x2000)
        self.write(self.BASE+0x2038, 'Q', self.BASE+0x5000)
        self.write(self.BASE+0x2080, 'Q', self.BASE+0x6000)
        self.write(self.BASE+0x4000, 'Q', self.BASE+0x8000)
        self.write(self.BASE+0x7008, 'I', 1000)
        for slot in (0x20, 0x28, 0x30, 0x60, 0x80):
            self.write(self.BASE+0x8000+slot, 'Q', self.BASE+0x1f000+slot)
        self.write(self.BASE+0x80a0, 'Q', 0x119700c)
        self.write(self.BASE+0x6000, 'Q', self.BASE+0x9000)
        self.write(self.BASE+0x9010, 'Q', self.BASE+0x1f0c0)
        self.set('X1', self.BASE); self.set('X2', context_word)
        self.uc.emu_start(0x13246d8, self.BASE+0x1ff04, count=10000)
        if self.get('PC') != self.BASE+0x1ff00: raise ValueError('Static submission exceeded bounds')
        return {'submissions': self.submissions, 'cleanupParts': self.cleanup,
                'returnWord': self.get('W0'), 'staticClassificationCalls': self.static_calls}

    def _node_fixture(self, node, vptr, context, gate):
        self.write(node, 'Q', vptr)
        self.write(node+0x118, '2Q', context, node)
        self.write(node+0x130, 'I', 0x31e0 | (0x18 if gate else 0))
        self.write(node+0xf0, '2Q', node+0xf0, node+0xf0)
        self.write(node+0x100, '2Q', node+0x100, node+0x100)
        offset = self.read(vptr-0x20, 'q')[0]
        self.write(node+offset+8, 'I', 100)

    def attach(self, child_count=1, gate=True, model_present=True, parent_present=True):
        if type(child_count) is not int or not 0 <= child_count <= 8 or any(type(v) is not bool for v in (gate, model_present, parent_present)):
            raise ValueError('Invalid bounded stable attachment fixture')
        self.construct(False); template = bytes(self.uc.mem_read(self.BASE, 0x190))
        self.uc.mem_write(self.BASE, bytes(0x20000)); self.registers(); self.lock_calls = []
        parent, root, scene = self.BASE+0x1000, self.BASE+0x2000, self.BASE+0x5000
        self._node_fixture(parent, 0x2486960, scene, gate)
        self._node_fixture(root, 0x24604d8, 0, gate)
        children = [self.BASE+0xb000+0x400*i for i in range(child_count)]
        for i, node in enumerate(children):
            self.uc.mem_write(node, template); self.write(node+0x120, 'Q', node)
            self.write(node+0x130, 'I', 0x31e0 | (0x18 if gate else 0))
            self.write(node+0xe8, 'Q', root)
            self.write(node+8, '2Q', children[i+1]+8 if i+1 < child_count else root+0xf0,
                       children[i-1]+8 if i else root+0xf0)
            self.write(node+0xf0, '2Q', node+0xf0, node+0xf0)
        if children: self.write(root+0xf0, '2Q', children[0]+8, children[-1]+8)
        # These scene members match the traced initializer; the initializer as
        # a whole is not executed by this stable-tree fixture.
        self.write(scene+0x80, 'Q', scene)
        self.write(self.BASE+0xa008, 'Q', root if model_present else 0)
        self.write(self.BASE+0xa100, 'Q', parent if parent_present else 0)
        self.set('X0', self.BASE+0xa000); self.set('X1', self.BASE+0xa100)
        self.uc.emu_start(0x3381f0, self.BASE+0x1ff04, count=10000)
        if self.get('PC') != self.BASE+0x1ff00: raise ValueError('Root attachment exceeded bounds')
        return {'rootContext': self.read(root+0x118, 'Q')[0],
                'childContexts': [self.read(node+0x118, 'Q')[0] for node in children],
                'rootParent': self.read(root+0xe8, 'Q')[0],
                'parentChildren': list(self.read(parent+0xf0, '2Q')),
                'rootReferences': self.read(root+self.read(0x24604d8-0x20, 'q')[0]+8, 'I')[0],
                'lockCalls': self.lock_calls, 'scene': scene, 'parent': parent, 'root': root}
