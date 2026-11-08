"""Execute original map normalization -> factory flag -> shader constructor.

Stream/tree insertion and preprocessing/GL bodies are explicit fixtures. Original
map bytes stay at their parsed addresses; the factory reads their actual headers.
"""
from native_sky_object_probe import NativeSkyObjectProbe
from scene_shader_metadata import verify_native, map_fixture, shader_word
from scene_material_cache import word


class NativeShaderMetadataProbe(NativeSkyObjectProbe):
    def __init__(self, image):
        verify_native(image); super().__init__(image)
        from unicorn import UC_HOOK_CODE
        for at in [0x2a0d70, 0x29fbb0, 0x1435f54, 0x148c160,
                   0x2a0930, 0x2a1b60,
                   *[self.BASE+0x1f800+32*i for i in range(7)]]:
            self.uc.hook_add(UC_HOOK_CODE, self._hook, begin=at, end=at)

    def _hook(self, uc, at, size, data):
        e = self.EXT
        if at == 0x2a0d70:
            if self.string(self.get('X2')) != '%s/file.map' or self.get('X1') != 63:
                raise ValueError('Manifest path formatter changed')
            path = self.string(self.get('X3'))+'/file.map'; self.path = path
            uc.mem_write(self.get('X0'), path.encode()+b'\0'); self.set('W0', len(path))
        elif at == 0x29fbb0:
            if self.get('X0') != len(self.map_data)+1: raise ValueError('Manifest allocation changed')
            self.set('X0', e+0x10000)
        elif at == 0x1435f54:
            if self.get('X0') != e+0x10e8: raise ValueError('Manifest insertion receiver changed')
            key, alias = self.read(self.get('X1'), '2Q')
            self.records.append({'pointer': key, 'aliasPointer': alias, 'key': self.string(key),
                                 'alias': self.string(alias) if alias else None,
                                 'keyOffset': key-e-0x10000,
                                 'firstFlag': self.read(key-4, 'B')[0], 'discardFlag': self.read(key-2, 'B')[0]})
        elif self.BASE+0x1f800 <= at <= self.BASE+0x1f8c0:
            slot = (at-self.BASE-0x1f800)//32
            receiver = self.get('X0'); self.callbacks.append(slot)
            if slot == 0:
                if receiver != e+0x2000: raise ValueError('Manifest root receiver changed')
                self.set('X0', e+0x2800)
            elif slot == 1:
                if receiver != e+0x2400 or self.string(self.get('X1')) != 'fixture-shaders/file.map':
                    raise ValueError('Manifest stream open changed')
                self.write(self.get('X8'), 'Q', e+0x2600)
            elif slot == 2:
                if receiver != e+0x2600: raise ValueError('Manifest stream size changed')
                self.set('X0', len(self.map_data))
            elif slot == 3:
                if (receiver != e+0x2600 or self.get('X1') != e+0x10000 or
                        self.get('W2') != len(self.map_data)):
                    raise ValueError('Manifest stream read changed')
                if self.map_data: uc.mem_write(self.get('X1'), self.map_data)
            elif slot == 4:
                if receiver != e+0x2000 or self.get('X1') != e+0x10e8:
                    raise ValueError('Manifest install receiver changed')
            elif slot == 5:
                if receiver != e+0xa038: raise ValueError('Capability receiver changed')
                self.set('W0', self.capability_word)
            else: raise ValueError('Unexpected shader fixture callback')
        elif at == 0x148c160:
            if self.get('X2') != e+0xc000 or self.get('X3') != len(self.sources[0].encode()):
                raise ValueError('Preprocessor source input changed')
            self.preprocess_inputs.append(self.read(self.get('SP')+0x18, 'B')[0])
            obj = self.get('X0'); uc.mem_write(obj, bytes(0x168))
            self.write(obj+0x138, 'Q', e+0x9000 if self.preprocess_ok else 0)
            for off in (0x148, 0x158): self.write(obj+off, '2Q', obj+off, obj+off)
        elif at == 0x29f0f0 and self.phase == 'shader':
            if self.get('X0') != 0x30 or self.shader_allocations: raise ValueError('Shader allocation changed')
            self.shader_allocations.append(0x30); self.set('X0', e+0x8000)
        elif at == 0x2a1e50 and self.phase == 'shader':
            if (self.get('X0') != e+0x6018 or self.get('X1') != e+0x4000 or
                    self.get('X2') != len(self.object_name.encode())):
                raise ValueError('Shader-name copy changed')
            uc.mem_write(self.get('X0'), bytes(uc.mem_read(self.get('X1'), self.get('X2'))))
        elif at == 0x2a0930:
            self.events.append(['createShader', self.get('W0')]); self.set('W0', self.gl_handle)
        elif at == 0x2a1b60:
            n = self.get('W1')
            if self.get('W0') != self.gl_handle or self.get('X2') != e+0x9000 or self.get('X3') != 0:
                raise ValueError('glShaderSource arguments changed')
            self.events.append(['source', n, [self.string(self.read(self.get('X2')+8*i, 'Q')[0]) for i in range(n)]])
        elif at == 0x1432db0 and self.phase == 'shader':
            if self.get('X0') != e+0x8000: raise ValueError('Shader compile receiver changed')
            self.events.append(['compileShader', self.compile_word])
            if self.compile_word & 1:
                flags = self.read(e+0x8018, 'I')[0]; self.write(e+0x8018, 'I', flags | 8)
            self.set('W0', self.compile_word)
        else: return super()._hook(uc, at, size, data)
        self.set('PC', self.get('X30'))

    def parse_map(self, data):
        map_fixture(data); self.reset_object('fixture-shader'); e = self.EXT
        self.map_data = data; self.records = []; self.callbacks = []; self.path = None
        self.write(0x2505c38, 'Q', e+0x1f100); self.write(e+0x1f100, 'Q', 0x123456789)
        self.write(e+0x10d8, 'Q', e+0x2000); self.write(e+0x1058, 'Q', e+0x2200)
        self.write(e+0x2000, 'Q', e+0x2100); self.write(e+0x24e8, 'Q', e+0x2300)
        self.write(e+0x2350, 'Q', e+0x2400); self.write(e+0x2400, 'Q', e+0x2500)
        self.write(e+0x2600, 'Q', e+0x2700); self.write(e+0x2608, 'I', 100)
        for obj, slot, n in [(0x2100, 0x18, 0), (0x2500, 0x18, 1),
                             (0x2700, 0x40, 2), (0x2700, 0x18, 3), (0x2100, 0x10, 4)]:
            self.write(e+obj+slot, 'Q', self.BASE+0x1f800+32*n)
        self.uc.mem_write(e+0x2800, b'fixture-shaders\0'); self.set('X0', e+0x1000)
        self.run(0x141cf60)
        self.loaded_callbacks = list(self.callbacks)
        return {'records': self.records, 'loadedByte': self.read(e+0x1198, 'B')[0],
                'streamReferences': self.read(e+0x2608, 'I')[0], 'path': self.path,
                'callbacks': self.callbacks, 'buffer': bytes(self.uc.mem_read(e+0x10000, len(data)+1))}

    def _shader_inputs(self, stage, sources, compile_word, handle):
        shader_word(stage, 0); word(compile_word, 32); word(handle, 32)
        if (not isinstance(sources, (list, tuple)) or len(sources) > 3 or
                any(not isinstance(s, str) or '\0' in s or len(s.encode()) > 96 for s in sources)):
            raise ValueError('Expected up to three bounded source-string fixtures')
        e = self.EXT; self.registers(); self.phase = 'shader'
        self.uc.mem_write(0x20000000, bytes(0x10000)); self.name_allocations = []
        self.sources = sources; self.compile_word = compile_word; self.gl_handle = handle
        self.events = []; self.callbacks = []; self.shader_allocations = []; self.preprocess_inputs = []
        self.capability_word = 0
        self.uc.mem_write(e+0x8000, bytes(0x2000))
        for i, s in enumerate(sources):
            self.uc.mem_write(e+0xc000+128*i, s.encode()+b'\0')
            self.write(e+0x9000+8*i, 'Q', e+0xc000+128*i)
        self.write(e+0xa038, 'Q', e+0xd000)
        self.write(e+0xd0c0, 'Q', self.BASE+0x1f8a0)
        self.write(0x2505c38, 'Q', e+0x1f100); self.write(e+0x1f100, 'Q', 0x123456789)

    def _shader_result(self):
        e = self.EXT
        return {'word18': self.read(e+0x8018, 'I')[0], 'vptr': self.read(e+0x8000, 'Q')[0],
                'name': self.string(self.read(e+0x8010, 'Q')[0]), 'handle': self.read(e+0x8028, 'I')[0],
                'cacheStatus': self.read(e+0x802c, 'H')[0], 'references': self.read(e+0x8008, 'I')[0],
                'events': self.events}

    def construct_shader(self, stage, flag, sources=(), compile_word=1, handle=91):
        shader_word(stage, flag); self.reset_object('fixture-shader')
        self._shader_inputs(stage, sources, compile_word, handle); e = self.EXT
        self.set('X0', e+0x8000); self.set('W1', stage); self.set('X2', e+0x4000)
        self.set('X3', e+0x9000); self.set('X4', e+0xa000); self.set('W5', flag)
        self.set('X7', e+0xb100); self.run(0x14368e4)
        return {**self._shader_result(), 'cachedBeforeCompile': self.read(e+0xb100, 'B')[0]}

    def factory_from_map(self, record=None, stage=1, preprocess_ok=True):
        if (record is not None and (type(record) is not int or not 0 <= record < len(self.records))) or type(preprocess_ok) is not bool:
            raise ValueError('Expected explicit parsed record index or absent descriptor')
        self._shader_inputs(stage, ('fixture-preprocessed-source',), 1, 91); e = self.EXT
        self.preprocess_ok = preprocess_ok
        descriptor = e+0xb000 if record is not None else 0
        if descriptor: self.write(descriptor, '2Q', self.records[record]['pointer'], self.records[record]['aliasPointer'])
        self.write(self.get('SP')+0x28, 'Q', descriptor)
        self.set('X0', e+0xa000); self.set('W1', stage); self.set('X2', e+0xc000)
        self.set('X3', len(self.sources[0].encode())); self.set('X5', e+0x4000)
        self.set('X8', e+0xb200); self.run(0x1424d2c)
        pointer, status = self.read(e+0xb200, 'QI')
        return {'output': pointer, 'status': status, 'preprocessInputs': self.preprocess_inputs,
                'allocations': self.shader_allocations, 'shader': self._shader_result() if pointer else None}
