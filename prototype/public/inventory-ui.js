import { EQUIPMENT_SLOTS, itemById, bagEntries } from './items.js';

export function inventorySelection(character, selection) {
  if (selection?.slot && character?.equipment?.[selection.slot]) return { ...selection, item: itemById(character.equipment[selection.slot]), equipped: true };
  if (selection?.id && (character?.inventory?.[selection.id] || 0) > 0) return { id: selection.id, item: itemById(selection.id), equipped: false };
  return null;
}

export function createInventoryUI(profile, { send, stop, focusGame }) {
  const $ = id => document.getElementById(id), dialog = $('inventory-dialog');
  let character, selection, filter = 'all', pending = false, pendingGoal, timer, signature;
  // Slot indices are original display-list positions. Local body-part meanings
  // below are an explicit web mapping, not a decoded native equipment enum.
  const localSlots = { 0: 'chest', 1: 'mainHand', 6: 'feet' };
  const sourceSlots = profile.inventory.layouts.equipment.slots;
  const equipment = $('equipment-slots'), bag = $('bag-slots');
  const stage = document.querySelector('.equipment-stage');
  const resize = new ResizeObserver(() => $('equipment-canvas').style.setProperty('--equipment-scale', String(stage.clientWidth / 660)));
  resize.observe(stage);
  window.addEventListener('pagehide', () => { resize.disconnect(); clearTimeout(timer); }, { once: true });
  function image(key, className = 'item-icon') {
    const img = document.createElement('img'), entry = profile.itemIcons.icons[key];
    img.src = entry.url; img.alt = ''; img.className = className; img.width = img.height = 96; return img;
  }
  function open() {
    if (!character || dialog.open) return;
    stop(); dialog.showModal(); render(); $('inventory-close').focus();
  }
  function close() { if (dialog.open) dialog.close(); }
  function finish(message) { pending = false; pendingGoal = null; clearTimeout(timer); if (message) $('inventory-status').textContent = message; renderDetail(); }
  function renderDetail() {
    const selected = inventorySelection(character, selection), content = $('item-detail-content');
    content.replaceChildren(); $('item-action').hidden = true;
    if (!selected?.item) {
      const hint = document.createElement('p'); hint.textContent = '选择物品查看详情，或点击装备槽卸下装备。'; content.append(hint); return;
    }
    const item = selected.item, title = document.createElement('h3'), kind = document.createElement('span'), text = document.createElement('p');
    title.textContent = item.name; kind.className = 'item-kind'; kind.textContent = item.slot ? `${EQUIPMENT_SLOTS[item.slot]} · ${selected.equipped ? '已穿戴' : '装备'}` : `材料 · 数量 ${character.inventory[item.id]}`;
    text.textContent = item.description; content.append(image(item.id), kind, title, text);
    if (item.slot) {
      $('item-action').hidden = false; $('item-action').textContent = selected.equipped ? '卸下装备' : '穿戴装备';
      $('item-action').disabled = pending || character.hp <= 0;
    }
  }
  function render() {
    if (!character) return;
    const entries = bagEntries(character), visible = entries.filter(item => filter === 'all' || Boolean(item.slot) === (filter === 'equipment'));
    $('bag-count').textContent = `${entries.length} / 40 格`;
    $('inventory-gold').textContent = character.gold;
    $('equipment-name').textContent = `${character.name} · Lv.${character.level}`;
    $('equipment-attack').textContent = character.stats.attack;
    $('equipment-armor').textContent = character.stats.armor;
    $('equipment-life').textContent = `${character.hp} / ${character.maxHp}`;
    bag.replaceChildren();
    for (let index = 0; index < 40; index++) {
      const item = visible[index], node = document.createElement(item ? 'button' : 'span');
      node.className = 'inventory-slot'; node.dataset.index = index;
      if (item) {
        node.type = 'button'; node.dataset.item = item.id; node.append(image(item.id));
        node.title = `${item.name} ×${item.quantity}`; node.setAttribute('aria-label', node.title);
        const amount = document.createElement('b'); amount.textContent = item.quantity; node.append(amount);
        node.setAttribute('aria-pressed', String(selection?.id === item.id));
        node.addEventListener('click', () => { selection = { id: item.id }; render(); bag.querySelector(`[data-item="${item.id}"]`)?.focus(); });
      } else node.setAttribute('aria-hidden', 'true');
      bag.append(node);
    }
    equipment.replaceChildren();
    for (const source of sourceSlots) {
      const slot = localSlots[source.index], id = slot && character.equipment[slot], node = document.createElement(slot ? 'button' : 'span');
      node.className = `inventory-slot equipment-slot${slot ? '' : ' inactive-slot'}`;
      node.dataset.sourceSlot = source.index;
      // Bounds are native stage pixels; the surrounding canvas scales uniformly.
      node.style.left = `${source.x}px`; node.style.top = `${source.y}px`;
      if (slot) {
        node.type = 'button'; node.dataset.slot = slot; const label = document.createElement('span'); label.className = 'equipment-slot-label';
        label.textContent = EQUIPMENT_SLOTS[slot]; node.append(label);
        if (id) node.append(image(id));
        const name = itemById(id)?.name; node.title = `${EQUIPMENT_SLOTS[slot]}：${name || '未穿戴'}`; node.setAttribute('aria-label', node.title);
        node.setAttribute('aria-pressed', String(selection?.slot === slot));
        node.addEventListener('click', () => { selection = { slot }; render(); equipment.querySelector(`[data-slot="${slot}"]`)?.focus(); });
      } else { node.setAttribute('aria-hidden', 'true'); }
      equipment.append(node);
    }
    renderDetail();
  }
  $('inventory-open').addEventListener('click', open);
  $('inventory-close').addEventListener('click', close);
  dialog.addEventListener('close', () => { stop(); focusGame(); });
  for (const button of document.querySelectorAll('[data-bag-filter]')) button.addEventListener('click', () => {
    filter = button.dataset.bagFilter;
    for (const tab of document.querySelectorAll('[data-bag-filter]')) tab.setAttribute('aria-pressed', String(tab === button));
    render();
  });
  $('item-action').addEventListener('click', () => {
    const selected = inventorySelection(character, selection); if (!selected?.item?.slot || pending || character.hp <= 0) return;
    pending = true; pendingGoal = selected.equipped ? { id: selected.item.id } : { slot: selected.item.slot };
    $('inventory-status').textContent = '正在更换装备…'; renderDetail();
    send(selected.equipped ? { type: 'unequip', slot: selected.slot } : { type: 'equip', slot: selected.item.slot, itemId: selected.item.id });
    timer = setTimeout(() => finish('操作暂未完成，请检查连接后重试。'), 5000);
  });
  return {
    open, close, get isOpen() { return dialog.open; },
    setModel(url) { $('equipment-model').src = url; },
    update(value) {
      character = value; $('inventory-open').disabled = !value;
      if (!value) { close(); finish(); signature = null; return; }
      if (pending && inventorySelection(value, pendingGoal)) { selection = pendingGoal; finish('装备已由服务器保存。'); }
      const next = JSON.stringify([value.inventory, value.equipment, value.stats, value.gold, value.hp]);
      if (next !== signature) { signature = next; if (dialog.open) render(); }
    },
    notice(text) { if (dialog.open && pending) finish(text); },
  };
}
