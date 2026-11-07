// Exact QuestListHero.getQuestList branch order. Input is UI-list state, not a
// static object's quest_status or a guessed server quest/reward decision.
export function questListAppearance(status,failed,profile){
  if(failed===true)return {icon:profile.failedIcon,label:'失败'};
  if(failed!==false||!Number.isInteger(status))return {icon:null,label:'状态未知'};
  const icon=profile.statusIcons[String(status)]||null;
  return {icon,label:{unfinished:'未完成',complete:'完成',dailyComplete:'每日完成'}[icon]||`未映射状态 ${status}`};
}
export function questListGroup(type,profile){
  for(const [group,values]of Object.entries(profile.bookGroups))if(values.includes(type))return group;
  return null;
}
export function isEmptyQuestList(state){return Array.isArray(state?.active)&&state.active.length===0;}
