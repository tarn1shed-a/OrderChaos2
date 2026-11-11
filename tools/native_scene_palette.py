"""Original missing-attribute defaults, camera light and character RGB outputs.

Explicit renderer/material metadata and GL recording sinks are interfaces, not
an original Android device, compiled program or complete frame.
"""
from source_physics import SourcePhysics


class PaletteProbe(SourcePhysics):
    def __init__(self, image):
        self.gl, self.names = [], []
        self.blend_lookup, self.blend_writes = [], []
        super().__init__(image)
        from unicorn import UC_HOOK_CODE
        for address in (0x13bc2ec, 0x13bde64, 0x14006c4, 0x13dc360):
            self.uc.hook_add(UC_HOOK_CODE, self.hook, begin=address, end=address)

    def hook(self, uc, address, size, data):
        if address == 0x14006c4:
            name = self.cstr(self.get('X1')).decode()
            if name != 'blend_color' or self.get('W2') != 0:
                raise ValueError('Unexpected original blend lookup')
            self.blend_lookup.append(name)
            self.set('W0', self.blend_index)  # Explicit reflected-name lookup fixture.
        elif address == 0x13dc360:
            self.blend_writes.append({'index': self.get('W1'), 'element': self.get('W2'),
                                      'value': list(self.r(self.get('X3'), '4f'))})
        elif address == 0x13bc2ec:
            self.names.append(self.cstr(self.get('X1')).decode())
            self.set('W0', 0xffff)  # No invented global material declaration table.
        elif address == 0x13bde64:
            raise ValueError('Unexpected global declaration write in no-table experiment')
        elif self.imports.get(address, '').startswith('gl'):
            name = self.imports[address]
            row = {'name': name, 'location': self.get('W0')}
            if name == 'glVertexAttrib4f':
                row['value'] = [self.gf('S'+str(i)) for i in range(4)]
            elif name == 'glUniform3fv':
                row['value'] = list(self.r(self.get('X2'), '3f'))
            else:
                row['args'] = [self.get('W'+str(i)) for i in range(3)]
            self.gl.append(row)
        else:
            return super().hook(uc, address, size, data)
        self.set('PC', self.get('X30'))

    def missing_attributes(self):
        device, program, attributes = self.alloc(0x3000), self.alloc(256), self.alloc(48)
        mapping, descriptor = self.alloc(256), self.alloc(256)
        self.uc.mem_write(mapping, bytes([255])*256)
        self.w(program+0xdc, 'B', 2)
        self.w(program+0x20, 'Q', attributes)
        for i, semantic in enumerate((18, 22)):
            self.w(attributes+i*24+8, 'Q', semantic | (3 << 16) | ((i+5) << 32))
        self.gl = []
        self.call(0x14118f8, {'X0': device, 'X1': program, 'X2': descriptor, 'X3': mapping})
        expected = [[1., 0., 0., 1.], [0., 1., 0., 1.]]
        if [r.get('value') for r in self.gl] != expected:
            raise ValueError('Original missing tangent/binormal defaults differ')
        return {'nativeCPU': True, 'genericBufferFallback': False, 'calls': self.gl,
                'tangentSemantic': 18, 'binormalSemantic': 22, 'originalGPUObserved': False}

    def default_light(self, world_matrix=None):
        # Exact vectors and quaternion initialization from329700, not a new sun.
        quaternion, forward, direction = self.alloc(16), self.alloc(12), self.alloc(12)
        self.uc.mem_write(quaternion, self.image.read(0x1df76f0, 16))
        self.w(forward, '3f', 0, 0, 1)
        self.w(direction, '3f', -1, 1, -1)
        self.call(0x11dd004, {'X0': quaternion, 'X1': forward, 'X2': direction})
        x, y, z, w = q = list(self.r(quaternion, '4f'))
        # Standard quaternion->matrix graphics interface, separately passed to
        # the real original object-space light uploader below.
        matrix = [1-2*y*y-2*z*z, 2*x*y+2*z*w, 2*x*z-2*y*w, 0,
                  2*x*y-2*z*w, 1-2*x*x-2*z*z, 2*y*z+2*x*w, 0,
                  2*x*z+2*y*w, 2*y*z-2*x*w, 1-2*x*x-2*y*y, 0, 0, 0, 0, 1]
        device, world, box = self.alloc(0x3000), self.alloc(64), self.alloc(24)
        self.call(0x148cb40, {'X0': device+0x2070})
        self.w(world, '16f', *(world_matrix or [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]))
        self.call(0x1413868, {'X0': device, 'W1': 2, 'X2': world, 'X3': box, 'W4': 0})
        light, transform, declaration = self.alloc(256), self.alloc(64), self.alloc(24)
        self.w(transform, '16f', *matrix)
        self.w(light+0x60, 'Q', transform)
        self.w(light+0x70, 'H', 2)
        self.w(declaration+8, 'I', 7)
        self.w(declaration+16, 'H', 20 | (10 << 8))
        self.gl = []
        self.call(0x1414888, {'X0': device, 'X1': light, 'X2': declaration})
        if len(self.gl) != 1 or self.gl[0]['name'] != 'glUniform3fv':
            raise ValueError('Original default light upload differs')
        return {'nativeCPU': True, 'sourceForward': [0, 0, 1], 'sourceDirection': [-1, 1, -1],
                'quaternion': q, 'uploadedObjectDirection': self.gl[0]['value'], 'identityModel': world_matrix is None, 'sourceLightType': 2,
                'hostQuaternionMatrix': True, 'laterOverridesObserved': False}

    def colors(self, ambient, diffuse, intensities):
        a, d, owner = self.alloc(12), self.alloc(12), self.alloc(0x400)
        self.w(a, '3f', *ambient)
        self.w(d, '3f', *diffuse)
        for address, value in zip((0x25092e8, 0x25092ec, 0x25092f0), intensities):
            self.w(address, 'f', value)
        self.names = []
        self.call(0x34d228, {'X0': owner, 'X1': a, 'X2': d})
        if not {'light_ambient_char', 'light_diffuse_char', 'light_specular_char'} <= set(self.names):
            raise ValueError('Original character palette global names differ')
        return {name: list(self.r(address, '3f')) for name, address in
                [('ambient', 0x2527864), ('diffuse', 0x2527870), ('specular', 0x252787c)]}

    def factory_flags(self, level):
        from unicorn import UC_HOOK_CODE
        seen = []
        def boundary(uc, address, size, data):
            seen.append(self.get('W0'))
            uc.emu_stop()
        hook = self.uc.hook_add(UC_HOOK_CODE, boundary, begin=0x550db4, end=0x550db4)
        try:
            # Intentionally stop before the macro text formatter, with the
            # original constructor's flags already produced.
            for i in range(31):self.set('X'+str(i), 0)
            self.set('SP', self.STACK)
            self.set('X30', self.EXIT)
            self.set('X0', self.alloc(64))
            self.uc.emu_start(0x550f08, self.EXIT, count=1000)
        finally:
            self.uc.hook_del(hook)
        if seen != [0x807]:
            raise ValueError('Original fresh project loader flags differ')
        obj, custom, config = self.alloc(256), self.alloc(256), self.alloc(256)
        self.w(obj+0xb0, 'Q', custom)
        self.w(config+0x50, 'I', level)
        self.w(0x2528220, 'Q', config)
        self.call(0x333940, {'X0': obj})
        quality = self.r(custom+0xc, 'I')[0]
        if level != 2 or quality != 0:
            raise ValueError('Only the original APK high shader default is supported')
        return {'nativeCPU': True, 'loaderFlags': seen[0], 'ShadersLevel': level,
                'qualityFlags': quality, 'textFormatterExecuted': False, 'actualDeviceObserved': False}

    def default_blend(self, present=True, gate=True):
        """Execute the original default setter, with explicit name lookup/sink.

        The same vec4(1) write is present after creation in550fec. No effect
        creation, reflected declaration or GPU success is manufactured here.
        """
        holder, material = self.alloc(8), self.alloc(64)
        self.w(holder, 'Q', material)
        self.w(material+8, 'Q', self.alloc(32))
        self.w(0x250aee4, 'B', int(gate))
        self.blend_index = 3 if present else 0xffff
        self.blend_lookup, self.blend_writes = [], []
        self.call(0x550f70, {'X0': holder})
        return {'lookup': self.blend_lookup, 'writes': self.blend_writes,
                'reflectedLookupFixture': True, 'materialCreationExecuted': False,
                'nativeCPU': True, 'originalGPUObserved': False}
