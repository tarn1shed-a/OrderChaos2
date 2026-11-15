"""Original map1 containment for the bounded quest208 coastal route.

Original row constructors, polygon preparation and containment execute ARM64.
Parsed FTABLE storage, COW strings, numeric scanning and vector storage are
explicit host interfaces. No environment activation or server state is made.
"""
import ctypes
import hashlib
import json
from pathlib import Path

from source_physics import SourcePhysics
from analyze_native_resources import NATIVE_SHA256
from scene_zone_selection import verify_native,phase_allows
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from skill_attachments import decode_ftable


class MainlineZoneProbe(SourcePhysics):
    def __init__(self,image):
        if hashlib.sha256(image.data).hexdigest()!=NATIVE_SHA256:raise ValueError('Original zone native build differs')
        verify_native(image);super().__init__(image)
        from unicorn import UC_HOOK_CODE
        self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=0x1de7658,end=0x1de7658)
        self.libc=ctypes.CDLL(None);self.libc.sscanf.restype=ctypes.c_int

    def string(self,text):
        raw=text.encode();p=self.alloc(24+len(raw)+1);self.w(p,'QQq',len(raw),len(raw),1000000000);self.uc.mem_write(p+24,raw+b'\0');return p+24

    def hook(self,uc,address,size,data):
        name=self.imports.get(address)
        if name=='sscanf':
            raw=self.cstr(self.get('X0'));fmt=self.cstr(self.get('X1'))
            if fmt!=b'%f':raise ValueError('Original polygon scanner format changed')
            value=ctypes.c_float();count=self.libc.sscanf(ctypes.c_char_p(raw),ctypes.c_char_p(fmt),ctypes.byref(value))
            if count==1:self.w(self.get('X2'),'f',value.value)
            self.set('W0',count)
        elif name=='_ZNSt6vectorIfSaIfEE9push_backERKf':
            vector=self.get('X0');value=self.r(self.get('X1'),'I')[0];begin,end,capacity=self.r(vector,'3Q')
            if end==capacity:
                count=(end-begin)//4;new_capacity=max(1,count*2);new=self.alloc(new_capacity*4)
                if count:uc.mem_write(new,bytes(uc.mem_read(begin,count*4)))
                begin,end,capacity=new,new+count*4,new+new_capacity*4
            self.w(end,'I',value);self.w(vector,'3Q',begin,end+4,capacity)
        elif address==0x1de7658:
            raw=self.cstr(self.r(self.get('X0'),'Q')[0]);start=self.get('X2');character=bytes([self.get('W1')&255])
            position=raw.find(character,start);self.set('X0',position if position>=0 else(1<<64)-1)
        else:return super().hook(uc,address,size,data)
        self.set('PC',self.get('X30'))

    def row(self,row,table):
        pointer=self.alloc(0x1f0);self.call(0x4c0a18,{'X0':pointer});at=pointer
        for key,kind in zip(table['columns'],table['physicalTypes']):
            value=row[key]
            if kind=='s':self.w(at,'Q',self.string(value));at+=8
            elif kind=='f':self.w(at,'f',value);at+=4
            else:self.w(at,'I',value&0xffffffff);at+=4
        if at-pointer!=0x164:raise ValueError('Original zone runtime row layout changed')
        return pointer


def verify_route_region(image,source=None):
    source=source or Sources(DEFAULT_SOURCE);table=decode_ftable(source.read('tables/zones.tbl'),'ID')
    rows=sorted((r for r in table['rows']if r['map_id']==1),key=lambda r:r['ID'])
    e=MainlineZoneProbe(image);pointers={r['ID']:e.row(r,table)for r in rows}
    endpoints=decode_ftable(source.read('tables/creature_spawns.tbl'))['rows'];a=next(r for r in endpoints if r['id']==2335);b=next(r for r in endpoints if r['id']==2337)
    points=[]
    for k in range(65):
        fraction=k/64;x=a['position_x']+(b['position_x']-a['position_x'])*fraction;z=a['position_z']+(b['position_z']-a['position_z'])*fraction
        tested=[]
        def choose(candidates):
            found=[]
            for r in candidates:
                if not phase_allows(r['phasing_id'],0):continue
                result=e.call(0x4c2bcc,{'X0':pointers[r['ID']]},{'S0':x,'S1':z})
                tested.append({'id':r['ID'],'definition':r['definition'],'inside':bool(result&1),'priority':r['priority']})
                if result&1:found.append(r)
            return max(found,key=lambda r:r['priority']&0xffffffff)if found else None
        base=choose([r for r in rows if r['level']==0 and r['fly']<=0])
        overlay=choose([r for r in rows if base and r['parent_ID']==base['ID']])
        points.append({'fraction':fraction,'point':[x,z],'baseId':base['ID']if base else None,'overlayId':overlay['ID']if overlay else None,'containment':tested})
    if any(p['baseId']!=3 or p['overlayId']!=5 for p in points):raise ValueError('Original route chooses another source region')
    polygons=[]
    for r in rows:
        if r['parent_ID']!=3 or r['definition']==0:continue
        p=pointers[r['ID']];polygons.append({'id':r['ID'],'sourcePoints':r['points'],'preparedFlag':e.r(p+0x16c,'I')[0],'nativeVertexCount':e.r(p+0x170,'I')[0]})
    routines={}
    for address in(0x4c0a18,0x4c2bcc,0x4c2cf4):
        metadata,_=image.routine(address);routines[hex(address)]={**metadata,'sha256':hashlib.sha256(image.read(int(metadata['start'],16),metadata['size'])).hexdigest()}
    return {'format':'oc2-mainline208-native-zone-selection-v1','mapId':1,'questId':208,'phaseFlagsInput':0,'baseId':3,'overlayId':5,
        'points':points,'originalContainmentAndPolygonPreparationExecuted':True,'originalFull4c4de4Executed':False,'originalFullEnvironmentOrGPUExecuted':False,
        'polygons':polygons,'nativeRoutines':routines,'sourceProofs':source.proofs,
        'hostInterfaces':['explicit parsed original FTABLE row storage','COW string storage','host libc sscanf %f','vector float storage','phase0 and unsigned-priority source catalog traversal'],
        'scope':'Only the65 original-route sample points, not whole map residency, live phase or environment history.'}


if __name__=='__main__':
    import argparse
    from analyze_native_resources import NativeImage
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--output',type=Path,required=True);args=cli.parse_args()
    from tutorial_map_geometry import ROOT,local_output
    output=local_output(args.output)
    if output.exists():raise ValueError('Preserve old zone evidence')
    report=verify_route_region(NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes()))
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'baseId':report['baseId'],'overlayId':report['overlayId'],'points':len(report['points']),'polygons':report['polygons']}))
