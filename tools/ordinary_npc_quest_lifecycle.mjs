// Candidate-only source staging for the compatible MissionDialog controller.
// Does not change the source file, world, transport, task rules or any save.
// The host must call invalidate() on disconnect / character-session change.
export function stageOrdinaryNPCQuestLifecycle(source){
  if(typeof source!=='string')throw TypeError('Quest UI source required');
  const replace=(before,after)=>{
    if(source.split(before).length!==2)throw Error('Quest UI lifecycle source anchor differs');
    source=source.replace(before,after);
  };
  replace('}catch(error){if(token===epoch)reset();onError(error);throw error;}',
    '}catch(error){if(disposed||token!==epoch)return null;reset();onError(error);throw error;}');
  replace('vm.open();await draw(token);return inspect();',
    'vm.open();if(!await draw(token))return null;return inspect();');
  replace('if(!requested){pending=false;await draw(token);return {sent:false,confirmation:true};}',
    'if(!requested){pending=false;if(!await draw(token))return null;return {sent:false,confirmation:true};}');
  replace("pending=false;await open(old.questId);return {sent:false,reason:'state-changed'};",
    "pending=false;const refreshedEpoch=epoch+1;await open(old.questId);\n        if(disposed||epoch!==refreshedEpoch)return null;return {sent:false,reason:'state-changed'};");
  replace("if(!disposed&&token===epoch){pending=false;await open(old.questId).catch(()=>{});}onError(error);throw error;",
    "if(disposed||token!==epoch)return null;\n      pending=false;const recoveryEpoch=epoch+1;await open(old.questId).catch(()=>{});\n      if(disposed||epoch!==recoveryEpoch)return null;onError(error);throw error;");
  replace("if(result?.ok!==true)throw Error(result?.error||'Quest action rejected');\n      if(!disposed&&token===epoch)reset();return {sent:true,type,result};",
    "if(disposed||token!==epoch)return null;\n      if(result?.ok!==true)throw Error(result?.error||'Quest action rejected');\n      reset();return {sent:true,type,result};");
  replace('return Object.freeze({open,pressOK,close,inspect,',
    'return Object.freeze({open,pressOK,close,inspect,\n    invalidate(){if(disposed)return false;reset();return true;},');
  return source;
}
