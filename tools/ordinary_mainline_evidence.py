"""Join original post-tutorial task references without creating task rules.

Reports, original text and complete rows stay in analysis/raw. An empty quest
script is not a runnable-task certificate. This does not access a server/save,
choose a birth point, accept a quest or substitute text for missing dialogue.
"""
import argparse
import json
import re
from pathlib import Path

from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from skill_attachments import decode_ftable
from skill_icons import decode_localized_names
from tutorial_map_geometry import local_output

TABLES = {
    'quests': 'entry', 'quest_objective': 'id', 'quest_objective_logic': 'id',
    'quest_reward_item': 'id', 'quest_logic_item': 'id',
    'chat_menu': 'id', 'chat_menu_option': 'id', 'chat_menu_require': 'id',
    'chat_menu_display_filter': 'id', 'creature_proto': 'entry',
    'creature_spawns': 'id', 'staticobject_proto': 'entry',
    'staticobject_spawns': 'id',
}
QUESTS = (208, 447, 209, 210, 211, 212, 161, 162, 1088, 218, 461)


def id_list(raw):
    """Retain explicit references; do not interpret AND/OR/removal semantics."""
    if not isinstance(raw, str) or not re.fullmatch(r'[0-9,\s]*', raw):
        raise ValueError('Unsupported original quest-reference encoding')
    values = [int(v) for v in re.split(r'[,\s]+', raw.strip()) if v]
    if values == [0] or not values:
        return []
    if 0 in values or len(values) != len(set(values)):
        raise ValueError('Ambiguous original quest references')
    return values


def references(quests):
    edges = []
    for q in quests:
        for field in ('RequiredQuest', 'RequiredOneOfQuest'):
            for predecessor in id_list(q[field]):
                edges.append({'from': predecessor, 'to': q['entry'], 'sourceField': field})
    return edges


def objective_refs(quest_id, objectives, logic):
    selected = sorted((r for r in objectives if r['quest_id'] == quest_id),
                      key=lambda r: (r['step'], r['obj_idx']))
    indices = [r['obj_idx'] for r in selected]
    if len(set(indices)) != len(indices):
        raise ValueError('Ambiguous original objective index')
    selected_logic = [r for r in logic if r['quest_id'] == quest_id]
    return {'steps': [{'objective': r, 'logic': [v for v in selected_logic
                    if v['obj_idx'] == r['obj_idx']]} for r in selected],
            'orphanLogic': [r for r in selected_logic if r['obj_idx'] not in indices]}


def one(rows, field, value):
    matches = [r for r in rows if r[field] == value]
    if len(matches) != 1:
        raise ValueError('Original reference absent/ambiguous: '+field+'='+str(value))
    return matches[0]


def dialogue_refs(first, menus, options, requirements, strings):
    """Return static recommendations, never a simulated received ChatMenuList."""
    pending = [first]
    seen, pages, placeholders = set(), [], []
    while pending:
        ident = pending.pop(0)
        if ident in seen:
            continue
        seen.add(ident)
        menu = one(menus, 'id', ident)
        page = {'menu': menu, 'requirements': [], 'texts': [], 'options': []}
        for i in range(1, 7):
            if menu['info_'+str(i)]:
                text_id = menu['info_'+str(i)]
                text = strings.get(text_id)
                page['texts'].append({'id': text_id, 'value': text})
                if text is None or text.strip().lower() == 'test':
                    placeholders.append({'menu': ident, 'textId': text_id, 'value': text})
        if menu['info_require']:
            page['requirements'].append(one(requirements, 'id', menu['info_require']))
        for i in range(1, 7):
            option_id = menu['option_'+str(i)]
            if not option_id:
                continue
            option = one(options, 'id', option_id)
            entry = {'option': option, 'texts': [], 'requirement': None}
            required = menu['option_require_'+str(i)]
            if required:
                entry['requirement'] = one(requirements, 'id', required)
            for j in range(1, 7):
                text_id = option['random_text_'+str(j)]
                if not text_id:
                    continue
                text = strings.get(text_id)
                entry['texts'].append({'id': text_id, 'value': text})
                if text is None or text.strip().lower() == 'test':
                    placeholders.append({'option': option_id, 'textId': text_id, 'value': text})
            page['options'].append(entry)
            # References only: neither redirect nor link is executed locally.
            pending.extend(v for v in (option['link_menu'], option['redirect_menu']) if v)
        pages.append(page)
    return {'staticPages': pages, 'unavailableTextReferences': placeholders,
            'receivedMenuOrTextIdsKnown': False, 'dialogueExecutionRecovered': False}


def audit(source=DEFAULT_SOURCE):
    s = Sources(source)
    tables = {name: decode_ftable(s.read('tables/'+name+'.tbl'), key)['rows']
              for name, key in TABLES.items()}
    names = decode_localized_names(s.read('tables/String_Quest_zh.tbl'), 'SC')['values']
    strings = decode_localized_names(s.read('tables/String_Chat_Menu_zh.tbl'), 'SC')['values']
    quests = [one(tables['quests'], 'entry', q) for q in QUESTS]
    tasks = []
    for q in quests:
        refs = objective_refs(q['entry'], tables['quest_objective'], tables['quest_objective_logic'])
        actor_ids = {q['StartGiverID'], q['FinishGiverID']}
        tasks.append({'quest': q, 'localized': {field: names[q[field]] for field in
                      ('Title', 'Details', 'Objectives', 'IncompleteText', 'CompletionText')},
                      **refs,
                      'npcPrototypes': [r for r in tables['creature_proto'] if r['entry'] in actor_ids],
                      'npcSpawns': [r for r in tables['creature_spawns']
                                    if r['entry'] in actor_ids and r['map'] == q['ZoneId']],
                      'rewardItems': [r for r in tables['quest_reward_item'] if r['quest_id'] == q['entry']],
                      'logicItems': [r for r in tables['quest_logic_item'] if r['quest_id'] == q['entry']]})
    dialogue = dialogue_refs(64, tables['chat_menu'], tables['chat_menu_option'],
                             tables['chat_menu_require'], strings)
    box = one(tables['staticobject_proto'], 'entry', 202)
    return {'format': 'oc2-ordinary-mainline-continuation-evidence-v1',
            'quests': tasks, 'dependencyReferences': references(tables['quests']),
            'dialogue208': dialogue,
            'box202': {'proto': box, 'spawns': [r for r in tables['staticobject_spawns']
                                               if r['Entry'] == 202 and r['map'] == 1]},
            'dialogueDisplayFilters': [r for r in tables['chat_menu_display_filter']
                                      if r['id'] in {p['menu']['filter_id'] for p in dialogue['staticPages']}],
            'sourceProofs': s.proofs, 'originalServerRecovered': False,
            'runtimeEnabled': False, 'savesAccessed': False,
            'boundaries': [
                'References are source evidence, not reconstructed predicates or task approval.',
                'An empty quest.script does not erase object scripts, dialogue conditions or orphan references.',
                'Static chat recommendations do not prove which text IDs the original server actually sent.',
                'Quest461 has no fabricated dependency edge into this mainline. Map1 is not tutorial map5.',
                'No missing dialogue, source objective, first birth point, spawn condition or reward side effect is filled.',
            ]}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    output = local_output(args.output)
    if output.exists():
        p.error('Preserve previous evidence; choose a new private output')
    result = audit(args.source)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'output': str(output), 'quests': len(result['quests']),
                      'dialogueTextGaps': len(result['dialogue208']['unavailableTextReferences']),
                      'runtimeEnabled': False}))
