"""Original ARM64 state emission and bounded transparent-record experiments.

GL calls are recorded sinks. No original GPU, Android device or live scene is
executed. Explicit virtual getter results are experimental inputs, not source
wall runtime priority/position observations.
"""
import hashlib

from source_physics import SourcePhysics
from scene_render_state import verify_native

ROUTINES = {
    0x1341548: (372, '008119ddc6a6856f9b8eb9b802c74ad1c81cdbb82c562db415fc8258b6ec6d75'),
    0x134196c: (760, 'f341cfe11b4f97842ea5d8c12750b1d944897ceb8da65f2d23dac657e37657bf'),
    0x12f5770: (1884, '3b4e5057ac562c1383c29f67ece6a19745a23c133245dbce931ad8ad435619f2'),
    0x12f6920: (572, '5996b811b12913f6e20f0556ababe6813a576265c0f672bc675e3127daf3ad5f'),
}


class Probe(SourcePhysics):
    GET_BIAS = SourcePhysics.EXIT+0x800
    GET_PRIORITY = SourcePhysics.EXIT+0x810
    GET_TAG = SourcePhysics.EXIT+0x820
    GET_POSITION = SourcePhysics.EXIT+0x830
    def __init__(self, image):
        verify_native(image)
        for address, (size, digest) in ROUTINES.items():
            if hashlib.sha256(image.read(address, size)).hexdigest() != digest:
                raise ValueError('Original transparent record/sort code changed')
        self.gl = []
        super().__init__(image)
        from unicorn import UC_HOOK_CODE
        for address in (self.GET_BIAS, self.GET_PRIORITY, self.GET_TAG, self.GET_POSITION):
            self.uc.hook_add(UC_HOOK_CODE, self.hook, begin=address, end=address)

    def hook(self, uc, address, size, data):
        if address in (self.GET_BIAS, self.GET_PRIORITY, self.GET_TAG, self.GET_POSITION):
            if address == self.GET_BIAS:
                self.sf('S0', self.bias)
            elif address == self.GET_PRIORITY:
                self.set('W0', self.priority & 0xffffffff)
            elif address == self.GET_TAG:
                self.set('W0', 17)
            else:
                self.set('X0', self.position_data)
            self.set('PC', self.get('X30'))
            return
        name = self.imports.get(address, '')
        if name.startswith('gl'):
            self.gl.append({'name': name, 'args': [self.get('W'+str(i)) for i in range(4)]})
            self.set('PC', self.get('X30'))
            return
        super().hook(uc, address, size, data)

    def distance(self, camera, position, *, mode='explicit', bias=0, priority=3):
        if mode not in ('explicit', 'matrix', 'box'):
            raise ValueError('Unknown original distance-input branch')
        self.bias, self.priority = bias, priority
        node, vtable, record, eye = self.alloc(0x200), self.alloc(0x220), self.alloc(40), self.alloc(12)
        self.w(node, 'Q', vtable)
        self.w(eye, '3f', *camera)
        for offset, address in ((0x58, self.GET_TAG), (0x1d8, self.GET_BIAS), (0x1e8, self.GET_PRIORITY),
                                (0x80, self.GET_POSITION), (0x90, self.GET_POSITION)):
            self.w(vtable+offset, 'Q', address)
        self.position_data = self.alloc(64)
        if mode == 'box':
            self.w(node+0x131, 'B', 8)
            self.w(self.position_data, '6f', *(v-1 for v in position), *(v+1 for v in position))
        else:
            self.w(self.position_data+(0x30 if mode == 'matrix' else 0), '3f', *position)
        self.call(0x1341548, {'X0': record, 'X1': node, 'X2': eye, 'X3': 0, 'X4': 0,
                             'X5': self.position_data if mode == 'explicit' else 0, 'W6': 0x7fffffff, 'W7': 1})
        return {'priority': self.r(record+24, 'i')[0], 'tag': self.r(record+28, 'I')[0], 'distance': self.r(record+32, 'f')[0]}

    def sort(self, rows):
        """Original heap helper + swaps at12f5bcc; null-material fixtures only."""
        n = len(rows)
        records = self.alloc((n+1)*40)
        context = self.alloc(8)
        for i, row in enumerate(rows, 1):
            self.w(records+i*40, '3QiIfI', row['id'], 0, 0, row['priority'], 0, row['distance'], 0)
        # Exactly the source 1-based heap argument layout and 36-byte exchanges;
        # the final four padding bytes are not part of the sort key/record copy.
        for index in range((n-1)//2+1, 0, -1):
            self.call(0x134196c, {'X0': records, 'W1': index, 'W2': n+1, 'X3': context})
        for end in range(n, 0, -1):
            a, b = records+40, records+end*40
            first, last = bytes(self.uc.mem_read(a, 36)), bytes(self.uc.mem_read(b, 36))
            self.uc.mem_write(a, last)
            self.uc.mem_write(b, first)
            self.call(0x134196c, {'X0': records, 'W1': 1, 'W2': end, 'X3': context})
        return [self.r(records+i*40, 'Q')[0] for i in range(1, n+1)]


def state_proof(image, effect):
    probe = Probe(image)
    _, table = effect.section(164)
    results = []
    for field in (32, 36):
        profile = effect.rel(table+field)
        technique = effect.rel(profile+4)
        source_pass = effect.rel(technique+12)
        src, out, device = probe.alloc(88), probe.alloc(28), probe.alloc(0x3000)
        probe.uc.mem_write(src, effect.b[source_pass+72:source_pass+160])
        probe.call(0x114dd1c, {'X0': out, 'X1': src})
        state = bytes(probe.uc.mem_read(out, 28))
        probe.uc.mem_write(device+0x38+0x48c, state)
        probe.gl = []
        probe.call(0x1433a54, {'X0': device+0x38, 'X1': out})
        calls = {x['name']: x['args'] for x in probe.gl}
        if (calls.get('glBlendEquation', [])[:1] != [32774] or
                calls.get('glBlendFunc', [])[:2] != [770, 771] or
                calls.get('glDepthMask', [])[:1] != [0] or
                calls.get('glDepthFunc', [])[:1] != [515]):
            raise ValueError('Original blended-wall GL emission differs')
        results.append({'profileField': field, 'state28': state.hex(), 'calls': probe.gl})
    return {'nativeCPU': True, 'originalGPUObserved': False, 'profiles': results}
