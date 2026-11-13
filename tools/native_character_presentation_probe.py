"""Execute original constructor, rebuild frontier, UI direction and cached offset.

The rebuild predicate is an explicit fixture; stop before formatting macros.
The light quaternion-to-matrix conversion and GL recording sink are interfaces.
No original GPU success, full actor state or font face is manufactured.
"""
from native_scene_palette import PaletteProbe
from character_presentation_evidence import verify_native


class PresentationProbe(PaletteProbe):
    def __init__(self, image):
        verify_native(image)
        super().__init__(image)
        from unicorn import UC_HOOK_CODE
        self.factory_flags_observed = []
        for at in (0x332630, 0x550db4, 0x9d4eb4):
            self.uc.hook_add(UC_HOOK_CODE, self.hook, begin=at, end=at)

    def hook(self, uc, at, size, data):
        if at == 0x332630:
            self.set('W0', 0)  # Explicit no-extra-rebuild predicate fixture.
            self.set('PC', self.get('X30'))
        elif at == 0x550db4:
            self.factory_flags_observed.append(self.get('W0'))
            self.set('PC', self.EXIT)  # Source flags ready; no macro/GPU creation claim.
        elif at == 0x9d4eb4:
            self.set('PC', self.EXIT)  # Original unpack/scaling block ended, before model lookup.
        else:
            return super().hook(uc, at, size, data)

    def new_model(self):
        model = self.alloc(0xe20)
        self.call(0x31f178, {'X0': model})
        return {'hair': list(self.r(model+0xdc0, '3f')),
                'skin': list(self.r(model+0xdcc, '3f')),
                'eye': list(self.r(model+0xdd8, '3f')),
                'materialUpdateAllowed': self.r(model+0x14, 'B')[0],
                'nativeCPU': True}

    def rebuild_factory(self):
        model = self.alloc(0xe20)
        self.call(0x31f178, {'X0': model})
        owner = self.alloc(0x88); self.w(owner, 'Q', model)
        self.w(owner+0x10, 'B', 1)
        self.factory_flags_observed = []
        self.call(0x332440, {'X0': owner})
        return {'flags': self.factory_flags_observed, 'predicateFixture': False,
                'nativeCPU': True, 'stoppedBeforeMacroFormatting': True}

    def ui_light(self):
        q, forward, target = self.alloc(16), self.alloc(12), self.alloc(12)
        self.w(forward, '3f', 0, 0, 1); self.w(target, '3f', -10, 10, 3.4)
        self.call(0x11dd004, {'X0': q, 'X1': forward, 'X2': target})
        x, y, z, w = self.r(q, '4f')
        matrix = [1-2*y*y-2*z*z, 2*x*y+2*z*w, 2*x*z-2*y*w, 0,
                  2*x*y-2*z*w, 1-2*x*x-2*z*z, 2*y*z+2*x*w, 0,
                  2*x*z+2*y*w, 2*y*z-2*x*w, 1-2*x*x-2*y*y, 0, 0, 0, 0, 1]
        device, world, box = self.alloc(0x3000), self.alloc(64), self.alloc(24)
        self.call(0x148cb40, {'X0': device+0x2070})
        self.w(world, '16f', 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
        self.call(0x1413868, {'X0': device, 'W1': 2, 'X2': world, 'X3': box, 'W4': 0})
        light, transform, declaration = self.alloc(256), self.alloc(64), self.alloc(24)
        self.w(transform, '16f', *matrix); self.w(light+0x60, 'Q', transform)
        self.w(light+0x70, 'H', 2); self.w(declaration+8, 'I', 7)
        self.w(declaration+16, 'H', 20 | (10 << 8)); self.gl = []
        self.call(0x1414888, {'X0': device, 'X1': light, 'X2': declaration})
        if len(self.gl) != 1 or self.gl[0]['name'] != 'glUniform3fv':
            raise ValueError('Original UI direction uploader differs')
        return {'uploadedObjectDirection': self.gl[0]['value'], 'nativeCPU': True,
                'hostQuaternionMatrix': True, 'identityModel': True, 'originalGPUObserved': False}

    def cached_name_offset(self, value):
        actor, output = self.alloc(0x600), self.alloc(12)
        self.w(actor+0x138, 'f', 1); self.w(actor+0x4c, 'B', 0)
        self.w(actor+0x590, '3f', *value)
        self.call(0x904fdc, {'X0': actor, 'X8': output})
        return list(self.r(output, '3f'))

    def packed_colors(self, hair, skin):
        table = self.alloc(0xb0)
        self.w(table+0xa0, 'I', hair); self.w(table+0x9c, 'I', skin)
        # Exact original block; not the full equipment/model constructor.
        self.call(0x9d4e4c, {'X20': table})
        return {'hair': list(self.r(self.STACK+0x18, '3f')),
                'skin': list(self.r(self.STACK+8, '3f'))}

    def font_geometry_units(self):
        return {'glyphUnitMultiplier': list(self.r(0x1df7aac, '2f')),
                'sourceNameFontSizeArgument': 16,
                'screenPixelSizeRecovered': False,
                'distanceSpacingIsNotProvenNameScale': True}
