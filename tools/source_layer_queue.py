"""Two source queues with explicit scalar-track views, never invented bone masks."""
import struct
from source_stop_queue import SourceStopQueue
from source_animation_blending import SourceAnimationBlending
from source_physics import f32
from layer_queue_assets import FORMAT


class SourceLayerQueue(SourceStopQueue):
    def __init__(self,image):
        self.layers_native=False;self.layer_active=None
        super().__init__(image)
        from unicorn import UC_HOOK_CODE
        for a in [0x32f17c,0x32c9dc,0x331c94]:self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=a,end=a)

    def hook(self,uc,a,n,data):
        if self.queue_native and a==0x331c94:
            name=self.cstr(self.get('X2')).decode()
            if name not in self.layer_profile['sourceClipNames']:raise ValueError('Unrecovered original clip availability '+name)
            self.set('W0',1);self.set('PC',self.get('X30'));return
        if self.queue_native and self.imports.get(a)=='sprintf':
            fmt=self.cstr(self.get('X1'))
            if fmt!=b'%s':raise ValueError('Unrecovered layer formatting '+repr(fmt)+' caller '+hex(self.get('X30')))
            raw=self.cstr(self.get('X2'));uc.mem_write(self.get('X0'),raw+b'\0');self.set('W0',len(raw));self.set('PC',self.get('X30'));return
        if self.layers_native and self.queue_selection and a==0x32f14c:
            channel=self.get('W20');record=bytes(uc.mem_read(self.get('SP')+0x60,0x58));name=record[:64].split(b'\0')[0].decode()
            if self.r(self.get('SP')+0xb0,'Q')[0]:raise ValueError('Unrecovered layer event provider')
            if(channel,name)not in self.prepared:raise ValueError('Unrecovered layer track resource')
            self.publishing[channel]=self.prepared[channel,name];self.set('PC',0x32f16c);return
        if self.layers_native and self.queue_selection and a==0x32f17c:
            self.selections.append((self.get('W20'),bytes(uc.mem_read(self.get('SP')+0x60,0x58))))
            self.set('PC',0x32ff08);return
        if self.layers_native and a==0x32c9dc:
            # The original clock getter consumes the supplied loaded-track
            # view: current native clock minus native range start. This is a
            # scalar host interface, not an original model/bone graph.
            channel=self.get('W1');layer=self.layer_active['layers'][channel];control=self.publishing.get(channel)or layer['control']
            self.sf('S0',f32(self.r(control+8,'f')[0]-self.r(control+0x20,'f')[0])if control else -1)
            self.set('PC',self.get('X30'));return
        return super().hook(uc,a,n,data)

    def load_layer_queue(self,profile):
        if profile.get('format')!=FORMAT or profile['nativeSHA256']!=self.image_hash()or profile['engineFlags']!=3:raise ValueError('Unknown original model layer profile')
        self.layer_profile=profile
        return {'sourceLayerQueueCPU':True,'sourcePriorityQueryCPU':True,'sourceChannels':2,'distinctPoseCompositionRestored':False,'originalModelAnimationLoader':False}

    def queue_actor(self,actor):
        q=super().queue_actor(actor)
        if'layers'in q:return q
        self.call(0x32c14c,{'X0':q['engine'],'W1':self.layer_profile['engineFlags']})
        view=self.alloc(0x180);self.w(view+0xa8,'Q',q['engine']);q['view']=view
        second={k:q[k]for k in ['engine','controller','provider','record']}
        for k in ['control','current','previous']:second[k]=None
        second.update(sequence=0,completions=0)
        node=self.alloc(0xd8);weights=self.alloc(8);holder=self.alloc(8);self.w(node+0x48,'2Q',weights,weights+4);self.w(weights,'2f',1,0);self.w(node+0x90,'I',1);self.w(holder,'Q',node)
        second.update(blendNode=node,weights=weights,holder=holder);q['layers']=[q,second]
        # Execute the original root's child order and initial weights on
        # explicitly supplied reference-counted scalar containers.
        root=self.alloc(0x120);pointers=self.alloc(16);w=self.alloc(8);aux=self.alloc(8);vt=self.alloc(0x40)+24;self.w(vt-24,'q',0)
        children=[]
        for _ in range(2):
            child=self.alloc(0x20);self.w(child,'QI',vt,100);holder=self.alloc(8);self.w(holder,'Q',child);children.append(holder)
        self.w(root+0x78,'3Q',pointers,pointers,pointers+16);self.w(root+0x48,'3Q',w,w+8,w+8);self.w(root+0x60,'3Q',aux,aux+8,aux+8)
        self.call(0x330940,{'X0':root,'X1':children[1],'X2':children[0]});q['layerWeights']=list(self.r(w,'2f'))
        return q

    def priority_query(self,actor,q,action=0xffffffff):
        at=actor['address'];saved=self.r(at+0x38,'Q')[0];self.w(at+0x38,'Q',q['view']);self.queue_native=True
        try:return self.call(0xa50148,{'X0':q['controller'],'W1':action})&0xffffffff
        finally:self.queue_native=False;self.w(at+0x38,'Q',saved)

    def request_pair(self,actor,q,pair):
        d=actor['display'];self.requests=[];self.queue_native=True;at=actor['address'];saved=self.r(at+0x38,'Q')[0];self.w(at+0x38,'Q',q['view'])
        try:
            got=0
            if pair[0]==-1:
                self.call(0x331b30,{'X0':q['view'],'W1':0xffffffff});self.call(0x331b20,{'X0':q['view'],'W1':0xffffffff})
            for primary,action in [(1,pair[0]),(0,pair[1])]:
                if action>0:got=self.call(0xa4d6c8,{'X0':q['controller'],'W1':primary,'X2':q['record'],'X3':d['animation'],'W4':1,'W5':action,'W6':got,'X7':q['provider']})
            requests=list(self.requests)
            for request in requests:
                if request['channel']not in (0,1,0xffffffff):raise ValueError('Unrecovered animation priority result')
                config=self.alloc(0x30);self.w(config,'QI3f3Q',self.string(request['name'].encode()),request['flags'],request['speed'],request['begin'],request['blend'],0,0,0)
                if request['kind']=='play':
                    self.original_fragment(0xa2dd68,0xa2dd78,{'X21':config+8});self.call(0x331a28,{'X0':q['view'],'W1':request['channel'],'X2':config})
                else:self.call(0x331cf8,{'X0':q['view'],'W1':request['channel'],'X2':config})
        finally:self.queue_native=False;self.w(at+0x38,'Q',saved)
        return requests

    def select_queue(self,q,milliseconds):
        self.prepared=q.setdefault('preparedPool',{});self.publishing={};self.selections=[];self.layer_active=q
        for channel in range(2):
            names={self.cstr(q['engine']+0x5a0+channel*0x58).decode()}
            base=q['engine']+channel*0x218;head,count=self.r(base+0x2f8,'b')[0],self.r(base+0x2fa,'b')[0]
            for i in range(count):names.add(self.cstr(base+0xe8+((head+i)%6)*0x58).decode())
            for name in names-{''}:
                if name not in self.stop_profile['ranges']:raise ValueError('Original layer track absent')
                if(channel,name)in self.prepared:continue
                owner=self.alloc(0x90);self.original_fragment(0x1189f74,0x118a060,{'X19':owner});c=self.r(owner+0x18,'Q')[0];r=self.stop_profile['ranges'][name];table=self.alloc(32)
                self.w(table,'IiQ4I',1,4,self.string(r['sourceName'].encode()),r['startMs'],r['endMs'],r['originMs'],0);self.call(0x1196824,{'X0':c,'X1':table});self.prepared[channel,name]=c
        self.queue_native=self.queue_selection=self.layers_native=True
        try:self.call(0x330d0c,{'X0':q['engine'],'W1':milliseconds})
        finally:self.queue_native=self.queue_selection=self.layers_native=False
        for channel,record in self.selections:
            name=record[:64].split(b'\0')[0].decode();self.bind_selected(q['layers'][channel],record,channel,self.prepared.pop((channel,name)))

    def display_tick(self,actor,moving,milliseconds):
        state=SourceAnimationBlending.display_tick(self,actor,moving,milliseconds);q=self.queue_actor(actor);d=actor['display'];words=state['cachedWords'];pair=self.blending_profile['stateActions'].get(str(words[0]|words[1]))
        if pair is None or self.r(d['animation']+0x1d0,'2i')!=(0,0):return state
        requests=[];key=tuple(words)
        if key!=q['key']:requests=self.request_pair(actor,q,pair);q['key']=key
        self.select_queue(q,milliseconds);layers=[];self.queue_native=True
        try:
            for channel,layer in enumerate(q['layers']):
                before=self.r(q['engine']+0x10+channel*4,'B')[0]
                for p in [layer['current'],layer['previous']]:
                    if p:self.call(0x11962c0,{'X0':p['control']},{'S0':milliseconds});p['ageMs']=self.r(p['control']+8,'f')[0]-p['startMs']
                after=self.r(q['engine']+0x10+channel*4,'B')[0]
                if not(before&1)and after&1:layer['completions']+=1
                clean=lambda p:{k:v for k,v in p.items()if k not in ('control','startMs')}if p else None
                layers.append({'channel':channel,'current':clean(layer['current']),'previous':clean(layer['previous']),'sequence':layer['sequence'],'weights':self.blend_tick(layer,milliseconds),'durationMs':self.r(layer['blendNode']+0xb4,'I')[0],'remainingMs':self.r(layer['blendNode']+0xb8,'I')[0],'completionCount':layer['completions']})
        finally:self.queue_native=False
        same=all(layers[0][k]==layers[1][k]for k in ['current','previous','weights','remainingMs'])
        state.pop('reason',None)
        result={**state,'sourceChannels':2,'nativeLayerQueueCPU':True,'nativePriorityQueryCPU':True,'layerRootWeights':q['layerWeights'],'layers':layers,'layerPoseAgreement':same,'distinctPoseCompositionRestored':False,'prioritySelection':self.priority_query(actor,q),'originalTwoChannelAnimation':False,'requests':requests}
        if not same:return{**result,'available':False,'reason':'distinct-track-bone-composition-not-recovered'}
        return{**result,**{k:v for k,v in layers[0].items()if k!='channel'},'available':True,'nativeQueueCPU':True,'nativeTimedCompletionCPU':True,'nativeBlendCPU':True}
