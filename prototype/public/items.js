// Local prototype rules. The recovered art does not imply original item stats.
export const EQUIPMENT_SLOTS = Object.freeze({ mainHand: '主手', chest: '胸甲', feet: '鞋靴' });
export const ITEMS = Object.freeze({
  trainingSword: Object.freeze({ id: 'trainingSword', name: '营地练习剑', kind: '装备', slot: 'mainHand', attack: 4, armor: 0, health: 0, description: '普通攻击伤害 +4。技能伤害不变。' }),
  linenArmor: Object.freeze({ id: 'linenArmor', name: '营地布甲', kind: '装备', slot: 'chest', attack: 0, armor: 1, health: 20, description: '防御 +1，生命上限 +20。穿戴不会恢复当前生命。' }),
  travelerBoots: Object.freeze({ id: 'travelerBoots', name: '营地旅靴', kind: '装备', slot: 'feet', attack: 0, armor: 1, health: 0, description: '防御 +1。每次受到野狼攻击至少损失 1 点生命。' }),
  wolfPelt: Object.freeze({ id: 'wolfPelt', name: '狼皮', kind: '材料', description: '参与击败野狼获得的材料，保存在角色背包中。' }),
});
export const itemById = id => typeof id === 'string' && Object.hasOwn(ITEMS, id) ? ITEMS[id] : null;
export const starterInventory = () => ({ trainingSword: 1, linenArmor: 1, travelerBoots: 1, wolfPelt: 0 });
export const emptyEquipment = () => ({ mainHand: null, chest: null, feet: null });
export function equipmentStats(character) {
  const result = { attack: 20, armor: 0, maxHp: 100 + (character.level - 1) * 20 };
  for (const slot of Object.keys(EQUIPMENT_SLOTS)) {
    const item = itemById(character.equipment?.[slot]);
    if (item?.slot !== slot) continue;
    result.attack += item.attack; result.armor += item.armor; result.maxHp += item.health;
  }
  return result;
}
export function bagEntries(character) {
  return Object.values(ITEMS).filter(item => (character?.inventory?.[item.id] || 0) > 0)
    .map(item => ({ ...item, quantity: character.inventory[item.id] }));
}
