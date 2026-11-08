"""Execute original prefix selection and source-mutation cleanup, without GL.

Rewrite stack18 is explicitly zero. Allocator and bounded C-library bodies are
fixtures; enum selection, prefix assembly, lists, empty lookup and cleanup execute.
"""
import re

from native_sky_mesh_probe import NativeSkyMeshProbe
from scene_shader_preprocess import verify_native, prefix_plan, source_view


class NativeShaderPreprocessProbe(NativeSkyMeshProbe):
    def __init__(self, image):
        verify_native(image); super().__init__(image)
        from unicorn import UC_HOOK_CODE
        for at in (0x11dcc20, 0x11dcc44, 0x2a1f70, 0x29f4c0, 0x2a1d30, 0x29e3c0, 0x148c8bc, 0x14836bc):
            self.uc.hook_add(UC_HOOK_CODE, self._hook, begin=at, end=at)

    def string_bytes(self, at):
        data = bytes(self.uc.mem_read(at, 16384))
        if b'\0' not in data: raise ValueError('Unterminated bounded prefix string')
        return data.split(b'\0')[0]

    def _hook(self, uc, at, size, data):
        if at == self.BASE+0x1ff00: uc.emu_stop(); return
        if at == 0x11dcc20:
            amount = self.get('X0'); pointer = self.heap; end = pointer+((amount+15) & ~15)
            if not 1 <= amount <= 8192 or end > self.BASE+0x1b000: raise ValueError('Unexpected prefix allocation')
            self.heap = end; self.allocations.append((pointer, amount)); self.live.add(pointer); self.set('X0', pointer)
        elif at == 0x11dcc44:
            pointer = self.get('X0')
            if pointer not in self.live: raise ValueError('Unexpected or repeated prefix free')
            self.live.remove(pointer); self.freed.append(pointer)
        elif at == 0x2a1f70:
            if self.get('X1') != 0x1f4c3a3: raise ValueError('Uncovered source-version format')
            source = self.string_bytes(self.get('X0'))
            # Explicit bounded C-library bridge, not the original sscanf body.
            match = re.match(rb'\s*#\s*version\s+(\d+)(?:\s+e(.))?', source)
            self.scan_calls += 1; self.set('W0', 0)
            if match:
                self.write(self.get('X2'), 'I', int(match[1])); self.set('W0', 1)
                if match[2]: self.write(self.get('X3'), 'B', match[2][0]); self.set('W0', 2)
        elif at == 0x29f4c0:
            amount = self.get('X2')
            if amount > 128: raise ValueError('Unexpected bounded prefix copy')
            value = self.string_bytes(self.get('X1'))[:amount]
            if amount: uc.mem_write(self.get('X0'), value+bytes(amount-len(value)))
        elif at == 0x2a1d30:
            if self.get('X1') != 0x1f4c451 or self.get('W2') != 120:
                raise ValueError('Uncovered generated shader version')
            fmt = self.string_bytes(self.get('X1'))
            value = fmt % (self.get('W2'), self.string_bytes(self.get('X3')))
            uc.mem_write(self.get('X0'), value+b'\0'); self.set('W0', len(value))
        elif at == 0x29e3c0:
            left, right = self.string_bytes(self.get('X0')), self.string_bytes(self.get('X1'))
            self.set('W0', (int(left > right)-int(left < right)) & 0xffffffff)
        elif at in (0x148c8bc, 0x14836bc):
            raise ValueError('Error formatting/token rewrite is outside prefix-probe scope')
        else: return super()._hook(uc, at, size, data)
        self.set('PC', self.get('X30'))

    def run(self, at):
        self.uc.emu_start(at, self.BASE+0x1ff04, count=100000)
        if self.get('PC') != self.BASE+0x1ff00: raise ValueError('Prefix probe exceeded instruction bound')

    def expression(self, alpha_func):
        prefix_plan(1, alpha_func=alpha_func); self.registers(); self.set('W0', alpha_func)
        self.run(0x141de74)
        return {'pointer': self.get('X0'), 'length': self.get('X1'), 'value': self.string_bytes(self.get('X0'))}

    def preprocess(self, source, stage=1, flags=16, allow_alpha=1, alpha_func=2, extra=None):
        plan = prefix_plan(stage, flags, allow_alpha, alpha_func, extra); source_view(source)
        b = self.BASE; self.uc.mem_write(b, bytes(0x20000)); self.uc.mem_write(0x20000000, bytes(0x10000))
        self.registers(); self.heap = b+0x10000; self.allocations = []; self.freed = []; self.live = set(); self.scan_calls = 0
        self.write(b+0x2000, 'Q', b+0x2100); self.write(b+0x2008, 'II', 440, flags)
        self.write(b+0x2104, 'I', plan['normalizedVersion'])
        self.uc.mem_write(b+0x4000, source+b'\0'); self.uc.mem_write(b+0x3000, b'fixture-shader\0')
        if extra is not None:
            self.uc.mem_write(b+0x8000, extra+b'\0'); self.write(self.get('SP'), 'Q', b+0x8000)
        self.write(self.get('SP')+8, 'B', allow_alpha); self.write(self.get('SP')+16, 'I', alpha_func)
        # stack18 token-rewrite switch, macro map and remaining callback inputs stay zero.
        for name, value in [('X0', b), ('X1', b+0x2000), ('X2', b+0x4000), ('X3', len(source)),
                            ('X4', b+0x3000), ('W6', stage), ('X7', b+0x7000)]: self.set(name, value)
        self.run(0x148c160)
        array = self.read(b+0x138, 'Q')[0]
        if array == 0: raise ValueError('Unexpected null prefix source array')
        segments = []; pointers = []
        for i in range(32):
            pointer = self.read(array+8*i, 'Q')[0]
            if pointer == 0: break
            pointers.append(pointer); segments.append(self.string_bytes(pointer))
        else: raise ValueError('Prefix source array did not terminate')
        mutated = bytes(self.uc.mem_read(b+0x4000, len(source)+1))
        self.registers(); self.set('X0', b); self.run(0x148ca60)
        restored = bytes(self.uc.mem_read(b+0x4000, len(source)+1)) == source+b'\0'
        return {'segments': segments, 'pointers': pointers, 'mutatedSource': mutated,
                'sourceRestored': restored, 'allocations': [n for _, n in self.allocations],
                'freed': len(self.freed), 'remainingAllocations': len(self.live), 'versionScanCalls': self.scan_calls,
                'cleanupFields': list(self.read(b+8, 'Q'))+list(self.read(b+0x30, 'Q'))+list(self.read(b+0x140, 'Q'))}
