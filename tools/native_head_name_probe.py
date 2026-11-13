"""Bounded original CPU font requests and billboard transform, with named fixtures.

No FreeType success, glyph bitmap, live actor relationship or Android GPU output
is fabricated. Stop at face creation, size request, or matrix upload boundaries.
"""
import math

from source_physics import SourcePhysics
from head_name_evidence import verify_native


class HeadNameProbe(SourcePhysics):
    PREFLIGHT = SourcePhysics.EXIT+0x900

    def __init__(self, image):
        verify_native(image)
        super().__init__(image)
        from unicorn import UC_HOOK_CODE
        for at in (0x5e0590, 0x1473ae8, 0x1a6178c, 0x1a56a48,
                   0x3aa6f4, 0x1a58fb4, self.PREFLIGHT):
            self.uc.hook_add(UC_HOOK_CODE, self.hook, begin=at, end=at)

    def hook(self, uc, at, size, data):
        if at == 0x5e0590:
            self.set('W0', 0)  # Explicit non-bidi, empty-string matrix fixture.
        elif at == 0x1473ae8:
            if self.get('W1') != 2 or self.get('W3') != 0:
                raise ValueError('Unexpected original matrix upload kind')
            self.matrix_output = list(self.r(self.get('X2'), '16f'))
            self.set('PC', self.EXIT)
            return
        elif at == 0x1a6178c:
            self.w(self.get('X0'), 'Q', self.alloc(8))  # Library token, not FreeType.
            self.set('W0', 0)
        elif at == 0x1a56a48:
            self.font_output = self.cstr(self.get('X1')).decode('ascii')
            if self.get('X2') != 0:
                raise ValueError('Unexpected original font face index')
            self.set('PC', self.EXIT)
            return
        elif at == 0x3aa6f4:
            # Only the explicit cache-miss state; do not claim source cache ran.
            self.w(self.cache_fixture+28, 'I', 0)
            self.set('X0', self.cache_fixture)
        elif at == 0x1a58fb4:
            self.face_output = self.get('X0')
            self.size_output = self.get('W2')
            self.set('PC', self.EXIT)
            return
        elif at == self.PREFLIGHT:
            self.preflight_output = 'position-requested'
            self.set('PC', self.EXIT)
            return
        else:
            return super().hook(uc, at, size, data)
        self.set('PC', self.get('X30'))

    def font_request(self, language, *, secondary=False):
        if not isinstance(language, int) or not 0 <= language < 15:
            raise ValueError('Only verified source language-table indices are allowed')
        self.w(0x2529aa8, 'I', language)
        owner = self.alloc(0x4200)
        self.font_output = None
        self.call(0x3aa2b4 if secondary else 0x3a9bf4, {'X0': owner})
        return {'languageIndexFixture': language, 'secondaryLoader': secondary,
                'requestedPath': self.font_output, 'FreeTypeExecuted': False}

    def glyph_face(self, *, secondary, secondary_available):
        owner, output = self.alloc(0x4200), self.alloc(32)
        primary, fallback = self.alloc(8), self.alloc(8)
        self.w(owner+0x4088, 'Q', primary)
        self.w(owner+0x40b0, 'Q', fallback if secondary_available else 0)
        self.cache_fixture = self.alloc(32)
        self.w(0x2509354, 'I', 2)  # Explicit raster-density fixture.
        self.face_output = None
        self.call(0x36a218, {'X0': owner, 'X1': output, 'W2': ord('A'),
                            'W3': 16, 'W4': 0, 'W5': int(secondary)})
        if self.face_output not in (primary, fallback) or (self.face_output == fallback and not secondary_available):
            raise ValueError('Unexpected original glyph face selection')
        return {'requestedSecondary': secondary, 'secondaryAvailable': secondary_available,
                'selectedFace': 'secondary' if self.face_output == fallback else 'primary',
                'requestedRasterHeight': self.size_output, 'FreeTypeExecuted': False,
                'cacheMissIsFixture': True}

    def matrix(self, *, camera=(0, 0, 10), position=(0, 0, 0), scale=(1, 1, 1), basis=None):
        if any(len(v) != 3 or not all(math.isfinite(n) for n in v) for v in (camera, position, scale)):
            raise ValueError('Finite three-axis matrix inputs required')
        basis = list(basis) if basis is not None else [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
        if len(basis) != 16 or not all(math.isfinite(n) for n in basis):
            raise ValueError('Finite source camera-basis fixture required')
        root, context, cam, vt_memory, driver, world, render = [self.alloc(n) for n in
                                                              (0x8210, 0x300, 0x400, 0x420, 0x100, 0x300, 0x100)]
        vt = vt_memory+0x20  # Explicit zero virtual-base offset/refcount fixture.
        self.w(root+8, 'Q', vt); self.w(cam, 'Q', vt)
        self.w(vt+0x90, 'Q', 0x1364640); self.w(vt+0x150, 'Q', 0x1363f10)
        self.w(root+0x120, 'Q', context); self.w(context+0x38, 'Q', driver)
        self.w(context+0x238, 'Q', cam)
        self.w(root+0x158, 'Q', 0x2528d78)  # Real source empty wide-string singleton.
        transform = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, *position, 1]
        self.w(root+0x30, '16f', *transform)  # (root + 8) + source getter's 0x28.
        transform[12:15] = camera
        self.w(cam+0x28, '16f', *transform)
        self.w(cam+0x78, '16f', *basis)
        self.w(root+0xcc, '3f', *scale)  # (root + 8) + source getter's 0xc4.
        self.w(0x2528db0, 'Q', world); self.w(world+0x1c0, 'Q', render)
        self.w(render+0x30, 'Q', cam)
        self.w(0x250bb48, 'B', 1)
        self.matrix_output = None
        self.call(0x36d344, {'X0': root})
        return {'cameraPositionFixture': list(camera), 'textPositionFixture': list(position),
                'nodeScaleFixture': list(scale), 'basisFixture': basis,
                'uploadedMatrix': self.matrix_output, 'nativeCPU': True,
                'GPUExecuted': False, 'emptyTextFixture': True,
                'liveCameraBasisRecovered': False}

    def preflight(self, *, enabled, name, model):
        actor, vt = self.alloc(0x600), self.alloc(0x400)
        self.w(actor, 'Q', vt)
        self.w(vt+0x70, 'Q', self.PREFLIGHT)
        self.w(vt+0x310, 'Q', self.FALSE)  # Explicit no dynamic-name refresh fixture.
        header = self.alloc(32)
        self.w(header, 'Q', 1 if name else 0)
        self.w(actor+0x210, 'Q', header+24)
        self.w(actor+0x38, 'Q', self.alloc(8) if model else 0)
        self.w(0x250bb48, 'B', int(enabled))
        self.preflight_output = 'returned-before-position'
        self.call(0x91088c, {'X0': actor})
        return self.preflight_output

    def material(self, *, manager_present=True):
        root, owner, material = self.alloc(0x8210), self.alloc(0x20), self.alloc(8)
        self.w(root+0x81d8, 'Q', owner if manager_present else 0)
        self.w(owner+0x10, 'Q', material)
        return self.call(0x36e18c, {'X0': root}) == material

    def relationship_manager_gate(self, *, flag, code):
        """Raw observed fields only; their gameplay labels are not recovered."""
        owner = self.alloc(0x60)
        self.w(owner+0x14, 'B', flag)
        self.w(owner+0x50, 'I', code)
        return bool(self.call(0x82f09c, {'X0': owner}) & 1)
