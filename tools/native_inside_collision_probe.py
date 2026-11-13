"""Execute the original inside-PHY filename/chain selection in isolation.

Archive presence, libc and resource handles are explicit host interfaces. Each
non-null handle comes from the original PHY reader, never generated geometry.
"""
import hashlib
from source_physics import SourcePhysics


ROUTINES = {
    0xa61030: (1328, 'c3a0db7d786cc1a7e47f206e1bff0cefa2cf138eed2ba6d68b2ee8abd49092ad'),
    0xa85cb0: (1524, '4a1b7474e845b7056ca51f16f85f52f11faeb782fbf55a9b68486aaf66f85b98'),
    0xa862a4: (960, '5b5952cf56e0772418879bb814685639e8c18a1360286dbb9e8a9f2ce793b1da'),
}


class InsidePhysicsProbe(SourcePhysics):
    EXISTS = SourcePhysics.EXIT + 0x800

    def __init__(self, image):
        from unicorn import UC_HOOK_CODE
        for address, (size, sha) in ROUTINES.items():
            if hashlib.sha256(image.read(address, size)).hexdigest() != sha:
                raise ValueError('Original inside collision routine differs')
        super().__init__(image)
        self.uc.hook_add(UC_HOOK_CODE, self.hook, begin=0xa862a4, end=0xa862a4)
        self.uc.hook_add(UC_HOOK_CODE, self.hook, begin=self.EXISTS, end=self.EXISTS)
        self.reads = []; self.probes = []; self.handles = {}; self.present = set()
        provider = self.alloc(0x80); vtable = self.alloc(0x40)
        self.w(provider, 'Q', vtable); self.w(vtable + 0x18, 'Q', self.EXISTS)
        for address in range(0x25451f8, 0x2545221, 8):
            self.w(address, 'Q', provider if address == 0x25451f8 else 0)

    def hook(self, uc, address, size, data):
        if address == 0xa862a4:
            name = self.cstr(self.get('X0')).decode()
            self.reads.append(name); self.set('X0', self.handles.get(name, 0))
        elif address == self.EXISTS:
            name = self.cstr(self.get('X1')).decode()
            self.probes.append(name); self.set('X0', int(name in self.present))
        elif address in self.imports and self.imports[address] == 'strcpy':
            uc.mem_write(self.get('X0'), self.cstr(self.get('X1')) + b'\0')
        elif address in self.imports and self.imports[address] == 'strrchr':
            pointer = self.get('X0'); raw = self.cstr(pointer)
            char = self.get('W1') & 255
            at = len(raw) if char == 0 else raw.rfind(bytes([char]))
            self.set('X0', pointer + at if at >= 0 else 0)
        else:
            return super().hook(uc, address, size, data)
        self.set('PC', self.get('X30'))

    def select(self, model, sources, simplified=False, inside=True):
        """Current four source models only; reject unexamined extra files."""
        if not model.endswith('.bdae'):
            raise ValueError('Expected original model path')
        stem = model.rsplit('.', 1)[0]
        if stem.endswith('_h'):
            stem = stem[:-2]
        normal = stem + '.phy'
        extras = [stem + suffix for suffix in ('_s.phy', '_inside.phy', '_inside_s.phy')]
        if any(sources.candidates(name) for name in extras):
            raise ValueError('Additional PHY exists; chain merge needs separate verification')
        raw = sources.read(normal)
        head = self.read_phy(raw, normal)
        original_links = self.links(head)
        self.handles = {normal: head}; self.present = {normal}
        self.reads = []; self.probes = []
        # Pointer is relocated by the base ELF loader. No guessed global address.
        quality = self.r(0x2507368, 'Q')[0]
        self.w(quality, 'B', int(simplified))
        name = self.alloc(len(model.encode()) + 1)
        self.uc.mem_write(name, model.encode() + b'\0')
        output = self.alloc(8)
        result = self.call(0xa85cb0, {'X0': name, 'X1': output, 'W2': int(inside)})
        selected = self.r(output, 'Q')[0]
        if selected != head or self.links(selected) != original_links:
            raise ValueError('Original inside selection changed the supplied normal chain')
        return {'head': selected, 'selected': normal,
                'sourceSHA256': hashlib.sha256(raw).hexdigest(),
                'readRequests': list(self.reads), 'presenceProbes': list(self.probes),
                'shapeCount': len(original_links), 'normalChainUnchanged': True,
                'originalReturn': result & 255, 'insideInput': bool(inside),
                'simplifiedInput': bool(simplified),
                'scope': 'original filename/fallback/inside branch; host archive-presence and parsed-resource handles'}

    def links(self, head):
        result = []
        while head:
            if head in result or len(result) >= 4096:
                raise ValueError('Invalid original PHY list')
            result.append(head); head = self.r(head + 8, 'Q')[0]
        return result
