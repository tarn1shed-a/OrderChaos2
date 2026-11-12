"""Execute source light setters, frame prefix and complete RGB producer.

Reflection name/index and uniform submission are recording interfaces. No
Android GPU, actual material cache or weather history is claimed.
"""
from native_scene_palette import PaletteProbe
from scene_lighting import verify_native, DEFAULTS


class TempleAmbientProbe(PaletteProbe):
    def __init__(self, image):
        verify_native(image)
        self.indices, self.submissions = {}, {}
        super().__init__(image)

    def hook(self, uc, address, size, data):
        if address == 0x13bc2ec:
            name = self.cstr(self.get('X1')).decode()
            index = self.indices.setdefault(name, len(self.indices))
            self.set('W0', index)
        elif address == 0x13bde64:
            name = next(k for k,v in self.indices.items() if v == self.get('W1'))
            if self.get('W2') != 0: raise ValueError('Unexpected source global element')
            self.submissions[name] = list(self.r(self.get('X3'), '3f'))
        else:
            return super().hook(uc, address, size, data)
        self.set('PC', self.get('X30'))

    def produce(self, ambient_packed, diffuse_packed, intensities, adds=(0., 0.)):
        from unicorn import UC_HOOK_CODE
        renderer, root, owner = self.alloc(0x400), self.alloc(0x400), self.alloc(0x400)
        wrapper, light, colors = self.alloc(0x80), self.alloc(0x80), self.alloc(0x40)
        self.w(renderer+0x18, 'Q', root); self.w(root+0x38, 'Q', owner)
        self.w(renderer+0x30, 'Q', wrapper); self.w(wrapper+0x38, 'Q', light)
        self.w(light+0x20, 'Q', colors)
        self.call(0x329c40, {'X0':light,'W1':ambient_packed})
        self.call(0x329bf0, {'X0':light,'W1':diffuse_packed})
        self.w(renderer+0xa0, '2f', *adds)
        for index, key in enumerate([*DEFAULTS, 'model_intensity_lightMap']):
            self.w(0x25092e8+index*4, 'f', intensities[key])
        self.indices, self.submissions = {}, {}
        def stop(uc, at, size, data): self.set('PC', self.EXIT)
        h = self.uc.hook_add(UC_HOOK_CODE, stop, begin=0x34e5f8, end=0x34e5f8)
        try: self.call(0x34e53c, {'X0':renderer})
        finally: self.uc.hook_del(h)
        expected = {'light_common','light_lightMap','light_model_lightMap'}
        if not expected <= self.submissions.keys(): raise ValueError('Source RGB submissions missing')
        return {'packedAmbient':ambient_packed,'packedDiffuse':diffuse_packed,
                'ambient':list(self.r(colors+4,'3f')),'diffuse':list(self.r(colors+0x14,'3f')),
                'adds':list(adds),'submitted':dict(self.submissions),
                'sourceCPU':True,'originalGPUObserved':False,
                'interfaces':['explicit reflected indices','uniform submission recording','explicit current scalar intensities and weather additions']}
