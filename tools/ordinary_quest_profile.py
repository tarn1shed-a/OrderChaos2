"""Export one bounded ordinary quest for the authorized compatible executor.

Original full tables, text, icons and output stay private. Server policies below
are explicitly reconstructed; an empty script column does not prove original
server behavior. This does not read or migrate any character file.
"""
import argparse
import json
from pathlib import Path

from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from skill_attachments import decode_ftable
from skill_icons import decode_localized_names
from tutorial_map_geometry import local_output


def export_profile(source=DEFAULT_SOURCE):
    s = Sources(source)
    def rows(name, key):
        return decode_ftable(s.read('tables/' + name + '.tbl'), key)['rows']
    def one(values, **match):
        found = [r for r in values if all(r[k] == v for k, v in match.items())]
        if len(found) != 1:
            raise ValueError('Original ordinary-quest reference is not unique: ' + str(match))
        return found[0]
    quests = rows('quests', 'entry')
    q = one(quests, entry=461)
    if (q['ZoneId'], q['Type'], q['StartGiverType'], q['FinishGiverType'],
        q['StartGiverID'], q['FinishGiverID'], q['script'], q['RequiredQuest'],
        q['RequiredOneOfQuest']) != (1, 2, 1, 1, 2079, 2079, '', '0', ''):
        raise ValueError('Retrace changed ordinary-quest prerequisites/actors')
    for name in ['RequiredRaces', 'RequiredClass', 'LimitTime', 'SpecialFlags',
                 'FestivalID', 'TimeRangeBegin', 'TimeRangeEnd']:
        if q[name] != 0:
            raise ValueError('Unsupported original gate: ' + name)
    names = decode_localized_names(s.read('tables/String_Quest_zh.tbl'), 'SC')['values']
    objectives = sorted([r for r in rows('quest_objective', 'id') if r['quest_id'] == q['entry']], key=lambda r: r['step'])
    if [(r['obj_idx'], r['obj_type'], r['step'], r['value']) for r in objectives] != [(1, 2, 1, 4), (2, 6, 2, 0)]:
        raise ValueError('Unsupported original objective sequence')
    logic = [r for r in rows('quest_objective_logic', 'id') if r['quest_id'] == q['entry']]
    if sorted((r['obj_idx'], r['type'], r['entry'], r['value']) for r in logic) != [(1, 2, 467, 0), (1, 4, 50125, 1)]:
        raise ValueError('Unsupported original collection logic')
    takeback = one(rows('quest_logic_item', 'id'), quest_id=q['entry'])
    if (takeback['item_id'], takeback['count'], takeback['type'], takeback['takeback_all']) != (50125, 4, 2, 1):
        raise ValueError('Original takeback item changed')
    reward = one(rows('quest_reward_item', 'id'), quest_id=q['entry'])
    if (reward['item_id'], reward['count'], reward['type'], reward['class'], reward['event_reward']) != (20028, 1, 3, 100, 0):
        raise ValueError('Original reward row changed')
    npc = one(rows('creature_proto', 'entry'), entry=q['StartGiverID'])
    if npc['script'] or npc['quest_visible_id'] != 0:
        raise ValueError('Unsupported NPC script/visibility')
    spawn = one(rows('creature_spawns', 'id'), entry=npc['entry'], map=q['ZoneId'])
    proto = one(rows('staticobject_proto', 'entry'), entry=467)
    if proto['script'] or (proto['Type'], proto['spellid'], proto['quest_visible_id']) != (6, 15, 466):
        raise ValueError('Unsupported collection object')
    all_spawns = [r for r in rows('staticobject_spawns', 'id') if r['Entry'] == 467 and r['map'] == q['ZoneId']]
    objects = [r for r in all_spawns if r['phasing_id'] == 0]
    if len(objects) != 11 or len(all_spawns) != 14:
        raise ValueError('Retrace original phase selection')
    pos = lambda r: [r['position_x'], r['position_y'], r['position_z']]
    actor_id = 'npc:' + str(spawn['id'])
    zone = one(rows('quests_zones', 'ID'), ID=q['start_zone'])
    if zone['map_id'] != q['ZoneId'] or zone['box_orientation'] != 0:
        raise ValueError('Retrace compatible task-area entry placement')
    def item(item_id, count, **extra):
        return {'id': item_id, 'count': count,
                'icon': 'ui/icons/item/' + ('red_skull_plan.png' if item_id == 20028 else 'service_part.png'),
                'quality': 3 if item_id == 20028 else 1, 'isGem': False, **extra}
    profile = {
        'format': 'oc2-compatible-ordinary-quests-v1', 'originalServerRecovered': False,
        'mapId': q['ZoneId'], 'world': 'dawnwatch',
        'entryPosition': [zone['x']-zone['box_x']/2,zone['y'],zone['z']+zone['box_z']/2],
        'entryOrigin': 'compatible-task-area-entry-derived-from-original-start-zone-corner-not-first-spawn',
        'actors': [{'id': actor_id, 'entry': npc['entry'], 'mapId': q['ZoneId'],
                    'position': pos(spawn), 'range': 3.0,
                    'rangeOrigin': 'compatible-nearby-guard-not-original-radius'}],
        'objects': [{'id': 'object:' + str(r['id']), 'entry': r['Entry'], 'mapId': r['map'],
                     'position': pos(r), 'range': 2.0,
                     'rangeOrigin': 'compatible-nearby-guard-not-decoded-unit'} for r in objects],
        'items': {'50125': item(50125, 1), '20028': item(20028, 1)},
        'quests': [{
            'id': q['entry'], 'sourceScript': q['script'], 'sourceType': q['Type'],
            'title': names[q['Title']], 'detail': names[q['Details']],
            'objectiveText': names[q['Objectives']], 'incomplete': names[q['IncompleteText']],
            'completion': names[q['CompletionText']], 'minLevel': q['MinLevel'],
            'prerequisites': [], 'removeQuests': [int(v) for v in q['RemoveQuests'].split(',') if v],
            'startActor': actor_id, 'finishActor': actor_id,
            'collect': {'itemId': takeback['item_id'], 'count': objectives[0]['value'],
                        'sourceType': objectives[0]['obj_type'], 'sourceIndex': objectives[0]['obj_idx'],
                        'text': names[objectives[0]['text']],
                        'objectIds': ['object:' + str(r['id']) for r in objects]},
            'finishSourceType': objectives[1]['obj_type'], 'takeBackAll': True,
            'reward': {'money': q['RewMoney'], 'xp': q['RewXP'], 'favor': q['RewFavor'],
                       'items': [item(reward['item_id'], reward['count'], guaranteed=True,
                                      sourceType=reward['type'], sourceClass=reward['class'])]},
        }],
        'compatibility': {
            'authorization': 'User approved original-data-compatible execution on 2026-11-15; not recovered original server code.',
            'appearance': 'Instantiate this original phase-0 NPC; source static rows are not original runtime GUIDs or schedules.',
            'visibility': 'Show phase-0 source collection objects per character while quest collection is active; original filter 466 conditions are retained separately.',
            'collection': 'One item per distinct source object per character and accepted quest. Collection timing/respawn are not claimed recovered.',
            'reward': 'Use the one original item/count row as a fixed once-only compatible award; original type3/class100 dispatch is not claimed recovered.',
            'radius': '3/2 source scene units are explicit web proximity guards. NPC zero and static raw200 have not established original scaled radii.',
            'persistence': 'Separate atomic quest/reward ledger; never reinterpret or migrate legacy character XP/level formulas.',
            'itemIcons': 'Explicit same-key itemdisplay binding for displayid0, not a recovered original fallback branch.',
        },
        'sourceProofs': s.proofs,
    }
    return profile


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    out = local_output(args.output)
    if out.exists():
        raise ValueError('Preserve existing exports; use a new filename')
    result = export_profile(args.source)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'output': str(out), 'questIds': [r['id'] for r in result['quests']],
                      'actors': len(result['actors']), 'objects': len(result['objects']),
                      'originalServerRecovered': False}))
