"""Original type8 shell and scene-resource request parameters.

Original pre-admission is checked separately. The queue node/loader context are
explicit containers; BEFF I/O/completion, driver and GPU are not successful stubs.
"""
from source_physics import SourcePhysics


class SceneEffectRequestProbe(SourcePhysics):
    def __init__(self, image):
        super().__init__(image)
        from unicorn import UC_HOOK_CODE
        self.ends = []; self.stop = set(); self.requests = []
        for at in (0xa61ec0, 0xa62a78, 0xa5cfb8, 0x325234, 0xeaf19c):
            self.uc.hook_add(UC_HOOK_CODE, self.hook, begin=at, end=at)

    def hook(self, uc, at, size, data):
        if at in self.stop:
            self.ends.append(at); self.set('PC', self.EXIT); return
        if at == 0xa5cfb8:
            self.requests.append({'kind': 'original-async-scene-effect-request',
                'source': self.cstr(self.get('X1')).decode(), 'position': list(self.r(self.get('X2'), '3f')),
                'scale': list(self.r(self.get('X3'), '3f')), 'quaternion': [self.gf('S'+str(n)) for n in range(4)],
                'originalResourceTaskExecuted': False})
            self.set('X0', 0); self.set('PC', self.get('X30')); return
        if at == 0x325234:
            self.requests.append({'kind': 'original-sync-scene-effect-request',
                'source': self.cstr(self.get('X1')).decode(), 'argument2': self.get('W2'),
                'originalResourceProviderExecuted': False})
            self.set('PC', self.EXIT); self.ends.append(at); return
        return super().hook(uc, at, size, data)

    def fragment(self, begin, ends, regs, floats=None):
        self.stop = set(ends); self.ends = []
        try: self.call(begin, regs, floats)
        finally: self.stop = set()
        if len(self.ends) != 1: raise ValueError('Original effect fragment missed its end')
        return self.ends[0]

    def request(self, raw_itm, record_index, *, async_loading=None):
        import struct
        version, x, z, count, models = struct.unpack_from('<5i', raw_itm, 4)
        if raw_itm[:4] != b'AITM' or version != 5 or not 0 <= record_index < count:
            raise ValueError('Explicit original AITM record required')
        rec = raw_itm[24+record_index*76:24+(record_index+1)*76]
        if len(rec) != 76 or struct.unpack_from('<I', rec)[0] != 8:
            raise ValueError('Only original type8 records')
        # Execute the actual allocation/initial writes from the source worker.
        self.fragment(0xa61ae8, (0xa61ec0,), {})
        owner = self.get('X20')
        if self.r(owner, 'Q')[0] != 0x2423de8: raise ValueError('Original type8 vtable changed')
        data = self.alloc(len(raw_itm)); self.uc.mem_write(data, raw_itm)
        loader = self.alloc(0x120); root = self.alloc(0x300); settings = self.alloc(0x100)
        self.w(loader+0x10, '2i', x, z); self.w(loader+0x40, 'Q', data+24)
        self.w(loader+0x48, 'Q', data+24+count*76+4); self.w(loader+0x50, 'i', models)
        self.w(root+0x270, 'Q', settings); self.w(settings+0x84, '3i', 3, 3, 1)
        self.w(0x2528db0, 'Q', root)
        pointer = self.r(0x25071b8, 'Q')[0]; before = self.r(pointer, 'B')[0]
        if async_loading is not None:
            if type(async_loading) is not bool: raise ValueError('Explicit async-loading control required')
            self.w(pointer, 'B', int(async_loading))
        self.requests = []
        end = self.fragment(0xa62958, (0xa62a78,), {
            'X19': loader, 'X25': owner, 'X22': record_index, 'X20': 76,
            'X21': 0, 'X27': 0x2528000}, {'S8': 0})
        return {'nativeType8ConstructionExecuted': True, 'nativeRequestParameterSegmentExecuted': True,
            'requests': list(self.requests), 'end': hex(end),
            'loadedOriginalAsyncSwitch': before, 'selectedAsyncSwitch': self.r(pointer, 'B')[0],
            'noExtraLevelManagerFixture': True, 'preAdmissionMustBeVerifiedSeparately': True,
            'sourceSceneCompletionExecuted': False, 'liveServerStateSupplied': False, 'GPUExecuted': False}

    def local_effect_constructor_flags(self):
        node = self.alloc(0x310)
        # Execute the local initializer after the base transform-node boundary.
        self.fragment(0xeaf068, (0xeaf19c,), {'X19': node, 'X21': node+0x2fc,
            'W20': 0x3f800000, 'W22': 0xffffffff})
        return {'nativeLocalInitializerExecuted': True, 'baseNodeConstructorExecuted': False,
            'byte218': self.r(node+0x218, 'B')[0], 'byte219': self.r(node+0x219, 'B')[0],
            'visible21a': self.r(node+0x21a, 'B')[0], 'byte21b': self.r(node+0x21b, 'B')[0],
            'time250': self.r(node+0x250, 'I')[0], 'wholeEffectConstructed': False}
