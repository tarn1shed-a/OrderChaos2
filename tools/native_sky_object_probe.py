"""Isolated native flag producers; GL/cache/link results and input metadata are fixtures."""
from native_sky_assembly_probe import NativeSkyAssemblyProbe
from scene_sky_object_flags import verify_native, initial_flags, provider_flags, validate_stages
from scene_material_cache import word


class NativeSkyObjectProbe(NativeSkyAssemblyProbe):
    EXT = 0x30000000
    EMPTY = 0x2528d58

    def __init__(self, image):
        verify_native(image); super().__init__(image); self.uc.mem_map(self.EXT, 0x20000)
        from unicorn import UC_HOOK_CODE
        for at in [0x30da3c, 0x2a1f90, 0x13cec0c, 0x1432db0, 0x2a1730, 0x1432f2c,
                   0x13ce9bc, 0x2a1a10, 0x1400050,
                   *[self.BASE+0x1f700+i*0x20 for i in range(6)]]:
            self.uc.hook_add(UC_HOOK_CODE, self._hook, begin=at, end=at)
        self.bind_external = False

    def _hook(self, uc, at, size, data):
        e = self.EXT
        if at == 0x1400050:
            if self.bind_external:
                if self.get('W4') != 1: raise ValueError('Only one constructed object is attached')
                self.write(self.BASE+0x6020, 'Q', e)
            return
        if at == 0x30da3c:
            if self.get('X0') != len(self.object_name.encode())+25 or self.name_allocations:
                raise ValueError('Unexpected native string allocation')
            self.name_allocations.append(self.get('X0')); self.set('X0', e+0x6000)
        elif at == 0x2a1e50 and self.phase == 'object':
            if (self.get('X0') != e+0x6018 or self.get('X1') != e+0x4000 or
                    self.get('X2') != len(self.object_name.encode())):
                raise ValueError('Unexpected object-name copy')
            uc.mem_write(self.get('X0'), bytes(uc.mem_read(self.get('X1'), self.get('X2'))))
        elif at == 0x2a1f90:
            self.events.append(['create']); self.set('W0', self.gl_handle)
        elif at == 0x13cec0c:
            if self.get('X0') != e: raise ValueError('Backend cache receiver changed')
            self.events.append(['cache']); self.set('W0', self.cache_word)
        elif at == 0x1432db0:
            self.events.append(['compile', self.get('X0')]); self.set('W0', 1)
        elif at == 0x2a1730:
            self.events.append(['attach', self.get('W0'), self.get('W1')])
        elif at == 0x1432f2c:
            if self.get('X0') != e: raise ValueError('Backend link receiver changed')
            self.events.append(['link']); self.set('W0', self.link_word)
        elif at == 0x13ce9bc:
            if self.get('X0') != e: raise ValueError('Backend cleanup receiver changed')
            self.events.append(['cleanup'])
        elif at == 0x2a1a10:
            self.events.append(['delete', self.get('W0')])
        elif self.BASE+0x1f700 <= at <= self.BASE+0x1f7a0:
            if self.get('X0') != e+0x5000: raise ValueError('Object provider receiver changed')
            slot = (at-self.BASE-0x1f700)//0x20
            if slot == 0:
                if self.string(self.get('X1')) != 'Name': raise ValueError('Provider name field changed')
                self.write(self.get('X8'), 'Q', self.EMPTY)
            elif slot == 1: self.events.append(['open', self.string(self.get('X1'))])
            elif slot == 2: self.events.append(['close'])
            elif slot == 3:
                if self.string(self.get('X1')) != 'VertexAttributeMask': raise ValueError('Provider attribute mask name changed')
                self.set('W0', self.usage_word)
            elif slot == 4:
                name = self.string(self.get('X1')); self.events.append(['bool', name])
                if name not in ('HasDiscard', 'HasAlphaTest'): raise ValueError('Unexpected object flag field')
                self.set('W0', self.discard_word if name == 'HasDiscard' else self.alpha_word)
            else:
                if self.string(self.get('X1')) != 'AlphaFunc' or self.get('X2') != 0x2499310:
                    raise ValueError('AlphaFunc callback/table changed')
                self.set('W0', self.alpha_enum)
        else:
            return super()._hook(uc, at, size, data)
        self.set('PC', self.get('X30'))

    def reset_object(self, name):
        if not isinstance(name, str) or '\0' in name or len(name.encode()) > 96:
            raise ValueError('Expected bounded object name')
        self.uc.mem_write(self.EXT, bytes(0x20000)); self.uc.mem_write(0x20000000, bytes(0x10000)); self.registers()
        self.phase = 'object'; self.object_name = name; self.name_allocations = []; self.events = []; self.bind_external = False
        self.uc.mem_write(self.EXT+0x4000, name.encode()+b'\0')

    def construct_base(self, flags=0, mask=7, control=0, metadata_count=None, index=0, name='fixture-object'):
        initial_flags(flags, mask, control, metadata_count); word(index, 16); self.reset_object(name)
        e = self.EXT; self.write(e+0x2100, 'Q', e+0x2200 if metadata_count is not None else 0)
        if metadata_count is not None: self.write(e+0x2214, 'I', metadata_count)
        self.write(e+0x2108, 'Q', e+0x2300)
        self.write(self.get('SP'), 'Q', e+0x2108)
        self.set('X0', e); self.set('W1', index); self.set('X2', e+0x4000); self.set('X3', e+0x1a000)
        self.set('W4', flags); self.set('W5', mask); self.set('W6', control); self.set('X7', e+0x2100)
        self.run(0x1466860)
        return {'wordE2': self.read(e+0xe2, 'H')[0], 'vptr': self.read(e, 'Q')[0],
                'index': self.read(e+0xe0, 'H')[0], 'references': self.read(e+8, 'I')[0],
                'name': self.string(self.read(e+0x18, 'Q')[0]), 'sourceHolders': list(self.read(e+0x2100, '2Q')),
                'metadata': self.read(e+0xb8, 'Q')[0], 'otherMetadata': self.read(e+0xc8, 'Q')[0]}

    def construct_backend(self, stages=(0, 1, None), gl_handle=71, cache_word=0, link_word=1):
        validate_stages(stages)
        for value in (gl_handle, cache_word, link_word): word(value, 32)
        self.reset_object('fixture-backend'); e = self.EXT
        self.gl_handle, self.cache_word, self.link_word = gl_handle, cache_word, link_word
        for i, flag in enumerate(stages):
            if flag is None: continue
            shader = e+0x3100+256*i; self.write(e+0x3000+8*i, 'Q', shader)
            self.write(shader+8, 'I', 100); self.write(shader+0x18, 'B', flag); self.write(shader+0x28, 'I', 100+i)
        self.write(0x2505c38, 'Q', e+0x1f100); self.write(e+0x1f100, 'Q', 0x123456789)
        sp = self.get('SP'); self.write(sp, '3Q', e+0x2108, e+0x2400, e+0x2500)
        self.set('X0', e); self.set('X2', e+0x4000); self.set('X3', e+0x3000)
        self.set('W5', 7); self.set('X7', e+0x2100); self.run(0x1436534)
        return {'wordE2': self.read(e+0xe2, 'H')[0], 'vptr': self.read(e, 'Q')[0],
                'shaderMask': self.read(e+0xdf, 'B')[0], 'interval': self.read(e+0xde, 'B')[0],
                'handle': self.read(e+0x100, 'I')[0], 'events': self.events,
                'shaderReferences': [None if f is None else self.read(e+0x3108+256*i, 'I')[0] for i, f in enumerate(stages)]}

    def apply_provider(self, before, discard_word, alpha_word=0, alpha_enum=0, usage_word=0):
        provider_flags(before, discard_word, alpha_word, alpha_enum); word(usage_word, 32)
        self.reset_object(''); e = self.EXT
        self.discard_word, self.alpha_word, self.alpha_enum, self.usage_word = discard_word, alpha_word, alpha_enum, usage_word
        self.write(e+0x18, 'Q', self.EMPTY); self.write(e+0xde, 'B', 0xff); self.write(e+0xe2, 'H', before)
        self.write(e+0x5000, 'Q', e+0x5200)
        for i, slot in enumerate((0x118, 0x70, 0x88, 0xc0, 0x1d8, 0x210)):
            self.write(e+0x5200+slot, 'Q', self.BASE+0x1f700+32*i)
        self.set('X0', e); self.set('X1', e+0x5000); self.run(0x146a1d4)
        return {'wordE2': self.read(e+0xe2, 'H')[0], 'attributeMask': self.read(e+0xd8, 'I')[0], 'events': self.events}

    def queue_constructed(self, state, scene_byte=0):
        if not isinstance(state, bytes) or len(state) != 28: raise ValueError('Expected translated28-byte state')
        self.bind_external = True
        assembled = self.assemble([{'name': 'constructed-object', 'passes': [
            {'state': state, 'programWordE2': 0, 'programByteDF': 0}]}])
        self.bind_external = False
        return {'objectWordE2': assembled['techniques'][0]['passes'][0]['programWordE2'],
                'objectReferences': assembled['techniques'][0]['passes'][0]['programReferences'],
                'queue': self.enqueue(0, scene_byte)}
