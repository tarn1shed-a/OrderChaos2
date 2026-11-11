"""Bounded original empty-record handling and fresh texture archive ordering.

Filesystem presence, stream/archive handles, name-cache miss, C++ strings and
locks are explicit interfaces. No Android VFS, texture or GPU success is claimed.
"""
from source_physics import SourcePhysics


class MissingRecordProbe(SourcePhysics):
    EXISTS, OPEN = 0x30000800, 0x30000810

    def __init__(self, image):
        self.stage, self.trace, self.archives = None, [], {}
        super().__init__(image)
        from unicorn import UC_HOOK_CODE
        for a in (self.EXISTS, self.OPEN, 0x1de639c, 0x1de8b74, 0x5565f0,
                  0x5565b0, 0x1502a54, 0x1502c20, 0x54bf70):
            self.uc.hook_add(UC_HOOK_CODE, self.hook, begin=a, end=a)

    def string(self, dest, raw):
        p = self.alloc(len(raw)+25)
        self.w(p, 'QQi', len(raw), len(raw), 0)
        self.uc.mem_write(p+24, raw+b'\0')
        self.w(dest, 'Q', p+24)

    def archive(self, p, name):
        if name not in self.available:
            raise ValueError('Archive handle requested without local input')
        table = self.alloc(64)
        self.w(table+0x18, 'Q', self.OPEN)
        self.w(p, 'Q', table)
        self.w(p+8, 'I', 100)  # Explicit retained handle; no destructor claim.
        self.archives[p] = name

    def hook(self, uc, at, size, data):
        if at == self.EXISTS:
            name = self.cstr(self.get('X1')).decode()
            self.trace.append({'kind': 'presence', 'name': name, 'present': name in self.available})
            self.set('W0', int(name in self.available))
        elif at == self.OPEN:
            name = self.cstr(self.get('X1')).decode()
            if self.stage == 'mount':
                if name != 'res_t.bin':
                    raise ValueError('Unexpected original base stream request')
                marker = self.alloc(64); self.w(marker+8, 'I', 100)
            else:
                archive = self.archives[self.get('X0')]
                self.trace.append({'kind': 'archiveLookup', 'pack': archive, 'name': name})
                marker = self.alloc(64) if archive in self.containing else 0
            self.w(self.get('X8'), 'Q', marker)  # Stream interface, not a real decoder.
        elif at == 0x1de639c:
            self.string(self.get('X0'), self.cstr(self.get('X1')))
        elif at == 0x1de8b74:
            dest = self.get('X0')
            self.string(dest, self.cstr(self.get('X2'))[:self.get('X3')]+self.cstr(self.r(dest, 'Q')[0]))
            self.set('X0', dest)
        elif at in (0x5565f0, 0x5565b0):
            name = 'res_t.bin' if at == 0x5565f0 else self.cstr(self.get('X1')).decode()
            self.archive(self.get('X0'), name)
        elif at == 0x54bf70:
            self.w(self.get('X8'), 'Q', 0)  # Explicit cold name cache only.
        elif at in (0x1502a54, 0x1502c20):
            pass
        elif self.imports.get(at) == 'sprintf':
            if self.cstr(self.get('X1')) != b'res_t_upd%d.bin':
                raise ValueError('Uncovered mount formatter')
            raw = ('res_t_upd%d.bin' % self.get('W2')).encode()
            uc.mem_write(self.get('X0'), raw+b'\0'); self.set('W0', len(raw))
        else:
            return super().hook(uc, at, size, data)
        self.set('PC', self.get('X30'))

    def fresh_archives(self, available, containing):
        self.available, self.containing = set(available), set(containing)
        self.archives, self.trace, self.stage = {}, [], 'mount'
        owner, context, fs, table = self.alloc(256), self.alloc(128), self.alloc(512), self.alloc(512)
        vector = self.alloc(64)
        self.w(fs+0x80, '3Q', vector, vector, vector+64)
        self.w(fs, 'Q', table)
        self.w(table+0xd8, 'Q', self.EXISTS); self.w(table+0x18, 'Q', self.OPEN)
        self.w(table+0x140, 'Q', 0x54b774)  # Actual source filesystem virtual slot.
        self.w(context+0x50, 'Q', fs)
        for i in range(6):
            self.w(owner+0x30+i*24, 'Q', self.alloc(8))
        returned = self.call(0x8f8508, {'X0': owner, 'X1': context})
        begin, end = self.r(fs+0x80, '2Q')
        order = [self.archives[self.r(a, 'Q')[0]] for a in range(begin, end, 8)]
        mount_trace = list(self.trace)
        self.stage, self.trace = 'search', []
        name, output = self.alloc(64), self.alloc(8)
        self.uc.mem_write(name, b'texture/lightmap.tga\0')
        self.call(0x54bc84, {'X0': fs, 'X1': name, 'X8': output})
        attempts = [r['pack'] for r in self.trace if r['kind'] == 'archiveLookup']
        return {'mountReturned': returned, 'order': order, 'attempts': attempts,
                'selected': attempts[-1] if self.r(output, 'Q')[0] else None,
                'presence': mount_trace, 'coldCache': True, 'otherArchiveGroupsEmpty': True,
                'archiveStreamsAreInterfaces': True, 'nativeCPU': True, 'originalDeviceObserved': False}

    def no_record(self, raw, object_id):
        table, holder, rows, maximum = self.alloc(len(raw)), self.alloc(8), self.alloc(24), self.alloc(4)
        self.uc.mem_write(table, raw); self.w(holder, 'Q', table)
        self.call(0x3293a8, {'X0': holder, 'W1': object_id, 'X2': rows, 'X3': maximum})
        if self.r(rows, '3Q') != (0, 0, 0):
            raise ValueError('Original DAT unexpectedly has object records')
        owner = self.alloc(0x200)
        self.call(0x33db74, {'X0': owner})
        before = bytes(self.uc.mem_read(owner, 0x200))
        textures, array = self.alloc(24), self.alloc(8)
        self.w(textures, '3Q', array, array+8, array+8)
        self.w(0x25091e8, 'B', 1)  # Explicit lightmap-enabled branch.
        self.call(0x33ee00, {'X0': owner, 'W1': 0, 'X2': textures, 'X3': rows})
        if before != bytes(self.uc.mem_read(owner, 0x200)):
            raise ValueError('Original empty-record setter modified fresh owner')
        # Explicit loaded model pointer; guard must return before traversing it.
        self.w(owner+0x98, 'Q', self.alloc(64))
        before = bytes(self.uc.mem_read(owner, 0x200))
        self.call(0x33faa0, {'X0': owner, 'W1': 0})
        if before != bytes(self.uc.mem_read(owner, 0x200)):
            raise ValueError('Original empty-atlas guard modified owner')
        return {'objectId': object_id, 'recordCount': 0, 'atlasMaximumOutput': self.r(maximum, 'I')[0],
                'freshVectorsUnchanged': True, 'noAtlasReplacement': True, 'nativeCPU': True,
                'loadedModelPointerFixture': True, 'GPUExecuted': False}
