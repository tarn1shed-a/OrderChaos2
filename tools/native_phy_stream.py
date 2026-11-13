"""Run the original archive-memory stream and PHY reader, including exact EOF.

The archive has already been decoded and SHA checked by the caller. Allocation,
libc and installation of the file-wrapper fields are host interfaces. Neither
the original file/count nor collision geometry is repaired or padded here.
"""
import hashlib

from scene_collision import decode_phy
from source_physics import SourcePhysics


ROUTINES = {
    0x122987c: (352, '2aeb2de1f263b219d013e3740612e1e80ab9f34014408a70bad817b2ccf42ce9'),
    0x12762ec: (116, '27bf52487476bf42f5c52d59d88a381f6f3655c427973146bec0c5c323d829bb'),
    0xa7fca4: (100, 'cc73e8a76fcf6b7c691bd27d4d73c5399ef5095fed3de437748313d1f666ea49'),
    0xa9ad2c: (16, '04560bcab57bc7e7e2590407c75ce7065853f35427b5d7b8b3467bda04eef066'),
    0xa7fd84: (8, 'f289023bfc90be5c90aa1a98a40c5b356af639e69af0399f5914b2202364955c'),
}


class NativePHYStreamMixin:
    def __init__(self, image):
        for address, (size, digest) in ROUTINES.items():
            if hashlib.sha256(image.read(address, size)).hexdigest() != digest:
                raise ValueError('Original archive stream routine differs')
        super().__init__(image)
        self.phy_read_reports = []

    def hook(self, uc, address, size, data):
        name = self.imports.get(address)
        if name == 'malloc':
            self.set('X0', self.alloc(self.get('X0')))
        elif name == 'free':
            pass  # Bounded inspection arena, same ownership boundary as delete.
        else:
            return super().hook(uc, address, size, data)
        self.set('PC', self.get('X30'))

    def memory_stream(self, raw, name):
        if not raw or len(name.encode()) >= 1024:
            raise ValueError('Empty stream or unbounded source name')
        data = self.alloc(len(raw)); self.uc.mem_write(data, raw)
        filename = self.alloc(len(name.encode()) + 1)
        self.uc.mem_write(filename, name.encode() + b'\0')
        output = self.alloc(8)
        # Actual constructor used by original decompression branches 8 and 14.
        self.call(0x122987c, {'X0': data, 'X1': len(raw), 'X2': filename,
                              'W3': 0, 'X8': output})
        stream = self.r(output, 'Q')[0]
        if self.r(stream, 'Q')[0] != 0x246e860:
            raise ValueError('Original memory-stream constructor selected another class')
        return stream, filename

    def read_phy(self, raw, name='source.phy'):
        stream, filename = self.memory_stream(raw, name)
        # VFS has supplied the decoded resource. Install that explicit handle
        # into the source file-wrapper layout; its real read/name/valid methods
        # execute. Do not claim the absent Android VFS constructor ran.
        self.w(self.stream, 'Q', 0x2425a70)
        self.w(self.stream + 0x10, 'Q', stream)
        self.w(self.stream + 0x18, 'Q', len(raw))
        self.w(self.stream + 0x20, 'Q', filename)
        self.uc.mem_write(self.filename, name.encode() + b'\0')
        self.uc.mem_write(self.descriptor, bytes(16))
        self.w(self.descriptor + 8, 'Q', self.stream)
        head = self.call(0xa8674c, {'X0': self.descriptor})
        count = 0; seen = set(); pointer = head
        while pointer:
            if pointer in seen or count >= 4096:
                raise ValueError('Invalid original PHY chain')
            seen.add(pointer); count += 1
            pointer = self.r(pointer + 8, 'Q')[0]
        error = self.r(self.descriptor, 'B')[0]
        at = self.r(stream + 0x30, 'Q')[0]
        if not head or at != len(raw):
            raise ValueError('Original PHY did not retain a complete consumed prefix')
        # A failed read alone never permits partial geometry. Require the
        # retained source records to end at the exact unmodified file boundary.
        decoded = decode_phy(raw, retained_at_eof=count if error else None)
        if count != len(decoded['shapes']):
            raise ValueError('Source records and original retained chain disagree')
        self.phy_read_reports.append({
            'name': name, 'sourceSHA256': hashlib.sha256(raw).hexdigest(),
            'declaredShapeCount': int.from_bytes(raw[:4], 'little'),
            'retainedShapeCount': count, 'bytesConsumed': at,
            'descriptorError': error,
            'scope': 'original archive memory read, file-wrapper read and PHY reader; host VFS handle/allocation/libc',
        })
        return head


class NativePHYStreamPhysics(NativePHYStreamMixin, SourcePhysics):
    pass
