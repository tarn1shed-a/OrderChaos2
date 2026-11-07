"""Bounded source Shape1/3/4 paint reader for the recovered IGM frame.

Exports source paths/fills/lines for browser SVG rendering, not new artwork.
Unknown styles/flags fail closed. Specification: Adobe SWF v19, shapes/gradients.
"""
import struct
from ui_assets import Bits
from hud_assets import sprite_frames,resolve

def paths(edges,closed):
    result=[];pending=list(edges)
    while pending:
        start,control,end=pending.pop(0);point=end;parts=[f'M {start[0]} {start[1]}']
        parts.append(f'Q {control[0]} {control[1]} {end[0]} {end[1]}' if control else f'L {end[0]} {end[1]}')
        while point!=start:
            index=next((i for i,v in enumerate(pending) if v[0]==point),None)
            if index is None:
                if closed:raise ValueError('Open source fill contour')
                break
            _,control,end=pending.pop(index);parts.append(f'Q {control[0]} {control[1]} {end[0]} {end[1]}' if control else f'L {end[0]} {end[1]}');point=end
        if point==start:parts.append('Z')
        result.append(' '.join(parts))
    return ' '.join(result)

def shape(kind,raw):
    if kind not in (2,32,83):raise ValueError('Unsupported IGM shape tag')
    b=Bits(raw,2);bounds=b.rect();at=b.pos();winding=False
    if kind==83:
        edge_bounds=b.rect();at=b.pos();flags=raw[at];at+=1
        if flags&~7:raise ValueError('Unknown Shape4 flags')
        winding=bool(flags&4)
    channels=4 if kind in (32,83) else 3
    def take(n):
        nonlocal at
        if at+n>len(raw):raise ValueError('Truncated source paint')
        value=raw[at:at+n];at+=n;return value
    def count():
        n=take(1)[0]
        if n==255:n=struct.unpack('<H',take(2))[0]
        if n>16:raise ValueError('IGM paint count exceeds supported span')
        return n
    def color():return list(take(channels))+([255] if channels==3 else [])
    def matrix():
        nonlocal at
        bits=Bits(raw,at);value=bits.matrix();at=bits.pos();return value
    def fill():
        typ=take(1)[0]
        if typ==0:return {'kind':'solid','color':color()}
        if typ in (16,18):
            m=matrix();flags=take(1)[0];spread,interpolation,n=flags>>6,(flags>>4)&3,flags&15
            if spread>2 or interpolation>1 or not 1<=n<=15 or kind!=83 and (spread or interpolation or n>8):raise ValueError('Unsupported source gradient flags')
            stops=[{'ratio':take(1)[0],'color':color()} for _ in range(n)]
            if stops!=sorted(stops,key=lambda s:s['ratio']):raise ValueError('Unsorted source gradient')
            return {'kind':'linear' if typ==16 else 'radial','matrix':m,'spread':spread,'interpolation':interpolation,'stops':stops}
        if typ in (64,65,66,67):return {'kind':'bitmap','bitmapId':struct.unpack('<H',take(2))[0],'matrix':matrix(),'sourceType':typ}
        raise ValueError('Unsupported source fill style')
    fills=[fill() for _ in range(count())];lines=[]
    for _ in range(count()):
        width=struct.unpack('<H',take(2))[0]
        if kind==83:
            bits=Bits(raw,at);start,join=bits.u(2),bits.u(2);has_fill,noh,nov,hint=[bits.u(1) for _ in range(4)];reserved=bits.u(5);no_close=bits.u(1);end=bits.u(2);at=bits.pos()
            if reserved or start>2 or end>2 or join>2 or noh or nov or hint or start!=end:raise ValueError('Unsupported IGM line flags')
            miter=struct.unpack('<H',take(2))[0]/256 if join==2 else 4
            paint=fill() if has_fill else {'kind':'solid','color':color()}
            lines.append({'width':width,'cap':start,'join':join,'miter':miter,'noClose':bool(no_close),'paint':paint})
        else:lines.append({'width':width,'cap':0,'join':0,'miter':4,'noClose':False,'paint':{'kind':'solid','color':color()}})
    bits=Bits(raw,at);nf,nl=bits.u(4),bits.u(4);x=y=0;f0=f1=line=0;fe=[[] for _ in fills];le=[[] for _ in lines]
    for _ in range(100000):
        if bits.u(1):
            straight=bits.u(1);size=bits.u(4)+2;start=(x,y)
            if straight:
                if bits.u(1):dx,dy=bits.s(size),bits.s(size)
                elif bits.u(1):dx,dy=0,bits.s(size)
                else:dx,dy=bits.s(size),0
                x+=dx;y+=dy;control=None
            else:
                control=(x+bits.s(size),y+bits.s(size));x=control[0]+bits.s(size);y=control[1]+bits.s(size)
            edge=(start,control,(x,y))
            if f0:fe[f0-1].append(((x,y),control,start))
            if f1:fe[f1-1].append(edge)
            if line:le[line-1].append(edge)
        else:
            flags=bits.u(5)
            if not flags:break
            if flags&1:size=bits.u(5);x,y=bits.s(size),bits.s(size)
            if flags&2:f0=bits.u(nf)
            if flags&4:f1=bits.u(nf)
            if flags&8:line=bits.u(nl)
            if flags&16:raise ValueError('Mid-shape styles are not supported')
            if max(f0,f1)>len(fills) or line>len(lines):raise ValueError('Source style index outside arrays')
    else:raise ValueError('Source path exceeds reader bound')
    bits.align()
    if bits.pos()!=len(raw):raise ValueError('Trailing source shape data')
    return {'boundsTwips':bounds,'fillRule':'nonzero' if winding else 'evenodd',
        'fills':[{'paint':p,'path':paths(e,True)} for p,e in zip(fills,fe) if e],
        'lines':[dict(p,path=paths(e,False)) for p,e in zip(lines,le) if e]}

def display_tree(doc,cid,library,depth=0):
    if depth>8:raise ValueError('IGM display tree too deep')
    rec=doc['records'].get(cid)
    if cid==0 or rec and rec[0]==39:
        children=[]
        for item in sprite_frames(doc,cid)[0]:
            if any(k in item for k in ('filters','clipDepth','blendMode')):raise ValueError('Unsupported IGM placement effect')
            child_doc,child_id=resolve(doc,item,library)
            children.append({'matrixTwips':item['matrixTwips'],'colorTransform':item['colorTransform'],'sourceDepth':item['depth'],
                'node':display_tree(child_doc,child_id,library,depth+1)})
        return {'kind':'group','sourceSWF':doc['path'],'sourceCharacterId':cid,'children':children}
    if not rec:raise ValueError('IGM source character missing')
    return {'kind':'shape','sourceSWF':doc['path'],'sourceCharacterId':cid,**shape(*rec)}

def bounds(node):
    if node['kind']=='shape':
        x0,x1,y0,y1=node['boundsTwips'];return [x0,y0,x1,y1]
    points=[]
    for child in node['children']:
        x0,y0,x1,y1=bounds(child['node']);a,b,c,d,tx,ty=child['matrixTwips']
        points.extend((a*x+c*y+tx,b*x+d*y+ty) for x,y in [(x0,y0),(x0,y1),(x1,y0),(x1,y1)])
    if not points:raise ValueError('Empty IGM tree')
    xs,ys=zip(*points);return [min(xs),min(ys),max(xs),max(ys)]

def text_style(kind,raw):
    if kind!=37:raise ValueError('Expected source EditText')
    b=Bits(raw,2);rect=b.rect();at=b.pos();flags=int.from_bytes(raw[at:at+2],'big');at+=2
    if flags&0x80 or not flags&0x100 or not flags&0x400 or not flags&0x20:raise ValueError('Unsupported IGM EditText flags')
    font,height=struct.unpack_from('<HH',raw,at);at+=4;rgba=list(raw[at:at+4]);at+=4
    if flags&0x200:at+=2
    align=raw[at];left,right,indent,leading=struct.unpack_from('<HHHh',raw,at+1);at+=9
    end=raw.index(0,at);variable=raw[at:end].decode();at=end+1;initial=''
    if flags&0x8000:end=raw.index(0,at);initial=raw[at:end].decode();at=end+1
    if at!=len(raw) or align>3:raise ValueError('Unknown IGM text extent/alignment')
    return {'boundsPixels':[v/20 for v in rect],'fontId':font,'fontHeight':height/20,'colorRGBA':rgba,'align':align,
        'marginsPixels':[left/20,right/20,indent/20],'leadingPixels':leading/20,'border':bool(flags&8),'initialHTML':initial,'variable':variable}
