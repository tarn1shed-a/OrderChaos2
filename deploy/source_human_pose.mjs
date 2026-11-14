// Runtime pose transport only; no character/default/action/animation decisions.
import {stageSourceSpeciesCollision} from './source_avatar_server.mjs';
const bindingId='4032ecda85c04ddd350db92ff1eee1a8934ad5b3f69bb3236ea0cc2810609b85';

export function sourceHumanPose(value,sourceIdentity,playerIdentity){
 if(typeof sourceIdentity!=='string'||!sourceIdentity||typeof playerIdentity!=='string'||!playerIdentity||
  value?.format!=='oc2-human-original-fast-pose-v1'||value.actorKey!==sourceIdentity||value.bindingId!==bindingId||
  value.valueEncoding!=='float32-le-base64'||value.valueBytes!==1992||typeof value.values!=='string'||!/^[A-Za-z0-9+/]{2656}$/.test(value.values))
  throw Error('Complete own original human pose required');
 const bytes=Buffer.from(value.values,'base64');
 if(bytes.length!==1992)throw Error('Original human pose byte span differs');
 for(let at=0;at<bytes.length;at+=4)if(!Number.isFinite(bytes.readFloatLE(at)))throw Error('Nonfinite original human pose');
 // Both identities come from the existing collision adapter. This maps its
 // private VM scope to the public actor ID; neither is an original-server GUID.
 return {format:value.format,actorKey:playerIdentity,bindingId,valueEncoding:value.valueEncoding,valueBytes:1992,values:value.values};
}

export function stageSourceHumanPoseCollision(source){
 source=stageSourceSpeciesCollision(source);
 const before='entity.sourceAnimation=result.sourceAnimation;';
 if(source.split(before).length!==2)throw Error('Reviewed source-animation transport anchor differs');
 return `import {sourceHumanPose} from ${JSON.stringify(import.meta.url)};\n`+source.replace(before,
  before+"if(result.sourceHumanPose){if(entity.sourceAvatar?.key!=='human-male'||info.sourceHumanPose?.bindingId!==result.sourceHumanPose.bindingId)throw Error('Unconfigured original human pose');entity.sourceHumanPose=sourceHumanPose(result.sourceHumanPose,identity(entity),entity.id);}else{if(info.sourceHumanPose&&entity.sourceAvatar?.key==='human-male')throw Error('Missing original human pose');delete entity.sourceHumanPose;}");
}
