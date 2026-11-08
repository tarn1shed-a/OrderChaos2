"""Original document-header gate and driver profile writers in isolated ARM64."""
from native_effect_remapping_probe import NativeEffectRemappingProbe
from scene_profile_inputs import verify_native, header_contract, ROOT_TAG, VERSION
from scene_material_cache import word


class NativeProfileInputsProbe(NativeEffectRemappingProbe):
    INPUT = 0x70000000

    def __init__(self, image):
        verify_native(image); super().__init__(image); self.uc.mem_map(self.INPUT, 0x10000)
        from unicorn import UC_HOOK_CODE
        for at in (0x1273160, 0x142ad3c, 0x1409fc8, 0x1409b04, 0x1409bb8, 0x14098e4, 0x140b688,
                   *[self.INPUT+0xf000+x for x in (0, 0x20, 0x40, 0x60, 0x80, 0x200, 0x220)]):
            self.uc.hook_add(UC_HOOK_CODE, self._hook, begin=at, end=at)

    def _hook(self, uc, at, size, data):
        p = self.INPUT
        if self.phase == 'profile-header':
            if at == 0x14098e4: return
            if at in (0x1409fc8, 0x1409b04, 0x1409bb8):
                self.header_accepted = at == 0x1409fc8; uc.emu_stop(); return
            if at == 0x1273160:
                if self.read(self.get('X0'), 'Q')[0] != p+0x2000: raise ValueError('Parser holder identity changed')
                self.write(self.get('X8'), 'Q', p+0x3000 if self.document_present else 0)
            elif at == 0x142ad3c: self.messages += 1
            elif at == 0x11dcd28: self.set('W0', self.alloc_mode)
            elif at == 0x11dcd40: self.alloc_mode = self.get('W0')
            elif at == 0x29e3c0:
                self.set('W0', int(self.string(self.get('X0')) != self.string(self.get('X1'))))
            elif at == p+0xf000:
                if self.get('X0') != p+0x2000: raise ValueError('Stream identity changed')
                self.set('X0', p+0x7000)
            elif at in (p+0xf020, p+0xf040, p+0xf060, p+0xf080):
                if self.get('X0') != p+0x3000: raise ValueError('Parsed node identity changed')
                if at == p+0xf020:
                    self.set('W0', self.reader_word if self.reader_calls == 0 else 0); self.reader_calls += 1
                elif at == p+0xf040: self.set('W0', self.node_type)
                elif at == p+0xf060: self.set('X0', p+0x4000)
                else:
                    if self.string(self.get('X1')) != 'version': raise ValueError('Header attribute changed')
                    self.set('X0', p+0x4100 if self.version_present else 0)
            else: return super()._hook(uc, at, size, data)
            self.set('PC', self.get('X30')); return
        if self.phase == 'profile-wrapper' and at in (0x14098e4, 0x140b688):
            if self.get('X0') != self.TECH+0x1800: raise ValueError('Driver registry delegate changed')
            if at == 0x14098e4 and self.get('X1') != p+0x1000: raise ValueError('Driver loader holder changed')
            self.delegate_calls += 1; self.set('W0', self.delegate_word); self.set('PC', self.get('X30')); return
        if self.phase == 'profile-scope' and at in (p+0xf200, p+0xf220):
            if self.get('X0') != p+0x9000: raise ValueError('Render-state virtual receiver changed')
            if at == p+0xf200:
                if self.read(self.get('X1'), 'Q')[0] != p+0x6000 or bytes(uc.mem_read(self.get('X2'), 3)) != bytes(3):
                    raise ValueError('Original parent push arguments changed')
                self.render_pushes += 1; self.render_events.append(['push', self.current_profile()])
            else:
                self.render_pops += 1; self.render_events.append(['pop', self.current_profile()])
                self.write(self.get('X8'), 'Q', 0)
            self.set('PC', self.get('X30')); return
        return super()._hook(uc, at, size, data)

    def header(self, tag=ROOT_TAG, version=VERSION, node_type=1, reader_word=1, document=True):
        header_contract(tag, version, node_type, reader_word, document)
        p = self.INPUT; self.uc.mem_write(p, bytes(0x10000)); self.registers(); self.phase = 'profile-header'
        self.alloc_mode = 0; self.messages = 0; self.header_accepted = None; self.reader_calls = 0
        self.document_present, self.version_present = document, version is not None
        self.node_type, self.reader_word = node_type, reader_word
        self.write(p+0x1000, 'Q', p+0x2000); self.write(p+0x2000, 'Q', p+0x2100)
        self.write(p+0x2008, 'I', 100); self.write(p+0x2150, 'Q', p+0xf000)
        self.write(p+0x3000, 'Q', p+0x3100); self.write(p+0x3008, 'I', 100)
        for slot, delta in [(0x18, 0x20), (0x28, 0x40), (0x80, 0x60), (0x50, 0x80)]: self.write(p+0x3100+slot, 'Q', p+0xf000+delta)
        self.uc.mem_write(p+0x4000, (tag or '').encode()+b'\0')
        if version is not None: self.uc.mem_write(p+0x4100, version.encode()+b'\0')
        self.set('X0', p+0x8000); self.set('X1', p+0x1000)
        self.uc.emu_start(0x14098e4, self.BASE+0x1ff04, count=3000)
        if self.header_accepted is None: raise ValueError(f'Header gate exceeded declared frontier at{self.get("PC"):#x}; input={(tag, version, node_type, reader_word, document)}')
        return {'headerAccepted': self.header_accepted, 'messages': self.messages,
                'stop': hex(self.get('PC')), 'streamReferences': self.read(p+0x2008, 'I')[0],
                'allocatorModeAtStop': self.alloc_mode, 'fullParserExecuted': False}

    def init_driver(self, initial):
        word(initial, 32); p = self.INPUT; self.uc.mem_write(p, bytes(0x10000))
        self.write(p+0x9000, 'Q', p+0x9400); self.write(p+0x92f8, 'Q', self.TECH+0x1800)
        self.write(p+0x9320, 'I', initial); self.write(p+0x9530, 'Q', p+0xf200); self.write(p+0x9538, 'Q', p+0xf220)
        self.write(p+0x6008, 'I', 100); self.scope_stack = []; self.render_pushes = self.render_pops = 0; self.render_events = []

    def current_profile(self): return self.read(self.INPUT+0x9320, 'I')[0]

    def load_wrapper(self, result_word, clear=False):
        word(result_word, 32)
        if type(clear) is not bool: raise ValueError('Expected explicit clear wrapper')
        self.registers(); self.phase = 'profile-wrapper'; self.delegate_word = result_word; self.delegate_calls = 0
        self.set('X0', self.INPUT+0x9000); self.set('X1', self.INPUT+0x1000)
        self.run(0x147f288 if clear else 0x147f24c, 300)
        return {'profile': self.current_profile(), 'returnWord': self.get('W0'), 'delegateCalls': self.delegate_calls}

    def push_profile(self, target, kind=0):
        word(target, 32)
        if type(kind) is not int or kind not in (0, 1) or len(self.scope_stack) >= 4: raise ValueError('Uncovered scoped profile fixture')
        node = self.INPUT+0x5000+256*len(self.scope_stack); self.uc.mem_write(node, bytes(128))
        self.write(node+0x20, 'Q', self.INPUT+0x6000); self.write(node+(0x40 if kind == 0 else 0x44), 'I', target)
        self.registers(); self.phase = 'profile-scope'; self.set('X0', node); self.set('X1', self.INPUT+0x9000)
        self.run(0x12fc848 if kind == 0 else 0x12fce90, 500); self.scope_stack.append((node, kind))
        return {'profile': self.current_profile(), 'saved': self.read(node+(0x3c if kind == 0 else 0x40), 'I')[0],
                'parentActive': self.read(node+0x38, 'B')[0], 'materialReferences': self.read(self.INPUT+0x6008, 'I')[0]}

    def pop_profile(self):
        if not self.scope_stack: raise ValueError('No scoped profile fixture to end')
        node, kind = self.scope_stack.pop(); self.registers(); self.phase = 'profile-scope'
        self.set('X0', node); self.set('X1', self.INPUT+0x9000)
        self.run(0x12fc87c if kind == 0 else 0x12fcec4, 500)
        return {'profile': self.current_profile(), 'parentActive': self.read(node+0x38, 'B')[0],
                'materialReferences': self.read(self.INPUT+0x6008, 'I')[0]}

    def select_current(self, base, variant):
        current = self.current_profile()
        if (type(base) is not int or not 0 <= base < len(self.built_rows) or type(variant) is not int or
                not 0 <= variant < self.variant_count or current != 0xffffffff and current >= self.profile_count):
            raise ValueError('Selector outside explicit current driver profile fixture')
        p = self.INPUT; self.registers(); self.phase = 'registration'; self.selector_calls = 0
        self.write(p+0x8008, 'Q', self.output_effect); self.write(p+0x8010, 'B', base); self.write(p+0x8018, 'B', variant)
        self.set('X0', p+0x8000); self.set('X1', p+0x9000); self.run(0x13ed140, 300)
        return self.get('W0')
