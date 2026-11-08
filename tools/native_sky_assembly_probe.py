"""Original ARM64 state translation, complete empty-reflection effect assembly,
then queue3 through the assembled pass table. Imports/program metadata are fixtures.
"""
from native_sky_mesh_probe import NativeSkyMeshProbe
from scene_sky_assembly import verify_native, assembly_layout
from scene_material_cache import word


class NativeSkyAssemblyProbe(NativeSkyMeshProbe):
    def __init__(self, image):
        verify_native(image); super().__init__(image)
        from unicorn import UC_HOOK_CODE
        for at in [0x29e010, 0x11ddd2c, 0x3c0fbc, 0x2a1e50, 0x29f4e0, 0x29eaf0,
                   0x1488cd0, 0x148b650, 0x13ed140, 0x12f3acc,
                   self.BASE+0x1f400, self.BASE+0x1f420, self.BASE+0x1f600, self.BASE+0x1f620]:
            self.uc.hook_add(UC_HOOK_CODE, self._hook, begin=at, end=at)

    def string(self, at): return bytes(self.uc.mem_read(at, 128)).split(b'\0')[0].decode()

    def _hook(self, uc, at, size, data):
        b = self.BASE
        if at == b+0x1ff00: uc.emu_stop(); return
        if at == 0x1488cd0: self.pass_calls += 1; return
        if at == 0x148b650: self.entry_calls += 1; return
        if at == 0x13ed140: self.selector_calls += 1; return
        if at == 0x12f3acc: self.frontier = True; uc.emu_stop(); return
        if at == b+0x1f400:
            if self.get('X0') != b+0x3100: raise ValueError('Modifier count receiver changed')
            self.count_calls += 1; self.set('W0', len(self.modifiers))
        elif at == b+0x1f420:
            i = self.get('W1')
            if self.get('X0') != b+0x3100 or i >= len(self.modifiers): raise ValueError('Modifier getter changed')
            self.set('X0', b+0xc000+128*i)
        elif at in (b+0x1f600, b+0x1f620):
            if self.get('X0') != b+0x1800: raise ValueError('Queue node getter receiver changed')
            self.set('W0', 0 if at == b+0x1f600 else 9)
        elif at == 0x29e010:
            self.set('X0', len(self.string(self.get('X0')).encode()))
        elif at == 0x11ddd2c:
            name = self.string(self.get('X1'))
            if name not in self.modifiers or self.get('W2') != 1: raise ValueError('Unexpected assembly intern input')
            if self.read(self.get('X0'), 'I')[0] != len(name.encode())+1: raise ValueError('Intern length changed')
            pointer = self.objects[name]; self.write(pointer+0x10, 'I', self.read(pointer+0x10, 'I')[0]+1)
            self.set('X0', pointer)
        elif at == 0x3c0fbc:
            if self.phase == 'queue':
                if self.get('X0') != 32 or self.get('W1') != 0: raise ValueError('Unexpected queue allocation')
                self.set('X0', b+0x16000)
            else:
                if self.get('X0') != self.expected_bytes or self.get('W1') != 0x1000 or self.allocations:
                    raise ValueError('Effect allocation size/flags changed')
                self.allocations.append(self.get('X0')); self.set('X0', b+0x10000)
                uc.mem_write(b+0x10000, bytes([0xa5])*self.expected_bytes)
        elif at == 0x29f0f0:
            if self.get('X0') != 24 or self.aux_allocations: raise ValueError('Unexpected effect reference allocation')
            self.aux_allocations.append(24); self.set('X0', b+0x1e000)
        elif at == 0x2a1e50:
            amount = self.get('X2')
            if amount != 0: raise ValueError('Only empty global/binding copy is covered')
        elif at == 0x29f4e0:
            text = self.string(self.get('X1'))
            if text != self.effect_name: raise ValueError('Unexpected effect name strcpy')
            uc.mem_write(self.get('X0'), text.encode()+b'\0')
        elif at == 0x29eaf0:
            if self.get('X2') != 0: raise ValueError('Only empty property default fill is covered')
        else: raise ValueError('Unexpected original import/callback in assembly probe')
        self.set('PC', self.get('X30'))

    def run(self, at, count=30000):
        self.uc.emu_start(at, self.BASE+0x1ff04, count=count)
        if self.get('PC') != self.BASE+0x1ff00: raise ValueError('Effect assembly probe exceeded bounds')

    def translate(self, source):
        if not isinstance(source, bytes) or len(source) != 88: raise ValueError('Expected88 source state bytes')
        self.registers(); self.uc.mem_write(self.BASE+0x1000, source)
        self.uc.mem_write(self.BASE+0x1100, bytes(28))
        self.set('X0', self.BASE+0x1100); self.set('X1', self.BASE+0x1000)
        self.run(0x114dd1c, 400)
        return bytes(self.uc.mem_read(self.BASE+0x1100, 28))

    def assemble(self, techniques, modifiers=(), effect_name='fixture-effect', index=0):
        expected = assembly_layout(techniques, modifiers, effect_name, index)
        b = self.BASE; self.uc.mem_write(b, bytes(0x20000)); self.uc.mem_write(0x20000000, bytes(0x10000))
        self.registers(); self.phase = 'assembly'; self.modifiers = modifiers; self.effect_name = effect_name
        self.expected_bytes = expected['allocationBytes']; self.allocations = []; self.aux_allocations = []
        self.pass_calls = self.entry_calls = self.count_calls = 0; self.techniques = techniques
        names = list(dict.fromkeys([*[t['name'] for t in techniques], *modifiers]))
        self.objects = {name: b+0xb000+128*i for i, name in enumerate(names)}
        for name, pointer in self.objects.items():
            self.write(pointer+0x10, 'I', 100); self.uc.mem_write(pointer+24, name.encode()+b'\0')
        self.write(b+0x3100, 'Q', b+0x3200)
        self.write(b+0x3210, 'Q', b+0x1f400); self.write(b+0x3218, 'Q', b+0x1f420)
        self.uc.mem_write(b+0x3300, effect_name.encode()+b'\0')
        for i, name in enumerate(modifiers): self.uc.mem_write(b+0xc000+128*i, name.encode()+b'\0')
        part = 0
        for i, technique in enumerate(techniques):
            t = b+0x5000+32*i; self.write(b+0x3500+8*i, 'Q', t)
            self.write(t, '2Q', self.objects[technique['name']], b+0x6000+72*part)
            self.write(t+0x10, 'B', len(technique['passes']))
            for record in technique['passes']:
                at, program = b+0x6000+72*part, b+0x8000+256*part
                self.uc.mem_write(at, record['state']); self.write(at+0x20, 'Q', program)
                self.write(program+8, 'I', 100); self.write(program+0xe2, 'H', record['programWordE2'])
                self.write(program+0xdf, 'B', record['programByteDF']); part += 1
        self.set('X0', b+0x3000); self.set('W1', index); self.set('X2', b+0x3300)
        self.set('X3', b+0x3100); self.set('W4', len(techniques)); self.set('X5', b+0x3500)
        self.set('X8', b+0x2000); self.run(0x1400050)
        effect = b+0x10000; table = self.read(effect+0x30, 'Q')[0]; result = []
        for i in range(len(techniques)):
            at = table+24*i; name, passes = self.read(at, '2Q'); count, flag = self.read(at+0x10, '2B')
            records = []
            for n in range(count):
                row = passes+72*n; program = self.read(row+0x20, 'Q')[0]
                records.append({'state': bytes(self.uc.mem_read(row, 28)), 'programWordE2': self.read(program+0xe2, 'H')[0],
                                'programReferences': self.read(program+8, 'I')[0],
                                'copyBits': list(self.read(row+0x46, '2B'))})
            result.append({'name': self.string(name+24), 'passCount': count, 'headerByte11': flag, 'passes': records})
        return {'packedWord': self.read(effect+0x1c, 'H')[0], 'index': self.read(effect+0x18, 'H')[0],
                'allocationBytes': self.allocations, 'auxAllocationBytes': self.aux_allocations,
                'passCalls': self.pass_calls, 'entryCalls': self.entry_calls, 'modifierCountCalls': self.count_calls,
                'outputEffect': self.read(b+0x2000, 'Q')[0], 'references': self.read(effect, 'I')[0],
                'effectName': self.string(self.read(effect+0x10, 'Q')[0]), 'techniques': result}

    def enqueue(self, index, scene_byte=0):
        word(index, 8); word(scene_byte, 8)
        if not index < len(self.techniques): raise ValueError('Queue technique index outside assembled fixture')
        b = self.BASE; self.registers(); self.uc.mem_write(0x20000000, bytes(0x10000))
        self.uc.mem_write(b+0x1000, bytes(0x1000)); self.phase = 'queue'; self.frontier = False; self.selector_calls = 0
        self.write(b+0x1038, 'Q', b+0x3000)
        self.write(b+0x3320, 'I', 0xffffffff); self.write(b+0x12a8, 'B', scene_byte)
        self.write(b+0x1400, 'Q', b+0x1500); self.write(b+0x1508, 'Q', b+0x10000); self.write(b+0x1510, 'B', index)
        self.write(b+0x1800, 'Q', b+0x1a00)
        for slot in (0x210, 0x200): self.write(b+0x1a00+slot, 'Q', b+0x1f600)
        self.write(b+0x1a58, 'Q', b+0x1f620)
        self.set('X0', b+0x1000); self.set('X1', b+0x1800); self.set('X3', b+0x1400)
        self.set('X4', 1); self.set('W5', 3); self.set('W7', 7)
        self.uc.emu_start(0x12f368c, b+0x1ff04, count=3000)
        if not self.frontier and self.get('PC') != b+0x1ff00: raise ValueError('Assembled queue probe exceeded bounds')
        if self.frontier: return {'completed': False, 'queueOffset': 0x160, 'selectorCalls': self.selector_calls, 'record': None}
        used = [off for off in (0x130, 0x148) if self.read(b+0x1000+off, 'Q')[0]]
        if len(used) != 1: raise ValueError('Unexpected assembled queue container')
        begin, end, limit = self.read(b+0x1000+used[0], '3Q')
        if (begin, end, limit) != (b+0x16000, b+0x16020, b+0x16020): raise ValueError('Assembled queue record size changed')
        return {'completed': True, 'queueOffset': used[0], 'selectorCalls': self.selector_calls,
                'record': list(self.read(begin, '3Q2I'))}
