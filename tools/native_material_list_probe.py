"""Bounded original material lookup and rebuild consumers.

Source requests stop before effect acquisition. List insertion/cache and later
decision fragments use separately labelled pointer fixtures, never a successful
shader/material response injected into the source-creation call.
"""
from unicorn import UC_HOOK_CODE
from native_material_adjustment_probe import NativeMaterialAdjustmentProbe


class NativeMaterialListProbe(NativeMaterialAdjustmentProbe):
    def __init__(self, image):
        from material_list_evidence import verify_native
        verify_native(image)
        self.list_mode = None
        self.list_boundary = None
        self.list_trace = []
        super().__init__(image)
        for at in (0x1184e70, 0x111a324, 0x550fec, 0x112a6a4, 0x112920c,
                   0x1126e90, 0x553f5c, 0x1127250, 0x33c590, 0x33bc90,
                   0x33c1f4, 0x33bd9c):
            self.uc.hook_add(UC_HOOK_CODE, self.list_hook, begin=at, end=at)

    def material_hook(self, uc, at, size, data):
        if at == 0x33b854 and self.list_mode == 'rebuild':
            return  # Execute the original consumer to a narrower boundary.
        return super().material_hook(uc, at, size, data)

    def list_hook(self, uc, at, size, data):
        if self.list_mode == 'request':
            self.list_trace.append(hex(at))
            if at == 0x1127250:
                self.list_boundary = {
                    'kind': 'effectRequestNotCompleted', 'file': self.c(self.get('X5')).decode(),
                    'name': self.c(self.get('X4')).decode(), 'resultSupplied': False}
                uc.emu_stop()
        elif self.list_mode == 'rebuild' and at in (0x33c590, 0x33bc90):
            node = self.get('X23')
            self.list_boundary = {
                'kind': 'oldParameterQueryNotExecuted' if at == 0x33c590
                        else 'oldEffectInspectionNotExecuted',
                'definition': self.r(node+0x10, 'Q')[0],
                'materialPointerFixture': self.r(node+0x18, 'Q')[0],
                'waterEnabledBeforeBoundary': self.r(self.get('X29')-0x98, 'B')[0]}
            uc.emu_stop()
        elif self.list_mode == 'decision' and at in (0x33c1f4, 0x33bd9c):
            self.list_boundary = {'kind': 'keepOld' if at == 0x33c1f4 else 'requestNewMaterial',
                                  'address': hex(at)}
            uc.emu_stop()

    def material_references(self, root, info):
        """Execute the local binding-resolution fragment on relocated source bytes."""
        ref = self.local_geometry_ref(info)
        count, rel = self.r(ref+0x14, 'Ii')
        if not 0 < count <= 32:
            raise ValueError('Uncovered number of source material bindings')
        rows = []
        for i in range(count):
            binding = ref+0x18+rel+i*88
            if self.r(binding, 'Q')[0]:
                raise ValueError('External material reference is outside this local experiment')
            self.regs()
            for key, value in dict(X22=root+0x170, X26=ref+0x18, X23=i, W27=88, W28=80).items():
                self.set(key, value)
            self.run(0x111b9f8, 0x111ba54)
            definition = self.get('X1')
            rows.append({'part': i, 'definition': definition,
                         'material': self.c(self.r(definition, 'Q')[0]).decode(),
                         'localIndex': self.r(binding+0x10, 'i')[0],
                         'sourceExtraArgumentsPointer': self.r(definition+0x18, 'Q')[0],
                         'externalReference': False})
        return rows

    def use_factory(self, root, project):
        if type(project) is not bool:
            raise ValueError('Explicit original factory choice required')
        fac = self.r(root+0x178, 'Q')[0]
        self.uc.mem_write(fac, bytes(32))
        if project:
            self.material_active = True
            self.regs()
            self.set('X0', fac)
            self.run(0x550f08)
        else:
            self.w(fac, 'Q', 0x244d308)

    def material_lookup(self, root, definition, device_present):
        if type(device_present) is not bool:
            raise ValueError('Explicit device-pointer condition required')
        self.material_active, self.list_mode = True, 'request'
        self.list_boundary, self.list_trace = None, []
        out = self.alloc(8)
        self.regs()
        self.set('X0', root)
        self.set('X1', definition)
        self.set('X2', self.alloc(256) if device_present else 0)
        self.set('X8', out)
        self.uc.emu_start(0x11850fc, self.EXIT, count=200000)
        pc = self.get('PC')
        if pc not in (self.EXIT, 0x1127250):
            raise ValueError('Material lookup escaped its declared boundary')
        result = self.list_boundary or {'kind': 'returned', 'pointer': self.r(out, 'Q')[0]}
        self.list_mode, self.material_active = None, False
        return dict(result, trace=list(self.list_trace), stoppedAt=hex(pc))

    def insert_result_fragment(self, root, definition, pointer):
        """Separate post-call condition, not a fabricated source-creation result."""
        out = self.alloc(8)
        self.w(out, 'Q', pointer)
        self.regs()
        self.set('X19', definition)
        self.set('X20', root)
        self.set('X21', out)
        self.run(0x1184f20, 0x1184f58)

    def pointer_fixture(self):
        pointer = self.alloc(64)
        self.w(pointer, 'I', 100)  # Reference counter only; no effect or GPU object.
        return pointer

    def material_entries(self, root):
        rows, seen = [], set()
        head = root+0x1c8
        node = self.r(head, 'Q')[0]
        while node != head:
            if node in seen or len(seen) >= 32:
                raise ValueError('Uncovered material list structure')
            seen.add(node)
            definition, material = self.r(node+0x10, '2Q')
            rows.append({'node': node, 'definition': definition, 'pointerFixture': material,
                         'material': self.c(self.r(definition, 'Q')[0]).decode()})
            node = self.r(node, 'Q')[0]
        return rows

    def rebuild_entry(self, root, mode, device_present=True, factory_present=True):
        if mode not in (0, 1) or type(device_present) is not bool or type(factory_present) is not bool:
            raise ValueError('Explicit scoped rebuild conditions required')
        fac = self.r(root+0x178, 'Q')[0]
        self.material_active, self.list_mode, self.list_boundary = True, 'rebuild', None
        self.regs()
        for key, value in dict(X0=root, X1=self.alloc(256) if device_present else 0,
                               X2=fac if factory_present else 0, X3=self.alloc(64), W4=mode).items():
            self.set(key, value)
        self.uc.emu_start(0x33b854, self.EXIT, count=200000)
        pc = self.get('PC')
        if pc not in (self.EXIT, 0x33c590, 0x33bc90):
            raise ValueError('Material rebuild escaped its declared boundary')
        result = self.list_boundary or {'kind': 'returned', 'word': self.get('W0')}
        self.list_mode, self.material_active = None, False
        return dict(result, stoppedAt=hex(pc), mode=mode, parameterMapFixture='empty')

    def replacement_decision(self, case):
        """Execute only the original post-result branches on explicit pointer conditions."""
        if case not in ('nullEffect', 'sameEffect', 'differentEffect', 'nullNewMaterial'):
            raise ValueError('Explicit decision fragment required')
        self.list_mode, self.list_boundary = 'decision', None
        self.regs()
        self.uc.mem_write(self.get('SP')-0x100, bytes(0x500))
        self.set('X29', self.get('SP')+0x300)
        old, old_effect, new_effect = self.pointer_fixture(), self.alloc(64), self.alloc(64)
        self.w(old+8, 'Q', old_effect)
        ref = self.alloc(8)
        self.w(ref, 'Q', old)
        self.set('X24', ref)
        effect = {'nullEffect': 0, 'sameEffect': old_effect, 'differentEffect': new_effect,
                  'nullNewMaterial': new_effect}[case]
        self.w(self.get('SP')+0xb8, 'Q', effect)
        self.w(self.get('X29')-0xa8, 'Q', 0)
        self.uc.emu_start(0x33be44 if case == 'nullNewMaterial' else 0x33bd84,
                          self.EXIT, count=100)
        if self.list_boundary is None or self.get('PC') not in (0x33c1f4, 0x33bd9c):
            raise ValueError('Replacement decision escaped its fragment')
        unchanged = self.r(ref, 'Q')[0] == old
        self.list_mode = None
        return dict(self.list_boundary, case=case, oldPointerUnchanged=unchanged,
                    separatePostCallFixture=True, effectOrMaterialResultSuppliedToCreation=False)
