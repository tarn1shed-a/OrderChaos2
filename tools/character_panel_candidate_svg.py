"""Independent SVG export of original skill-page display lists for local QA.

Uses existing strict source readers. No artwork or replacement layout is made.
Rendered original resources must remain below ignored analysis/raw/.
"""
import hashlib
import io
import re
import struct
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image
from hud_assets import compose,resolve,sprite_frames,rectangle_bitmap
from swf_ui_graphics import shape,text_style
from ui_assets import parse_font3

NS='http://www.w3.org/2000/svg';ET.register_namespace('',NS)
def el(tag,attrs=None):return ET.Element('{'+NS+'}'+tag,{k:str(v)for k,v in(attrs or{}).items()})
def matrix(m):return 'matrix('+' '.join(map(str,m))+')'
def rgb(c):return 'rgb('+','.join(map(str,c[:3]))+')'


class SourcePanelSVG:
    def __init__(self,load,library,output):
        self.load,self.library,self.output=load,library,Path(output)
        self.output.mkdir(parents=True,exist_ok=True)
        self.assets={};self.warnings=[];self.fonts={};self.count=0;self.text_fields={}
        self.selected_frames={};self.animated_paths=set()

    def key(self):
        self.count+=1;return 'source-panel-'+str(self.count)

    def asset(self,path):
        raw=self.load(path);digest=hashlib.sha256(raw).hexdigest();name='atlas-'+digest[:20]+'.png'
        image=Image.open(io.BytesIO(raw));image.verify()
        (self.output/name).write_bytes(raw)
        self.assets[path]={'url':'/assets/character-source/'+name,'sha256':digest,'bytes':len(raw)}
        return self.assets[path]['url']

    def source_image(self,doc,bid,path):
        """Use an exact external image or lossless same-symbol library crop.

        Some original page SWFs retain external image names while library.swf
        has their packed atlas shape. Never infer an atlas rectangle from pixels.
        """
        try:return self.asset(path),doc['bitmaps'][bid]
        except KeyError:pass
        stem=Path(path).stem;cid=self.library['symbols'].get(stem)
        if cid is not None and self.library['records'].get(cid,(None,))[0]==39:
            children=sprite_frames(self.library,cid)[0]
            if len(children)==1 and children[0]['matrixTwips']==[1,0,0,1,0,0]:
                shape_id=children[0].get('characterId');record=self.library['records'].get(shape_id)
                if record and record[0]==2:
                    try:bitmap,rect,m,bounds,_=rectangle_bitmap(record[1])
                    except ValueError:bitmap=None
                    if bitmap is not None:
                        names=[n for n,v in self.library['symbols'].items()if v==bitmap]
                        if len(names)==1 and Path(names[0]).name==names[0]:
                            atlas='ui/Texture/'+names[0];raw=self.load(atlas);im=Image.open(io.BytesIO(raw));crop=im.crop(rect)
                            if im.size==self.library['bitmaps'][bitmap] and crop.size==doc['bitmaps'][bid] and [bounds[0],bounds[2]]==[0,0] and [bounds[1]/20,bounds[3]/20]==list(crop.size):
                                if m[0]<0:crop=crop.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                                if m[3]<0:crop=crop.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                                encoded=io.BytesIO();crop.save(encoded,format='PNG');payload=encoded.getvalue();digest=hashlib.sha256(payload).hexdigest();filename='source-crop-'+digest[:20]+'.png';(self.output/filename).write_bytes(payload)
                                self.assets[path]={'url':'/assets/character-source/'+filename,'sha256':digest,'bytes':len(payload),'mode':'same-exported-symbol-lossless-source-crop','sourceSymbol':stem,'sourceLibrary':self.library['path'],'sourceSprite':cid,'sourceShape':shape_id,'sourceAtlas':atlas,'sourceAtlasSHA256':hashlib.sha256(raw).hexdigest(),'sourceRect':rect}
                                return self.assets[path]['url'],crop.size
        warning={'sourceSWF':doc['path'],'sourceBitmap':bid,'sourceImage':path,'boundary':'Original external image absent; no exact same-symbol library crop. Drawing left empty.'}
        if warning not in self.warnings:self.warnings.append(warning)
        return None,doc['bitmaps'][bid]

    def font(self,doc,identifier):
        if doc['path']not in self.fonts:
            decoded={}
            for raw in doc['fonts']:
                cid,flags,lang,n=struct.unpack_from('<HBBB',raw);name=raw[5:5+n].rstrip(b'\0').decode()
                count=struct.unpack_from('<H',raw,5+n)[0]
                decoded[cid]=parse_font3(raw)if flags&128 and count else{'id':cid,'name':name}
            self.fonts[doc['path']]=decoded
        return self.fonts[doc['path']][identifier]

    def paint(self,doc,p,defs):
        if p['kind']=='solid':return rgb(p['color']),p['color'][3]/255
        key=self.key()
        if p['kind']=='bitmap':
            bid=p['bitmapId'];names=[n for n,v in doc['symbols'].items()if v==bid]
            if len(names)!=1 or Path(names[0]).name!=names[0]:raise ValueError('Missing source skill atlas namespace')
            path='ui/Texture/'+names[0];url,size=self.source_image(doc,bid,path)
            if not url:return 'none',0
            node=el('pattern',{'id':key,'patternUnits':'userSpaceOnUse','width':size[0],'height':size[1],'patternTransform':matrix(p['matrix'])})
            node.append(el('image',{'href':url,'width':size[0],'height':size[1],
                                  'image-rendering':'auto'if p['sourceType']<66 else'pixelated'}))
        elif p['kind']in('linear','radial'):
            node=el('linearGradient'if p['kind']=='linear'else'radialGradient',{
                'id':key,'gradientUnits':'userSpaceOnUse','gradientTransform':matrix(p['matrix']),
                'spreadMethod':['pad','reflect','repeat'][p['spread']],
                'color-interpolation':'linearRGB'if p['interpolation']else'sRGB',
                **({'x1':-16384,'y1':0,'x2':16384,'y2':0}if p['kind']=='linear'else{'cx':0,'cy':0,'r':16384})})
            for stop in p['stops']:node.append(el('stop',{'offset':stop['ratio']/255,'stop-color':rgb(stop['color']),'stop-opacity':stop['color'][3]/255}))
        else:raise ValueError('Unsupported source skill paint')
        defs.append(node);return 'url(#'+key+')',1

    def draw(self,doc,cid,path,defs,depth=0,frame=None):
        if depth>24:raise ValueError('Source skill drawing recursion exceeds bound')
        record=doc['records'].get(cid)
        group=el('g',{'data-source-path':path,'data-source-id':cid,'data-source-file':doc['path']})
        if path.endswith('.CooldownForSkill'):
            self.warnings.append({'path':path,'boundary':'No original cooldown snapshot; source morph countdown left empty.'})
            return group
        if not record:raise ValueError('Missing source skill display record '+doc['path']+' '+str(cid)+' '+path)
        if record[0]==39:
            if path in self.animated_paths and frame is None:
                for number in range(1,len(sprite_frames(doc,cid))+1):
                    child=self.draw(doc,cid,path,defs,depth,number);child.set('data-attribute-frame',str(number));child.set('display','inline'if number==1 else'none');group.append(child)
                return group
            active=[]
            selected=frame or self.selected_frames.get(path,1)
            group.set('data-source-selected-frame',str(selected))
            for p in sprite_frames(doc,cid)[selected-1]:
                dd,ii=resolve(doc,p,self.library)
                child=self.draw(dd,ii,path+'.'+p.get('name',str(ii)),defs,depth+1)
                child.set('transform',matrix(p['matrixTwips']))
                c=p['colorTransform']
                if c['multiply']!=[256]*4 or c['add']!=[0]*4:
                    key=self.key();f=el('filter',{'id':key,'color-interpolation-filters':'sRGB'});values=[]
                    for row in range(4):values.extend([c['multiply'][row]/256 if row==col else 0 for col in range(4)]+[c['add'][row]/255])
                    f.append(el('feColorMatrix',{'type':'matrix','values':' '.join(map(str,values))}));defs.append(f);child.set('filter','url(#'+key+')')
                if p.get('filters'):self.warnings.append({'path':path,'boundary':'Flash filter rasterization','filters':p['filters']})
                if p.get('blendMode',1)not in(0,1):raise ValueError('Unsupported skill blend mode')
                if 'clipDepth'in p:
                    key=self.key();clip=el('clipPath',{'id':key,'clipPathUnits':'userSpaceOnUse'})
                    def flatten(node,parent=(1,0,0,1,0,0)):
                        local=node.get('transform');m=compose(parent,list(map(float,local[7:-1].split())))if local else parent
                        if node.tag.rsplit('}',1)[-1]=='path':
                            leaf=ET.fromstring(ET.tostring(node));leaf.set('transform',matrix(m));leaf.set('fill-opacity','1');clip.append(leaf)
                        else:
                            for sub in node:flatten(sub,m)
                    flatten(child)
                    if not len(clip):raise ValueError('Missing source skill clipping geometry')
                    defs.append(clip);active.append((p['clipDepth'],key));continue
                active=[v for v in active if p['depth']<=v[0]]
                for _,key in active:
                    wrap=el('g',{'clip-path':'url(#'+key+')'});wrap.append(child);child=wrap
                group.append(child)
        elif record[0]in(2,22,32,83):
            spec=shape(*record,extended=True)
            for fill in spec['fills']:
                color,alpha=self.paint(doc,fill['paint'],defs)
                group.append(el('path',{'d':fill['path'],'fill':color,'fill-opacity':alpha,'fill-rule':spec['fillRule']}))
            for line in spec['lines']:
                color,alpha=self.paint(doc,line['paint'],defs)
                group.append(el('path',{'d':line['path'],'fill':'none','stroke':color,'stroke-opacity':alpha,'stroke-width':line['width'],
                                       'stroke-linecap':['round','butt','square'][line['cap']],'stroke-linejoin':['round','bevel','miter'][line['join']]}))
        elif record[0]==37:
            style=text_style(*record);font=self.font(doc,style['fontId']);x0,x1,y0,y1=[v*20 for v in style['boundsPixels']]
            left,right,indent=style['marginsPixels'][:3];align=style['align']
            x=x0+(left+indent)*20 if align==0 else x1-right*20 if align==1 else(x0+x1)/2
            family='EntryDisplay'if'Alegreya'in font['name']else'EntryGothic'if'League'in font['name']else'EntryText'
            metric={'y':y0+style['fontHeight']*font['ascent']/1024}if'ascent'in font else{'y':y0,'dominant-baseline':'text-before-edge'}
            node=el('text',{'x':x,**metric,'font-family':family,'font-size':style['fontHeight']*20,
                'fill':rgb(style['colorRGBA']),'fill-opacity':style['colorRGBA'][3]/255,
                'text-anchor':['start','end','middle','start'][align],'data-entry-text':'true','data-font-source':font['name'],
                'data-source-leading':style['leadingPixels']*20,
                'data-source-bounds':' '.join(map(str,[x0,y0,x1-x0,y1-y0]))})
            node.text='' # Authored examples are not live actor values.
            group.append(node);self.text_fields[path]={'sourceSWF':doc['path'],'sourceCharacterId':cid,'style':style}
        else:raise ValueError('Unsupported source skill display tag '+str(record[0]))
        return group

    def export(self,doc,cid,name,selected_frames=None,animated_paths=()):
        self.selected_frames=selected_frames or {};self.animated_paths=set(animated_paths)
        svg=el('svg',{'viewBox':'0 0 1136 640','preserveAspectRatio':'xMidYMid meet'})
        defs=el('defs');svg.append(defs);wrap=el('g',{'transform':'scale(0.05)','data-source-page':name})
        wrap.append(self.draw(doc,cid,'',defs));svg.append(wrap)
        raw=ET.tostring(svg,encoding='utf-8');filename=name+'.svg';(self.output/filename).write_bytes(raw)
        return {'url':'/assets/character-source/'+filename,'sha256':hashlib.sha256(raw).hexdigest(),
                'sourceSWF':doc['path'],'sourceSHA256':doc['sourceSHA256'],'sourceRoot':cid}
