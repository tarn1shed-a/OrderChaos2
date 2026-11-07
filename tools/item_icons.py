"""Select original item art through verified same-key records, not guessed filenames."""
import hashlib
import io
import json
from pathlib import Path
from PIL import Image
from skill_attachments import decode_ftable
from skill_icons import decode_localized_names

ITEMS_TABLE = 'tables/items.tbl'
DISPLAY_TABLE = 'tables/itemdisplayinfo.tbl'
NAME_TABLE = 'tables/String_Item_zh.tbl'
SELECTION = {
    'trainingStaff': (200520,14949,'plant_staff.png'),
    'trainingGreatsword': (200496,14925,'plant_greatsword.png'),
    'wolfPelt': (50006, 568, 'tanning_coarse_skin.png'),
    'trainingSword': (200230, 7743, 'august_spatha.png'),
    'linenArmor': (100422, 7780, 'faith_chest.png'),
    'travelerBoots': (100423, 7781, 'faith_feet.png'),
}


def recover_item_icons(extract, output):
    loaded = {}
    def load(path):
        if path not in loaded:
            value = extract(path)
            loaded[path] = bytes(value) if isinstance(value, (bytes, bytearray, memoryview)) else Path(value).read_bytes()
        return loaded[path]
    items = decode_ftable(load(ITEMS_TABLE), 'entry')
    displays = decode_ftable(load(DISPLAY_TABLE), 'ID')
    names = decode_localized_names(load(NAME_TABLE), 'SC')
    by_item = {row['entry']: row for row in items['rows']}
    by_display = {row['ID']: row for row in displays['rows']}
    icons, images = {}, {}
    for key, (identifier, name_id, filename) in SELECTION.items():
        item, display = by_item.get(identifier, {}), by_display.get(identifier, {})
        if item.get('name1') != name_id or item.get('displayid') != 0 or display.get('Icon') != filename or not names['values'].get(name_id):
            raise ValueError(f'Original item same-key/icon/name reference mismatch: {key}')
        path = 'ui/icons/item/' + filename
        raw = load(path)
        with Image.open(io.BytesIO(raw)) as image:
            if image.format != 'PNG' or image.size != (96, 96) or image.mode != 'RGBA':
                raise ValueError('Original item icon format/dimensions mismatch')
            image.verify()
        target = f'item-{key}.png'; images[target] = raw
        icons[key] = {'url': '/assets/ui/' + target, 'width': 96, 'height': 96,
            'sourcePath': path, 'sourcePack': 'ui_icon_1.bin', 'sourceSHA256': hashlib.sha256(raw).hexdigest(),
            'mode': 'unchanged-full-source-png', 'linkMode': 'same-key-table-match',
            'item': {'path': ITEMS_TABLE, 'entry': identifier, 'name1': name_id, 'displayid': 0},
            'display': {'path': DISPLAY_TABLE, 'ID': identifier, 'Icon': filename},
            'sourceName': {'path': NAME_TABLE, 'field': 'SC', 'id': name_id, 'value': names['values'][name_id]}}
    profile = {'format': 'oc2-item-icons-v1', 'icons': icons,
        'sources': {path: table['verification'] for path, table in ((ITEMS_TABLE, items), (DISPLAY_TABLE, displays), (NAME_TABLE, names))},
        'provenance': {'originalStatsRestored': False, 'nativeZeroDisplayFallbackVerified': False,
            'limitations': [
                'Original items.entry equals itemdisplayinfo.ID, whose Icon names the exact PNG. All selected items.displayid values are zero; the native zero-display fallback is not proven.',
                'Local starter gear, names, stats and wolf rewards borrow these original images; they do not reproduce original item rules.']}}
    destination = Path(output) / 'ui'; destination.mkdir(parents=True, exist_ok=True)
    for name, raw in images.items(): (destination / name).write_bytes(raw)
    (destination / 'item-icons.json').write_text(json.dumps(profile, ensure_ascii=False, indent=2))
    return profile
