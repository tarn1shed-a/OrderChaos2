"""Original material-option/cache branches, stopping before unresolved rebuilds.

Only bounded printf and C++ string storage are added environment adapters.
No preparation, shader, texture or GPU success is supplied to the original code.
"""
from unicorn import UC_HOOK_CODE
from native_mesh_scene_probe import NativeMeshSceneProbe


class NativeMaterialAdjustmentProbe(NativeMeshSceneProbe):
    def __init__(self, image):
        from material_adjustment_evidence import verify_native
        verify_native(image)
        self.material_active = False
        self.material_mode = None
        self.material_trace = []
        self.option_result = None
        super().__init__(image)
        for at in (0x2a1d30, 0x3cf0b8, 0x33f870, 0x33f87c, 0x33abb8,
                   0x33b854, 0x327160, 0x33f8f4, 0x33f970):
            self.uc.hook_add(UC_HOOK_CODE, self.material_hook, begin=at, end=at)

    def observe(self, uc, at, size, data):
        if at == 0x33f7b4 and self.material_active:
            return  # Execute original adjustment, rather than the older stop.
        return super().observe(uc, at, size, data)

    def material_hook(self, uc, at, size, data):
        if not self.material_active:
            return
        if at == 0x2a1d30:
            raw = self.c(self.get('X1'))
            if b'%' in raw:
                raise ValueError('Uncovered material macro printf format')
            uc.mem_write(self.get('X0'), raw+b'\0')
            self.set('W0', len(raw))
            self.set('PC', self.get('X30'))
        elif at == 0x3cf0b8:
            dest, length = self.get('X0'), self.get('X2')
            if length > 4096:
                raise ValueError('Material macro string exceeds bounded storage')
            raw = bytes(uc.mem_read(self.get('X1'), length))
            block = self.alloc(length+25)
            self.w(block, 'QQi', length, length, 0)
            uc.mem_write(block+24, raw+b'\0')
            self.w(dest, 'Q', block+24)
            self.set('PC', self.get('X30'))
        elif at == 0x33f870:
            self.option_result = {'requestedFlags': self.get('W22'), 'cachedFlags': self.get('W11')}
        elif at == 0x33f87c and self.material_mode == 'options':
            uc.emu_stop()
        elif at in (0x33abb8, 0x33b854):
            self.boundary = {'kind': 'materialPreparationNotExecuted' if at == 0x33abb8
                             else 'materialRebuildNotExecuted', 'address': hex(at)}
            uc.emu_stop()
        elif at == 0x327160:
            loader, ref = self.get('X0'), self.get('X1')
            root = self.r(ref, 'Q')[0]
            self.material_trace.append({'kind': 'originalReloadEntry', 'mode': self.get('W2'),
                                        'flags': self.get('W3'),
                                        'rootStamp': self.r(root+0x148, 'I')[0],
                                        'loaderFlags': self.r(loader+8, 'I')[0],
                                        'variantName': self.c(self.r(loader+0x10, 'Q')[0]).decode(),
                                        'defines': self.c(self.r(loader+0x18, 'Q')[0]).decode()})
        elif at in (0x33f8f4, 0x33f970):
            self.material_trace.append({'kind': 'originalReloadReturned', 'word': self.get('W0')})

    def source_shadow_field(self, record, config_value):
        """Execute both original consumers of ITM+0x40 bit0, with explicit config."""
        if len(record) != 76 or config_value not in (0, 1, 2):
            raise ValueError('Original ITM record and explicit scoped config required')
        raw = self.alloc(76)
        self.uc.mem_write(raw, bytes(record))
        self.regs()
        self.set('X23', raw)
        self.run(0xa61cf8, 0xa61d10)
        source_bit = self.r(self.get('SP')+0xc8, 'B')[0]
        param = self.alloc(0xa0)
        self.w(param+0x98, 'B', source_bit)
        config = self.r(0x2528220, 'Q')[0]
        self.w(config+0x40, 'I', config_value)
        self.regs()
        self.set('X22', 0x2528000)
        self.set('X21', param)
        self.set('X19', self.owner)
        self.run(0x33ed7c, 0x33ed9c)
        return {'sourceBit': source_bit, 'explicitConfigValue': config_value,
                'ownerByte178': self.r(self.owner+0x178, 'B')[0]}

    def atlas_presence_fixture(self, slot, present):
        """Only a pointer condition, never a constructed/loaded texture."""
        if slot not in (0, 1) or type(present) is not bool:
            raise ValueError('Explicit slot and texture-pointer condition required')
        vector, marker = self.alloc(8), self.alloc(16)
        self.w(vector, 'Q', marker if present else 0)
        self.w(self.owner+0xb8+slot*24, '3Q', vector, vector+8, vector+8)

    def adjustment(self, slot, fading=False, special=False, options_only=False):
        if slot not in (0, 1) or any(type(v) is not bool for v in (fading, special, options_only)):
            raise ValueError('Explicit bounded material inputs required')
        self.material_active = True
        self.material_mode = 'options' if options_only else 'body'
        self.option_result, self.material_trace, self.boundary = None, [], None
        before = {'processedBits': self.r(self.owner+0x5b, 'B')[0],
                  'cachedFlags': self.r(self.owner+0x90+slot*4, 'I')[0]}
        self.regs()
        self.set('X0', self.owner)
        self.set('W1', slot)
        self.set('W2', int(fading))
        self.set('W3', int(special))
        self.uc.emu_start(0x33f7b4, self.EXIT, count=200000)
        pc = self.get('PC')
        if pc not in (self.EXIT, 0x33f87c, 0x33abb8, 0x33b854):
            raise ValueError('Material execution escaped its declared boundary')
        result = {'options': self.option_result, 'boundary': self.boundary,
                  'stoppedAt': hex(pc), 'returnedWord': self.get('W0') if pc == self.EXIT else None,
                  'trace': self.material_trace, 'before': before,
                  'after': {'processedBits': self.r(self.owner+0x5b, 'B')[0],
                            'cachedFlags': self.r(self.owner+0x90+slot*4, 'I')[0]}}
        self.material_active = False
        return result
