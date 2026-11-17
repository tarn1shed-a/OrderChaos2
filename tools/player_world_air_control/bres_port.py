"""Existing original BRES reader on the same physical actor VM, byte I/O only."""
from native_bres_world_bounds_probe import NativeBresWorldBoundsProbe

class SameVMBresPort:
    # Original reader helpers already used by the frozen source probes. The
    # only new lifetime is a separate byte-stream/context carrier in this VM.
    POINTS={0x29f0f0,0x29fbb0,0x3c0fbc,0x11dcc20,0x2a1030,0x29f220,0x2a0180,0x30da84,0x11dcc44,
      0x2a1e50,0x29f5b0,0x30000100,0x30000104,0x30000108,0x29e010,0x29e3c0,0x2a2120,0x29eaf0,
      0x1de8970,0x1de9b88,0x1502ff4,0x1503330,0x1502cf0,0x1502fc0,0x1561f2c,0x1561f34,0x14f40b4,0x14f3e5c,
      0x11ddd2c,0x138aaa8}
    def __init__(self,engine):
        self.engine=engine;self.uc=engine.uc;self.BASE=engine.alloc(0xa000);self.EXIT=engine.EXIT
        self.events=[];self.nodes={};self.flag_writes=[];self.prepared=[]
    def __getattr__(self,name):return getattr(self.engine,name)
    def alloc(self,n):return self.engine.alloc(n)
    c=NativeBresWorldBoundsProbe.c
    source_slice=NativeBresWorldBoundsProbe.source_slice
    regs=NativeBresWorldBoundsProbe.regs
    run=NativeBresWorldBoundsProbe.run
    hook=NativeBresWorldBoundsProbe.hook
    load=NativeBresWorldBoundsProbe.load
