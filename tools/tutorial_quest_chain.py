"""Audit the original tutorial chain before wiring a playable quest.

This reader never accepts/completes quests, moves roles, or writes saves. Table
centres are checkpoints for investigation, not paths or completion predicates.
Full source rows and derived reports belong in ignored analysis/raw/.
"""
import argparse
import hashlib
import json
from pathlib import Path

from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE, index, read_entry
from skill_attachments import decode_ftable
from skill_icons import decode_localized_names
from tutorial_map_geometry import local_output


TABLES = {
    'quests': 'entry', 'quest_objective': 'id',
    'quest_objective_logic': 'id', 'quests_zones': 'ID',
    'creature_spawns': 'id', 'creature_proto': 'entry',
    'staticobject_spawns': 'id', 'staticobject_proto': 'entry',
    'staticobject_displayinfo': 'entry', 'npc_interactive': 'id',
    'quest_logic_item': 'id', 'quest_reward_item': 'id',
    'quest_map_exit': 'zone_id', 'scripts': 'Id',
}


def link_objectives(quest_id, objectives, logic, zones):
    """Join on quest_id + obj_idx; order by the original step, never row ID."""
    selected = [r for r in objectives if r['quest_id'] == quest_id]
    indices = [r['obj_idx'] for r in selected]
    if len(set(indices)) != len(indices):
        raise ValueError('Ambiguous original objective index')
    zone_by_id = {r['ID']: r for r in zones}
    if len(zone_by_id) != len(zones):
        raise ValueError('Ambiguous original zone ID')
    result = []
    for row in sorted(selected, key=lambda r: (r['step'], r['obj_idx'])):
        targets = []
        for target in logic:
            if target['quest_id'] != quest_id or target['obj_idx'] != row['obj_idx']:
                continue
            zone_id = target['zone']
            if zone_id and zone_id not in zone_by_id:
                raise ValueError('Original objective references an absent zone')
            targets.append({'logic': target, 'zone': zone_by_id.get(zone_id)})
        # A missing target remains missing. No synthetic radius or reach event.
        result.append({'objective': row, 'targets': targets})
    if any(r['obj_idx'] not in indices for r in logic if r['quest_id'] == quest_id):
        raise ValueError('Orphan original objective-logic record')
    return result


def audit(source=DEFAULT_SOURCE):
    sources = Sources(source)
    tables = {name: decode_ftable(sources.read('tables/' + name + '.tbl'), key)
              for name, key in TABLES.items()}
    rows = {name: table['rows'] for name, table in tables.items()}
    quests = [r for r in rows['quests'] if r['QuestArea'] == 'Tutorial']
    if len(quests) != 1 or quests[0]['entry'] != 202:
        raise ValueError('Different tutorial chain: retrace before use')
    quest = quests[0]
    text = decode_localized_names(sources.read('tables/String_Quest_zh.tbl'), 'SC')
    steps = link_objectives(202, rows['quest_objective'],
                            rows['quest_objective_logic'], rows['quests_zones'])
    for step in steps:
        step['text'] = text['values'][step['objective']['text']]
    if [s['objective']['step'] for s in steps] != list(range(1, 11)):
        raise ValueError('Different tutorial objective sequence')
    map_id = quest['ZoneId']
    creatures = [r for r in rows['creature_spawns'] if r['map'] == map_id]
    objects = [r for r in rows['staticobject_spawns'] if r['map'] == map_id]
    entries = {r['entry'] for r in creatures}
    object_entries = {r['Entry'] for r in objects}
    prototypes = [r for r in rows['staticobject_proto'] if r['entry'] in object_entries]
    displays = {r['DisplayID'] for r in prototypes}
    elevators = [r for r in objects if any(r[k] != 0 for k in
                 ('elevator_star_y', 'elevator_over_y', 'elevator_speed'))]
    scripts = sorted({quest['script']} |
                     {r['script'] for r in prototypes if r['script']} |
                     {r['script'] for r in rows['creature_proto']
                      if r['entry'] in entries and r['script']})
    return {
        'format': 'oc2-tutorial-chain-evidence-v1',
        'quest': quest, 'title': text['values'][quest['Title']],
        'steps': steps, 'mapId': map_id,
        'startGiverSameEntryCandidates': [r for r in creatures if r['entry'] == quest['StartGiverID']],
        'finishGiverSameEntryCandidates': [r for r in creatures if r['entry'] == quest['FinishGiverID']],
        'creatureSpawns': creatures, 'objectSpawns': objects,
        'creaturePrototypes': [r for r in rows['creature_proto'] if r['entry'] in entries],
        'objectPrototypes': prototypes,
        'objectDisplays': [r for r in rows['staticobject_displayinfo'] if r['entry'] in displays],
        'elevatorSpawns': elevators,
        'npcInteractions': [r for r in rows['npc_interactive'] if r['quest'] == 202],
        'rewardItems': [r for r in rows['quest_reward_item'] if r['quest_id'] == 202],
        'logicItems': [r for r in rows['quest_logic_item'] if r['quest_id'] == 202],
        'mapExits': [r for r in rows['quest_map_exit'] if r['map_id'] == map_id],
        'scriptReferences': scripts,
        'scriptReferenceFilenameMatches': {name: [n for n in sources.lookup if name.lower() in n]
                                           for name in scripts},
        'sourceProofs': sources.proofs,
        'tableProofs': {name: table['verification'] for name, table in tables.items()},
        'localizedProof': text['verification'],
        'acceptedQuest': None, 'completionPredicate': None, 'routeVerified': False,
        'originalServerScriptsRecovered': False,
        'limits': [
            'No state is manufactured from static tables. Missing is not false or zero.',
            'FinishGiverID=0 and AutoShowFinish=1 do not prove automatic completion.',
            'obj_idx and step differ; logic type and entry remain original raw values.',
            'Zone centres are not movement paths; same-number matches are candidates, not proved type dispatch.',
            'Map5 tables include an elevator and manual spawns; static geometry alone cannot certify the route.',
            'Schema-less starter/finisher tables are not decoded or declared empty by this reader.',
        ],
    }


def scan_script_references(source=DEFAULT_SOURCE):
    """Search every decoded GBMP member, retaining integrity checks.

    Byte/name absence does not rule out unknown nested or encoded scripts.
    """
    needles = [b'tutorial_quest202', b'tutorial_npc972_ai',
               b'tutorial_obj188_trigger', b'tutorial_obj190_khalin_hammer']
    records = index(source); count = 0; total = 0; hits = []; lua = []
    for record in records:
        if record['path'].endswith('/'):
            continue
        raw = read_entry(record, source); count += 1; total += len(raw)
        matched = [n.decode() for n in needles if n in raw]
        if matched:
            hits.append({'path': record['path'], 'pack': record['pack'],
                         'sha256': hashlib.sha256(raw).hexdigest(), 'matches': matched})
        if b'\x1bLua' in raw[:32] or b'\x1bLJ' in raw[:32]:
            lua.append({'path': record['path'], 'pack': record['pack']})
    return {'decodedMembers': count, 'decodedBytes': total,
            'referenceContentHits': hits, 'luaMagicNearStart': lua,
            'scope': 'Every indexed GBMP file, decompressed and length/CRC checked. '
                     'Unknown encoded/nested representations remain unexcluded.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--scan-content', action='store_true')
    args = parser.parse_args(); output = local_output(args.output)
    report = audit(args.source)
    if args.scan_content:
        report['scriptContentScan'] = scan_script_references(args.source)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'output': str(output), 'steps': len(report['steps']),
                      'elevators': len(report['elevatorSpawns']),
                      'routeVerified': False, 'gameplayChanged': False}))
