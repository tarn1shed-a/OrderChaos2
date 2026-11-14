"""Reduce research observer overhead without replacing original ARM64 math.

Only the passive heap-write logger can be removed after source setup. Invalid
memory guards, original code, resource readers and every environment hook stay.
The scalar queue clocks/weights are never predicted or changed.
"""
import math
import copy
import hashlib
import struct
import time
from types import MappingProxyType
from collections import OrderedDict
from character_human_queue_composition_probe import HumanCompositionProbe
DISPATCH=bytes.fromhex('f353bca9f55b01a9f77b02a9e81b00fdf30300aaf403012af50302aaf60303aa0840201e600640a9620e41a9360400f9290840f93f7d00a97f0000b90041201e24008052a0023fd67382009194060071a1feff54e81b40fdf77b42a9f55b41a9f353c4a8c0035fd6f353bca9f55b01a9f76302a9fe1b00f9f30300aaf403012af50302aaf60303aaf80304aa17008052e00315aae103172a620e40a9650a40f944008052e60316aa00033fd6f70600117362009194060071c1feff54fe1b40f9f76342a9f55b41a9f353c4a8c0035fd6')


class FastHumanCompositionProbe(HumanCompositionProbe):
    def __init__(self,*args):
        import native_bres_world_bounds_probe as native
        from unicorn import UC_HOOK_MEM_WRITE,UC_HOOK_CODE
        image=args[0];plt=image.elf.get_section_by_name('.plt');plt_begin=plt['sh_addr'];plt_end=plt_begin+plt['sh_size']-1
        if not all(plt_begin<=at<=plt_end for at in image.imports):raise ValueError('Original imported entry leaves source PLT')
        real=native.Uc;self.passive_observers=[];self.import_hook=None;self.merged_import_hook_requests=0
        self.allocated_blocks={};self.free_blocks=[];self.recycling=False;self.recycled_allocations=0;self.original_free_requests=0
        def make_uc(*values,**kwargs):
            uc=real(*values,**kwargs);add=uc.hook_add
            def registered(kind,callback,*rest,**kw):
                if kind==UC_HOOK_CODE and kw.get('begin')==kw.get('end')and kw.get('begin')in image.imports:
                    self.merged_import_hook_requests+=1
                    if self.import_hook is None:
                        def dispatch(machine,at,size,data):
                            if at in image.imports:self.hook(machine,at,size,data)
                        self.import_hook=add(UC_HOOK_CODE,dispatch,begin=plt_begin,end=plt_end)
                    return self.import_hook
                handle=add(kind,callback,*rest,**kw)
                if kind==UC_HOOK_MEM_WRITE and callback.__name__=='flag_write'and callback.__self__ is self:self.passive_observers.append(handle)
                return handle
            uc.hook_add=registered;return uc
        # The inherited source loader creates its own emulator. Capture only
        # the handle of its passive logger; never patch a frozen source file.
        native.Uc=make_uc
        try:super().__init__(*args)
        finally:native.Uc=real
        if len(self.passive_observers)!=1:raise ValueError('Only the known passive source flag observer may be disabled')
        self.passive_write_observer_enabled=True;self.profile_times=[];self.sample_cache=OrderedDict();self.sample_cache_limit=64;self.sample_cache_hits=0;self.sample_cache_misses=0

    def alloc(self,n):
        if type(n)is not int or n<0 or n>0x200000:raise ValueError('Bounded source allocator request differs')
        if self.recycling:
            for i,(pointer,size)in enumerate(self.free_blocks):
                if size>=n:
                    self.free_blocks.pop(i);self.uc.mem_write(pointer,bytes(n));self.allocated_blocks[pointer]=(size,True);self.recycled_allocations+=1;return pointer
        pointer=super().alloc(n);self.allocated_blocks[pointer]=(((n+63)//64)*64,True);return pointer

    def hook(self,uc,at,size,data):
        if self.recycling and at in(0x29f220,0x2a0180,0x30da84,0x11dcc44,0x3c0fe8):
            pointer=self.get('X0');self.original_free_requests+=1
            if pointer:
                block=self.allocated_blocks.get(pointer)
                if not block or not block[1]:raise ValueError('Original temporary free has no live host allocation')
                self.allocated_blocks[pointer]=(block[0],False);self.free_blocks.append((pointer,block[0]))
            self.set('PC',self.get('X30'));return
        return super().hook(uc,at,size,data)

    def bind_profile(self,profile):
        from character_human_queue_probe import profile_hash
        from analyze_native_resources import NATIVE_SHA256
        if hasattr(self,'bound_motion'):raise ValueError('Original source profile is already bound; use another independent VM')
        if not isinstance(profile,dict)or profile.get('sha256')!=profile_hash(profile)or profile.get('nativeSHA256')!=NATIVE_SHA256 or hashlib.sha256(self.image.data).hexdigest()!=NATIVE_SHA256 or profile.get('species',{}).get('sourceModelId')!=1 or profile['species']['dataSHA256']!=self.mask_report['bodyDataSHA256']:raise ValueError('Verified loaded native profile/body agreement required')
        self.bound_profile_sha256=profile['sha256'];self.bound_motion=MappingProxyType({k:profile['species'][k]for k in('format','sha256','key','race','gender','sourceModelId')})
        self.bound_ranges=MappingProxyType({name:MappingProxyType(copy.deepcopy(row))for name,row in profile['species']['ranges'].items()})
        self.sample_cache.clear()

    def compose_bound_packet(self,packet):
        if not hasattr(self,'bound_motion'):raise ValueError('Bind the exact immutable original source profile first')
        if not isinstance(packet,dict)or any(packet.get(k)is not True for k in('nativeQueueCPU','nativeTimedCompletionCPU','nativeBlendCPU','nativePriorityQueryCPU'))or packet.get('sourceMotion')!=self.bound_motion or len(packet.get('layers',[]))!=2:raise ValueError('Verified explicit human source queue packet required')
        for i,row in enumerate(packet['layers']):
            weights=row.get('weights');current=row.get('current');previous=row.get('previous')
            if row.get('channel')!=i or not isinstance(current,dict)or not isinstance(weights,list)or len(weights)!=2 or any(type(w)not in(int,float)or not math.isfinite(w)or not 0<=w<=1 for w in weights)or abs(sum(weights)-1)>1e-6:raise ValueError('Exact two-child source queue weights required')
            if previous is None and weights!=[1.,0.]:raise ValueError('Missing original previous child with nonzero weight')
            for child in(current,previous):
                if child is None:continue
                source_range=self.bound_ranges.get(child.get('clip'));age=child.get('ageMs')
                if not source_range or type(age)not in(int,float)or not math.isfinite(age)or not 0<=age<=source_range['endMs']-source_range['startMs']:raise ValueError('Explicit bounded own original clip clock required')
        self.profile_times=[]
        layers=[];sample_cache={};mix_cache={}
        def sampled(child):
            key=(child['clip'],child['ageMs'])
            if key not in sample_cache:sample_cache[key]=self.own_values(child['clip'],child['ageMs'],self.bound_ranges)
            return sample_cache[key]
        for row in packet['layers']:
            current=row['current'];previous=row['previous'];values=sampled(current);old=sampled(previous)if previous else None
            key=((current['clip'],current['ageMs']),(previous['clip'],previous['ageMs'])if previous else None,tuple(row['weights']))
            if key not in mix_cache:mix_cache[key]=self.mix_loaded_values(values,old,row['weights'])
            layers.append(mix_cache[key])
        self.last_evaluation_reuse={'uniqueSampleCalls':len(sample_cache),'uniqueMixCalls':len(mix_cache),'scope':'same immutable source and exact clip/age/weight arguments within this packet only'}
        result=self.compose_values(layers);result.update({'sourceQueuePacket':packet,'sourceMotion':packet['sourceMotion'],'intraLayerPropertyMixCPU':True,'ordinaryMixModeFromOriginalConstructor':0});return result

    def remove_passive_observer(self):
        if not self.passive_write_observer_enabled:raise ValueError('Passive observer was already removed')
        for handle in self.passive_observers:self.uc.hook_del(handle)
        self.passive_write_observer_enabled=False

    def prepare_batch(self):
        if getattr(self,'batch_prepared',False)or not hasattr(self,'frame')or len(self.channels)!=135:raise ValueError('Original full 135-property composition must be prepared exactly once first')
        self.dispatch_base=0x30000400;self.uc.mem_write(self.dispatch_base,DISPATCH)
        n=len(self.channels);self.sample_rows=self.alloc(n*32);self.sample_output=self.alloc(n*16);contexts=self.alloc(n*24);states=self.alloc(n*16);indexes=self.alloc(n*4)
        for i,row in enumerate(self.channels):
            context=contexts+i*24;self.w(context,'3Q',row['record'],0,states+i*16);self.w(self.sample_rows+i*32,'4Q',row['object'],context,self.sample_output+i*16,indexes+i*4)
        self.mix_rows=self.alloc(n*24);self.mix_values=self.alloc(n*32);self.mix_factors=self.alloc(8);self.mix_output=self.alloc(n*16)
        for i in range(n):self.w(self.mix_rows+i*24,'3Q',self.mix_values+i*32,self.mix_factors,self.mix_output+i*16)
        self.batch_prepared=True

    def enable_temporary_recycling(self):
        if not getattr(self,'batch_prepared',False)or self.recycling:raise ValueError('Enable source temporary recycling only once after loaded source setup')
        # The original caller still decides the lifetime. This supplies a
        # bounded host allocator at the already explicit allocator boundary;
        # it does not claim to execute the original Android arena manager.
        self.recycling=True

    def sampled_batch_values(self,name,age_ms,ranges):
        if not getattr(self,'batch_prepared',False)or name not in ranges or type(age_ms)not in(int,float)or not math.isfinite(age_ms)or not 0<=age_ms<=ranges[name]['endMs']-ranges[name]['startMs']:raise ValueError('Prepared source batch and explicit bounded own clip clock required')
        absolute=ranges[name]['startMs']+age_ms
        indexes=[i for i,row in enumerate(self.segments)if row['startMs']<=absolute<=row['endMs']]
        if not indexes:raise ValueError('Original segment does not cover exact source sample')
        index=indexes[-1]
        if index not in self.segment_cache:
            obj,vt=self.alloc(16),self.alloc(32);self.w(obj,'Q',vt);self.w(vt+0x10,'Q',0x30000108)
            self.segment_cache[index]=self.invoke(0x117c40c,X0=self.segment_table+16+index*40,X1=obj,W2=0)
        self.invoke(self.dispatch_base,time=absolute,X0=self.sample_rows,W1=len(self.channels),X2=0x1109aec,X3=self.segment_cache[index])
        values=struct.unpack('<'+str(len(self.channels)*4)+'f',self.uc.mem_read(self.sample_output,len(self.channels)*16))
        return [list(values[i*4:i*4+(4 if row['type']==5 else 3)])for i,row in enumerate(self.channels)]

    def mixed_batch_values(self,current,previous,weights):
        if previous is None:
            if weights!=[1.,0.]:raise ValueError('Missing original previous child with nonzero weight')
            return current
        if not getattr(self,'batch_prepared',False):raise ValueError('Explicit original mix batch must be prepared first')
        payload=[]
        for a,b in zip(current,previous):
            values=list(a)+list(b);payload.extend(values+[0.]*(8-len(values)))
        self.uc.mem_write(self.mix_values,struct.pack('<'+str(len(payload))+'f',*payload));self.w(self.mix_factors,'2f',*weights)
        self.invoke(self.dispatch_base+104,X0=self.mix_rows,W1=len(self.channels),X2=self.composer+0x48,X3=self.frame_holder,X4=0x11894f8)
        values=struct.unpack('<'+str(len(self.channels)*4)+'f',self.uc.mem_read(self.mix_output,len(self.channels)*16))
        return [list(values[i*4:i*4+(4 if row['type']==5 else 3)])for i,row in enumerate(self.channels)]

    def own_values(self,*args):
        started=time.perf_counter();name,age,ranges=args
        if ranges is not getattr(self,'bound_ranges',None):raise ValueError('Bounded sample cache requires the same immutable loaded source ranges')
        key=(name,age)
        if key in self.sample_cache:
            result=self.sample_cache.pop(key);self.sample_cache[key]=result;self.sample_cache_hits+=1
        else:
            values=self.sampled_batch_values(*args)if getattr(self,'batch_prepared',False)else super().own_values(*args);result=tuple(tuple(row)for row in values);self.sample_cache[key]=result;self.sample_cache_misses+=1
            if len(self.sample_cache)>self.sample_cache_limit:self.sample_cache.popitem(last=False)
        self.profile_times.append({'stage':'original-sample-or-exact-loaded-value-reuse','milliseconds':(time.perf_counter()-started)*1000});return result

    def mix_loaded_values(self,*args):
        started=time.perf_counter();result=self.mixed_batch_values(*args)if getattr(self,'batch_prepared',False)else super().mix_loaded_values(*args);self.profile_times.append({'stage':'original-intra-layer-mix','milliseconds':(time.perf_counter()-started)*1000});return result

    def compose_values(self,*args):
        started=time.perf_counter();result=super().compose_values(*args);self.profile_times.append({'stage':'original-cross-layer-composition-and-worlds','milliseconds':(time.perf_counter()-started)*1000});return result
