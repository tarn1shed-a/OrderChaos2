"""Decode the observed DNAV v4 ABI, verified against native addTile 15ed978.

This is not the current upstream v7 ABI: header=96, poly=32, link=12,
detail=8 (four ushort fields), BV=16. Original navigation bytes stay local.
"""
import hashlib
import math
import struct

def decode_nav(data):
    if len(data)<96:raise ValueError('Truncated navigation header')
    magic,version,x,z,user,*counts=struct.unpack_from('<IIii10I',data)
    if magic!=0x444e4156 or version!=4:raise ValueError('Unsupported navigation build')
    polygons,vertices,links,details,detail_vertices,triangles,bv,off_mesh,off_base=counts
    if not (0<polygons<=100000 and 0<vertices<=65535 and details==polygons and off_mesh==0 and off_base==polygons):
        raise ValueError('Unsupported navigation counts/off-mesh branch')
    agent_height,agent_radius,climb,*bounds,quant=struct.unpack_from('<10f',data,56)
    if not all(math.isfinite(v) for v in [agent_height,agent_radius,climb,*bounds,quant]) or min(agent_height,agent_radius,climb,quant)<=0:
        raise ValueError('Invalid navigation bounds/agent')
    if any(bounds[i]>bounds[i+3] for i in range(3)):raise ValueError('Inverted navigation bounds')
    at=96;sections={}
    for name,count,stride in [('vertices',vertices,12),('polygons',polygons,32),('links',links,12),('details',details,8),
                              ('detailVertices',detail_vertices,12),('triangles',triangles,4),('bvNodes',bv,16)]:
        sections[name]=(at,at+count*stride);at+=count*stride
    if at!=len(data):raise ValueError('Navigation section extents differ from payload')
    def points(name):
        a,b=sections[name];result=[list(v) for v in struct.iter_unpack('<3f',data[a:b])]
        if any(not math.isfinite(n) for v in result for n in v):raise ValueError('Non-finite navigation vertex')
        if any(not bounds[i]-1e-3<=v[i]<=bounds[i+3]+1e-3 for v in result for i in range(3)):
            raise ValueError('Navigation vertex outside source tile bounds')
        return result
    vv=points('vertices');dv=points('detailVertices');polys=[]
    for i in range(polygons):
        row=struct.unpack_from('<I12HHBB',data,sections['polygons'][0]+i*32)
        count=row[-2];indices=list(row[1:7])[:count];neighbours=list(row[7:13])[:count]
        if not 3<=count<=6 or len(set(indices))!=count or any(v>=vertices for v in indices):raise ValueError('Invalid navigation polygon indices')
        if row[-1]>>6 or row[-3]!=1 or row[-1]!=0:raise ValueError('Untraced navigation polygon type/flags/area')
        if any(n and (n&0x8000 and n not in (0x8000,0x8002,0x8004,0x8006) or not n&0x8000 and n>polygons) for n in neighbours):
            raise ValueError('Invalid navigation adjacency')
        # Source detail record is 4H, not the upstream v7 uint/uint/byte ABI.
        vb,vc,tb,tc=struct.unpack_from('<4H',data,sections['details'][0]+i*8)
        if vb+vc>detail_vertices or tb+tc>triangles or tc==0:raise ValueError('Invalid navigation detail spans')
        for j in range(tb,tb+tc):
            tri=data[sections['triangles'][0]+j*4:sections['triangles'][0]+j*4+4]
            if any(v>=count+vc for v in tri[:3]):raise ValueError('Navigation detail triangle index outside polygon')
        polys.append({'vertices':indices,'neighbours':neighbours,'flags':row[-3],'area':row[-1],
                      'detail':{'vertexBase':vb,'vertexCount':vc,'triangleBase':tb,'triangleCount':tc}})
    return {'tile':[x,z],'userId':user,'vertices':vv,'polygons':polys,'detailVertices':dv,
        'detailTriangles':[list(v) for v in struct.iter_unpack('<4B',data[slice(*sections['triangles'])])],
        'agent':{'height':agent_height,'radius':agent_radius,'climb':climb},'bounds':{'min':bounds[:3],'max':bounds[3:]},
        'verification':{'sourceSHA256':hashlib.sha256(data).hexdigest(),'bytesConsumed':at,'fileSize':len(data),
                        'counts':dict(zip(['polygons','vertices','links','details','detailVertices','triangles','bvNodes','offMesh','offBase'],counts)),
                        'sections':{k:list(v) for k,v in sections.items()}}}

def build_graph(tiles):
    """Use explicit internal neighbours; pair opposite source boundary portals.

    Boundary overlap and height tolerance are a bounded web stitcher; no links
    are invented for edges whose neighbour word is zero.
    """
    nodes=[];lookup={};externals=[]
    for tile in tiles:
        key=tuple(tile['tile'])
        if key in lookup:raise ValueError('Duplicate navigation tile')
        lookup[key]=len(nodes)
        for index,poly in enumerate(tile['polygons']):
            points=[tile['vertices'][i] for i in poly['vertices']]
            nodes.append({'tile':list(key),'sourceIndex':index,'vertices':points,'flags':poly['flags'],'area':poly['area'],
                'center':[sum(v[k] for v in points)/len(points) for k in range(3)],'edges':[]})
    for tile in tiles:
        base=lookup[tuple(tile['tile'])]
        for i,poly in enumerate(tile['polygons']):
            node=nodes[base+i];vs=node['vertices']
            for edge,n in enumerate(poly['neighbours']):
                a,b=vs[edge],vs[(edge+1)%len(vs)]
                if n&0x8000:externals.append((base+i,n&7,a,b,tile['agent']['climb']))
                elif n:
                    to=base+n-1;other=nodes[to]
                    if not any(all(abs(a[k]-d[k])<1e-3 and abs(b[k]-c[k])<1e-3 for k in range(3)) for c,d in zip(other['vertices'],other['vertices'][1:]+other['vertices'][:1])):
                        raise ValueError('Source internal neighbour does not share reversed edge')
                    node['edges'].append({'to':to,'portal':[a,b],'source':'internal'})
    directions={0:(1,0),2:(0,1),4:(-1,0),6:(0,-1)}
    for i,side,a,b,climb in externals:
        axis=2 if side in (0,4) else 0;fixed=0 if axis==2 else 2;dx,dz=directions[side];tile=nodes[i]['tile']
        for j,other,c,d,other_climb in externals:
            if other!=(side+4)%8 or nodes[j]['tile']!=[tile[0]+dx,tile[1]+dz] or abs(a[fixed]-c[fixed])>1e-3:continue
            lo=max(min(a[axis],b[axis]),min(c[axis],d[axis]));hi=min(max(a[axis],b[axis]),max(c[axis],d[axis]))
            if hi-lo<=.02:continue
            def sample(v,w,t):
                f=(t-v[axis])/(w[axis]-v[axis]);return [v[k]+(w[k]-v[k])*f for k in range(3)]
            aa,bb=sample(a,b,lo),sample(a,b,hi);cc,dd=sample(c,d,lo),sample(c,d,hi)
            if min(abs(aa[1]-cc[1]),abs(bb[1]-dd[1]))>2*min(climb,other_climb):continue
            node=nodes[i];node['edges'].append({'to':j,'portal':[aa,bb],'source':'external'})
    return nodes
