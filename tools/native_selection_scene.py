"""Bounded original selection callbacks; recording sinks do not create models.

The original ARM64 selection and integer-config consumer execute in Unicorn.
String ownership, a supplied configuration value, libc strtol and visibility
notifications are explicit host boundaries. No account/server/GPU is supplied.
"""
import ctypes
import hashlib

from source_physics import SourcePhysics

ROUTINES = {
    0x53b5c8: (3776, '47ee5ff8976cdb9cc2e4c8735c19a4a0db5c12a2116156fb925ed7ea28faff1f'),
    0x53d8ec: (3636, '20847bf8a531da647ca375ee3e01012c2aac376d1f94faea5eaaf1c0105c16fd'),
    0x543568: (900, 'ee56ae7b09ff4befc131903d0c88559b4565353339c885a584948e3c63da1c37'),
    0xa792c4: (316, '9054e5a35aa7790c22c2af4aab4dcff66b704a02faefb0793ce5041e20f867a2'),
    0x53ca0c: (2248, '01493e438fa22bedbdaa97e6d35b3394411f02630ba18171227a52b4c985b649'),
}


def verify(image):
    for address, (size, digest) in ROUTINES.items():
        if hashlib.sha256(image.read(address, size)).hexdigest() != digest:
            raise ValueError('Original selection consumer differs')


class NativeSelectionScene(SourcePhysics):
    VISIBILITY = SourcePhysics.EXIT + 0x800

    def __init__(self, image):
        from unicorn import UC_HOOK_CODE
        verify(image)
        super().__init__(image)
        self.notifications = []
        self.config_value = b''
        for at in (0x1de639c, 0xa78ffc, self.VISIBILITY):
            self.uc.hook_add(UC_HOOK_CODE, self.hook, begin=at, end=at)
        self.libc_strtol = ctypes.CDLL(None).strtol
        self.libc_strtol.argtypes = (ctypes.c_char_p, ctypes.POINTER(ctypes.c_void_p), ctypes.c_int)
        self.libc_strtol.restype = ctypes.c_long

    def owned_string(self, raw):
        p = self.alloc(len(raw) + 25)
        self.w(p, '3Q', len(raw), len(raw), 1000)
        self.uc.mem_write(p + 24, raw + b'\0')
        return p + 24

    def hook(self, uc, address, size, data):
        if address == self.VISIBILITY:
            self.notifications.append({'object': self.get('X0'), 'visible': self.get('W1'),
                                       'secondArgument': self.get('W2')})
        elif address == 0x1de639c:
            self.w(self.get('X0'), 'Q', self.owned_string(self.cstr(self.get('X1'))))
        elif address == 0xa78ffc:
            # Explicit parsed-config input; the configuration loader is not run.
            self.w(self.get('X8'), 'Q', self.owned_string(self.config_value))
        elif self.imports.get(address) == 'strtol':
            raw = self.cstr(self.get('X0'))
            host = ctypes.create_string_buffer(raw)
            end = ctypes.c_void_p()
            value = self.libc_strtol(host, ctypes.byref(end), self.get('W2'))
            consumed = end.value - ctypes.addressof(host)
            self.w(self.get('X1'), 'Q', self.get('X0') + consumed)
            self.set('X0', value & ((1 << 64) - 1))
        else:
            return super().hook(uc, address, size, data)
        self.set('PC', self.get('X30'))

    def config_integer(self, value, default=5):
        if not isinstance(value, str) or len(value) > 64 or '\0' in value:
            raise ValueError('Expected bounded explicit configuration input')
        self.config_value = value.encode('ascii')
        config, section, key = [self.alloc(16) for _ in range(3)]
        result = self.call(0xa792c4, {'X0': config, 'X1': section, 'X2': key,
                                    'X3': default & ((1 << 64) - 1)})
        return result - (1 << 64) if result >> 63 else result

    def switch_existing(self, index, previous=0):
        if index not in (0, 1) or previous not in (None, 0, 1):
            raise ValueError('Only supplied existing-list records are supported')
        manager, vector, vtable = self.alloc(0x200), self.alloc(16), self.alloc(0x100)
        objects = [self.alloc(0x100) for _ in range(2)]
        self.w(vtable + 0x80, 'Q', self.VISIBILITY)
        for i, obj in enumerate(objects):
            shared, wrapper = self.alloc(8), self.alloc(8)
            self.w(wrapper, 'Q', obj)
            self.w(shared, 'Q', wrapper)
            self.w(vector + 8*i, 'Q', shared)
            self.w(obj, 'Q', vtable)
        self.w(manager + 0x128, '2Q', vector, vector + 16)
        self.w(manager + 0x160, 'Q', objects[previous] if previous is not None else 0)
        self.notifications = []
        returned = self.call(0x543568, {'X0': manager, 'W1': index})
        return {'returned': returned, 'selectedIndex': objects.index(self.r(manager + 0x160, 'Q')[0]),
                'notifications': [{**event, 'object': objects.index(event['object'])}
                                  for event in self.notifications],
                'originalInstructionsExecuted': True, 'modelOrGPUCreated': False}
