"""Run bounded original preview math and display gates with explicit fixtures.

The callbacks supply SWF visibility, actor relation, selected actor and a draw
boundary. They never pretend that a browser role has original actor state, a
native material, a compiled shader, or a successfully rendered texture.
"""
import math

from source_physics import SourcePhysics
from character_display_evidence import verify_native


class CharacterDisplayProbe(SourcePhysics):
    CALLBACK = SourcePhysics.EXIT + 0x800

    def __init__(self, image):
        verify_native(image)
        super().__init__(image)
        from unicorn import UC_HOOK_CODE
        for at in (0x616564, 0x619ba4, 0x91088c, 0x909770, 0x908634,
                   self.CALLBACK):
            self.uc.hook_add(UC_HOOK_CODE, self.hook, begin=at, end=at)

    def hook(self, uc, at, size, data):
        if self.imports.get(at) == 'tan':
            self.df('D0', math.tan(self.gd('D0')))
        elif at == 0x616564:
            # Explicit SWF visibility input; no synthetic Flash object graph.
            if self.mode != 'preview': raise ValueError('Unexpected preview visibility lookup')
            self.set('W0', int(self.visible))
        elif at == self.CALLBACK:
            self.callback_calls += 1
            self.set('W0', int(self.suppressed if self.mode == 'preview' else self.relation))
        elif at == 0x619ba4:
            if self.mode != 'preview': raise ValueError('Unexpected preview draw boundary')
            self.outcome = 'passed-pre-draw-gates'
            self.set('PC', self.EXIT)
            return
        elif at in (0x91088c, 0x909770):
            if self.mode != 'name': raise ValueError('Unexpected name renderer boundary')
            self.outcome = 'draw-name-branch' if at == 0x91088c else 'remove-name-branch'
            self.set('PC', self.EXIT)
            return
        elif at == 0x908634:
            if self.mode != 'name': raise ValueError('Unexpected selected-actor lookup')
            self.set('X0', self.selected)
        else:
            return super().hook(uc, at, size, data)
        self.set('PC', self.get('X30'))

    def preview_gate(self, *, model=True, created=True, visible=True, texture=True,
                     once=False, already_drawn=False, suppressed=False):
        self.mode = 'preview'
        self.visible, self.suppressed = visible, suppressed
        self.callback_calls, self.outcome = 0, 'not-drawn'
        obj, vt = self.alloc(0x100), self.alloc(0x100)
        self.w(obj, 'Q', vt)
        self.w(vt+0xb8, 'Q', self.CALLBACK)
        self.w(obj+0xc8, 'Q', self.alloc(0x20) if model else 0)
        self.w(obj+0xbc, '2B', int(created), int(texture))
        self.w(obj+0x70, '2B', int(once), int(already_drawn))
        self.call(0x619b10, {'X0': obj}, limit=1000)
        return {'outcome': self.outcome, 'suppressionChecks': self.callback_calls,
                'alreadyDrawn': bool(self.r(obj+0x71, 'B')[0]),
                'textureRendered': False}

    def name_gate(self, *, flags=0, local_actor=True, relation=False, selected=False):
        self.mode, self.relation = 'name', relation
        self.callback_calls, self.outcome = 0, 'not-drawn'
        actor, local, manager, vt = [self.alloc(n) for n in (0x600, 0x100, 0x100, 0x400)]
        self.w(actor, 'Q', vt)
        self.w(vt+0x308, 'Q', 0x909770)
        self.w(vt+0x168, 'Q', self.CALLBACK)
        self.w(local, 'Q', vt)
        self.w(actor+0x5a0, 'I', flags)
        self.w(manager+0x68, 'Q', local if local_actor else 0)
        self.w(0x2528df8, 'Q', manager)
        self.selected = actor if selected else 0
        self.call(0x8fe804, {'X0': actor}, limit=1000)
        return {'outcome': self.outcome, 'relationChecks': self.callback_calls,
                'textRendered': False, 'originalActorStateSupplied': False}

    def projection(self, *, aspect, fov=math.pi/4, near=.1, far=3000.):
        if not all(math.isfinite(v) for v in (aspect, fov, near, far)) or not (
                aspect > 0 and 0 < fov < math.pi and 0 < near < far):
            raise ValueError('Finite perspective parameters required')
        obj, vt = self.alloc(0x400), self.alloc(0x400)
        self.w(obj, 'Q', vt)
        self.w(vt+0x310, 'Q', self.FALSE)  # Explicit perspective branch.
        self.w(obj+0x178, '4f', fov, aspect, near, far)
        self.w(obj+0x188, 'B', 0)  # Finite projection constructor branch.
        self.call(0x12baf08, {'X0': obj}, limit=1000)
        return list(self.r(obj+0x210, '16f'))

    def light_defaults(self):
        obj, matrix_owner = self.alloc(0x90), self.alloc(8)
        # Non-null matrix owner selects source constructor's external-owner
        # branch; no pooled transform allocation is manufactured.
        self.call(0x13da1a8, {'X0': obj, 'X1': matrix_owner}, limit=1000)
        return {name: list(self.r(obj+off, '4f')) for name, off in
                [('ambient', 4), ('diffuse', 0x14), ('specular', 0x24)]}
