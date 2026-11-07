"""Read source PHY boxes/cylinders/polyhedra and BDAE geometry-node bindings.

Static decoding only. Native readers a8674c/a85534/a86b3c confirm field order,
axis conversion (x,z,-y), radian angles and four uint16 values per face.
Original face/shape flags are retained; the web query policy is explicit.
"""
import hashlib
import math
import struct
from pathlib import Path
from bdae_skin import compose, multiply

def geometry_transforms(reader, model):
    count, table=reader.section(220)
    if count!=1:raise ValueError('Expected one scene node tree')
    roots,start=reader.u(table+16),reader.rel(table+20)
    result={};seen=set()
    mesh_names={mesh['name']:i for i,mesh in enumerate(model['meshes'])}
    def visit(at,parent):
        reader.at(at,96)
        if at in seen or len(seen)>2048:raise ValueError('Cyclic scene node tree')
        seen.add(at)
        p=list(reader.unpack('3f',at+24));q=list(reader.unpack('4f',at+36));s=list(reader.unpack('3f',at+52))
        if not all(math.isfinite(v) for v in p+q+s) or abs(sum(v*v for v in q)-1)>.002 or any(abs(v)<1e-8 for v in s):raise ValueError('Invalid scene TRS')
        local=compose(p,q,s);world=multiply(parent,local) if parent else local
        n=reader.u(at+80)
        if n>64:raise ValueError('Too many scene node attachments')
        if n:
            desc=reader.rel(at+84);reader.at(desc,n*8)
            for i in range(n):
                record=desc+8*i
                if reader.u(record)!=3:continue
                ref=reader.rel(record+4);reader.at(ref,16)
                name=reader.string(reader.q(ref+8))
                if not name.startswith('#') or name[1:] not in mesh_names:raise ValueError('Unknown explicit geometry binding')
                mesh=mesh_names[name[1:]]
                if mesh in result:raise ValueError('Multiple source instances of a scene mesh require separate geometry')
                result[mesh]={'matrix':world,'node':reader.string(reader.q(at)),'reference':name}
        n=reader.u(at+72)
        if n>1024:raise ValueError('Too many scene children')
        for i in range(n):visit(reader.rel(at+76)+96*i,world)
    if not 0<roots<1024:raise ValueError('Invalid scene root count')
    for i in range(roots):visit(start+96*i,None)
    if set(result)!=set(range(len(model['meshes']))):raise ValueError('Scene mesh lacks an explicit node binding')
    return result

def apply_scene_transforms(reader, model):
    bindings=geometry_transforms(reader,model)
    for index,mesh in enumerate(model['meshes']):mesh['sourceNodeTransform']=bindings[index]
    model['sceneNodes']={'mode':'explicit-type3-geometry-reference','transformsAppliedAtRuntime':True}
    model['warnings']=[warning for warning in model.get('warnings',[]) if not warning.startswith('Static source geometry only;')]
    model['warnings'].append('Source geometry-node transforms are applied; original static material shaders are not evaluated.')
    return model

def decode_phy(raw):
    at=0
    def read(fmt):
        nonlocal at
        size=struct.calcsize('<'+fmt)
        if at+size>len(raw):raise ValueError('Truncated PHY')
        v=struct.unpack_from('<'+fmt,raw,at);at+=size;return v
    def vector(v):return [v[0],v[2],-v[1]]
    count,=read('I')
    if not 0<count<=4096:raise ValueError('Invalid PHY shape count')
    shapes=[]
    for _ in range(count):
        begin=at;kind,flags=read('II')
        if kind not in (3,4,7):raise ValueError('Unsupported PHY shape kind: '+str(kind))
        angle=read('f')[0] if kind!=7 else 0
        center=vector(read('3f'));half=list(read('3f'));half=[half[0],half[2],half[1]]
        if not all(math.isfinite(v) for v in [angle,*center,*half]) or any(v<=0 for v in half):raise ValueError('Invalid PHY shape dimensions')
        record={'kind':{3:'box',4:'cylinder',7:'polyhedron'}[kind],'sourceType':kind,'flags':flags,
                'center':center,'halfExtents':half,'yawRadians':angle,'sourceOffset':begin}
        if kind==7:
            nv,nf=read('2h')
            if not 4<=nv<=32767 or not 4<=nf<=32767:raise ValueError('Invalid PHY polygon counts')
            vertices=[vector(read('3f')) for _ in range(nv)];faces=[list(read('4H')) for _ in range(nf)]
            if any(not math.isfinite(v) for p in vertices for v in p) or any(i>=nv for face in faces for i in face[:3]):raise ValueError('Invalid PHY polygon data')
            record.update(vertices=vertices,faces=faces)
        shapes.append(record)
    if at!=len(raw):raise ValueError('Trailing PHY data')
    return {'shapes':shapes,'sourceSHA256':hashlib.sha256(raw).hexdigest(),'bytesConsumed':at}

def recover_collision(extract, scenery):
    sources={};instances=[]
    for entry in scenery:
        path=entry['model'].removesuffix('.bdae')+'.phy'
        value=extract(path);raw=bytes(value) if isinstance(value,(bytes,bytearray)) else Path(value).read_bytes()
        parsed=decode_phy(raw);sources[path]=parsed
        for instance in entry['instances']:
            instances.append({**instance,'sourcePHY':path})
    door_path='model/scene_generator_temple_000/god_door_01.phy'
    value=extract(door_path);raw=bytes(value) if isinstance(value,(bytes,bytearray)) else Path(value).read_bytes()
    sources[door_path]=decode_phy(raw)
    return {'format':'oc2-scene-collision-v2','sources':sources,'instances':instances,
        'dynamicLab':{'sourcePHY':door_path,'sourceModel':'/assets/models/dynamic-door.json',
            'placement':'local validation fixture; not an original map placement or original door trajectory',
            'logicalPosition':[920,360],'lift':9,'transitionMs':800,'interactDistance':4},
        'query':{'forwardMargin':struct.unpack('<f',struct.pack('<f',.31))[0],
                 'stepProbeCap':.5,'wallNormalYThreshold':.5,'stepProbeMultiplier':3.5},
        'provenance':{'sourceAxes':'x,z,-y; boxes add native Y yaw; AITM instance TRS retained',
            'nativeReaders':['0xa8674c','0xa85534','0xa86b3c'],
            'nativeMotion':['0x90c610','0xa878c0','0xa883a4'],
            'limitations':['Source boxes/cylinders/polyhedra and node bindings recovered. Browser ray/slide queries reimplement a bounded static subset, not the original complete engine.',
                'Runtime-object registration, transform updates, self exclusion and disable-byte filtering are traced. Original actor registration, moving-platform carry, push/crush and vehicle policies are not restored.',
                'Web queries use both face directions, finite ground support and a 0.5 step cap. Complete original slope, terrain contact and exceptional branches remain under study.']}}
