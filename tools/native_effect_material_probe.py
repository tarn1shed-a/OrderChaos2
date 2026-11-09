"""Original BDAE resource construction and source-effect association.

Byte streams, string/allocator storage and lock initialization are environment
adapters. No VFS mount, compiled effect, program, texture or GPU success is supplied.
"""
from unicorn import UC_HOOK_CODE
from native_material_list_probe import NativeMaterialListProbe


class NativeEffectMaterialProbe(NativeMaterialListProbe):
    def __init__(self, image):
        from effect_material_evidence import verify_native
        verify_native(image)
        self.effect_mode, self.effect_boundary = None, None
        self.io_active = False
        super().__init__(image)
        for at in (0x316b60, 0x15025fc, 0x3000010c, 0x30000110,
                   0x1117584, 0x1127290, 0x150f020):
            self.uc.hook_add(UC_HOOK_CODE, self.effect_hook, begin=at, end=at)

    def list_hook(self, uc, at, size, data):
        if at == 0x1127250 and self.effect_mode == 'creation':
            self.list_trace.append(hex(at))
            return  # Continue the original method to its first device dereference.
        return super().list_hook(uc, at, size, data)

    def effect_hook(self, uc, at, size, data):
        if self.io_active and at in (0x316b60, 0x15025fc, 0x3000010c, 0x30000110):
            if at == 0x316b60:
                raw = self.c(self.get('X1'))
                block = self.alloc(len(raw)+25)
                self.w(block, '3Q', len(raw), len(raw), 100)
                uc.mem_write(block+24, raw+b'\0')
                self.w(self.get('X0'), 'Q', block+24)
            elif at == 0x3000010c:
                self.set('X0', len(self.raw))
            elif at == 0x30000110:
                self.set('X0', self.cursor)
            self.set('PC', self.get('X30'))
        elif self.effect_mode == 'dependency' and at == 0x1117584:
            self.effect_boundary = {'kind': 'dependencyRequestNotExecuted',
                                    'file': self.c(self.get('X1')).decode()}
            uc.emu_stop()
        elif self.effect_mode == 'creation' and at == 0x1127290:
            self.effect_boundary = {'kind': 'firstDeviceDereferenceNotExecuted',
                                    'sourceEffectDefinition': self.get('X3'),
                                    'file': self.c(self.get('X5')).decode(),
                                    'name': self.c(self.get('X4')).decode(),
                                    'compiledEffectResultSupplied': False}
            uc.emu_stop()
        elif self.effect_mode == 'missing' and at == 0x150f020:
            self.effect_boundary = {'kind': 'originalMissingEffectDiagnostic',
                                    'format': self.c(self.get('X2')).decode(),
                                    'sourceFile': self.c(self.get('X3')).decode(),
                                    'fallbackEffectNotExecuted': True}
            uc.emu_stop()

    def resource_from_inner_stream(self, raw, name):
        if not isinstance(raw, bytes) or raw[:8] != b'BRES\xfe\xff\0\0':
            raise ValueError('Complete original inner BRES stream required')
        if not isinstance(name, str) or '\0' in name or not 0 < len(name.encode()) < 512:
            raise ValueError('Bounded original resource name required')
        self.raw, self.cursor, self.io_active = raw, 0, True
        # Explicit already-unwrapped stream policy; original 117f010 executes
        # its common branch. This is not original archive mount/open execution.
        self.w(0x25bae80, 'Q', self.alloc(0x180))
        stream, vt = self.alloc(128), self.alloc(128)
        self.w(stream, 'QI', vt, 100)
        for off, target in ((0x18, 0x30000100), (0x30, 0x30000104),
                            (0x40, 0x3000010c), (0x48, 0x30000110)):
            self.w(vt+off, 'Q', target)
        filename, ref, resource = self.alloc(len(name.encode())+1), self.alloc(16), self.alloc(176)
        self.uc.mem_write(filename, name.encode()+b'\0')
        self.w(ref, 'Q', stream)
        before = len(self.events)
        self.regs()
        for key, value in dict(X0=resource, X1=filename, X2=ref, X3=0, W4=0).items():
            self.set(key, value)
        self.run(0x117ec68)
        self.io_active = False
        self.w(resource+8, 'I', 100)  # Retain research-owned resource across fragments.
        self.ctx = resource+0x48
        buffer = self.r(self.ctx, 'Q')[0]
        if not buffer:
            raise ValueError('Original resource reader did not produce a BRES buffer')
        return {'resource': resource, 'info': self.r(buffer+0x28, 'Q')[0],
                'sourceReadByte': self.r(resource+0x50, 'B')[0],
                'originalStreamEvents': self.events[before:],
                'VFSOpenExecuted': False, 'compiledEffectCreated': False}

    def dependency_fragment(self, resource, info, index):
        if type(index) is not int or not 0 <= index < self.r(info+0xac, 'I')[0]:
            raise ValueError('Original material index required')
        self.effect_mode, self.effect_boundary = 'dependency', None
        self.regs()
        self.uc.mem_write(self.get('SP')-0x200, bytes(0x400))
        self.set('X29', self.get('SP')+0x100)
        self.w(self.get('SP')+0x40, 'Q', info)
        for key, value in dict(X20=resource, X26=info+0xb0, W14=80, X25=index,
                               X24=index*80, X23=index-1).items():
            self.set(key, value)
        self.uc.emu_start(0x1180a58, 0x1180db8, count=20000)
        pc = self.get('PC')
        if pc not in (0x1117584, 0x1180db8):
            raise ValueError('Material dependency fragment escaped scope')
        result = self.effect_boundary or {'kind': 'alreadyResolvedOrReused',
                                          'definition': self.r(self.get('X28'), 'Q')[0]}
        self.effect_mode = None
        return dict(result, stoppedAt=hex(pc))

    def associate_source_effect(self, definition, index, source_resource):
        """Run original name lookup and write-back, not a handwritten pointer patch."""
        before = self.r(definition+0x18, 'Q')[0]
        self.regs()
        self.uc.mem_write(self.get('SP')-0x200, bytes(0x400))
        self.set('X29', self.get('SP')+0x100)
        self.w(self.get('X29')-0x80, '2Q', source_resource, 0x244d308)
        for key, value in dict(X19=definition-index*80, X25=index, W14=80, X28=definition+0x18).items():
            self.set(key, value)
        self.run(0x1180d90, 0x1180dac)
        pointer = self.r(definition+0x18, 'Q')[0]
        return {'before': before, 'after': pointer,
                'effectName': self.c(self.r(pointer, 'Q')[0]).decode() if pointer else None,
                'originalLookupAndStoreExecuted': True, 'compiledEffectCreated': False}

    def creation_frontier(self, root, definition, project):
        self.use_factory(root, project)
        self.material_active, self.list_mode, self.effect_mode = True, 'request', 'creation'
        self.effect_boundary, self.list_trace = None, []
        output = self.alloc(8)
        self.regs()
        for key, value in dict(X0=root, X1=definition, X2=self.alloc(0x400), X8=output).items():
            self.set(key, value)
        self.uc.emu_start(0x11850fc, self.EXIT, count=200000)
        if self.get('PC') != 0x1127290 or not self.effect_boundary:
            raise ValueError('Creation did not reach its declared device boundary')
        self.material_active, self.list_mode, self.effect_mode = False, None, None
        return dict(self.effect_boundary, projectFactoryFixture=project, stoppedAt='0x1127290',
                    trace=list(self.list_trace))

    def missing_effect_fragment(self, original_resource):
        self.effect_mode, self.effect_boundary = 'missing', None
        self.regs()
        self.uc.mem_write(self.get('SP')-0x200, bytes(0x400))
        pair = self.alloc(16)
        self.w(pair, 'Q', original_resource)
        self.w(self.get('SP')+0x130, 'Q', pair)
        self.set('X20', 0)
        self.uc.emu_start(0x112745c, self.EXIT, count=100)
        if self.get('PC') != 0x150f020 or not self.effect_boundary:
            raise ValueError('Original missing-definition branch escaped scope')
        self.effect_mode = None
        return self.effect_boundary
