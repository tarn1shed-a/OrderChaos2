"""Locate human source animation clock differences against the original CPU.

Frozen source packages, rigs and readers are read-only. The additional decoder
preserves source values and uses the original uint16-frame -> rounded-ms clock.
"""
import argparse
import bisect
import copy
import hashlib
import json
import math
import struct
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'analysis/raw/character-world-motion-20261115'
NATIVE=ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'
MODELS={
 'female':{'body':'model/npc/character/human/female/oc2_human_f_body_01.bdae','animation':'model/npc/character/human/female/anim/animations.bdae','old':'character-human-female-world-20261115','failed':'run_normal_front','properties':131,
           'bodySHA256':'e2533d6704c7bf68de0335d29aac9b072b2ea01f8d52bdb6769189f41b3627c4','animationSHA256':'5c883cd225dbc2391c67b0a2f5cee5edaab72585359432dace49b7341f228d41'},
 'male':{'body':'model/npc/character/human/male/oc2_human_m_body_01.bdae','animation':'model/npc/character/human/male/anim/animations.bdae','old':'character-human-world-20261115','failed':'jumplandrun','properties':135,
         'bodySHA256':'2fb559ab9d1ed126cffb8c18d8b07ab11ccb32193487d7c778a64e6d19acb6b6','animationSHA256':'1798ec8c3cc2fa0c136f8f3c278928b1ca6dbdf7c9bbc4871d3fb197cd50000e'},
}
ACTIONS=('idle','walk_forward','run_normal_front','run_idle','jump_start','jump_air','jump_air_drop','jump_land','jumplandrun','swim_idle','swim_forward')
MS_PER_FRAME_BITS=0x42055555
FRAMES_PER_MS_BITS=0x3cf5c290
QUATERNION_EPSILON_BITS=0x3d4ccccd
NATIVE_SHA256='77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4'
PINS={0x1109aec:(212,'ddc6dc050e1247a6452fd57356b9d2121b120235af1de0ae4e0c143cab78e588'),
      0x114a61c:(2052,'cf3bd4fc700ab14c0b9e9af78cb595c3be3040db7c4fe71248a1feaccd2bf85e'),
      0x114afcc:(424,'7f2eda6fabb3cc0186bfe28a3f97e627fedf71079fa2972889d4b515877bfd2d')}


def f32(value):return struct.unpack('<f',struct.pack('<f',value))[0]


def source_frame_milliseconds(frame):
    if type(frame)is not int or not 0<=frame<=65535:raise ValueError('Original uint16 frame required')
    scaled=f32(f32(frame)*struct.unpack('<f',struct.pack('<I',MS_PER_FRAME_BITS))[0])
    return int(f32(scaled+(.5 if scaled>0 else -.5)))


def parse_source_clock(reader,names):
    """Keep original sample values; only correct the evidenced source key times."""
    decoded=reader.parse(names)
    channels=reader.channels();segments=reader.segments()
    for clip in decoded['clips']:
        start,end=clip['sourceRangeFrames'];begin_ms,end_ms=clip['sourceRangeMs']
        if (source_frame_milliseconds(start),source_frame_milliseconds(end))!=(begin_ms,end_ms):
            raise ValueError('Unclosed source range/rounded-key boundary')
        relevant=[s for s in segments if s['startMs']<=end_ms and s['endMs']>=begin_ms]
        for track,channel in zip(clip['tracks'],channels):
            if (track['node'],track['type'])!=(channel['node'],channel['type']):raise ValueError('Source channel order differs')
            merged={};components=channel['components']
            for segment in relevant:
                nt,at=reader._source(segment,channel['timeIndex']);nv,av=reader._source(segment,channel['valueIndex'])
                frames=reader.unpack('H'*(nt//2),at);values=reader.unpack('f'*(nv//4),av)
                for i,frame in enumerate(frames):
                    row=list(values[i*components:(i+1)*components])
                    if frame in merged and merged[frame]!=row:raise ValueError('Original repeated frame values differ')
                    merged[frame]=row
            source_frames=sorted(merged)
            track['nativeClock']={'timeType':3,'frames':source_frames,'values':[v for frame in source_frames for v in merged[frame]],'components':components,
                                  'msPerFrameBits':hex(MS_PER_FRAME_BITS),'framesPerMsBits':hex(FRAMES_PER_MS_BITS)}
            frames=[start+round(t*30)for t in track['times']]
            if any(abs((frame-start)/30-time)>1e-8 for frame,time in zip(frames,track['times'])):
                raise ValueError('Old decoder time cannot be linked to an exact original frame')
            times=[(source_frame_milliseconds(frame)-begin_ms)/1000 for frame in frames]
            if any(a>=b for a,b in zip(times,times[1:])):raise ValueError('Rounded original keys are not strictly ordered')
            track['times']=times
        clip['duration']=(end_ms-begin_ms)/1000
        clip['sourceClock']='uint16 absolute frame * original float32 33.333332; round-to-nearest integer ms; original interpolation'
    decoded['verification']['sourceFrameMillisecondsRoundedBeforeInterpolation']=True
    decoded['verification']['sourceValuesChanged']=False
    return decoded


def source_track_sample(track,begin_ms,relative_seconds):
    native=track['nativeClock'];frames=native['frames'];width=native['components'];values=native['values']
    absolute=f32(begin_ms+relative_seconds*1000)
    frame=f32(absolute*struct.unpack('<f',struct.pack('<I',FRAMES_PER_MS_BITS))[0])
    at=max(0,min(len(frames)-1,bisect.bisect_right(frames,frame)-1))
    left=source_frame_milliseconds(frames[at]);a=tuple(values[at*width:(at+1)*width])
    if at==len(frames)-1 or int(absolute)==left:return a
    right=source_frame_milliseconds(frames[at+1]);weight=max(0.,min(1.,f32(f32(absolute-left)/f32(right-left))))
    b=tuple(values[(at+1)*width:(at+2)*width])
    if weight==0:return a
    if weight==1:return b
    if track['type']=='quaternion':return source_quaternion_interpolate(a,b,weight)
    return tuple(f32(x+f32(weight*f32(y-x)))for x,y in zip(a,b))


def source_quaternion_interpolate(a,b,weight):
    """Original 11dd664 branch and float32 operations, not a new epsilon."""
    dot=f32(f32(a[0]*b[0])+f32(a[1]*b[1]));dot=f32(f32(a[2]*b[2])+dot);dot=f32(f32(a[3]*b[3])+dot)
    if dot<0:a=tuple(-x for x in a);dot=-dot
    epsilon=struct.unpack('<f',struct.pack('<I',QUATERNION_EPSILON_BITS))[0]
    if f32(1+dot)<=epsilon:raise ValueError('Uncovered original antipodal quaternion branch')
    if f32(1-dot)<epsilon:
        result=[f32(x+f32(f32(y-x)*weight))for x,y in zip(a,b)]
        norm=f32(f32(result[0]*result[0])+f32(result[1]*result[1]));norm=f32(norm+f32(result[2]*result[2]));norm=f32(norm+f32(result[3]*result[3]))
        if norm==0:return tuple(result)
        inverse=f32(1/f32(math.sqrt(norm)));return tuple(f32(x*inverse)for x in result)
    angle=f32(math.acos(dot));inverse=f32(1/f32(math.sin(angle)))
    left=f32(f32(math.sin(f32(f32(1-weight)*angle)))*inverse);right=f32(inverse*f32(math.sin(f32(angle*weight))))
    return tuple(f32(f32(x*left)+f32(y*right))for x,y in zip(a,b))


def host_source_pose(skin,clip,time):
    from bdae_character import aliases
    from bdae_skin import multiply
    from tutorial_npc_binding_probe import world_matrices
    nodes=copy.deepcopy(skin['nodes']);by_name=aliases(nodes);samples={}
    for track in clip['tracks']:
        value=list(source_track_sample(track,clip['sourceRangeMs'][0],time));nodes[by_name[track['node']]][track['type']]=value
        samples[(track['node'],{'position':1,'quaternion':5,'scale':10}[track['type']])]=value
    world=world_matrices(nodes)
    return[multiply(world[bone['node']],bone['inverse'])for bone in skin['bones']],samples


def difference(native,wanted):
    direct=max(abs(a-b)for a,b in zip(native,wanted))
    return min(direct,max(abs(a+b)for a,b in zip(native,wanted)))if len(native)==4 else direct


def recover(image,source,gender,fractional_boundaries=False):
    from map_loading_evidence import Sources
    from bdae_convert import BDAE
    from bdae_animation import BDAEAnimation
    from scene_flags_evidence import literal_nodes
    from character_human_female_binding import FemaleControllerProbe,source_controller
    from tutorial_npc_binding_probe import host_pose,host_vertices
    from unicorn import UC_HOOK_CODE

    if hashlib.sha256(image.data).hexdigest()!=NATIVE_SHA256 or struct.unpack('<I',image.read(0x1f02100,4))[0]!=MS_PER_FRAME_BITS or struct.unpack('<I',image.read(0x1e62ca4,4))[0]!=FRAMES_PER_MS_BITS or struct.unpack('<I',image.read(0x1df7a78,4))[0]!=QUATERNION_EPSILON_BITS:
        raise ValueError('Original source clock image/constant differs')
    for at,(size,digest)in PINS.items():
        if hashlib.sha256(image.read(at,size)).hexdigest()!=digest:raise ValueError('Original source clock instructions differ')
    record=MODELS[gender];sources=Sources(source)
    class Probe(FemaleControllerProbe):
        def __init__(self,*args):
            super().__init__(*args);self.clock_trace=[];self.current_channel=None;self.warm={}
            for at in (0x114ac94,0x114acc0,0x1109b7c,0x1109ba0):self.uc.hook_add(UC_HOOK_CODE,self.observe,begin=at,end=at)

        def observe(self,uc,at,size,data):
            if self.current_channel is None:return
            row={'at':hex(at),'node':self.current_channel['node'],'type':self.current_channel['type']}
            if at==0x114ac94:row.update(leftMs=self.get('W8'),rightMs=self.get('W9'))
            elif at==0x114acc0:row['weight']=struct.unpack('<f',struct.pack('<I',self.get('S0')))[0]
            elif at==0x1109b7c:row.update(interpolationTarget=hex(self.get('X8')),leftIndex=self.get('W2'),rightIndex=self.get('W3'),weight=struct.unpack('<f',struct.pack('<I',self.get('S0')))[0])
            else:row.update(copyTarget=hex(self.get('X8')),index=self.get('W2'))
            self.clock_trace.append(row)

        def sampled_pose(self,absolute_ms,warm=False):
            indexes=[i for i,s in enumerate(self.segments)if s['startMs']<=absolute_ms<=s['endMs']]
            if not indexes:raise ValueError('Original segment does not cover sample')
            index=indexes[-1]
            if index not in self.segment_cache:
                obj,vt=self.alloc(16),self.alloc(32);self.w(obj,'Q',vt);self.w(vt+0x10,'Q',0x30000108)
                self.segment_cache[index]=self.invoke(0x117c40c,X0=self.segment_table+16+index*40,X1=obj,W2=0)
            samples=[];self.clock_trace=[]
            for ordinal,ch in enumerate(self.channels):
                key=(index,ordinal)
                if not warm or key not in self.warm:
                    context,state,output,sample_index=self.alloc(24),self.alloc(16),self.alloc(16),self.alloc(4)
                    self.w(context,'3Q',ch['record'],self.segment_cache[index],state)
                    if warm:self.warm[key]=(context,output,sample_index)
                else:context,output,sample_index=self.warm[key]
                self.current_channel=ch
                self.invoke(0x1109aec,time=absolute_ms,X0=ch['object'],X1=context,X2=output,X3=sample_index,W4=1)
                self.current_channel=None
                values=list(self.r(output,'4f'if ch['type']==5 else'3f'))
                setter=self.r(self.r(ch['object'],'Q')[0]+0x98,'Q')[0]
                self.invoke(setter,X0=ch['object'],X1=output,X2=self.native_nodes[ch['node']])
                samples.append({'node':ch['node'],'type':ch['type'],'value':values})
            self.propagate()
            return {'absoluteMs':absolute_ms,'samples':samples,'matrices':self.palette_case(),'clockTrace':list(self.clock_trace)}

    with tempfile.TemporaryDirectory(prefix='oc2-human-motion-')as tmp:
        paths={}
        for kind in ('body','animation'):
            p=Path(tmp)/record[kind];p.parent.mkdir(parents=True,exist_ok=True);raw=sources.read(record[kind]);p.write_bytes(raw);paths[kind]=p
            pin=record[kind+'SHA256']
            if pin is not None and hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('Original source identity differs')
        reader=BDAE(paths['body']);animation=BDAEAnimation(paths['animation'])
        data=json.loads((ROOT/'analysis/raw'/record['old']/'candidate-v3/assets/character.json').read_text())
        skin=source_controller(reader,{'meshes':[data['meshes'][0]]},literal_nodes(reader),0)
        p=Probe(image,reader,reader,skin,0);p.animation(animation)
        present=[name for name in ACTIONS if sum(r['name']==name for r in animation.ranges())==1]
        old={c['name']:c for c in animation.parse(present)['clips']};new={c['name']:c for c in parse_source_clock(animation,present)['clips']}
        rows=[]
        for name in present:
            range_=next(r for r in animation.ranges()if r['name']==name);duration=range_['endMs']-range_['startMs']
            times=sorted(set([0,duration//2,duration,*range(0,duration+1,max(1,duration//8))]))
            if fractional_boundaries:
                times=sorted(set(times+[t for t in(33.125,33.25,33.3125,33.34375,33.5,66.5,66.6875,66.875,66.9375,67.125,99.875,100.125,duration-.125)if 0<t<duration]))
            cases=[]
            for relative in times:
                actual=p.sampled_pose(range_['startMs']+relative);versions={}
                for version,clip in [('old',old[name]),('corrected',new[name])]:
                    matrices,samples=(host_pose if version=='old'else host_source_pose)(skin,clip,relative/1000)
                    errors=sorted([{'node':r['node'],'type':r['type'],'error':difference(r['value'],samples[(r['node'],r['type'])]),'native':r['value'],'host':samples[(r['node'],r['type'])]}for r in actual['samples']],key=lambda r:r['error'],reverse=True)
                    matrix_error=max(abs(a-b)for got,want in zip(actual['matrices'],matrices)for a,b in zip(got,want))
                    vertices=p.vertices(data['meshes'][0]['positions']);expected=host_vertices(skin,data['meshes'][0]['positions'],matrices)
                    versions[version]={'maximumSampleError':errors[0]['error'],'maximumPaletteError':matrix_error,'maximumVertexError':max(abs(a-b)for a,b in zip(vertices,expected)),'topSampleDifferences':errors[:3]}
                cases.append({'relativeMs':relative,'sourceProperties':len(actual['samples']),'nativeSamples':actual['samples'],'nativePalette':actual['matrices'],**versions,
                    **({'clockTrace':actual['clockTrace']}if name==record['failed']and relative in(0,duration//2,duration)else{})})
            rows.append({'name':name,'sourceRange':range_,'oldDuration':old[name]['duration'],'correctedDuration':new[name]['duration'],'cases':cases,
                'admitted':all(max(c['corrected'][k]for k in('maximumSampleError','maximumPaletteError','maximumVertexError'))<=.002 for c in cases)})
        # Verify source cache initialisation and seeking without rewriting source
        # node spaces or controller inverses. Cold and real cached native paths.
        cache_cases=[];name=record['failed'];range_=next(r for r in animation.ranges()if r['name']==name);duration=range_['endMs']-range_['startMs']
        for relative in(0,duration//2,duration,duration//2,0):
            cold=p.sampled_pose(range_['startMs']+relative)
            warm=p.sampled_pose(range_['startMs']+relative,True)
            cache_cases.append({'relativeMs':relative,'maximumSampleError':max(difference(a['value'],b['value'])for a,b in zip(cold['samples'],warm['samples'])),
                'maximumPaletteError':max(abs(a-b)for got,want in zip(cold['matrices'],warm['matrices'])for a,b in zip(got,want))})
        return {'format':'oc2-character-world-motion-clock-v1','gender':gender,'nativeSHA256':hashlib.sha256(image.data).hexdigest(),
            'sourceProofs':sources.proofs,'originalCPUExecuted':True,'comparisonTolerance':.002,'sourcePropertyCount':record['properties'],
            'sourceFrameTimeConstant':{'address':'0x1f02100','bits':hex(MS_PER_FRAME_BITS),'float32':struct.unpack('<f',image.read(0x1f02100,4))[0]},
            'clips':rows,'admittedActions':[r['name']for r in rows if r['admitted']], 'unadmittedActions':[r['name']for r in rows if not r['admitted']],
            'absentActions':[name for name in ACTIONS if name not in present],'coldWarmNativeCases':cache_cases,'allMeshNativeVertexExecution':False,
            'sourceValuesRigWeightsInversesUnchanged':True,'fractionalBoundariesChecked':fractional_boundaries,'savesReadOrWritten':False,'productionChanged':False}


if __name__=='__main__':
    from analyze_native_resources import NativeImage
    from resource_packs import DEFAULT_SOURCE
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--gender',choices=MODELS,required=True);cli.add_argument('--output',type=Path,required=True)
    cli.add_argument('--fractional-boundaries',action='store_true')
    cli.add_argument('--native',type=Path,default=NATIVE);cli.add_argument('--source',type=Path,default=DEFAULT_SOURCE);args=cli.parse_args()
    if args.output.exists():raise ValueError('Preserve existing motion evidence')
    image=NativeImage(args.native.read_bytes());report=recover(image,args.source,args.gender,args.fractional_boundaries)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'gender':args.gender,'admittedActions':report['admittedActions'],'unadmittedActions':report['unadmittedActions'],'absentActions':report['absentActions']}))
