"""Execute the original allowed-zero pass/list/finalization bodies in isolation."""
from native_effect_modifier_probe import NativeEffectModifierProbe
from scene_effect_techniques import verify_native, validate_inputs


class NativeEffectTechniqueProbe(NativeEffectModifierProbe):
    TECH = 0x40000000

    def __init__(self, image):
        verify_native(image); super().__init__(image); self.uc.mem_map(self.TECH, 0x40000)
        self.bind_techniques = False
        from unicorn import UC_HOOK_CODE
        for at in (0x11dcc20, 0x11dcd28, 0x11dcd40, 0x141c0c0, 0x1427c74,
                   0x1488d3c, 0x1428660, 0x1404728):
            self.uc.hook_add(UC_HOOK_CODE, self._hook, begin=at, end=at)

    def _hook(self, uc, at, size, data):
        t = self.TECH
        if at == 0x1400050 and self.bind_techniques:
            self.set('W4', len(self.built_rows)); self.set('X5', t+0x900)
            self.actual_factory_inputs.append({'techniqueCount': self.get('W4'), 'pointerArray': self.get('X5')})
        if self.phase == 'technique':
            if at == 0x11dcc20:
                amount = self.get('W0')
                if amount not in self.allowed_allocations: raise ValueError('Unexpected technique allocation size')
                pointer = self.heap; self.heap += (amount+15) & ~15
                if self.heap > t+0x40000: raise ValueError('Technique fixture arena exhausted')
                self.allocations_tech.append(amount); self.set('X0', pointer)
            elif at == 0x11dcd28:
                self.set('W0', self.alloc_mode); self.mode_calls.append(['get', self.alloc_mode])
            elif at == 0x11dcd40:
                self.alloc_mode = self.get('W0'); self.mode_calls.append(['set', self.alloc_mode])
            elif at == 0x141c0c0:
                pb = self.current_builder
                if (self.get('X0') != t+0x1100 or self.get('X1') != pb+0x20 or
                        self.get('W2') != 0 or self.get('W3') != 0 or self.get('W4') != 0 or
                        self.read(self.get('X5'), 'Q')[0] != 0 or self.read(self.get('X6'), 'Q')[0] != 0 or
                        self.get('X7') != t+0x1200):
                    raise ValueError('Program factory boundary arguments changed')
                self.compiler_calls += 1
                self.write(self.get('X8'), 'QI', self.current_program, 0)
            elif at == 0x1427c74:
                self.pool_calls += 1; return
            elif at == 0x1488d3c:
                self.cleanup_calls += 1; return
            elif at == 0x1428660:
                self.constructor_calls += 1; return
            elif at == 0x1404728:
                self.finalizer_calls += 1; return
            else:
                return super()._hook(uc, at, size, data)
            self.set('PC', self.get('X30')); return
        return super()._hook(uc, at, size, data)

    def _list(self, sentinel, node_offset=0):
        result = []; node = self.read(sentinel, 'Q')[0]; previous = sentinel
        while node != sentinel:
            if node in [r+node_offset for r in result] or len(result) >= 32:
                raise ValueError('Invalid bounded technique list')
            if self.read(node+8, 'Q')[0] != previous: raise ValueError('Broken original previous link')
            result.append(node-node_offset); previous, node = node, self.read(node, 'Q')[0]
        if self.read(sentinel+8, 'Q')[0] != previous: raise ValueError('Broken original list tail')
        return result

    def build(self, techniques, finalize_flags=0):
        expected = validate_inputs(techniques, finalize_flags); actual = self.query()
        if actual['countWord'] != 0 or actual['zeroAllowed'] != 1:
            raise ValueError('Only observed allowed-zero provider route is covered')
        t = self.TECH; self.uc.mem_write(t, bytes(0x40000)); self.built_rows = techniques
        self.heap = t+0x20000; self.allocations_tech = []; self.mode_calls = []; self.alloc_mode = 0
        self.compiler_calls = self.pool_calls = self.cleanup_calls = self.constructor_calls = self.finalizer_calls = 0
        self.pass_calls = self.entry_calls = 0
        self.allowed_allocations = {24, 64, *[n*72 for n in expected['passCounts']],
                                    *expected['passCounts'], *[n*32 for n in expected['passCounts']]}
        self.write(t+0x800, 'Q', t); self.write(t+0x30, 'Q', t+0x1000)
        self.write(t+0x12f0, 'Q', t+0x1100); self.write(t+0x40, 'Q', self.EXT+0x2000)
        for off in (0x58, 0x80, 0x90, 0xb0, 0xc0): self.write(t+off, '2Q', t+off, t+off)
        self.write(t+0x78, 'Q', t+0x5000); self.write(t+0x5000, 'Q', t+0x10000)
        for i in range(16): self.write(t+0x10000+96*i, 'Q', t+0x10000+96*(i+1) if i < 15 else 0)
        self.phase = 'technique'; self.programs = []; self.node_uses = []; records = []; part = 0
        for i, row in enumerate(techniques):
            name = t+0x2000+128*i; self.write(name+0x10, 'I', 100)
            self.uc.mem_write(name+24, row['name'].encode()+b'\0'); self.write(t+0x48, 'Q', name)
            for v in row['passes']:
                pb, program = t+0x3000+256*part, t+0x6000+256*part
                self.current_builder, self.current_program = pb, program; self.programs.append(program)
                self.uc.mem_write(pb, v['state']); self.write(program+8, 'I', 100)
                self.write(program+0xe2, 'H', v['programWordE2']); self.write(program+0xdf, 'B', v['programByteDF'])
                self.registers(); self.set('X0', t+0x800); self.set('X1', pb); self.set('X2', t+0x1200)
                self.run(0x1404044)
                if self.get('W0') != 1: raise ValueError('Original pass admission failed')
                self.node_uses.append(self._list(t+0x80)[-1]); part += 1
            if self._list(t+0xb0): raise ValueError('Unexpected deferred template path')
            self.registers(); self.set('X0', t+0x800); self.set('W1', finalize_flags); self.set('W2', 7)
            self.run(0x140434c)
            object_at = self.get('X0')
            if self._list(t+0x80) or self._list(t+0xb0): raise ValueError('Pending original lists not cleared')
            objects = self._list(t+0x58, 0x18)
            if not objects or objects[-1] != object_at: raise ValueError('Original technique append/return mismatch')
            self.write(t+0x900+8*i, 'Q', object_at)
            passes = self.read(object_at+8, 'Q')[0]; count, flag = self.read(object_at+0x10, '2B')
            flags_at = self.read(object_at+0x30, 'Q')[0]; reflection_at = self.read(object_at+0x28, 'Q')[0]
            record = {'name': self.string(self.read(object_at, 'Q')[0]+24), 'passCount': count,
                      'headerByte11': flag, 'flags': list(self.uc.mem_read(flags_at, count)),
                      'reflectionWords': [list(self.read(reflection_at+32*j, '4Q')) for j in range(count)],
                      'states': [bytes(self.uc.mem_read(passes+72*j, 28)).hex() for j in range(count)],
                      'programPointers': [self.read(passes+72*j+0x20, 'Q')[0] for j in range(count)]}
            records.append(record)
        return {'techniques': records, 'builderCount': self.read(t+0x50, 'Q')[0],
                'originalIndexByte': self.read(t+0xd1, 'B')[0], 'currentName': self.read(t+0x48, 'Q')[0],
                'compilerFixtureCalls': self.compiler_calls, 'poolCalls': self.pool_calls,
                'cleanupCalls': self.cleanup_calls, 'constructorCalls': self.constructor_calls,
                'finalizerCalls': self.finalizer_calls, 'allocationBytes': self.allocations_tech,
                'modeRestored': self.alloc_mode == 0, 'nodeUses': self.node_uses,
                'programReferences': [self.read(p+8, 'I')[0] for p in self.programs]}

    def assemble_built(self):
        self.bind_techniques = True; self.actual_factory_inputs = []
        try:
            result = self.assemble_provider(self.built_rows)
            result['intermediateFactoryInputs'] = self.actual_factory_inputs
            return result
        finally: self.bind_techniques = False
