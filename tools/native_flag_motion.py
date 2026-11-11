"""Bounded original flag bone assembly, channel sampling and palette execution.

Stream/allocator/string/lock/libm services are host interfaces. Source loader,
property selection, sampler, node setters/world propagation and bone lookup/matrix
writer execute the pinned original ARM64. No mesh GPU success is fabricated.
"""
import hashlib,math,struct
from native_bres_world_bounds_probe import NativeBresWorldBoundsProbe
from scene_flags_evidence import literal_nodes,controller_evidence,animation_evidence


class NativeFlagMotion(NativeBresWorldBoundsProbe):
    def __init__(self,image,reader):
        super().__init__(image)
        from unicorn import UC_HOOK_CODE
        for a in set([0x29f300,0x2a2430,0x3c0fe8,*image.imports]):
            if a not in (0x29e010,0x29e3c0,0x2a2120,0x29eaf0,0x29f0f0,0x29fbb0,0x29f220,0x2a0180,0x2a1030,0x2a1e50,0x29f5b0):
                self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=a,end=a)
        self.image=image;self.reader=reader
        # The source .init_array constructor builds the compatibility bitmap
        # and publishes its address. Without this, base-zero emulation could
        # misread ELF header bytes through a null bitmap pointer. Never use an
        # uninitialized table as evidence of property merging/optimization.
        self.regs();self.uc.emu_start(0x119bf2c,self.EXIT,count=500000)
        if self.get('PC')!=self.EXIT:raise ValueError('Original compatibility bootstrap exceeded its bound')
        self.regs();self.set('X20',0x25da730);self.run(0x2ce3d0,0x2ce3ec)
        if self.r(0x25bb068,'Q')[0]!=0x25da770 or self.r(0x25da770+24,'Q')[0]&(1<<10):raise ValueError('Original property compatibility initialization failed')
        self.loaded=self.load(reader.b);info=self.loaded['info']
        self.nodes_source=literal_nodes(reader);self.skin=controller_evidence(reader,reader.parse(),self.nodes_source)
        self.animation=animation_evidence(reader)
        self.pair=self.alloc(16);res=self.alloc(0x100);fac=self.alloc(16);self.holder=self.alloc(8)
        self.w(self.pair,'2Q',res,fac);self.w(res+8,'I',10000);self.w(res+0x48,'Q',self.loaded['main']);self.w(fac,'Q',0x2416430)
        self.invoke(0x112ba70,X1=self.pair,X8=self.holder);self.root=self.r(self.holder,'Q')[0]
        scene=info+0xe0+self.r(info+0xe0,'i')[0];first=scene+20+self.r(scene+20,'i')[0]
        # Scope is the unchanged original bone subtrees. The mesh and light
        # attachments are NOT claimed constructed by this CPU experiment.
        for i in range(self.r(scene+16,'I')[0]):
            rec=first+i*96;name=self.c(self.r(rec,'Q')[0]).decode()
            if not name.startswith('Bone'):continue
            out=self.alloc(8)
            self.invoke(0x111dae0,X0=self.pair,X1=self.alloc(16),X2=rec,X3=self.holder,X8=out)
            self.invoke(self.r(self.r(self.root,'Q')[0]+0xd0,'Q')[0],X0=self.root,X1=out)
        self.propagate();self.native_nodes={n['name']:n['nativeProbeAddress']for n in self.tree(self.root)}
        for n in self.nodes_source:
            if n['aliases']and n['aliases'][0]in self.native_nodes:
                address=self.native_nodes[n['aliases'][0]]
                for alias in[n['name'],*n['aliases']]:self.native_nodes[alias]=address
        self.manager=self.alloc(0x100);self.invoke(0x1103d9c,X0=self.manager)
        self.invoke(0x1106f94,X0=self.manager,X1=self.pair);self.invoke(0x110749c,X0=self.manager)
        # Read the actual ORIGINAL selected properties after source bootstrap.
        self.channels=[];count=self.r(self.manager+0x40,'I')[0];start=self.r(self.manager+0x98,'Q')[0]
        objects=self.r(self.manager+0x28,'Q')[0];targets=self.r(self.manager+0x10,'Q')[0]
        raw_count,raw_table=reader.section(64)
        for i in range(count):
            kind,rec=self.r(start+i*16,'2Q')
            if kind!=2:raise ValueError('Flag source property is not the verified sampled route')
            target=self.r(targets+i*8,'Q')[0];name=self.c(self.r(target,'Q')[0]).decode();typ=self.r(target+8,'I')[0]
            matches=[(j,c)for j,c in enumerate(self.animation['channels'])if c['target']==name and c['targetType']==typ]
            if len(matches)!=1 or typ not in(1,5,10):raise ValueError('Unverified original flag property')
            j,ch=matches[0];node=next((n for n in self.nodes_source if n['name']==name),None)
            if not node or not node['aliases']or node['aliases'][0]not in self.native_nodes:raise ValueError('Missing original flag animation target')
            obj=self.r(objects+i*8,'Q')[0]
            self.channels.append({'sourceIndex':j,'source':ch,'record':rec,'object':obj,'targetNode':self.native_nodes[node['aliases'][0]],'state':self.alloc(16),'index':self.alloc(4),'output':self.alloc(16)})
        # Source animation removable buffer: actual original reader, not a
        # replacement source table or invented pointer layout.
        seg=info+0x4c+self.r(info+0x4c,'i')[0];reader_obj=self.alloc(16);vt=self.alloc(32)
        self.w(reader_obj,'Q',vt);self.w(vt+0x10,'Q',0x30000108)
        self.segment=self.invoke(0x117c40c,X0=seg+16,X1=reader_obj,W2=0)
        for c in self.channels:
            c['context']=self.alloc(24);self.w(c['context'],'3Q',c['record'],self.segment,c['state'])
        cnt,rel=self.r(info+0xbc,'Ii');record=info+0xc0+rel
        if cnt!=1 or self.r(record,'I')[0]!=0:raise ValueError('Expected original kind0 flag controller')
        wr=record+16+self.r(record+16,'i')[0];body=self.invoke(0x117c40c,X0=wr,X1=reader_obj,W2=0)
        context=self.alloc(0x40);self.w(context,'I',1);provider=self.alloc(0x50)
        self.invoke(0x11985fc,X0=provider,X1=body,X2=context);self.w(provider+0x18,'Q',self.root)
        self.invoke(0x119c21c,X0=provider)
        count=self.r(body+0x50,'I')[0];v=self.r(context+8,'Q')[0]
        self.bone_pointers=[self.r(v+i*8,'Q')[0]for i in range(count)]
        if any(not x for x in self.bone_pointers)or count!=len(self.skin['bones']):raise ValueError('Original flag bone lookup failed; no identity fallback')
        self.inverse=body+4+self.r(body+4,'i')[0];self.palette=self.alloc(count*64)
        for i,bone in enumerate(self.skin['bones']):
            if list(self.r(self.inverse+i*64,'16f'))!=bone['inverseBindMatrix']:raise ValueError('Original relocated inverse bind differs')
            if self.bone_pointers[i]!=self.native_nodes[bone['alias']]+0x28:raise ValueError('Bone matrix lookup did not resolve the original world matrix')
        self.clock=self.alloc(0x70);self.invoke(0x1195f3c,X0=self.clock)
        n,t=reader.section(84);range_source=self.alloc(32)
        # Exact source range payload; only the name pointer is unused by this
        # clock entry. The original range setter supplies start/end/time0.
        if n!=1:raise ValueError('Expected one original flag range')
        self.w(range_source,'Ii',1,4);self.uc.mem_write(range_source+8,reader.b[t:t+24])
        self.invoke(0x1196824,X0=self.clock,X1=range_source)
        if self.r(self.clock+0x29,'B')[0]!=1 or self.r(self.clock+0x34,'f')[0]!=1 or self.r(self.clock+0x20,'2f')!=(0,4000):raise ValueError('Original fresh flag clock differs')

    def hook(self,uc,a,n,d):
        if a==0x29f300:self.set('W0',1)
        elif a==0x2a2430:self.w(self.get('X0'),'B',1)
        elif a==0x3c0fe8:pass
        elif self.im.imports.get(a)=='strcasecmp':
            x,y=self.c(self.get('X0')).lower(),self.c(self.get('X1')).lower();self.set('W0',((x>y)-(x<y))&0xffffffff)
        elif self.im.imports.get(a)in('sinf','acosf','sqrtf','fmodf','fmod'):
            name=self.im.imports[a];bits='d'if name=='fmod'else'f';reg='D'if bits=='d'else'S';fmt='Q'if bits=='d'else'I'
            values=[struct.unpack('<'+bits,struct.pack('<'+fmt,self.get(reg+str(i))))[0]for i in range(2 if name.startswith('fmod')else 1)]
            f=math.fmod if name.startswith('fmod')else getattr(math,name[:-1]);value=f(*values)
            self.set(reg+'0',struct.unpack('<'+fmt,struct.pack('<'+bits,value))[0])
        else:return super().hook(uc,a,n,d)
        self.set('PC',self.get('X30'))

    def invoke(self,a,*,time=None,**regs):
        self.regs()
        for k,v in regs.items():self.set(k,v)
        if time is not None:self.set('S0',struct.unpack('<I',struct.pack('<f',time))[0])
        self.run(a);return self.get('X0')

    def propagate(self):self.invoke(0x1362320,X0=self.root,W1=1,W2=1)

    def pose(self,time):
        sampled=[]
        for c in self.channels:
            self.invoke(0x1109aec,time=time,X0=c['object'],X1=c['context'],X2=c['output'],X3=c['index'],W4=1)
            values=list(self.r(c['output'],'4f'if c['source']['targetType']==5 else'3f'))
            setter=self.r(self.r(c['object'],'Q')[0]+0x98,'Q')[0]
            self.invoke(setter,X0=c['object'],X1=c['output'],X2=c['targetNode'])
            sampled.append({'sourceIndex':c['sourceIndex'],'value':values})
        self.propagate()
        for i,p in enumerate(self.bone_pointers):self.invoke(0x119935c,X0=self.palette+i*64,X1=p,X2=self.inverse+i*64)
        return {'timeMs':time,'channels':sampled,'boneMatrices':list(self.r(self.palette,str(len(self.bone_pointers)*16)+'f'))}

    def tick(self,dt):
        if not math.isfinite(dt)or dt<0:raise ValueError('Nonnegative flag clock delta required')
        self.invoke(0x11962c0,time=dt,X0=self.clock)
        return {'dt':dt,'timeMs':self.r(self.clock+8,'f')[0],'crossedEnd':bool(self.r(self.clock+0x2a,'B')[0])}

    def vertices(self,positions):
        """Original affine-weight scatter on the real source vertex influences.

        Output is source-model space. The caller chooses position-only streams;
        this does not claim the original GPU or its full normal/tangent path.
        """
        n=len(positions)//3;source=self.alloc(n*12);dest=self.alloc(n*12)
        self.w(source,str(n*3)+'f',*positions);src_desc=self.alloc(16);dst_desc=self.alloc(16)
        self.w(src_desc,'IIQ',12,0,source);self.w(dst_desc,'IIQ',12,0,dest)
        for bone in range(len(self.bone_pointers)):
            influences=[(v,i)for i,(indices,weights)in enumerate(zip(self.skin['literalIndices4'],self.skin['literalWeights2']))for j,v in enumerate(weights)if v>0 and indices[j]==bone]
            if not influences:continue
            table=self.alloc(len(influences)*8)
            for k,(weight,index)in enumerate(influences):self.w(table+k*8,'fHH',weight,index,0)
            self.invoke(0x119bd7c,W0=len(influences),X1=self.palette+bone*64,X2=table,W3=1,X4=src_desc,X5=dst_desc)
        return list(self.r(dest,str(n*3)+'f'))
