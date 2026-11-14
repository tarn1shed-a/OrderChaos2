"""Original867/971 skeleton, named bone lookup and palette comparisons.

The frozen rest-equals-bind reader remains unchanged. This branch requires
typed source controllers and original CPU matrix/vertex agreement instead of
changing source poses/inverses or relaxing its diagnostic threshold.
"""
import copy
import hashlib
import math
import struct

from bdae_skin import compose,multiply
from bdae_character import aliases
from bdae_animation import BDAEAnimation,sample
from scene_flags_evidence import literal_nodes
from native_flag_motion import NativeFlagMotion
from native_bres_world_bounds_probe import NativeBresWorldBoundsProbe

FORMAT='oc2-tutorial-npc-binding-native-v1'
ASSETS={
    867:{'model':'model/npc/creature/elemental/water_elemental_high/water_elemental_hi.bdae',
        'outer':'0f9ee656fa3d6ff77b7955d98ba27da5baeff5da335e1812df638f4d89416962',
        'inner':'ebce882cf994944b66df518158d1a6c4d9486840d3642c1e6c5412b262ba1320',
        'animation':'952897d5b23edb52353196e5d8486c072af0100e246de32cf8dba3d457f1e144'},
    971:{'model':'model/npc/creature/demon/powerful_demon/powerful_demon.bdae',
        'outer':'1e802f723c8a10e89d5881c823f8b7f476f42640968c057669ad8ee6f6dcf8ba',
        'inner':'5b7468f257c8b6c89f242d3b466e86e8143cbd22ab138d3cc0a223e6cc929c6a',
        'animation':'ba381cc3a46c9170119d1a18fa33b6c8cedebed859d531f66caf9200f2d978bb'},
}
PINS={
    0x1198c40:(1820,'71343ce79849bce0352efa06176a33bfef2f08669967c915161e171f1644919a'),
    0x11985fc:(44,'6f0cab5ad28febc95189f8759e487bce4b0fa8e08a27cfc9dfd851dcce8c43f6'),
    0x119c21c:(708,'bfac5502dd5d6f32c448bd06e84ab777e2bf6b70e7efb504c4791de181071437'),
    0x119935c:(576,'64ab7ac83d1a2eb9b5e8e4e07033ccc52270a1ec07140daff3cc43729d670c7c'),
    0x119bd7c:(432,'ae9d8e3800415dda3615701ac44b39df9312eeedda8dbd335ff6647f25ae3232'),
    0x1109aec:(212,'ddc6dc050e1247a6452fd57356b9d2121b120235af1de0ae4e0c143cab78e588'),
    0x111dae0:(12352,'f17215c1c77acee17978266577a9fcf7ebe0e86bfc22ab0dbd06a1120db6ffa6'),
    0x1362320:(168,'46a9ae0b2b5be057fcdc1982335c153bd0b14437b5c2411cb96585151ed39ce5'),
}


def verify(image):
    for at,(size,digest)in PINS.items():
        if hashlib.sha256(image.read(at,size)).hexdigest()!=digest:raise ValueError('Original binding routine changed')


def world_matrices(nodes):
    world=[]
    for i,node in enumerate(nodes):
        if not -1<=node['parent']<i:raise ValueError('Source node parent order differs')
        local=compose(node['position'],node['quaternion'],node['scale'])
        world.append(local if node['parent']<0 else multiply(world[node['parent']],local))
    return world


def controller(reader,data):
    nodes=literal_nodes(reader);node_map=aliases(nodes);count,table=reader.section(188)
    if count!=1 or reader.u(table)!=0 or len(data['meshes'])!=1:raise ValueError('Only one original kind0 controller/mesh is in scope')
    name=reader.string(reader.q(table+8));attachments=[(i,a)for i,n in enumerate(nodes)for a in n['attachments']if a['kind']==2]
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


class BindingProbe(NativeFlagMotion):
    def __init__(self,image,reader,skin):
        verify(image);NativeBresWorldBoundsProbe.__init__(self,image)
        from unicorn import UC_HOOK_CODE
        for at in set([0x29f300,0x2a2430,0x3c0fe8,*image.imports]):
            if at not in(0x29e010,0x29e3c0,0x2a2120,0x29eaf0,0x29f0f0,0x29fbb0,0x29f220,0x2a0180,0x2a1030,0x2a1e50,0x29f5b0):self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=at,end=at)
        self.image=image;self.reader=reader;self.skin=skin;self.nodes_source=skin['nodes'];self.loaded=self.load(reader.b);info=self.loaded['info']
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
        record=info+0xc0+self.r(info+0xc0,'i')[0];wrapper=record+16+self.r(record+16,'i')[0]
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

    def resource_pair(self,loaded):
        pair,res,fac=self.alloc(16),self.alloc(0x100),self.alloc(16)
        self.w(pair,'2Q',res,fac);self.w(res+8,'I',10000);self.w(res+0x48,'Q',loaded['main']);self.w(fac,'Q',0x2416430);return pair

    def palette_case(self):
        # Execute the actual caller loop over provider context bone pointers
        # and controller inverse matrices; graphics buffer allocation precedes
        # this fragment and is supplied as an explicitly bounded output span.
        self.regs();self.set('X23',self.provider);self.set('X26',self.palette);self.run(0x11990b8,0x119912c)
        return [list(self.r(self.palette+i*64,'16f'))for i in range(len(self.bone_pointers))]

    def animation(self,reader):
        self.regs();self.uc.emu_start(0x119bf2c,self.EXIT,count=500000)
        if self.get('PC')!=self.EXIT:raise ValueError('Original compatibility bootstrap exceeded bound')
        self.regs();self.set('X20',0x25da730);self.run(0x2ce3d0,0x2ce3ec)
        self.animation_reader=reader;self.animation_loaded=self.load(reader.b);info=self.animation_loaded['info'];pair=self.resource_pair(self.animation_loaded)
        manager=self.alloc(0x100);self.invoke(0x1103d9c,X0=manager);self.invoke(0x1106f94,X0=manager,X1=pair);self.invoke(0x110749c,X0=manager)
        count=self.r(manager+0x40,'I')[0];start=self.r(manager+0x98,'Q')[0];objects=self.r(manager+0x28,'Q')[0];targets=self.r(manager+0x10,'Q')[0]
        if count!=len(reader.channels()):raise ValueError('Original selected property count differs')
        self.channels=[]
        for i in range(count):
            kind,record=self.r(start+i*16,'2Q');target=self.r(targets+i*8,'Q')[0];name=self.c(self.r(target,'Q')[0]).decode();typ=self.r(target+8,'I')[0]
            if kind!=2 or typ not in(1,5,10)or name not in self.native_nodes:raise ValueError('Uncovered original animation property/target')
            self.channels.append({'record':record,'node':name,'type':typ,'object':self.r(objects+i*8,'Q')[0]})
        self.segment_table=info+0x4c+self.r(info+0x4c,'i')[0];self.segments=reader.segments();self.segment_cache={}

    def pose(self,absolute_ms):
        indexes=[i for i,s in enumerate(self.segments)if s['startMs']<=absolute_ms<=s['endMs']]
        if not indexes:raise ValueError('Original segment does not cover sample')
        index=indexes[-1]
        if index not in self.segment_cache:
            obj,vt=self.alloc(16),self.alloc(32);self.w(obj,'Q',vt);self.w(vt+0x10,'Q',0x30000108)
            self.segment_cache[index]=self.invoke(0x117c40c,X0=self.segment_table+16+index*40,X1=obj,W2=0)
        samples=[]
        for ch in self.channels:
            context,state,output,sample_index=self.alloc(24),self.alloc(16),self.alloc(16),self.alloc(4)
            self.w(context,'3Q',ch['record'],self.segment_cache[index],state)
            self.invoke(0x1109aec,time=absolute_ms,X0=ch['object'],X1=context,X2=output,X3=sample_index,W4=1)
            values=list(self.r(output,'4f'if ch['type']==5 else'3f'))
            setter=self.r(self.r(ch['object'],'Q')[0]+0x98,'Q')[0]
            self.invoke(setter,X0=ch['object'],X1=output,X2=self.native_nodes[ch['node']])
            samples.append({'node':ch['node'],'type':ch['type'],'value':values})
        self.propagate();return {'absoluteMs':absolute_ms,'samples':samples,'matrices':self.palette_case()}

    def vertices(self,positions):
        n=len(positions)//3;source,dest=self.alloc(n*12),self.alloc(n*12);self.w(source,str(n*3)+'f',*positions)
        src,dst=self.alloc(16),self.alloc(16);self.w(src,'IIQ',12,0,source);self.w(dst,'IIQ',12,0,dest)
        for bone in range(len(self.bone_pointers)):
            influences=[(weight,i)for i,(joints,values)in enumerate(zip(self.skin['indices'],self.skin['weights']))for joint,weight in zip(joints,values)if weight>0 and joint==bone]
            if not influences:continue
            table=self.alloc(len(influences)*8)
            for i,(weight,index)in enumerate(influences):self.w(table+i*8,'fHH',weight,index,0)
            self.invoke(0x119bd7c,W0=len(influences),X1=self.palette+bone*64,X2=table,W3=1,X4=src,X5=dst)
        return list(self.r(dest,str(n*3)+'f'))


def host_pose(skin,clip=None,time=0):
    nodes=copy.deepcopy(skin['nodes']);by_name=aliases(nodes);samples={}
    if clip:
        for track in clip['tracks']:
            width=4 if track['type']=='quaternion'else 3
            rows=[track['values'][i:i+width]for i in range(0,len(track['values']),width)]
            value=list(sample(track['times'],rows,time,track['type']=='quaternion'))
            nodes[by_name[track['node']]][track['type']]=value
            samples[(track['node'],{'position':1,'quaternion':5,'scale':10}[track['type']])]=value
    world=world_matrices(nodes)
    return [multiply(world[bone['node']],bone['inverse'])for bone in skin['bones']],samples


def host_vertices(skin,positions,matrices):
    result=[]
    for vertex,(joints,weights)in enumerate(zip(skin['indices'],skin['weights'])):
        value=positions[vertex*3:vertex*3+3];out=[0.,0.,0.]
        for joint,weight in zip(joints,weights):
            if not weight:continue
            matrix=matrices[joint]
            for row in range(3):out[row]+=weight*(sum(matrix[column*4+row]*value[column]for column in range(3))+matrix[12+row])
        result.extend(out)
    return result


def recover_model(image,reader,animation_reader,data):
    from bdae_skin import recover_skin
    matches=[entry for entry,record in ASSETS.items()if hashlib.sha256(reader.b).hexdigest()==record['inner']and hashlib.sha256(reader.path.read_bytes()).hexdigest()==record['outer']and hashlib.sha256(animation_reader.b).hexdigest()==record['animation']]
    if len(matches)!=1:raise ValueError('Unverified original model/animation pair')
    skin=controller(reader,data)
    try:recover_skin(reader,data)
    except ValueError as error:
        diagnostic=str(error)
        if diagnostic!='Rest skeleton and inverse binds do not reproduce bind shape':raise
    else:raise ValueError('This bounded branch expects the known frozen-reader rest diagnostic')
    probe=BindingProbe(image,reader,skin);host_rest,_=host_pose(skin)
    rest_error=max(abs(a-b)for native,host in zip(probe.rest_case,host_rest)for a,b in zip(native,host))
    if rest_error>.002:raise ValueError('Native assembled rest palette differs; no tolerance relaxation')
    decoded=animation_reader.parse(['idle']);clip=decoded['clips'][0];range_=next(r for r in animation_reader.ranges()if r['name']=='idle')
    if range_['startMs']!=22000 or range_['endMs']!=24000:raise ValueError('Unexpected original idle range')
    probe.animation(animation_reader);cases=[]
    for ms in[0,123,500,1000,1555,2000]:
        native=probe.pose(range_['startMs']+ms);host,samples=host_pose(skin,clip,ms/1000)
        matrix_error=max(abs(a-b)for actual,want in zip(native['matrices'],host)for a,b in zip(actual,want));sample_error=0.
        for row in native['samples']:
            want=samples[(row['node'],row['type'])];error=max(abs(a-b)for a,b in zip(want,row['value']))
            if row['type']==5:error=min(error,max(abs(a+b)for a,b in zip(want,row['value'])))
            sample_error=max(sample_error,error)
        vertices=probe.vertices(data['meshes'][0]['positions']);wanted=host_vertices(skin,data['meshes'][0]['positions'],host)
        vertex_error=max(abs(a-b)for a,b in zip(vertices,wanted))
        if max(matrix_error,sample_error,vertex_error)>.002:
            raise ValueError('Original sampled pose/palette/vertices differ; no correction or tolerance relaxation: '+str((ms,matrix_error,sample_error,vertex_error)))
        cases.append({**native,'relativeMs':ms,'nativeVertices':vertices,'maximumSampleError':sample_error,
            'maximumPaletteError':matrix_error,'maximumVertexError':vertex_error,
            'sourceBounds':[[min(vertices[a::3])for a in range(3)],[max(vertices[a::3])for a in range(3)]]})
    rig={'nodes':skin['nodes'],'skins':[{'mesh':0,'name':data['meshes'][0]['name']+'-skin',
        'boneNames':[r['alias']for r in skin['bones']],'boneNodes':[r['node']for r in skin['bones']],
        'inverseBindMatrices':[r['inverse']for r in skin['bones']],'bindShapeMatrix':skin['bindShapeMatrix'],
        'skinIndices':[j if w else 0 for indices,weights in zip(skin['indices'],skin['weights'])for j,w in zip(indices,weights+[0.]*(4-len(weights)))],
        'skinWeights':[w for values in skin['weights']for w in values+[0.]*(4-len(values))],
        'verification':{'originalCPUComparisonTolerance':.002,'maximumWeightSumError':skin['maximumWeightSumError'],
            'normalizationApplied':False,'inverseOrPoseCorrectionApplied':False,
            'restEqualsBindDiagnosticError':max(r['restEqualsBindDiagnosticError']for r in skin['bones']),
            'maximumNativeRestPaletteError':rest_error,'maximumNativePaletteError':max(r['maximumPaletteError']for r in cases),
            'maximumNativeVertexError':max(r['maximumVertexError']for r in cases)}}]}
    node_map=aliases(rig['nodes']);bound_clip={**clip,'tracks':[{**r,'node':node_map[r['node']]}for r in clip['tracks']]}
    return rig,[bound_clip],{'format':FORMAT,'frozenReaderDiagnostic':diagnostic,'frozenReaderThresholdUnchanged':.002,
        'nativeRestPalette':probe.rest_case,'maximumNativeRestPaletteError':rest_error,
        'restEqualsBindMaximumDiagnosticError':max(r['restEqualsBindDiagnosticError']for r in skin['bones']),
        'nativeBoneCount':len(skin['bones']),'nativeSelectedProperties':len(probe.channels),'nativeCases':cases,
        'originalCPU':'111dae0 nodes;119c21c named lookup;1109aec + original property setters;1362320 propagate;11990b8..119912c real palette loop;119bd7c affine weight scatter',
        'sourceNodeTRSInverseWeightsPreserved':True,'additionalBindShapeOrCorrectionApplied':False,
        'hostBoundaries':['Original stream/allocator/string/lock/libm interfaces','Bounded output span after graphics allocation','Independent browser matrices, skeleton/GPU submission, material rewrite, camera and loop clock'],
        'originalFullGPUOrActivityObserved':False}
