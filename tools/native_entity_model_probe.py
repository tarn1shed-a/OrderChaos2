"""Bounded original EntityConfig reader, binding and fresh filename branches.

XML tokenization/file I/O, standard storage, element casts and existence queries
are adapters. Original DOM traversal, integer getter, field reader, model/ID
lookup, cullmode choice and filename branches execute pinned ARM64 instructions.
Execution ends before model task allocation; no assets or game are rendered.
"""
import xml.etree.ElementTree as ET

from native_device_selection_probe import NativeDeviceSelectionProbe
from unicorn import UC_HOOK_CODE


class NativeEntityModelProbe(NativeDeviceSelectionProbe):
    CONFIG = 0x1000d000

    def __init__(self, image):
        from entity_model_evidence import verify_native
        verify_native(image)
        super().__init__(image)
        for at, size in [(0x4c9000, 0x2000), (0x33e000, 0x2000),
                         (0x1aaa000, 0x3000), (0x8fb000, 0x1000), (0x1ab2000, 0x1000)]:
            self.uc.mem_map(at, size)
            self.uc.mem_write(at, image.read(at, size))
        for page in [0x1e66000, 0x1e33000, 0x1df7000, 0x1e05000, 0x1fa9000,
                     0x1fb0000, 0x1ffc000, 0x1fd2000, 0x1dfc000, 0x1e02000, 0x1df8000]:
            self.uc.mem_map(page, 0x1000)
            self.uc.mem_write(page, image.read(page, 0x1000))
        self.uc.mem_map(0x2527000, 0x1000)
        self.stream, self.vtable = self.BASE+0xb000, self.BASE+0xb100
        self.w(self.stream, 'Q', self.vtable)
        for slot, callback in [(0x30, 0x30000200), (0x18, 0x30000204), (8, 0x30000208)]:
            self.w(self.vtable+slot, 'Q', callback)
        self.element_vtable = self.BASE+0xb200
        for slot in (0x28, 0x58):
            self.w(self.element_vtable+slot, 'Q', 0x3000020c)
        self.w(0x2505c38, 'Q', self.BASE+0xb300)
        self.w(self.BASE+0xb300, 'Q', 0xcafe)
        for at in [0x8fb9f8, 0x1aac48c, 0x1ab2e88, 0x1aac8b4, 0x29f220,
                   0x2a1d30, 0x2a1250, 0x30000200, 0x30000204, 0x30000208,
                   0x3000020c, 0x30000210]:
            self.uc.hook_add(UC_HOOK_CODE, self.entity_hook, begin=at, end=at)
        self.loaded = False

    def rawstr(self, value):
        raw = value.encode()
        at = self.alloc(16+len(raw)+1)
        self.uc.mem_write(at+16, raw+b'\0')
        return at

    def dom(self, element):
        """Explicit parsed DOM layout, not an execution of original XML parsing."""
        node = self.alloc(160)
        self.w(node, 'Q', self.element_vtable)
        self.w(node+0x38, 'Q', self.rawstr(element.tag))
        head, previous = node+0x50, None
        for key, value in element.attrib.items():
            attr = self.alloc(64)
            self.w(attr+0x20, '2Q', self.rawstr(key), self.rawstr(value))
            self.w(node+0x88 if previous is None else previous+0x38, 'Q', attr)
            previous = attr
        self.w(node+0x88 if previous is None else previous+0x38, 'Q', head)
        previous = None
        for child in element:
            at = self.dom(child)
            self.w(node+0x28 if previous is None else previous+0x48, 'Q', at)
            previous = at
        return node

    def entity_hook(self, uc, at, size, data):
        if at == 0x8fb9f8:
            self.set('X0', self.stream)
        elif at == 0x30000200:
            self.set('X0', len(self.xml))
        elif at == 0x30000204:
            if self.get('W2') != len(self.xml):
                raise ValueError('Uncovered file read size')
            uc.mem_write(self.get('X1'), self.xml)
        elif at in (0x30000208, 0x3000020c, 0x29f220, 0x1aac8b4):
            pass  # release, element self-cast, delete and DOM destruction boundaries
        elif at == 0x1aac48c:
            doc = self.get('X0')
            uc.mem_write(doc, bytes(0x60))
            self.w(doc+0x28, 'Q', self.dom_root)
        elif at == 0x1ab2e88:
            if self.c(self.get('X1')) != self.xml:
                raise ValueError('XML source buffer differs')
        elif at == 0x2a1d30:
            fmt = self.c(self.get('X1'))
            if fmt not in (b'%s.bdae', b'%s_l.bdae'):
                raise ValueError('Uncovered filename format')
            value = fmt.replace(b'%s', self.c(self.get('X2')))
            uc.mem_write(self.get('X0'), value+b'\0')
            self.set('W0', len(value))
        elif at == 0x2a1250:
            vector = self.get('X0')
            begin, end, capacity = self.r(vector, '3Q')
            if begin or end or capacity:
                raise ValueError('Only the fresh filename vector allocation is adapted')
            begin = self.alloc(32)
            self.w(begin, 'Q', self.r(self.get('X1'), 'Q')[0])
            self.w(vector, '3Q', begin, begin+8, begin+32)
        elif at == 0x30000210:
            name = self.c(self.get('X1')).decode()
            self.exists_queries.append(name)
            self.set('W0', int(self.exists(name)))
        else:
            raise ValueError(hex(at))
        self.set('PC', self.get('X30'))

    def load(self, raw):
        if self.loaded:
            raise ValueError('Only a fresh EntityConfig is in this experiment scope')
        if not isinstance(raw, bytes) or len(raw) > 32768 or b'\0' in raw:
            raise ValueError('Bounded, NUL-free XML input required')
        root = ET.fromstring(raw)
        if root.tag != 'Entity':
            raise ValueError('This experiment requires the original Entity root')
        self.xml, self.dom_root = raw, self.dom(root)
        self.registers()
        self.set('X0', self.CONFIG)
        self.run_checked(0x4c92d4)
        self.registers()
        self.set('X0', self.CONFIG)
        self.set('X1', self.s('world/tutorial/EntityConfig.xml'))
        self.mode = 'entity'
        self.run_checked(0x4c975c)
        self.loaded = True
        return self.models()

    def models(self):
        result, head = [], self.CONFIG
        node = self.r(head, 'Q')[0]
        while node != head:
            if len(result) > 100:
                raise ValueError('Unbounded model list')
            at = self.r(node+0x10, 'Q')[0]
            distance, lod, device = self.r(at+8, '3i')
            item = {'model': self.hstr(at).decode(), 'distanceInt': distance,
                    'lod': lod, 'device': device, 'instances': []}
            instance_head = at+0x18
            inode = self.r(instance_head, 'Q')[0]
            while inode != instance_head:
                if len(item['instances']) > 100:
                    raise ValueError('Unbounded instance list')
                pointer = self.r(inode+0x10, 'Q')[0]
                values = self.r(pointer, '6i')
                item['instances'].append(dict(zip(
                    ['id', 'phase', 'distanceInt', 'lod', 'device', 'mode'], values)))
                inode = self.r(inode, 'Q')[0]
            result.append(item)
            node = self.r(node, 'Q')[0]
        return result

    def bind(self, model, ident, initial=-1):
        if not self.loaded or not 0 <= ident <= 0xffffffff:
            raise ValueError('Loaded config and explicit u32 ID required')
        self.registers()
        self.mode = 'bind'
        self.w(self.BASE+0x4000+0x1b0, 'Q', self.CONFIG)
        obj, params = self.BASE+0xe000, self.BASE+0xe400
        self.w(params, 'Q', self.s(model))
        self.w(params+0x9c, 'I', ident)
        self.w(obj+0x168, 'f', initial)
        self.set('X19', obj)
        self.set('X21', params)
        if self.run(0x33ec1c, 0x33ecac) != 0x33ecac:
            raise ValueError('Binding exceeded scope')
        return self.r(obj+0x168, 'f')[0]

    def initial(self, config, incoming):
        if type(config) is not int or config not in (0, 1, 2) or incoming not in (0, 1):
            raise ValueError('Explicit supported config and incoming slot required')
        self.registers()
        self.w(self.BASE+0x3000+0x28, 'I', config)
        self.set('X22', 0x2528000)
        self.set('W20', incoming)
        if self.run(0x33edbc, 0x33eddc) != 0x33eddc:
            raise ValueError('Initial request exceeded scope')
        return {'requestedSlot': self.get('W1'), 'forceSingleSlot': bool(self.get('W2'))}

    def static_initial(self, config):
        """a6196c's static-record caller argument, then 33ebf8's config choice."""
        if type(config) is not int or config not in (0, 1, 2):
            raise ValueError('Explicit supported config required')
        self.registers()
        self.w(self.BASE+0x3000+0x28, 'I', config)
        holder, vtable = self.BASE+0xf300, self.BASE+0xf400
        self.w(holder, 'Q', vtable)
        self.w(vtable+0xb0, 'Q', 0xa63218)
        self.w(self.get('SP')+8, 'Q', holder)
        if self.run(0xa61e7c, 0xa61eb4) != 0xa61eb4 or self.get('X8') != 0xa63218:
            raise ValueError('Static factory argument exceeded scope')
        incoming = self.get('W2')
        return {'incomingSlot': incoming} | self.initial(config, incoming)

    def fresh(self, model, slot, force, exists):
        """Return one task's candidate list; the worker chooses a candidate."""
        from scene_lightmap_binding import fresh_model_requests
        fresh_model_requests(model, slot, force, False)  # validate scope, discard oracle result
        self.registers()
        self.mode, self.exists, self.exists_queries = 'fresh', exists, []
        obj = self.BASE+0xe000
        self.uc.mem_write(obj, bytes(0x200))
        self.w(obj+0x60, 'Q', self.s(model[:-5]))
        self.set('X0', obj)
        self.set('W1', slot)
        self.set('W2', int(force))
        engine, fs, vtable = self.BASE+0xf000, self.BASE+0xf100, self.BASE+0xf200
        self.w(0x25276f8, 'Q', engine)
        self.w(engine+0x50, 'Q', fs)
        self.w(fs, 'Q', vtable)
        self.w(vtable+0xd8, 'Q', 0x30000210)
        if self.run(0x33f2fc, 0x33f5d0) != 0x33f5d0:
            raise ValueError('Fresh filename request exceeded scope')
        begin, end, capacity = self.r(self.get('SP')+0x18, '3Q')
        count = (end-begin)//8
        if count not in (1, 2) or not begin <= end <= capacity:
            raise ValueError('Uncovered filename vector state')
        return {'requests': [{'slot': self.r(obj+0xac+i, 'B')[0],
                              'path': self.hstr(begin+i*8).decode()} for i in range(count)],
                'existsQueries': list(self.exists_queries)}
