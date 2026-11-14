"""Lossless transport for completed original poses, not a new animation system."""
import base64
import hashlib
import math
import struct
NATIVE='77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4'
BODY='e6d6e16b6bed829922ebc06fbd7ff458a0ea1c4622d0fbd46a81c5493b71d783'
MASK='0d18cc2976795cbb2535f3ca73bc9e8810f18a84d6f653f075c6de370c1f25b1'
MOTION='14adc20cc5f602ab97c9f10414522a38e7590199efc90cb57dfe0868af21cada'


class FastPoseTransport:
    def __init__(self,binding):
        if not isinstance(binding,dict)or binding.get('nativeSHA256')!=NATIVE or binding.get('sourceBodyDataSHA256')!=BODY or binding.get('sourceMaskSHA256')!=MASK or binding.get('sourceMotion',{}).get('sha256')!=MOTION or any(binding['sourceMotion'].get(k)!=v for k,v in [('race',0),('gender',0),('sourceModelId',1),('key','human-male')])or binding.get('properties')!=135 or binding.get('originalComposerEntry')!='0x372318'or binding.get('serverDefaultsSupplied')is not False:raise ValueError('Exact original loaded human binding required')
        self.order=[]
        for i,row in enumerate(binding.get('propertyOrder',[])):
            if row.get('sourcePropertyIndex')!=i or type(row.get('node'))is not int or not isinstance(row.get('sourceNode'),str)or row.get('sourceType')not in(1,5)or row.get('originalPropertyWeight')not in(0.,.5,1.):raise ValueError('Original property target/order required')
            self.order.append((row['sourceNode'],row['sourceType'],row['node'],row['originalPropertyWeight']))
        if len(self.order)!=135 or sum(16 if r[1]==5 else 12 for r in self.order)!=1992:raise ValueError('Original full 1992-byte pose required')
        self.motion=dict(binding['sourceMotion'])
        description='\n'.join([NATIVE,BODY,MASK,MOTION]+[f'{i}|{r[2]}|{r[0]}|{r[1]}|'+struct.pack('<f',r[3]).hex()for i,r in enumerate(self.order)])
        self.binding_id=hashlib.sha256(description.encode('ascii')).hexdigest()

    def project(self,pose,actor_key):
        if not isinstance(actor_key,str)or not 0<len(actor_key)<=128:raise ValueError('Explicit existing host actor identity required')
        if not isinstance(pose,dict)or pose.get('format')!='oc2-human-original-composed-properties-v1'or pose.get('nativeSHA256')!=NATIVE or pose.get('sourceBodyDataSHA256')!=BODY or pose.get('sourceMaskSHA256')!=MASK or pose.get('sourceMotion')!=self.motion or pose.get('originalFullCompositionEntryExecuted')is not True or pose.get('intraLayerPropertyMixCPU')is not True or pose.get('ordinaryMixModeFromOriginalConstructor')!=0 or pose.get('originalGPUExecuted')is not False or pose.get('completeFrameContextFactoryExecuted')is not False or len(pose.get('properties',[]))!=135:raise ValueError('Completed original CPU human pose required')
        calls=pose.get('originalSetterCalls',[])
        if len(calls)!=135 or sorted(r.get('property',-1)for r in calls)!=list(range(135))or any(r.get('entry')!='0x11891f4'or r.get('source')!='original-composition'for r in calls):raise ValueError('Complete real original target writes required')
        values=[]
        for row,expected in zip(pose['properties'],self.order):
            v=row.get('value',[])
            if row.get('node')!=expected[0]or row.get('type')!=expected[1]or len(v)!=(4 if expected[1]==5 else 3)or any(type(x)not in(int,float)or not math.isfinite(x)or abs(x)>3.4028234663852886e38 for x in v):raise ValueError('Original property payload differs')
            values.extend(v)
        payload=struct.pack('<'+str(len(values))+'f',*values)
        if list(struct.unpack('<'+str(len(values))+'f',payload))!=values:raise ValueError('Only already-original float32 values may be transported losslessly')
        return {'format':'oc2-human-original-fast-pose-v1','actorKey':actor_key,'bindingId':self.binding_id,'valueEncoding':'float32-le-base64','valueBytes':1992,'values':base64.b64encode(payload).decode('ascii')}
