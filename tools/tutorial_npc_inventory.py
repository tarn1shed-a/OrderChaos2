"""Audit original Tutorial creature relationships without creating live actors.

The result is source evidence, never an ObjectCreate message, quest marker,
player spawn or appearance/availability decision. Full rows stay ignored.
"""
import argparse
import collections
import hashlib
import json
import re
import struct
from pathlib import Path

from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from skill_attachments import decode_ftable
from tutorial_map_geometry import local_output

FORMAT = 'oc2-tutorial-npc-inventory-v1'
TABLES = {
    'creature_spawns': 'id', 'creature_proto': 'entry',
    'creature_appearance': 'entry', 'creaturedisplayinfo': 'ID',
    'creaturedisplayinfoextra': 'ID', 'creaturemodeldata': 'ID',
    'creature_display_filter': 'ID', 'phasing_area': 'id',
    'itemdisplayinfo': 'ID', 'itemmodeldata': 'ID', 'race_features': 'id',
    'quests': 'entry', 'emote': 'id',
}
NAME_TABLE = 'tables/String_Creature_zh.tbl'
EQUIPMENT_FIELDS = ('Helm', 'Shoulder', 'Shirt', 'Chest', 'Boots', 'Gloves',
                    'Legs', 'MainHand', 'OffHand')


def selected_names(data, wanted):
    """Validate the physical table, decode only requested original string rows.

    The supplied creature table has an unrelated non-UTF8 row. Replacing that
    byte sequence, silently using another language or relaxing UTF8 is unsafe.
    All physical spans are checked; requested malformed text is rejected.
    """
    if len(data) < 44 or data[:8] != b'FTABLE\0\0':
        raise ValueError('Invalid localized table header')
    version, count, columns, ids, types, rows, stride, pool, reserved = struct.unpack_from('<9I', data, 8)
    if (version != 0x100000 or not 0 < count <= 100000 or columns != 2 or stride != 10 or
            reserved or not 44 < ids or types != ids + count*4 or rows != types+3 or
            pool != rows+count*stride or pool >= len(data) or data[types:rows] != b'us\0'):
        raise ValueError('Unsupported localized table layout')
    schema = data[44:ids].split(b'\0', 1)[0].decode('utf8')
    columns = re.findall(r'^\s*`([^`]+)`\s+', schema, re.MULTILINE)
    if not columns or columns[0] != 'ID' or 'SC' not in columns:
        raise ValueError('Missing original simplified-Chinese language column')
    identifiers = struct.unpack_from('<'+'I'*count, data, ids)
    if len(set(identifiers)) != count:
        raise ValueError('Duplicate localized ID')
    wanted = set(wanted) - {0}
    values = {}
    for index, identifier in enumerate(identifiers):
        actual, pointer, size = struct.unpack_from('<IIH', data, rows+index*stride)
        if (actual != identifier or not pool <= pointer < len(data) or pointer+size > len(data)):
            raise ValueError('Localized ID/span differs')
        raw = data[pointer:pointer+size] if size else data[pointer:pointer+1]
        if raw[-1:] != b'\0' or b'\0' in raw[:-1]:
            raise ValueError('Malformed localized string terminator')
        if identifier in wanted:
            values[identifier] = raw[:-1].decode('utf8')
    if wanted != set(values):
        raise ValueError('Requested source name missing')
    return values, {'rows': count, 'decodedSelectedRows': len(values),
                    'allPhysicalSpansChecked': True, 'allTextDecoded': False,
                    'sourceSHA256': hashlib.sha256(data).hexdigest()}


def unique(rows, key):
    result = {row[key]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError('Duplicate original key: '+key)
    return result


def audit(source=DEFAULT_SOURCE):
    sources = Sources(source)
    tables = {name: decode_ftable(sources.read('tables/'+name+'.tbl'), key)
              for name, key in TABLES.items()}
    indexed = {name: unique(table['rows'], TABLES[name]) for name, table in tables.items()}
    spawns = [row for row in tables['creature_spawns']['rows'] if row['map'] == 5]
    entries = sorted({row['entry'] for row in spawns})
    appearances = [indexed['creature_appearance'][entry] for entry in entries]
    wanted_names = {row[field] for row in appearances for field in ('name', 'subname', 'info_str')}
    names, name_proof = selected_names(sources.read(NAME_TABLE), wanted_names)
    creatures = []
    for entry in entries:
        appearance = indexed['creature_appearance'][entry]
        rows = [row for row in spawns if row['entry'] == entry]
        # A spawn display override and appearance default are separate source
        # candidates. Their actual original runtime selector is not invented.
        display_ids = sorted({appearance['creaturedisplayinfo_id']} | {row['displayid'] for row in rows if row['displayid']})
        displays = []
        for identifier in display_ids:
            display = indexed['creaturedisplayinfo'][identifier]
            model = indexed['creaturemodeldata'][display['Model']]
            model_path = model['ModelPath']
            candidates = len(sources.candidates(model_path))
            if candidates == 1:
                sources.read(model_path)
            extra_id = display['ExtraDisplayInformation']
            extra = indexed['creaturedisplayinfoextra'].get(extra_id) if extra_id else None
            if extra_id and extra is None:
                raise ValueError('Original extra display ID missing')
            items = []
            if extra:
                for slot in EQUIPMENT_FIELDS:
                    if extra[slot]:
                        item = indexed['itemdisplayinfo'].get(extra[slot])
                        if item is None:
                            raise ValueError('Original extra item display missing')
                        items.append({'extraField': slot, 'display': item,
                                      'models': [indexed['itemmodeldata'][value] for key, value in item.items()
                                                 if key.startswith('Model') and value]})
            displays.append({'display': display, 'model': model,
                             'modelLocalCandidates': candidates, 'extra': extra,
                             'equipmentAcrossRaceGenderFields': items})
        selected_filter = indexed['creature_display_filter'].get(appearance['creature_display_filter_id'])
        creatures.append({'entry': entry, 'name': names.get(appearance['name']),
                          'subname': names.get(appearance['subname']),
                          'infoText': names.get(appearance['info_str']),
                          'appearance': appearance, 'prototype': indexed['creature_proto'][entry],
                          'spawns': rows, 'appearanceCandidates': displays,
                          'displayFilter': selected_filter,
                          'questStartReferences': [row['entry'] for row in tables['quests']['rows'] if row['StartGiverID'] == entry],
                          'questFinishReferences': [row['entry'] for row in tables['quests']['rows'] if row['FinishGiverID'] == entry],
                          'runtimeExistence': None, 'runtimeGUID': None,
                          'runtimeAppearanceSelection': None, 'questAvailability': None})
    return {'format': FORMAT, 'mapId': 5, 'creatures': creatures,
            'summary': {'spawns': len(spawns), 'entries': len(entries),
                        'manualSpawnValues': dict(collections.Counter(row['manual_spawn'] for row in spawns)),
                        'phaseValues': dict(collections.Counter(row['phase'] for row in spawns)),
                        'phasingIdValues': dict(collections.Counter(row['phasing_id'] for row in spawns))},
            'phasingAreas': [row for row in tables['phasing_area']['rows'] if row['map_id'] == 5],
            'tableProofs': {name: table['verification'] for name, table in tables.items()},
            'nameProof': name_proof, 'sourceProofs': sources.proofs,
            'limits': ['Static spawn/prototype/appearance candidates are not activity messages or current appearance.',
                       'phase/phasing_id/manual_spawn/raw flags are preserved; zero is not a proof of unconditional visibility.',
                       'No invented NPC names, locations, GUIDs, quest icons, accept state or live appearance.',
                       'Original table labels are evidence; full native selectors and server conditions remain separate.'],
            'savesReadOrWritten': False, 'productionChanged': False}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    output = local_output(args.output)
    if output.exists():
        cli.error('Existing evidence is preserved; choose a new output')
    report = audit(args.source)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(output), **report['summary'], 'productionChanged': False}))


if __name__ == '__main__':
    main()
