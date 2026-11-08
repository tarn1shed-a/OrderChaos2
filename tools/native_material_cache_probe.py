"""Isolated original cache writers/lookups; inputs/import bodies are fixtures."""
from native_sky_mesh_probe import NativeSkyMeshProbe
from scene_material_cache import verify_native, validate_table, word, apply_selector


class NativeMaterialCacheProbe:
    BASE = NativeSkyMeshProbe.BASE

    def __init__(self, image):
        verify_native(image); self.p = NativeSkyMeshProbe(image)
        from unicorn import UC_HOOK_CODE
        for at in [0x29e010, 0x11ddd2c, 0x13edca0, 0x13eafc0, 0x2a1e50, 0x29eaf0,
                   *[self.BASE+0x1f400+x for x in (0, 0x20, 0x40, 0x60)]]:
            self.p.uc.hook_add(UC_HOOK_CODE, self._hook, begin=at, end=at)

    def reset(self):
        self.p.uc.mem_write(self.BASE, bytes(0x20000)); self.p.uc.mem_write(0x20000000, bytes(0x10000))
        self.p.registers(); self.calls = []; self.feature_index = 0; self.sections = []

    def string(self, at):
        return bytes(self.p.uc.mem_read(at, 128)).split(b'\0')[0].decode() if at else None

    def _hook(self, uc, at, size, data):
        p, b = self.p, self.BASE
        if at == 0x2a1e50 or at == 0x29eaf0:
            size = p.get('X2')
            if not 0 <= size <= 128: raise ValueError('Copy/fill outside explicit auxiliary fixture')
            if size:
                value = bytes(uc.mem_read(p.get('X1'), size)) if at == 0x2a1e50 else bytes([p.get('W1') & 255])*size
                uc.mem_write(p.get('X0'), value)
            self.calls.append(['memcpy' if at == 0x2a1e50 else 'memset', size])
        elif at == 0x29e010:
            if p.get('X0') != b+0x9000: raise ValueError('Unexpected provider name strlen')
            p.set('X0', len(self.string(p.get('X0')))); self.calls.append(['strlen'])
        elif at == 0x11ddd2c:
            if (p.get('X1') != b+0x9000 or p.get('W2') != 0 or
                    p.read(p.get('X0'), 'I')[0] != len(self.string(b+0x9000))+1):
                raise ValueError('Intern callback arguments changed')
            p.set('X0', self.name_pointer); self.calls.append(['intern', self.name_pointer])
        elif at == 0x13edca0:
            if p.get('X0') != b+0x8000 or p.get('X1') != b+0x9100:
                raise ValueError('Group lookup receiver/name changed')
            p.set('W0', self.group_word); self.calls.append(['group', self.group_word])
        elif at == 0x13eafc0:
            if p.get('X0') != b or p.get('X1') != b+0x5000 or self.sections != ['Parameters']:
                raise ValueError('Parameters boundary changed')
            self.calls.append(['parameters'])
        else:
            if p.get('X0') != b+0x5000: raise ValueError('Provider receiver changed')
            slot = at-b-0x1f400
            if slot == 0:
                field = self.string(p.get('X1')); self.calls.append(['field', field])
                if field == 'Base Technique': p.set('X0', b+0x9000 if self.base_present else 0)
                elif field == 'Group': p.set('X0', b+0x9100)
                else: raise ValueError('Unknown provider field')
            elif slot == 0x20:
                section = self.string(p.get('X1')); self.sections.append(section); self.calls.append(['open', section])
            elif slot == 0x40:
                if not self.sections: raise ValueError('Unmatched provider section close')
                self.calls.append(['close', self.sections.pop()])
            elif slot == 0x60:
                if self.sections != ['Technique Modifiers'] or self.string(p.get('X1')) != 'feature'+str(self.feature_index):
                    raise ValueError('Modifier name/section changed')
                p.set('W0', self.features[self.feature_index]); self.feature_index += 1
            else: raise ValueError('Unexpected provider slot')
        p.set('PC', p.get('X30'))

    def run(self, target):
        self.p.uc.emu_start(target, self.BASE+0x1ff04, count=10000)
        if self.p.get('PC') != self.BASE+0x1ff00: raise ValueError('Material probe exceeded bounds')

    def table(self, names, bits):
        validate_table(names, bits); p, b = self.p, self.BASE
        p.write(b+8, 'Q', b+0x2000)
        p.write(b+0x201c, '2B', bits, len(names)*(1 << bits))
        p.write(b+0x2030, 'Q', b+0x3000)
        for i, pointer in enumerate(names): p.write(b+0x3000+24*(i << bits), 'Q', pointer)

    def lookup(self, names, bits, name_pointer, complete=False):
        validate_table(names, bits); word(name_pointer, 64)
        self.reset(); self.table(names, bits); p, b = self.p, self.BASE
        p.write(b+0x7000, 'Q', name_pointer)
        p.set('X0', b+0x2000); p.set('X1', b+0x7000)
        self.run(0x1400310 if complete else 0x140025c)
        return p.get('W0')

    def apply(self, base, variation, names, features, name_pointer, group_nonempty=False,
              group_word=0, base_present=True):
        apply_selector(base, variation, names, features, name_pointer, group_nonempty, group_word)
        if type(base_present) is not bool: raise ValueError('Expected explicit base field presence')
        if name_pointer and (not self.BASE+0xc000 <= name_pointer <= self.BASE+0x1d000 or name_pointer % 8):
            raise ValueError('Intern result must be in the explicit probe object arena')
        self.reset(); self.table(names, len(features)); p, b = self.p, self.BASE
        self.name_pointer, self.features, self.group_word, self.base_present = name_pointer, features, group_word, base_present
        # Even a missing lookup can return an interned object distinct from every table name.
        if name_pointer: p.write(name_pointer+0x10, 'I', 100)
        p.write(b+0x10, 'B', base); p.write(b+0x18, 'B', variation)
        p.write(b+0x5000, 'Q', b+0x6000)
        for slot, delta in [(0x208, 0), (0x70, 0x20), (0x88, 0x40), (0x1d8, 0x60)]:
            p.write(b+0x6000+slot, 'Q', b+0x1f400+delta)
        p.write(b+0x2008, 'Q', b+0x7800); p.write(b+0x7af8, 'Q', b+0x8000)
        p.write(b+0x2028, 'Q', b+0xa000)
        for i in range(len(features)):
            pointer = b+0xb000+128*i; p.write(b+0xa000+8*i, 'Q', pointer)
            p.uc.mem_write(pointer+24, ('feature'+str(i)).encode()+b'\0')
        p.uc.mem_write(b+0x9000, b'fixture-name\0')
        p.uc.mem_write(b+0x9100, b'fixture-group\0' if group_nonempty else b'\0')
        p.set('X0', b); p.set('X1', b+0x5000); self.run(0x13eda68)
        return {'baseByte': p.read(b+0x10, 'B')[0], 'variationByte': p.read(b+0x18, 'B')[0],
                'calls': self.calls, 'modifierCalls': self.feature_index,
                'internReferences': p.read(name_pointer+0x10, 'I')[0] if name_pointer else None}

    def construct(self, header, auxiliary=b'', copied=False):
        if not isinstance(header, bytes) or len(header) != 14 or not isinstance(auxiliary, bytes) or len(auxiliary) % 4 or len(auxiliary) > 128:
            raise ValueError('Expected explicit bounded constructor header/auxiliary data')
        if type(copied) is not bool: raise ValueError('Expected constructor source presence')
        self.reset(); p, b = self.p, self.BASE
        p.uc.mem_write(b, bytes([0xa5])*256); p.uc.mem_write(b+0x3000, header)
        p.write(b+0x4000, 'Q', b+0x2000); p.write(b+0x2000, 'I', 100)
        p.write(b+0x201d, 'B', len(auxiliary)//4)
        p.write(b+0x5020, 'Q', b+0x6000)
        if auxiliary: p.uc.mem_write(b+0x6000, auxiliary)
        p.set('X0', b); p.set('X1', b+0x4000); p.set('X3', b+0x3000)
        p.set('X6', b+0x5000 if copied else 0); self.run(0x13ecc24)
        return {'header': bytes(p.uc.mem_read(b+0x10, 14)), 'references': p.read(b, 'I')[0],
                'effectReferences': p.read(b+0x2000, 'I')[0], 'auxiliary': bytes(p.uc.mem_read(b+0x40, len(auxiliary))),
                'name': p.read(b+0x28, 'Q')[0], 'auxiliaryPointer': p.read(b+0x20, 'Q')[0]}

    def reset_cache(self, base, variation, shift):
        word(base, 8); word(variation, 8); word(shift, 8)
        self.reset(); p, b = self.p, self.BASE
        p.write(b+8, 'Q', b+0x2000); p.write(b+0x201c, 'B', shift)
        p.write(b+0x10, 'B', base); p.write(b+0x18, 'B', variation)
        p.set('X0', b); self.run(0x13ed094)
        return (p.read(b+0x10, 'B')[0], p.read(b+0x18, 'B')[0], p.read(b+0x1a, 'I')[0])

    def copy_cache(self, source_bytes, destination_bytes, same_effect=True, same_object=False, auxiliary=b''):
        if len(source_bytes) != 2 or len(destination_bytes) != 2 or type(same_effect) is not bool or type(same_object) is not bool:
            raise ValueError('Expected explicit cache copy inputs')
        for value in (*source_bytes, *destination_bytes): word(value, 8)
        if not isinstance(auxiliary, bytes) or len(auxiliary) % 4 or len(auxiliary) > 128:
            raise ValueError('Expected bounded auxiliary words')
        self.reset(); p, b = self.p, self.BASE
        source = b if same_object else b+0x4000
        p.write(b+8, 'Q', b+0x2000)
        if not same_object: p.write(source+8, 'Q', b+0x2000 if same_effect else b+0x2100)
        p.write(b+0x201d, 'B', len(auxiliary)//4)
        p.write(b+0x10, 'B', destination_bytes[0]); p.write(b+0x18, 'B', destination_bytes[1])
        if not same_object:
            p.write(source+0x10, 'B', source_bytes[0]); p.write(source+0x18, 'B', source_bytes[1])
        p.write(b+0x20, 'Q', b+0x6000)
        if not same_object: p.write(source+0x20, 'Q', b+0x7000)
        if auxiliary: p.uc.mem_write(b+0x7000, auxiliary)
        p.write(b+0x8000, 'Q', source); p.set('X0', b); p.set('X1', b+0x8000)
        self.run(0x13ed1fc)
        return {'returnWord': p.get('W0'), 'baseByte': p.read(b+0x10, 'B')[0],
                'variationByte': p.read(b+0x18, 'B')[0], 'dirtyWord': p.read(b+0x1a, 'H')[0],
                'auxiliary': bytes(p.uc.mem_read(b+0x6000, len(auxiliary)))}
