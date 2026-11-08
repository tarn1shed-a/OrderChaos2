"""Original modifier slots, builder admission and zero-mask source application."""
from native_sky_assembly_probe import NativeSkyAssemblyProbe
from scene_effect_modifiers import verify_native, builder_gate, getter_index
from scene_material_cache import word


class NativeEffectModifierProbe(NativeSkyAssemblyProbe):
    EXT = 0x30000000

    def __init__(self, image):
        verify_native(image); super().__init__(image); self.uc.mem_map(self.EXT, 0x20000)
        from unicorn import UC_HOOK_CODE
        for at in (0x1400050, 0x114d41c, 0x114d428, 0x114d440, 0x1406974, 0x12b573c, self.BASE+0x1fa00):
            self.uc.hook_add(UC_HOOK_CODE, self._hook, begin=at, end=at)
        self.bind_provider = False; self.native_counts = self.native_names = self.native_zero = 0
        self.name_indices = []

    def _hook(self, uc, at, size, data):
        e = self.EXT
        if at == 0x1400050:
            if self.bind_provider: self.set('X3', e+0x2000)
            return
        if at == 0x114d41c: self.native_counts += 1; return
        if at == 0x114d428:
            self.native_names += 1; self.name_indices.append(self.get('W1')); return
        if at == 0x114d440: self.native_zero += 1; return
        if at == 0x1406974:
            if self.phase != 'gate': raise ValueError('Unexpected builder continuation')
            self.continues = True; uc.emu_stop(); return
        if at == 0x12b573c:
            if self.phase != 'gate': raise ValueError('Unexpected modifier log')
            self.logs += 1; self.set('PC', self.get('X30')); return
        if at == self.BASE+0x1fa00:
            if (self.get('X0') != e+0x3000 or self.get('X1') != e+0x4000 or self.get('X5') != e+0x5000):
                raise ValueError('Original source-loader identity changed')
            self.loader_calls.append({'effectOffset': self.get('X2')-e-0x10000,
                                      'techniqueOffset': self.get('X3')-e-0x10000,
                                      'passOffset': self.get('X4')-e-0x10000})
            self.set('PC', self.get('X30')); return
        return super()._hook(uc, at, size, data)

    def _reset(self):
        self.uc.mem_write(self.EXT, bytes(0x20000)); self.bind_provider = False; self.phase = 'provider'
        self.write(self.EXT+0x2000, 'Q', 0x245a3f0)

    def use_source(self, source, field):
        profiles = [p for p in source['profiles'] if p['field'] == field]
        if len(profiles) != 1 or len(source['blob']) > 0x8000: raise ValueError('Uncovered source profile/arena')
        self._reset(); self.source = source; self.profile = profiles[0]; self.names = []
        self.uc.mem_write(self.EXT+0x10000, source['blob'])
        self.write(self.EXT+0x2020, 'Q', self.EXT+0x10000+self.profile['descriptorOffset'])

    def use_fixture(self, names=(), policy=0, count_word=None):
        if not isinstance(names, (list, tuple)) or len(names) > 7 or any(
                not isinstance(n, str) or not 0 < len(n.encode()) <= 64 or '\0' in n for n in names):
            raise ValueError('Expected0..7 bounded modifier-name fixtures')
        count = len(names) if count_word is None else count_word; builder_gate(count, policy)
        self._reset(); self.source = None; self.names = list(names)
        self.write(self.EXT+0x2020, 'Q', self.EXT+0x2400)
        self.write(self.EXT+0x2400, '3I', count, 0xfc, policy)
        for i, name in enumerate(names):
            self.write(self.EXT+0x2500+8*i, 'Q', self.EXT+0x6000+128*i)
            self.uc.mem_write(self.EXT+0x6000+128*i, name.encode()+b'\0')

    def query(self, index=None):
        self.registers(); self.set('X0', self.EXT+0x2000); self.run(0x114d41c); count = self.get('W0')
        self.registers(); self.set('X0', self.EXT+0x2000); self.run(0x114d440); zero = self.get('W0')
        name = None
        if index is not None:
            getter_index(index, len(self.names)); self.registers(); self.set('X0', self.EXT+0x2000)
            self.set('W1', index); self.run(0x114d428); name = self.string(self.get('X0'))
        return {'countWord': count, 'zeroAllowed': zero, 'name': name}

    def gate(self):
        self.registers(); self.phase = 'gate'; self.continues = False; self.logs = 0; e = self.EXT
        before = (self.native_counts, self.native_zero)
        self.write(e+0x4800, 'Q', 0); self.write(e+0x4810, 'Q', 0xfeedface)
        self.set('X0', e+0x4900); self.set('X1', e+0x4800); self.set('X3', e+0x4300)
        self.set('X4', e+0x2000); self.set('X8', e+0x4810)
        self.uc.emu_start(0x14068b0, self.BASE+0x1ff04, count=1000)
        if self.get('PC') not in (0x1406974, self.BASE+0x1ff00): raise ValueError('Builder gate exceeded frontier')
        return {'continues': self.continues, 'logs': self.logs,
                'countCalls': self.native_counts-before[0], 'zeroCalls': self.native_zero-before[1],
                'output': self.read(e+0x4810, 'Q')[0]}

    def apply_zero(self, technique, pass_index=0):
        word(pass_index, 32)
        if self.source is None or type(technique) is not int or not 0 <= technique < len(self.profile['techniques']):
            raise ValueError('Expected original source technique')
        row = self.profile['techniques'][technique]
        if (pass_index & 255) >= len(row['passes']): raise ValueError('Pass fixture index outside source')
        self.registers(); e = self.EXT; self.loader_calls = []
        self.write(e+0x2010, '2Q', e+0x4000, e+0x3000)
        self.write(e+0x2028, '2Q', e+0x10000+self.source['effectOffset'], e+0x10000+row['offset'])
        self.write(e+0x3000, 'Q', e+0x3100); self.write(e+0x3300, 'Q', self.BASE+0x1fa00)
        self.set('X0', e+0x2000); self.set('W2', pass_index); self.set('W3', 0); self.set('X4', e+0x5000)
        self.run(0x114d454)
        return {'returnWord': self.get('W0'), 'loaderCalls': self.loader_calls}

    def assemble_provider(self, techniques):
        actual = self.query()
        if actual['countWord'] != len(self.names) or len(self.names) > 5: raise ValueError('Assembly fixture count mismatch')
        before = self.native_counts, self.native_names
        name_start = len(self.name_indices)
        self.bind_provider = True
        result = self.assemble(techniques, self.names)
        self.bind_provider = False
        result['fixtureModifierCountCallbacks'] = result.pop('modifierCountCalls')
        result['originalModifierCountCalls'] = self.native_counts-before[0]
        result['originalModifierNameCalls'] = self.native_names-before[1]
        result['originalNameIndices'] = self.name_indices[name_start:]
        return result

    def assemble_profile(self, profile, program_flags=0):
        word(program_flags, 16)
        techniques = [{'name': t['name'], 'passes': [{'state': self.translate(p['sourceState']),
                       'programWordE2': program_flags, 'programByteDF': 0} for p in t['passes']]}
                      for t in profile['techniques']]
        return self.assemble_provider(techniques)
