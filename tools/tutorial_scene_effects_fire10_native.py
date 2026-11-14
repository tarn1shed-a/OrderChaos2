"""Consume the original shape/quality header before the fire10 clock probe."""
from tutorial_scene_effects_lifecycle_probe import SceneEffectLifecycleProbe


class SceneFire10NativeProbe(SceneEffectLifecycleProbe):
    def __init__(self, image):
        super().__init__(image)
        from unicorn import UC_HOOK_CODE
        for a in (0xeb3f58, 0xeb3f84):
            self.uc.hook_add(UC_HOOK_CODE, self.hook, begin=a, end=a)

    def hook(self, uc, a, n, d):
        if a in self.stop: return super().hook(uc, a, n, d)
        if a == 0xeb3f58:
            if self.header is None: raise ValueError('Original header required')
            uc.mem_write(self.get('SP')+0x50, self.header)
            self.w(self.get('SP')+0x48, 'Q', self.header_emitter)
            return
        return super().hook(uc, a, n, d)

    def make_emitter(self, root, raw, decoded):
        em = super().make_emitter(root, raw, decoded)
        self.header = raw[decoded['headerOffset']:decoded['headerOffset']+80]
        self.header_emitter = em
        try: self.fragment(0xeb3f58, (0xeb3f84,), {})
        finally: self.header = None
        return em
