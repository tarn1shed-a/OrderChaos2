"""Original 135-property two-track composition on original human values.

Original sampler, property mixers, 372318 and real node setters execute.
The explicitly loaded frame/cache storage and child value publication are host
interfaces; this is not a claim of the complete Android animation graph factory.
"""
import json
import hashlib
import math
from pathlib import Path
from character_human_queue_bones_probe import HumanMaskProbe,bind_original_mask
from character_human_combat_probe import ROOT
RAW=ROOT/'analysis/raw/character-human-queue-composition-20261115'
MASK=ROOT/'analysis/raw/character-human-queue-bones-20261115/source-property-mask-final.json'
FORMAT='oc2-human-original-composed-properties-v1'


def checked_queue_packet(packet,profile):
    from character_human_queue_probe import profile_hash
    from analyze_native_resources import NATIVE_SHA256
    if not isinstance(profile,dict)or profile.get('sha256')!=profile_hash(profile)or profile.get('nativeSHA256')!=NATIVE_SHA256 or profile.get('species',{}).get('sourceModelId')!=1:raise ValueError('Verified original human queue profile required')
    required=('nativeQueueCPU','nativeTimedCompletionCPU','nativeBlendCPU','nativePriorityQueryCPU')
    if not isinstance(packet,dict)or any(packet.get(k)is not True for k in required)or packet.get('sourceMotion')!={k:profile['species'][k]for k in('format','sha256','key','race','gender','sourceModelId')}or len(packet.get('layers',[]))!=2:raise ValueError('Verified explicit human source queue packet required')
    for i,row in enumerate(packet['layers']):
        weights=row.get('weights');current=row.get('current');previous=row.get('previous')
        if row.get('channel')!=i or not isinstance(current,dict)or not isinstance(weights,list)or len(weights)!=2 or any(type(w)not in(int,float)or not math.isfinite(w)or not 0<=w<=1 for w in weights)or abs(sum(weights)-1)>1e-6:raise ValueError('Exact two-child source queue weights required')
        if previous is None and weights!=[1.,0.]:raise ValueError('Missing original previous child with nonzero weight')
        for child in (current,previous):
            if child is None:continue
            source_range=profile['species']['ranges'].get(child.get('clip'))
            age=child.get('ageMs')
            if not source_range or type(age)not in(int,float)or not math.isfinite(age)or not 0<=age<=source_range['endMs']-source_range['startMs']:raise ValueError('Explicit bounded own original clip clock required')
    return packet


class HumanCompositionProbe(HumanMaskProbe):
    CHILD=0x30000210
    CHILD_BIND=0x30000214
    CHILD_META=0x30000218

    def __init__(self,*args):
        self.compose_active=False;self.layer_samples=[];self.child_calls=[]
        super().__init__(*args)
        from unicorn import UC_HOOK_CODE
        for at in(self.CHILD,self.CHILD_BIND,self.CHILD_META,0x11891f4,0x11894f8,0x3732ac,0x3734f4):self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=at,end=at)

    def hook(self,uc,at,size,data):
        if at==0x110c954 and not self.mask_mode:return
        if at==self.CHILD:
            child=self.get('X0');index=self.child_ids[child];destination=self.get('X2')
            if not destination:raise ValueError('Uncovered direct child evaluation')
            source=self.r(destination,'Q')[0];slot=self.r(destination+8,'i')[0]
            if slot!=index:raise ValueError('Original child and output layer index disagree')
            frame,buffer=self.r(source+8,'2Q');stride=self.r(source+0x18,'i')[0]
            if frame!=self.frame or stride!=2:raise ValueError('Original two-track value-cache shape differs')
            for i,values in enumerate(self.layer_samples[index]):
                self.w(buffer+self.value_offsets[i]*stride+self.value_widths[i]*index,str(len(values))+'f',*values)
            self.child_calls.append({'layer':index,'properties':len(self.layer_samples[index]),'originalSelectedCacheStride':stride,'loadedTrackValueHostInterface':True});self.set('W0',0);self.set('PC',self.get('X30'));return
        if at==self.CHILD_BIND:self.set('PC',self.get('X30'));return
        if at==self.CHILD_META:self.set('X0',self.meta_holder);self.set('PC',self.get('X30'));return
        if at==0x11891f4:
            if self.compose_active:self.setter_calls.append({'property':self.get('W1'),'entry':'0x11891f4','source':'original-composition'})
            return
        if at in(0x11894f8,0x3732ac,0x3734f4):
            if self.compose_active:self.combination_calls.append(hex(at))
            return
        return super().hook(uc,at,size,data)

    def bitset(self,*,all_values):
        p=self.alloc(0x20);buf=self.alloc(((len(self.channels)+31)//32)*4)
        self.w(p+8,'I',1000);self.w(p+0x10,'Q',buf);self.w(p+0x18,'Q',self.range_reference)
        if all_values:self.invoke(0x10fa5f4,X0=p)
        return p

    def prepare_composition(self,data):
        report=json.loads(MASK.read_text());self.bound=bind_original_mask(report,data);self.data=data;self.mask_report=report
        if [(c['node'],c['type'])for c in self.channels]!=[(r['sourceNode'],r['sourceType'])for r in self.bound]:raise ValueError('Actual original property order differs')
        self.value_widths=list(self.r(self.r(self.manager+0x48,'Q')[0],str(len(self.channels))+'B'))
        self.value_offsets=list(self.r(self.r(self.manager+0x60,'Q')[0],str(len(self.channels))+'H'))
        if any(width!={1:12,5:16,10:12}[c['type']]for width,c in zip(self.value_widths,self.channels)):raise ValueError('Original property width differs')
        size=self.value_offsets[-1]+self.value_widths[-1];self.frame=self.alloc(0xa0);self.frame_holder=self.alloc(8);self.w(self.frame_holder,'Q',self.frame)
        # Bounded loaded-property domain storage for original bitset helpers.
        # The domain size is from the actual source property manager, not a
        # fabricated gameplay mask or an invented bone hierarchy.
        range_source=self.alloc(0x80);span=self.alloc(12);self.w(span,'3I',0,0,len(self.channels));self.w(range_source+0x68,'Q',span)
        self.range_reference=self.alloc(0x20);self.w(self.range_reference+8,'I',1000);self.w(self.range_reference+0x10,'Q',range_source+0x10)
        self.w(self.frame+8,'I',1000);self.w(self.frame+0x10,'Q',self.range_reference)
        self.w(self.frame+0x18,'Q',self.bitset(all_values=True))
        active=self.alloc(0x28);ids=self.alloc(len(self.channels)*2);self.w(ids,str(len(self.channels))+'H',*range(len(self.channels)));self.w(active+0x10,'3Q',ids,ids+len(self.channels)*2,ids+len(self.channels)*2)
        self.w(self.frame+0x30,'Q',active);self.w(self.frame+0x58,'2I',0,size)
        self.w(self.manager+8,'I',1000);self.w(self.frame+0x48,'Q',self.manager)
        for off,source in((0x68,self.manager+0x48),(0x70,self.manager+0x60)):
            holder=self.alloc(8);self.w(holder,'Q',self.r(source,'Q')[0]);self.w(self.frame+off,'Q',holder)
        targets=self.alloc(len(self.channels)*8);self.w(targets,str(len(self.channels))+'Q',*(self.native_nodes[c['node']]for c in self.channels))
        self.w(self.frame+0x78,'Q',targets);self.w(self.frame+0x90,'Q',targets)
        self.composer=self.alloc(0x120);self.fragment(0x32f1b4,0x32f22c,X0=self.composer,X23=self.composer)
        if self.r(self.composer+0x94,'I')[0]!=0:raise ValueError('Original ordinary property-mix constructor mode differs')
        self.child_ids={};children=[];self.meta_holder=self.alloc(8);self.w(self.meta_holder,'Q',self.manager)
        for i in range(2):
            child=self.alloc(16);vt=self.alloc(0x100)+24;self.w(vt-24,'q',0);self.w(vt+0xa8,'Q',self.CHILD_META);self.w(vt+0xb0,'Q',self.CHILD_BIND);self.w(vt+0xc8,'Q',self.CHILD);self.w(child,'QI',vt,1000);holder=self.alloc(8);self.w(holder,'Q',child);children.append(holder);self.child_ids[child]=i
        self.invoke(0x330940,X0=self.composer,X1=children[1],X2=children[0])
        helper=self.alloc(0x48);values=self.alloc(len(self.channels)*4);self.w(helper+0x10,'3Q',values,values+len(self.channels)*4,values+len(self.channels)*4)
        for off in(0x30,0x38,0x40):self.w(helper+off,'Q',self.bitset(all_values=False))
        self.invoke(0x11036a0,time=0,X0=helper)
        for i,value in enumerate(report['compatible']['sourcePropertyWeights']):self.invoke(0x110c954,time=value,X0=helper,W1=i)
        holder=self.alloc(8);self.w(holder,'Q',helper);self.invoke(0x118f630,X0=self.composer,X1=holder)
        for off in(0xa0,0xa8,0xb0):self.w(self.composer+off,'Q',self.bitset(all_values=False))
        self.w(self.composer+0xb8,'B',1);self.w(self.composer+0xbc,'8i',*report['compatible']['cachedSpecialIndices']);self.w(self.composer+0xfa,'B',0)
        self.setter_calls=[];self.combination_calls=[]
        return {'properties':len(self.channels),'sourceValueBytes':size,'sourceWidthOffsetsReadFromOriginalManager':True,'originalComposerConstructionExecuted':True,'completeFrameContextFactoryExecuted':False}

    def own_values(self,name,age_ms,ranges):
        if name not in ranges or not isinstance(age_ms,(int,float))or not math.isfinite(age_ms)or not 0<=age_ms<=ranges[name]['endMs']-ranges[name]['startMs']:raise ValueError('Explicit bounded own original clip clock required')
        result=self.pose(ranges[name]['startMs']+age_ms)
        if [(v['node'],v['type'])for v in result['samples']]!=[(c['node'],c['type'])for c in self.channels]:raise ValueError('Native source sampler order differs')
        return [p['value']for p in result['samples']]

    def mix_loaded_values(self,current,previous,weights):
        if previous is None:
            if weights!=[1.,0.]:raise ValueError('Missing original previous child with nonzero weight')
            return current
        values=self.alloc(32);factors=self.alloc(8);out=self.alloc(16);self.w(factors,'2f',*weights);result=[]
        for i,(a,b)in enumerate(zip(current,previous)):
            self.w(values,str(len(a)+len(b))+'f',*(a+b))
            self.invoke(0x11894f8,X0=self.composer+0x48,W1=i,X2=values,X3=factors,W4=2,X5=out,X6=self.frame_holder)
            result.append(list(self.r(out,str(len(a))+'f')))
        return result

    def compose_packet(self,packet,profile):
        checked_queue_packet(packet,profile)
        if profile['nativeSHA256']!=hashlib.sha256(self.image.data).hexdigest()or profile['species']['dataSHA256']!=self.mask_report['bodyDataSHA256']:raise ValueError('Original queue, native image and exact body must agree')
        layers=[]
        for i,row in enumerate(packet['layers']):
            weights=row.get('weights');current=row.get('current');previous=row.get('previous')
            values=self.own_values(current['clip'],current['ageMs'],profile['species']['ranges'])
            old=self.own_values(previous['clip'],previous['ageMs'],profile['species']['ranges'])if previous else None
            layers.append(self.mix_loaded_values(values,old,weights))
        result=self.compose_values(layers);result.update({'sourceQueuePacket':packet,'sourceMotion':packet['sourceMotion'],'intraLayerPropertyMixCPU':True,'ordinaryMixModeFromOriginalConstructor':0});return result

    def compose_values(self,layers):
        if len(layers)!=2 or any(len(v)!=len(self.channels)for v in layers):raise ValueError('Two complete original property arrays required')
        for values in layers:
            for v,c in zip(values,self.channels):
                if len(v)!={1:3,5:4,10:3}[c['type']]or not all(math.isfinite(x)for x in v):raise ValueError('Original property width/value differs')
        self.layer_samples=layers;self.setter_calls=[];self.combination_calls=[];self.child_calls=[];self.compose_active=True
        try:self.invoke(0x372318,time=0,X0=self.composer,X1=self.frame_holder,X2=0)
        except Exception as error:raise RuntimeError('Source composition stopped at '+hex(self.get('PC'))+' LR='+hex(self.get('X30')))from error
        finally:self.compose_active=False
        self.propagate();rows=[]
        for c in self.channels:
            node=self.native_nodes[c['node']];typ=c['type']
            if typ not in(1,5):raise ValueError('Unrecovered source target getter type')
            offset={1:0xa8,5:0xb4}[typ]
            rows.append({'node':c['node'],'type':typ,'value':list(self.r(node+offset,'4f'if typ==5 else'3f'))})
        names=sorted({name for s in self.data['rig']['skins']for name in s['boneNames']})
        return {'format':FORMAT,'nativeSHA256':self.mask_report['nativeSHA256'],'sourceBodyDataSHA256':self.mask_report['bodyDataSHA256'],'sourceMaskSHA256':self.mask_report['sha256'],'properties':rows,'allSkinBoneWorldMatrices':{n:list(self.r(self.native_nodes[n]+0x28,'16f'))for n in names},'nativeBoneMatrices':self.palette_case(),'originalSetterCalls':list(self.setter_calls),'originalCombinationCalls':list(self.combination_calls),'loadedChildPublications':list(self.child_calls),'originalFullCompositionEntryExecuted':True,'originalGPUExecuted':False,'completeFrameContextFactoryExecuted':False}
