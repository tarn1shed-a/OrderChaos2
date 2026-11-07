"""Recover source skill icons through checked proto/rune/state references.

The web skills are local adaptations. This module proves the selected source
icon links without claiming that the complete original player skills run here.
Original PNGs and localized strings are only written below converted/ui/.
"""
import hashlib
import io
import json
import re
import struct
from pathlib import Path

from PIL import Image
from skill_attachments import decode_ftable

PROTO_TABLE = 'tables/skill_proto.tbl'
RUNE_TABLE = 'tables/skill_runes.tbl'
STATE_TABLE = 'tables/skill_visual_state.tbl'
EFFECT_TABLE = 'tables/skill_visual_effect.tbl'
NAME_TABLES = {'en': ('tables/String_Skill_en.tbl', 'EN'),
               'zh': ('tables/String_Skill_zh.tbl', 'SC')}
ICON_PACK = 'ui_icon_1.bin'
SELECTION = {
    'fireball': {'skillId':17,'editName':'Scorcher','runeId':68,'icon':'skill/fire_blast.png','nameStrId':3279,
        'links':[('chantState',67,[('casterRHandEff',24,'effects/skill/mage/scorcher_default_cast_hand_loop.beff')]),
                 ('releaseState',32,[('casterRHandEff',23,'effects/skill/mage/scorcher_default_missile_link_loop.beff')])]},
    'arcane_missile': {'skillId':90,'editName':'ArcaneMissile','runeId':360,'icon':'skill/arcane_missile.png','nameStrId':3263,
        'links':[('channellingState',130,[('casterRHandEff',110,'effects/skill/mage/arcane_blade_absorption_channel_chest_acyclic.beff')]),
                 ('releaseState',128,[('casterRHandEff',59,'effects/skill/mage/arcane_missile_default_missile_link_loop.beff')])]},
    'frost_blast': {'skillId': 94, 'editName': 'FrostBlast', 'runeId': 376,
        'icon': 'skill/frost_blast.png', 'nameStrId': 3287,
        'links': [('releaseState', 137, [('targetGroundEff', 65,
                   'effects/skill/mage/frost_blast_default_channel_ground_acyclic.beff')])]},
}


def _bytes(value):
    return bytes(value) if isinstance(value, (bytes, bytearray, memoryview)) else Path(value).read_bytes()


def decode_localized_names(data, language):
    """Read localized FTABLEs whose SQL retains all languages but rows have ID/text.

    These files have physical ``us`` records of ten bytes. Nonempty lengths
    include their terminating NUL; empty strings have zero length and still
    point at a NUL. This differs from the normal multi-column source tables.
    """
    if language not in ('EN', 'SC') or len(data) < 44 or data[:8] != b'FTABLE\0\0':
        raise ValueError('Unsupported localized FTABLE header or language')
    version, count, columns, ids_at, types_at, rows_at, stride, pool_at, reserved = struct.unpack_from('<9I', data, 8)
    if (version != 0x100000 or not 1 <= count <= 100000 or columns != 2 or stride != 10 or reserved
            or not (44 < ids_at and types_at == ids_at + count * 4
                    and rows_at == types_at + 3 and pool_at == rows_at + count * stride
                    and pool_at < len(data))):
        raise ValueError('Invalid localized FTABLE sections')
    if data[types_at:rows_at] != b'us\0':
        raise ValueError('Unsupported localized FTABLE physical types')
    try:
        schema = data[44:ids_at].split(b'\0', 1)[0].decode('utf-8')
    except UnicodeDecodeError as error:
        raise ValueError('Invalid localized FTABLE schema') from error
    names = re.findall(r'^\s*`([^`]+)`\s+', schema, re.MULTILINE)
    if not names or names[0] != 'ID' or language not in names or len(names) != len(set(names)):
        raise ValueError('Localized FTABLE schema has no selected language')
    identifiers = struct.unpack_from('<' + 'I' * count, data, ids_at)
    if len(set(identifiers)) != count:
        raise ValueError('Duplicate localized FTABLE ID')
    values = {}
    for index, identifier in enumerate(identifiers):
        actual, pointer, size = struct.unpack_from('<IIH', data, rows_at + index * stride)
        if actual != identifier:
            raise ValueError('Localized FTABLE ID index mismatch')
        if pointer < pool_at or pointer >= len(data) or pointer + size > len(data):
            raise ValueError('Localized FTABLE string outside pool')
        raw = data[pointer:pointer + size] if size else data[pointer:pointer + 1]
        if raw[-1:] != b'\0' or b'\0' in raw[:-1]:
            raise ValueError('Localized FTABLE string missing terminator or embedded NUL')
        try:
            values[identifier] = raw[:-1].decode('utf-8')
        except UnicodeDecodeError as error:
            raise ValueError('Invalid localized FTABLE UTF-8') from error
    return {'values': values, 'language': language,
            'verification': {'rows': count, 'rowStride': stride,
                'stringPoolOffset': pool_at, 'sourceSHA256': hashlib.sha256(data).hexdigest()}}


def recover_skill_icons(extract, output):
    """extract(path) returns archive-checked bytes or a Path; output is converted root.

    Full-resolution icon paths are unique to ui_icon_1.bin in the supplied data.
    ui.bin's distinct *_0.5x.png files are not silently used or upscaled.
    """
    loaded = {}
    def load(path):
        if path not in loaded:
            loaded[path] = _bytes(extract(path))
        return loaded[path]
    tables = {path: decode_ftable(load(path), identifier) for path, identifier in
              ((PROTO_TABLE, 'skillId'), (RUNE_TABLE, 'id'), (STATE_TABLE, 'id'), (EFFECT_TABLE, 'id'))}
    rows = {path: {row[identifier]: row for row in tables[path]['rows']} for path, identifier in
            ((PROTO_TABLE, 'skillId'), (RUNE_TABLE, 'id'), (STATE_TABLE, 'id'), (EFFECT_TABLE, 'id'))}
    names = {locale: decode_localized_names(load(path), language)
             for locale, (path, language) in NAME_TABLES.items()}
    icons, images = {}, {}
    for key, expected in SELECTION.items():
        proto = rows[PROTO_TABLE].get(expected['skillId'], {})
        rune = rows[RUNE_TABLE].get(expected['runeId'], {})
        if (proto.get('editName') != expected['editName'] or proto.get('rune0') != expected['runeId']
                or rune.get('icon') != expected['icon'] or rune.get('nameStrId') != expected['nameStrId']):
            raise ValueError(f'Selected source proto/rune/icon reference mismatch: {key}')
        links = []
        for field, state_id, proofs in expected['links']:
            state = rows[STATE_TABLE].get(state_id, {})
            if rune.get(field) != state_id:
                raise ValueError(f'Source rune/state reference mismatch: {key}/{field}')
            effect_links = []
            for slot, effect_id, path in proofs:
                effect = rows[EFFECT_TABLE].get(effect_id, {})
                if state.get(slot) != effect_id or effect.get('pathName') != path:
                    raise ValueError(f'Source state/effect reference mismatch: {key}/{slot}')
                effect_links.append({'slotField': slot, 'effectId': effect_id, 'effectPath': path})
            links.append({'runeField': field, 'stateId': state_id, 'effects': effect_links})
        localized = {}
        for locale, table in names.items():
            value = table['values'].get(expected['nameStrId'])
            if not value:
                raise ValueError(f'Source localized skill name missing: {key}/{locale}')
            localized[locale] = {'path': NAME_TABLES[locale][0], 'field': NAME_TABLES[locale][1],
                                 'stringId': expected['nameStrId'], 'value': value}
        path = 'ui/icons/' + expected['icon']
        if not re.fullmatch(r'ui/icons/skill/[a-z_]+\.png', path):
            raise ValueError('Unsafe source icon path')
        raw = load(path)
        with Image.open(io.BytesIO(raw)) as image:
            if image.format != 'PNG' or image.size != (96, 96) or image.mode != 'RGBA':
                raise ValueError('Source skill icon format/dimensions differ from verified PNG')
            image.verify()
        filename = f'skill-{key}.png'
        images[filename] = raw
        icons[key] = {'url': '/assets/ui/' + filename, 'width': 96, 'height': 96,
            'mode': 'unchanged-full-source-png', 'sourceRect': [0, 0, 96, 96],
            'sourcePath': path, 'sourcePack': ICON_PACK,
            'sourceSHA256': hashlib.sha256(raw).hexdigest(), 'sourceIconReference': expected['icon'],
            'sourceSkill': {'path': PROTO_TABLE, 'idColumn': 'skillId', 'id': proto['skillId'],
                'editName': proto['editName'], 'runeField': 'rune0', 'runeId': rune['id']},
            'sourceRune': {'path': RUNE_TABLE, 'id': rune['id'], 'iconField': 'icon',
                'nameStrId': rune['nameStrId']},
            'sourceNames': localized, 'effectLinks': links}
    sources = {path: {'pack': 'tables.bin', **table['verification']} for path, table in tables.items()}
    sources.update({NAME_TABLES[locale][0]: {'pack': 'tables.bin', **table['verification']}
                    for locale, table in names.items()})
    profile = {'format': 'oc2-skill-icons-v1', 'icons': icons, 'sources': sources,
        'provenance': {'selection': 'source-proto-to-rune-to-icon, cross-checked with selected source effects',
            'resizing': False, 'atlasInference': False, 'completeOriginalPlayerSkills': False,
            'limitations': [
                'Selected player Scorcher17/rune68, ArcaneMissile90/rune360 and FrostBlast94/rune376 are linked to their actual icons and source states; server combat outcomes remain local.',
                'Full 96x96 source PNGs are copied unchanged; cropping/masking and button layout in the browser are web adaptations.']}}
    destination = Path(output) / 'ui'
    destination.mkdir(parents=True, exist_ok=True)
    for name, raw in images.items():
        (destination / name).write_bytes(raw)
    (destination / 'skill-icons.json').write_text(json.dumps(profile, ensure_ascii=False, indent=2))
    return profile
