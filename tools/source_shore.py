"""Original normal locomotion decisions, stopped before animation dispatch.

The host supplies the existing actor/input records. A captured request is NOT
an original animation loading/priority/transition completion result.
"""
from source_diving import SourceDiving


class SourceShore(SourceDiving):
    def load_shore(self):
        return {'sourceShoreDecision': True, 'originalAnimationDispatcher': False}

    def input_guard(self, actor):
        # Execute the original entry checks: vertical acceleration, JUMP,
        # actor flags, and the supplied normal input mode. No water-depth guess.
        a=actor['address'];vt=self.r(a,'Q')[0];saved=self.r(vt+0x2b8,'Q')[0]
        self.w(vt+0x2b8,'Q',0x912ce4)
        try:
            return self.fragment(0x9e2c68,{0x9e2d10,0x9e35c8},{'X0':a,'W1':0})==0x9e2d10
        finally:self.w(vt+0x2b8,'Q',saved)

    def locomotion_decision(self, actor):
        from unicorn import UC_HOOK_CODE
        a=actor['address'];vt=self.r(a,'Q')[0];saved={off:self.r(vt+off,'Q')[0]for off in [0x2b8,0x200]}
        self.w(vt+0x2b8,'Q',0x912ce4);self.w(vt+0x200,'Q',0x912140)
        result=[]
        def stop(uc,at,size,data):
            if at in (0xa528bc,0xa3cf28):
                result.append({'posture':self.get('W1'),'boundary':hex(at)})
                self.set('PC',self.EXIT)
            # Other branches require unrecovered combat/skill context. Stop
            # explicitly instead of fabricating its provider or state success.
            elif at==0x91b198:
                result.append({'posture':None,'boundary':hex(at)})
                self.set('PC',self.EXIT)
        h=self.uc.hook_add(UC_HOOK_CODE,stop)
        try:self.call(0xa6906c,{'X0':0,'X1':actor['animation']})
        finally:
            self.uc.hook_del(h)
            for off,value in saved.items():self.w(vt+off,'Q',value)
        if result:return result[0]
        return {'posture':actor['lastPosture'],'boundary':'original-return'}

    def actor_tick(self,identity,position,velocity_xz=(0,0),milliseconds=50,jump=False,control=None):
        actor=self.actors.get(identity)or self.actor(identity,position);a=actor['address']
        self.w(actor['manager']+0x68,'Q',a);self.w(0x2528df8,'Q',actor['manager'])
        # Original 9e2c68 submits a planar vector through virtual+48 before
        # its water-direction branch. The web host supplies that vector here;
        # its original guard must pass, so real jump/fall velocity is retained.
        swimming=bool(self.call(0x90e26c,{'X0':a})&1)
        if not swimming and self.input_guard(actor):
            import math
            speed=math.hypot(*velocity_xz);v=self.scratch+0x6a00
            self.w(v,'3f',*([velocity_xz[0]/speed,0,velocity_xz[1]/speed]if speed else[0,0,0]))
            self.call(0xa2ba0c,{'X0':a,'X1':v});self.w(a+0x130,'f',speed)
        r=super().actor_tick(identity,position,velocity_xz,milliseconds,jump,control)
        # Jump/drop/landing remain the existing original physics requests. This
        # bounded selector is used only for ordinary ground/water locomotion.
        if actor['lastPosture']in (8,0x18,0x20,0x50):
            decision=self.locomotion_decision(actor)
            r['locomotionDecision']=decision
            r['locomotionPosture']=decision['posture']
        else:r['locomotionPosture']=None
        return r
