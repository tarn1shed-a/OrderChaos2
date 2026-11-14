"""Original human-female source controllers verified against original CPU.

The unchanged old rest-equals-bind diagnostic is retained. This bounded path
checks every controller against original bone lookup, palette and vertex code
rather than correcting source pose/inverses or loosening the .002 comparison.
"""
import hashlib, math
from bdae_character import aliases
from bdae_skin import multiply
from scene_flags_evidence import literal_nodes
from native_bres_world_bounds_probe import NativeBresWorldBoundsProbe
from tutorial_npc_binding_probe import BindingProbe,verify,world_matrices,host_pose,host_vertices
from tutorial_npc_soldier_probe import strict_original_skin
from character_human_female_probe import MODEL,ANIMATION

PINS = {
 'oc2_human_f_body_01.bdae':'e2533d6704c7bf68de0335d29aac9b072b2ea01f8d52bdb6769189f41b3627c4',
 'animations.bdae':'5c883cd225dbc2391c67b0a2f5cee5edaab72585359432dace49b7341f228d41',
 'hair_human_female_000_003.bdae':'3a811553d06319195e03b5bda9d57b87fbafd77f1c6a355f1e417a89bfe230d0',
 'oc2_human_f_light_industrial_consortium_chest.bdae':'5b8203403b240b181a57abaf70c591419c41ba934c7053d3f1b6c2072b6ef158',
 'oc2_human_f_light_industrial_consortium_hand.bdae':'7f2488ecbf10cc2b1c68d329a67a423e140b9fdc5ef133efcb4de932836e0710',
 'oc2_human_f_light_industrial_consortium_feet.bdae':'769b78b3b3a26855cb792bc8297b46384f96bbdad4b7d85c58e5dec27548eb9b',
}

def source_controller(reader,data,nodes,ordinal):
    node_map=aliases(nodes);count,table=reader.section(188); table += ordinal*24
    if not 0 <= ordinal < count or reader.u(table)!=0 or len(data['meshes'])!=1:raise ValueError('Only one original kind0 controller/mesh is in scope')
    name=reader.string(reader.q(table+8));attachments=[(i,a)for i,n in enumerate(literal_nodes(reader))for a in n['attachments']if a['kind']==2 and a['reference']=='#'+name]
    if name!=data['meshes'][0]['name']+'-skin'or len(attachments)!=1 or attachments[0][1]['reference']!='#'+name:
        raise ValueError('Original controller/mesh attachment differs')
    wrapper=reader.rel(table+16);prefix=reader.u(wrapper+4)&0xffffff;buffer,length=reader.q(wrapper+8),reader.q(wrapper+16)
    if not 1<=prefix<=256:raise ValueError('Uncovered source controller prefix')
    reader.at(buffer,length);body=buffer+(prefix-1)*8
    def bounded(at,size):
        if at<buffer or at+size>buffer+length:raise ValueError('Skin field escapes original removable buffer')
        reader.at(at,size);return at
    bounded(body,184);nb,max_weights=reader.u(body+88),reader.u(body+176)
    if not 0<nb<=128 or prefix!=nb+1 or not 1<=max_weights<=4 or reader.u(body+8)!=nb*16:raise ValueError('Invalid original bone layout')
    shape=list(reader.unpack('16f',body+16));inverse,names=reader.rel(body+12),reader.rel(body+92)
    bounded(inverse,nb*64);bounded(names,nb*8);bones=[];world=world_matrices(nodes)
    for i in range(nb):
        field=names+i*8;pointer=bounded(field+reader.q(field),1);alias=reader.string(pointer);bounded(pointer,len(alias.encode())+1)
        if alias not in node_map:raise ValueError('Original skin bone missing; no identity fallback')
        inv=list(reader.unpack('16f',inverse+i*64))
        if not all(math.isfinite(v)for v in inv+shape):raise ValueError('Non-finite original controller matrix')
        node=node_map[alias];product=multiply(world[node],inv)
        bones.append({'alias':alias,'node':node,'inverse':inv,'restProduct':product,
            'restEqualsBindDiagnosticError':max(abs(a-b)for a,b in zip(product,shape))})
    at,size=reader.q(body+104),reader.q(body+112);vertices=data['meshes'][0]['vertexCount'];stride=(max_weights+1)*4
    if size!=vertices*stride:raise ValueError('Original skin/geometry vertex mismatch')
    reader.at(at,size);indices=[];weights=[];max_sum=0
    for i in range(vertices):
        joints=list(reader.unpack('4B',at+i*stride));values=list(reader.unpack(str(max_weights)+'f',at+i*stride+4));err=abs(sum(values)-1)
        if any(not math.isfinite(v)or v<0 or v>1.00001 for v in values)or err>.002 or any(v>0 and j>=nb for j,v in zip(joints,values)):
            raise ValueError('Invalid original source skin influence')
        indices.append(joints);weights.append(values);max_sum=max(max_sum,err)
    return {'nodes':nodes,'bones':bones,'bindShapeMatrix':shape,'mesh':0,'attachmentNode':attachments[0][0],
        'indices':indices,'weights':weights,'maximumInfluences':max_weights,'maximumWeightSumError':max_sum,
        'normalizationApplied':False,'inverseOrPoseCorrectionApplied':False}

class FemaleControllerProbe(BindingProbe):
    def run(self,address,end=None):
        # Human animation has more properties than the bounded monster files.
        # This only raises the finite instruction budget, never numeric error.
        self.uc.emu_start(address,end or self.EXIT,count=2000000)
        if self.get('PC')!=(end or self.EXIT):raise ValueError('Modular original instruction budget exceeded at '+hex(self.get('PC')))

    def tree(self,node,seen=None):
        seen=set()if seen is None else seen
        if node in seen or len(seen)>len(self.nodes_source):raise ValueError('Source-bounded modular tree exceeded')
        seen.add(node);pointer=self.r(node+0x20,'Q')[0]
        out=[{'nativeProbeAddress':node,'name':self.c(pointer).decode()if pointer else''}]
        head=node+0xf0;child=self.r(head,'Q')[0]
        while child!=head:
            out.extend(self.tree(child-8,seen));child=self.r(child,'Q')[0]
        return out

    def __init__(self,image,reader,base_reader,skin,ordinal):
        verify(image);NativeBresWorldBoundsProbe.__init__(self,image)
        from unicorn import UC_HOOK_CODE
        for at in set([0x29f300,0x2a2430,0x3c0fe8,*image.imports]):
            if at not in(0x29e010,0x29e3c0,0x2a2120,0x29eaf0,0x29f0f0,0x29fbb0,0x29f220,0x2a0180,0x2a1030,0x2a1e50,0x29f5b0):self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=at,end=at)
        self.image=image;self.reader=reader;self.skin=skin;self.nodes_source=skin['nodes'];self.loaded=self.load(base_reader.b);info=self.loaded['info']
        self.pair=self.resource_pair(self.loaded);self.holder=self.alloc(8)
        self.invoke(0x112ba70,X1=self.pair,X8=self.holder);self.root=self.r(self.holder,'Q')[0]
        scene=info+0xe0+self.r(info+0xe0,'i')[0];first=scene+20+self.r(scene+20,'i')[0]
        def empty_attachments(record):
            if self.r(record+80,'I')[0]:return False
            count=self.r(record+72,'I')[0];children=record+76+self.r(record+76,'i')[0]
            return all(empty_attachments(children+i*96)for i in range(count))
        self.assembled_roots=[]
        for i in range(self.r(scene+16,'I')[0]):
            record=first+i*96
            if not empty_attachments(record):continue # Cameras/lights/mesh GPU are not fabricated.
            output=self.alloc(8);self.invoke(0x111dae0,X0=self.pair,X1=self.alloc(16),X2=record,X3=self.holder,X8=output)
            self.invoke(self.r(self.r(self.root,'Q')[0]+0xd0,'Q')[0],X0=self.root,X1=output)
            self.assembled_roots.append(self.c(self.r(record,'Q')[0]).decode())
        self.propagate();tree=self.tree(self.root);self.native_nodes={r['name']:r['nativeProbeAddress']for r in tree}
        for node in self.nodes_source:
            if node['aliases']and node['aliases'][0]in self.native_nodes:
                address=self.native_nodes[node['aliases'][0]]
                for alias in[node['name'],*node['aliases']]:self.native_nodes[alias]=address
        self.piece_loaded=self.load(reader.b);info=self.piece_loaded['info']
        record=info+0xc0+self.r(info+0xc0,'i')[0]+ordinal*24;wrapper=record+16+self.r(record+16,'i')[0]
        obj=self.alloc(16);vt=self.alloc(32);self.w(obj,'Q',vt);self.w(vt+0x10,'Q',0x30000108)
        self.controller_body=self.invoke(0x117c40c,X0=wrapper,X1=obj,W2=0);self.context=self.alloc(0x40);self.w(self.context,'I',1);self.provider=self.alloc(0x50)
        self.invoke(0x11985fc,X0=self.provider,X1=self.controller_body,X2=self.context);self.w(self.provider+0x18,'Q',self.root)
        self.invoke(0x119c21c,X0=self.provider)
        count=self.r(self.controller_body+0x50,'I')[0];vector=self.r(self.context+8,'Q')[0]
        self.bone_pointers=[self.r(vector+i*8,'Q')[0]for i in range(count)]
        if count!=len(skin['bones'])or any(not p for p in self.bone_pointers):raise ValueError('Original bone lookup missing; no identity substitution')
        self.inverse=self.controller_body+4+self.r(self.controller_body+4,'i')[0];self.palette=self.alloc(count*64)
        for i,bone in enumerate(skin['bones']):
            if self.bone_pointers[i]!=self.native_nodes[bone['alias']]+0x28 or list(self.r(self.inverse+i*64,'16f'))!=bone['inverse']:
                raise ValueError('Native named bone/inverse binding differs from literal source')
        self.rest_case=self.palette_case()

def recover_female_skin(image,reader,base_reader,animation_reader,data,nodes):
    for r in (reader,base_reader,animation_reader):
        if r.path.name not in PINS or hashlib.sha256(r.path.read_bytes()).hexdigest()!=PINS[r.path.name]:
            raise ValueError('Unverified original female source pair')
    try:
        rig=strict_original_skin(reader,data,external_nodes=nodes)
        return rig,{'oldStrictDiagnostic':'pass','nativeAlternatePathRequired':False}
    except ValueError as error:
        if str(error)!='Rest skeleton and inverse binds do not reproduce bind shape':raise
    count,table=reader.section(188);mesh_by_name={m['name']+'-skin':i for i,m in enumerate(data['meshes'])}
    if count!=len(data['meshes']):raise ValueError('Unverified partial female skin set')
    clip=animation_reader.parse(['idle'])['clips'][0];range_=next(r for r in animation_reader.ranges()if r['name']=='idle')
    rig={'nodes':nodes,'skins':[],'quaternionConvention':'XYZW','matrixConvention':'column-major','coordinateSystem':'Y_UP'}
    reports=[]
    for ordinal in range(count):
        name=reader.string(reader.q(table+ordinal*24+8))
        if name not in mesh_by_name:raise ValueError('Source female skin name has no exact geometry')
        index=mesh_by_name[name];mesh=data['meshes'][index]
        skin=source_controller(reader,{'meshes':[mesh]},nodes,ordinal)
        probe=FemaleControllerProbe(image,reader,base_reader,skin,ordinal)
        host,_=host_pose(skin)
        rest_error=max(abs(a-b)for actual,want in zip(probe.rest_case,host)for a,b in zip(actual,want))
        if rest_error>.002:raise ValueError('Original female rest palette differs')
        probe.animation(animation_reader);cases=[]
        for ms in (0,500,2000,4000):
            if ms>range_['endMs']-range_['startMs']:continue
            native=probe.pose(range_['startMs']+ms);host,samples=host_pose(skin,clip,ms/1000)
            matrix_error=max(abs(a-b)for actual,want in zip(native['matrices'],host)for a,b in zip(actual,want))
            sample_error=0.
            for row in native['samples']:
                want=samples[(row['node'],row['type'])];error=max(abs(a-b)for a,b in zip(want,row['value']))
                if row['type']==5:error=min(error,max(abs(a+b)for a,b in zip(want,row['value'])))
                sample_error=max(sample_error,error)
            vertices=probe.vertices(mesh['positions']);wanted=host_vertices(skin,mesh['positions'],host)
            vertex_error=max(abs(a-b)for a,b in zip(vertices,wanted))
            if max(matrix_error,sample_error,vertex_error)>.002:
                raise ValueError('Original female CPU comparison failed: '+str((name,ms,matrix_error,sample_error,vertex_error)))
            cases.append({'relativeMs':ms,'maximumPaletteError':matrix_error,'maximumSampleError':sample_error,'maximumVertexError':vertex_error,'vertices':len(vertices)//3})
        rig['skins'].append({'mesh':index,'name':name,'boneNames':[r['alias']for r in skin['bones']],
            'boneNodes':[r['node']for r in skin['bones']],'inverseBindMatrices':[r['inverse']for r in skin['bones']],
            'bindShapeMatrix':skin['bindShapeMatrix'],
            'skinIndices':[j if w else 0 for js,ws in zip(skin['indices'],skin['weights'])for j,w in zip(js,ws+[0.]*(4-len(ws)))],
            'skinWeights':[w for ws in skin['weights']for w in ws+[0.]*(4-len(ws))],
            'verification':{'normalizationApplied':False,'sourceFloatWeightsRetainedAfterStrictValidation':True,
                'inverseOrPoseCorrectionApplied':False,'originalCPUComparisonTolerance':.002,
                'maximumWeightSumError':skin['maximumWeightSumError'],'maximumNativeRestPaletteError':rest_error,
                'maximumNativePaletteError':max(r['maximumPaletteError']for r in cases),'maximumNativeVertexError':max(r['maximumVertexError']for r in cases)}})
        reports.append({'ordinal':ordinal,'skin':name,'sourceRestEqualsBindDiagnosticError':max(r['restEqualsBindDiagnosticError']for r in skin['bones']),
            'oldStrictDiagnostic':'Rest skeleton and inverse binds do not reproduce bind shape','nativeBoneCount':len(skin['bones']),
            'nativeAnimationProperties':len(probe.channels),'nativeRestPaletteError':rest_error,'cases':cases})
    return rig,{'oldStrictDiagnostic':'retained; not a runtime rejection','sourcePoseInversesWeightsUnchanged':True,'controllers':reports,
        'sourceIdleRangeMs':[range_['startMs'],range_['endMs']],'originalCPUExecuted':True,'GPUAndOriginalRuntimeObserved':False}
