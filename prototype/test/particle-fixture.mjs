export const curve=(value,{frames=[0],loop=false,kind='float'}={})=>({frames,loop,kind,values:Array.isArray(value)?value:[value]});
export function emitter(overrides={}) {
  const curves={};for(const name of ['outerX','outerY','outerZ','rotateX','rotateY','rotateZ','translateX','translateY','translateZ','radialSpeed','directedSpeed','coneAngle'])curves[name]=curve(0);
  curves.innerPercent=curve(0,{kind:'int'});for(const n of ['volumeHigh','volumeMedium','volumeLow'])curves[n]=curve(1);
  curves.direction=curve([[0,1,0]],{kind:'vector3'});
  const pc={};for(const name of ['red','green','blue','alpha','secondaryRed','secondaryGreen','secondaryBlue'])pc[name]=curve(255,{kind:'int'});
  for(const name of ['unknownF0','uvLeft','uvTop','rotateX','rotateY','rotateZ'])pc[name]=curve(0);
  for(const name of ['uvRight','uvBottom','sizeX','sizeY','scaleX','scaleY'])pc[name]=curve(1);
  const headerWords=Array(20).fill(0);headerWords[7]=3;headerWords[9]=headerWords[10]=headerWords[11]=1;
  return {shape:0,headerWords,startFrame:0,durationFrames:3,intervalFrames:[1,1,1],curves,children:[],affectors:[],
    particle:{texture:'texture/test.tga',type:0,followFlags:0,lifeFrames:20,lifeRandomPercent:0,sizeRandomPercent:0,keepXY:true,
      baseAngles:[0,0,0],baseAngleRandomPercent:[0,0,0],rotationRandomPercent:[0,0,0],pivot:[0,0],
      material:{id:16,blend:'additive',twoColor:true},curves:pc},...overrides};
}
export function definition(emitters=[emitter()]) {return{emitters,verification:{completePayload:true},sampleRate:30,textures:['texture/test.tga'],textureURLs:{'texture/test.tga':'/assets/test.png'}};}
