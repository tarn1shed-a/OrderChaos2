"""Original ARM64 font rasterization/layout with explicit host graphics buffers.

File/allocator/thread ABI and GPU resource handles are host interfaces. The
font face, glyph cache, rasterizer, layout, outline vertices and indices execute
original instructions. No Android GL context or original live actor is claimed.
"""
import base64
import hashlib
import io
import struct

from source_physics import SourcePhysics
from head_name_evidence import verify_native

WOFF_SHA256 = 'db0deb165609fa1026e97bf528e596915028aca0472958f124ad3c8ef1b4cd88'


def full_font_from_woff(raw):
    """Unwrap existing full source tables; never subset or use a system font."""
    from fontTools.ttLib import TTFont
    from fontTools.ttLib.sfnt import SFNTWriter
    if hashlib.sha256(raw).hexdigest() != WOFF_SHA256:
        raise ValueError('Unverified original full font container')
    font = TTFont(io.BytesIO(raw), lazy=True, recalcTimestamp=False)
    out = io.BytesIO(); writer = SFNTWriter(out, len(font.reader.keys()), font.sfntVersion)
    for tag in sorted(font.reader.keys()):
        writer[tag] = font.reader[tag]
    writer.close()
    decoded = out.getvalue()
    check = TTFont(io.BytesIO(decoded), lazy=True)
    for tag in font.reader.keys():
        a, b = font.reader[tag], check.reader[tag]
        if tag == 'head':
            a, b = a[:8]+b'\0'*4+a[12:], b[:8]+b'\0'*4+b[12:]
        if a != b:
            raise ValueError('Font container conversion changed a source table')
    return decoded


class FontDrawCPU(SourcePhysics):
    TEXTURE_MAP = SourcePhysics.EXIT+0xa00

    def __init__(self, image, font):
        verify_native(image)
        self.allocations = {}; self.jumps = {}; self.tls = {}; self.next_tls = 1
        self.files = {}; self.buffers = {}; self.bindings = {}; self.materials = {}
        self.font = font
        super().__init__(image)
        from unicorn import UC_HOOK_CODE
        for at in (0x144c340, 0x14524a0, 0x5555bc, 0x13acad8, 0x13dc85c,
                   0x13dc9ec, 0x1450430, 0x1462ff8, 0x14509dc, self.TEXTURE_MAP):
            self.uc.hook_add(UC_HOOK_CODE, self.hook, begin=at, end=at)
        imports = {name: at for at, name in self.imports.items()}
        self.call(0x1a61848, {f'X{i}': imports[name] for i, name in
                             enumerate(('fopen', 'fclose', 'fread', 'fseek', 'ftell'))})
        self.driver = self.alloc(0x3000)
        world, context, holder = self.alloc(0x300), self.alloc(0x400), self.alloc(24)
        self.w(0x2528db0, 'Q', world); self.w(world+0x18, 'Q', context)
        self.w(context+0x20, 'Q', holder); self.w(holder+0x10, 'Q', self.driver)
        self.w(holder+8, 'I', 100)  # Explicit host resource lifetime/reference input.
        self.w(self.driver+0x300, 'Q', self.driver)
        self.owner = self.alloc(0x80000)
        self.call(0x3a9498, {'X0': self.owner}, limit=10000000)
        if not self.r(self.owner+0x4088, 'Q')[0]:
            raise ValueError('Original font face creation failed')

    def alloc(self, size):
        address = super().alloc(size)
        self.allocations[address] = size
        return address

    def resource(self, size=256):
        address, vt = self.alloc(size), self.alloc(256)
        self.w(address, 'Q', vt); self.w(address+8, 'I', 100)
        return address, vt

    def hook(self, uc, at, size, data):
        name = self.imports.get(at)
        if name in ('malloc', 'calloc'):
            length = self.get('X0')*(self.get('X1') if name == 'calloc' else 1)
            self.set('X0', self.alloc(length))
        elif name == 'realloc':
            old, length = self.get('X0'), self.get('X1'); new = self.alloc(length)
            if old:
                uc.mem_write(new, bytes(uc.mem_read(old, min(length, self.allocations[old]))))
            self.set('X0', new)
        elif name == 'free':
            pass  # No address reuse inside this bounded VM; source cleanup calls still run.
        elif name == 'setjmp':
            regs = [*[f'X{i}' for i in range(19, 31)], 'SP', *[f'D{i}' for i in range(8, 16)]]
            self.jumps[self.get('X0')] = {r: self.get(r) for r in regs}
            self.set('W0', 0)
        elif name == 'longjmp':
            env, value = self.get('X0'), self.get('W1')
            for r, v in self.jumps[env].items(): self.set(r, v)
            self.set('W0', value or 1); self.set('PC', self.get('X30')); return
        elif name == 'fopen':
            path, mode = self.cstr(self.get('X0')).decode(), self.cstr(self.get('X1')).decode()
            if mode not in ('r', 'rb'):
                raise ValueError('Font loader requested a write')
            if path != 'ui/Font/Alegreya-Bold.ttf':
                # No secondary/substitute font is supplied by this bounded renderer.
                if path != 'ui/Font/LeagueGothic-Regular.ttf':
                    raise ValueError('Unexpected original font path')
                self.set('X0', 0)
            else:
                handle = self.alloc(16); self.files[handle] = {'data': self.font, 'at': 0}
                self.set('X0', handle)
        elif name in ('fseek', 'fseeko'):
            f = self.files[self.get('X0')]; off = self.get('X1')
            if off >> 63: off -= 1 << 64
            f['at'] = (0, f['at'], len(f['data']))[self.get('W2')]+off
            if f['at'] < 0: raise ValueError('Invalid font seek')
            self.set('W0', 0)
        elif name in ('ftell', 'ftello'):
            self.set('X0', self.files[self.get('X0')]['at'])
        elif name == 'fread':
            out, unit, count, handle = [self.get(f'X{i}') for i in range(4)]
            f = self.files[handle]; raw = f['data'][f['at']:f['at']+unit*count]
            if raw: uc.mem_write(out, raw)
            f['at'] += len(raw); self.set('X0', len(raw)//unit if unit else 0)
        elif name == 'fclose':
            del self.files[self.get('X0')]; self.set('W0', 0)
        elif name == 'getenv':
            self.set('X0', 0)  # Explicit environment without FT debug/override variables.
        elif name in ('strcmp', 'strncmp', 'memcmp'):
            if name == 'strcmp':
                a, b = self.cstr(self.get('X0')), self.cstr(self.get('X1'))
            else:
                length = self.get('X2')
                a, b = [bytes(uc.mem_read(self.get(r), length)) for r in ('X0', 'X1')]
                if name == 'strncmp': a, b = a.split(b'\0')[0], b.split(b'\0')[0]
            self.set('W0', (1 if a > b else -1 if a < b else 0) & 0xffffffff)
        elif name == 'strstr':
            start = self.get('X0'); index = self.cstr(start).find(self.cstr(self.get('X1')))
            self.set('X0', start+index if index >= 0 else 0)
        elif name in ('wmemcpy', 'wmemmove'):
            uc.mem_write(self.get('X0'), bytes(uc.mem_read(self.get('X1'), self.get('X2')*4)))
        elif name == 'wcslen':
            start, count = self.get('X0'), 0
            while self.r(start+count*4, 'I')[0]:
                count += 1
                if count > 128: raise ValueError('Unbounded font wide string')
            self.set('X0', count)
        elif name == '__cxa_guard_acquire':
            self.set('W0', int(not self.r(self.get('X0'), 'B')[0]))
        elif name == '__cxa_guard_release': self.w(self.get('X0'), 'B', 1)
        elif name in ('__cxa_guard_abort', '__cxa_atexit'): self.set('W0', 0)
        elif name in ('pthread_self', 'gettid'): self.set('X0', 1)
        elif name == 'pthread_key_create':
            self.w(self.get('X0'), 'I', self.next_tls); self.next_tls += 1; self.set('W0', 0)
        elif name == 'pthread_getspecific': self.set('X0', self.tls.get(self.get('W0'), 0))
        elif name == 'pthread_setspecific':
            self.tls[self.get('W0')] = self.get('X1'); self.set('W0', 0)
        elif name in ('pthread_mutex_lock', 'pthread_mutex_unlock', 'pthread_mutex_init',
                      'pthread_mutex_destroy', 'pthread_mutexattr_init',
                      'pthread_mutexattr_destroy', 'pthread_mutexattr_settype'):
            self.set('W0', 0)  # Single-thread host ABI; no Android scheduling claim.
        elif at == 0x144c340:
            self.texture_size = self.r(self.get('X1'), '2I')
            texture, vt = self.resource(); self.w(vt+0x58, 'Q', self.TEXTURE_MAP)
            self.texture_pixels = self.alloc(self.texture_size[0]*self.texture_size[1])
            self.w(self.get('X8'), 'Q', texture)
        elif at == self.TEXTURE_MAP: self.set('X0', self.texture_pixels)
        elif at == 0x5555bc:
            kind = self.get('W1')
            if kind not in (0x1c, 0x1d): raise ValueError('Unexpected font material')
            material = self.alloc(64); self.w(material, 'I', 100)
            self.w(material+8, 'Q', self.alloc(64)); self.w(self.get('X8'), 'Q', material)
            self.materials[kind] = material
        elif at == 0x13acad8:
            self.set('W0', 0 if self.get('W1') == 2 else 0xffff)  # Host sampler semantic binding.
        elif at in (0x14524a0, 0x13dc85c, 0x13dc9ec):
            pass  # Graphics upload/binding sink; pixel/layout computations are untouched.
        elif at == 0x1450430:
            declaration = self.alloc(64); self.w(declaration, 'I', 100)
            self.w(self.get('X8'), 'Q', declaration)
        elif at == 0x1462ff8:
            description = list(self.r(self.get('X1'), '8I'))
            buffer, _ = self.resource()
            self.buffers[buffer] = {'description': description,
                                    'data': self.r(self.get('X1')+16, 'Q')[0]}
            self.w(self.get('X8'), 'Q', buffer)
        elif at == 0x14509dc:
            self.bindings[self.get('X0')] = self.r(self.get('X1'), 'Q')[0]
        else:
            return super().hook(uc, at, size, data)
        self.set('PC', self.get('X30'))

    def text(self, value):
        if not isinstance(value, str) or not 1 <= len(value) <= 24 or any(ord(c) < 32 for c in value):
            raise ValueError('Bounded nonempty character name required')
        root = self.alloc(0x8210); wide = self.alloc((len(value)+1)*4)
        self.uc.mem_write(wide, value.encode('utf-32-le')+b'\0'*4)
        color, extra = self.alloc(4), self.alloc(8)
        self.w(color, 'I', 0xfffed8a2)  # Original self relation == false branch, low-byte red.
        self.w(extra, 'Q', 0x2528d58)
        self.call(0x36a83c, {'X0': root, 'X1': self.owner, 'X2': wide, 'X3': color,
                            'X4': color, 'W5': 16, 'W6': 0, 'W7': 1}, {'S0': 0},
                  stack=(extra, 0), limit=20000000)
        geom = self.r(root+0x8168, 'Q')[0]
        declaration, index_buffer = self.r(geom+0x10, '2Q')
        count, vertices = self.r(geom+0x24, 'I')[0], self.r(geom+0x2c, 'I')[0]
        vertex_buffer = self.bindings[declaration]
        if not 0 < vertices <= len(value)*8 or count != vertices//4*6:
            raise ValueError('Original font geometry exceeds the bounded name')
        vertex_raw = bytes(self.uc.mem_read(self.buffers[vertex_buffer]['data'], vertices*24))
        index_raw = bytes(self.uc.mem_read(self.buffers[index_buffer]['data'], count*2))
        pixels = bytes(self.uc.mem_read(self.texture_pixels, self.texture_size[0]*self.texture_size[1]))
        if not any(pixels): raise ValueError('Original font produced no atlas pixels')
        # PNG is a lossless transport container for the original R8 alpha plane.
        from PIL import Image
        alpha = Image.frombytes('L', self.texture_size, pixels)
        rgba = Image.new('RGBA', self.texture_size, (255, 255, 255, 0)); rgba.putalpha(alpha)
        out = io.BytesIO(); rgba.save(out, format='PNG')
        return {'format': 'oc2-source-self-name-v1', 'vertexCount': vertices, 'indexCount': count,
                'vertices': base64.b64encode(vertex_raw).decode(), 'indices': base64.b64encode(index_raw).decode(),
                'atlas': 'data:image/png;base64,'+base64.b64encode(out.getvalue()).decode(),
                'width': self.texture_size[0], 'height': self.texture_size[1],
                'nativeGlyphCPU': True, 'hostGraphicsBuffers': True, 'originalGPUObserved': False}
