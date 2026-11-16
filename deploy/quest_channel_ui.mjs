import {createSource461GatherProgress} from './quest461_gather_program.mjs';
import {createSourceChannelView} from './source_channel_view.mjs';
import {createChannelTimeline,sourceChannelPlacement} from './channel_timeline.mjs';
const BASE='/assets/source-quest461-channel-v1/',NS='http://www.w3.org/2000/svg';
export async function createQuestChannelUI({load=fetch}={}){
 const text=async name=>{const r=await load(BASE+name);if(!r.ok)throw Error('原收集界面资料未就绪');return r.text();};
 const [program,profile]=await Promise.all(['program.json','profile.json'].map(text));
 const core=await createSource461GatherProgress(program,profile),timeline=createChannelTimeline(core);
 const host=document.createElement('div');host.className='source-quest-channel';
 const screen=document.createElementNS(NS,'svg');screen.setAttribute('viewBox','0 0 1136 640');
 const window=document.createElementNS(NS,'g');screen.append(window);host.append(screen);document.body.append(host);
 let view,raf=0,last=0,disposed=false;
 try{
  view=await createSourceChannelView(window,{load});
  const measured=view.measureInitialSourceBounds(),p=sourceChannelPlacement(view.sourceWindow,measured);
  window.setAttribute('transform',`translate(${p.x} ${p.y}) scale(${p.scale})`);
  host.dataset.sourceChannelMeasurement=JSON.stringify(measured);
  host.dataset.sourceChannelPlacement=JSON.stringify(p);
  const render=state=>{if(!state)return;view.render(state);host.dataset.sourceChannelPhase=timeline.inspect().phase;};
  const frame=now=>{
   if(disposed)return;render(timeline.advance(Math.max(0,now-last)));last=now;
   if(timeline.needsFrame())raf=requestAnimationFrame(frame);else raf=0;
  };
  const animate=()=>{last=performance.now();if(!raf&&timeline.needsFrame())raf=requestAnimationFrame(frame);};
  return Object.freeze({
   begin(channel){if(disposed)throw Error('Source channel window disposed');if(timeline.begin(channel)){render(timeline.inspect().state);animate();}},
   end(id,result){if(disposed)return;const now=performance.now();render(timeline.advance(Math.max(0,now-last)));last=now;
    if(timeline.end(id,result)){render(timeline.inspect().state);animate();}},
   invalidate(){if(disposed)return;cancelAnimationFrame(raf);raf=0;timeline.invalidate();view.render({...core.inspect(),shown:false});delete host.dataset.sourceChannelPhase;},
   dispose(){if(disposed)return;disposed=true;cancelAnimationFrame(raf);timeline.invalidate();view.dispose();host.remove();},
  });
 }catch(error){view?.dispose();host.remove();throw error;}
}
