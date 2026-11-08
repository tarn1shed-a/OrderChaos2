"""Isolated ARM64 mesh-node construction and self-delegate submission.

Allocator, matrix refresh, mesh queries and queue callback are synthetic.
The original factory/constructors, node gate, fast visitor and submission body
execute in Unicorn; this is not the live client, GL or a full scene loader.
"""
import struct

from scene_sky_mesh import verify_native


class NativeSkyMeshProbe:
    BASE = 0x10000000

    def __init__(self, image):
        verify_native(image)
        from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
        from unicorn import arm64_const
        self.reg = arm64_const; self.uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        for segment in image.elf.iter_segments():
            if segment['p_type'] != 'PT_LOAD': continue
            start = segment['p_vaddr'] & ~4095
            end = (segment['p_vaddr']+segment['p_memsz']+4095) & ~4095
            self.uc.mem_map(start, end-start)
            self.uc.mem_write(segment['p_vaddr'], segment.data())
        for rel in image.elf.get_section_by_name('.rela.dyn').iter_relocations():
            if rel['r_info_type'] == 1027: self.write(rel['r_offset'], 'Q', rel['r_addend'])
        self.uc.mem_map(self.BASE, 0x20000); self.uc.mem_map(0x20000000, 0x10000)
        for at in [0x29f0f0, 0x1364674, 0x1132bc8, self.BASE+0x1ff00,
                   *[self.BASE+0x1f000+x for x in (0, 0x20, 0x28, 0x30, 0x60, 0x80, 0xa0, 0xc0)]]:
            self.uc.hook_add(UC_HOOK_CODE, self._hook, begin=at, end=at)

    def write(self, at, fmt, *v): self.uc.mem_write(at, struct.pack('<'+fmt, *v))
    def read(self, at, fmt): return struct.unpack('<'+fmt, self.uc.mem_read(at, struct.calcsize('<'+fmt)))
    def set(self, name, v): self.uc.reg_write(getattr(self.reg, 'UC_ARM64_REG_'+name), v)
    def get(self, name): return self.uc.reg_read(getattr(self.reg, 'UC_ARM64_REG_'+name))

    def registers(self):
        for i in range(31): self.set(f'X{i}', 0)
        for i in range(32): self.set(f'Q{i}', 0)
        self.set('SP', 0x20008000); self.set('X30', self.BASE+0x1ff00)

    def _hook(self, uc, at, size, data):
        if at == self.BASE+0x1ff00: uc.emu_stop(); return
        if at == 0x1132bc8:
            if self.get('X0') != self.BASE: raise ValueError('Self-delegate receiver changed')
            self.delegate_calls += 1
            return  # Execute the complete original submission body.
        if at == 0x29f0f0:
            if self.get('X0') != 0x190 or self.allocations: raise ValueError('Unexpected mesh allocation')
            self.allocations.append(0x190); self.set('X0', self.BASE)
        elif at == 0x1364674:
            if self.get('X0') != self.BASE: raise ValueError('Matrix refresh receiver changed')
            self.matrix_calls += 1; self.set('W0', 0)
        else:
            slot = at-self.BASE-0x1f000
            if slot == 0xc0:
                if self.get('X0') != self.BASE+0x6000 or self.get('X1') != self.BASE:
                    raise ValueError('Queue callback receiver/node changed')
                if (self.get('X2') != self.context_word or self.get('W7') != 0x7fffffff or
                        self.get('X6') != 0 or self.read(self.get('X3'), 'Q')[0] != 0):
                    raise ValueError('Queue callback arguments changed')
                self.submissions.append({'part': self.get('X4'), 'code': self.get('W5')})
            else:
                if self.get('X0') != self.BASE+0x4000: raise ValueError('Mesh callback receiver changed')
                if slot == 0x80:
                    if self.get('X1') != self.BASE+0x5000: raise ValueError('Mesh driver input changed')
                elif slot == 0x20: self.set('W0', len(self.classifications))
                elif slot == 0x28:
                    self.part = self.get('W1')
                    self.write(self.get('X8'), 'Q', self.BASE+0x7000)
                elif slot == 0x30: self.set('X0', 0)
                elif slot == 0xa0:
                    if (self.get('W1') != 0 or self.get('X2') != self.BASE+0x5000 or
                            self.get('W3') != self.part or self.get('W4') != self.context_word >> 16):
                        raise ValueError('Mesh classification arguments changed')
                    self.set('W0', self.classifications[self.part])
                elif slot == 0x60: self.cleanup.append(self.part)
                else: raise ValueError('Unexpected mesh callback')
        self.set('PC', self.get('X30'))

    def construct(self, mesh_present=True):
        if type(mesh_present) is not bool: raise ValueError('Expected explicit mesh presence')
        self.uc.mem_write(self.BASE, bytes(0x20000)); self.uc.mem_write(0x20000000, bytes(0x10000))
        self.registers(); self.allocations = []; self.matrix_calls = 0; self.delegate_calls = 0
        self.write(self.BASE, '400B', *([0xa5]*400))
        mesh = self.BASE+0x4000 if mesh_present else 0
        self.write(self.BASE+0x3000, 'Q', mesh)
        self.write(self.BASE+0x4008, 'I', 100)
        self.set('X2', self.BASE+0x3000); self.set('X8', self.BASE+0x3100)
        self.uc.emu_start(0x112b640, self.BASE+0x1ff04, count=1000)
        if self.get('PC') != self.BASE+0x1ff00: raise ValueError('Mesh constructor exceeded bounds')
        return {'vptr': self.read(self.BASE, 'Q')[0], 'delegate': self.read(self.BASE+0x120, 'Q')[0],
                'mesh': self.read(self.BASE+0x158, 'Q')[0], 'mode': self.read(self.BASE+0x170, 'I')[0],
                'output': self.read(self.BASE+0x3100, 'Q')[0], 'nodeReferences': self.read(self.BASE+0x188, 'I')[0],
                'meshReferences': self.read(self.BASE+0x4008, 'I')[0], 'matrixCallbacks': self.matrix_calls,
                'allocationBytes': self.allocations}

    def submit(self, classifications, flags=0, mesh_present=True, driver_present=True, gate=True, context_word=0x12340056):
        from scene_sky_mesh import submission_decision
        submission_decision(classifications, flags, mesh_present, driver_present)
        if (type(gate) is not bool or type(context_word) is not int or not 0 <= context_word <= 0xffffffff):
            raise ValueError('Invalid explicit visitor context')
        self.construct(mesh_present); self.registers(); self.classifications = classifications
        self.context_word = context_word; self.submissions = []; self.cleanup = []; self.delegate_calls = 0
        self.write(self.BASE+0x130, 'I', (flags & ~0x18) | (0x18 if gate else 0))
        self.write(self.BASE+0x118, 'Q', self.BASE+0x2000)
        self.write(self.BASE+0x2038, 'Q', self.BASE+0x5000 if driver_present else 0)
        self.write(self.BASE+0x2080, 'Q', self.BASE+0x6000)
        self.write(self.BASE+0x4000, 'Q', self.BASE+0x8000)
        self.write(self.BASE+0x7008, 'I', 1000)
        for slot in (0x20, 0x28, 0x30, 0x60, 0x80, 0xa0):
            self.write(self.BASE+0x8000+slot, 'Q', self.BASE+0x1f000+slot)
        self.write(self.BASE+0x6000, 'Q', self.BASE+0x9000)
        self.write(self.BASE+0x9010, 'Q', self.BASE+0x1f0c0)
        self.set('X1', self.BASE); self.set('X2', context_word)
        self.uc.emu_start(0x13246d8, self.BASE+0x1ff04, count=10000)
        if self.get('PC') != self.BASE+0x1ff00: raise ValueError('Mesh submission exceeded bounds')
        return {'submissions': self.submissions, 'cleanupParts': self.cleanup,
                'returnWord': self.get('W0'), 'delegateCalls': self.delegate_calls}
