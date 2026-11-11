"""Original single-channel queue and timed completion on supplied source tracks.

Resource/GPU construction is deliberately bypassed at its boundary. The host
provides loaded-track metadata; queue decisions, record copies, time and finish
callbacks execute the original CPU instructions. Audio markers remain absent.
"""
from source_animation_blending import SourceAnimationBlending


class SourceStopQueue(SourceAnimationBlending):
    ROW=0x30000a00

    def __init__(self,image):
        self.queue_native=False;self.queue_selection=False
        super().__init__(image)
        from unicorn import UC_HOOK_CODE
        for a in [self.ROW,0x1de9d0c,0xa2e108,0x9e9314,0x32f14c,0x32ffcc]:
            self.uc.hook_add(UC_HOOK_CODE,self.hook,begin=a,end=a)
        self.names={};self.requests=[]

    def string(self,raw):
        if raw not in self.names:
            p=self.alloc(len(raw)+25);self.w(p,'2Qi',len(raw),len(raw),1000000)
            self.uc.mem_write(p+24,raw+b'\0');self.names[raw]=p+24
        return self.names[raw]

    def hook(self,uc,a,n,data):
        if self.queue_native:
            name=self.imports.get(a)
            if a==0x1de8970:
                self.w(self.get('X0'),'Q',self.string(bytes(uc.mem_read(self.get('X1'),self.get('X2')))))
            elif a==0x1de9d0c:self.w(self.get('X0'),'Q',self.r(self.get('X1'),'Q')[0])
            elif a==self.ROW:
                row=self.blending_profile['actions'][str(self.get('W1'))];p=self.get('X2')
                self.w(p,'IQIIIIfI',row['anim_id'],self.string(row['anim_name'].encode()),row['loop'],row['weapon_state'],row['freeze_start_time'],row['blend_time'],row['play_speed'],row['combination']);self.set('W0',1)
            elif a==0x9e9314:
                self.requests.append({'kind':'play','name':self.cstr(self.get('X2')).decode(),'channel':self.get('W1'),'flags':self.get('W3'),'speed':self.gf('S0'),'begin':self.gf('S1'),'blend':self.gf('S2')})
            elif a==0xa2e108:
                p=self.get('X2');flags,speed,begin,blend=self.r(p+8,'I3f')
                self.requests.append({'kind':'default','name':self.cstr(self.r(p,'Q')[0]).decode(),'channel':self.get('W1'),'flags':flags,'speed':speed,'begin':begin,'blend':blend})
            elif name=='fmodf':
                import math
                self.sf('S0',math.fmod(self.gf('S0'),self.gf('S1')))
            elif name in ('strcmp','strncmp','strcasecmp','strstr','strncpy'):
                x,y=self.cstr(self.get('X0')),self.cstr(self.get('X1'))
                if name=='strncpy':
                    count=self.get('X2');uc.mem_write(self.get('X0'),(y+b'\0'*count)[:count])
                elif name=='strstr':
                    at=x.find(y);self.set('X0',self.get('X0')+at if at>=0 else 0)
                else:
                    if name=='strncmp':x,y=x[:self.get('X2')],y[:self.get('X2')]
                    if name=='strcasecmp':x,y=x.lower(),y.lower()
                    self.set('W0',((x>y)-(x<y))&0xffffffff)
            elif a==0x32f14c and self.queue_selection:
                # The next instruction calls 32e4cc, the original resource
                # loader. Stop that path; publish only the selected CPU record.
                self.selected=bytes(uc.mem_read(self.get('SP')+0x60,0x58))
                if self.r(self.get('SP')+0xb0,'Q')[0]:raise ValueError('Unrecovered per-clip event provider')
                self.set('PC',0x32ff08);return
            elif a==0x32ffcc and self.queue_selection:
                # Original current-record copy and flag writes completed.
                # Resource attachment/bone graphs/GPU are not performed here.
                # Rejoin before the original guard-register reload/cleanup;
                # no optional marker event was supplied at this boundary.
                self.set('X8',0);self.set('PC',0x3302a0);return
            else:return super().hook(uc,a,n,data)
            self.set('PC',self.get('X30'));return
        return super().hook(uc,a,n,data)

    def load_stop_queue(self,profile):
        if profile['format']!='oc2-source-stop-queue-v1' or profile['nativeSHA256']!=self.image_hash():raise ValueError('Original stop queue profile differs')
        self.stop_profile=profile
        return {'sourceStopQueueCPU':True,'sourceTimedCompletionCPU':True,'originalModelAnimationLoader':False,'originalTwoChannelAnimation':False}

    def queue_actor(self,actor):
        if 'stopQueue'in actor:return actor['stopQueue']
        e=self.alloc(0x700);owner=self.alloc(0x100);metadata=self.alloc(0x200)
        self.w(owner+8,'Q',metadata);self.w(owner+0x14,'B',1)
        self.original_fragment(0x32bcac,0x32be9c,{'X0':e,'X1':owner})
        self.call(0x32c14c,{'X0':e,'W1':1}) # Explicit one-channel inspection host.
        controller=self.alloc(0xc0);self.w(controller,'Q',actor['address']);self.w(controller+0xa8,'Q',self.r(0x2504cc8,'Q')[0]+24)
        provider=self.alloc(0x40);vt=self.alloc(0x40);self.w(provider,'Q',vt);self.w(vt+0x18,'Q',self.ROW)
        record=self.alloc(0x50);node=self.alloc(0xd8);weights=self.alloc(8);holder=self.alloc(8)
        self.w(node+0x48,'2Q',weights,weights+4);self.w(weights,'2f',1,0);self.w(node+0x90,'I',1);self.w(holder,'Q',node)
        q={'engine':e,'controller':controller,'provider':provider,'record':record,'key':None,'control':None,'current':None,'previous':None,'sequence':0,'blendNode':node,'weights':weights,'holder':holder,'completions':0}
        actor['stopQueue']=q;return q

    def request_pair(self,actor,q,pair):
        d=actor['display'];self.requests=[];self.queue_native=True
        try:
            got=0
            if pair[0]==-1:
                # a4cc8c -> a4d638 -> 331b30/331b20. The model wrappers
                # only unwrap engine+a8; run their original CPU targets here.
                self.call(0x32d9e0,{'X0':q['engine'],'W1':0xffffffff})
                self.call(0x32d978,{'X0':q['engine'],'W1':0xffffffff})
            for primary,action in [(1,pair[0]),(0,pair[1])]:
                if action<=0:continue
                got=self.call(0xa4d6c8,{'X0':q['controller'],'W1':primary,'X2':q['record'],'X3':d['animation'],'W4':1,'W5':action,'W6':got,'X7':q['provider']})
            requests=list(self.requests)
            for request in requests:
                if request['channel']not in (0,0xffffffff):raise ValueError('Unrecovered original animation channel')
                config=self.alloc(0x30);self.w(config,'QI3f3Q',self.string(request['name'].encode()),request['flags'],request['speed'],request['begin'],request['blend'],0,0,0)
                if request['kind']=='default':self.call(0x32e9dc,{'X0':q['engine'],'W1':0,'X2':config})
                else:
                    self.original_fragment(0xa2dd68,0xa2dd78,{'X21':config+8})
                    stored=self.alloc(0x58);self.call(0x32b518,{'X0':stored,'X1':config});self.call(0x32d58c,{'X0':q['engine'],'W1':0,'X2':stored})
        finally:self.queue_native=False
        return requests

    def select_queue(self,q,milliseconds):
        self.queue_native=self.queue_selection=True;self.selected=None
        try:self.call(0x330d0c,{'X0':q['engine'],'W1':milliseconds})
        finally:self.queue_native=self.queue_selection=False
        if not self.selected:return
        self.bind_selected(q,self.selected)

    def bind_selected(self,q,selected,channel=0,control=None):
        name=selected[:64].split(b'\0')[0].decode()
        if name not in self.stop_profile['ranges']:raise ValueError('Original selected track missing')
        old=q['control'];q['previous']=q['current']
        if old:self.original_fragment(0x32fd74,0x32fd78,{'X21':old})
        if control is None:
            owner=self.alloc(0x90);self.original_fragment(0x1189f74,0x118a060,{'X19':owner});control=self.r(owner+0x18,'Q')[0]
        r=self.stop_profile['ranges'][name];table=self.alloc(32);self.w(table,'IiQ4I',1,4,self.string(r['sourceName'].encode()),r['startMs'],r['endMs'],r['originMs'],0)
        self.call(0x1196824,{'X0':control,'X1':table})
        import struct
        flags,speed,begin,blend=struct.unpack_from('<I3f',selected,64)
        self.call(0x11967dc,{'X0':control,'W1':(flags>>4)&1});self.w(control+0x34,'f',speed)
        if begin>0:self.call(0x1196234,{'X0':control},{'S0':r['startMs']+begin})
        self.original_fragment(0x32fe58,0x32fe68,{'X19':q['engine'],'X27':channel,'X23':control})
        q['control']=control;q['current']={'clip':name,'ageMs':0,'loop':bool(flags&0x10),'control':control,'startMs':r['startMs']};q['sequence']+=1
        self.blend_start(q,blend,2 if q['previous']else 1)

    def display_tick(self,actor,moving,milliseconds):
        state=super().display_tick(actor,moving,milliseconds);q=self.queue_actor(actor);d=actor['display']
        words=state['cachedWords'];pair=self.blending_profile['stateActions'].get(str(words[0]|words[1]))
        if pair is None or self.r(d['animation']+0x1d0,'2i')!=(0,0):return state
        key=tuple(words);requests=[]
        if key!=q['key']:requests=self.request_pair(actor,q,pair);q['key']=key
        self.select_queue(q,milliseconds)
        before=self.r(q['engine']+0x10,'B')[0]
        self.queue_native=True
        try:
            for p in [q['current'],q['previous']]:
                if p:
                    self.call(0x11962c0,{'X0':p['control']},{'S0':milliseconds});p['ageMs']=self.r(p['control']+8,'f')[0]-p['startMs']
        finally:self.queue_native=False
        after=self.r(q['engine']+0x10,'B')[0]
        if not(before&1)and after&1:q['completions']+=1
        weights=self.blend_tick(q,milliseconds)
        clean=lambda p:{k:v for k,v in p.items()if k not in ('control','startMs')}if p else None
        state.pop('reason',None)
        return {**state,'available':True,'primaryQueueRestored':False,'originalTwoChannelAnimation':False,'sequence':q['sequence'],'current':clean(q['current']),'previous':clean(q['previous']),'weights':weights,'durationMs':self.r(q['blendNode']+0xb4,'I')[0],'remainingMs':self.r(q['blendNode']+0xb8,'I')[0],'nativeBlendCPU':True,'nativeQueueCPU':True,'nativeTimedCompletionCPU':True,'pending':self.r(q['engine']+0x2fa,'b')[0],'completionCount':q['completions'],'requests':requests}
