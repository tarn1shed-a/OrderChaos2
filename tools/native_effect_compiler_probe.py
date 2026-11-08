"""Run original1406e94 to its post-constructor/pre-cache assembly frontier."""
from native_effect_technique_probe import NativeEffectTechniqueProbe
from scene_effect_compiler import verify_native, empty_input_contract, COMPILER, FRONTIER


class NativeEffectCompilerProbe(NativeEffectTechniqueProbe):
    def __init__(self, image):
        verify_native(image); super().__init__(image)
        from unicorn import UC_HOOK_CODE
        for at in (FRONTIER, 0x12b56a4):
            self.uc.hook_add(UC_HOOK_CODE, self._hook, begin=at, end=at)

    def _hook(self, uc, at, size, data):
        if self.phase in ('compiler', 'compiler-guard'):
            if at == FRONTIER:
                self.reached_frontier = True; uc.emu_stop(); return
            if at in (0x12b573c, 0x12b56a4):
                if self.phase != 'compiler-guard': raise ValueError('Unexpected compiler warning/error path')
                self.guard_logs += 1; self.set('PC', self.get('X30')); return
            if at == 0x11dcc20:
                amount = self.get('W0')
                if self.pointer_allocations or amount != self.contract['pointerArrayBytes']:
                    raise ValueError('Unexpected compiler auxiliary allocation')
                pointer = self.heap; self.heap += (amount+15) & ~15
                self.pointer_allocations.append(amount); self.set('X0', pointer)
                self.set('PC', self.get('X30')); return
            if at == 0x11dcd28:
                self.set('W0', self.alloc_mode); self.set('PC', self.get('X30')); return
            if at == 0x11dcd40:
                self.alloc_mode = self.get('W0'); self.set('PC', self.get('X30')); return
            if at == 0x1400050:
                stack = self.get('SP')
                self.factory_input = {'manager': self.get('X0'), 'index': self.get('W1'),
                                      'name': self.get('X2'), 'provider': self.get('X3'),
                                      'techniqueCount': self.get('W4'), 'pointerArray': self.get('X5'),
                                      'ordinaryCount': self.get('W6'), 'ordinaryArray': self.get('X7'),
                                      'stackWords': [self.read(stack, 'I')[0], self.read(stack+8, 'B')[0],
                                                     *[self.read(stack+v, 'Q')[0] for v in (0x10, 0x18, 0x20)],
                                                     self.read(stack+0x28, 'H')[0], self.read(stack+0x30, 'Q')[0]]}
                self.factory_output = self.get('X8')
                self.factory_pointers = list(self.read(self.get('X5'), str(self.get('W4'))+'Q'))
                # Observe only; every original register and array remains untouched.
        return super()._hook(uc, at, size, data)

    def _prepare(self, effect_name):
        t = self.TECH
        self.uc.mem_write(self.BASE, bytes(0x20000)); self.uc.mem_write(0x20000000, bytes(0x10000))
        self.registers(); self.bind_provider = self.bind_techniques = False
        self.contract = empty_input_contract(self.built_rows, effect_name)
        self.effect_name = effect_name; self.modifiers = []; self.expected_bytes = self.contract['effectAllocationBytes']
        self.allocations = []; self.aux_allocations = []; self.pointer_allocations = []
        self.pass_calls = self.entry_calls = self.count_calls = 0
        self.reached_frontier = False; self.guard_logs = 0; self.factory_input = None
        self.uc.mem_write(t+0x1a00, effect_name.encode()+b'\0'); self.write(t+0x38, 'Q', t+0x1a00)
        self.write(t+0x1900, 'Q', 0xfeedcafe)
        self.set('X0', t+0x1800); self.set('X1', t+0x800); self.set('X8', t+0x1900)

    def compile_frontier(self, effect_name='fixture-effect'):
        t = self.TECH
        if self.read(t+0x48, 'Q')[0] or self.read(t+0xd4, 'I')[0]:
            raise ValueError('Probe requires closed technique and zero binding matrix')
        for program in self.programs:
            if self.read(program+0xde, 'B')[0] or any(self.read(program+v, 'H')[0] for v in (0x3a, 0x6a, 0x9a)):
                raise ValueError('Probe covers explicit empty reflection only')
        for off in (0xf0, 0x100): self.write(t+off, '2Q', t+off, t+off)
        self._prepare(effect_name); self.phase = 'compiler'
        self.uc.emu_start(COMPILER, self.BASE+0x1ff04, count=100000)
        if not self.reached_frontier or self.get('PC') != FRONTIER or self.factory_input is None:
            raise ValueError('Original compiler did not reach declared assembly frontier')
        effect = self.read(self.factory_output, 'Q')[0]; table = self.read(effect+0x30, 'Q')[0]; records = []
        for i in range(self.factory_input['techniqueCount']):
            name, passes = self.read(table+24*i, '2Q'); count, flag = self.read(table+24*i+0x10, '2B')
            records.append({'name': self.string(name+24), 'passCount': count, 'headerByte11': flag,
                            'states': [bytes(self.uc.mem_read(passes+72*j, 28)).hex() for j in range(count)],
                            'programReferences': [self.read(self.read(passes+72*j+0x20, 'Q')[0]+8, 'I')[0] for j in range(count)]})
        return {'frontier': hex(self.get('PC')), 'factoryInput': self.factory_input,
                'factoryTechniquePointers': self.factory_pointers, 'pointerArrayAllocationBytes': self.pointer_allocations,
                'effectAllocationBytes': self.allocations, 'packedWord': self.read(effect+0x1c, 'H')[0],
                'index': self.read(effect+0x18, 'H')[0], 'effectReferences': self.read(effect, 'I')[0],
                'inputBuilderHolder': self.read(t+0x800, 'Q')[0], 'publicOutput': self.read(t+0x1900, 'Q')[0],
                'compilerModeAtFrontier': self.alloc_mode, 'techniques': records,
                'factoryInputsPatched': False, 'cacheRegistrationExecuted': False}

    def reject_guard(self, null_holder=False):
        if type(null_holder) is not bool: raise ValueError('Expected explicit null/open guard input')
        t = self.TECH; self._prepare('fixture-effect'); self.phase = 'compiler-guard'
        self.write(t+0x800, 'Q', 0 if null_holder else t)
        if not null_holder: self.write(t+0x48, 'Q', t+0x2000)
        self.run(COMPILER)
        return {'output': self.read(t+0x1900, 'Q')[0], 'builderHolder': self.read(t+0x800, 'Q')[0],
                'logs': self.guard_logs, 'factoryCalled': self.factory_input is not None}
