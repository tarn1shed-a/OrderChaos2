"""Execute original property rewrite callbacks and source-array reconstruction."""
from native_shader_preprocess_probe import NativeShaderPreprocessProbe
from scene_shader_rewrite import verify_native, property_spans


class NativeShaderRewriteProbe(NativeShaderPreprocessProbe):
    def __init__(self, image):
        verify_native(image); super().__init__(image)
        from unicorn import UC_HOOK_CODE
        for at in (0x148c160, 0x2a1000, 0x2a10a0, 0x2a1380, 0x14903e4, 0x1484ce8, 0x148ca60, 0x1484b48):
            self.uc.hook_add(UC_HOOK_CODE, self._hook, begin=at, end=at)

    def run(self, at):
        self.uc.emu_start(at, self.BASE+0x1ff04, count=1000000)
        if self.get('PC') != self.BASE+0x1ff00: raise ValueError('Rewrite probe exceeded instruction bound')

    def _hook(self, uc, at, size, data):
        b = self.BASE
        if at == 0x148c160:
            self.write(self.get('SP')+0x18, 'B', int(self.enabled)); return
        if at == 0x14836bc:
            self.rewrite_calls += 1; return  # Execute the original body, not a callback result.
        if at == 0x1484b48:
            self.rewrite_returns.append(self.get('W0')); return
        if at == 0x1484ce8:
            if self.get('X0') != b+0x148: raise ValueError('Rewrite insertion receiver changed')
            start, end = self.get('X1')-b-0x4000, self.get('X2')-b-0x4000
            if not 0 <= start <= end <= self.source_length: raise ValueError('Rewrite range outside source')
            self.events.append({'start': start, 'end': end,
                                'text': self.string_bytes(self.get('X3')) if self.get('X3') else None,
                                'owned': self.get('W4') & 1})
            return  # Original48-byte allocation/stores and list insertion execute.
        if at == 0x148ca60:
            self.records = []; sentinel = b+0x148; pointer = self.read(sentinel, 'Q')[0]
            for _ in range(9):
                if pointer == sentinel: break
                start, end, text = self.read(pointer+0x10, '3Q')
                self.records.append({'start': start-b-0x4000, 'end': end-b-0x4000,
                                     'text': self.string_bytes(text) if text else None,
                                     'owned': self.read(pointer+0x28, 'B')[0]})
                pointer = self.read(pointer, 'Q')[0]
            else: raise ValueError('Unexpected insertion-record list size/cycle')
            if self.records != self.events: raise ValueError('Original insertion-record layout/list changed')
            return  # Execute complete original cleanup after recording its real list.
        if at in (0x2a1000, 0x2a10a0, 0x2a1380):
            char = self.get('W0'); alpha = 65 <= char <= 90 or 97 <= char <= 122
            value = alpha if at == 0x2a1000 else ((alpha or 48 <= char <= 57) if at == 0x2a10a0 else char in (9, 10, 11, 12, 13, 32))
            self.set('W0', int(value)); self.set('PC', self.get('X30')); return
        if at == 0x29f4c0:
            amount = self.get('X2')
            if amount > 8192: raise ValueError('Unbounded rewrite copy')
            if amount:
                value = self.string_bytes(self.get('X1'))[:amount]
                uc.mem_write(self.get('X0'), value+bytes(amount-len(value)))
            self.set('PC', self.get('X30')); return
        if at == 0x14903e4: raise ValueError('Native rewrite-error formatting is outside probe scope')
        return super()._hook(uc, at, size, data)

    def rewrite(self, source, stage=1, flags=16, allow_alpha=1, alpha_func=2, extra=None, enabled=True):
        if type(enabled) is not bool: raise ValueError('Expected explicit rewrite switch')
        property_spans(source)
        self.enabled = enabled; self.source_length = len(source); self.events = []; self.records = []
        self.rewrite_calls = 0; self.rewrite_returns = []
        result = super().preprocess(source, stage, flags, allow_alpha, alpha_func, extra)
        return {**result, 'records': self.records, 'rewriteCalls': self.rewrite_calls, 'rewriteReturns': self.rewrite_returns}
