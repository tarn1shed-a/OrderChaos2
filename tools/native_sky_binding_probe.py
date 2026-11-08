"""Full original preloaded-effect material binding with explicit zero properties.

Names/scalars are supplied through a synthetic pointer view. Interner and memory
imports are fixtures; original archive loading, FX assembly and GPU do not run.
"""
from native_sky_mesh_probe import NativeSkyMeshProbe
from scene_sky_binding import verify_native, validate_spec


class NativeSkyBindingProbe:
    BASE = NativeSkyMeshProbe.BASE

    def __init__(self, image):
        verify_native(image); self.p = NativeSkyMeshProbe(image)
        from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
        for at in [0x29e010, 0x11ddd2c, 0x3c0fbc, 0x29eaf0, 0x14006c4, 0x1400310]:
            self.p.uc.hook_add(UC_HOOK_CODE, self._hook, begin=at, end=at)
        self.p.uc.hook_add(UC_HOOK_MEM_WRITE, self._write, begin=self.BASE+0x5010, end=self.BASE+0x5010)

    def string(self, at):
        return bytes(self.p.uc.mem_read(at, 128)).split(b'\0')[0].decode()

    def _write(self, uc, access, at, size, value, data):
        if self.p.get('PC') == 0x11297c8:
            if size != 1: raise ValueError('BDAE selector write width changed')
            self.selector_writes.append(value)

    def _hook(self, uc, at, size, data):
        p, b = self.p, self.BASE
        if at == 0x14006c4:
            if p.get('X0') != b+0x6000 or p.get('W2') != 0: raise ValueError('Property lookup receiver/start changed')
            self.parameter_names.append(self.string(p.get('X1'))); return
        if at == 0x1400310:
            if p.get('X0') != b+0x6000: raise ValueError('Complete lookup effect receiver changed')
            self.technique_lookups += 1; return
        if at == 0x29e010:
            text = self.string(p.get('X0'))
            if text not in self.objects: raise ValueError('Unexpected material input strlen')
            p.set('X0', len(text.encode()))
        elif at == 0x11ddd2c:
            text = self.string(p.get('X1')); mode = p.get('W2')
            if text not in self.objects or mode not in (0, 1) or p.read(p.get('X0'), 'I')[0] != len(text.encode())+1:
                raise ValueError('Material interner arguments changed')
            pointer = self.objects[text]; refs = p.read(pointer+0x10, 'I')[0]
            p.write(pointer+0x10, 'I', refs+1); p.set('X0', pointer)
            self.intern_calls.append([text, mode])
        elif at == 0x3c0fbc:
            amount = 0x40+4*self.table_size
            if p.get('X0') != amount or p.get('W1') != 0x1000 or self.allocations:
                raise ValueError('Unexpected material allocation')
            self.allocations.append(amount); p.set('X0', b+0x5000)
        elif at == 0x29eaf0:
            if p.get('X0') != b+0x5040 or p.get('W1') != 0 or p.get('X2') != 4*self.table_size:
                raise ValueError('Unexpected material auxiliary memset')
            if self.table_size: uc.mem_write(b+0x5040, bytes(4*self.table_size))
        p.set('PC', p.get('X30'))

    def bind(self, spec, names, modifier_bits=0):
        validate_spec(spec, names, modifier_bits)
        p, b = self.p, self.BASE
        p.uc.mem_write(b, bytes(0x20000)); p.uc.mem_write(0x20000000, bytes(0x10000)); p.registers()
        self.parameter_names = []; self.technique_lookups = 0; self.intern_calls = []
        self.allocations = []; self.selector_writes = []; self.table_size = len(names)
        texts = list(dict.fromkeys([spec['name'], *names, *[s for prop in spec['properties']
                                 for s in (prop['name'], prop['techniqueName']) if s is not None]]))
        self.objects = {text: b+0x9000+128*i for i, text in enumerate(texts)}
        strings = {text: b+0x13000+128*i for i, text in enumerate(texts)}
        for text, pointer in self.objects.items():
            p.write(pointer+0x10, 'I', 1000); p.uc.mem_write(pointer+24, text.encode()+b'\0')
            p.uc.mem_write(strings[text], text.encode()+b'\0')
        p.write(b+0x3000, 'Q', b+0x6000); p.write(b+0x6000, 'I', 100)
        p.write(b+0x601c, '2B', modifier_bits, len(names)); p.write(b+0x6030, 'Q', b+0x7000)
        for i, name in enumerate(names): p.write(b+0x7000+24*i, 'Q', self.objects[name])
        p.uc.mem_write(b+0x5000, bytes([0xa5])*(0x40+4*len(names)))
        material, properties = b+0x10000, b+0x11000
        p.write(material, 'Q', strings[spec['name']]); p.write(material+0x40, 'I', spec['word40'])
        p.write(material+0x20, 'Ii', len(spec['properties']), properties-(material+0x24))
        for i, prop in enumerate(spec['properties']):
            at, value = properties+32*i, b+0x12000+32*i
            p.write(at, 'Q', strings[prop['name']]); p.write(at+16, 'I', prop['kind'])
            p.write(at+28, 'i', value-(at+28)); p.write(value, '2I', *prop['valueWords'])
            p.write(value+8, 'Q', strings[prop['techniqueName']] if prop['techniqueName'] is not None else 0)
        # Source factory slot+0x88, with a preloaded explicit effect reference.
        p.set('X8', b+0x1000); p.set('X1', b+0x2000); p.set('X3', b+0x3000)
        p.set('X4', material); p.set('X5', b+0x4000)
        p.uc.emu_start(0x1129190, b+0x1ff04, count=20000)
        if p.get('PC') != b+0x1ff00: raise ValueError('BDAE binding probe exceeded bounds')
        return {'selectorByte': p.read(b+0x5010, 'B')[0], 'variationByte': p.read(b+0x5018, 'B')[0],
                'selectorWrites': self.selector_writes, 'outputMaterial': p.read(b+0x1000, 'Q')[0],
                'materialReferences': p.read(b+0x5000, 'I')[0], 'effectReferences': p.read(b+0x6000, 'I')[0],
                'owner': p.read(b+0x5038, 'Q')[0], 'parameterLookups': self.parameter_names,
                'techniqueLookups': self.technique_lookups, 'internCalls': self.intern_calls,
                'allocationBytes': self.allocations,
                'internReferences': {name: p.read(pointer+0x10, 'I')[0] for name, pointer in self.objects.items()},
                'auxiliary': bytes(p.uc.mem_read(b+0x5040, 4*len(names)))}
