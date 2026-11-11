"""Original part setter/getters and 33faa0 loop, with explicit object fixtures.

No shader/texture/material creation is faked as a native success: 342194 is an
argument-recording boundary, not executed. The scene query supplies one node;
mesh storage/refcounts are explicit arrays, not an original device snapshot.
"""
from unicorn import UC_HOOK_CODE
from native_material_list_probe import NativeMaterialListProbe

class PartLightmapProbe(NativeMaterialListProbe):
    def __init__(self,image):
        from scene_part_lightmaps import verify
        verify(image);self.part_mode=False;super().__init__(image)
        for at in (0x1364464,0x342194,0x30000200,0x30000204):
            self.uc.hook_add(UC_HOOK_CODE,self.part_hook,begin=at,end=at)

    def references(self,raw):
        self.heap=self.BASE+0x10000;self.events=[];self.nodes={};self.prepared=[]
        loaded=self.load(raw,False);root=self.alloc(0x200);res=self.alloc(0x60)
        self.w(root+0x170,'Q',res);self.w(res+0x48,'Q',loaded['main'])
        return self.material_references(root,loaded['info'])

    def part_hook(self,uc,at,size,data):
        if not self.part_mode:raise ValueError('Unexpected part fixture callback')
        if at==0x1364464:
            if self.get('W1')!=0x5f796e61:raise ValueError('Unexpected source node query')
            self.w(self.get('X2'),'3Q',self.node_list,self.node_list+8,self.node_list+8)
        elif at==0x30000200:self.set('W0',0x6d656164)
        elif at==0x30000204:self.w(self.get('X8'),'Q',self.mesh)
        elif at==0x342194:
            mat=self.r(self.get('X2'),'Q')[0];atlas=self.r(self.get('X3'),'Q')[0]
            if mat not in self.materials or atlas not in self.atlases:raise ValueError('Unknown source binding identity')
            self.calls.append({'material':self.materials.index(mat),'binding':self.atlases.index(atlas),'uvTransform':list(self.r(self.get('X4'),'2f')+self.r(self.get('X5'),'2f'))})
        self.set('PC',self.get('X30'))

    def bindings(self,order,bindings):
        if sorted(order)!=list(range(len(order)))or not bindings:raise ValueError('Explicit unique parts and nonempty bindings required')
        owner=self.alloc(0x180);self.mesh=self.alloc(0x80);records=self.alloc(len(order)*24)
        self.w(self.mesh,'Q',0x244e410);self.w(self.mesh+8,'I',1000);self.w(self.mesh+0x40,'2Q',records,records+len(order)*24)
        self.materials=[self.pointer_fixture()for _ in order];holders=[self.alloc(8)for _ in order]
        for i,index in enumerate(order):
            self.w(holders[i],'Q',self.materials[index]);bind=self.alloc(8);self.w(bind,'Q',self.pointer_fixture())
            drawable=self.alloc(0x50);self.w(drawable+8,'I',1000);self.w(records+i*24,'Q',drawable)
            self.regs()
            for k,v in dict(X0=self.mesh,W1=i,X2=holders[i],X3=bind).items():self.set(k,v)
            self.run(0x113235c)
        self.regs();self.set('X0',self.mesh);self.run(0x1132210)
        if self.get('W0')!=len(order):raise ValueError('Original part count differs')
        vt=self.alloc(0x300)+32;node=self.alloc(32);self.w(node,'Q',vt);self.w(node+8,'I',1000)
        self.w(vt+0x1b0,'Q',0x30000200);self.w(vt+0x270,'Q',0x30000204)
        self.node_list=self.alloc(8);self.w(self.node_list,'Q',node);self.w(owner+0x98,'Q',node)
        self.atlases=[self.alloc(0x60)for _ in bindings];ap=self.alloc(8*len(bindings));uv=self.alloc(8*len(bindings));scale=self.alloc(8*len(bindings))
        for i,b in enumerate(bindings):
            self.w(self.atlases[i]+8,'I',1000);self.w(ap+i*8,'Q',self.atlases[i]);self.w(uv+i*8,'2f',*b['uvTransform'][:2]);self.w(scale+i*8,'2f',*b['uvTransform'][2:])
        for offset,ptr in [(0xb8,ap),(0xe8,uv),(0x118,scale)]:self.w(owner+offset,'3Q',ptr,ptr+len(bindings)*8,ptr+len(bindings)*8)
        self.calls=[];self.part_mode=True;self.regs();self.set('X0',owner);self.set('W1',0)
        try:self.run(0x33faa0)
        finally:self.part_mode=False
        expected=[{'material':idx,'binding':i if i<len(bindings)else 0,'uvTransform':bindings[i if i<len(bindings)else 0]['uvTransform']}for i,idx in enumerate(order)]
        if self.calls!=expected:raise ValueError('Original part loop differs from recovered binding rule')
        return {'nativeCPU':True,'setterAndGettersExecuted':True,'bindingLoopExecuted':True,'parameterSetterExecuted':False,'GPUCreated':False,'sceneProvider':'one explicit node fixture','calls':self.calls}
