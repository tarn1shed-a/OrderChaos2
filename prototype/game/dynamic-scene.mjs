// Original door geometry exercises the recovered runtime registration/query path.
// Placement, lift trajectory and safe-close policy belong to this local lab.
export class DynamicScene {
  constructor(motion,now){
    this.motion=motion;this.spec=motion.profile.dynamicLab;
    if(!this.spec)throw new Error('动态碰撞验证资源缺失，请重建资源');
    const [x,y]=this.spec.logicalPosition,p=motion.point(x,y),anchor={x,y};
    // Use the same bounded ground placement as an actor. An unbounded support
    // ray would choose the temple roof above the local test location.
    motion.place(anchor);this.base=[p.x,anchor.worldY,p.z];
    this.object={id:'source-door',sourcePHY:this.spec.sourcePHY,sourceModel:this.spec.sourceModel,
      position:[...this.base],quaternion:[0,0,0,1],scale:[1,1,1],open:false,disabled:false};
    this.update(now);
  }
  update(now){
    const o=this.object,t=o.transition;
    if(t){const f=Math.max(0,Math.min(1,(now-t.at)/this.spec.transitionMs));o.position[1]=this.base[1]+t.from+(t.to-t.from)*f;if(f===1)delete o.transition;}
    this.motion.updateDynamic(o);
  }
  interact(player,id,now,actors=[]){
    const o=this.object;if(id!==o.id)return '未知交互对象';
    if(player.hp<=0)return '倒地后无法操作试验门';
    const p=this.motion.point(player.x,player.y);
    if(Math.hypot(p.x-this.base[0],p.z-this.base[2])>this.spec.interactDistance)return '靠近试验门再操作';
    if(o.transition)return '试验门正在移动';
    if(o.open){
      // Explicit web policy: reject a close through a living actor. This is not
      // evidence that the original client implemented this crush policy.
      const shape=this.motion.profile.sources[o.sourcePHY].shapes[0];
      for(const a of actors){if(a.hp<=0)continue;const at=this.motion.point(a.x,a.y),h=shape.halfExtents,c=shape.center;
        if(Math.abs(at.x-this.base[0]-c[0])<=h[0]+this.motion.margin&&Math.abs(at.z-this.base[2]-c[2])<=h[2]+this.motion.margin&&a.worldY<this.base[1]+c[1]+h[1])return '门下有人，暂不能关闭';
      }
    }
    o.open=!o.open;o.transition={at:now,from:o.position[1]-this.base[1],to:o.open?this.spec.lift:0};return null;
  }
  snapshot(){return [structuredClone(this.object)];}
}
