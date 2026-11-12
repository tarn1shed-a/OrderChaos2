"""Bounded original entry-position and initial-support CPU execution.

Positions, actor identity, loading-state values and static scene registration are
explicit host fixtures. No original server reply, spawn or Android frame exists
in this probe. Never choose the highest surface as a substitute spawn.
"""
import hashlib
from source_physics import SourcePhysics

PINS={
    0xa0902c:(140,'516fcc49fc74193ce670114787628f2985177bcc10f5c44e3a427ac12107d756'),
    0x9037d4:(236,'b25e335d0e84971cdfee10ef145731e4725e31b7f51c1bf7c2e6eab858ef01ba'),
    0x90c348:(476,'0c86a7a7e904efc973c26fd7d9515a7d3188b10082866fddf412b10e2f85494f'),
    0xa87750:(216,'bb91a2d2abaf7844eb90fd0b6de39ffd37bbdd0fec03a7ab1544ee680681f7f6'),
    0x363b9c:(404,'3790bae647e19b69ac2a6a4b2440b4f2d143e8c92ba15eee7e4d8887b6d148c5'),
}

class NativeMapEntryProbe(SourcePhysics):
    def __init__(self,image):
        from map_streaming_evidence import verify_native
        verify_native(image)
        for at,(size,digest)in PINS.items():
            if hashlib.sha256(image.read(at,size)).hexdigest()!=digest:
                raise ValueError('Original map-entry CPU routine differs')
        rels={r['r_offset']:r['r_addend']for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()}
        for slot,target in {0x68:0xa0902c,0x70:0x904f7c,0x128:0x90c348,0x448:0xa0e3ac}.items():
            if rels.get(0x24228a8+slot)!=target:raise ValueError('Original Hero entry slot differs')
        super().__init__(image)

    def fragment(self,start,stop,regs):
        from unicorn import UC_HOOK_CODE
        ends=[]
        def boundary(uc,at,size,data):
            if at==stop:ends.append(at);self.set('PC',self.EXIT)
        hook=self.uc.hook_add(UC_HOOK_CODE,boundary,begin=stop,end=stop)
        try:self.call(start,regs,limit=2000)
        finally:self.uc.hook_del(hook)
        if ends!=[stop]:raise ValueError('Original entry fragment did not reach its boundary')

    def entry_position(self,point):
        """Execute original Hero setter then original loading-center capture."""
        actor=self.actor('entry-'+str(len(self.actors)),[0,0,0]);a=actor['address']
        position=self.alloc(12);self.w(position,'3f',*point)
        self.call(0xa0902c,{'X0':a,'X1':position})
        self.w(actor['manager']+0x68,'Q',a);self.w(0x2528df8,'Q',actor['manager'])
        # Use the original getter in the captured virtual call, not a host value.
        self.w(self.r(a,'Q')[0]+0x70,'Q',0x904f7c)
        root=self.r(0x2528db0,'Q')[0]
        self.w(root+0x164,'3f',17,19,23);self.w(root+0xb9,'B',0)
        self.fragment(0xa358c0,0xa35900,{'X26':0x2528000})
        return actor,{'suppliedPosition':list(self.r(position,'3f')),
                      'currentPosition':list(self.r(a+0x118,'3f')),
                      'pendingPosition':list(self.r(a+0x1ac,'3f')),
                      'loadingCenter':list(self.r(root+0x164,'3f')),
                      'mapReloadFlag':self.r(root+0xb9,'B')[0]}

    def initial_support(self,actor,stage=(1,4),preserve_pending=False):
        """Run all of 90c348 with explicit stage/optional pending-object input."""
        a=actor['address'];root=self.r(0x2528db0,'Q')[0]
        manager=self.alloc(0x80);state=self.alloc(0x80)
        self.w(root+0x178,'Q',manager);self.w(manager+0x58,'Q',state)
        self.w(state+0x58,'i',stage[0]);self.w(state+0x40,'i',stage[1])
        self.w(a+0x1f4,'i',5)
        if preserve_pending:
            pending=self.alloc(0x80);self.w(pending+0x70,'B',1);self.w(a+0x1e8,'Q',pending)
        self.call(0x90c348,{'X0':a})
        return {'explicitStage':list(stage),'explicitPendingPreservation':preserve_pending,
                'currentPosition':list(self.r(a+0x118,'3f')),
                'pendingPosition':list(self.r(a+0x1ac,'3f')),
                'supportCached':bool(self.r(a+0xc00,'B')[0]),
                'cachedSupport':self.r(a+0xbfc,'f')[0]}
