export function monsterStateText(monster){
  return ({idle:'待命',chasing:'追击中',attacking:'交战中',returning:'脱战返回',blocked:'道路受阻',frozen:'受控制',dead:'已击败'})[monster?.ai?.state]||'战斗目标';
}
