"""ElfMale33 own82-property original composition; no borrowed body/action."""
import copy
import hashlib
import json
import math
from pathlib import Path
from types import FunctionType,MappingProxyType
from character_human_queue_fast_probe import FastHumanCompositionProbe,DISPATCH
from character_human_queue_composition_probe import HumanCompositionProbe
from character_human_queue_bones_probe import mask_hash
from bdae_character import aliases

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'analysis/raw/player-choice-elf-male-20261115'
BASE=ROOT/'analysis/raw/character-elf-male-world-20261115/candidate-v2'
NATIVE='77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4'
MODEL='model/npc/character/elf/male/oc2_elf_m_body_01.bdae'
ANIMATION='model/npc/character/elf/male/anim/animations.bdae'

def canonical(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def bind_elf_mask(report,data):
    if report.get('format')!='oc2-source-elf-male-layer-mask-v1' or report.get('sha256')!=mask_hash(report) or \
      report.get('nativeSHA256')!=NATIVE or report.get('bodyDataCanonicalSHA256')!=canonical(data) or \
      report.get('sourceModelId')!=33 or data.get('source')!=MODEL or report.get('compatible',{}).get('propertiesCompatible')is not True:
        raise ValueError('Exact original ElfMale33 property mask required')
    names=aliases(data['rig']['nodes']);order=report['sourcePropertyOrder'];weights=report['compatible']['sourcePropertyWeights']
    if len(order)!=82 or len(weights)!=82:raise ValueError('Own complete82 elf properties required')
    result=[]
    for i,(row,weight)in enumerate(zip(order,weights)):
        if row['index']!=i or row['node']not in names or row['type']not in(1,5,10) or weight not in(0.,.5,1.):
            raise ValueError('Uncovered own elf property target')
        result.append({'sourcePropertyIndex':i,'node':names[row['node']],'sourceNode':row['node'],
            'sourceType':row['type'],'originalPropertyWeight':weight})
    return result

class ElfCompositionProbe(FastHumanCompositionProbe):
    def prepare_elf(self,data,report):
        method=HumanCompositionProbe.prepare_composition
        scope={**method.__globals__,'MASK':self.elf_mask_file,'bind_original_mask':bind_elf_mask}
        result=FunctionType(method.__code__,scope)(self,data)
        if result['properties']!=82 or self.mask_report!=report:raise ValueError('Own elf source setup differs')
        return result

    def bind_elf_profile(self,profile):
        from species_world_profiles import validate_profile
        validate_profile(profile,NATIVE)
        if hasattr(self,'bound_motion') or profile.get('sourceModelId')!=33 or profile.get('race')!=1 or profile.get('gender')!=0 or \
          profile['dataSHA256']!=self.mask_report['bodyDataSHA256'] or hashlib.sha256(self.image.data).hexdigest()!=NATIVE:
            raise ValueError('Own elf ranges/body agreement required')
        self.bound_motion=MappingProxyType({k:profile[k]for k in('format','sha256','key','race','gender','sourceModelId')})
        self.bound_ranges=MappingProxyType({name:MappingProxyType(copy.deepcopy(row))for name,row in profile['ranges'].items()})
        self.bound_profile_sha256=profile['sha256'];self.sample_cache.clear()

    def prepare_batch(self):
        if getattr(self,'batch_prepared',False)or not hasattr(self,'frame')or len(self.channels)!=82:
            raise ValueError('Prepare own82-property composer once')
        self.dispatch_base=0x30000400;self.uc.mem_write(self.dispatch_base,DISPATCH)
        n=len(self.channels);self.sample_rows=self.alloc(n*32);self.sample_output=self.alloc(n*16)
        contexts=self.alloc(n*24);states=self.alloc(n*16);indexes=self.alloc(n*4)
        for i,row in enumerate(self.channels):
            context=contexts+i*24;self.w(context,'3Q',row['record'],0,states+i*16)
            self.w(self.sample_rows+i*32,'4Q',row['object'],context,self.sample_output+i*16,indexes+i*4)
        self.mix_rows=self.alloc(n*24);self.mix_values=self.alloc(n*32);self.mix_factors=self.alloc(8);self.mix_output=self.alloc(n*16)
        for i in range(n):self.w(self.mix_rows+i*24,'3Q',self.mix_values+i*32,self.mix_factors,self.mix_output+i*16)
        self.batch_prepared=True

    def compose_values(self,layers):
        if len(layers)!=2 or any(len(v)!=82 for v in layers):raise ValueError('Two own complete82-property layers required')
        for values in layers:
            for value,c in zip(values,self.channels):
                if len(value)!={1:3,5:4,10:3}[c['type']]or not all(math.isfinite(v)for v in value):
                    raise ValueError('Own original property width/value differs')
        self.layer_samples=layers;self.setter_calls=[];self.combination_calls=[];self.child_calls=[];self.compose_active=True
        try:self.invoke(0x372318,time=0,X0=self.composer,X1=self.frame_holder,X2=0)
        except Exception as error:raise RuntimeError('Own elf source composition stopped at '+hex(self.get('PC')))from error
        finally:self.compose_active=False
        self.propagate();rows=[]
        # Scale type10 really dispatches1167f10 -> node.v158=1363f18;
        # that original setter writes c4/c8/cc. Source+fixture receipt retained.
        for c in self.channels:
            offset={1:0xa8,5:0xb4,10:0xc4}[c['type']];node=self.native_nodes[c['node']]
            rows.append({'node':c['node'],'type':c['type'],'value':list(self.r(node+offset,'4f'if c['type']==5 else'3f'))})
        names=sorted({name for skin in self.data['rig']['skins']for name in skin['boneNames']})
        return {'format':'oc2-elf-male-original-composed-properties-v1','nativeSHA256':self.mask_report['nativeSHA256'],
            'sourceBodyDataSHA256':self.mask_report['bodyDataSHA256'],'sourceMaskSHA256':self.mask_report['sha256'],
            'properties':rows,'allSkinBoneWorldMatrices':{name:list(self.r(self.native_nodes[name]+0x28,'16f'))for name in names},
            'nativeBoneMatrices':self.palette_case(),'originalSetterCalls':list(self.setter_calls),
            'originalCombinationCalls':list(self.combination_calls),'loadedChildPublications':list(self.child_calls),
            'originalFullCompositionEntryExecuted':True,'originalGPUExecuted':False,'completeFrameContextFactoryExecuted':False}

def binding_id(binding):
    import struct
    description='\n'.join([binding['nativeSHA256'],binding['sourceBodyDataSHA256'],binding['sourceMaskSHA256'],binding['sourceMotion']['sha256']]+
        [f"{i}|{r['node']}|{r['sourceNode']}|{r['sourceType']}|"+struct.pack('<f',r['originalPropertyWeight']).hex()for i,r in enumerate(binding['propertyOrder'])])
    return hashlib.sha256(description.encode()).hexdigest()

class ElfPoseTransport:
    def __init__(self,binding):
        if binding.get('format')!='oc2-source-elf-male-pose-binding-v1'or binding.get('nativeSHA256')!=NATIVE or \
          binding.get('sourceMotion',{}).get('sourceModelId')!=33 or binding.get('sourceMotion',{}).get('key')!='elf-male' or \
          binding.get('properties')!=82 or binding.get('valueBytes')!=sum(16 if r['sourceType']==5 else 12 for r in binding['propertyOrder'])or \
          binding.get('bindingId')!=binding_id(binding):raise ValueError('Verified own elf pose binding required')
        self.binding=binding;self.binding_id=binding['bindingId']

    def project(self,pose,actor_key):
        import base64,struct
        b=self.binding
        if not isinstance(actor_key,str)or not 0<len(actor_key)<=128 or pose.get('sourceMotion')!=b['sourceMotion']or \
          pose.get('sourceBodyDataSHA256')!=b['sourceBodyDataSHA256']or pose.get('sourceMaskSHA256')!=b['sourceMaskSHA256']or \
          pose.get('originalFullCompositionEntryExecuted')is not True or pose.get('intraLayerPropertyMixCPU')is not True or \
          pose.get('ordinaryMixModeFromOriginalConstructor')!=0 or len(pose.get('properties',[]))!=82:
            raise ValueError('Complete own original elf composition required')
        calls=pose.get('originalSetterCalls',[])
        if len(calls)!=82 or sorted(c.get('property',-1)for c in calls)!=list(range(82))or \
          any(c.get('entry')!='0x11891f4'or c.get('source')!='original-composition'for c in calls):
            raise ValueError('All82 original target setters required')
        values=[]
        for row,target in zip(pose['properties'],b['propertyOrder']):
            v=row.get('value',[])
            if row.get('node')!=target['sourceNode']or row.get('type')!=target['sourceType']or len(v)!=(4 if row['type']==5 else 3)or \
              any(type(x)not in(int,float)or not math.isfinite(x)for x in v):raise ValueError('Own elf payload differs')
            values.extend(v)
        payload=struct.pack('<'+str(len(values))+'f',*values)
        if len(payload)!=b['valueBytes']or list(struct.unpack('<'+str(len(values))+'f',payload))!=values:
            raise ValueError('Lossless complete elf float32 values required')
        return {'format':'oc2-source-elf-male-native-pose-v1','actorKey':actor_key,'bindingId':self.binding_id,
            'valueEncoding':'float32-le-base64','valueBytes':b['valueBytes'],'values':base64.b64encode(payload).decode()}
