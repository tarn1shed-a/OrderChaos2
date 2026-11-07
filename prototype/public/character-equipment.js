import { EQUIPMENT_SLOTS, itemById } from './items.js';

export function equipmentAppearanceKey(equipment) {
  return Object.keys(EQUIPMENT_SLOTS).map(slot => itemById(equipment?.[slot])?.slot === slot ? equipment[slot] : '-').join('|');
}

export function validateEquipmentAppearance(data) {
  const appearance = data.appearance;
  if (!appearance) return null;
  if (appearance.format !== 'oc2-equipment-appearance-v1' || !Array.isArray(appearance.baseMeshIndices) || !appearance.baseMeshIndices.length || !appearance.items) throw new Error('原装备外观清单不匹配，请更新本地资源');
  const valid = index => Number.isInteger(index) && index >= 0 && index < data.meshes.length;
  const used = new Set();
  for (const index of appearance.baseMeshIndices) {
    if (!valid(index) || used.has(index)) throw new Error('原角色基体网格索引无效');
    used.add(index);
  }
  const base = new Set(used);
  for (const [id, entry] of Object.entries(appearance.items)) {
    if (!itemById(id)?.slot || itemById(id).slot !== entry.slot || !Array.isArray(entry.meshIndices) || !entry.meshIndices.length || !Array.isArray(entry.hideBaseMeshIndices)) throw new Error('原装备部位映射无效');
    for (const index of entry.meshIndices) {
      if (!valid(index) || used.has(index)) throw new Error('原装备网格索引无效');
      used.add(index);
    }
    if (!entry.hideBaseMeshIndices.every(index => base.has(index))) throw new Error('原装备隐藏部位无效');
  }
  if (used.size !== data.meshes.length || !['trainingSword','linenArmor','travelerBoots'].every(id => appearance.items[id])) throw new Error('原装备外观资源不完整');
  for (const [index, mesh] of data.meshes.entries()) {
    const attachment = mesh.attachment;
    if (!attachment) continue;
    if (!Number.isInteger(attachment.node) || !data.rig.nodes[attachment.node] || !Array.isArray(attachment.matrix) || attachment.matrix.length !== 16 || !attachment.matrix.every(Number.isFinite) || data.rig.skins.some(skin => skin.mesh === index)) throw new Error('原武器挂点无效');
  }
  return appearance;
}

// Visibility changes only. Geometry, weights, bones and animation clocks stay intact.
export function applyEquipmentMeshes(objects, appearance, equipment) {
  const visible = new Set(appearance.baseMeshIndices), worn = [];
  for (const [id, item] of Object.entries(appearance.items)) {
    if (equipment?.[item.slot] !== id) continue;
    for (const index of item.hideBaseMeshIndices) visible.delete(index);
    for (const index of item.meshIndices) visible.add(index);
    worn.push(id);
  }
  objects.forEach((object, index) => { object.visible = visible.has(index); });
  return { key: equipmentAppearanceKey(equipment), items: worn, visibleMeshIndices: [...visible].sort((a,b) => a-b) };
}
