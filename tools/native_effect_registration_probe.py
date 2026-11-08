"""Bounded original compiler return, cache miss/hit and exact scratch cleanup."""
from native_effect_compiler_probe import NativeEffectCompilerProbe
from scene_effect_compiler import FRONTIER
from scene_effect_registration import verify_native, name_hash


class NativeEffectRegistrationProbe(NativeEffectCompilerProbe):
    CACHE = 0x50000000

    def __init__(self, image):
        verify_native(image); super().__init__(image); self.uc.mem_map(self.CACHE, 0x10000)
        from unicorn import UC_HOOK_CODE
        for at in (0x1503508, 0x1503598, 0x11dcc44, 0x140203c, 0x1402d1c,
                   0x14270b8, 0x142acf0, 0x14082dc, 0x14021c8, 0x13ffc08,
                   0x1430b50, 0x142aca4, 0x142064c, 0x3c5da0, 0x150530c, 0x29f220, 0x3c0fe8, 0x29e3c0):
            self.uc.hook_add(UC_HOOK_CODE, self._hook, begin=at, end=at)

    def build(self, techniques, finalize_flags=0):
        self.owned_allocations = {}
        return super().build(techniques, finalize_flags)

    def _hook(self, uc, at, size, data):
        if self.phase in ('technique', 'compiler') and at == 0x11dcc20:
            amount = self.get('W0'); super()._hook(uc, at, size, data)
            pointer = self.get('X0')
            if pointer in self.owned_allocations: raise ValueError('Scratch allocator reused live storage')
            self.owned_allocations[pointer] = amount; return
        if self.phase != 'registration': return super()._hook(uc, at, size, data)
        t, c = self.TECH, self.CACHE
        if at == FRONTIER: return  # Resume actual compiler after the prior observer stop.
        if at in (0x14082dc, 0x14021c8):
            self.hashes.append(self.get('X25' if at == 0x14082dc else 'X24')); return
        if at in self.observed_bodies:
            self.observed_bodies[at] += 1; return
        if at in (0x1503508, 0x1503598):
            pointer = self.get('X0')
            if pointer not in (0x25dd458, t+0x1848): raise ValueError('Unexpected cache lock identity')
            if at == 0x1503508: self.locks.append(pointer)
            elif not self.locks or self.locks.pop() != pointer: raise ValueError('Unbalanced original lock order')
            self.lock_events.append([hex(at), pointer])
        elif at == 0x3c0fbc:
            if self.get('X0') != 72 or self.get('W1') != 0x1000 or self.cache_allocations:
                raise ValueError('Only one pre-capacity cache-record allocation is covered')
            self.cache_allocations.append(72); self.set('X0', c+0x3000)
        elif at == 0x11dcc44:
            pointer = self.get('X0')
            if pointer not in self.owned_allocations and pointer not in (t, t+0x1a00):
                raise ValueError('Free outside declared scratch/owned builder fixtures')
            if pointer in self.freed: raise ValueError('Original compiler freed scratch twice')
            self.freed.add(pointer)
            if pointer == t:
                self.builder_before_free = {'techniqueCount': self.read(t+0x50, 'Q')[0],
                                            'name': self.read(t+0x38, 'Q')[0],
                                            'techniqueHead': self.read(t+0x58, 'Q')[0],
                                            'allocatorMode': self.alloc_mode}
        elif at == 0x29f220:
            if self.get('X0') != self.BASE+0x1e000: raise ValueError('Unexpected auxiliary delete')
            self.auxiliary_deletes += 1
        elif at == 0x3c0fe8:
            if self.get('X0') != self.fresh_effect or self.read(self.fresh_effect, 'I')[0] != 0:
                raise ValueError('Unexpected nonzero-reference effect delete')
            self.fresh_deletes += 1
        elif at == 0x150530c:
            self.thread_checks += 1; self.set('W0', 1)
        elif at == 0x29e3c0:
            self.comparisons += 1
            a, b = self.string(self.get('X0')).encode(), self.string(self.get('X1')).encode()
            self.set('W0', ((a > b)-(a < b)) & 0xffffffff)
        elif at == 0x11dcd40: self.alloc_mode = self.get('W0')
        else: return super()._hook(uc, at, size, data)
        self.set('PC', self.get('X30'))

    def register(self, effect_name='fixture-effect', mode='miss', collision_name=None):
        if mode not in ('miss', 'hit', 'collision'): raise ValueError('Uncovered cache fixture mode')
        digest = name_hash(effect_name)
        if mode == 'collision' and (collision_name == effect_name or name_hash(collision_name) != digest):
            raise ValueError('Collision fixture requires distinct names with actual equal hashes')
        frontier = self.compile_frontier(effect_name)
        t, c = self.TECH, self.CACHE; registry = t+0x1800
        self.fresh_effect = self.read(self.factory_output, 'Q')[0]
        self.uc.mem_write(c, bytes(0x10000)); self.write(0x25dd460, 'B', 1)
        self.write(t+0x110, '2Q', t+0x110, t+0x110)
        self.write(registry+0x18, 'QI', c+0x1000, 8)
        self.write(registry+0x28, '3Q', c+0x2000, c+0x2000, c+0x2040)
        for n in range(8): self.write(c+0x1000+8*n, 'Q', c+0x1000+8*n)
        if mode != 'miss':
            head = c+0x1000+8*(digest & 7)
            self.write(head, 'Q', c+0x4000); self.write(c+0x4000, '2Q', head, digest)
            self.write(c+0x4030, '2Q', c+0x6000, c+0x7000); self.write(c+0x4042, 'H', 0)
            cached_name = effect_name if mode == 'hit' else collision_name
            self.uc.mem_write(c+0x7000, cached_name.encode()+b'\0'); self.write(c+0x6000, 'I', 20)
            self.write(c+0x2000, 'Q', c+0x4000); self.write(registry+8, 'I', 1)
            self.write(registry+0x30, 'Q', c+0x2008); self.write(registry+0x40, 'H', 1)
        self.write(t+0x12f8, 'Q', c+0x8000)
        self.write(c+0x8068, '2Q', c+0x8058, c+0x8058)
        self.locks = []; self.lock_events = []; self.hashes = []; self.freed = set()
        self.cache_allocations = []; self.auxiliary_deletes = self.fresh_deletes = self.thread_checks = self.comparisons = 0
        self.observed_bodies = {at: 0 for at in (0x140203c, 0x1402d1c, 0x14270b8, 0x142acf0,
                                                0x1488d3c, 0x13ffc08, 0x1430b50, 0x142aca4, 0x142064c, 0x3c5da0)}
        self.builder_before_free = None; self.phase = 'registration'
        self.uc.emu_start(FRONTIER, self.BASE+0x1ff04, count=100000)
        if self.get('PC') != self.BASE+0x1ff00: raise ValueError('Original compiler did not complete bounded return')
        expected_frees = set(self.owned_allocations) | {t, t+0x1a00}
        if self.freed != expected_frees or self.locks or self.builder_before_free is None:
            raise ValueError('Scratch cleanup, builder release or lock accounting incomplete')
        begin, end = self.read(registry+0x28, '2Q'); slots = list(self.read(begin, str((end-begin)//8)+'Q'))
        output = self.read(t+0x1900, 'Q')[0]
        return {'mode': mode, 'nameHash': digest, 'nativeHashes': self.hashes,
                'publicOutput': output, 'freshEffect': self.fresh_effect, 'cachedFixture': c+0x6000,
                'outputReferences': self.read(output, 'I')[0], 'outputIndex': self.read(output+0x18, 'H')[0],
                'cacheCount': self.read(registry+8, 'I')[0], 'nextIndex': self.read(registry+0x40, 'H')[0],
                'cacheSlots': slots, 'cacheAllocationBytes': self.cache_allocations,
                'registrationCalls': self.observed_bodies[0x140203c], 'effectDestructorCalls': self.observed_bodies[0x13ffc08],
                'builderDestructorCalls': self.observed_bodies[0x1402d1c], 'intermediateDestructorCalls': self.observed_bodies[0x14270b8],
                'managerTreeRemovalCalls': self.observed_bodies[0x1430b50],
                'auxiliaryVirtualCalls': [self.observed_bodies[a] for a in (0x3c5da0, 0x142064c)],
                'freshEffectDeletes': self.fresh_deletes, 'auxiliaryDeletes': self.auxiliary_deletes,
                'strcmpCalls': self.comparisons, 'threadCheckCallbacks': self.thread_checks,
                'scratchAllocationsFreed': len(self.owned_allocations), 'ownedFixtureFrees': 2,
                'builderBeforeFree': self.builder_before_free, 'lockEvents': self.lock_events,
                'allocatorModeRestored': self.alloc_mode == 0, 'inputHolder': self.read(t+0x800, 'Q')[0],
                'programReferences': [self.read(p+8, 'I')[0] for p in self.programs],
                'factoryInputsPatched': frontier['factoryInputsPatched'], 'boundedCompilerBodyReturned': True}
