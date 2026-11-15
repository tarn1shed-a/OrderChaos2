"""Trace each exact fresh UI tuple through the original player body refresh.

The empty equipment and player wrapper are explicit compatibility inputs. They
do not claim original server creation properties, equipment or model completion.
"""
import hashlib
import json
from player_choice_matrix import ROOT, RAW


def recover(image, source):
    from map_loading_evidence import Sources
    from tutorial_npc_robe_probe import RobeProbe
    from native_default_underwear import verify
    verify(image)
    matrix=json.loads((RAW/'matrix-source-v1.json').read_text())
    sources=Sources(source)

    class Probe(RobeProbe):
        def hook(self,uc,at,size,data):
            if at==0x9d4c48 and self.mode=='choice-world':
                value=self.get('X1')
                self.result={'slots':list(self.r(value,'37I')),'modelId':self.get('W2'),
                    'sourceColorAt9c':self.r(value+0x9c,'I')[0],'sourceColorAta0':self.r(value+0xa0,'I')[0],
                    'weapons':list(self.r(value+0x94,'2I')),
                    'requestArgs':[self.get('W3'),self.get('W4'),self.cstr(self.get('X5')).decode(),self.get('W6')]}
                self.set('PC',self.EXIT);return
            return super().hook(uc,at,size,data)

        def appearance(self,body,draft):
            actor,attrs,wrapper=self.alloc(0x2000),self.alloc(0x1000),self.alloc(0x200)
            self.w(actor,'Q',0x24228a8);self.w(actor+0x18,'Q',attrs);self.w(actor+0x38,'Q',wrapper)
            self.w(wrapper+8,'I',1000);self.w(0x2528df8,'Q',self.alloc(0x200))
            values={0:0x20a,0x280:draft['displayId'],0x400:draft['skinColorWord'],0x410:draft['hairColorWord'],
                0x418:draft['face'],0x408:draft['hair'],0x420:draft['beard']}
            offsets=(0,0x240,0x280,0x318,0x320,0x330,0x348,0x340,0x400,0x408,0x410,0x418,0x420,
                0x428,0x430,0x438,0x380,0x388,0x390,0x398,0x3c0,0x3c8,0x358,0x368)
            for off in offsets:self.call(0xa9995c,{'X0':attrs+off,'W1':values.get(off,0)})
            self.mode,self.result,self.lookup_calls='choice-world',None,[]
            try:self.call(0x900234,{'X0':actor,'X1':wrapper,'W2':0,'W3':0,'W4':0,'W5':0})
            finally:self.mode=None
            if not self.result or self.result['modelId']!=body['sourceModel']['ID']:
                raise ValueError('Original player refresh did not retain its selected body')
            result={**self.result,'tableLookups':list(self.lookup_calls)}
            self.body_path=body['sourceModel']['ModelPath']
            requests=[self.feature(slot,value,draft['face']) for slot,value in enumerate(self.result['slots']) if slot<7 or value]
            colors={}
            for label,key in [('skin','skinColorWord'),('hair','hairColorWord')]:
                destination=self.alloc(12);self.call(0x9d3dc8,{'W0':draft[key],'X1':destination});colors[label]=list(self.r(destination,'3f'))
            return {'parts':result,'resourceRequests':requests,'sourceColors':colors,
                    'originalPlayerRefreshEntry':'0x900234','bodyHandoff':'0x9d4c48',
                    'featureConsumer':'0x9d64e8','colorConsumer':'0x9d3dc8',
                    'explicitEmptyEquipment':True,'sourceServerInitialEquipmentKnown':False,
                    'explicitKindAttribute0':'0x20a','modelCompletionSupplied':False}

        def feature(self,slot,value,face):
            owner,holder,model,vt=self.alloc(256),self.alloc(8),self.alloc(256),self.alloc(64)
            self.w(owner+0x40,'Q',holder);self.w(holder,'Q',model);self.w(model,'Q',vt);self.w(vt+0x10,'Q',self.MODEL_KIND)
            self.w(model+0x90,'Q',self.cpp_string(self.body_path.encode()));self.w(owner+0x4c,'I',face)
            self.weapon_mode,self.resource_request='resource',None;self.lookup_calls,self.exists_queries=[],[]
            try:self.call(0x9d64e8,{'X0':owner,'W1':slot,'W2':value,'W3':1})
            finally:self.weapon_mode=None
            if self.resource_request is None:raise ValueError('Original feature request boundary not reached')
            request={**self.resource_request,'inputValue':value,'tableLookups':list(self.lookup_calls),'sourceExistsQueries':list(self.exists_queries)}
            request['sourceResourceCandidates']=len(self.sources.candidates(request['path'])) if request.get('path') else 0
            return request

    p=Probe(image,sources);rows=[]
    for body in matrix['bodyChoices']:
        for choice in body['choices']:
            draft=choice['stages'][1]['freshAppearance']
            rows.append({'uiRace':body['uiRace'],'gender':body['gender'],'profession':choice['profession'],
                         'sourceModelId':body['sourceModel']['ID'],'draft':draft,**p.appearance(body,draft)})
    return {'format':'oc2-original-player-choice-world-source-v1','nativeSHA256':hashlib.sha256(image.data).hexdigest(),
            'choices':rows,'sourceProofs':sources.proofs,'originalCodeExecuted':True,
            'createsOriginalOrCompatibleRole':False,'sourceGPUOrGeometrySamplingClaimed':False,'savesReadOrWritten':False}


if __name__=='__main__':
    from analyze_native_resources import NativeImage
    from resource_packs import DEFAULT_SOURCE
    output=RAW/'world-appearance-source-v1.json'
    if output.exists():raise ValueError('Preserve existing original world-choice proof')
    result=recover(NativeImage((ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so').read_bytes()),DEFAULT_SOURCE)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'choices':len(result['choices']),
        'unresolvedNonemptyRequests':[(r['uiRace'],r['gender'],r['profession'],q['path'],q['sourceResourceCandidates']) for r in result['choices']for q in r['resourceRequests']if q.get('path')and q['sourceResourceCandidates']!=1],
        'nonzeroSourceClothingSlots':[(r['uiRace'],r['gender'],r['profession'],r['parts']['slots'][3:])for r in result['choices']if any(r['parts']['slots'][3:])]}))
