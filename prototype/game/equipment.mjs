import { EQUIPMENT_SLOTS, itemById, equipmentStats } from '../public/items.js';

// Only item/slot identifiers are accepted; ownership and all stats come from the save.
export function changeEquipment(character, request) {
  if (character.hp <= 0) return { error: '倒地时无法更换装备' };
  const slot = request.slot;
  if (typeof slot !== 'string' || !Object.hasOwn(EQUIPMENT_SLOTS, slot)) return { error: '未知装备位置' };
  if (request.type === 'equip') {
    const item = itemById(request.itemId);
    if (!item || item.slot !== slot) return { error: '物品不能装备到这个位置' };
    if (character.equipment[slot] === item.id) return { error: '这件装备已穿戴' };
    if (!(character.inventory[item.id] > 0)) return { error: '背包中没有这件物品' };
    const previous = character.equipment[slot];
    character.inventory[item.id]--;
    if (previous) character.inventory[previous]++;
    character.equipment[slot] = item.id;
  } else if (request.type === 'unequip') {
    const previous = character.equipment[slot];
    if (!previous) return { error: '这个位置没有装备' };
    character.inventory[previous]++; character.equipment[slot] = null;
  } else return { error: '未知装备操作' };
  character.maxHp = equipmentStats(character).maxHp;
  character.hp = Math.min(character.hp, character.maxHp);
  return { message: request.type === 'equip' ? `已穿戴${itemById(request.itemId).name}` : `已卸下${EQUIPMENT_SLOTS[slot]}装备` };
}
