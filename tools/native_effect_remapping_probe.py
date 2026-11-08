"""Original packed-rule remap generation, real cache storage and real selector."""
from native_effect_registration_probe import NativeEffectRegistrationProbe
from scene_effect_compiler import FRONTIER
from scene_effect_remapping import verify_native, validate_rules


class NativeEffectRemappingProbe(NativeEffectRegistrationProbe):
    RULES = 0x60000000

    def __init__(self, image):
        verify_native(image); super().__init__(image); self.uc.mem_map(self.RULES, 0x40000)
        self.in_remap = False; self.rule_config = None
        from unicorn import UC_HOOK_CODE
        for at in (0x1408860, 0x140b78c, 0x11e14c4, 0x29fbb0):
            self.uc.hook_add(UC_HOOK_CODE, self._hook, begin=at, end=at)

    def _hook(self, uc, at, size, data):
        if self.phase == 'registration' and at == FRONTIER and self.rule_config is not None:
            self._install_rules()
        if self.phase == 'registration' and at == 0x1408860:
            self.remap_calls += 1; self.remap_return = self.get('X30')
            if len(self.built_rows) != 1: self.in_remap = True
            return
        if self.in_remap:
            if at == 0x140b78c: self.table_calls += 1; return
            if at == 0x11e14c4: self.pattern_calls += 1; return
            if at == 0x11dcc20:
                amount = self.get('W0')
                if amount not in (2*max(self.profile_count, self.variant_count), len(self.built_rows)):
                    raise ValueError('Unexpected remapping scratch allocation')
                pointer = self.rule_heap; self.rule_heap += (amount+15) & ~15
                self.rule_allocations[pointer] = amount; self.set('X0', pointer)
                self.set('PC', self.get('X30')); return
            if at == 0x11dcc44:
                pointer = self.get('X0')
                if pointer not in self.rule_allocations or pointer in self.rule_frees:
                    raise ValueError('Unexpected remapping scratch release')
                self.rule_frees.add(pointer); self.set('PC', self.get('X30')); return
            if at == 0x29fbb0:
                amount = self.profile_count*self.variant_count*len(self.built_rows)
                if self.get('X0') != amount or self.matrix_allocations: raise ValueError('Unexpected remapping table allocation')
                self.matrix_allocations.append(amount); self.set('X0', self.RULES+0x30000)
                self.set('PC', self.get('X30')); return
            if at in (0x2a1e50, 0x29eaf0):
                amount = self.get('X2')
                if not 0 <= amount <= 8: raise ValueError('Uncovered remapping copy/fill extent')
                value = bytes(uc.mem_read(self.get('X1'), amount)) if at == 0x2a1e50 else bytes([self.get('W1') & 255])*amount
                uc.mem_write(self.get('X0'), value); self.set('PC', self.get('X30')); return
            if at == 0x11dcd28:
                self.set('W0', self.alloc_mode); self.set('PC', self.get('X30')); return
            if at == 0x11dcd40:
                self.alloc_mode = self.get('W0')
                if self.get('X30') == self.remap_return: self.in_remap = False
                self.set('PC', self.get('X30')); return
        return super()._hook(uc, at, size, data)

    def _install_rules(self):
        r, t = self.RULES, self.TECH; self.uc.mem_write(r, bytes(0x40000))
        self.rule_heap = r+0x20000; self.rule_allocations = {}; self.rule_frees = set()
        self.matrix_allocations = []; self.remap_calls = self.table_calls = self.pattern_calls = 0
        self.write(t+0x1890, 'Q', self.profile_count); self.write(t+0x18a0, 'Q', self.variant_count)
        self.write(t+0x18a8, 'Q', r+0x1000 if self.rule_config else 0)
        effect = self.read(self.factory_output, 'Q')[0]; table = self.read(effect+0x30, 'Q')[0]
        names = {row['name']: self.read(table+24*i, 'Q')[0] for i, row in enumerate(self.built_rows)}
        cursor = r+0x4000
        def obj(value):
            nonlocal cursor
            at = cursor; cursor += 128; self.uc.mem_write(at+24, value.encode()+b'\0'); return at
        for i, rule in enumerate(self.rule_config):
            at = r+0x1000+8*(self.profile_count+self.variant_count)+256*i
            self.write(at, 'Q2I', obj(rule['pattern']), 1, 256 if i+1 < len(self.rule_config) else 0)
            profiles = [] if rule['profiles'] is None else rule['profiles']
            variants = [] if rule['variants'] is None else rule['variants']
            self.write(at+0x10, '2H', len(profiles), 1)
            if profiles: self.write(at+0x14, str(len(profiles))+'H', *profiles)
            part = at+0x14+2*len(profiles); self.write(part, '2H', len(variants), 1)
            if variants: self.write(part+4, str(len(variants))+'H', *variants)
            pair = (part+4+2*len(variants)+7) & ~7
            target = 0 if rule['target'] is None else names.get(rule['target'])
            if target is None: target = obj(rule['target'])
            self.write(pair, '2Q', 0 if rule['source'] is None else obj(rule['source']), target)

    def register_rules(self, rules, profiles, variants, effect_name='fixture-effect'):
        names = [row['name'] for row in self.built_rows]; validate_rules(names, rules, profiles, variants)
        self.rule_config = rules; self.profile_count, self.variant_count = profiles, variants
        result = self.register(effect_name, 'miss')
        self.output_effect = result['publicOutput']
        if self.in_remap or set(self.rule_allocations) != self.rule_frees:
            raise ValueError('Remapping temporary cleanup incomplete')
        node = self.read(self.CACHE+0x2000, 'Q')[0]; pointer = self.read(node+0x20, 'Q')[0]
        size = profiles*variants*len(names)
        return {'boundedCompilerBodyReturned': result['boundedCompilerBodyReturned'],
                'map': bytes(self.uc.mem_read(pointer, size)).hex() if pointer else None,
                'mapPointer': pointer, 'remapCalls': self.remap_calls, 'tableCalls': self.table_calls,
                'patternCalls': self.pattern_calls, 'matrixAllocationBytes': self.matrix_allocations,
                'temporaryAllocationBytes': list(self.rule_allocations.values()),
                'temporaryFrees': len(self.rule_frees), 'allocatorModeRestored': result['allocatorModeRestored']}

    def select_registered(self, base, profile, variant):
        if type(base) is not int or not 0 <= base < len(self.built_rows): raise ValueError('Uncovered group index')
        if type(profile) is not int or profile != -1 and not 0 <= profile < self.profile_count:
            raise ValueError('Uncovered explicit profile')
        if type(variant) is not int or not 0 <= variant < self.variant_count: raise ValueError('Uncovered variation')
        r = self.RULES; self.registers(); self.selector_calls = 0
        self.write(r+0x8000+8, 'Q', self.output_effect); self.write(r+0x8010, 'B', base)
        self.write(r+0x8018, 'B', variant)
        self.write(r+0x92f8, 'Q', self.TECH+0x1800); self.write(r+0x9320, 'I', profile & 0xffffffff)
        self.set('X0', r+0x8000); self.set('X1', r+0x9000)
        self.run(0x13ed140, 300)
        return self.get('W0')
